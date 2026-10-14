// ======================================================
// FOOTY254 FAVORITES
// ======================================================
//
// Shared localStorage-backed favorites store. Previously the Favorites
// page read from this storage key, but nothing anywhere in the app ever
// wrote to it — there was no save/heart button, so "Saved" was a
// permanently empty destination no matter what a user did. This is the
// single source of truth both MatchCard (writer) and Favorites (reader)
// now share.

const STORAGE_KEY = "footy254_favorites";

// Fired on the same change that updates localStorage so every mounted
// MatchCard/Favorites instance in this tab re-renders immediately —
// the native "storage" event only fires in *other* tabs, never the one
// that made the change.
const CHANGE_EVENT = "footy254-favorites-changed";

export function getFavorites() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);

    if (!saved) return [];

    const parsed = JSON.parse(saved);

    return Array.isArray(parsed) ? parsed : [];
  } catch (error) {
    console.error("Unable to read favorites.", error);
    return [];
  }
}

function persist(favorites) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(favorites));
  window.dispatchEvent(new CustomEvent(CHANGE_EVENT));
}

export function isFavorite(matchId) {
  return getFavorites().some(
    (match) => Number(match.match_id) === Number(matchId)
  );
}

export function addFavorite(match) {
  if (!match?.match_id) return;

  const current = getFavorites();

  if (current.some((m) => Number(m.match_id) === Number(match.match_id))) {
    return;
  }

  persist([...current, match]);
}

export function removeFavorite(matchId) {
  const current = getFavorites();

  persist(
    current.filter(
      (match) => Number(match.match_id) !== Number(matchId)
    )
  );
}

export function toggleFavorite(match) {
  if (isFavorite(match.match_id)) {
    removeFavorite(match.match_id);
  } else {
    addFavorite(match);
  }
}

export function subscribeFavorites(callback) {
  function handleChange() {
    callback(getFavorites());
  }

  window.addEventListener(CHANGE_EVENT, handleChange);
  window.addEventListener("storage", handleChange);

  return () => {
    window.removeEventListener(CHANGE_EVENT, handleChange);
    window.removeEventListener("storage", handleChange);
  };
}
