from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from data_pipeline.data_fetcher import fetch_competition_matches

logger = logging.getLogger(__name__)

# ==========================================================
# CONFIGURATION
# ==========================================================

DEFAULT_DAYS_AHEAD = 30

TRACKED_COMPETITION_CODES = (
    "PL",      # Premier League
    "PD",      # La Liga
    "BL1",     # Bundesliga
    "SA",      # Serie A
    "FL1",     # Ligue 1
    "ELC",     # Championship
    "CL",      # Champions League
    "WC"       #FIFA World Cup
)

VALID_STATUSES = {
    "SCHEDULED",
    "TIMED",
    "LIVE",
    "IN_PLAY",
    "PAUSED",
    "FINISHED",
}

# ==========================================================
# DATETIME HELPERS
# ==========================================================

def parse_utc_datetime(value: str) -> datetime:
    """
    Convert football-data.org UTC datetime string
    into a timezone-aware datetime.
    """

    return datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )


# ==========================================================
# MATCH NORMALIZATION
# ==========================================================

def normalize_match(match: dict[str, Any]) -> dict[str, Any]:
    """
    Convert football-data.org response into
    FOOTY254 internal fixture structure.
    """

    kickoff = parse_utc_datetime(match["utcDate"])

    score = match.get("score") or {}

    full_time = score.get("fullTime") or {}

    return {

        # -------------------------
        # Match
        # -------------------------

        "match_id": match["id"],

        "status": match["status"],

        "stage": match.get("stage"),

        "matchday": match.get("matchday"),

        # -------------------------
        # Competition
        # -------------------------

        "competition_id": match["competition"]["id"],

        "competition": match["competition"]["name"],

        "competition_code": match["competition"]["code"],

        "season": match["season"]["id"],

        # -------------------------
        # Home Team
        # -------------------------

        "home_team_id": match["homeTeam"]["id"],

        "home_team": match["homeTeam"]["name"],

        # -------------------------
        # Away Team
        # -------------------------

        "away_team_id": match["awayTeam"]["id"],

        "away_team": match["awayTeam"]["name"],

        # -------------------------
        # Kickoff
        # -------------------------

        "utc_date": kickoff,

        "match_date": kickoff.date(),

        "kickoff_time": kickoff.time(),

        "kickoff": kickoff,

        # -------------------------
        # Scores
        # -------------------------

        "score_home": full_time.get("home"),

        "score_away": full_time.get("away"),

        "winner": score.get("winner"),
    }


# ==========================================================
# FETCH UPCOMING MATCHES
# ==========================================================
RETENTION_DAYS = 30

def fetch_upcoming_matches(
    days_ahead: int = DEFAULT_DAYS_AHEAD,
) -> list[dict[str, Any]]:
    """
    Download all tracked competition fixtures
    occurring within the next `days_ahead` days.
    """

    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=days_ahead)
    retention_cutoff = now - timedelta(days=RETENTION_DAYS)
    future_cutoff = cutoff

    cutoff = now + timedelta(days=days_ahead)

    fixtures = []

    seen_match_ids = set()

    logger.info(
        "Collecting fixtures for next %d days...",
        days_ahead,
    )

    for competition in TRACKED_COMPETITION_CODES:

        try:

            matches = fetch_competition_matches(
                competition_code=competition,
                date_from=datetime.now(timezone.utc).date().isoformat(),
                date_to=cutoff.date().isoformat(),
            )

            logger.info(
                "%s -> %d matches",
                competition,
                len(matches),
            )

            for match in matches:

                if not match:
                    continue

                status = match.get("status")

                if status not in VALID_STATUSES:
                    continue

                kickoff = parse_utc_datetime(match["utcDate"])

                if kickoff < retention_cutoff:
                    continue

                if kickoff > future_cutoff:
                    continue

                match_id = match["id"]

                if match_id in seen_match_ids:
                    continue

                seen_match_ids.add(match_id)

                fixtures.append(
                    normalize_match(match)
                )

        except Exception:

            logger.exception(
                "Unable to process competition %s",
                competition,
            )

    fixtures.sort(
        key=lambda fixture: fixture["kickoff"]
    )

    logger.info(
        "Collected %d unique fixtures.",
        len(fixtures),
    )

    return fixtures
