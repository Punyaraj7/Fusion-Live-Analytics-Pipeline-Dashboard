# Data Accuracy Verification Note

**Date:** 2026-09-21
**Verified by:** Punyaraj Sonawane
**Scope:** Cross-check of KPI metrics produced by `transform.build_dashboard_dataset()` against
the raw source data pulled from the FusionLive API (`raw_json/*.json`, captured 2026-09-17 15:28).

## Method

For each metric, the raw JSON payload was independently parsed (counting records and status
values with a plain Python script), then compared against the same value produced by re-running
the project's own transform logic (`transform.build_dashboard_dataset`) on the identical raw
payloads. The two independent computations were required to agree before a metric was accepted
as correct.

## Metrics checked

| Metric | Definition (from `transform.py`) | Independent count from raw JSON | `build_dashboard_dataset()` output | Match |
|---|---|---|---|---|
| Active Customers | companies where `statusCode` == `ACTIVE` (case-insensitive) | 957 / 957 companies are `ACTIVE` | 957 | Yes |
| Active Workspaces | workspaces where `statusCode` == `LIVE` (case-insensitive) | 433 `Live`, 62 `Offline`, 97 `Rollout` (592 total) | 433 | Yes |
| Active Users | users where `status` == `ACTIVE USER` (case-insensitive) | 2625 `Active User`, 92 `Barred User` (2717 total) | 2625 | Yes |

**Conclusion:** the extraction/metric-calculation logic in `transform.py` is correct — all three
metrics recomputed from raw source data match what the code produces when run directly against
`raw_json/*.json`.

## Discrepancy found (and root cause)

The values above do **not** match what is currently sitting in `output/fusionlive_dashboard_data.csv`,
`output/companies.csv`, `output/users.csv`, and `output/workspaces.csv` on disk:

| File | Current on-disk content | Expected |
|---|---|---|
| `output/fusionlive_dashboard_data.csv` | 1 row: `Active Customers,2` | 3 rows: `957 / 433 / 2625` |
| `output/companies.csv` | 1 row: `Acme` | 957 companies |
| `output/users.csv` | 1 row: `Alice Brown` | 2717 users |
| `output/workspaces.csv` | 1 row: `WS1` | 592 workspaces |

**Root cause:** `load.save_outputs()` ([load.py:99-106](load.py#L99)) writes the summary, feature,
adoption, workspaces, users, companies and full-dataset CSVs to hardcoded paths imported from
`config.py` (`OUTPUT_CSV`, `OUTPUT_WORKSPACES`, `OUTPUT_USERS`, `OUTPUT_COMPANIES`, `OUTPUT_FULL`,
etc.). Only the SQLite `db_path` argument is overridable by callers/tests — the CSV destinations
are not. `tests/test_etl.py::test_save_outputs_writes_sqlite_database` and
`test_save_outputs_removes_stale_sqlite_journal_before_writing` call `save_outputs()` with dummy
fixture rows (e.g. `"Alice Brown"`, `"WS1"`, `"Acme"`) and a `tmp_path` DB, but that dummy data is
still written straight into the real `output/*.csv` files. Every `pytest` run therefore silently
overwrites the production CSV outputs with test fixtures. This was reproduced directly: the
`output/*.csv` files carry a `21-09-2026 12:55:56` timestamp (matching the pytest run performed in
this session) while `raw_json/*.json` and the untouched `output/workspace_modules.csv` /
`workspace_feature_fact.csv` retain their original `17-09-2026` ETL timestamps.

**Fix required (not yet applied):** parameterize `save_outputs()`'s CSV destinations the same way
`db_path` already is (e.g. accept an `output_dir`/explicit path kwargs, defaulting to the `config`
values), and have the tests write to `tmp_path` for CSVs as well, so test runs can no longer
mutate real ETL output.

## Summary

- Extraction and metric-calculation logic: **verified correct** (3/3 metrics match independent recount).
- Current files in `output/`: **not trustworthy** — they reflect the last `pytest` run, not the last real ETL run against `raw_json/`.
- Action item: fix `save_outputs()` path handling, then re-run `main.py` to regenerate clean `output/*.csv` files before they're used for reporting.
