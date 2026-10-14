import logging
import os

import joblib
import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import cross_val_score

# ==========================================================
# LOGGING
# ==========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)

# ==========================================================
# PATHS
# ==========================================================

BASE_DIR = os.path.dirname(__file__)

DATA_DIR = os.path.join(
    BASE_DIR,
    "..",
    "data",
)

MODELS_DIR = os.path.join(
    BASE_DIR,
    "models",
)

os.makedirs(
    MODELS_DIR,
    exist_ok=True,
)

DATASET_FILE = os.path.join(
    DATA_DIR,
    "processed_matches.csv",
)

# ==========================================================
# LOAD DATASET
# ==========================================================

def load_dataset():

    if not os.path.exists(DATASET_FILE):

        raise FileNotFoundError(

            f"Dataset not found:\n{DATASET_FILE}\n\n"

            "Run dataset_builder.py first."

        )

    logger.info(
        "Loading processed dataset..."
    )

    df = pd.read_csv(DATASET_FILE)

    logger.info(
        "Loaded %d training rows.",
        len(df),
    )

    return df

# ==========================================================
# VALIDATION
# ==========================================================

REQUIRED_COLUMNS = [

    "home_team",
    "away_team",

    "match_id",
    "competition",
    "competition_code",
    "season",
    "matchday",
    "stage",

    "home_form",
    "away_form",

    "home_goals",
    "away_goals",

    "home_attack",
    "away_attack",

    "home_defence",
    "away_defence",

    "home_avg_scored",
    "away_avg_scored",

    "home_avg_conceded",
    "away_avg_conceded",

    "home_goal_difference",
    "away_goal_difference",

    "home_win_rate",
    "away_win_rate",

    "home_clean_sheet_rate",
    "away_clean_sheet_rate",

    "home_momentum",
    "away_momentum",

    "home_win_streak",
    "away_win_streak",

    "home_failed_to_score_streak",
    "away_failed_to_score_streak",

    "home_clean_sheet_streak",
    "away_clean_sheet_streak",

    "home_recent_shots",
    "away_recent_shots",

    "home_recent_shots_on_target",
    "away_recent_shots_on_target",

    "home_recent_possession",
    "away_recent_possession",

    "home_recent_corners",
    "away_recent_corners",

    "home_recent_cards",
    "away_recent_cards",

    "home_recent_goals",
    "away_recent_goals",

    "home_recent_conceded",
    "away_recent_conceded",

    "home_home_form",
    "away_away_form",

    "home_rest",
    "away_rest",

    "home_recent_xg",
    "away_recent_xg",

    "home_recent_xga",
    "away_recent_xga",

    "home_recent_points",
    "away_recent_points",

    "home_unbeaten",
    "away_unbeaten",

    "home_strength",
    "away_strength",

    "attack_difference",
    "defence_difference",
    "form_difference",
    "goal_difference",
    "win_rate_difference",

    "recent_points_difference",
    "recent_goal_difference",
    "recent_conceded_difference",
    "strength_difference",
    "momentum_difference",
    "shots_difference",
    "sot_difference",
    "possession_difference",
    "corners_difference",
    "cards_difference",
    "home_advantage",

    "result",
]

def validate_dataset(df):

    missing = [

        column

        for column in REQUIRED_COLUMNS

        if column not in df.columns

    ]

    if missing:

        raise RuntimeError(

            "Dataset missing columns:\n"

            + "\n".join(missing)

        )

    if len(df) < 300:

        logger.warning(

            "Very small dataset (%d rows).",

            len(df),

        )

    logger.info(

        "Dataset validation successful."

    )

# ==========================================================
# TEAM ENCODER
# ==========================================================

def build_encoder(df):

    teams = sorted(

        set(df.home_team)

        |

        set(df.away_team)

    )

    encoder = LabelEncoder()

    encoder.fit(teams)

    joblib.dump(

        encoder,

        os.path.join(

            MODELS_DIR,

            "team_encoder.pkl",

        ),

    )

    logger.info(

        "Saved encoder (%d teams)",

        len(teams),

    )

    return encoder
# ==========================================================
# BUILD ELO RATINGS
# ==========================================================

def build_elo(df, k_factor=20):

    logger.info(
        "Building Elo ratings..."
    )

    elo = {}

    for match in df.itertuples(index=False):

        home = match.home_team
        away = match.away_team

        home_rating = elo.get(home, 1500)
        away_rating = elo.get(away, 1500)

        expected_home = (
            1 /
            (
                1 +
                10 ** (
                    (away_rating - home_rating) / 400
                )
            )
        )

        expected_away = 1 - expected_home

        if match.result == 0:

            score_home = 1
            score_away = 0

        elif match.result == 2:

            score_home = 0
            score_away = 1

        else:

            score_home = 0.5
            score_away = 0.5

        elo[home] = (
            home_rating +
            k_factor *
            (score_home - expected_home)
        )

        elo[away] = (
            away_rating +
            k_factor *
            (score_away - expected_away)
        )

    joblib.dump(

        elo,

        os.path.join(
            MODELS_DIR,
            "team_elo.pkl"
        ),

    )

    logger.info(
        "Saved Elo ratings for %d teams.",
        len(elo),
    )

    return elo


# ==========================================================
# BUILD TEAM STATS
# ==========================================================

def build_team_stats(df):

    logger.info(
        "Building team statistics..."
    )

    stats = {}

    teams = sorted(
        set(df.home_team)
        |
        set(df.away_team)
    )

    for team in teams:

        home = df[
            df.home_team == team
        ]

        away = df[
            df.away_team == team
        ]

        def mean_feature(home_column, away_column):
            return pd.concat(
                [home[home_column], away[away_column]]
            ).mean()

        attack = mean_feature("home_attack", "away_attack")
        defence = mean_feature("home_defence", "away_defence")
        form = mean_feature("home_form", "away_form")

        stats[team] = {

            "attack": round(float(attack),4),

            "defence": round(float(defence),4),

            "form": round(float(form),4),

            "avg_scored": round(float(mean_feature(
                "home_avg_scored",
                "away_avg_scored")),4),

            "avg_conceded": round(float(mean_feature(
                "home_avg_conceded",
                "away_avg_conceded")),4),

            "goal_difference": round(float(mean_feature(
                "home_goal_difference",
                "away_goal_difference")),4),

            "win_rate": round(float(mean_feature(
                "home_win_rate",
                "away_win_rate")),4),

            "clean_sheet_rate": round(float(mean_feature(
                "home_clean_sheet_rate",
                "away_clean_sheet_rate")),4),

            "recent_goals_scored": round(float(mean_feature(
                "home_recent_goals",
                "away_recent_goals")),4),

            "recent_goals_conceded": round(float(mean_feature(
                "home_recent_conceded",
                "away_recent_conceded")),4),

            "recent_points": round(float(mean_feature(
                "home_recent_points",
                "away_recent_points")),4),

            "home_form": round(float(home["home_home_form"].mean()),4),

            "away_form": round(float(away["away_away_form"].mean()),4),

            "recent_xg": round(float(mean_feature(
                "home_recent_xg",
                "away_recent_xg")),4),

            "recent_xga": round(float(mean_feature(
                "home_recent_xga",
                "away_recent_xga")),4),

            "home_strength": round(float(home["home_strength"].mean()),4),

            "away_strength": round(float(away["away_strength"].mean()),4),

            "unbeaten": round(float(mean_feature(
                "home_unbeaten",
                "away_unbeaten")),4),

            "rest_days": round(float(mean_feature(
                "home_rest",
                "away_rest")),4),

            "momentum": round(float(mean_feature(
                "home_momentum",
                "away_momentum")), 4),

            "win_streak": round(float(mean_feature(
                "home_win_streak",
                "away_win_streak")), 4),

            "failed_to_score_streak": round(float(mean_feature(
                "home_failed_to_score_streak",
                "away_failed_to_score_streak")), 4),

            "clean_sheet_streak": round(float(mean_feature(
                "home_clean_sheet_streak",
                "away_clean_sheet_streak")), 4),

            "recent_goal_difference": round(float(mean_feature(
                "home_recent_goal_difference",
                "away_recent_goal_difference")), 4),

            "recent_shots": round(float(mean_feature(
                "home_recent_shots",
                "away_recent_shots")), 4),

            "recent_shots_on_target": round(float(mean_feature(
                "home_recent_shots_on_target",
                "away_recent_shots_on_target")), 4),

            "recent_possession": round(float(mean_feature(
                "home_recent_possession",
                "away_recent_possession")), 4),

            "recent_corners": round(float(mean_feature(
                "home_recent_corners",
                "away_recent_corners")), 4),

            "recent_cards": round(float(mean_feature(
                "home_recent_cards",
                "away_recent_cards")), 4),
        }

    joblib.dump(

        stats,

        os.path.join(
            MODELS_DIR,
            "team_stats.pkl",
        ),

    )

    logger.info(

        "Saved statistics for %d teams.",

        len(stats),

    )

    return 


# ==========================================================
# FEATURE MATRIX
# ==========================================================

def prepare_features(df, encoder, elo):

    logger.info(
        "Preparing feature matrix..."
    )

    df = df.copy()

    df["home_enc"] = encoder.transform(
        df.home_team
    )

    df["away_enc"] = encoder.transform(
        df.away_team
    )

    df["home_elo"] = df.home_team.map(

        lambda team:

        (elo.get(team, 1500) - 1500)

        / 400

    )

    df["away_elo"] = df.away_team.map(

        lambda team:

        (elo.get(team, 1500) - 1500)

        / 400

    )

    df["elo_difference"] = (

        df.home_elo

        - df.away_elo

    )

    NON_FEATURE_COLUMNS = {
        "match_id",
        "competition",
        "competition_code",
        "season",
        "matchday",
        "stage",
        "home_team",
        "away_team",
        "home_goals",
        "away_goals",
        "result",
    }

    FEATURE_COLUMNS = [
        column
        for column in df.columns
        if column not in NON_FEATURE_COLUMNS
    ]

    if "match_id" in FEATURE_COLUMNS:
        raise RuntimeError(
            "Invalid ML feature schema: match_id must not be used as a predictive feature."
        )

    joblib.dump(
        FEATURE_COLUMNS,
        os.path.join(
            MODELS_DIR,
            "feature_columns.pkl",
        ),
    )

    X = (
        df[FEATURE_COLUMNS]
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
        .astype(float)
        .values
    )

    y = df[
        "result"
    ].values

    scaler = StandardScaler()

    X = scaler.fit_transform(X)

    joblib.dump(

        scaler,

        os.path.join(
            MODELS_DIR,
            "scaler.pkl",
        ),

    )

    logger.info(

        "Feature matrix created."

    )

    logger.info(

        "Features : %d",

        len(FEATURE_COLUMNS),

    )

    return (

        X,

        y,

        FEATURE_COLUMNS,

        scaler,

    )

# ==========================================================
# TRAIN MODEL
# ==========================================================

def train_model(X, y):

    logger.info(
        "Splitting training dataset..."
    )

    X_train, X_test, y_train, y_test = train_test_split(

        X,

        y,

        test_size=0.20,

        random_state=42,

        stratify=y,

    )

    logger.info(

        "Training samples : %d",

        len(X_train),

    )

    logger.info(

        "Testing samples  : %d",

        len(X_test),

    )

    logger.info(
        "Training Random Forest..."
    )

    model = RandomForestClassifier(

        n_estimators=600,

        max_depth=16,

        min_samples_split=8,

        min_samples_leaf=4,

        class_weight="balanced",

        bootstrap=True,

        random_state=42,

        n_jobs=-1,

    )

    cv_scores = cross_val_score(
        model,
        X_train,
        y_train,
        cv=5,
        scoring="accuracy",
        n_jobs=-1,
    )

    logger.info(
        "Cross-validation accuracy: %.4f ± %.4f",
        cv_scores.mean(),
        cv_scores.std(),
    )

    model.fit(
        X_train,
        y_train,
    )

    logger.info(
        "Training completed."
    )

    predictions = model.predict(X_test)

    probabilities = model.predict_proba(X_test)

    accuracy = accuracy_score(

        y_test,

        predictions,

    )

    logger.info(

        "Accuracy : %.4f",

        accuracy,

    )

    print()

    print("=" * 70)

    print("CLASSIFICATION REPORT")

    print("=" * 70)

    print(

        classification_report(

            y_test,

            predictions,

            target_names=[

                "HOME",

                "DRAW",

                "AWAY",

            ],

            digits=4,

        )

    )

    print()

    print("=" * 70)

    print("CONFUSION MATRIX")

    print("=" * 70)

    print(

        confusion_matrix(

            y_test,

            predictions,

        )

    )

    print()

    logger.info(
        "Calculating feature importance..."
    )

    return (

        model,

        accuracy,

        probabilities,

    )

# ==========================================================
# FEATURE IMPORTANCE
# ==========================================================

def print_feature_importance(

    model,

    feature_columns,

):

    importance = pd.DataFrame(

        {

            "Feature": feature_columns,

            "Importance": model.feature_importances_,

        }

    )

    importance.to_csv(
        os.path.join(
            MODELS_DIR,
            "feature_importance.csv",
        ),
        index=False,
    )

    importance = importance.sort_values(

        by="Importance",

        ascending=False,

    )

    print()

    print("=" * 70)

    print("FEATURE IMPORTANCE")

    print("=" * 70)

    print(

        importance.to_string(

            index=False

        )

    )

    print()

    return importance


# ==========================================================
# SAVE MODEL PACKAGE
# ==========================================================

def save_model(
    model,
    scaler,
):

    package = {
        "model": model,
        "scaler": scaler,
    }

    filename = os.path.join(
        MODELS_DIR,
        "football_model.pkl",
    )

    joblib.dump(
        package,
        filename,
    )

    logger.info(
        "Saved football_model.pkl"
    )

    # -----------------------------------------
    # Save class mapping
    # -----------------------------------------

    joblib.dump(
        {
            0: "HOME",
            1: "DRAW",
            2: "AWAY",
        },
        os.path.join(
            MODELS_DIR,
            "class_mapping.pkl",
        ),
    )

    logger.info(
        "Saved class_mapping.pkl"
    )


# ==========================================================
# SAVE TRAINING METADATA
# ==========================================================

def save_metadata(

    accuracy,

    rows,

    features,

):

    metadata = {
        "accuracy": float(accuracy),
        "rows": int(rows),
        "features": int(features),
        "model": "RandomForestClassifier",
        "version": "FOOTY254 V3",
        "n_estimators": 600,
        "max_depth": 16,
        "rolling_matches": 5,
    }

    joblib.dump(

        metadata,

        os.path.join(

            MODELS_DIR,

            "training_metadata.pkl",

        ),

    )

    logger.info(
        "Saved training metadata."
    )


# ==========================================================
# TRAIN PIPELINE
# ==========================================================


def train():

    logger.info("=" * 70)
    logger.info("FOOTY254 MODEL TRAINING")
    logger.info("=" * 70)

    # ------------------------------------------------------
    # LOAD DATASET
    # ------------------------------------------------------

    df = load_dataset()

    validate_dataset(df)

    logger.info(
        "Training rows : %d",
        len(df),
    )

    # ------------------------------------------------------
    # TEAM ENCODER
    # ------------------------------------------------------

    encoder = build_encoder(df)

    # ------------------------------------------------------
    # TEAM ELO
    # ------------------------------------------------------

    elo = build_elo(df)

    # ------------------------------------------------------
    # TEAM STATS
    # ------------------------------------------------------

    build_team_stats(df)

    # ------------------------------------------------------
    # FEATURES
    # ------------------------------------------------------

    X, y, feature_columns, scaler = prepare_features(

        df,

        encoder,

        elo,

    )

    # ------------------------------------------------------
    # TRAIN MODEL
    # ------------------------------------------------------

    model, accuracy, _ = train_model(

        X,

        y,

    )

    # ------------------------------------------------------
    # FEATURE IMPORTANCE
    # ------------------------------------------------------

    print_feature_importance(

        model,

        feature_columns,

    )

    # ------------------------------------------------------
    # SAVE MODEL
    # ------------------------------------------------------

    save_model(

        model,

        scaler,

    )

    # ------------------------------------------------------
    # SAVE METADATA
    # ------------------------------------------------------

    save_metadata(

        accuracy,

        len(df),

        len(feature_columns),

    )

    logger.info("=" * 70)
    logger.info("TRAINING COMPLETE")
    logger.info("=" * 70)

    logger.info(
        "Model accuracy : %.4f",
        accuracy,
    )

    logger.info(
        "Teams trained : %d",
        len(encoder.classes_),
    )

    logger.info(
        "Features : %d",
        len(feature_columns),
    )

    logger.info(
        "Artifacts saved to %s",
        MODELS_DIR,
    )


# ==========================================================
# ENTRY POINT
# ==========================================================

if __name__ == "__main__":

    train()
