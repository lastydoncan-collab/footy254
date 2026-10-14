import { teams } from "./teams.js";

export const featuredFixtures = [
  { home: "Liverpool FC", away: "Arsenal FC", kickoff: "19:30", league: "Premier League" },
  { home: "Manchester City FC", away: "Chelsea FC", kickoff: "21:00", league: "Premier League" },
  { home: "Real Madrid CF", away: "FC Barcelona", kickoff: "22:15", league: "La Liga" },
  { home: "Bayern Munich", away: "Paris Saint-Germain", kickoff: "23:00", league: "Champions League" },
];

export function fallbackPrediction(home, away) {
  const seed = `${home}${away}`.split("").reduce((sum, char) => sum + char.charCodeAt(0), 0);
  const homeWin = 36 + (seed % 24);
  const draw = 18 + (seed % 13);
  const awayWin = Math.max(8, 100 - homeWin - draw);
  const prediction =
    homeWin >= awayWin && homeWin >= draw ? `${home} win` : awayWin >= draw ? `${away} win` : "Draw";

  return {
    home,
    away,
    prediction,
    confidence: Math.min(94, Math.max(homeWin, draw, awayWin) + 24),
    probabilities: {
      home_win: homeWin,
      draw,
      away_win: awayWin,
    },
    xg: {
      home: (1.1 + (homeWin / 100) * 1.8).toFixed(2),
      away: (0.8 + (awayWin / 100) * 1.7).toFixed(2),
    },
  };
}

export function fallbackMatches() {
  return featuredFixtures.map((fixture) => ({
    ...fallbackPrediction(fixture.home, fixture.away),
    kickoff: fixture.kickoff,
    league: fixture.league,
  }));
}

export function fallbackTeams() {
  return teams;
}
