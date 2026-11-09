import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { RefreshCw, Wallet as WalletIcon, Trophy, History } from "lucide-react";

import OddsFixtureCard from "../components/OddsFixtureCard";
import { useAuth } from "../context/AuthContext";
import { getOddsBoard, getWallet } from "../services/betting";
import { connectOddsSocket } from "../services/oddsSocket";

// Quick links row to the other betting pages (wallet / jackpots / history).
function QuickLinks({ balance, authenticated }) {
  return (
    <div className="flex flex-wrap gap-2">
      <Link
        to="/betting/wallet"
        className="flex items-center gap-2 rounded-xl border border-white/10 bg-pitch px-3 py-2 text-sm font-semibold hover:border-signal/40"
      >
        <WalletIcon size={16} className="text-signal" />
        {authenticated ? `KES ${Number(balance ?? 0).toFixed(2)}` : "Wallet"}
      </Link>
      <Link
        to="/betting/jackpots"
        className="flex items-center gap-2 rounded-xl border border-white/10 bg-pitch px-3 py-2 text-sm font-semibold hover:border-signal/40"
      >
        <Trophy size={16} className="text-gold" />
        Jackpots
      </Link>
      <Link
        to="/betting/history"
        className="flex items-center gap-2 rounded-xl border border-white/10 bg-pitch px-3 py-2 text-sm font-semibold hover:border-signal/40"
      >
        <History size={16} className="text-chalk/70" />
        My bets
      </Link>
    </div>
  );
}

export default function Betting() {
  const { authenticated } = useAuth();

  const [board, setBoard] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [balance, setBalance] = useState(null);
  const [competition, setCompetition] = useState("ALL");
  const [live, setLive] = useState(false);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError("");
      const rows = await getOddsBoard();
      setBoard(rows);
    } catch (err) {
      console.error(err);
      setError("We couldn't load the odds board. Check your connection.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Wallet balance is only meaningful when signed in; a 401 just means
  // "not logged in", not a real error.
  useEffect(() => {
    if (!authenticated) {
      setBalance(null);
      return;
    }
    let active = true;
    getWallet()
      .then((w) => active && setBalance(w.balance))
      .catch(() => active && setBalance(null));
    return () => {
      active = false;
    };
  }, [authenticated]);

  // Live odds: merge WebSocket price updates into the already-loaded board
  // instead of re-fetching the whole list on every tick.
  useEffect(() => {
    const unsubscribe = connectOddsSocket((update) => {
      setLive(true);
      const matchId = Number(update.match_id ?? update.matchId);
      if (!matchId) return;

      setBoard((prev) => {
        const idx = prev.findIndex((m) => Number(m.match_id) === matchId);
        if (idx === -1) return prev;
        const next = [...prev];
        next[idx] = { ...next[idx], ...update };
        return next;
      });
    });
    return unsubscribe;
  }, []);

  const competitions = useMemo(() => {
    const set = new Set(board.map((m) => m.competition).filter(Boolean));
    return ["ALL", ...Array.from(set).sort()];
  }, [board]);

  const filtered = useMemo(() => {
    if (competition === "ALL") return board;
    return board.filter((m) => m.competition === competition);
  }, [board, competition]);

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-3xl font-black">Betting</h1>
          <p className="mt-1 text-slate-400">
            Odds generated from the FOOTY254 prediction model, shaded against live exposure.
            {live && <span className="ml-1 text-xs text-signal">● Live</span>}
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

      <QuickLinks balance={balance} authenticated={authenticated} />

      {competitions.length > 2 && (
        <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1">
          {competitions.map((c) => (
            <button
              key={c}
              onClick={() => setCompetition(c)}
              className={`shrink-0 rounded-full px-3 py-1.5 text-xs font-semibold transition ${
                competition === c
                  ? "bg-signal text-ink"
                  : "bg-pitch text-chalk/70 hover:bg-turf"
              }`}
            >
              {c === "ALL" ? "All competitions" : c}
            </button>
          ))}
        </div>
      )}

      {loading && (
        <div className="rounded-2xl border border-white/10 bg-pitch p-6 text-center text-slate-300">
          Loading odds...
        </div>
      )}

      {error && (
        <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-5 text-red-300">
          {error}
        </div>
      )}

      {!loading && !error && filtered.length === 0 && (
        <div className="rounded-2xl border border-white/10 bg-pitch p-8 text-center">
          <h2 className="text-xl font-black">No odds available right now</h2>
          <p className="mt-2 text-slate-400">
            Odds are generated automatically as fixtures come in. Check back shortly.
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {filtered.map((m) => (
          <OddsFixtureCard key={m.match_id} match={m} />
        ))}
      </div>
    </div>
  );
}
