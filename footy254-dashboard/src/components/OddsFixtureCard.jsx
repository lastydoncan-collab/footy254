import { useState } from "react";
import { useBetSlip } from "../context/BetSlipContext";
import { MARKETS } from "../services/betting";

function OddsButton({ label, odds, selected, disabled, onClick, compact }) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`
        flex flex-col items-center rounded-xl border transition
        ${compact ? "px-1.5 py-1.5" : "flex-1 px-2 py-2"}
        ${
          disabled
            ? "cursor-not-allowed border-white/5 bg-ink/30 text-chalk/30"
            : selected
              ? "border-signal bg-signal text-ink"
              : "border-white/10 bg-ink/60 text-chalk hover:border-signal/50 hover:bg-ink"
        }
      `}
    >
      <span
        className={`${compact ? "text-[9px]" : "text-[10px]"} font-semibold uppercase tracking-wide ${
          selected ? "text-ink/70" : "text-chalk/60"
        }`}
      >
        {label}
      </span>
      <span className={`${compact ? "text-xs" : "text-sm"} font-black tabular-nums`}>
        {odds != null ? Number(odds).toFixed(2) : "—"}
      </span>
    </button>
  );
}

// One row of the odds board: fixture info + a market tab strip (1X2 / BTTS
// / O-U 2.5) with that market's clickable odds buttons underneath. Tapping
// a button adds/replaces that fixture's leg in the bet slip - it does NOT
// navigate anywhere, so the user is free to tap picks across several
// fixtures before opening the slip.
export default function OddsFixtureCard({ match }) {
  const { addLeg, isSelected } = useBetSlip();
  const [activeMarket, setActiveMarket] = useState("1X2");

  const kickoff = match.kickoff ? new Date(match.kickoff) : null;
  const live = match.fixture_status === "LIVE" || match.fixture_status === "IN_PLAY";

  const market = MARKETS.find((m) => m.key === activeMarket) ?? MARKETS[0];

  function pick(selection, odds) {
    if (odds == null) return;
    addLeg({
      matchId: match.match_id,
      market: market.key,
      selection,
      homeTeam: match.home_team,
      awayTeam: match.away_team,
      competition: match.competition,
      odds: Number(odds),
    });
  }

  return (
    <article className="rounded-2xl border border-white/10 bg-pitch p-4">
      <div className="flex items-center justify-between gap-2 text-xs text-chalk/60">
        <span className="truncate">{match.competition}</span>
        <div className="flex shrink-0 items-center gap-2">
          {live ? (
            <span className="flex items-center gap-1 rounded-full bg-signal px-2 py-0.5 font-bold text-ink">
              <span className="h-1.5 w-1.5 rounded-full bg-ink" /> LIVE
            </span>
          ) : (
            kickoff && (
              <span>
                {kickoff.toLocaleDateString([], { day: "numeric", month: "short" })}{" "}
                {kickoff.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </span>
            )
          )}
        </div>
      </div>

      <div className="mt-2 space-y-1">
        <p className="truncate font-bold">{match.home_team}</p>
        <p className="truncate font-bold">{match.away_team}</p>
      </div>

      {/* Market tabs - 6 markets now, so this scrolls horizontally on
          narrow cards instead of wrapping awkwardly. */}
      <div className="mt-3 -mx-1 flex gap-1 overflow-x-auto border-b border-white/10 px-1 pb-2">
        {MARKETS.map((m) => (
          <button
            key={m.key}
            type="button"
            onClick={() => setActiveMarket(m.key)}
            className={`shrink-0 rounded-lg px-2.5 py-1 text-xs font-bold transition ${
              activeMarket === m.key
                ? "bg-signal text-ink"
                : "text-chalk/60 hover:bg-white/5 hover:text-chalk"
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>

      <div
        className={
          market.layout === "grid"
            ? "mt-3 grid grid-cols-4 gap-1.5 sm:grid-cols-5"
            : "mt-3 flex gap-2"
        }
      >
        {market.selections.map((s) => (
          <OddsButton
            key={s.selection}
            label={s.shortLabel}
            odds={match[s.oddsField]}
            disabled={match[s.oddsField] == null}
            selected={isSelected(match.match_id, market.key, s.selection)}
            onClick={() => pick(s.selection, match[s.oddsField])}
            compact={market.layout === "grid"}
          />
        ))}
      </div>
      {market.key !== "1X2" && market.selections.every((s) => match[s.oddsField] == null) && (
        <p className="mt-2 text-center text-[11px] text-chalk/40">
          Not available for this fixture yet.
        </p>
      )}
    </article>
  );
}
