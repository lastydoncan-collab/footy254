from database.db_config import get_connection


def increment_finished_matches(count: int):

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                UPDATE automation_state
                SET
                    value = value + %s,
                    updated_at = NOW()
                WHERE key='new_finished_matches';
                """,
                (count,),
            )

        conn.commit()


def get_finished_match_counter():

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT value
                FROM automation_state
                WHERE key='new_finished_matches';
                """
            )

            row = cur.fetchone()

            return row["value"] if row else 0


def reset_finished_counter():

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                UPDATE automation_state
                SET
                    value=0,
                    updated_at=NOW()
                WHERE key='new_finished_matches';
                """
            )

        conn.commit()