import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Sparkles, RefreshCw, ChevronLeft, ChevronRight } from "lucide-react";

import FixtureTile from "../components/FixtureTile";
import { useAuth } from "../context/AuthContext";
import { getPredictions } from "../services";
import { isToday, sortByFavoriteLeague } from "../utils/fixtureHelpers";

// 4 columns x 3 rows on desktop, 3 x 4 on tablets, 2 x 6 / 1 x 12 on phones.
const PAGE_SIZE = 12;

const VIEWS = [
  { id: "all", label: "All" },
  { id: "today", label: "Today" },
  { id: "upcoming", label: "Upcoming" },
];

export default function Predictions() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();

  const view = VIEWS.some((v) => v.id === params.get("view")) ? params.get("view") : "all";
  const league = params.get("league") || "";
  const team = params.get("team") || "";
  const page = Math.max(1, Number(params.get("page")) || 1);

  const [predictions, setPredictions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refreshMs = (user?.refresh_rate_seconds || 30) * 1000;

  const load = useCallback(async ({ silent = false } = {}) => {
    try {
      if (!silent) setLoading(true);
      setError("");
      setPredictions(await getPredictions());
    } catch (err) {
      console.error(err);
      setError(
        err?.status === 401
          ? "LOGIN_REQUIRED"
          : err?.status === 403
          ? "PREMIUM_REQUIRED"
          : "SERVER_ERROR"
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
    const id = setInterval(() => load({ silent: true }), refreshMs);
    return () => clearInterval(id);
  }, [load, refreshMs]);

  function setParam(changes) {
    const next = new URLSearchParams(params);
    Object.entries(changes).forEach(([k, v]) => (v ? next.set(k, v) : next.delete(k)));
    setParams(next, { replace: true });
  }

  const leagues = useMemo(
    () => [...new Set(predictions.map((p) => p.competition).filter(Boolean))].sort(),
    [predictions]
  );

  const visible = useMemo(() => {
    let list = predictions;
    if (view === "today") list = list.filter(isToday);
    if (view === "upcoming") list = list.filter((p) => !isToday(p));
    if (league) list = list.filter((p) => p.competition === league);
    if (team) list = list.filter((p) => p.home_team === team || p.away_team === team);
    return sortByFavoriteLeague(list, league ? "" : user?.favorite_league);
  }, [predictions, view, league, team, user?.favorite_league]);

  const pages = Math.max(1, Math.ceil(visible.length / PAGE_SIZE));
  const current = Math.min(page, pages);
  const slice = visible.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE);

  const chip = (active) =>
    `shrink-0 rounded-full px-4 py-1.5 text-sm font-semibold ${
      active ? "bg-chalk text-ink" : "bg-pitch text-chalk/80 hover:bg-turf"
    }`;

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-3xl font-black">Predict</h1>
          <p className="mt-1 text-slate-400">
            AI picks for every fixture, {PAGE_SIZE} per page.
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

      {team && (
        <p className="flex items-center gap-2 text-sm">
          Showing fixtures for <strong>{team}</strong>
          <button onClick={() => setParam({ team: "", page: "" })} className="font-bold text-signal hover:underline">
            Clear
          </button>
        </p>
      )}

      {!error && (
        <div className="space-y-3">
          <div className="flex gap-2 overflow-x-auto pb-1" role="tablist" aria-label="Fixture view">
            {VIEWS.map((v) => (
              <button
                key={v.id}
                role="tab"
                aria-selected={view === v.id}
                onClick={() => setParam({ view: v.id === "all" ? "" : v.id, page: "" })}
                className={chip(view === v.id)}
              >
                {v.label}
              </button>
            ))}
          </div>

          {leagues.length > 1 && (
            <div className="flex gap-2 overflow-x-auto pb-1" aria-label="League">
              <button onClick={() => setParam({ league: "", page: "" })} className={chip(!league)}>
                All leagues
              </button>
              {leagues.map((l) => (
                <button
                  key={l}
                  onClick={() => setParam({ league: l, page: "" })}
                  className={chip(league === l)}
                >
                  {l}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {loading && (
        <div className="rounded-2xl border border-white/10 bg-pitch p-8 text-center">
          <Sparkles className="mx-auto mb-4 animate-pulse text-signal" size={34} />
          <p className="text-slate-300">Loading predictions...</p>
        </div>
      )}

      {!loading && error === "LOGIN_REQUIRED" && (
        <div className="rounded-2xl border border-white/10 bg-pitch p-8 text-center">
          <h2 className="text-2xl font-black">Sign in to see predictions</h2>
          <p className="mt-3 text-slate-300">Create a free account or sign in to continue.</p>
          <button
            onClick={() => navigate("/login", { state: { from: { pathname: "/predictions" } } })}
            className="mt-6 rounded-xl bg-signal px-8 py-3 font-black text-ink"
          >
            Sign in
          </button>
        </div>
      )}

      {!loading && error === "PREMIUM_REQUIRED" && (
        <div className="rounded-2xl border border-signal/30 bg-signal/10 p-8 text-center">
          <h2 className="text-3xl font-black">FOOTY254 Premium</h2>
          <p className="mt-4 text-slate-300">
            AI match predictions, win probabilities, expected goals and confidence scores are for
            Premium members.
          </p>
          <button
            onClick={() => navigate("/subscriptions")}
            className="mt-8 rounded-xl bg-signal px-8 py-3 font-black text-ink hover:opacity-90"
          >
            See plans
          </button>
        </div>
      )}

      {!loading && error === "SERVER_ERROR" && (
        <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-5 text-red-300">
          We couldn't load predictions. Check your connection and press Refresh.
        </div>
      )}

      {!loading && !error && visible.length === 0 && (
        <div className="rounded-2xl border border-white/10 bg-pitch p-8 text-center">
          <Sparkles size={40} className="mx-auto mb-4 text-signal" />
          <h2 className="text-xl font-black">Nothing to show here</h2>
          <p className="mt-2 text-slate-400">
            {predictions.length === 0
              ? "Predictions appear once fixtures are synced and the model has run."
              : "No fixtures match this filter. Try another view or league."}
          </p>
        </div>
      )}

      {!loading && !error && slice.length > 0 && (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4">
            {slice.map((p) => (
              <FixtureTile key={p.match_id} match={p} />
            ))}
          </div>

          {pages > 1 && (
            <nav className="flex items-center justify-center gap-3" aria-label="Pages">
              <button
                disabled={current === 1}
                onClick={() => setParam({ page: String(current - 1) })}
                className="rounded-xl bg-pitch p-2 disabled:opacity-40"
                aria-label="Previous page"
              >
                <ChevronLeft />
              </button>
              <span className="text-sm text-slate-300">
                Page {current} of {pages} · {visible.length} fixtures
              </span>
              <button
                disabled={current === pages}
                onClick={() => setParam({ page: String(current + 1) })}
                className="rounded-xl bg-pitch p-2 disabled:opacity-40"
                aria-label="Next page"
              >
                <ChevronRight />
              </button>
            </nav>
          )}
        </>
      )}
    </div>
  );
}
