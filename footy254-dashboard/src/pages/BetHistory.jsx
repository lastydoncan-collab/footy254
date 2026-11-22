import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { getMySlips } from "../services/betting";
import BackButton from "../components/BackButton";

const STATUS_STYLES = {
  WON: "bg-leaf/20 text-leaf",
  LOST: "bg-red-500/20 text-red-300",
  PENDING: "bg-gold/20 text-gold",
  OPEN: "bg-gold/20 text-gold",
  VOID: "bg-chalk/20 text-chalk/70",
};

function StatusBadge({ status }) {
  const style = STATUS_STYLES[status?.toUpperCase()] || "bg-chalk/20 text-chalk/70";
  return (
    <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${style}`}>
      {status || "PENDING"}
    </span>
  );
}

function SlipCard({ slip }) {
  const legs = slip.legs || slip.bet_legs || [];
  const placedAt = slip.created_at ? new Date(slip.created_at) : null;

  return (
    <article className="rounded-2xl border border-white/10 bg-pitch p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs text-chalk/50">
            {legs.length > 1 ? `Multi-bet · ${legs.length} legs` : "Single bet"}
            {placedAt && ` · ${placedAt.toLocaleDateString([], { day: "numeric", month: "short" })}`}
          </p>
          <p className="mt-1 text-sm text-chalk/70">
            Stake KES {Number(slip.stake ?? slip.total_stake ?? 0).toFixed(2)} · Potential payout{" "}
            <span className="font-bold text-chalk">
              {Number(slip.potential_payout ?? slip.payout ?? 0).toFixed(2)}
            </span>
          </p>
        </div>
        <StatusBadge status={slip.status} />
      </div>

      {legs.length > 0 && (
        <div className="mt-3 space-y-1.5 border-t border-white/5 pt-3">
          {legs.map((leg, i) => (
            <div key={leg.id ?? i} className="flex items-center justify-between text-sm">
              <span className="truncate text-chalk/80">
                {leg.home_team && leg.away_team
                  ? `${leg.home_team} vs ${leg.away_team}`
                  : `Match ${leg.match_id}`}{" "}
                — {leg.selection}
              </span>
              <span className="shrink-0 font-semibold tabular-nums text-chalk/60">
                {Number(leg.odds ?? leg.price ?? 0).toFixed(2)}
              </span>
            </div>
          ))}
        </div>
      )}
    </article>
  );
}

export default function BetHistory() {
  const [slips, setSlips] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError("");
      setSlips(await getMySlips());
    } catch (err) {
      console.error(err);
      setError(
        err?.status === 401
          ? "Sign in to see your bet history."
          : "We couldn't load your bets right now."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-5">
      <BackButton />
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-3xl font-black">My Bets</h1>
          <p className="mt-1 text-slate-400">Every slip you've placed, settled and pending.</p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-2 rounded-xl bg-turf px-4 py-2 text-sm font-semibold hover:bg-line disabled:opacity-50"
        >
          <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {loading && (
        <div className="rounded-2xl border border-white/10 bg-pitch p-6 text-center text-slate-300">
          Loading bets...
        </div>
      )}

      {error && (
        <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-5 text-red-300">
          {error}
        </div>
      )}

      {!loading && !error && slips.length === 0 && (
        <div className="rounded-2xl border border-white/10 bg-pitch p-8 text-center">
          <h2 className="text-xl font-black">No bets yet</h2>
          <p className="mt-2 text-slate-400">Pick some odds on the Betting page to get started.</p>
        </div>
      )}

      <div className="space-y-3">
        {slips.map((slip) => (
          <SlipCard key={slip.id} slip={slip} />
        ))}
      </div>
    </div>
  );
}
