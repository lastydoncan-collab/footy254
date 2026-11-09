# PitchIQ Football Predictions

PitchIQ is an independent football data, forecast, and betting-slip application. With an API-Football key, it fetches fixtures, available football odds markets, and the provider's fixture predictions. The match board supports live/today/upcoming views, team/league search, favorites, sorting, and match-level market browsing. Forecasts are explicitly attributed to the data provider; PitchIQ does not claim those predictions as its own AI model. See [BETIKA-COMPARISON.md](BETIKA-COMPARISON.md) for the public-feature comparison and remaining integration gaps.

## Run locally

Requires Node.js 22.5 or later (for the built-in `node:sqlite` module — you'll
see an "experimental feature" warning on startup; that's expected). No
package installation is needed: there is still no `node_modules` here.

1. Copy `.env.example` to `.env`.
2. Add your API-Football key as `APISPORTS_KEY` in `.env` (or use `API_FOOTBALL_KEY`). Keep `.env` private and do not commit it.
3. Run `node server.mjs` from this directory.
4. Open `http://127.0.0.1:4173`.

The local server keeps the provider key out of browser code, requests the API over HTTPS, and caches responses to reduce calls. Fixtures in the live view refresh every 15 seconds; today's and upcoming fixtures refresh every minute. Odds and predictions load per match. Provider coverage, availability, and plan limits apply. Without a key, the app clearly labels its sample fixtures and estimates.

## Betting slip

Singles, multiples and jackpot-style slips, with KES stake calculations, run in **paper mode only** — no sportsbook account, no deposits, no cash wagers, no real winnings. A football-data API key does not authorize or provide real-money wagering.

What changed from a pure front-end demo: every paper wallet, stake and settlement now lives in a real SQLite database (`db.mjs`/`betting.mjs`), not browser `localStorage`. A session cookie (no login) identifies your paper wallet, so balance and bet history survive a page reload *and* a server restart — this is a genuine, if small, backend, not a simulation running entirely in the browser.

- **Wallet**: starts with KES 10,000 in paper money; `+ Top up` adds another 5,000 (dev/demo convenience only — there is deliberately no public deposit endpoint).
- **Placing a bet**: `POST /api/bets/place` debits the wallet and writes the slip + legs in one database transaction; an over-stake request is rejected and nothing is debited.
- **Settlement**: `POST /api/bets/settle {fixtureId}` resolves every pending leg on that fixture.
  - Sample (`demo-*`) fixtures: the outcome is a weighted-random draw from that fixture's own forecast percentages, decided **server-side** — the "Simulate result" button can't be used to force a win.
  - Live fixtures (a real API-Football ID): the server fetches the fixture's actual final score and only settles once it reports full-time (`FT`).
  - Only the match-result (1X2) market can be verified from a final score. A bet placed on any other market (goals, BTTS, handicap, …) settles **VOID** and its stake is refunded — it is never silently guessed at.
  - A multi/jackpot leg that voids is dropped from the accumulator (the payout is recalculated from the remaining legs' odds); every other leg still has to win.
- **History**: `GET /api/bets` returns every slip for your wallet with live per-leg status (`PENDING`/`WON`/`LOST`/`VOID`), served from the database, not reconstructed from local receipts.

This is still a long way from a licensed sportsbook (see `BETIKA-COMPARISON.md`), but the paper-money ledger itself is now real, auditable application state, which is the piece worth carrying over if this gets merged into a larger backend later.

## Configuration

- `APISPORTS_KEY` or `API_FOOTBALL_KEY`: API-Football data key
- `PORT`: local server port (default `4173`)

The API adapter is isolated in `server.mjs`; additional football providers can be integrated once their names and API details are known. Never put secrets in `app.js`, `index.html`, screenshots, or source control.
