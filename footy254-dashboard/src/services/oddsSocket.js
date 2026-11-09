// ======================================================
// LIVE ODDS SOCKET
// ======================================================
//
// Thin wrapper around the public `/api/betting/ws/odds` feed published by
// services/odds_hub.py on the backend. No auth - odds are public, same as
// live scores.
//
// Usage:
//   const unsubscribe = connectOddsSocket((update) => { ... });
//   // later: unsubscribe();
//
// One shared socket per tab (not one per subscriber) so opening the odds
// board on several pages / components doesn't open N connections.

import { BASE_URL } from "./api";

let socket = null;
let listeners = new Set();
let reconnectTimer = null;
let reconnectDelayMs = 1000;

function wsUrl() {
  // BASE_URL is like "https://host/api" or "/api" (relative, same-origin
  // dev proxy). Build the absolute ws(s):// URL from it either way.
  const base = BASE_URL.startsWith("http")
    ? BASE_URL
    : `${window.location.origin}${BASE_URL}`;

  return base.replace(/^http/, "ws") + "/betting/ws/odds";
}

function broadcast(update) {
  for (const fn of listeners) {
    try {
      fn(update);
    } catch (err) {
      console.error("Odds subscriber threw:", err);
    }
  }
}

function open() {
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
    return;
  }

  try {
    socket = new WebSocket(wsUrl());
  } catch (err) {
    console.warn("Could not open odds socket:", err);
    scheduleReconnect();
    return;
  }

  socket.onopen = () => {
    reconnectDelayMs = 1000;
  };

  socket.onmessage = (event) => {
    try {
      const update = JSON.parse(event.data);
      broadcast(update);
    } catch {
      // Non-JSON frame (e.g. a keepalive ping some proxies inject) - ignore.
    }
  };

  socket.onclose = () => {
    socket = null;
    if (listeners.size > 0) scheduleReconnect();
  };

  socket.onerror = () => {
    // onclose fires right after - the reconnect is scheduled there.
  };
}

function scheduleReconnect() {
  if (reconnectTimer) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    if (listeners.size > 0) open();
  }, reconnectDelayMs);
  // Back off up to 15s so a backend that's down doesn't get hammered.
  reconnectDelayMs = Math.min(reconnectDelayMs * 1.6, 15000);
}

export function connectOddsSocket(onUpdate) {
  listeners.add(onUpdate);
  open();

  return function unsubscribe() {
    listeners.delete(onUpdate);
    if (listeners.size === 0 && socket) {
      socket.close();
      socket = null;
    }
  };
}
