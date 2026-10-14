// ======================================================
// FOOTY254 TEAMS SERVICE
// ======================================================

import { get } from "./api";
import { fallbackTeams } from "../data/mockData";

// ======================================================
// GET ALL TEAMS
// ======================================================

export async function getTeams() {

  try {

    const data = await get("/teams");

    return {

      count:
        data.count ??
        data.teams?.length ??
        0,

      teams: Array.isArray(data.teams)
        ? data.teams
        : fallbackTeams(),

    };

  } catch (error) {

    console.warn(
      "Unable to load teams from backend. Using fallback teams.",
      error
    );

    return {

      count: fallbackTeams().length,

      teams: fallbackTeams(),

    };

  }

}

// ======================================================
// FIND TEAM
// ======================================================

export async function findTeam(name) {

  const data = await getTeams();

  return data.teams.find(

    team =>

      team.toLowerCase() ===
      name.toLowerCase()

  );

}

// ======================================================
// SEARCH TEAMS
// ======================================================

export async function searchTeams(query) {

  const data = await getTeams();

  if (!query) {

    return data.teams;

  }

  return data.teams.filter(team =>

    team
      .toLowerCase()
      .includes(
        query.toLowerCase()
      )

  );

}