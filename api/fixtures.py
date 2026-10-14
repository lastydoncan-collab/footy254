from fastapi import APIRouter, HTTPException

from services.cache import ttl_cache

from database.fixtures_repository import (
    get_fixture,
    get_live_fixtures,
    get_upcoming_fixtures,
    get_finished_fixtures,
    fixture_statistics,
)

router = APIRouter(
    prefix="/fixtures",
    tags=["Fixtures"],
)

# ==========================================================
# SERIALIZER
# ==========================================================

def serialize_fixture(fixture):

    if fixture is None:
        return None

    return {

        # -------------------------
        # Match
        # -------------------------

        "match_id": fixture.get("match_id"),

        "status": fixture.get("status"),

        "stage": fixture.get("stage"),

        "matchday": fixture.get("matchday"),

        # -------------------------
        # Competition
        # -------------------------

        "competition_id": fixture.get("competition_id"),

        "competition": fixture.get("competition"),

        "competition_code": fixture.get("competition_code"),

        "season": fixture.get("season"),

        # -------------------------
        # Teams
        # -------------------------

        "home_team_id": fixture.get("home_team_id"),

        "away_team_id": fixture.get("away_team_id"),

        "home_team": fixture.get("home_team"),

        "away_team": fixture.get("away_team"),

        # -------------------------
        # Fixture
        # -------------------------

        "utc_date": fixture.get("utc_date"),

        "match_date": fixture.get("match_date"),

        "kickoff_time": fixture.get("kickoff_time"),

        "kickoff": fixture.get("kickoff"),

        "score_home": fixture.get("score_home"),

        "score_away": fixture.get("score_away"),

        "winner": fixture.get("winner"),

        "last_updated": fixture.get("last_updated"),
    }


@ttl_cache(30)
def _cached_upcoming():
    return get_upcoming_fixtures()


@ttl_cache(10)
def _cached_live():
    return get_live_fixtures()


# ==========================================================
# UPCOMING FIXTURES
# ==========================================================

@router.get("/")
@router.get("/upcoming")
def upcoming_fixtures():

    fixtures = _cached_upcoming()

    return {

        "success": True,

        "count": len(fixtures),

        "window_days": 30,

        "fixtures": [

            serialize_fixture(fixture)

            for fixture in fixtures

        ],

    }


# ==========================================================
# LIVE FIXTURES
# ==========================================================

@router.get("/live")
def live_fixtures():

    fixtures = _cached_live()

    return {

        "success": True,

        "count": len(fixtures),

        "fixtures": [

            serialize_fixture(fixture)

            for fixture in fixtures

        ],

    }


# ==========================================================
# FIXTURE STATUS
# ==========================================================

@router.get("/status/summary")
def fixture_status():

    stats = fixture_statistics()

    return {

        "success": True,

        "statistics": stats,

    }

# ==========================================================
# FINISHED FIXTURES
# ==========================================================

@router.get("/finished")
def finished_fixtures():

    fixtures = get_finished_fixtures()

    return {

        "success": True,

        "count": len(fixtures),

        "fixtures": [

            serialize_fixture(fixture)

            for fixture in fixtures

        ],

    }


# Declared LAST: '/{match_id}' matches any single path segment, so placing it
# earlier shadowed '/finished' (it answered 422 'not an integer').
# ==========================================================
# SINGLE FIXTURE
# ==========================================================

@router.get("/{match_id}")
def fixture_details(match_id: int):

    fixture = get_fixture(match_id)

    if fixture is None:
        raise HTTPException(
            status_code=404,
            detail="Fixture not found.",
        )

    return {

    "success": True,

    "fixture": serialize_fixture(fixture),

}
