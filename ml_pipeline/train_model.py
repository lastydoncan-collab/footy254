import logging
import os

import joblib
import numpy as np
import pandas as pd

from sklearn.calibration import CalibratedClassifierCV
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
# CHRONOLOGICAL ORDER + RECENCY WEIGHTS
# ==========================================================

# Half-life for recency weighting: a match this many days old carries half
# the training weight of today's match, decaying exponentially from there.
# ~2 seasons feels right for football — old enough to still value a deep
# history, recent enough that this year's form actually outweighs 2016.
RECENCY_HALF_LIFE_DAYS = 730


def sort_chronologically(df):
    """
    Sort the dataset oldest-to-newest by match_date and reset the index.

    build_elo() walks the dataframe sequentially to update ratings match by
    match, so it has always silently depended on chronological row order
    (previously guaranteed only implicitly, by dataset_builder.py writing
    rows in the order its SQL query returned them). Sorting explicitly here
    makes that guarantee self-evident, and is also what the time-based
    train/test split below depends on.

    Falls back to the dataset's existing row order (with a warning) if this
    is a dataset built before "match_date" was added as a column — train()
    still works, it just can't do a time-based split or recency weighting
    until the dataset is rebuilt.
    """

    if "match_date" not in df.columns:

        logger.warning(
            "Dataset has no 'match_date' column (built with an older "
            "dataset_builder.py) — skipping chronological sort. Re-run "
            "build_dataset() to enable the time-based train/test split and "
            "recency weighting."
        )

        return df, False

    df = df.copy()

    df["match_date"] = pd.to_datetime(
        df["match_date"],
        errors="coerce",
        utc=True,
    )

    unparsed = int(df["match_date"].isna().sum())

    if unparsed:
        logger.warning(
            "%d row(s) have an unparsable match_date; they sort first "
            "(oldest) and get the lowest recency weight.",
            unparsed,
        )

    df = df.sort_values(
        "match_date",
        na_position="first",
    ).reset_index(drop=True)

    return df, True


def compute_recency_weights(df, has_dates, half_life_days=RECENCY_HALF_LIFE_DAYS):
    """
    Exponential-decay sample weight: 1.0 for the most recent match in the
    dataset, 0.5 at `half_life_days` old, 0.25 at twice that, and so on.

    Replaces the previous behaviour of weighting every historical row
    identically regardless of age — a 2014 match and a 2026 match used to
    count exactly the same toward the model's decision boundaries, which
    actively fights against learning current team strength.
    """

    if not has_dates:
        return np.ones(len(df))

    most_recent = df["match_date"].max()

    age_days = (
        (most_recent - df["match_date"]).dt.total_seconds() / 86400.0
    )

    weights = np.power(0.5, age_days / half_life_days)

    weights = np.nan_to_num(weights, nan=float(np.nanmedian(weights)) if np.isfinite(np.nanmedian(weights)) else 1.0)

    return weights

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
        "match_date",
        "sample_weight",
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

def train_model(X, y, sample_weight, has_dates):

    logger.info(
        "Splitting training dataset..."
    )

    if has_dates:

        # Time-based holdout: the oldest 80% of matches train the model,
        # the most recent 20% test it. X/y/sample_weight all arrive in
        # chronological order (sort_chronologically() upstream), so this is
        # a positional split, not a random one. This is the honest way to
        # evaluate a football model — a random split lets the model see
        # match N+50's data patterns bleed into predicting match N (same
        # teams, overlapping seasons, shared rolling-form windows), which
        # is almost certainly why the previous random split scored higher
        # than this model will actually perform in production, predicting
        # fixtures it has never seen *or trained near in time*.
        logger.info(
            "Using a chronological (time-based) train/test split."
        )

        split_index = int(len(X) * 0.80)

        X_train, X_test = X[:split_index], X[split_index:]
        y_train, y_test = y[:split_index], y[split_index:]
        w_train, w_test = (
            sample_weight[:split_index],
            sample_weight[split_index:],
        )

    else:

        # No match_date available (dataset built before this upgrade) —
        # fall back to the original random stratified split rather than
        # failing outright.
        logger.info(
            "Using a random stratified train/test split (no match_date)."
        )

        (
            X_train, X_test,
            y_train, y_test,
            w_train, w_test,
        ) = train_test_split(
            X,
            y,
            sample_weight,
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
        "Training calibrated Random Forest..."
    )

    base_model = RandomForestClassifier(

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
        base_model,
        X_train,
        y_train,
        cv=5,
        scoring="accuracy",
        n_jobs=-1,
    )

    logger.info(
        "Cross-validation accuracy (uncalibrated base estimator): %.4f ± %.4f",
        cv_scores.mean(),
        cv_scores.std(),
    )

    # Wrap the Random Forest in isotonic probability calibration. A raw
    # RandomForestClassifier's predict_proba() output is NOT a calibrated
    # probability — it is a vote fraction across trees, and tree ensembles
    # are well known to be overconfident near 0/1 and underconfident near
    # the middle, which for a 3-class problem is exactly where draws live.
    # CalibratedClassifierCV refits the base estimator across `cv` internal
    # folds and learns a monotonic remapping from raw scores to empirically
    # correct probabilities per class, replacing the previous approach of a
    # single hardcoded softmax "temperature" constant (1.40) that could not
    # know whether the model was over- or under-confident for any one
    # class — least of all draws specifically.
    model = CalibratedClassifierCV(
        base_model,
        method="isotonic",
        cv=5,
    )

    model.fit(
        X_train,
        y_train,
        sample_weight=w_train,
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

        "Accuracy (%s split) : %.4f",
        "time-based" if has_dates else "random",
        accuracy,

    )

    report_text = classification_report(

        y_test,

        predictions,

        target_names=[

            "HOME",

            "DRAW",

            "AWAY",

        ],

        digits=4,

    )

    report_dict = classification_report(
        y_test,
        predictions,
        target_names=["HOME", "DRAW", "AWAY"],
        digits=4,
        output_dict=True,
    )

    matrix = confusion_matrix(

        y_test,

        predictions,

    )

    print()

    print("=" * 70)

    print("CLASSIFICATION REPORT")

    print("=" * 70)

    print(report_text)

    print()

    print("=" * 70)

    print("CONFUSION MATRIX")

    print("=" * 70)

    print(matrix)

    print()

    logger.info(
        "Calculating feature importance..."
    )

    return (

        model,

        accuracy,

        probabilities,

        report_dict,

        matrix,

    )

# ==========================================================
# FEATURE IMPORTANCE
# ==========================================================

def extract_feature_importances(model, n_features):
    """
    CalibratedClassifierCV has no .feature_importances_ of its own (it isn't
    a tree model) — it holds one fitted copy of the base RandomForest per
    internal CV fold, in .calibrated_classifiers_. Average their individual
    .feature_importances_ for a single importance ranking, same shape and
    meaning as before this change, just sourced from the calibrated model's
    internal folds instead of one plain RandomForestClassifier.
    """

    if hasattr(model, "feature_importances_"):
        # Backward-compatible path, in case an uncalibrated model is ever
        # passed in here directly (e.g. for debugging).
        return np.asarray(model.feature_importances_)

    totals = np.zeros(n_features)
    count = 0

    for calibrated_classifier in getattr(model, "calibrated_classifiers_", []):

        # Attribute was renamed base_estimator -> estimator in scikit-learn
        # 1.4; support both so this keeps working across the version range
        # requirements-backend.txt pins (1.8.x as of this writing).
        estimator = getattr(
            calibrated_classifier,
            "estimator",
            None,
        ) or getattr(
            calibrated_classifier,
            "base_estimator",
            None,
        )

        if estimator is not None and hasattr(estimator, "feature_importances_"):
            totals += estimator.feature_importances_
            count += 1

    if count == 0:
        logger.warning(
            "Could not extract feature importances from the calibrated "
            "model; feature_importance.csv will be all zeros."
        )
        return totals

    return totals / count


def print_feature_importance(

    model,

    feature_columns,

):

    importance = pd.DataFrame(

        {

            "Feature": feature_columns,

            "Importance": extract_feature_importances(model, len(feature_columns)),

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

    report_dict=None,

    confusion=None,

    has_dates=False,

):

    metadata = {
        "accuracy": float(accuracy),
        "rows": int(rows),
        "features": int(features),
        "model": "RandomForestClassifier + CalibratedClassifierCV(isotonic)",
        "version": "FOOTY254 V4",
        "n_estimators": 600,
        "max_depth": 16,
        "rolling_matches": 5,
        "split": "time-based (80/20, chronological)" if has_dates else "random stratified (80/20)",
        "recency_weighting": bool(has_dates),
        "recency_half_life_days": RECENCY_HALF_LIFE_DAYS if has_dates else None,
    }

    # Persist per-class precision/recall/F1 (previously only printed to
    # stdout at training time and lost on the next retrain) so draw
    # performance specifically — historically the weak point for 1X2
    # classifiers — is trackable across retrains instead of only visible in
    # a log line that scrolls away.
    if report_dict:

        metadata["per_class"] = {

            label: {

                "precision": round(float(report_dict[label]["precision"]), 4),
                "recall": round(float(report_dict[label]["recall"]), 4),
                "f1_score": round(float(report_dict[label]["f1-score"]), 4),
                "support": int(report_dict[label]["support"]),

            }

            for label in ("HOME", "DRAW", "AWAY")

            if label in report_dict

        }

        metadata["draw_recall"] = metadata["per_class"].get(
            "DRAW", {}
        ).get("recall")

        metadata["macro_f1"] = round(
            float(report_dict["macro avg"]["f1-score"]), 4
        ) if "macro avg" in report_dict else None

    if confusion is not None:
        metadata["confusion_matrix"] = confusion.tolist()
        metadata["confusion_matrix_labels"] = ["HOME", "DRAW", "AWAY"]

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
    # CHRONOLOGICAL ORDER + RECENCY WEIGHTS
    # ------------------------------------------------------

    df, has_dates = sort_chronologically(df)

    sample_weight = compute_recency_weights(df, has_dates)

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

    model, accuracy, _, report_dict, confusion = train_model(

        X,

        y,

        sample_weight,

        has_dates,

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

        report_dict=report_dict,

        confusion=confusion,

        has_dates=has_dates,

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
