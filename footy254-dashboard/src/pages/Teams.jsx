import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Search } from "lucide-react";
import { getTeams } from "../services";

export default function Teams() {
  const [teams, setTeams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");

  useEffect(() => {
    let cancelled = false;
    getTeams()
      .then((d) => !cancelled && setTeams(d.teams.map((t) => (typeof t === "string" ? t : t.team_name || t.name))))
      .catch(() => !cancelled && setError("We couldn't load teams."))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  const shown = useMemo(
    () => teams.filter((t) => t && t.toLowerCase().includes(query.trim().toLowerCase())),
    [teams, query]
  );

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-3xl font-black">Teams</h1>
        <p className="mt-1 text-slate-400">{teams.length} clubs in our leagues. Pick one to see its fixtures.</p>
      </header>

      <label className="relative block">
        <span className="sr-only">Search teams</span>
        <Search size={18} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" />
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search teams"
          className="w-full rounded-2xl py-3 pl-11 pr-4 outline-none"
        />
      </label>

      {loading && <p className="text-slate-400">Loading teams...</p>}
      {error && <p className="text-red-300">{error}</p>}
      {!loading && !error && shown.length === 0 && <p className="text-slate-400">No team matches “{query}”.</p>}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4">
        {shown.map((team) => (
          <Link
            key={team}
            to={`/predictions?team=${encodeURIComponent(team)}`}
            className="rounded-2xl border border-white/10 bg-pitch p-4 font-bold transition hover:border-signal/50 hover:bg-turf"
          >
            {team}
          </Link>
        ))}
      </div>
    </div>
  );
}
