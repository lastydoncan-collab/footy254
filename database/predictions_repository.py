from database.db_config import get_connection


# ==========================================================
# PREDICTION WINDOW
# ==========================================================

PREDICTION_WINDOW_DAYS = 30

# ==========================================================
# SERIALIZER
# ==========================================================

def _serialize_prediction(row):

    if row is None:
        return None

    return {

        # -------------------------
        # Match
        # -------------------------

        "match_id": row["match_id"],

        "status": row["status"],

        "stage": row["stage"],

        "matchday": row["matchday"],

        # -------------------------
        # Competition
        # -------------------------

        "competition": row["competition"],

        "competition_code": row["competition_code"],

        "competition_id": row["competition_id"],

        "season": row["season"],

        # -------------------------
        # Teams
        # -------------------------

        "home_team": row["home_team"],

        "away_team": row["away_team"],

        "home_team_id": row["home_team_id"],

        "away_team_id": row["away_team_id"],

        # -------------------------
        # Fixture
        # -------------------------

        "match_date": row["match_date"],

        "kickoff": row["kickoff"],

        "score_home": row["score_home"],

        "score_away": row["score_away"],

        "winner": row["winner"],

        # -------------------------
        # AI Prediction
        # -------------------------

        "prediction": row["prediction"],

        "confidence": row["confidence"],

        "home_win_probability": row["home_win"],

        "draw_probability": row["draw"],

        "away_win_probability": row["away_win"],

        "expected_home_goals": row["xg_home"],

        "expected_away_goals": row["xg_away"],

        "generated_at": row["generated_at"],

    }
# ==========================================================
# SAVE / UPDATE PREDICTION
# ==========================================================

def save_prediction(match_id, prediction):

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                INSERT INTO predictions
                (
                    match_id,
                    prediction,
                    confidence,
                    home_win,
                    draw,
                    away_win,
                    xg_home,
                    xg_away,
                    generated_at
                )

                VALUES
                (
                    %s,%s,%s,%s,%s,%s,%s,%s,NOW()
                )

                ON CONFLICT(match_id)

                DO UPDATE SET

                    prediction   = EXCLUDED.prediction,
                    confidence   = EXCLUDED.confidence,
                    home_win     = EXCLUDED.home_win,
                    draw         = EXCLUDED.draw,
                    away_win     = EXCLUDED.away_win,
                    xg_home      = EXCLUDED.xg_home,
                    xg_away      = EXCLUDED.xg_away,
                    generated_at = NOW();
                """,
                (
                    match_id,
                    prediction["prediction"],
                    float(prediction["confidence"]),
                    float(prediction["probabilities"]["home_win"]),
                    float(prediction["probabilities"]["draw"]),
                    float(prediction["probabilities"]["away_win"]),
                    float(prediction["xg"]["home"]),
                    float(prediction["xg"]["away"]),
                ),
            )

        conn.commit()

    return prediction

# ==========================================================
# LATEST PREDICTIONS
# ==========================================================

def get_latest_predictions(limit=50):

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT *

                FROM predictions

                JOIN fixtures f

                ON predictions.match_id = f.match_id

                WHERE

                    f.status IN
                    (
                        'SCHEDULED',
                        'TIMED'
                    )

                    AND f.kickoff >= NOW()

                    AND f.kickoff <= NOW() + INTERVAL '30 days'

                ORDER BY

                    f.kickoff ASC
                LIMIT %s;
                """,
                (limit,),
            )

            return cur.fetchall()
        
# ==========================================================
# GET ALL PREDICTIONS
# ==========================================================

def get_all_predictions():

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT *

                FROM predictions

                JOIN fixtures f

                ON predictions.match_id = f.match_id

                WHERE

                    f.status IN
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

            return cur.fetchall()


# ==========================================================
# GET SINGLE PREDICTION
# ==========================================================

def get_prediction(match_id):

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT

                    f.match_id,

                    f.status,
                    f.stage,
                    f.matchday,

                    f.competition,
                    f.competition_code,
                    f.competition_id,
                    f.season,

                    f.home_team,
                    f.away_team,

                    f.home_team_id,
                    f.away_team_id,

                    f.match_date,
                    f.kickoff,

                    f.score_home,
                    f.score_away,
                    f.winner,

                    p.prediction,
                    p.confidence,
                    p.home_win,
                    p.draw,
                    p.away_win,
                    p.xg_home,
                    p.xg_away,
                    p.generated_at

                FROM fixtures f

                LEFT JOIN predictions p
                ON p.match_id = f.match_id

                WHERE f.match_id=%s;
                """,
                (match_id,),
            )

            row = cur.fetchone()

            return _serialize_prediction(row)


# ==========================================================
# FIXTURE + PREDICTION
# ==========================================================

def get_predictions_with_fixtures():

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT

                    f.match_id,

                    f.status,
                    f.stage,
                    f.matchday,

                    f.competition,
                    f.competition_code,
                    f.competition_id,
                    f.season,

                    f.home_team,
                    f.away_team,

                    f.home_team_id,
                    f.away_team_id,

                    f.match_date,
                    f.kickoff,

                    f.score_home,
                    f.score_away,
                    f.winner,

                    p.prediction,
                    p.confidence,

                    p.home_win,
                    p.draw,
                    p.away_win,

                    p.xg_home,
                    p.xg_away,

                    p.generated_at

                FROM fixtures f

                INNER JOIN predictions p

                ON p.match_id = f.match_id

                WHERE
                    f.status IN
                    (
                        'SCHEDULED',
                        'TIMED'
                    )
                    AND f.kickoff >= NOW()

                    AND f.kickoff <= NOW() + INTERVAL '30 days'

                    ORDER BY f.kickoff ASC;
                """
            )

            rows = cur.fetchall()

            return [
                _serialize_prediction(row)
                for row in rows
            ]
        
# ==========================================================
# PREDICTIONS BY FIXTURE STATUS
# ==========================================================

def get_predictions_by_status(status):

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT

                    f.status,
                    f.stage,
                    f.matchday,

                    f.competition,
                    f.competition_code,
                    f.competition_id,
                    f.season,
                    f.match_id,
                    f.home_team,
                    f.away_team,
                    f.competition,
                    f.match_date,
                    f.kickoff,

                    p.prediction,
                    p.confidence,
                    p.home_win,
                    p.draw,
                    p.away_win,
                    p.xg_home,
                    p.xg_away

                FROM predictions p

                JOIN fixtures f

                    ON p.match_id=f.match_id

                WHERE

                f.status = %s

                AND f.kickoff >= NOW()

                AND f.kickoff <= NOW() + INTERVAL '30 days'
                """,
                (status,),
            )

            rows = cur.fetchall()

            return [
                _serialize_prediction(row)
                for row in rows
            ]
        
# ==========================================================
# DELETE ALL PREDICTIONS
# ==========================================================

def delete_all_predictions():

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                DELETE FROM predictions;
                """
            )

        conn.commit()

# ==========================================================
# DELETE SINGLE PREDICTION
# ==========================================================

def delete_prediction(match_id):

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                DELETE

                FROM predictions

                WHERE match_id=%s;
                """,
                (match_id,),
            )

        conn.commit()

# ==========================================================
# PREDICTION STATISTICS
# ==========================================================

def prediction_statistics():

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT

                COUNT(*) FILTER
                (
                WHERE f.status IN
                (
                'SCHEDULED',
                'TIMED'
                )
                ) AS active_predictions,

                COUNT(*) FILTER
                (
                WHERE f.status='FINISHED'
                ) AS completed_predictions,

                AVG(confidence),

                MAX(generated_at)

                FROM predictions p

                JOIN fixtures f

                ON p.match_id=f.match_id;
                """
            )

            return cur.fetchone()