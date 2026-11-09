import { useBetSlip } from "../context/BetSlipContext";

function OddsButton({ label, odds, selected, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`
        flex flex-1 flex-col items-center rounded-xl border px-2 py-2 transition
        ${
          selected
            ? "border-signal bg-signal text-ink"
            : "border-white/10 bg-ink/60 text-chalk hover:border-signal/50 hover:bg-ink"
        }
      `}
    >
      <span className={`text-[10px] font-semibold uppercase tracking-wide ${selected ? "text-ink/70" : "text-chalk/60"}`}>
        {label}
      </span>
      <span className="text-sm font-black tabular-nums">{Number(odds).toFixed(2)}</span>
    </button>
  );
}

// One row of the odds board: fixture info + three clickable 1X2 odds
// buttons that add/remove a leg from the bet slip.
export default function OddsFixtureCard({ match }) {
  const { addLeg, isSelected } = useBetSlip();

  const kickoff = match.kickoff ? new Date(match.kickoff) : null;
  const live = match.fixture_status === "LIVE" || match.fixture_status === "IN_PLAY";

  function pick(selection, odds) {
    addLeg({
      matchId: match.match_id,
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

      <div className="mt-3 flex gap-2">
        <OddsButton
          label="1"
          odds={match.home_odds}
          selected={isSelected(match.match_id, "HOME")}
          onClick={() => pick("HOME", match.home_odds)}
        />
        <OddsButton
          label="X"
          odds={match.draw_odds}
          selected={isSelected(match.match_id, "DRAW")}
          onClick={() => pick("DRAW", match.draw_odds)}
        />
        <OddsButton
          label="2"
          odds={match.away_odds}
          selected={isSelected(match.match_id, "AWAY")}
          onClick={() => pick("AWAY", match.away_odds)}
        />
      </div>
    </article>
  );
}
