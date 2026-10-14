// ======================================================
// FOOTY254 DASHBOARD SERVICE
// ======================================================

import { getTeams } from "./teams";
import { getUpcomingFixtures } from "./fixtures";
import { getSyncStatus } from "./sync";

// ======================================================
// LOAD DASHBOARD
// ======================================================
//
// Promise.allSettled instead of Promise.all: these three calls hit
// independent backend concerns (sync status, teams, fixtures). If any one
// of them is briefly down, the other two still have data worth showing —
// Promise.all would have thrown away all three and crashed the page.

export async function loadDashboard() {

  const [
    syncResult,
    teamsResult,
    fixturesResult,
  ] = await Promise.allSettled([

    getSyncStatus(),

    getTeams(),

    getUpcomingFixtures(),

  ]);

  if (syncResult.status === "rejected") {
    console.error("Dashboard: sync status unavailable.", syncResult.reason);
  }
  if (teamsResult.status === "rejected") {
    console.error("Dashboard: teams unavailable.", teamsResult.reason);
  }
  if (fixturesResult.status === "rejected") {
    console.error("Dashboard: fixtures unavailable.", fixturesResult.reason);
  }

  const sync =
    syncResult.status === "fulfilled" ? syncResult.value : {};

  const teams =
    teamsResult.status === "fulfilled" ? teamsResult.value : {};

  const fixtures =
    fixturesResult.status === "fulfilled" ? fixturesResult.value : {};

  const upcomingFixtures =
    fixtures.fixtures || [];

  const totalTeams =
    teams.teams?.length || 0;

  const liveMatches =
    upcomingFixtures.filter(

      match =>

        match.status === "LIVE" ||

        match.status === "IN_PLAY"

    );

  const todaysMatches =
    upcomingFixtures.filter(

      match =>

        match.match_date ===
        today()

    );

  return {

    service:

      sync.service,

    status:

      sync.status,

    model:

      sync.model,

    pipeline:

      sync.pipeline,

    totalTeams,

    totalFixtures:

      upcomingFixtures.length,

    liveMatches:

      liveMatches.length,

    todaysMatches:

      todaysMatches.length,

    upcomingFixtures,

    // Lets the UI show a subtle "some data may be stale" notice rather than
    // pretending everything loaded when it didn't.
    partial:

      syncResult.status === "rejected" ||
      teamsResult.status === "rejected" ||
      fixturesResult.status === "rejected",

  };

}

// ======================================================
// TODAY
// ======================================================

function today() {

  return new Date()

    .toISOString()

    .split("T")[0];

}

// ======================================================
// RECENT FIXTURES
// ======================================================

export async function getRecentFixtures(
  limit = 5
) {

  const data =
    await getUpcomingFixtures();

  return data.fixtures.slice(
    0,
    limit
  );

}

// ======================================================
// DASHBOARD STATS
// ======================================================

export async function getDashboardStats() {

  const dashboard =
    await loadDashboard();

  return [

    {

      title: "Teams",

      value: dashboard.totalTeams,

    },

    {

      title: "Upcoming",

      value: dashboard.totalFixtures,

    },

    {

      title: "Live",

      value: dashboard.liveMatches,

    },

    {

      title: "Today",

      value: dashboard.todaysMatches,

    },

  ];

}