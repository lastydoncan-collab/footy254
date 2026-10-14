from database.db_config import get_connection

conn = get_connection()

cur = conn.cursor()

cur.execute("""
SELECT
    COUNT(*)
FROM fixtures
WHERE status='FINISHED';
""")

print(cur.fetchone())

cur.execute("""
SELECT
    match_id,
    home_team,
    away_team,
    score_home,
    score_away
FROM fixtures
LIMIT 5;
""")

for row in cur.fetchall():
    print(row)

conn.close()