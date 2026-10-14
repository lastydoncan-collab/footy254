// ======================================================
// FOOTY254 FIXTURES SERVICE
// ======================================================

import {
  get,
  post,
} from "./api";

import {
  fallbackMatches,
} from "../data/mockData";

// ======================================================
// GET UPCOMING FIXTURES
// ======================================================

export async function getUpcomingFixtures() {

  try {

    const data = await get(
      "/fixtures/upcoming"
    );

    return {

      count:
        data.count ??
        0,

      fixtures: Array.isArray(
        data.fixtures
      )
        ? data.fixtures
        : [],

    };

  } catch (error) {

    console.warn(
      "Unable to load upcoming fixtures. Using fallback data.",
      error
    );

    const fixtures = fallbackMatches();

    return {

      count: fixtures.length,

      fixtures,

    };

  }

}

// ======================================================
// GET LIVE FIXTURES
// ======================================================
//
// Unlike predictions, live fixture status (score, kickoff, in-progress
// state) is public — /fixtures/live has no auth requirement on the
// backend. No mock fallback here: fabricating a fake "match in progress"
// when the backend is actually unreachable would be actively misleading,
// unlike the upcoming-fixtures fallback above (which only fills in
// schedule placeholders, not live state).

export async function getLiveFixtures() {

  const data = await get("/fixtures/live");

  return {

    count: data.count ?? 0,

    fixtures: Array.isArray(data.fixtures)
      ? data.fixtures
      : [],

  };

}

// ======================================================
// GET FIXTURE DETAILS
// ======================================================

export async function getFixture(matchId) {

  return await get(
    `/fixtures/${matchId}`
  );

}

// ======================================================
// SYNCHRONIZE FIXTURES
// ======================================================

export async function syncFixtures(
  daysAhead = 7
) {

  return await post(
    `/sync/fixtures?days_ahead=${daysAhead}`
  );

}

// ======================================================
// GET FIXTURE BY ID
// ======================================================

export async function findFixture(
  matchId
) {

  const data =
    await getUpcomingFixtures();

  return data.fixtures.find(

    fixture =>

      Number(fixture.match_id) ===
      Number(matchId)

  );

}

// ======================================================
// FILTER BY COMPETITION
// ======================================================

export async function getFixturesByCompetition(
  competitionCode
) {

  const data =
    await getUpcomingFixtures();

  return data.fixtures.filter(

    fixture =>

      fixture.competition_code ===
      competitionCode

  );

}

// ======================================================
// FILTER BY TEAM
// ======================================================

export async function getFixturesByTeam(
  teamName
) {

  const data =
    await getUpcomingFixtures();

  return data.fixtures.filter(

    fixture =>

      fixture.home_team === teamName ||

      fixture.away_team === teamName

  );

}