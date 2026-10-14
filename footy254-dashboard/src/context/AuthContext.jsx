import {
  createContext,
  useContext,
  useEffect,
  useState,
} from "react";

import { SESSION_EXPIRED_EVENT } from "../services/api.js";

import {
  login,
  register,
  getCurrentUser,
  logout,
  forgotPassword,
  resetPassword,
  loginWithTwoFactor,
} from "../services";

const AuthContext = createContext(null);

const AUTH_SYNC_KEY = "footy254:auth-sync";

function announceAuthChange() {
  // Only a change signal - never any credential or user data.
  try {
    localStorage.setItem(AUTH_SYNC_KEY, String(Date.now()));
  } catch {
    // Storage can be unavailable (private mode); cross-tab sync is optional.
  }
}

export function AuthProvider({ children }) {

  const [user, setUser] = useState(null);

  const [loading, setLoading] = useState(true);

  // ==========================================
  // RESTORE SESSION
  // ==========================================

  useEffect(() => {

    let cancelled = false;

    async function restoreSession() {

      // The access/refresh tokens live in httpOnly cookies this code can't
      // read directly, so the only way to know if a session exists is to
      // ask the backend. A 401 here (no cookie, or an expired/invalid one
      // that the automatic refresh in api.js couldn't rescue) just means
      // "not logged in" — not an error worth surfacing.

      try {

        const response =
          await getCurrentUser();

        if (!cancelled) {

          setUser(response.user);

        }

      } catch {

        if (!cancelled) {

          setUser(null);

        }

      } finally {

        if (!cancelled) {

          setLoading(false);

        }

      }

    }

    restoreSession();

    return () => {

      cancelled = true;

    };

  }, []);

  // ==========================================
  // KEEP EVERY TAB IN SYNC
  // ==========================================

  useEffect(() => {

    // The API client fires this when a silent token refresh fails: the
    // session is over, so drop the stale logged-in UI.
    function onSessionExpired() {
      setUser(null);
    }

    // Signing out (or in) in another tab must be reflected here too.
    function onStorage(event) {

      if (event.key === AUTH_SYNC_KEY) {

        getCurrentUser()
          .then(response => setUser(response.user))
          .catch(() => setUser(null));

      }

    }

    window.addEventListener(SESSION_EXPIRED_EVENT, onSessionExpired);
    window.addEventListener("storage", onStorage);

    return () => {
      window.removeEventListener(SESSION_EXPIRED_EVENT, onSessionExpired);
      window.removeEventListener("storage", onStorage);
    };

  }, []);

  // ==========================================
  // LOGIN
  // ==========================================

  async function signIn(email, password) {

    const response =
      await login(email, password);

    // Accounts with two-factor on get a challenge instead of a session; the
    // caller finishes sign-in with completeTwoFactor().
    if (response.two_factor_required) {

      return response;

    }

    setUser(response.user);

    announceAuthChange();

    return response;

  }

  async function completeTwoFactor(challenge, code) {

    const response =
      await loginWithTwoFactor(challenge, code);

    setUser(response.user);

    announceAuthChange();

    return response;

  }

  // ==========================================
  // REGISTER
  // ==========================================

  async function signUp(userData) {

    const response =
      await register(userData);

    // Registration does not issue a token.  Keeping a user in context here
    // would make the UI appear signed in until the first protected request.
    return response;

  }

  // ==========================================
  // LOGOUT
  // ==========================================

  async function signOut() {

    try {

      await logout();

    } finally {

      // Even if the request failed (offline), the user asked to sign out:
      // clear local state so the UI cannot keep showing a signed-in view.
      setUser(null);

      announceAuthChange();

    }

  }

  // ==========================================
  // REFRESH USER
  // ==========================================

  async function refreshUser() {

    try {

      const response =
        await getCurrentUser();

      setUser(response.user);

      return response.user;

    } catch {

      setUser(null);

      return null;

    }

  }

  // ==========================================
  // CONTEXT VALUE
  // ==========================================

  const value = {

    user,

    loading,

    authenticated: !!user,

    isAdmin: !!user?.is_admin,

    login: signIn,

    completeTwoFactor,

    setUser,

    register: signUp,

    logout: signOut,

    refreshUser,

    forgotPassword,

    resetPassword,

  };

  return (

    <AuthContext.Provider value={value}>

      {children}

    </AuthContext.Provider>

  );

}

// The context provider and this hook intentionally share a module.
// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {

  return useContext(AuthContext);

}
