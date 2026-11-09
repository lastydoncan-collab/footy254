# PitchIQ / Betika public feature comparison

**Reviewed:** 17 October 2026. This is a public-feature comparison, not a review of authenticated or real-money flows. No Betika account was accessed and no wager was placed. Betika-specific claims below come from its public Kenya landing page and current app-store descriptions. REA runtime Evidence was unavailable: the local `rea doctor --client codex --json` command exited 1 because the source checkout has no compiled runtime.

| Area | Betika public feature set | PitchIQ after this update | Gap / integration required |
|---|---|---|---|
| Sports catalogue | Sports landing and multiple sports are advertised | Football fixtures only through API-Football | Other sport data providers and sport-specific markets |
| Football match discovery | Prematch, live, fixtures, match search and live score entry points | Today/live/next-seven-days, team/league search, league filter, kick-off/forecast sort, favorites | Live-score details/events and additional competition browsing depend on provider coverage |
| Football markets | App listing advertises 100+ markets, including goals, BTTS, double chance, corners and handicap | Displays 1X2 on cards; exposes all markets returned for a fixture in match details | API-Football/bookmaker coverage varies; not Betika's own price feed or market catalogue |
| Predictions | No comparable football AI prediction feature claimed in the public material reviewed | Keeps the provider 1X2 forecast and its source label | PitchIQ forecasts are provider data; coverage is fixture-dependent |
| Betslip | Single/multi, cash wager workflows advertised | Single/multiple and generic jackpot-style slip, KES estimate, server-side SQLite wallet, transactional stake/payout, and 1X2 settlement (other markets void + refund) | Paper-only; wallet balance has no cash value, no deposit/withdrawal rails, no cash-out, and settlement is demo-triggered (weighted-random for sample fixtures, or real final score for live ones) rather than automatic |
| Jackpots | Dedicated products with operator-defined fixtures, rules, entry and prize handling | User-built paper slip with a sample minimum | Real jackpot requires the operator's product/rules/feed and settlement integration |
| Account and payments | Login/register, deposit/withdrawal and local payment rails are advertised | Guest browser session | No auth, wallet, payment rails, KYC, or account ledger configured |
| Promotions | Bet boosts, bonuses and promotions are advertised | None | Needs current campaign feed and operator eligibility rules |
| Casino, virtuals and crash games | Casino, virtuals, Aviator/crash products appear in public product navigation/listings | Not included | Separate licensed game content, supplier SDK/API, wallet and game-session integrations |
| Responsible play and support | Public pages list age and responsible-gambling information; app listing advertises support | Paper-only disclaimer and information toast | Production needs functional age/eligibility, limits, exclusion, support and audit integrations |
| Preferences/performance | Public site exposes display/theme and data-saver preferences; app listing describes mobile use | Responsive web UI with local gradient theme | No measured latency comparison; no service-level or native-app parity evidence |

## Evidence and limits

- [Betika Kenya public landing page](https://www.betika.com/en-ke/) lists its public navigation, preferences, live/prematch/jackpot/casino/virtual/crash products, and responsible-play information.
- [Betika app listing](https://play.google.com/store/apps/details?id=com.app.betika.android&hl=en_GB&gl=KE) advertises live betting, jackpots, casino/virtual/crash games, cash-out, bet boosts, deposits/withdrawals, and a broad sports-market catalogue.
- [API-Football documentation guide](https://www.api-football.com/news/post/fifa-world-cup-2026-guide-to-using-data-with-api-sports) describes fixture, prediction and odds endpoints; the data returned is provider coverage, not Betika's sportsbook feed.
- The available project configuration contains no API key. Live responses, odds coverage, Betika's logged-in UX and actual performance have not been verified in this comparison.
- REA skill guidance was read and followed for authorization, provenance and unknowns, but this run did not produce REA Evidence because its compiled runtime is missing. The table is based on public web observations and PitchIQ source inspection.

## Update log

- 18 October 2026: added a real SQLite-backed wallet, bet-slip and
  settlement layer (`db.mjs` / `betting.mjs`) replacing the previous
  browser-`localStorage`-only paper receipts, so balance and bet history now
  persist server-side across reloads and restarts. Still paper money only —
  no deposit/withdrawal rails were added, and no Betika system was accessed
  or inspected to make this change.

## Scope boundary

PitchIQ remains an independent football product. A football-data key does not supply or authorize sportsbook account, wagering, payment, casino, game-provider, settlement, or regulator integrations. Real-money operations must be built against an explicitly selected licensed operator and its approved production controls; they must not be simulated as if cash bets were live.
