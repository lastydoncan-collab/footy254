import {
  Calendar,
  Clock,
  Trophy,
  ChevronRight,
  Heart,
} from "lucide-react";

import { useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";

import { isFavorite, toggleFavorite, subscribeFavorites } from "../utils/favorites";

export default function MatchCard({ match }) {
  const navigate = useNavigate();

  const {
    match_id,

    competition,
    competition_code,

    stage,
    status,

    kickoff,

    home_team,
    away_team,

    prediction,
    confidence,

    home_win_probability,
    draw_probability,
    away_win_probability,

    expected_home_goals,
    expected_away_goals,
  } = match;

  const [saved, setSaved] = useState(() => isFavorite(match_id));

  // Stay in sync if this same match is (un)favorited from elsewhere —
  // e.g. removed from the Favorites page while this card is also on
  // screen (Predictions and Favorites can render the same match_id).
  useEffect(() => {
    return subscribeFavorites(() => {
      setSaved(isFavorite(match_id));
    });
  }, [match_id]);

  function handleToggleFavorite(event) {
    event.stopPropagation();
    toggleFavorite(match);
    setSaved(isFavorite(match_id));
  }

  const kickoffDate = kickoff
    ? new Date(kickoff)
    : null;

  const formatPercent = (value) =>
    typeof value === "number"
      ? `${value.toFixed(1)}%`
      : "--";

  const formatXG = (value) =>
    typeof value === "number"
      ? value.toFixed(2)
      : "--";

  function openPrediction() {
    navigate(`/predictions/${match_id}`);
  }

  return (
    <article className="rounded-[24px] border border-white/10 bg-pitch p-5 shadow-xl transition hover:border-signal/30">

      {/* Competition */}

      <div className="mb-4 flex items-center justify-between">

        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-signal">
          <Trophy size={14} />
          <span>{competition}</span>
        </div>

        <div className="flex items-center gap-2">

          <span className="rounded-full bg-turf px-3 py-1 text-xs font-semibold text-slate-300">
            {stage || competition_code}
          </span>

          <button
            type="button"
            onClick={handleToggleFavorite}
            aria-label={saved ? "Remove from saved" : "Save prediction"}
            aria-pressed={saved}
            className={`rounded-full p-2 transition ${
              saved
                ? "bg-red-500/15 text-red-400 hover:bg-red-500/25"
                : "bg-turf text-slate-400 hover:text-red-400"
            }`}
          >
            <Heart size={16} fill={saved ? "currentColor" : "none"} />
          </button>

        </div>

      </div>

      {/* Teams */}

      <div className="space-y-3">

        <div className="text-xl font-black">
          {home_team || "TBD"}
        </div>

        <div className="text-center text-sm text-slate-500">
          VS
        </div>

        <div className="text-xl font-black">
          {away_team || "TBD"}
        </div>

      </div>

      {/* Date */}

      <div className="mt-6 grid grid-cols-2 gap-3">

        <div className="rounded-xl bg-turf p-3">

          <div className="mb-1 flex items-center gap-2 text-xs text-slate-400">
            <Calendar size={14} />
            Date
          </div>

          <div className="font-bold">
            {kickoffDate
              ? kickoffDate.toLocaleDateString()
              : "--"}
          </div>

        </div>

        <div className="rounded-xl bg-turf p-3">

          <div className="mb-1 flex items-center gap-2 text-xs text-slate-400">
            <Clock size={14} />
            Kickoff
          </div>

          <div className="font-bold">
            {kickoffDate
              ? kickoffDate.toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })
              : "--"}
          </div>

        </div>

      </div>

      {/* Prediction */}

      {prediction && (

        <div className="mt-5 rounded-2xl bg-turf p-4">

          <div className="flex items-center justify-between">

            <span className="text-sm text-slate-400">
              AI Prediction
            </span>

            <span className="font-black text-signal">
              {formatPercent(confidence)}
            </span>

          </div>

          <div className="mt-2 text-lg font-black">
            {prediction}
          </div>

        </div>

      )}

      {/* Probabilities */}

      {(home_win_probability != null ||
        draw_probability != null ||
        away_win_probability != null) && (

        <div className="mt-4 grid grid-cols-3 gap-2 text-center">

          <div className="rounded-xl bg-turf p-3">

            <div className="text-xs text-slate-400">
              Home
            </div>

            <div className="font-black">
              {formatPercent(home_win_probability)}
            </div>

          </div>

          <div className="rounded-xl bg-turf p-3">

            <div className="text-xs text-slate-400">
              Draw
            </div>

            <div className="font-black">
              {formatPercent(draw_probability)}
            </div>

          </div>

          <div className="rounded-xl bg-turf p-3">

            <div className="text-xs text-slate-400">
              Away
            </div>

            <div className="font-black">
              {formatPercent(away_win_probability)}
            </div>

          </div>

        </div>

      )}

      {/* xG */}

      {(expected_home_goals != null ||
        expected_away_goals != null) && (

        <div className="mt-4 grid grid-cols-2 gap-2">

          <div className="rounded-xl bg-turf p-3 text-center">

            <div className="text-xs text-slate-400">
              Home xG
            </div>

            <div className="font-black">
              {formatXG(expected_home_goals)}
            </div>

          </div>

          <div className="rounded-xl bg-turf p-3 text-center">

            <div className="text-xs text-slate-400">
              Away xG
            </div>

            <div className="font-black">
              {formatXG(expected_away_goals)}
            </div>

          </div>

        </div>

      )}

      {/* Status */}

      <div className="mt-5 flex items-center justify-between">

        <span className="rounded-full bg-signal/10 px-3 py-1 text-xs font-bold text-signal">
          {status}
        </span>

      </div>

      {/* View Prediction */}

      <button
        onClick={openPrediction}
        className="mt-5 flex w-full items-center justify-center gap-2 rounded-2xl bg-signal py-3 font-black text-ink transition hover:opacity-90"
      >
        View Prediction
        <ChevronRight size={18} />
      </button>

    </article>
  );
}