import { Heart } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { isFavorite, toggleFavorite, subscribeFavorites } from "../utils/favorites";
import { getProbabilities, isLiveMatch } from "../utils/fixtureHelpers";

const OUTCOME = ["Home", "Draw", "Away"];

// Compact fixture card sized for 3-4 column grids. Shows the live score when
// the match is in play and the AI outcome whenever a prediction is available.
export default function FixtureTile({ match, locked = false }) {
  const navigate = useNavigate();
  const id = match.match_id;
  const [saved, setSaved] = useState(() => isFavorite(id));

  useEffect(() => subscribeFavorites(() => setSaved(isFavorite(id))), [id]);

  const live = isLiveMatch(match);
  const probs = getProbabilities(match);
  const best = probs ? probs.indexOf(Math.max(...probs)) : -1;
  const kickoff = match.kickoff ? new Date(match.kickoff) : null;
  const hasScore = match.score_home != null && match.score_away != null;

  const pick =
    best === 0 ? match.home_team : best === 2 ? match.away_team : best === 1 ? "Draw" : null;

  return (
    <article
      className="flex cursor-pointer flex-col rounded-2xl border border-white/10 bg-pitch p-4 transition hover:border-signal/40"
      onClick={() => navigate(`/predictions/${id}`)}
    >
      <div className="flex items-center justify-between gap-2 text-xs text-chalk/70">
        <span className="truncate">{match.competition || match.competition_code}</span>
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
          <button
            type="button"
            aria-label={saved ? "Remove from saved" : "Save match"}
            aria-pressed={saved}
            onClick={(e) => {
              e.stopPropagation();
              toggleFavorite(match);
              setSaved(isFavorite(id));
            }}
            className={saved ? "text-signal" : "text-chalk/40 hover:text-signal"}
          >
            <Heart size={15} fill={saved ? "currentColor" : "none"} />
          </button>
        </div>
      </div>

      <div className="mt-3 space-y-1.5">
        <div className="flex items-center justify-between gap-2">
          <span className="truncate font-bold">{match.home_team || "TBD"}</span>
          {(live || hasScore) && (
            <span className="text-lg font-black tabular-nums">{match.score_home ?? 0}</span>
          )}
        </div>
        <div className="flex items-center justify-between gap-2">
          <span className="truncate font-bold">{match.away_team || "TBD"}</span>
          {(live || hasScore) && (
            <span className="text-lg font-black tabular-nums">{match.score_away ?? 0}</span>
          )}
        </div>
      </div>

      <div className="mt-auto pt-4">
        {probs ? (
          <>
            <div className="flex h-2 overflow-hidden rounded-full bg-ink" aria-hidden="true">
              <div className="bg-leaf" style={{ width: `${probs[0]}%` }} />
              <div className="bg-chalk/50" style={{ width: `${probs[1]}%` }} />
              <div className="bg-signal" style={{ width: `${probs[2]}%` }} />
            </div>
            <div className="mt-1 flex justify-between text-[11px] tabular-nums text-chalk/70">
              {probs.map((p, i) => (
                <span key={OUTCOME[i]}>
                  {OUTCOME[i]} {p.toFixed(0)}%
                </span>
              ))}
            </div>
            <p className="mt-2 truncate text-sm">
              <span className="text-chalk/60">AI pick: </span>
              <span className="font-bold text-chalk">{pick}</span>
              {typeof match.confidence === "number" && match.confidence > 0 && (
                <span className="text-chalk/60"> · {Math.round(match.confidence)}%</span>
              )}
            </p>
          </>
        ) : locked ? (
          <p className="text-xs text-chalk/60">Premium shows the AI pick for this match.</p>
        ) : (
          <p className="text-xs text-chalk/60">Prediction not ready yet.</p>
        )}
      </div>
    </article>
  );
}
