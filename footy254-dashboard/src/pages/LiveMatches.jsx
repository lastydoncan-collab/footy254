import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { RefreshCw } from "lucide-react";

import FixtureTile from "../components/FixtureTile";
import { useAuth } from "../context/AuthContext";
import { getLiveFixtures, getPredictions } from "../services";
import { sortByFavoriteLeague } from "../utils/fixtureHelpers";

export default function LiveMatches() {
  const { user, authenticated } = useAuth();

  const [matches, setMatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [locked, setLocked] = useState(false);
  const [updated, setUpdated] = useState(null);

  const refreshMs = Math.min(user?.refresh_rate_seconds || 30, 30) * 1000;

  const load = useCallback(
    async ({ silent = false } = {}) => {
      try {
        if (!silent) setLoading(true);
        setError("");

        // Live scores are public.
        const { fixtures } = await getLiveFixtures();

        // The AI outcome is premium: fetch it, but a 401/403 only means the
        // visitor sees scores without the pick.
        let byId = new Map();
        try {
          const all = await getPredictions();
          byId = new Map(all.map((p) => [Number(p.match_id), p]));
          setLocked(false);
        } catch (err) {
          setLocked(true);
          console.warn("Live predictions unavailable:", err?.status);
        }

        setMatches(
          fixtures.map((fx) => ({ ...(byId.get(Number(fx.match_id)) || {}), ...fx }))
        );
        setUpdated(new Date());
      } catch (err) {
        console.error(err);
        setError("We couldn't load live matches. Check your connection.");
      } finally {
        setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
    const id = setInterval(() => load({ silent: true }), refreshMs);
    return () => clearInterval(id);
  }, [load, refreshMs]);

  const list = sortByFavoriteLeague(matches, user?.favorite_league);

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-3xl font-black">Live</h1>
          <p className="mt-1 text-slate-400">
            Scores for matches in play, with the AI's pick for each.
            {updated && (
              <span className="ml-1 text-xs">
                Updated {updated.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}.
              </span>
            )}
          </p>
        </div>
        <button
          onClick={() => load()}
          disabled={loading}
          className="flex items-center gap-2 rounded-xl bg-turf px-4 py-2 text-sm font-semibold hover:bg-line disabled:opacity-50"
        >
          <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {locked && list.length > 0 && (
        <p className="rounded-2xl border border-white/10 bg-pitch p-4 text-sm text-slate-300">
          {authenticated ? (
            <>
              AI picks for live matches are part of Premium.{" "}
              <Link to="/subscriptions" className="font-bold text-signal hover:underline">
                See plans
              </Link>
            </>
          ) : (
            <>
              <Link to="/login" className="font-bold text-signal hover:underline">
                Sign in
              </Link>{" "}
              to see AI picks next to the scores.
            </>
          )}
        </p>
      )}

      {loading && (
        <div className="rounded-2xl border border-white/10 bg-pitch p-6 text-center text-slate-300">
          Loading live matches...
        </div>
      )}

      {error && (
        <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-5 text-red-300">
          {error}
        </div>
      )}

      {!loading && !error && list.length === 0 && (
        <div className="rounded-2xl border border-white/10 bg-pitch p-8 text-center">
          <h2 className="text-xl font-black">No matches in play right now</h2>
          <p className="mt-2 text-slate-400">
            See what's coming up on the{" "}
            <Link to="/predictions?view=upcoming" className="font-bold text-signal hover:underline">
              Predict page
            </Link>
            .
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4">
        {list.map((m) => (
          <FixtureTile key={m.match_id} match={m} locked={locked} />
        ))}
      </div>
    </div>
  );
}
