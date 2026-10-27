import json
import os
import sqlite3
import time
from pathlib import Path

import pandas as pd

from config import (
    OUTPUT_ADOPTION,
    OUTPUT_COMPANIES,
    OUTPUT_CSV,
    OUTPUT_FEATURES,
    OUTPUT_FULL,
    OUTPUT_USERS,
    OUTPUT_WORKSPACES,
    OUTPUT_WORKSPACE_MODULES,
    OUTPUT_WORKSPACE_FEATURE,
    DB_PATH,
)


def _clear_stale_sqlite_locks(db_path):
    if db_path is None:
        return

    lock_files = [
        Path(str(db_path) + "-journal"),
        Path(str(db_path) + "-wal"),
        Path(str(db_path) + "-shm"),
    ]
    for lock_file in lock_files:
        if lock_file.exists():
            try:
                lock_file.unlink()
            except OSError:
                pass


def _connect_sqlite(db_path, timeout_seconds=60):
    _clear_stale_sqlite_locks(db_path)
    conn = sqlite3.connect(db_path, timeout=timeout_seconds)
    conn.execute("PRAGMA busy_timeout = 60000")
    return conn


def _ensure_sqlite_table(conn, table_name, df):
    if df.empty:
        return

    columns = list(df.columns)
    column_defs = []
    for column in columns:
        dtype = df[column].dtype
        if pd.api.types.is_integer_dtype(dtype):
            sqlite_type = "INTEGER"
        elif pd.api.types.is_float_dtype(dtype):
            sqlite_type = "REAL"
        elif pd.api.types.is_bool_dtype(dtype):
            sqlite_type = "INTEGER"
        else:
            sqlite_type = "TEXT"
        column_defs.append(f'"{column}" {sqlite_type}')

    conn.execute(f'CREATE TABLE IF NOT EXISTS "{table_name}" ({", ".join(column_defs)})')


def _sanitize_value(value):
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if pd.isna(value):
        return None
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _prepare_dataframe_for_sql(df):
    if df is None:
        return None

    prepared_df = df.copy()
    for column in prepared_df.columns:
        prepared_df[column] = prepared_df[column].apply(_sanitize_value)
    return prepared_df


def _replace_table(conn, table_name, df):
    if df is None:
        return

    prepared_df = _prepare_dataframe_for_sql(df)
    conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
    prepared_df.to_sql(table_name, conn, if_exists="fail", index=False)


def save_outputs(summary_df, feature_df, adoption_df, full_df=None, workspaces_df=None, workspace_modules_df=None, workspace_feature_df=None, users_df=None, companies_df=None, db_path=None):
    output_dir = Path(OUTPUT_CSV).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_df.to_csv(OUTPUT_CSV, index=False)
    feature_df.to_csv(OUTPUT_FEATURES, index=False)
    adoption_df.to_csv(OUTPUT_ADOPTION, index=False)

    if workspaces_df is not None:
        workspaces_df.to_csv(OUTPUT_WORKSPACES, index=False)
        print(f"Saved workspaces to {OUTPUT_WORKSPACES}")
    if workspace_modules_df is not None and not workspace_modules_df.empty:
        workspace_modules_df.to_csv(OUTPUT_WORKSPACE_MODULES, index=False)
        print(f"Saved workspace modules to {OUTPUT_WORKSPACE_MODULES}")
    if workspace_feature_df is not None and not workspace_feature_df.empty:
        workspace_feature_df.to_csv(OUTPUT_WORKSPACE_FEATURE, index=False)
        print(f"Saved workspace feature fact to {OUTPUT_WORKSPACE_FEATURE}")
    else:
        print("No workspace modules to save (skipping CSV)")
    if users_df is not None:
        users_df.to_csv(OUTPUT_USERS, index=False)
        print(f"Saved users to {OUTPUT_USERS}")
    if companies_df is not None:
        companies_df.to_csv(OUTPUT_COMPANIES, index=False)
        print(f"Saved companies to {OUTPUT_COMPANIES}")
    if full_df is not None:
        full_df.to_csv(OUTPUT_FULL, index=False)
        print(f"Saved full dataset to {OUTPUT_FULL}")

    print(f"Saved KPIs to {OUTPUT_CSV}")
    print(f"Saved features to {OUTPUT_FEATURES}")
    print(f"Saved adoption matrix to {OUTPUT_ADOPTION}")

    target_db_path = Path(db_path) if db_path is not None else DB_PATH
    target_db_path.parent.mkdir(parents=True, exist_ok=True)

    last_lock_error = None
    for attempt in range(3):
        conn = _connect_sqlite(target_db_path)
        try:
            if summary_df is not None:
                _replace_table(conn, "summary", summary_df)
            if feature_df is not None:
                _replace_table(conn, "features", feature_df)
            if adoption_df is not None:
                _replace_table(conn, "adoption", adoption_df)
            if workspaces_df is not None:
                _replace_table(conn, "workspaces", workspaces_df)
            if workspace_modules_df is not None and not workspace_modules_df.empty:
                _replace_table(conn, "workspace_modules", workspace_modules_df)
            else:
                print("No workspace modules to write to DB (skipping table replace)")
            if workspace_feature_df is not None and not workspace_feature_df.empty:
                _replace_table(conn, "workspace_feature_fact", workspace_feature_df)
            else:
                print("No workspace feature fact rows to write to DB (skipping table replace)")
            if users_df is not None:
                _replace_table(conn, "users", users_df)
            if companies_df is not None:
                _replace_table(conn, "companies", companies_df)
            if full_df is not None:
                _replace_table(conn, "full_dataset", full_df)
            conn.commit()
            print(f"Saved ETL data to SQLite database at {target_db_path}")
            return
        except sqlite3.OperationalError as exc:
            last_lock_error = exc
            if "locked" in str(exc).lower() and attempt < 2:
                _clear_stale_sqlite_locks(target_db_path)
                time.sleep(2 * (attempt + 1))
                continue
            raise
        finally:
            conn.close()

    if last_lock_error is not None:
        raise last_lock_error
