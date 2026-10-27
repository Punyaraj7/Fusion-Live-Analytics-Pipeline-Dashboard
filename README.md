Fusion Live Analytics Pipeline

End-to-end pipeline that pulls Fusion Live platform data from the REST API, processes it, and loads it into a SQLite database. A Power BI dashboard on top of the database tracks workspace status, user activity and module adoption.

Pipeline
Fusion Live API (JSON) → CSV → SQLite → Power BI

Python pulls the data from the API, flattens it to CSV and loads it into SQLite. Power BI then builds the model and visuals on top.

Dashboard
Page	Insights
Workspace Overview	Active, rollout, offline and expired workspaces; top owners; creation trend
Companies	Company types, system types, SSO/MFA coverage
Users	Active, inactive and barred users by company
Module Adoption	Modules enabled per workspace and per module
Adoption Tiers	Core (40%+), moderate (10–40%), low (<10%) and dormant (≤2%) modules
Workspace × Module	Enabled/disabled heatmap
Workspace × Feature Type	Adoption by feature family
Module Co-occurrence	Which modules are enabled together
Key Definitions
Active workspace: status Live and end date not yet passed.
Active user: not barred, and logged in within the last 60 days.
Adoption %: enabled workspace × module combinations ÷ total combinations.
Tech Stack

Python · Pandas · Requests · SQLite · Power BI · DAX · Power Query

Security
API credentials are stored in .env, which is never committed.
Real data (*.db, *.csv, raw JSON) is excluded via .gitignore.
The dashboard is shared as a .pbit template, which contains no data.
Roadmap
Scheduled refresh
Cloud database (SQL Server / Fabric)
Historical trend tracking
