import {
    post,
    get,
    del,
} from "./api";

// ==========================================
// REGISTER
// ==========================================

export async function register(userData) {

    return post(
        "/auth/register",
        userData
    );

}

// ==========================================
// LOGIN
// ==========================================
//
// The backend sets httpOnly cookies on success — there is no token in the
// response for this client to store.

export async function login(
    email,
    password
) {

    return post(
        "/auth/login",
        {
            email,
            password,
        }
    );

}

// ==========================================
// CURRENT USER
// ==========================================

export async function getCurrentUser() {

    return get("/auth/me");

}

export async function changePassword(currentPassword, newPassword) {

    return post(
        "/auth/change-password",
        {
            current_password: currentPassword,
            new_password: newPassword,
        }
    );

}

// ==========================================
// FORGOT / RESET PASSWORD
// ==========================================

export async function forgotPassword(email) {

    return post(
        "/auth/forgot-password",
        { email }
    );

}

export async function resetPassword(token, newPassword) {

    return post(
        "/auth/reset-password",
        {
            token,
            new_password: newPassword,
        }
    );

}

// ==========================================
// ACTIVE SESSIONS
// ==========================================

export async function listSessions() {

    return get("/auth/sessions");

}

export async function revokeSession(sessionId) {

    return del(`/auth/sessions/${sessionId}`);

}

export async function revokeOtherSessions() {

    return post("/auth/sessions/revoke-others");

}

// ==========================================
// LOGOUT
// ==========================================
//
// Must hit the backend so the refresh token is revoked server-side, not
// just forgotten client-side.

export async function logout() {

    try {
        await post("/auth/logout");
    } catch {
        // Best-effort: even if this fails (e.g. offline), we still want the
        // caller to proceed with clearing local UI state.
    }

}

// ==========================================
// Backward compatibility
// ==========================================

export const registerUser = register;

export const loginUser = login;

export const logoutUser = logout;
