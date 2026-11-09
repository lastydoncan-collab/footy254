import { useCallback, useEffect, useState } from "react";
import { RefreshCw, Trophy } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { getActiveJackpots, enterJackpot } from "../services/betting";

function JackpotCard({ jackpot, onEnter, entering }) {
  const { authenticated } = useAuth();
  const fixtures = jackpot.fixtures || jackpot.jackpot_fixtures || [];
  const [picks, setPicks] = useState({});
  const [stake, setStake] = useState(String(jackpot.min_stake ?? jackpot.stake ?? 50));
  const [message, setMessage] = useState("");

  const closesAt = jackpot.closes_at ? new Date(jackpot.closes_at) : null;
  const allPicked = fixtures.length > 0 && fixtures.every((f) => picks[f.match_id]);

  function setPick(matchId, selection) {
    setPicks((prev) => ({ ...prev, [matchId]: selection }));
  }

  async function handleEnter() {
    setMessage("");
    try {
      await onEnter(jackpot.id, {
        picks: fixtures.map((f) => ({
          match_id: f.match_id,
          selection: picks[f.match_id],
        })),
        stake,
      });
      setMessage("Entry placed.");
      setPicks({});
    } catch (err) {
      setMessage(err?.message || "Could not enter jackpot.");
    }
  }

  return (
    <article className="rounded-2xl border border-white/10 bg-pitch p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="flex items-center gap-2 text-lg font-black text-chalk">
            <Trophy size={18} className="text-gold" />
            {jackpot.name || `Jackpot #${jackpot.id}`}
          </h3>
          {closesAt && (
            <p className="mt-1 text-xs text-chalk/60">
              Closes {closesAt.toLocaleDateString([], { day: "numeric", month: "short" })}{" "}
              {closesAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </p>
          )}
        </div>
        {jackpot.pool_amount != null && (
          <span className="shrink-0 rounded-full bg-gold/20 px-3 py-1 text-sm font-black text-gold">
            KES {Number(jackpot.pool_amount).toLocaleString()}
          </span>
        )}
      </div>

      <div className="mt-4 space-y-2">
        {fixtures.map((f) => (
          <div key={f.match_id} className="rounded-xl border border-white/10 bg-ink/60 p-3">
            <p className="truncate text-sm font-semibold text-chalk">
              {f.home_team} vs {f.away_team}
            </p>
            <div className="mt-2 flex gap-2">
              {["HOME", "DRAW", "AWAY"].map((sel) => (
                <button
                  key={sel}
                  type="button"
                  onClick={() => setPick(f.match_id, sel)}
                  className={`flex-1 rounded-lg px-2 py-1.5 text-xs font-bold transition ${
                    picks[f.match_id] === sel
                      ? "bg-signal text-ink"
                      : "bg-turf text-chalk/70 hover:bg-line"
                  }`}
                >
                  {sel === "HOME" ? "1" : sel === "DRAW" ? "X" : "2"}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      {fixtures.length > 0 && (
        <>
          <label className="mt-4 block text-xs font-semibold uppercase tracking-wide text-chalk/60">
            Stake (KES)
          </label>
          <input
            type="number"
            min="1"
            value={stake}
            onChange={(e) => setStake(e.target.value)}
            className="mt-1 w-full rounded-xl border border-white/10 bg-ink px-3 py-2 text-chalk outline-none focus:border-signal"
          />

          {message && <p className="mt-2 text-xs text-chalk/70">{message}</p>}

          <button
            type="button"
            disabled={!authenticated || !allPicked || entering}
            onClick={handleEnter}
            className="mt-3 w-full rounded-xl bg-signal px-4 py-2.5 text-sm font-bold text-ink hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {!authenticated
              ? "Sign in to enter"
              : entering
                ? "Entering..."
                : "Enter jackpot"}
          </button>
        </>
      )}
    </article>
  );
}

export default function Jackpots() {
  const [jackpots, setJackpots] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [entering, setEntering] = useState(false);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError("");
      setJackpots(await getActiveJackpots());
    } catch (err) {
      console.error(err);
      setError("We couldn't load jackpots right now.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleEnter(jackpotId, payload) {
    setEntering(true);
    try {
      await enterJackpot(jackpotId, payload);
    } finally {
      setEntering(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-3xl font-black">Jackpots</h1>
          <p className="mt-1 text-slate-400">
            Pick every fixture correctly to win the pool, tiered payouts for partial correct picks.
          </p>
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
          Loading jackpots...
        </div>
      )}

      {error && (
        <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-5 text-red-300">
          {error}
        </div>
      )}

      {!loading && !error && jackpots.length === 0 && (
        <div className="rounded-2xl border border-white/10 bg-pitch p-8 text-center">
          <h2 className="text-xl font-black">No open jackpots</h2>
          <p className="mt-2 text-slate-400">Check back once a new jackpot round opens.</p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {jackpots.map((j) => (
          <JackpotCard key={j.id} jackpot={j} onEnter={handleEnter} entering={entering} />
        ))}
      </div>
    </div>
  );
}
