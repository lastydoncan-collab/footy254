// ======================================================
// FOOTY254 ADMIN SERVICE
// Wraps the role-gated endpoints in api/admin.py. Every call here 403s for
// a non-admin session - the backend is the real gate, this is just the
// client for it.
// ======================================================

import { get, patch, post } from "./api";

export function listUsers({ search = "", limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams();

  if (search) params.set("search", search);
  params.set("limit", String(limit));
  params.set("offset", String(offset));

  return get(`/admin/users?${params.toString()}`);
}

export function updateUser(userId, changes) {
  return patch(`/admin/users/${userId}`, changes);
}

export function revokeUserSessions(userId) {
  return post(`/admin/users/${userId}/revoke-sessions`, {});
}
