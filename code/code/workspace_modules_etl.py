import os
import time
import json
import logging
from datetime import datetime

import pandas as pd

from auth import get_token
import api
from transform import build_workspace_modules_table
from config import OUTPUT_DIR, RAW_JSON_DIR, WORKSPACE_MODULE_REQUEST_DELAY, WORKSPACE_MODULE_CONCURRENCY
from concurrent.futures import ThreadPoolExecutor, as_completed


LOG_PATH = os.path.join(os.path.dirname(__file__), "logs", "workspace_modules_etl.log")


def setup_logging():
    logger = logging.getLogger("workspace_modules_etl")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        fh = logging.FileHandler(LOG_PATH)
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        logger.addHandler(sh)
    return logger


def normalize_workspaces_payload(payload):
    # payload from api.get_workspaces returns {'data': [...]}
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return data
    if isinstance(payload, list):
        return payload
    return []


def map_workspace_row(ws):
    # Accept a few possible key names
    wid = ws.get("workspaceId") or ws.get("id") or ws.get("workspace_id")
    name = ws.get("workspaceName") or ws.get("name") or ws.get("workspace_name")
    return int(wid) if wid is not None else None, name


def fetch_all_workspace_modules(token, workspaces, logger, delay=WORKSPACE_MODULE_REQUEST_DELAY, retries=3):
    # If concurrency is 1 or less, run sequentially (original behaviour)
    concurrency = WORKSPACE_MODULE_CONCURRENCY or 1
    rows = []
    total = len(workspaces)

    def fetch_for_workspace(idx, ws):
        wid, wname = map_workspace_row(ws)
        if wid is None:
            logger.warning("Skipping workspace with no id: %s", ws)
            return []
        logger.info("[%d/%d] Fetching modules for workspace %s (%s)", idx, total, wid, wname)
        attempt = 0
        payload = None
        while attempt < retries:
            attempt += 1
            try:
                payload = api.get_workspace_modules(token, wid)
                break
            except Exception as exc:
                logger.warning("Attempt %d failed for workspace %s: %s", attempt, wid, exc)
                time.sleep(2 ** attempt)
        if payload is None:
            logger.error("Failed to fetch modules for workspace %s after %d attempts", wid, retries)
            return []

        data = payload.get("data") if isinstance(payload, dict) else payload if isinstance(payload, list) else []
        if not data:
            logger.info("No modules found for workspace %s", wid)
            return []

        # ensure workspace_id and name in each item
        for item in data:
            if isinstance(item, dict):
                item.setdefault("workspace_id", wid)
                item.setdefault("workspace_name", wname)

        # Respect per-thread delay
        if delay and delay > 0:
            time.sleep(delay)

        return data

    if concurrency <= 1:
        # fallback to original sequential loop
        for idx, ws in enumerate(workspaces, start=1):
            rows.extend(fetch_for_workspace(idx, ws))
        return rows

    # Concurrent fetching with thread pool
    futures = {}
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        for idx, ws in enumerate(workspaces, start=1):
            futures[ex.submit(fetch_for_workspace, idx, ws)] = idx

        for fut in as_completed(futures):
            try:
                data = fut.result()
                if data:
                    rows.extend(data)
            except Exception as exc:
                logger.exception("Unhandled exception fetching workspace (future): %s", exc)

    return rows


def build_fact_dataframe(rows):
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    # Map fields to canonical schema
    mapping = {
        "workspace_id": "workspace_id",
        "workspace_name": "workspace_name",
        "moduleId": "module_id",
        "moduleId": "module_id",
        "moduleName": "module_name",
        "moduleKey": "module_key",
        "enabled": "enabled",
        "activeConfigModuleId": "active_config_module_id",
        "parentModuleId": "parent_module_id",
        "sortOrder": "sort_order",
    }

    # Create canonical columns where possible
    out = pd.DataFrame()
    out["workspace_id"] = df.get("workspace_id")
    out["workspace_name"] = df.get("workspace_name")
    out["module_key"] = df.get("moduleKey")
    out["module_name"] = df.get("moduleName")
    out["enabled"] = df.get("enabled")
    out["active_config_module_id"] = df.get("activeConfigModuleId")
    out["parent_module_id"] = df.get("parentModuleId")
    out["sort_order"] = df.get("sortOrder")

    out["load_datetime"] = datetime.utcnow()
    return out


def save_csv_and_maybe_db(df, csv_path, logger):
    if df is None or df.empty:
        logger.info("No workspace feature rows to save")
        return False
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    df.to_csv(csv_path, index=False)
    logger.info("Saved CSV to %s (rows=%d)", csv_path, len(df))

    # Optional SQL Server load if SQLALCHEMY_DB_URI provided
    db_uri = os.getenv("SQLALCHEMY_DB_URI")
    if not db_uri:
        logger.info("No SQLALCHEMY_DB_URI provided — skipping DB load")
        return True

    try:
        from sqlalchemy import create_engine, text
    except Exception as exc:
        logger.error("SQLAlchemy not available: %s — install sqlalchemy and a pyodbc driver to enable DB load", exc)
        return True

    engine = create_engine(db_uri)
    table_name = "workspace_feature_fact"
    try:
        # Write via pandas to_sql (replace) — for production consider staging + MERGE
        df.to_sql(table_name, engine, if_exists="replace", index=False)
        logger.info("Wrote %d rows to table %s", len(df), table_name)
    except Exception as exc:
        logger.exception("Failed to write to DB: %s", exc)
        return False

    return True


def main():
    logger = setup_logging()
    logger.info("Starting workspace modules ETL")

    try:
        token = get_token()
    except Exception as exc:
        logger.exception("Failed to get auth token: %s", exc)
        return

    try:
        workspaces_payload = api.get_workspaces(token)
    except Exception as exc:
        logger.exception("Failed to fetch workspaces: %s", exc)
        return

    workspaces = normalize_workspaces_payload(workspaces_payload)
    logger.info("Found %d workspaces", len(workspaces))

    rows = fetch_all_workspace_modules(token, workspaces, logger)

    # Save combined raw JSON
    os.makedirs(RAW_JSON_DIR, exist_ok=True)
    combined_path = os.path.join(RAW_JSON_DIR, "workspace_modules.json")
    with open(combined_path, "w", encoding="utf-8") as f:
        json.dump({"data": rows}, f, ensure_ascii=False, indent=2)
    logger.info("Saved combined raw JSON to %s", combined_path)

    df = build_fact_dataframe(rows)
    csv_path = os.path.join(OUTPUT_DIR, "workspace_feature_fact.csv")
    save_csv_and_maybe_db(df, csv_path, logger)

    logger.info("ETL finished")


if __name__ == "__main__":
    main()
