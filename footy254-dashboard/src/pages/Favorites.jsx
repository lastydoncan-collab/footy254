import { useEffect, useState } from "react";
import { Heart } from "lucide-react";

import MatchCard from "../components/MatchCard";
import {
  getFavorites,
  removeFavorite as removeFavoriteMatch,
  subscribeFavorites,
} from "../utils/favorites";

export default function Favorites() {
  const [favorites, setFavorites] = useState(() => getFavorites());
  const loading = false;

  // Stay in sync with favorites added/removed from MatchCard elsewhere in
  // the app (e.g. saved from Predictions, then this page opened next).
  useEffect(() => {
    return subscribeFavorites(setFavorites);
  }, []);

  // ==========================================
  // REMOVE FAVORITE
  // ==========================================

  function removeFavorite(matchId) {
    removeFavoriteMatch(matchId);
  }

  return (
    <div className="space-y-6">
      {/* Header */}

      <header>
        <p className="text-xs font-bold uppercase tracking-[0.22em] text-signal">
          Saved
        </p>

        <h1 className="mt-2 text-3xl font-black">
          Favorite Predictions
        </h1>

        <p className="mt-2 text-slate-400">
          Your saved prediction cards.
        </p>
      </header>

      {/* Loading */}

      {loading && (
        <div className="rounded-[28px] border border-white/10 bg-pitch p-8 text-center">
          <Heart
            className="mx-auto mb-4 animate-pulse text-signal"
            size={34}
          />

          <p className="text-slate-300">
            Loading favorites...
          </p>
        </div>
      )}

      {/* Empty */}

      {!loading && favorites.length === 0 && (
        <div className="rounded-[28px] border border-white/10 bg-pitch p-8 text-center">
          <Heart
            className="mx-auto mb-4 text-signal"
            size={36}
          />

          <h2 className="text-xl font-black">
            No saved predictions
          </h2>

          <p className="mt-2 text-slate-400">
            Save predictions to quickly access them later.
          </p>
        </div>
      )}

      {/* Favorite Cards */}

      {!loading && favorites.length > 0 && (
        <div className="grid gap-5">
          {favorites.map((match) => (
            <div
              key={match.match_id}
              className="relative"
            >
              <MatchCard
                match={match}
              />

              <button
                onClick={() =>
                  removeFavorite(match.match_id)
                }
                className="absolute right-4 top-4 rounded-full bg-red-500 px-3 py-2 text-xs font-bold text-white transition hover:bg-red-600"
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
