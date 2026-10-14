from datetime import datetime


def normalize_fixture(raw_match):
    """
    Converts Football-Data.org response into the FOOTY254 fixture schema.
    """

    competition = raw_match.get("competition", {})

    season = raw_match.get("season", {})

    home = raw_match.get("homeTeam", {})

    away = raw_match.get("awayTeam", {})

    score = raw_match.get("score", {})

    fulltime = score.get("fullTime", {})

    fixture = {
        # --------------------------------------------------
        # IDs
        # --------------------------------------------------
        "match_id": raw_match.get("id"),

        # --------------------------------------------------
        # Competition
        # --------------------------------------------------
        "competition": competition.get("name"),
        "competition_code": competition.get("code"),

        # --------------------------------------------------
        # Season
        # --------------------------------------------------
        "season": season.get("startDate", "")[:4]
        if season.get("startDate")
        else None,

        "matchday": raw_match.get("matchday"),

        "stage": raw_match.get("stage"),

        # --------------------------------------------------
        # Teams
        # --------------------------------------------------
        "home_team": home.get("name"),
        "away_team": away.get("name"),

        # --------------------------------------------------
        # Date
        # --------------------------------------------------
        "match_date": raw_match.get("utcDate")[:10]
        if raw_match.get("utcDate")
        else None,

        "kickoff": raw_match.get("utcDate"),

        # --------------------------------------------------
        # Status
        # --------------------------------------------------
        "status": raw_match.get("status"),

        # --------------------------------------------------
        # Score
        # --------------------------------------------------
        "score_home": fulltime.get("home"),

        "score_away": fulltime.get("away"),
    }

    home_goals = fixture["score_home"]
    away_goals = fixture["score_away"]

    if home_goals is None or away_goals is None:
        fixture["winner"] = None

    elif home_goals > away_goals:
        fixture["winner"] = "HOME"

    elif away_goals > home_goals:
        fixture["winner"] = "AWAY"

    else:
        fixture["winner"] = "DRAW"

    return fixture