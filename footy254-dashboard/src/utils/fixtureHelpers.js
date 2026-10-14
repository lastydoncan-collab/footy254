// Small helpers shared by the fixture grids (Predict, Live, Home).

const LIVE_STATUSES = new Set(["LIVE", "IN_PLAY", "PAUSED"]);

export function isLiveMatch(match) {
  return LIVE_STATUSES.has(String(match?.status || "").toUpperCase());
}

// Calendar day in Nairobi, e.g. "2026-10-13".
export function nairobiDay(date = new Date()) {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Africa/Nairobi" }).format(date);
}

export function isToday(match) {
  const raw = match?.kickoff || match?.utc_date || match?.match_date;
  if (!raw) return false;
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return String(raw).slice(0, 10) === nairobiDay();
  return nairobiDay(d) === nairobiDay();
}

// Home/draw/away as 0-100 numbers (the API may send 0-1 or 0-100).
export function getProbabilities(match) {
  const raw = [
    match?.home_win_probability ?? match?.home_win ?? match?.homeWin,
    match?.draw_probability ?? match?.draw,
    match?.away_win_probability ?? match?.away_win ?? match?.awayWin,
  ].map((v) => (v == null || v === "" ? null : Number(v)));

  if (raw.some((v) => v == null || Number.isNaN(v))) return null;

  const scale = Math.max(...raw) <= 1 ? 100 : 1;
  return raw.map((v) => v * scale);
}

export function sortByFavoriteLeague(matches, league) {
  if (!league || league === "All Leagues") return matches;
  return [...matches].sort((a, b) => {
    const am = (a.competition || "").includes(league) ? 0 : 1;
    const bm = (b.competition || "").includes(league) ? 0 : 1;
    return am - bm;
  });
}
