import { useState } from "react";
import { Link } from "react-router-dom";
import { Ticket, X, Trash2 } from "lucide-react";
import { useBetSlip } from "../context/BetSlipContext";
import { useAuth } from "../context/AuthContext";
import { selectionLabel, MARKETS } from "../services/betting";

function marketLabel(marketKey) {
  return MARKETS.find((m) => m.key === marketKey)?.label || marketKey;
}

// Floating bet-slip button + slide-up drawer, present on every page inside
// the dashboard layout (mounted once in DashboardLayout) so a selection
// made on the odds board survives navigating elsewhere.
export default function BetSlipDrawer() {
  const {
    legs,
    removeLeg,
    clearSlip,
    stake,
    setStake,
    combinedOdds,
    potentialPayout,
    open,
    setOpen,
    placing,
    placeBet,
    lastSlip,
    setLastSlip,
    error,
  } = useBetSlip();

  const { authenticated } = useAuth();
  const [justPlaced, setJustPlaced] = useState(false);

  if (legs.length === 0 && !lastSlip) return null;

  async function handlePlace() {
    try {
      await placeBet();
      setJustPlaced(true);
    } catch {
      // error already surfaced via context's `error`
    }
  }

  return (
    <>
      {/* Floating toggle */}
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="fixed bottom-24 right-4 z-50 flex items-center gap-2 rounded-full bg-signal px-4 py-3 font-bold text-ink shadow-2xl lg:bottom-6 lg:right-6"
      >
        <Ticket size={18} />
        {legs.length > 0 ? `Slip (${legs.length})` : "Slip"}
      </button>

      {open && (
        <div className="fixed inset-0 z-[70] flex items-end justify-center lg:items-center">
          <button
            type="button"
            aria-label="Close bet slip"
            onClick={() => setOpen(false)}
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
          />

          <div className="relative z-10 max-h-[85vh] w-full max-w-md overflow-y-auto rounded-t-[26px] border border-white/10 bg-pitch p-5 shadow-2xl lg:rounded-[26px]">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-black text-chalk">Bet Slip</h2>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="rounded-full p-1.5 text-chalk/60 hover:bg-white/10 hover:text-chalk"
              >
                <X size={18} />
              </button>
            </div>

            {!authenticated && (
              <p className="mb-4 rounded-xl border border-white/10 bg-ink/60 p-3 text-sm text-chalk/80">
                <Link to="/login" className="font-bold text-signal hover:underline">
                  Sign in
                </Link>{" "}
                to place a bet. Your selections are kept.
              </p>
            )}

            {lastSlip && legs.length === 0 && justPlaced ? (
              <div className="space-y-3 text-center">
                <p className="text-2xl">✅</p>
                <p className="font-bold text-chalk">Bet placed.</p>
                <p className="text-sm text-chalk/70">
                  Stake {lastSlip.stake ?? lastSlip.total_stake ?? "-"} ·{" "}
                  Potential payout {lastSlip.potential_payout ?? lastSlip.payout ?? "-"}
                </p>
                <div className="flex gap-2">
                  <Link
                    to="/betting/history"
                    onClick={() => setOpen(false)}
                    className="flex-1 rounded-xl bg-turf px-4 py-2 text-sm font-semibold hover:bg-line"
                  >
                    View history
                  </Link>
                  <button
                    type="button"
                    onClick={() => {
                      setLastSlip(null);
                      setJustPlaced(false);
                      setOpen(false);
                    }}
                    className="flex-1 rounded-xl bg-signal px-4 py-2 text-sm font-bold text-ink hover:opacity-90"
                  >
                    Done
                  </button>
                </div>
              </div>
            ) : (
              <>
                {legs.length === 0 ? (
                  <p className="py-6 text-center text-sm text-chalk/60">
                    No selections yet. Tap any odds on the betting board to add them here.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {legs.map((leg) => (
                      <div
                        key={leg.matchId}
                        className="flex items-center justify-between gap-2 rounded-xl border border-white/10 bg-ink/60 p-3"
                      >
                        <div className="min-w-0">
                          <p className="truncate text-xs text-chalk/60">{leg.competition}</p>
                          <p className="truncate text-sm font-semibold text-chalk">
                            {leg.homeTeam} vs {leg.awayTeam}
                          </p>
                          <p className="text-xs text-chalk/70">
                            {leg.market && leg.market !== "1X2" && (
                              <span className="mr-1 rounded bg-white/10 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-chalk/60">
                                {marketLabel(leg.market)}
                              </span>
                            )}
                            {selectionLabel(leg.market || "1X2", leg.selection, {
                              home_team: leg.homeTeam,
                              away_team: leg.awayTeam,
                            })}{" "}
                            @ {Number(leg.odds).toFixed(2)}
                          </p>
                        </div>
                        <button
                          type="button"
                          aria-label="Remove selection"
                          onClick={() => removeLeg(leg.matchId)}
                          className="shrink-0 rounded-full p-1.5 text-chalk/50 hover:bg-red-500/20 hover:text-red-300"
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                {legs.length > 0 && (
                  <>
                    <div className="mt-4 flex items-center justify-between text-sm text-chalk/70">
                      <span>{legs.length > 1 ? "Multi-bet" : "Single bet"}</span>
                      {legs.length > 1 && (
                        <span>Combined odds {combinedOdds.toFixed(2)}</span>
                      )}
                    </div>

                    <label className="mt-3 block text-xs font-semibold uppercase tracking-wide text-chalk/60">
                      Stake (KES)
                    </label>
                    <input
                      type="number"
                      min="1"
                      value={stake}
                      onChange={(e) => setStake(e.target.value)}
                      className="mt-1 w-full rounded-xl border border-white/10 bg-ink px-3 py-2 text-chalk outline-none focus:border-signal"
                    />

                    <div className="mt-2 flex items-center justify-between text-sm">
                      <span className="text-chalk/60">Potential payout</span>
                      <span className="font-black text-signal">
                        {potentialPayout.toFixed(2)}
                      </span>
                    </div>

                    {error && (
                      <p className="mt-2 rounded-lg border border-red-500/30 bg-red-500/10 p-2 text-xs text-red-300">
                        {error}
                      </p>
                    )}

                    <div className="mt-4 flex gap-2">
                      <button
                        type="button"
                        onClick={clearSlip}
                        className="rounded-xl bg-turf px-4 py-2.5 text-sm font-semibold hover:bg-line"
                      >
                        Clear
                      </button>
                      <button
                        type="button"
                        disabled={!authenticated || placing}
                        onClick={handlePlace}
                        className="flex-1 rounded-xl bg-signal px-4 py-2.5 text-sm font-bold text-ink hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {placing ? "Placing..." : "Place bet"}
                      </button>
                    </div>
                  </>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}
