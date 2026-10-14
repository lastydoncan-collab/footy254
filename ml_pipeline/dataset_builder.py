import logging
import os
import sys

import pandas as pd

# ==========================================================
# PROJECT ROOT
# ==========================================================

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(__file__)
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ==========================================================
# PROJECT IMPORTS
# ==========================================================

from database.db_config import get_connection

from ml_pipeline.core.feature_builder import (
    reset_history,
    update_team_history,
    team_features,
    create_training_features,
)

# ==========================================================
# LOGGING
# ==========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# ==========================================================
# CONFIGURATION
# ==========================================================


OUTPUT_DATASET = "data/processed_matches.csv"

# ==========================================================
# DATABASE
# ==========================================================

def load_finished_matches():

    logger.info("Loading finished fixtures from PostgreSQL...")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
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
            winner
        FROM fixtures
        WHERE status='FINISHED'
          AND score_home IS NOT NULL
          AND score_away IS NOT NULL
        ORDER BY
            match_date,
            kickoff;
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    columns = [
        "match_id",
        "competition",
        "competition_code",
        "season",
        "matchday",
        "stage",
        "match_date",
        "kickoff",
        "home_team",
        "away_team",
        "score_home",
        "score_away",
        "winner",
    ]

    df = pd.DataFrame(rows, columns=columns)

    logger.info("Loaded %d finished matches.", len(df))

    if df.empty:
        return df

    df["score_home"] = pd.to_numeric(
        df["score_home"],
        errors="coerce",
    )

    df["score_away"] = pd.to_numeric(
        df["score_away"],
        errors="coerce",
    )

    df = df.dropna(
        subset=[
            "score_home",
            "score_away",
        ]
    )

    df["score_home"] = df["score_home"].astype(int)
    df["score_away"] = df["score_away"].astype(int)

    return df


# ==========================================================
# CREATE TARGET
# ==========================================================

def create_target(
    home_goals: int,
    away_goals: int,
) -> int:

    if home_goals > away_goals:
        return 0

    if away_goals > home_goals:
        return 2

    return 1


# ==========================================================
# BUILD TRAINING ROW
# ==========================================================

def create_training_row(match) -> dict:

    home_stats = team_features(
        match.home_team,
    )

    away_stats = team_features(
        match.away_team,
    )

    row = {
        "match_id": match.match_id,
        "competition": match.competition,
        "competition_code": match.competition_code,
        "season": match.season,
        "matchday": match.matchday,
        "stage": match.stage,
        "home_team": match.home_team,
        "away_team": match.away_team,
    }

    row.update(
        create_training_features(
            home_stats,
            away_stats,
        )
    )

    row["home_goals"] = match.score_home
    row["away_goals"] = match.score_away
    row["result"] = create_target(

        match.score_home,

        match.score_away,

    )

    return row

# ==========================================================
# BUILD DATASET
# ==========================================================

def build_dataset() -> pd.DataFrame:

    logger.info(
        "Starting dataset generation..."
    )

    matches = load_finished_matches()

    if matches.empty:

        logger.warning(
            "No finished matches found."
        )

        return pd.DataFrame()

    # ------------------------------------------
    # Clear previous history
    # ------------------------------------------

    reset_history()

    dataset = []

    # ------------------------------------------
    # Chronological processing
    # ------------------------------------------

    for match in matches.itertuples(index=False):

        # --------------------------------------
        # Build features BEFORE this match
        # --------------------------------------

        row = create_training_row(match)

        dataset.append(row)

        match_datetime = pd.to_datetime(
            f"{match.match_date} {match.kickoff}",
            errors="coerce",
            utc=True,
        )

        # --------------------------------------
        # Update history AFTER this match
        # --------------------------------------

        update_team_history(

            team=match.home_team,

            goals_for=match.score_home,

            goals_against=match.score_away,

            is_home=True,

            match_date=match_datetime if pd.notna(match_datetime) else None,

        )

        update_team_history(

            team=match.away_team,

            goals_for=match.score_away,

            goals_against=match.score_home,

            is_home=False,

            match_date=match_datetime if pd.notna(match_datetime) else None,

        )

    # ------------------------------------------
    # Convert to dataframe
    # ------------------------------------------

    dataset = pd.DataFrame(dataset)

    os.makedirs(
        "data",
        exist_ok=True,
    )

    dataset.to_csv(

        OUTPUT_DATASET,

        index=False,

    )

    logger.info(

        "Dataset successfully built."

    )

    logger.info(

        "Training rows : %d",

        len(dataset),

    )

    logger.info(

        "Features      : %d",

        len(dataset.columns),

    )

    logger.info(

        "Saved to %s",

        OUTPUT_DATASET,

    )

    return dataset


# ==========================================================
# MAIN
# ==========================================================

if __name__ == "__main__":

    build_dataset()