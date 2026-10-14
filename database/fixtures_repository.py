import logging

from database.db_config import get_connection

logger = logging.getLogger(__name__)


# ==========================================================
# PREDICTION WINDOW
# ==========================================================

PREDICTION_WINDOW_DAYS = 30

# ==========================================================
# UPSERT SQL
# ==========================================================

UPSERT_SQL = """
INSERT INTO fixtures
(
    match_id,
    competition_id,
    competition,
    competition_code,
    season,
    matchday,
    stage,
    home_team_id,
    away_team_id,
    home_team,
    away_team,
    utc_date,
    match_date,
    kickoff_time,
    kickoff,
    status,
    score_home,
    score_away,
    winner,
    last_updated
)

VALUES
(
    %(match_id)s,
    %(competition_id)s,
    %(competition)s,
    %(competition_code)s,
    %(season)s,
    %(matchday)s,
    %(stage)s,
    %(home_team_id)s,
    %(away_team_id)s,
    %(home_team)s,
    %(away_team)s,
    %(utc_date)s,
    %(match_date)s,
    %(kickoff_time)s,
    %(kickoff)s,
    %(status)s,
    %(score_home)s,
    %(score_away)s,
    %(winner)s,
    NOW()
)

ON CONFLICT (match_id)

DO UPDATE SET

    competition      = EXCLUDED.competition,
    competition_code = EXCLUDED.competition_code,
    season           = EXCLUDED.season,
    matchday         = EXCLUDED.matchday,
    stage            = EXCLUDED.stage,

    home_team_id     = EXCLUDED.home_team_id,
    away_team_id     = EXCLUDED.away_team_id,

    home_team        = EXCLUDED.home_team,
    away_team        = EXCLUDED.away_team,

    utc_date         = EXCLUDED.utc_date,
    match_date       = EXCLUDED.match_date,
    kickoff_time     = EXCLUDED.kickoff_time,
    kickoff          = EXCLUDED.kickoff,

    status           = EXCLUDED.status,

    score_home       = EXCLUDED.score_home,
    score_away       = EXCLUDED.score_away,

    winner           = EXCLUDED.winner,

    last_updated     = NOW();
"""


# ==========================================================
# UPSERT SINGLE FIXTURE
# ==========================================================

def upsert_fixture(fixture):

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                UPSERT_SQL,
                fixture,
            )

        conn.commit()


# ==========================================================
# UPSERT MULTIPLE FIXTURES
# ==========================================================

def upsert_fixtures(fixtures):

    inserted = 0
    updated = 0
    failed = 0

    inserted_fixtures = []
    updated_fixtures = []
    newly_finished = []

    with get_connection() as conn:

        with conn.cursor() as cur:

            for fixture in fixtures:

                try:

                    cur.execute(
                        """
                        SELECT
                            status,
                            score_home,
                            score_away
                        FROM fixtures
                        WHERE match_id=%s
                        """,
                        (fixture["match_id"],),
                    )

                    existing = cur.fetchone()

                    cur.execute(
                        UPSERT_SQL,
                        fixture,
                    )

                    if existing is not None:

                        previous_status = existing["status"]

                        if (
                            previous_status != "FINISHED"
                            and fixture["status"] == "FINISHED"
                        ):

                            newly_finished.append(fixture)

                            logger.info(
                                "Fixture %s has just finished.",
                                fixture["match_id"],
                            )

                    if existing is None:

                        inserted += 1
                        inserted_fixtures.append(fixture)

                    else:

                        updated += 1
                        updated_fixtures.append(fixture)

                except Exception:

                    logger.exception(
                        "Unable to synchronize fixture %s",
                        fixture["match_id"],
                    )

                    failed += 1

        conn.commit()

    logger.info(
        "Fixtures synchronized. Inserted=%d Updated=%d Failed=%d",
        inserted,
        updated,
        failed,
    )

    return {

        "downloaded": len(fixtures),

        "newly_finished": newly_finished,

        "inserted": inserted,

        "updated": updated,

        "failed": failed,

        "fixtures_inserted": inserted_fixtures,

        "fixtures_updated": updated_fixtures,

        "fixtures_to_predict": inserted_fixtures + updated_fixtures,

    }


# ==========================================================
# UPCOMING FIXTURES
# ==========================================================

def get_upcoming_fixtures():

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT *

                FROM fixtures

                WHERE

                status IN
                (
                    'SCHEDULED',
                    'TIMED'
                )

                AND kickoff >= NOW()

                AND kickoff <= NOW() + INTERVAL '30 days'

                ORDER BY kickoff ASC;
                """
            )

            return cur.fetchall()


# ==========================================================
# LIVE FIXTURES
# ==========================================================

def get_live_fixtures():

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT *

                FROM fixtures

                WHERE status IN
                (
                    'LIVE',
                    'IN_PLAY',
                    'PAUSED',
                    'HALF_TIME'
                )

                ORDER BY kickoff ASC;
                """
            )

            return cur.fetchall()


# ==========================================================
# SINGLE FIXTURE
# ==========================================================

def get_fixture(match_id):

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT *

                FROM fixtures

                WHERE match_id=%s;
                """,
                (match_id,),
            )

            return cur.fetchone()

# ==========================================================
# GET FIXTURES BY STATUS
# ==========================================================

def get_fixtures_by_status(status):

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT *

                FROM fixtures

                WHERE status=%s

                ORDER BY kickoff ASC;
                """,
                (status,),
            )

            return cur.fetchall()
        
# ==========================================================
# FIXTURES NEEDING PREDICTIONS
# ==========================================================

def get_fixtures_needing_predictions():

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT

                    f.match_id,
                    f.home_team,
                    f.away_team,
                    f.competition,
                    f.competition_code,
                    f.season,
                    f.matchday,
                    f.stage,
                    f.kickoff,
                    f.match_date,
                    f.status

                FROM fixtures f

                LEFT JOIN predictions p

                    ON f.match_id = p.match_id

                WHERE

                p.match_id IS NULL

                AND f.status IN
                (
                    'SCHEDULED',
                    'TIMED'
                )

                AND f.kickoff >= NOW()

                AND f.kickoff <= NOW() + INTERVAL '30 days'

                ORDER BY
                    f.kickoff ASC;
                """
            )

            fixtures = cur.fetchall()

    logger.info(
        "Found %d fixtures requiring predictions.",
        len(fixtures),
    )

    return fixtures

# ==========================================================
# GET FINISHED FIXTURES
# ==========================================================

def get_finished_fixtures(limit=100):

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT *

                FROM fixtures

                WHERE status='FINISHED'

                ORDER BY kickoff DESC

                LIMIT %s;
                """,
                (limit,),
            )

            return cur.fetchall()
        
# ==========================================================
# GET FIXTURE BY TEAMS
# ==========================================================

def get_fixture_by_teams(home_team, away_team):

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT *

                FROM fixtures

                WHERE

                    home_team=%s

                    AND away_team=%s

                ORDER BY kickoff DESC

                LIMIT 1;
                """,
                (
                    home_team,
                    away_team,
                ),
            )

            return cur.fetchone()
        
# ==========================================================
# COUNT FIXTURES
# ==========================================================

def fixture_statistics():

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT

                    COUNT(*) AS total,

                    COUNT(*) FILTER (
                        WHERE status='FINISHED'
                    ) AS finished,

                    COUNT(*) FILTER (
                        WHERE status IN
                        (
                            'SCHEDULED',
                            'TIMED'
                        )
                    ) AS upcoming,

                    COUNT(*) FILTER (
                        WHERE status IN
                        (
                            'LIVE',
                            'IN_PLAY'
                        )
                    ) AS live

                FROM fixtures;
                """
            )

            return cur.fetchone()


# ==========================================================
# FIXTURES IN PREDICTION WINDOW
# ==========================================================

def get_prediction_window_fixtures():

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT *

                FROM fixtures

                WHERE

                    status IN
                    (
                        'SCHEDULED',
                        'TIMED'
                    )

                    AND kickoff >= NOW()

                    AND kickoff <= NOW() + INTERVAL '30 days'

                ORDER BY kickoff ASC;
                """
            )

            return cur.fetchall()