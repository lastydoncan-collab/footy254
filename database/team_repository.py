import logging

from database.db_config import get_connection

logger = logging.getLogger(__name__)


# ==========================================================
# GET ALL TEAMS
# ==========================================================

def get_all_teams():
    """
    Returns every unique team appearing in the fixtures table.

    The fixtures table is the single source of truth for both
    historical and upcoming matches.
    """

    query = """
        SELECT DISTINCT team_name
        FROM
        (
            SELECT home_team AS team_name
            FROM fixtures

            UNION

            SELECT away_team AS team_name
            FROM fixtures
        ) teams

        WHERE team_name IS NOT NULL
          AND team_name <> ''

        ORDER BY team_name;
    """

    try:

        with get_connection() as conn:

            with conn.cursor() as cur:

                cur.execute(query)

                rows = cur.fetchall()

        teams = []

        for row in rows:

            if isinstance(row, dict):

                teams.append(row["team_name"])

            else:

                teams.append(row[0])

        logger.info(
            "Loaded %d teams.",
            len(teams),
        )

        return teams

    except Exception:

        logger.exception(
            "Failed loading teams."
        )

        return []