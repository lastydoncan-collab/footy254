// ======================================================
// FOOTY254 ACCOUNT SERVICE (profile, preferences, 2FA, card payments)
// ======================================================

import { get, post, put, patch } from "./api";

export function updateProfile(data) {
  return patch("/account/profile", data);
}

export function updatePreferences(data) {
  return put("/account/preferences", data);
}

export function startTwoFactorSetup(password) {
  return post("/account/2fa/setup", { password });
}

export function enableTwoFactor(code) {
  return post("/account/2fa/enable", { code });
}

export function disableTwoFactor(password, code) {
  return post("/account/2fa/disable", { password, code });
}

export function loginWithTwoFactor(challenge, code) {
  return post("/auth/login/2fa", { challenge, code });
}

export function getCardStatus() {
  return get("/card/status");
}

export function startCardCheckout(plan) {
  return post("/card/checkout", { plan });
}

export function verifyCardPayment(reference) {
  return get(`/card/verify/${encodeURIComponent(reference)}`);
}
