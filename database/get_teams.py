from database.db_config import get_connection


def get_all_teams():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT DISTINCT home_team
        FROM matches

        UNION

        SELECT DISTINCT away_team
        FROM matches

        ORDER BY home_team
    """)

    teams = [row[0] for row in cur.fetchall()]

    cur.close()
    conn.close()

    return teams