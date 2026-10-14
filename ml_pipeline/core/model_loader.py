import os
import threading

import joblib

# ==========================================================
# MODEL DIRECTORY
# ==========================================================

BASE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "models",
)


def artifact(filename):
    return os.path.join(
        BASE_PATH,
        filename,
    )


# ==========================================================
# LOAD INDIVIDUAL ARTIFACTS
# ==========================================================

def load_model():

    loaded = joblib.load(
        artifact("football_model.pkl")
    )

    if isinstance(loaded, dict):
        return loaded["model"]

    return loaded


def load_scaler():

    scaler_path = artifact("scaler.pkl")

    if os.path.exists(scaler_path):

        return joblib.load(scaler_path)

    return None


def load_encoder():

    return joblib.load(
        artifact("team_encoder.pkl")
    )


def load_elo():

    return joblib.load(
        artifact("team_elo.pkl")
    )


def load_team_stats():

    return joblib.load(
        artifact("team_stats.pkl")
    )


def load_metadata():

    metadata_path = artifact(
        "training_metadata.pkl"
    )

    if os.path.exists(metadata_path):

        return joblib.load(
            metadata_path
        )

    return None


# ==========================================================
# LOAD EVERYTHING
# ==========================================================

def load_all():

    return {

        "model": load_model(),

        "scaler": load_scaler(),

        "encoder": load_encoder(),

        "elo": load_elo(),

        "team_stats": load_team_stats(),

        "metadata": load_metadata(),

    }


# ==========================================================
# CACHE
# ==========================================================

_cache_lock = threading.Lock()
_cache = {"stamp": None, "assets": None}


def _stamp():
    """Changes whenever retraining rewrites the model file."""

    try:
        return os.path.getmtime(artifact("football_model.pkl"))
    except OSError:
        return None


def load_all_cached():
    """
    Process-wide cached artifacts.

    The cache is keyed on the model file's modification time, so a model that
    was retrained by ANOTHER worker process is picked up automatically instead
    of every worker serving a stale model until restart.
    """

    stamp = _stamp()

    if _cache["assets"] is not None and _cache["stamp"] == stamp:
        return _cache["assets"]

    with _cache_lock:
        if _cache["assets"] is None or _cache["stamp"] != stamp:
            _cache["assets"] = load_all()
            _cache["stamp"] = stamp

        return _cache["assets"]


def _cache_clear():
    with _cache_lock:
        _cache["assets"] = None
        _cache["stamp"] = None


load_all_cached.cache_clear = _cache_clear


# ==========================================================
# MODEL STATUS
# ==========================================================

def model_status():

    artifacts = {

        "football_model": "football_model.pkl",

        "scaler": "scaler.pkl",

        "team_encoder": "team_encoder.pkl",

        "team_elo": "team_elo.pkl",

        "team_stats": "team_stats.pkl",

        "training_metadata": "training_metadata.pkl",

    }

    return {

        name: os.path.exists(

            artifact(filename)

        )

        for name, filename in artifacts.items()

    }

# ==========================================================
# RELOAD MODEL ARTIFACTS
# ==========================================================

def reload_model():

    load_all_cached.cache_clear()

    return load_all_cached()
