import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { randomBytes } from "node:crypto";

import {
  InsufficientFundsError,
  BettingError,
  getOrCreateWallet,
  getWalletTransactions,
  topUpWallet,
  placeSingleBet,
  placeMultiBet,
  getBetSlip,
  listBetSlips,
  settleFixtureLegs,
} from "./betting.mjs";

const root = fileURLToPath(new URL(".", import.meta.url));
const port = Number(process.env.PORT || 4173);
const host = "127.0.0.1";
const cache = new Map();
const API_ROOT = "https://v3.football.api-sports.io";
const SESSION_COOKIE = "pitchiq_session";
const SESSION_MAX_AGE_DAYS = 180;

await loadDotEnv();
const apiKey = process.env.APISPORTS_KEY || process.env.API_FOOTBALL_KEY || "";

const demoFixtures = [
  fixture("demo-1", "Premier League", "Man City", "Everton", "17:30 EAT", "NS", null, null, [1.42, 4.8, 7.6], [67, 20, 13], 82),
  fixture("demo-2", "La Liga", "Real Madrid", "Getafe", "19:00 EAT", "NS", null, null, [1.38, 5.0, 8.2], [64, 22, 14], 76),
  fixture("demo-3", "Serie A", "Inter Milan", "Torino", "20:45 EAT", "NS", null, null, [1.62, 3.7, 6.0], [58, 25, 17], 71),
  fixture("demo-4", "Premier League", "Arsenal", "Fulham", "20:00 EAT", "NS", null, null, [1.55, 4.1, 6.2], [61, 23, 16], 74),
  fixture("demo-5", "Champions League", "Barcelona", "Dortmund", "22:00 EAT", "NS", null, null, [1.85, 3.8, 3.9], [48, 27, 25], 67),
  fixture("demo-6", "La Liga", "Atlético", "Sevilla", "21:00 EAT", "NS", null, null, [1.78, 3.4, 5.1], [52, 29, 19], 64),
];

const server = createServer(async (request, response) => {
  setHeaders(response);
  const url = new URL(request.url || "/", `http://${host}:${port}`);
  try {
    if (url.pathname.startsWith("/api/")) {
      if (request.method === "OPTIONS") return send(response, 204, null);
      if (request.method !== "GET" && request.method !== "POST")
        return send(response, 405, { error: "Method not allowed" });
      if (url.pathname === "/api/status")
        return send(response, 200, {
          provider: "API-Football",
          configured: Boolean(apiKey),
          mode: apiKey ? "live-data / paper-bets" : "sample-data / paper-bets",
          realWageringEnabled: false,
          refreshedAt: new Date().toISOString(),
        });
      if (url.pathname === "/api/fixtures" && request.method === "GET")
        return await getFixtures(url, response);
      if (url.pathname === "/api/odds" && request.method === "GET")
        return await getOdds(url, response);
      if (url.pathname === "/api/predictions" && request.method === "GET")
        return await getPrediction(url, response);
      if (url.pathname === "/api/wallet" && request.method === "GET")
        return send(response, 200, getOrCreateWallet(sessionId(request, response)));
      if (url.pathname === "/api/wallet/transactions" && request.method === "GET")
        return send(response, 200, { transactions: getWalletTransactions(sessionId(request, response)) });
      if (url.pathname === "/api/wallet/topup" && request.method === "POST")
        return await walletTopUp(request, response);
      if (url.pathname === "/api/bets/place" && request.method === "POST")
        return await placePaperBet(request, response);
      if (url.pathname === "/api/bets" && request.method === "GET")
        return send(response, 200, { bets: listBetSlips(sessionId(request, response)) });
      const betMatch = url.pathname.match(/^\/api\/bets\/(\d+)$/);
      if (betMatch && request.method === "GET") {
        const slip = getBetSlip(sessionId(request, response), Number(betMatch[1]));
        if (!slip) return send(response, 404, { error: "Bet slip not found" });
        return send(response, 200, slip);
      }
      if (url.pathname === "/api/bets/settle" && request.method === "POST")
        return await settleFixture(request, response);
      return send(response, 404, { error: "API route not found" });
    }
    if (request.method !== "GET" && request.method !== "HEAD")
      return send(response, 405, { error: "Method not allowed" });
    const relative = url.pathname === "/" ? "index.html" : decodeURIComponent(url.pathname.slice(1));
    const target = resolve(root, normalize(relative));
    const rootPath = resolve(root);
    if (target !== rootPath && !target.startsWith(`${rootPath}/`) && !target.startsWith(`${rootPath}\\`))
      return send(response, 403, "Forbidden", "text/plain");
    const data = await readFile(target);
    response.writeHead(200, { "content-type": mimeType(extname(target)) });
    response.end(request.method === "HEAD" ? undefined : data);
  } catch (error) {
    send(response, 500, { error: error instanceof Error ? error.message : "Unexpected server error" });
  }
});

server.listen(port, host, () => {
  console.log(`PitchIQ ready at http://${host}:${port}`);
  console.log(`Football data: ${apiKey ? "API-Football connected" : "sample data (add APISPORTS_KEY)"}`);
  console.log("Wagering: paper mode only; no deposits or real-money bets are enabled.");
});

async function getFixtures(url, response) {
  const view = url.searchParams.get("view") || "today";
  if (!apiKey)
    return send(response, 200, { mode: "sample", view, updatedAt: new Date().toISOString(), data: view === "live" ? [] : demoFixtures });
  const params = view === "live"
    ? { live: "all", timezone: "Africa/Nairobi" }
    : view === "upcoming"
      ? { from: localDate(0), to: localDate(6), timezone: "Africa/Nairobi" }
      : { date: localDate(0), timezone: "Africa/Nairobi" };
  const ttl = view === "live" ? 15000 : 60000;
  const result = await cached(`fixtures:${view}`, ttl, () => apiFootball("/fixtures", params));
  return send(response, 200, { mode: "live", view, updatedAt: new Date().toISOString(), data: result.map(mapFixture) });
}

async function getOdds(url, response) {
  const id = requiredId(url.searchParams.get("fixture"));
  if (!apiKey) {
    const sample = demoFixtures.find((item) => item.id === id);
    if (!sample) return send(response, 404, { error: "Fixture not found in sample set" });
    return send(response, 200, { mode: "sample", updatedAt: new Date().toISOString(), data: sample.odds });
  }
  const live = url.searchParams.get("live") === "1";
  const path = live ? "/odds/live" : "/odds";
  // API-Football's pre-match prices update on a much longer cadence than live scores.
  const ttl = live ? 15000 : 10800000;
  const result = await cached(`odds:${live ? "live:" : "pre:"}${id}`, ttl, () => apiFootball(path, { fixture: id }));
  return send(response, 200, { mode: "live", updatedAt: new Date().toISOString(), data: firstMarket(result) });
}

async function getPrediction(url, response) {
  const id = requiredId(url.searchParams.get("fixture"));
  if (!apiKey) {
    const sample = demoFixtures.find((item) => item.id === id);
    if (!sample) return send(response, 404, { error: "Fixture not found in sample set" });
    return send(response, 200, { mode: "sample", updatedAt: new Date().toISOString(), data: sample.prediction });
  }
  const result = await cached(`prediction:${id}`, 3600000, () => apiFootball("/predictions", { fixture: id }));
  const raw = result[0];
  if (!raw) return send(response, 404, { error: "No forecast is available for this fixture" });
  const percent = raw.predictions?.percent || {};
  return send(response, 200, {
    mode: "live",
    updatedAt: new Date().toISOString(),
    data: {
      home: percent.home ? parsePercent(percent.home) : null,
      draw: percent.draw ? parsePercent(percent.draw) : null,
      away: percent.away ? parsePercent(percent.away) : null,
      advice: raw.predictions?.advice || "No model advice available",
      winner: raw.predictions?.winner?.name || null,
      goals: raw.predictions?.goals || null,
      source: "API-Football predictions",
    },
  });
}

async function placePaperBet(request, response) {
  const session = sessionId(request, response);
  const body = await readJson(request);
  if (body?.mode !== "paper")
    return send(response, 403, { error: "Real-money wagering is disabled. Configure a licensed operator integration before enabling cash bets." });
  const selections = Array.isArray(body.selections) ? body.selections : [];
  const stake = Number(body.stake);
  const kind = body.kind;

  const picks = selections.map((pick) => ({
    fixtureId: String(pick.fixtureId ?? ""),
    key: String(pick.key ?? ""),
    match: String(pick.match ?? "Fixture"),
    league: pick.league ? String(pick.league) : null,
    market: pick.market ? String(pick.market) : null,
    label: String(pick.label ?? ""),
    odds: Number(pick.odds),
  }));

  try {
    const slip = kind === "single"
      ? placeSingleBet(session, picks, stake)
      : placeMultiBet(session, picks, stake, kind);

    return send(response, 201, {
      betId: `PAPER-${slip.id}`,
      mode: "paper",
      kind: slip.bet_type,
      selectionCount: slip.legs.length,
      totalStake: slip.stake,
      combinedOdds: slip.combined_odds,
      potentialReturn: slip.potential_payout,
      wallet: getOrCreateWallet(session),
      message: "Paper bet recorded in your persistent demo wallet. No real money was taken and no real bet was placed.",
      createdAt: slip.placed_at,
    });
  } catch (error) {
    if (error instanceof InsufficientFundsError) return send(response, 402, { error: error.message });
    if (error instanceof BettingError) return send(response, 400, { error: error.message });
    throw error;
  }
}

async function walletTopUp(request, response) {
  const session = sessionId(request, response);
  const body = await readJson(request);
  try {
    const balance = topUpWallet(session, Number(body.amount));
    return send(response, 200, { balance, message: "Demo wallet topped up. This is paper money, not real currency." });
  } catch (error) {
    if (error instanceof BettingError) return send(response, 400, { error: error.message });
    throw error;
  }
}

/**
 * Resolve every pending bet leg on one fixture.
 *  - demo-* fixtures: outcome is a weighted-random draw from that sample
 *    fixture's own forecast percentages (decided server-side, not by the
 *    client, so the "simulate" button can't be used to force a win).
 *  - real API-Football fixture IDs: outcome is the fixture's actual final
 *    score, fetched fresh from the provider — requires APISPORTS_KEY and
 *    the match to have finished.
 */
async function settleFixture(request, response) {
  const body = await readJson(request);
  const fixtureId = String(body.fixtureId || "");
  if (!fixtureId) return send(response, 400, { error: "fixtureId is required." });

  try {
    let winner;

    if (fixtureId.startsWith("demo-")) {
      const sample = demoFixtures.find((item) => item.id === fixtureId);
      if (!sample) return send(response, 404, { error: "Unknown sample fixture." });
      winner = weightedOutcome(sample.prediction);
    } else {
      if (!apiKey) return send(response, 400, { error: "Connect an API-Football key, or use a sample (demo-*) fixture to simulate settlement." });
      const result = await apiFootball("/fixtures", { id: fixtureId });
      const match = result[0];
      if (!match) return send(response, 404, { error: "Fixture not found." });
      if (match.fixture?.status?.short !== "FT")
        return send(response, 400, { error: "This fixture hasn't finished yet." });
      const home = Number(match.goals?.home);
      const away = Number(match.goals?.away);
      winner = home > away ? "home" : away > home ? "away" : "draw";
    }

    const result = settleFixtureLegs(fixtureId, winner);
    return send(response, 200, result);
  } catch (error) {
    if (error instanceof BettingError) return send(response, 400, { error: error.message });
    throw error;
  }
}

function weightedOutcome(prediction) {
  const weights = {
    home: Math.max(0, Number(prediction?.home) || 0),
    draw: Math.max(0, Number(prediction?.draw) || 0),
    away: Math.max(0, Number(prediction?.away) || 0),
  };
  const total = weights.home + weights.draw + weights.away || 1;
  const roll = Math.random() * total;
  if (roll < weights.home) return "home";
  if (roll < weights.home + weights.draw) return "draw";
  return "away";
}

// ==========================================================
// SESSION  (cookie-identified persistent paper wallet — no login required)
// ==========================================================

function parseCookies(header = "") {
  const jar = {};
  header.split(";").forEach((part) => {
    const index = part.indexOf("=");
    if (index === -1) return;
    jar[part.slice(0, index).trim()] = decodeURIComponent(part.slice(index + 1).trim());
  });
  return jar;
}

function sessionId(request, response) {
  const cookies = parseCookies(request.headers.cookie);
  let id = cookies[SESSION_COOKIE];
  if (id && /^[a-f0-9]{32}$/.test(id)) return id;
  id = randomBytes(16).toString("hex");
  const maxAge = SESSION_MAX_AGE_DAYS * 86400;
  response.setHeader("set-cookie", `${SESSION_COOKIE}=${id}; Max-Age=${maxAge}; Path=/; HttpOnly; SameSite=Lax`);
  return id;
}

async function apiFootball(path, params) {
  const query = new URLSearchParams(params);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10000);
  try {
    const result = await fetch(`${API_ROOT}${path}?${query}`, {
      headers: { "x-apisports-key": apiKey, accept: "application/json" },
      signal: controller.signal,
    });
    const payload = await result.json();
    if (!result.ok) throw new Error(`API-Football returned HTTP ${result.status}`);
    if (payload.errors && Object.keys(payload.errors).length)
      throw new Error(`API-Football: ${JSON.stringify(payload.errors)}`);
    return payload.response || [];
  } finally {
    clearTimeout(timeout);
  }
}

async function cached(key, ttl, load) {
  const entry = cache.get(key);
  if (entry && entry.until > Date.now()) return entry.value;
  const value = await load();
  cache.set(key, { value, until: Date.now() + ttl });
  return value;
}

function mapFixture(item) {
  return {
    id: String(item.fixture.id),
    league: item.league?.name || "Football",
    country: item.league?.country || "",
    leagueLogo: item.league?.logo || null,
    kickoff: item.fixture?.date || null,
    time: item.fixture?.date || null,
    status: item.fixture?.status?.short || "NS",
    statusLong: item.fixture?.status?.long || "Not started",
    minute: item.fixture?.status?.elapsed ?? null,
    home: item.teams?.home?.name || "Home",
    away: item.teams?.away?.name || "Away",
    homeCode: item.teams?.home?.code || initials(item.teams?.home?.name),
    awayCode: item.teams?.away?.code || initials(item.teams?.away?.name),
    homeLogo: item.teams?.home?.logo || null,
    awayLogo: item.teams?.away?.logo || null,
    homeScore: item.goals?.home,
    awayScore: item.goals?.away,
    venue: item.fixture?.venue?.name || null,
    demo: false,
  };
}

function firstMarket(result) {
  const bookmakers = result.flatMap((entry) => entry.bookmakers || []);
  for (const bookmaker of bookmakers) {
    const markets = (bookmaker.bets || []).map((bet) => ({
      id: String(bet.id ?? bet.name ?? "market"),
      name: bet.name || "Other market",
      values: (bet.values || []).map((value) => ({
        value: String(value.value || ""),
        odds: Number(value.odd),
      })).filter((value) => Number.isFinite(value.odds) && value.odds > 1),
    })).filter((market) => market.values.length);
    const market = markets.find((bet) => /match winner|1x2|full.?time result/i.test(bet.name || ""));
    if (!markets.length) continue;
    const values = market?.values || [];
    const lookup = (pattern) => {
      const entry = values.find((value) => pattern.test(value.value || ""));
      return entry?.odds ?? null;
    };
    const data = {
      home: lookup(/^home$|^1$/i),
      draw: lookup(/^draw$|^x$/i),
      away: lookup(/^away$|^2$/i),
      market: market?.name || "Match markets",
      markets,
      bookmaker: bookmaker.name,
      updatedAt: bookmaker.update || result[0]?.update || null,
    };
    return data;
  }
  return null;
}

function fixture(id, league, home, away, time, status, homeScore, awayScore, odds, chances, confidence) {
  return {
    id, league, country: "Sample data", kickoff: null, time, status, statusLong: "Sample fixture",
    minute: null, home, away, homeCode: initials(home), awayCode: initials(away), homeScore, awayScore,
    demo: true,
    odds: { home: odds[0], draw: odds[1], away: odds[2], market: "1X2 sample market", bookmaker: "Sample prices", markets: [{ id: "sample-1x2", name: "Match result · sample", values: [{ value: "Home", odds: odds[0] }, { value: "Draw", odds: odds[1] }, { value: "Away", odds: odds[2] }] }] },
    prediction: { home: chances[0], draw: chances[1], away: chances[2], advice: "Illustrative forecast only", source: "Sample model", confidence },
  };
}

function requiredId(value) {
  if (!value || !/^[a-zA-Z0-9_-]{1,24}$/.test(value)) throw new Error("A valid fixture ID is required");
  return value;
}
function parsePercent(value) {
  const parsed = Number.parseFloat(String(value).replace("%", ""));
  return Number.isFinite(parsed) ? parsed : null;
}
function initials(name = "") { return name.split(/\s+/).map((part) => part.slice(0, 1)).join("").slice(0, 3).toUpperCase(); }
function localDate(offsetDays) {
  const date = new Date(Date.now() + offsetDays * 86400000);
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Africa/Nairobi", year: "numeric", month: "2-digit", day: "2-digit" }).format(date);
}
async function readJson(request) {
  let body = "";
  for await (const chunk of request) {
    body += chunk;
    if (body.length > 20000) throw new Error("Request body too large");
  }
  return JSON.parse(body || "{}");
}
async function loadDotEnv() {
  try {
    const content = await readFile(join(root, ".env"), "utf8");
    for (const line of content.split(/\r?\n/)) {
      const match = line.match(/^\s*([A-Za-z_][\w]*)\s*=\s*(.*)\s*$/);
      if (match && process.env[match[1]] === undefined) process.env[match[1]] = match[2].replace(/^(['"])(.*)\1$/, "$2");
    }
  } catch (error) {
    if (error?.code !== "ENOENT") throw error;
  }
}
function setHeaders(response) {
  response.setHeader("x-content-type-options", "nosniff");
  response.setHeader("referrer-policy", "no-referrer");
  response.setHeader("cache-control", "no-store");
}
function send(response, status, payload, contentType = "application/json; charset=utf-8") {
  response.writeHead(status, { "content-type": contentType });
  response.end(payload === null ? undefined : contentType.startsWith("application/json") ? JSON.stringify(payload) : payload);
}
function mimeType(extension) {
  return ({ ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".json": "application/json; charset=utf-8", ".svg": "image/svg+xml" })[extension] || "application/octet-stream";
}
