import sqlite3

conn = sqlite3.connect('dashboard.db')
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
print(cur.fetchall())
for table in ['summary', 'features', 'adoption', 'workspaces', 'users', 'companies', 'full_dataset']:
    cur.execute(f'SELECT COUNT(*) FROM "{table}"')
    print(table, cur.fetchone()[0])
conn.close()
