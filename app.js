const state = {
  fixtures: [],
  mode: "sample",
  view: "today",
  league: "all",
  sort: "time",
  query: "",
  favoritesOnly: false,
  favorites: new Set(Array.isArray(readStored("pitchiq-favorites", [])) ? readStored("pitchiq-favorites", []).map(String) : []),
  marketCache: new Map(),
  forecastCache: new Map(),
  slip: readStored("pitchiq-slip", []),
  kind: "single",
  wallet: null,
};

const grid = document.querySelector("#matchGrid");
const emptyState = document.querySelector("#emptyState");
const toast = document.querySelector("#toast");
const dialog = document.querySelector("#detailsDialog");
const API = "/api";
const currency = new Intl.NumberFormat("en-KE", { maximumFractionDigits: 2 });

function readStored(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key)) ?? fallback; }
  catch { return fallback; }
}
function escapeHtml(value = "") {
  return String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
}
function money(value) { return `KES ${currency.format(Number(value) || 0)}`; }
function isLive(fixture) { return ["1H", "HT", "2H", "ET", "P", "BT", "LIVE"].includes(fixture.status); }
function formattedTime(fixture) {
  if (isLive(fixture)) return fixture.minute == null ? fixture.statusLong || "LIVE" : `${fixture.minute}′`;
  if (!fixture.kickoff) return fixture.time || "Kick-off TBD";
  return new Intl.DateTimeFormat("en-KE", { timeZone: "Africa/Nairobi", hour: "2-digit", minute: "2-digit", hour12: false }).format(new Date(fixture.kickoff)) + " EAT";
}
function updatedLabel(value) {
  const date = value ? new Date(value) : new Date();
  return `● UPDATED ${new Intl.DateTimeFormat("en-KE", { timeZone: "Africa/Nairobi", hour: "2-digit", minute: "2-digit", hour12: false }).format(date)} EAT`;
}
function notify(message) {
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(notify.timer);
  notify.timer = setTimeout(() => toast.classList.remove("show"), 2400);
}

async function request(path, options) {
  const response = await fetch(`${API}${path}`, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || `Request failed (${response.status})`);
  return body;
}

async function initialize() {
  document.querySelector("#dateChip").innerHTML = `<span>▦</span> ${new Intl.DateTimeFormat("en-KE", { timeZone: "Africa/Nairobi", weekday: "short", day: "numeric", month: "short" }).format(new Date())} · EAT`;
  try {
    const status = await request("/status");
    state.mode = status.configured ? "live" : "sample";
    setDataStatus(state.mode, status.configured ? "API-Football connected" : "Sample mode · add API key");
    await loadFixtures(state.view);
  } catch (error) {
    setDataStatus("error", "Data server unavailable");
    showError(`${error.message}. Start the app with node server.mjs.`);
  }
  await refreshWallet();
  renderSlip();
  scheduleRefresh();
}

async function refreshWallet() {
  try {
    state.wallet = await request("/wallet");
  } catch {
    state.wallet = null;
  }
  renderWallet();
}

function renderWallet() {
  const node = document.querySelector("#walletBalance");
  if (!node) return;
  node.textContent = state.wallet ? money(state.wallet.balance) : "KES —";
}

function setDataStatus(mode, label) {
  const element = document.querySelector("#dataStatus");
  element.className = `data-status ${mode}`;
  element.querySelector("span").textContent = label;
}

async function loadFixtures(view = state.view) {
  state.view = view;
  setDataStatus(state.mode, state.mode === "live" ? "Updating fixtures…" : "Sample mode · paper bets");
  try {
    const result = await request(`/fixtures?view=${encodeURIComponent(view)}`);
    state.mode = result.mode;
    state.fixtures = result.data || [];
    document.querySelector("#lastUpdated").textContent = updatedLabel(result.updatedAt);
    document.querySelector("#liveCount").textContent = view === "live" ? String(state.fixtures.length) : "—";
    document.querySelector("#fixtureSubline").textContent = result.mode === "sample"
      ? "Sample fixtures and prices · add an API key for live data"
      : `${state.fixtures.length} fixtures · ${view === "live" ? "live scores refresh every 15 seconds" : "prices and forecasts load on demand"}`;
    setDataStatus(result.mode, result.mode === "live" ? "Live data" : "Sample data · paper mode");
    document.querySelectorAll(".date-tab").forEach((button) => button.classList.toggle("active", button.dataset.view === view));
    renderFixtures();
  } catch (error) {
    setDataStatus("error", "Feed error");
    showError(error.message);
  }
}

function filteredFixtures() {
  const query = state.query.trim().toLocaleLowerCase();
  let items = state.fixtures.filter((item) => {
    const matchesLeague = state.league === "all" || item.league === state.league;
    const matchesQuery = !query || `${item.home} ${item.away} ${item.league} ${item.country}`.toLocaleLowerCase().includes(query);
    const matchesFavorite = !state.favoritesOnly || state.favorites.has(item.id);
    return matchesLeague && matchesQuery && matchesFavorite;
  });
  if (state.view === "live") items = items.filter(isLive);
  if (state.sort === "confidence") items.sort((a, b) => confidence(b) - confidence(a));
  else items.sort((a, b) => new Date(a.kickoff || 0) - new Date(b.kickoff || 0));
  return items;
}
function confidence(fixture) {
  const forecast = state.forecastCache.get(fixture.id) || fixture.prediction;
  const values = [forecast?.home, forecast?.draw, forecast?.away].map(Number).filter(Number.isFinite);
  return values.length ? Math.max(...values) : 0;
}

function renderFixtures() {
  const items = filteredFixtures();
  emptyState.hidden = items.length > 0;
  grid.innerHTML = items.map(renderFixture).join("");
  document.querySelector("#favoriteCount").textContent = String(state.favorites.size);
  document.querySelector("#favoriteFilter").setAttribute("aria-pressed", String(state.favoritesOnly));
  document.querySelector("#emptyState span").textContent = state.favoritesOnly && state.favorites.size === 0
    ? "Star a fixture to build your favorites list."
    : state.mode === "sample" && state.view === "live"
    ? "There are no live sample fixtures. Add your API key to see live matches."
    : "Try another day or switch between live, today and upcoming.";
  document.querySelector(".nav-count").textContent = String(items.length);
}

function renderFixture(fixture) {
  const odds = state.marketCache.get(fixture.id) || fixture.odds || null;
  const forecast = state.forecastCache.get(fixture.id) || fixture.prediction || null;
  const status = isLive(fixture) ? `${fixture.minute ?? "LIVE"}${fixture.minute == null ? "" : "′"} · ${fixture.statusLong || "In play"}` : fixture.statusLong === "Not started" || fixture.status === "NS" ? formattedTime(fixture) : fixture.statusLong || fixture.status || formattedTime(fixture);
  const score = fixture.homeScore == null ? "VS" : `${fixture.homeScore} – ${fixture.awayScore ?? 0}`;
  const market = odds?.home || odds?.draw || odds?.away
    ? `<div class="market-head"><span class="market-title">${escapeHtml(odds.market || "1X2 · MATCH RESULT")}</span><span class="market-updated">${odds.updatedAt ? `As of ${escapeHtml(new Date(odds.updatedAt).toLocaleTimeString("en-KE", { timeZone: "Africa/Nairobi", hour: "2-digit", minute: "2-digit" }))}` : escapeHtml(odds.bookmaker || "")}</span></div><div class="market-row">${oddButton(fixture, "home", fixture.home, odds.home)}${oddButton(fixture, "draw", "Draw", odds.draw)}${oddButton(fixture, "away", fixture.away, odds.away)}</div>`
    : odds?.markets?.length
      ? `<div class="market-head"><span class="market-title">${odds.markets.length} AVAILABLE MARKETS</span><span class="market-updated">${escapeHtml(odds.bookmaker || "Provider prices")}</span></div><button class="load-market" data-action="analysis" data-fixture="${escapeHtml(fixture.id)}">Browse markets &amp; forecast →</button>`
      : `<button class="load-market" data-action="market" data-fixture="${escapeHtml(fixture.id)}">Load odds &amp; forecast</button>`;
  const probabilities = forecast ? `<div class="forecast-strip"><span>1X2</span><div class="forecast-bar"><i style="width:${pct(forecast.home)}%"></i><i style="width:${pct(forecast.draw)}%"></i><i style="width:${pct(forecast.away)}%"></i></div><span class="forecast-pct">${pct(forecast.home)}/${pct(forecast.draw)}/${pct(forecast.away)}</span></div>` : "";
  const favorite = state.favorites.has(fixture.id);
  return `<article class="match-card"><div class="match-meta"><span class="league-name">✦ ${escapeHtml(fixture.league)}${fixture.country ? ` · ${escapeHtml(fixture.country)}` : ""}</span><div class="match-tools"><span class="match-status ${isLive(fixture) ? "live" : ""}">${escapeHtml(status)}</span><button class="favorite-toggle ${favorite ? "selected" : ""}" data-action="favorite" data-fixture="${escapeHtml(fixture.id)}" aria-label="${favorite ? "Remove from" : "Add to"} favorites" aria-pressed="${favorite}">${favorite ? "★" : "☆"}</button></div></div><div class="teams"><div class="team">${teamBadge(fixture, "home")}<div class="team-name">${escapeHtml(fixture.home)}</div></div><div class="vs">${escapeHtml(score)}<div class="kickoff">${isLive(fixture) ? "LIVE" : formattedTime(fixture)}</div></div><div class="team">${teamBadge(fixture, "away")}<div class="team-name">${escapeHtml(fixture.away)}</div></div></div><div class="market-area">${market}</div>${probabilities}<div class="card-actions"><button class="analysis-button" data-action="analysis" data-fixture="${escapeHtml(fixture.id)}">${forecast ? "View forecasts & markets →" : "Get forecast & markets →"}</button>${fixture.demo ? "<span class=\"sample-label\">SAMPLE</span>" : ""}</div></article>`;
}
function teamBadge(fixture, side) {
  const logo = fixture[`${side}Logo`];
  if (logo && /^https:\/\//.test(logo)) return `<img class="team-logo" src="${escapeHtml(logo)}" alt="" loading="lazy" />`;
  return `<span class="team-badge" style="background:${side === "home" ? "#dceee1" : "#e4eaf3"};color:#34473f">${escapeHtml(fixture[`${side}Code`] || "FC")}</span>`;
}
function oddButton(fixture, outcome, label, odd, marketName = "Match result") {
  const value = Number(odd);
  if (!Number.isFinite(value) || value <= 1) return `<button class="odd-button unavailable" disabled><span>${escapeHtml(label)}</span><b>—</b></button>`;
  const key = `${fixture.id}:${outcome}`;
  const selected = state.slip.some((pick) => pick.key === key);
  return `<button class="odd-button ${selected ? "selected" : ""}" data-action="pick" data-fixture="${escapeHtml(fixture.id)}" data-outcome="${escapeHtml(outcome)}" data-market="${escapeHtml(marketName)}" data-label="${escapeHtml(label)}" data-odds="${value}"><span>${escapeHtml(label)}</span><b>${value.toFixed(2)}</b></button>`;
}
function pct(value) { const number = Number(value); return Number.isFinite(number) ? Math.max(0, Math.min(100, Math.round(number))) : 0; }
function showError(message) {
  grid.innerHTML = `<div class="error-banner">${escapeHtml(message)}. The app will retry automatically.</div>`;
  emptyState.hidden = true;
}

async function loadMarkets(fixtureId, force = false) {
  const fixture = state.fixtures.find((item) => item.id === fixtureId);
  const previous = state.marketCache.get(fixtureId);
  const forecastPrevious = state.forecastCache.get(fixtureId);
  const age = Date.now() - Math.max(previous?.fetchedAt || 0, forecastPrevious?.fetchedAt || 0);
  const freshFor = isLive(fixture || {}) ? 15000 : 10800000;
  if (!force && previous && forecastPrevious && age < freshFor) return;
  if (fixture?.demo) {
    state.marketCache.set(fixtureId, { ...fixture.odds, fetchedAt: Date.now() });
    state.forecastCache.set(fixtureId, { ...fixture.prediction, fetchedAt: Date.now() });
    return;
  }
  const [oddsResult, forecastResult] = await Promise.allSettled([
    request(`/odds?fixture=${encodeURIComponent(fixtureId)}${isLive(fixture || {}) ? "&live=1" : ""}`),
    request(`/predictions?fixture=${encodeURIComponent(fixtureId)}`),
  ]);
  if (oddsResult.status === "fulfilled" && oddsResult.value.data) state.marketCache.set(fixtureId, { ...oddsResult.value.data, fetchedAt: Date.now() });
  if (forecastResult.status === "fulfilled" && forecastResult.value.data) state.forecastCache.set(fixtureId, { ...forecastResult.value.data, fetchedAt: Date.now() });
  if (oddsResult.status === "rejected" && forecastResult.status === "rejected") throw new Error("Couldn’t load this match’s prices or forecast");
}

async function showAnalysis(fixtureId) {
  const fixture = state.fixtures.find((item) => item.id === fixtureId);
  if (!fixture) return;
  document.querySelector("#dialogTitle").textContent = `${fixture.home} vs ${fixture.away}`;
  const body = document.querySelector("#dialogBody");
  body.innerHTML = `<div class="dialog-content">Loading current prices and the provider forecast…</div>`;
  dialog.showModal();
  try {
    await loadMarkets(fixtureId);
    const forecast = state.forecastCache.get(fixtureId);
    const odds = state.marketCache.get(fixtureId);
    const forecastPanel = forecast
      ? `<div class="dialog-forecast"><strong>1X2 probability estimate</strong>${probRow(fixture.home, forecast.home)}${probRow("Draw", forecast.draw)}${probRow(fixture.away, forecast.away)}<div class="dialog-warning">Source: ${escapeHtml(forecast.source || (fixture.demo ? "sample data" : "API-Football"))}. Forecast coverage varies by competition; these estimates are not guarantees.</div></div>`
      : `<div class="dialog-warning">No provider forecast is available for this fixture.</div>`;
    const oddsPanel = renderMarketOptions(fixture, odds);
    const settlePanel = `<div class="dialog-settle"><button class="text-button" data-action="settle" data-fixture="${escapeHtml(fixture.id)}">${fixture.demo ? "Simulate full-time result (demo) →" : "Check if finished & settle bets →"}</button><p class="dialog-warning">${fixture.demo ? "Picks the outcome randomly, weighted by this fixture’s forecast — not chosen by you." : "Settles only once API-Football reports this fixture as finished (FT)."}</p></div>`;
    body.innerHTML = `<div class="dialog-content">${escapeHtml(forecast?.advice || "Provider forecast and available match markets.")}${forecastPanel}${oddsPanel}${settlePanel}</div>`;
    renderFixtures();
  } catch (error) {
    body.innerHTML = `<div class="dialog-content">${escapeHtml(error.message)}</div>`;
  }
}
function renderMarketOptions(fixture, odds) {
  const markets = odds?.markets || [];
  if (!markets.length) return `<div class="dialog-content">No odds markets are currently available for this fixture.</div>`;
  const sections = markets.map((market) => {
    const values = market.values.map((value, index) => oddButton(fixture, `market-${market.id}-${index}`, value.value, value.odds, market.name)).join("");
    return `<section class="dialog-market"><h3>${escapeHtml(market.name)}</h3><div class="dialog-market-values">${values}</div></section>`;
  }).join("");
  return `<section class="dialog-markets"><div class="dialog-market-head"><strong>Available markets</strong><span>${escapeHtml(odds.bookmaker || "Odds provider")}</span></div>${sections}<div class="dialog-warning">Market availability and update times vary by fixture and data plan. Paper slip only — settlement resolves the match-result (1X2) market; picks on other markets settle as void and refund their stake, since this app can't verify those outcomes from a final score alone.</div></section>`;
}
function probRow(label, value) {
  const number = pct(value);
  return `<div class="dialog-prob"><span>${escapeHtml(label)}</span><div class="dialog-prob-track"><i style="display:block;width:${number}%"></i></div><b>${number}%</b></div>`;
}
function formatOdd(value) { return Number(value) > 1 ? Number(value).toFixed(2) : "—"; }

function addPick(fixtureId, outcome, label, odds, marketName = "Match result") {
  const fixture = state.fixtures.find((item) => item.id === fixtureId);
  if (!fixture) return;
  const key = `${fixtureId}:${outcome}`;
  const existing = state.slip.findIndex((pick) => pick.fixtureId === fixtureId);
  if (existing >= 0) {
    if (state.slip[existing].key === key) state.slip.splice(existing, 1);
    else state.slip[existing] = pickFor(fixture, outcome, label, odds, marketName);
  } else state.slip.push(pickFor(fixture, outcome, label, odds, marketName));
  persistSlip();
  renderFixtures();
  renderSlip();
}
function pickFor(fixture, outcome, label, odds, market) {
  return { key: `${fixture.id}:${outcome}`, fixtureId: fixture.id, match: `${fixture.home} vs ${fixture.away}`, league: fixture.league, market, label, odds: Number(odds), demo: Boolean(fixture.demo) };
}
function persistSlip() { localStorage.setItem("pitchiq-slip", JSON.stringify(state.slip)); }

function renderSlip() {
  const items = document.querySelector("#slipItems");
  document.querySelector("#slipCount").textContent = String(state.slip.length);
  document.querySelectorAll(".saved-count").forEach((node) => node.textContent = state.slip.length);
  document.querySelectorAll(".mode-tab").forEach((button) => button.classList.toggle("active", button.dataset.kind === state.kind));
  if (!state.slip.length) {
    items.innerHTML = `<div class="slip-empty"><span>▤</span><strong>Your slip is empty</strong><p>Open a match market and tap an odd to add a selection.</p></div>`;
  } else {
    items.innerHTML = state.slip.map((pick) => `<div class="slip-item"><div class="slip-item-top"><strong>${escapeHtml(pick.match)}</strong><button class="remove-pick" data-remove="${escapeHtml(pick.key)}" aria-label="Remove selection">×</button></div><div class="slip-item-meta">${escapeHtml(pick.league)} · ${escapeHtml(pick.market || "Match result")} · <b>${escapeHtml(pick.label)}</b> @ ${Number(pick.odds).toFixed(2)}${pick.demo ? " · SAMPLE" : ""}</div></div>`).join("");
  }
  calculateSlip();
  document.querySelector("#placeBet").disabled = !state.slip.length || (state.kind === "multiple" && state.slip.length < 2) || (state.kind === "jackpot" && state.slip.length < 5);
  document.querySelector("#placeBet").textContent = state.kind === "jackpot" && state.slip.length < 5 ? `Add ${5 - state.slip.length} more for jackpot` : "Place paper bet →";
}

function calculateSlip() {
  const stake = Math.min(5000, Math.max(0, Number(document.querySelector("#stakeInput").value) || 0));
  const oddsProduct = state.slip.reduce((total, pick) => total * Number(pick.odds), 1);
  const totalStake = state.kind === "single" ? stake * state.slip.length : stake;
  const potential = state.kind === "single"
    ? state.slip.reduce((total, pick) => total + stake * Number(pick.odds), 0)
    : stake * oddsProduct;
  document.querySelector("#totalStake").textContent = money(totalStake);
  document.querySelector("#potentialReturn").textContent = money(potential);
  document.querySelector("#returnNote").textContent = state.kind === "jackpot" ? "paper odds estimate" : "if all picks win";
  if (document.querySelector("#stakeInput").value > 5000) document.querySelector("#stakeInput").value = "5000";
}

async function placePaperBet() {
  const button = document.querySelector("#placeBet");
  button.disabled = true;
  try {
    const receipt = await request("/bets/place", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ mode: "paper", kind: state.kind, stake: Number(document.querySelector("#stakeInput").value), selections: state.slip }),
    });
    notify(`${receipt.betId} recorded in your demo wallet`);
    state.slip = [];
    persistSlip();
    state.wallet = receipt.wallet || state.wallet;
    renderWallet();
    renderFixtures();
    renderSlip();
  } catch (error) {
    notify(error.message);
  } finally {
    button.disabled = !state.slip.length || (state.kind === "multiple" && state.slip.length < 2) || (state.kind === "jackpot" && state.slip.length < 5);
  }
}

async function simulateSettlement(fixtureId) {
  try {
    const result = await request("/bets/settle", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ fixtureId }),
    });
    await refreshWallet();
    const summary = result.legsSettled
      ? `${fixtureId}: ${result.winner.toUpperCase()} won · ${result.slipsWon} slip(s) paid, ${result.slipsLost} lost${result.slipsVoided ? `, ${result.slipsVoided} voided` : ""}`
      : "No pending bets were waiting on this fixture.";
    notify(summary);
    return result;
  } catch (error) {
    notify(error.message);
    return null;
  }
}

function scheduleRefresh() {
  clearTimeout(scheduleRefresh.timer);
  const interval = state.view === "live" ? 15000 : 60000;
  scheduleRefresh.timer = setTimeout(async () => {
    await loadFixtures(state.view);
    scheduleRefresh();
  }, interval);
}

grid.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const fixtureId = button.dataset.fixture;
  if (button.dataset.action === "favorite") {
    if (state.favorites.has(fixtureId)) state.favorites.delete(fixtureId);
    else state.favorites.add(fixtureId);
    localStorage.setItem("pitchiq-favorites", JSON.stringify([...state.favorites]));
    renderFixtures();
    return;
  }
  if (button.dataset.action === "pick") {
    addPick(fixtureId, button.dataset.outcome, button.dataset.label, Number(button.dataset.odds), button.dataset.market);
    return;
  }
  button.disabled = true;
  try {
    if (button.dataset.action === "market") await loadMarkets(fixtureId);
    if (button.dataset.action === "analysis") await showAnalysis(fixtureId);
    renderFixtures();
  } catch (error) { notify(error.message); }
  finally { button.disabled = false; }
});

document.querySelectorAll(".date-tab").forEach((button) => button.addEventListener("click", () => loadFixtures(button.dataset.view)));
document.querySelectorAll(".nav-item[data-view-link]").forEach((link) => link.addEventListener("click", () => loadFixtures(link.dataset.viewLink)));
document.querySelectorAll(".league-link").forEach((button) => button.addEventListener("click", () => {
  document.querySelectorAll(".league-link").forEach((item) => item.classList.remove("selected"));
  button.classList.add("selected");
  state.league = button.dataset.league;
  renderFixtures();
}));
document.querySelector("#sortButton").addEventListener("click", () => {
  state.sort = state.sort === "time" ? "confidence" : "time";
  document.querySelector("#sortButton span:first-of-type").textContent = state.sort === "time" ? "Kick-off time" : "Highest forecast";
  renderFixtures();
});
document.querySelector("#filterButton").addEventListener("click", () => {
  const leagues = ["all", ...new Set(state.fixtures.map((fixture) => fixture.league))];
  const nextIndex = (leagues.indexOf(state.league) + 1) % leagues.length;
  state.league = leagues[nextIndex];
  document.querySelector("#filterButton .filter-badge").textContent = state.league === "all" ? "All" : state.league;
  document.querySelectorAll(".league-link").forEach((button) => button.classList.toggle("selected", button.dataset.league === state.league));
  renderFixtures();
});
document.querySelector("#fixtureSearch").addEventListener("input", (event) => {
  state.query = event.currentTarget.value;
  renderFixtures();
});
document.querySelector("#favoriteFilter").addEventListener("click", () => {
  state.favoritesOnly = !state.favoritesOnly;
  renderFixtures();
});
document.querySelector("#dialogBody").addEventListener("click", async (event) => {
  const pickButton = event.target.closest('button[data-action="pick"]');
  if (pickButton) {
    addPick(pickButton.dataset.fixture, pickButton.dataset.outcome, pickButton.dataset.label, Number(pickButton.dataset.odds), pickButton.dataset.market);
    notify("Selection added to paper slip");
    return;
  }
  const settleButton = event.target.closest('button[data-action="settle"]');
  if (settleButton) {
    settleButton.disabled = true;
    await simulateSettlement(settleButton.dataset.fixture);
    settleButton.disabled = false;
  }
});
document.querySelector("#historyButton").addEventListener("click", async (event) => {
  event.preventDefault();
  document.querySelector("#dialogTitle").textContent = "Paper bet history";
  document.querySelector("#dialogBody").innerHTML = `<div class="dialog-content">Loading your bet history…</div>`;
  dialog.showModal();
  try {
    const { bets } = await request("/bets");
    document.querySelector("#dialogBody").innerHTML = bets.length
      ? `<div class="history-list">${bets.map(renderHistoryItem).join("")}</div>`
      : `<div class="dialog-content">No paper bets recorded on this wallet yet.</div>`;
  } catch (error) {
    document.querySelector("#dialogBody").innerHTML = `<div class="dialog-content">${escapeHtml(error.message)}</div>`;
  }
});
function renderHistoryItem(bet) {
  const statusClass = { WON: "won", LOST: "lost", VOID: "void", PENDING: "pending" }[bet.status] || "pending";
  const amount = bet.status === "WON" || bet.status === "VOID" ? `+${money(bet.payout)}` : bet.status === "LOST" ? `−${money(bet.stake)}` : money(bet.stake);
  return `<article class="history-item"><div><strong>PAPER-${bet.id} <span class="history-status ${statusClass}">${escapeHtml(bet.status)}</span></strong><span>${escapeHtml(new Date(bet.placed_at).toLocaleString("en-KE", { timeZone: "Africa/Nairobi" }))} EAT · ${escapeHtml(bet.bet_type)} · ${bet.legs.length} selection(s)</span></div><b>${amount}</b><ul>${bet.legs.map((leg) => `<li>${escapeHtml(leg.match_label)}: ${escapeHtml(leg.pick_label)} @ ${formatOdd(leg.odds)} <em>${escapeHtml(leg.status)}</em></li>`).join("")}</ul><small>Paper record only · no real money was wagered.</small></article>`;
}
document.querySelector("#topupButton").addEventListener("click", async () => {
  try {
    const result = await request("/wallet/topup", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ amount: 5000 }),
    });
    state.wallet = { ...state.wallet, balance: result.balance };
    renderWallet();
    notify("Demo wallet topped up by KES 5,000 (paper money only)");
  } catch (error) {
    notify(error.message);
  }
});
document.querySelector("#refreshButton").addEventListener("click", () => loadFixtures(state.view));
document.querySelector("#exploreButton").addEventListener("click", () => document.querySelector("#matchGrid").scrollIntoView({ behavior: "smooth", block: "start" }));
document.querySelector("#stakeInput").addEventListener("input", calculateSlip);
document.querySelector("#placeBet").addEventListener("click", placePaperBet);
document.querySelector("#clearSlip").addEventListener("click", () => { state.slip = []; persistSlip(); renderFixtures(); renderSlip(); });
document.querySelector("#slipItems").addEventListener("click", (event) => {
  const button = event.target.closest("[data-remove]");
  if (!button) return;
  state.slip = state.slip.filter((pick) => pick.key !== button.dataset.remove);
  persistSlip(); renderFixtures(); renderSlip();
});
document.querySelectorAll(".mode-tab").forEach((button) => button.addEventListener("click", () => { state.kind = button.dataset.kind; renderSlip(); }));
document.querySelector("#themeButton").addEventListener("click", () => {
  document.body.classList.remove("theme-coral", "theme-blue");
  const next = document.body.dataset.themeIndex || "0";
  if (next === "0") { document.body.classList.add("theme-coral"); document.body.dataset.themeIndex = "1"; }
  else if (next === "1") { document.body.classList.add("theme-blue"); document.body.dataset.themeIndex = "2"; }
  else document.body.dataset.themeIndex = "0";
});
document.querySelector("#closeDialog").addEventListener("click", () => dialog.close());
document.querySelector("#forecastNote").addEventListener("click", () => notify("Provider estimates summarize historical data and are not guarantees."));
document.querySelector("#responsibleButton").addEventListener("click", () => notify("Paper mode only. Real betting requires a licensed operator and responsible-gambling controls."));
document.querySelector("#betslip").addEventListener("click", (event) => {
  if (window.innerWidth <= 760 && !event.target.closest("button, input")) event.currentTarget.classList.toggle("expanded");
});

initialize();
