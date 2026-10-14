import logging
import os
from datetime import datetime, timedelta
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from dotenv import load_dotenv

load_dotenv()

# ==========================================================
# LOGGING
# ==========================================================

logger = logging.getLogger(__name__)

# ==========================================================
# CONFIGURATION
# ==========================================================

API_KEY = os.getenv("FOOTBALL_API_KEY", "").strip()

# A missing key must not stop the whole app (login, subscriptions and stored
# predictions all work without it); only live data collection is disabled, and
# _request() reports that clearly.
if not API_KEY:
    logger.warning(
        "FOOTBALL_API_KEY is not set: fixture synchronisation is disabled."
    )

BASE_URL = "https://api.football-data.org/v4"

DEFAULT_TIMEOUT = 20

HEADERS = {
    "X-Auth-Token": API_KEY,
}

# ==========================================================
# HTTP SESSION
# ==========================================================

session = requests.Session()

retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[
        429,
        500,
        502,
        503,
        504,
    ],
    allowed_methods=["GET"],
)

adapter = HTTPAdapter(max_retries=retry_strategy)

session.mount("https://", adapter)
session.mount("http://", adapter)

# ==========================================================
# INTERNAL REQUEST HELPER
# ==========================================================

def _request(
    endpoint: str,
    params: dict | None = None,
) -> dict[str, Any]:

    url = f"{BASE_URL}{endpoint}"

    if not API_KEY:
        logger.error("FOOTBALL_API_KEY is not set; skipping %s", endpoint)
        return {}

    try:

        response = session.get(
            url,
            headers=HEADERS,
            params=params,
            timeout=DEFAULT_TIMEOUT,
        )

        response.raise_for_status()

        # Optional logging of remaining API quota
        remaining = response.headers.get("X-Requests-Available-Minute")
        if remaining:
            logger.debug(
                "API requests remaining this minute: %s",
                remaining,
            )

        return response.json()

    except requests.exceptions.HTTPError as e:

        logger.error(
            "Football API HTTP Error: %s",
            e,
        )

    except requests.exceptions.Timeout:

        logger.error(
            "Football API request timed out."
        )

    except requests.exceptions.ConnectionError:

        logger.error(
            "Unable to connect to football-data.org"
        )

    except Exception:

        logger.exception(
            "Unexpected error while contacting football-data.org"
        )

    return {}

DEFAULT_DAYS_AHEAD = 30

RETENTION_DAYS = 30

# ==========================================================
# DATE HELPERS
# ==========================================================

def today_iso() -> str:

    return datetime.utcnow().date().isoformat()


def future_iso(days: int) -> str:

    return (
        datetime.utcnow().date() +
        timedelta(days=days)
    ).isoformat()


def past_iso(days: int) -> str:

    return (
        datetime.utcnow().date() -
        timedelta(days=days)
    ).isoformat()


future_iso(DEFAULT_DAYS_AHEAD)

past_iso(RETENTION_DAYS)

# ==========================================================
# MATCHES BY COMPETITION
# ==========================================================

def fetch_competition_matches(
    competition_code: str,
    status: str | None = None,
    season: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
):
    """
    Fetch matches for a competition.

    Optional filters:
        status
        season
        date_from
        date_to
    """

    params = {}

    if status:
        params["status"] = status

    if season:
        params["season"] = season

    if date_from:
        params["dateFrom"] = date_from

    if date_to:
        params["dateTo"] = date_to

    data = _request(
        f"/competitions/{competition_code}/matches",
        params=params,
    )

    return data.get("matches", [])

# ==========================================================
# MATCHES BY DATE RANGE
# ==========================================================

def fetch_matches_by_date(
    date_from: str,
    date_to: str,
):

    data = _request(
        "/matches",
        {
            "dateFrom": date_from,
            "dateTo": date_to,
        },
    )

    return data.get("matches", [])

# ==========================================================
# UPCOMING MATCHES
# ==========================================================

def fetch_upcoming_matches(
    days_ahead: int = 30,
):

    return fetch_matches_by_date(
        past_iso(30),
        future_iso(days_ahead),
    )

def past_iso(days: int) -> str:

    return (
        datetime.utcnow().date()
        - timedelta(days=days)
    ).isoformat()

# ==========================================================
# LIVE MATCHES
# ==========================================================

def fetch_live_matches():

    data = _request(
        "/matches",
        {
            "status": "LIVE"
        },
    )

    return data.get("matches", [])


# ==========================================================
# TIMED MATCHES
# ==========================================================

def fetch_timed_matches():

    data = _request(
        "/matches",
        {
            "status": "TIMED"
        },
    )

    return data.get("matches", [])

# ==========================================================
# FINISHED MATCHES
# ==========================================================

def fetch_finished_matches():

    data = _request(
        "/matches",
        {
            "status": "FINISHED"
        },
    )

    return data.get("matches", [])

# ==========================================================
# MATCHES BY STATUS
# ==========================================================

def fetch_matches_by_status(
    status: str,
):

    data = _request(
        "/matches",
        {
            "status": status
        },
    )

    return data.get("matches", [])

# ==========================================================
# SINGLE MATCH
# ==========================================================

def fetch_match(
    match_id: int,
):

    return _request(
        f"/matches/{match_id}"
    )

# ==========================================================
# COMPETITIONS
# ==========================================================

def fetch_competitions():

    data = _request(
        "/competitions"
    )

    return data.get(
        "competitions",
        [],
    )

# ==========================================================
# COMPETITION TEAMS
# ==========================================================

def fetch_competition_teams(
    competition_code: str,
):

    data = _request(
        f"/competitions/{competition_code}/teams"
    )

    return data.get(
        "teams",
        [],
    )

# ==========================================================
# API HEALTH CHECK
# ==========================================================

def ping() -> bool:

    try:

        competitions = fetch_competitions()

        return len(competitions) > 0

    except Exception:

        return False