import json
from pathlib import Path
import pandas as pd


def normalize_payload(payload):
    if isinstance(payload, dict):
        data = payload.get("data", payload)
        if isinstance(data, dict):
            if "workspaces" in data and isinstance(data["workspaces"], list):
                return data["workspaces"]
            if "users" in data and isinstance(data["users"], list):
                return data["users"]
            if "companies" in data and isinstance(data["companies"], list):
                return data["companies"]
        if isinstance(data, list):
            return data
    return []


def normalize_generic(payload):
    if isinstance(payload, dict):
        data = payload.get("data", payload)
        if isinstance(data, dict):
            if "modules" in data and isinstance(data["modules"], list):
                return data["modules"]
            if "items" in data and isinstance(data["items"], list):
                return data["items"]
            for value in data.values():
                if isinstance(value, list):
                    return value
            return []
        if isinstance(data, list):
            return data
    if isinstance(payload, list):
        return payload
    return []


def _flatten_value(value):
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    return value


def build_workspace_table(workspaces_payload):
    ws = normalize_payload(workspaces_payload)
    if ws:
        df_workspaces = pd.DataFrame(ws)
        if "id" in df_workspaces.columns:
            df_workspaces["workspace_id"] = df_workspaces["id"]
        if "name" in df_workspaces.columns:
            df_workspaces["workspace_name"] = df_workspaces["name"]
        if "statusCode" in df_workspaces.columns:
            df_workspaces["status_code"] = df_workspaces["statusCode"]
        if "owningCompany" in df_workspaces.columns:
            df_workspaces["owning_company_name"] = df_workspaces["owningCompany"].apply(
                lambda x: _flatten_value(x.get("label") if isinstance(x, dict) else x)
            )
        if "createdBy" in df_workspaces.columns:
            df_workspaces["created_by_name"] = df_workspaces["createdBy"].apply(
                lambda x: _flatten_value(x.get("label") if isinstance(x, dict) else x)
            )
        return df_workspaces
    return pd.DataFrame(columns=["workspace_id", "workspace_name", "status_code", "owning_company_name", "created_by_name"])


def build_user_table(users_payload):
    us = normalize_payload(users_payload)
    if us:
        df_users = pd.DataFrame(us)
        if "id" in df_users.columns:
            df_users["user_id"] = df_users["id"]
        if "firstName" in df_users.columns and "lastName" in df_users.columns:
            df_users["full_name"] = df_users["firstName"].fillna("") + " " + df_users["lastName"].fillna("")
        if "companyName" in df_users.columns:
            df_users["company_name"] = df_users["companyName"]
        if "status" in df_users.columns:
            df_users["user_status"] = df_users["status"]
        return df_users
    return pd.DataFrame(columns=["user_id", "full_name", "company_name", "user_status"])


def build_company_table(companies_payload):
    cs = normalize_payload(companies_payload)
    if cs:
        df_companies = pd.DataFrame(cs)
        if "id" in df_companies.columns:
            df_companies["company_id"] = df_companies["id"]
        if "name" in df_companies.columns:
            df_companies["company_name"] = df_companies["name"]
        if "statusCode" in df_companies.columns:
            df_companies["company_status"] = df_companies["statusCode"]
        return df_companies
    return pd.DataFrame(columns=["company_id", "company_name", "company_status"])


def build_workspace_modules_table(modules_payload, workspace_id=None):
    modules = normalize_generic(modules_payload)
    if modules:
        df = pd.DataFrame(modules)
        # Map known field names from the API response to canonical column names
        if "moduleId" in df.columns:
            df["module_id"] = df["moduleId"]
        elif "id" in df.columns:
            df["module_id"] = df["id"]
        if "moduleName" in df.columns:
            df["module_name"] = df["moduleName"]
        elif "name" in df.columns:
            df["module_name"] = df["name"]
        if "moduleKey" in df.columns:
            df["module_key"] = df["moduleKey"]
        if "type" in df.columns:
            df["module_type"] = df["type"]
        if "enabled" in df.columns:
            df["enabled"] = df["enabled"]
        if "activeConfigModuleId" in df.columns:
            df["active_config_module_id"] = df["activeConfigModuleId"]
        if "parentModuleId" in df.columns:
            df["parent_module_id"] = df["parentModuleId"]
        if "sortOrder" in df.columns:
            df["sort_order"] = df["sortOrder"]
        # add workspace_id if provided
        if workspace_id is not None:
            df["workspace_id"] = workspace_id

        # flatten nested structures
        for col in df.columns:
            if df[col].apply(lambda x: isinstance(x, (dict, list))).any():
                df[col] = df[col].apply(lambda v: _flatten_value(v))
        # Keep a stable column order for outputs
        preferred = [
            "workspace_id",
            "module_id",
            "module_key",
            "module_name",
            "module_type",
            "enabled",
            "active_config_module_id",
            "parent_module_id",
            "sort_order",
        ]
        existing = [c for c in preferred if c in df.columns]
        other = [c for c in df.columns if c not in existing]
        return df[existing + other]

    return pd.DataFrame(columns=["module_id", "module_name", "module_type", "workspace_id"])


def build_full_dataset(workspaces_payload, users_payload, companies_payload):
    ws = normalize_payload(workspaces_payload)
    us = normalize_payload(users_payload)
    cs = normalize_payload(companies_payload)

    if ws:
        df_workspaces = pd.DataFrame(ws)
        if "id" in df_workspaces.columns:
            df_workspaces["workspace_id"] = df_workspaces["id"]
        if "name" in df_workspaces.columns:
            df_workspaces["workspace_name"] = df_workspaces["name"]
        if "statusCode" in df_workspaces.columns:
            df_workspaces["status_code"] = df_workspaces["statusCode"]
        if "owningCompany" in df_workspaces.columns:
            df_workspaces["owning_company_name"] = df_workspaces["owningCompany"].apply(
                lambda x: _flatten_value(x.get("label") if isinstance(x, dict) else x)
            )
        if "createdBy" in df_workspaces.columns:
            df_workspaces["created_by_name"] = df_workspaces["createdBy"].apply(
                lambda x: _flatten_value(x.get("label") if isinstance(x, dict) else x)
            )
        df_workspaces["entity_type"] = "workspace"
    else:
        df_workspaces = pd.DataFrame(columns=["entity_type", "workspace_id", "workspace_name", "status_code", "owning_company_name", "created_by_name"])

    if us:
        df_users = pd.DataFrame(us)
        if "id" in df_users.columns:
            df_users["user_id"] = df_users["id"]
        if "firstName" in df_users.columns and "lastName" in df_users.columns:
            df_users["full_name"] = df_users["firstName"].fillna("") + " " + df_users["lastName"].fillna("")
        if "companyName" in df_users.columns:
            df_users["company_name"] = df_users["companyName"]
        if "status" in df_users.columns:
            df_users["user_status"] = df_users["status"]
        df_users["entity_type"] = "user"
    else:
        df_users = pd.DataFrame(columns=["entity_type", "user_id", "full_name", "company_name", "user_status"])

    if cs:
        df_companies = pd.DataFrame(cs)
        if "id" in df_companies.columns:
            df_companies["company_id"] = df_companies["id"]
        if "name" in df_companies.columns:
            df_companies["company_name"] = df_companies["name"]
        if "statusCode" in df_companies.columns:
            df_companies["company_status"] = df_companies["statusCode"]
        df_companies["entity_type"] = "company"
    else:
        df_companies = pd.DataFrame(columns=["entity_type", "company_id", "company_name", "company_status"])

    full_rows = []
    for _, row in df_workspaces.iterrows():
        full_rows.append({
            "entity_type": row.get("entity_type", "workspace"),
            "workspace_id": row.get("workspace_id"),
            "workspace_name": row.get("workspace_name"),
            "status_code": row.get("status_code"),
            "owning_company_name": row.get("owning_company_name"),
            "created_by_name": row.get("created_by_name"),
            "user_id": None,
            "full_name": None,
            "company_name": None,
            "user_status": None,
            "company_id": None,
            "company_status": None,
        })
    for _, row in df_users.iterrows():
        full_rows.append({
            "entity_type": row.get("entity_type", "user"),
            "workspace_id": None,
            "workspace_name": None,
            "status_code": None,
            "owning_company_name": None,
            "created_by_name": None,
            "user_id": row.get("user_id"),
            "full_name": row.get("full_name"),
            "company_name": row.get("company_name"),
            "user_status": row.get("user_status"),
            "company_id": None,
            "company_status": None,
        })
    for _, row in df_companies.iterrows():
        full_rows.append({
            "entity_type": row.get("entity_type", "company"),
            "workspace_id": None,
            "workspace_name": None,
            "status_code": None,
            "owning_company_name": None,
            "created_by_name": None,
            "user_id": None,
            "full_name": None,
            "company_name": row.get("company_name"),
            "user_status": None,
            "company_id": row.get("company_id"),
            "company_status": row.get("company_status"),
        })

    return pd.DataFrame(full_rows)


def build_dashboard_dataset(workspaces_payload, users_payload, companies_payload):
    ws = normalize_payload(workspaces_payload)
    us = normalize_payload(users_payload)
    cs = normalize_payload(companies_payload)

    df_workspaces = pd.DataFrame(ws)
    df_users = pd.DataFrame(us)
    df_companies = pd.DataFrame(cs)

    if "id" in df_workspaces.columns:
        df_workspaces["workspace_id"] = df_workspaces["id"]
    if "name" in df_workspaces.columns:
        df_workspaces["workspace_name"] = df_workspaces["name"]
    if "statusCode" in df_workspaces.columns:
        df_workspaces["status_code"] = df_workspaces["statusCode"]
    if "owningCompany" in df_workspaces.columns:
        df_workspaces["owning_company_name"] = df_workspaces["owningCompany"].apply(
            lambda x: _flatten_value(x.get("label") if isinstance(x, dict) else x)
        )

    if "id" in df_users.columns:
        df_users["user_id"] = df_users["id"]
    if "firstName" in df_users.columns and "lastName" in df_users.columns:
        df_users["full_name"] = df_users["firstName"].fillna("") + " " + df_users["lastName"].fillna("")
    if "companyName" in df_users.columns:
        df_users["company_name"] = df_users["companyName"]

    if "id" in df_companies.columns:
        df_companies["company_id"] = df_companies["id"]
    if "name" in df_companies.columns:
        df_companies["company_name"] = df_companies["name"]

    # Build KPI summary rows from the incoming data only.
    active_companies = len(df_companies[df_companies["statusCode"].astype(str).str.upper() == "ACTIVE"]) if "statusCode" in df_companies.columns else len(df_companies)
    active_workspaces = len(df_workspaces[df_workspaces["statusCode"].astype(str).str.upper() == "LIVE"]) if "statusCode" in df_workspaces.columns else len(df_workspaces)
    active_users = len(df_users[df_users["status"].astype(str).str.upper() == "ACTIVE USER"]) if "status" in df_users.columns else len(df_users)

    summary_rows = [
        {"metric_name": "Active Customers", "metric_value": active_companies, "metric_type": "kpi", "month": "Current"},
        {"metric_name": "Active Workspaces", "metric_value": active_workspaces, "metric_type": "kpi", "month": "Current"},
        {"metric_name": "Active Users", "metric_value": active_users, "metric_type": "kpi", "month": "Current"},
    ]
    summary_df = pd.DataFrame(summary_rows)

    feature_df = pd.DataFrame(columns=["feature", "area", "unique_users", "month", "mom", "trend"])
    adoption_df = pd.DataFrame(columns=["customer", "Document Search", "Workspaces", "Briefcase", "Module Config", "Stamp Templates"])

    return summary_df, feature_df, adoption_df
