// ======================================================
// FOOTY254 API CLIENT
// Shared HTTP client used by all frontend services.
// ======================================================

import {
  fallbackPrediction,
} from "../data/mockData.js";

// ======================================================
// CONFIGURATION
// ======================================================
//
// By default the API is on the SAME origin as the page, under /api (the
// FastAPI server serves this app; in development Vite proxies /api). That is
// what makes the app work on any device and network - a phone on the LAN, a
// laptop, an installed PWA - with no address baked into the build.
//
// VITE_API_URL is only for the unusual case of hosting the API on another
// domain, e.g. VITE_API_URL=https://api.example.com
//
// (A legacy value like http://127.0.0.1:8000 keeps working: /api is appended.)

const API_ORIGIN = (import.meta.env.VITE_API_URL || "").replace(/\/+$/, "");

export const BASE_URL = `${API_ORIGIN}/api`;

const REQUEST_TIMEOUT_MS = 30000;

// Fired when the session can no longer be recovered (refresh failed), so the
// UI can sign the user out everywhere instead of showing a stale logged-in
// state.
export const SESSION_EXPIRED_EVENT = "footy254:session-expired";

// ======================================================
// AUTH STATE
// ======================================================
//
// Access/refresh tokens live in httpOnly cookies set by the backend - this
// client never reads or stores them directly, which is what keeps them safe
// from theft via XSS. `credentials: "include"` is what makes the browser
// attach those cookies to every request below.

let refreshInFlight = null;

// Endpoints whose 401 means "wrong credentials / no session" and must NEVER
// trigger a refresh (that would loop). Everything else under /auth - notably
// /auth/me, used to restore a session on page load - SHOULD be rescued by a
// silent refresh; otherwise a user idle for more than the 15-minute access
// token lifetime appears logged out despite a valid 30-day refresh cookie.
const NO_REFRESH_ENDPOINTS = [
  "/auth/login",
  "/auth/register",
  "/auth/refresh",
  "/auth/logout",
  "/auth/forgot-password",
  "/auth/reset-password",
];

async function attemptRefresh() {
  // Coalesce concurrent 401s into a single refresh call instead of firing
  // one refresh request per failed request.
  if (!refreshInFlight) {
    refreshInFlight = fetch(`${BASE_URL}/auth/refresh`, {
      method: "POST",
      credentials: "include",
    })
      .then(res => res.ok)
      .catch(() => false)
      .finally(() => {
        refreshInFlight = null;
      });
  }

  return refreshInFlight;
}

// ======================================================
// ERROR HELPERS
// ======================================================

function extractMessage(body, status) {
  const detail = body?.detail;

  if (typeof detail === "string" && detail) {
    return detail;
  }

  // Defensive: a raw FastAPI validation list.
  if (Array.isArray(detail)) {
    const joined = detail
      .map(item => item?.msg)
      .filter(Boolean)
      .join(" ");

    if (joined) {
      return joined;
    }
  }

  if (typeof body?.message === "string" && body.message) {
    return body.message;
  }

  if (status === 429) {
    return "Too many requests. Please wait a moment and try again.";
  }

  return "Request failed.";
}

function makeError(message, status) {
  const error = new Error(message);
  error.status = status;
  return error;
}

async function readBody(response) {
  try {
    return await response.json();
  } catch {
    return {};
  }
}

// ======================================================
// GENERIC REQUEST
// ======================================================

export async function request(
  endpoint,
  options = {},
  _retried = false
) {
  const controller = new AbortController();
  const timer = setTimeout(
    () => controller.abort(),
    REQUEST_TIMEOUT_MS
  );

  let response;

  try {
    response = await fetch(
      `${BASE_URL}${endpoint}`,
      {
        ...options,
        credentials: "include",
        headers: options.headers,
        signal: controller.signal,
      }
    );
  } catch (cause) {
    // Offline, DNS failure, server down, or timeout. status 0 lets callers
    // tell "can't reach the server" apart from an HTTP error.
    throw makeError(
      cause?.name === "AbortError"
        ? "The server took too long to respond. Please try again."
        : "Unable to reach the server. Check your internet connection.",
      0
    );
  } finally {
    clearTimeout(timer);
  }

  // ------------------------------------
  // Unauthorized - try one silent token refresh before giving up.
  // ------------------------------------

  if (response.status === 401) {

    const canRefresh = !NO_REFRESH_ENDPOINTS.some(path =>
      endpoint.startsWith(path)
    );

    if (!_retried && canRefresh) {
      const refreshed = await attemptRefresh();

      if (refreshed) {
        return request(endpoint, options, true);
      }

      // The session is gone for good.
      window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
    }

    // Surface the server's message for credential endpoints (e.g. "Invalid
    // email or password.") instead of a generic "Login required.".
    const body = canRefresh ? {} : await readBody(response);

    throw makeError(
      canRefresh
        ? "Login required."
        : extractMessage(body, 401),
      401
    );
  }

  // ------------------------------------
  // Error responses
  // ------------------------------------

  if (!response.ok) {

    const body = await readBody(response);

    throw makeError(
      extractMessage(body, response.status),
      response.status
    );
  }

  // ------------------------------------
  // Empty response
  // ------------------------------------

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

// ======================================================
// HTTP SHORTCUTS
// ======================================================

export function get(endpoint) {
  return request(endpoint);
}

export function post(
  endpoint,
  body = {}
) {
  return request(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
}

export function put(
  endpoint,
  body = {}
) {
  return request(endpoint, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
}

export function patch(
  endpoint,
  body = {}
) {
  return request(endpoint, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
}

export function del(endpoint) {
  return request(endpoint, {
    method: "DELETE",
  });
}

// ======================================
// PREDICTION NORMALIZER
// ======================================

export function normalizePrediction(fixture, prediction = {}) {
  return {
    // ----------------------------------
    // Original fixture
    // ----------------------------------
    ...fixture,

    // ----------------------------------
    // Friendly aliases
    // ----------------------------------
    home: fixture.home_team,
    away: fixture.away_team,
    league: fixture.competition,

    // ----------------------------------
    // Prediction
    // ----------------------------------
    prediction:
      prediction.prediction ??
      fixture.prediction ??
      "Unavailable",

    confidence:
      prediction.confidence ??
      fixture.confidence ??
      0,

    homeWin:
      prediction.probabilities?.home_win ??
      prediction.homeWin ??
      fixture.homeWin ??
      0,

    draw:
      prediction.probabilities?.draw ??
      prediction.draw ??
      fixture.draw ??
      0,

    awayWin:
      prediction.probabilities?.away_win ??
      prediction.awayWin ??
      fixture.awayWin ??
      0,

    xgHome:
      prediction.xg?.home ??
      prediction.xgHome ??
      fixture.xgHome ??
      0,

    xgAway:
      prediction.xg?.away ??
      prediction.xgAway ??
      fixture.xgAway ??
      0,
  };
}

// ======================================================
// SAFE FALLBACK
// Used only when prediction endpoint is unavailable.
// ======================================================

export function predictionFallback(
  home,
  away
) {
  return fallbackPrediction(
    home,
    away
  );
}
