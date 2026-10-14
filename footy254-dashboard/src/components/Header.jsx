import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { getLiveFixtures } from "../services/fixtures";

function nairobiTime() {
  return new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Africa/Nairobi",
  }).format(new Date());
}

export default function Header() {
  const { authenticated, user } = useAuth();
  const [time, setTime] = useState(nairobiTime);
  const [liveCount, setLiveCount] = useState(null);

  useEffect(() => {
    const id = setInterval(() => setTime(nairobiTime()), 30000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    let active = true;
    const load = () =>
      getLiveFixtures()
        .then((d) => active && setLiveCount(d.count ?? d.fixtures.length))
        .catch(() => active && setLiveCount(null));
    load();
    const id = setInterval(load, 60000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  const name = user?.name || user?.full_name || user?.email || "";
  const initial = name ? name.trim()[0].toUpperCase() : "";

  return (
    <header className="sticky top-0 z-30 border-b border-white/10 bg-ink/85 backdrop-blur-md lg:pl-28">
      <div className="flag-stripe" aria-hidden="true" />
      <div className="mx-auto flex max-w-md items-center justify-between gap-3 px-4 py-3 sm:max-w-2xl lg:max-w-6xl">
        <Link to="/" className="flex flex-col leading-none" aria-label="FOOTY254 home">
          <span className="font-display font-display-italic text-2xl text-chalk">
            FOOTY<span className="text-signal">254</span>
          </span>
          <span className="mt-1 text-[11px] text-chalk/60">Smarter picks. Better wins.</span>
        </Link>

        <div className="flex items-center gap-2 text-xs">
          <Link
            to="/live"
            className="flex items-center gap-2 rounded-full border border-white/10 bg-pitch px-3 py-1.5 text-chalk"
          >
            <span
              className={`h-2 w-2 rounded-full ${liveCount > 0 ? "bg-signal" : "bg-chalk/30"}`}
              aria-hidden="true"
            />
            {liveCount === null ? "Live" : liveCount > 0 ? `${liveCount} live now` : "No live games"}
          </Link>

          <span className="hidden rounded-full border border-white/10 bg-pitch px-3 py-1.5 text-chalk/70 sm:inline">
            Nairobi {time}
          </span>

          {authenticated ? (
            <Link
              to="/settings"
              aria-label="Account settings"
              className="flex h-8 w-8 items-center justify-center rounded-full bg-chalk font-bold text-ink"
            >
              {initial || "•"}
            </Link>
          ) : (
            <Link to="/login" className="rounded-full bg-signal px-4 py-1.5 font-bold text-ink">
              Sign in
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
