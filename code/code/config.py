import os
from pathlib import Path
from dotenv import load_dotenv


def _clean_env(value, default=""):
    if value is None:
        return default

    value = str(value).strip()
    value = value.strip('"').strip("'")
    value = value.rstrip("/")
    return value or default


BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=False)

OUTPUT_DIR = BASE_DIR / "output"
RAW_JSON_DIR = BASE_DIR / "raw_json"
LOG_DIR = BASE_DIR / "logs"
SAMPLE_DATA_DIR = BASE_DIR / "sample_data"

for path in [OUTPUT_DIR, RAW_JSON_DIR, LOG_DIR, SAMPLE_DATA_DIR]:
    path.mkdir(parents=True, exist_ok=True)

BASE_URL = _clean_env(os.getenv("FUSION_BASE_URL", "https://qa.fusion.live/w/api"))
FUSION_USERNAME = _clean_env(os.getenv("FUSION_USERNAME", ""))
FUSION_PASSWORD = _clean_env(os.getenv("FUSION_PASSWORD", ""))
FUSION_CLIENT_TYPE = _clean_env(os.getenv("FUSION_CLIENT_TYPE", "web"))

OUTPUT_CSV = OUTPUT_DIR / "fusionlive_dashboard_data.csv"
OUTPUT_FEATURES = OUTPUT_DIR / "feature_usage.csv"
OUTPUT_ADOPTION = OUTPUT_DIR / "customer_feature_adoption.csv"
OUTPUT_WORKSPACES = OUTPUT_DIR / "workspaces.csv"
OUTPUT_USERS = OUTPUT_DIR / "users.csv"
OUTPUT_COMPANIES = OUTPUT_DIR / "companies.csv"
OUTPUT_FULL = OUTPUT_DIR / "fusionlive_full_dataset.csv"
OUTPUT_WORKSPACE_MODULES = OUTPUT_DIR / "workspace_modules.csv"
OUTPUT_WORKSPACE_FEATURE = OUTPUT_DIR / "workspace_feature_fact.csv"
DB_PATH = BASE_DIR / "dashboard.db"
WORKSPACE_MODULE_REQUEST_DELAY = float(os.getenv("WORKSPACE_MODULE_REQUEST_DELAY", "0.1"))
WORKSPACE_MODULE_CONCURRENCY = int(os.getenv("WORKSPACE_MODULE_CONCURRENCY", "5"))
