from database.db_config import get_connection


def store_fixtures(fixtures):

    conn = get_connection()

    cur = conn.cursor()

    inserted = 0

    for fixture in fixtures:

        cur.execute(
            """
            INSERT INTO fixtures (

                match_id,

                competition,

                competition_code,

                season,

                matchday,

                stage,

                match_date,

                kickoff,

                home_team,

                away_team,

                score_home,

                score_away,

                winner,

                status

            )

            VALUES (

                %(match_id)s,

                %(competition)s,

                %(competition_code)s,

                %(season)s,

                %(matchday)s,

                %(stage)s,

                %(match_date)s,

                %(kickoff)s,

                %(home_team)s,

                %(away_team)s,

                %(score_home)s,

                %(score_away)s,

                %(winner)s,

                %(status)s

            )

            ON CONFLICT (match_id)

            DO UPDATE SET

                competition = EXCLUDED.competition,

                competition_code = EXCLUDED.competition_code,

                season = EXCLUDED.season,

                matchday = EXCLUDED.matchday,

                stage = EXCLUDED.stage,

                match_date = EXCLUDED.match_date,

                kickoff = EXCLUDED.kickoff,

                home_team = EXCLUDED.home_team,

                away_team = EXCLUDED.away_team,

                score_home = EXCLUDED.score_home,

                score_away = EXCLUDED.score_away,

                winner = EXCLUDED.winner,

                status = EXCLUDED.status
            """,
            fixture,
        )

        inserted += 1

    conn.commit()

    cur.close()

    conn.close()

    print(f"Stored {inserted} fixtures.")

    return inserted