import json
from auth import get_token
from api import get_workspaces, get_users, get_companies, get_workspace_modules
from config import RAW_JSON_DIR, FUSION_USERNAME, FUSION_PASSWORD, ENV_PATH, WORKSPACE_MODULE_REQUEST_DELAY
from workspace_modules_etl import fetch_all_workspace_modules, build_fact_dataframe
import logging
import time


def save_json(name, payload):
    path = RAW_JSON_DIR / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"Saved raw JSON to {path}")


def main():
    has_live_credentials = bool(FUSION_USERNAME and FUSION_PASSWORD)
    print(f"Using env file: {ENV_PATH}")
    print(f"Credentials detected: username={bool(FUSION_USERNAME)}, password={bool(FUSION_PASSWORD)}")

    if not has_live_credentials:
        raise RuntimeError("Live credentials are missing. Set FUSION_USERNAME and FUSION_PASSWORD in the environment before running the ETL.")

    try:
        token = get_token()
        workspaces_payload = get_workspaces(token)
        users_payload = get_users(token)
        companies_payload = get_companies(token)
        print("Live data fetched successfully")
    except Exception as exc:
        raise RuntimeError(f"Live data fetch failed: {exc}") from exc

    save_json("workspaces", workspaces_payload)
    save_json("users", users_payload)
    save_json("companies", companies_payload)

    # Fetch workspace modules for all workspaces (use robust fetch with retries and throttling)
    from transform import build_dashboard_dataset, build_full_dataset, build_workspace_table, build_user_table, build_company_table, build_workspace_modules_table
    workspaces_df = build_workspace_table(workspaces_payload)
    # prepare workspace list for fetcher
    if isinstance(workspaces_payload, dict) and "data" in workspaces_payload:
        workspace_list = workspaces_payload["data"]
    elif isinstance(workspaces_payload, list):
        workspace_list = workspaces_payload
    else:
        workspace_list = workspaces_df.to_dict(orient="records")

    logger = logging.getLogger("workspace_modules_etl")
    rows = fetch_all_workspace_modules(token, workspace_list, logger)
    combined_payload = {"data": rows}
    save_json("workspace_modules", combined_payload)

    from load import save_outputs

    summary_df, feature_df, adoption_df = build_dashboard_dataset(
        workspaces_payload,
        users_payload,
        companies_payload,
    )
    
    users_df = build_user_table(users_payload)
    companies_df = build_company_table(companies_payload)
    full_df = build_full_dataset(
        workspaces_payload,
        users_payload,
        companies_payload,
    )
    workspace_modules_df = build_workspace_modules_table(combined_payload)
    workspace_feature_df = build_fact_dataframe(rows)
    save_outputs(
        summary_df,
        feature_df,
        adoption_df,
        full_df=full_df,
        workspaces_df=workspaces_df,
        workspace_modules_df=workspace_modules_df,
        workspace_feature_df=workspace_feature_df,
        users_df=users_df,
        companies_df=companies_df,
    )
    print("ETL completed successfully")


if __name__ == "__main__":
    main()
