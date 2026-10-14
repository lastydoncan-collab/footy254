import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Laptop, LogOut, ShieldCheck, Lock, X } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import TwoFactorCard from "../components/TwoFactorCard";
import { updatePreferences } from "../services";
import {
  changePassword,
  listSessions,
  revokeSession,
  revokeOtherSessions,
} from "../services/auth";

export default function Security() {
  const { user, logout, setUser } = useAuth();
  const navigate = useNavigate();

  const loginAlerts = user?.login_alerts !== false;
  const [alertError, setAlertError] = useState("");
  const [passwords, setPasswords] = useState({ current: "", next: "" });
  const [passwordMessage, setPasswordMessage] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [changingPassword, setChangingPassword] = useState(false);

  const [sessions, setSessions] = useState([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [sessionsError, setSessionsError] = useState("");
  const [revokingId, setRevokingId] = useState(null);
  const [revokingOthers, setRevokingOthers] = useState(false);

  useEffect(() => {

    async function load() {
      try {
        setSessionsLoading(true);
        setSessionsError("");
        const response = await listSessions();
        setSessions(response.sessions || []);
      } catch (error) {
        setSessionsError(error.message || "Unable to load active devices.");
      } finally {
        setSessionsLoading(false);
      }
    }

    load();

  }, []);

  async function toggleLoginAlerts() {
    setAlertError("");
    try {
      const response = await updatePreferences({
        notifications_enabled: user.notifications_enabled !== false,
        match_alerts: user.match_alerts !== false,
        login_alerts: !loginAlerts,
        favorite_league: user.favorite_league || "All Leagues",
        refresh_rate_seconds: user.refresh_rate_seconds || 30,
      });
      setUser(response.user);
    } catch (error) {
      setAlertError(error.message || "Couldn't save that setting.");
    }
  }

  async function handleRevoke(sessionId) {
    try {
      setRevokingId(sessionId);
      await revokeSession(sessionId);
      setSessions((previous) => previous.filter((s) => s.id !== sessionId));
    } catch (error) {
      setSessionsError(error.message || "Unable to revoke that session.");
    } finally {
      setRevokingId(null);
    }
  }

  async function handleRevokeOthers() {
    try {
      setRevokingOthers(true);
      await revokeOtherSessions();
      setSessions((previous) => previous.filter((s) => s.is_current));
    } catch (error) {
      setSessionsError(error.message || "Unable to log out other devices.");
    } finally {
      setRevokingOthers(false);
    }
  }

  async function handlePasswordChange(event) {
    event.preventDefault();
    setPasswordError("");
    setPasswordMessage("");

    if (passwords.next.length < 8) {
      setPasswordError("Your new password must be at least 8 characters.");
      return;
    }

    try {
      setChangingPassword(true);
      const response = await changePassword(passwords.current, passwords.next);
      setPasswordMessage(response.message || "Password updated successfully.");
      setPasswords({ current: "", next: "" });

      // The backend revokes every session (including this one) on password
      // change, so the current cookies are already dead — send the user to
      // log back in rather than leaving them on a page that will 401.
      setTimeout(async () => {
        // Clear the in-memory user too, so the UI doesn't keep looking
        // signed in on the way to the login page.
        await logout();
        navigate("/login", { replace: true });
      }, 1200);
    } catch (error) {
      setPasswordError(error.message || "Unable to update password.");
    } finally {
      setChangingPassword(false);
    }
  }

  return (
    <div className="space-y-6">

      {/* Header */}

      <header>
        <p className="text-xs font-bold uppercase tracking-[0.22em] text-signal">
          Security
        </p>

        <h1 className="mt-2 text-3xl font-black">
          Account Security
        </h1>

        <p className="mt-2 text-slate-400">
          Protect your FOOTY254 account.
        </p>
      </header>

      {/* Current Account */}

      <section className="rounded-[24px] border border-white/10 bg-pitch p-5">

        <div className="flex items-center gap-4">

          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-signal/20 text-2xl font-black text-signal">

            {user?.first_name?.charAt(0)}

          </div>

          <div>

            <h2 className="text-xl font-black">
              {user?.first_name} {user?.last_name}
            </h2>

            <p className="text-slate-400">
              @{user?.username}
            </p>

            <p className="text-sm text-slate-500">
              {user?.email}
            </p>

          </div>

        </div>

      </section>

      <section className="rounded-[24px] border border-white/10 bg-pitch p-5">

        <h3 className="font-black">Change Password</h3>

        <form onSubmit={handlePasswordChange} className="mt-4 space-y-3">

          <input
            type="password"
            autoComplete="current-password"
            required
            placeholder="Current password"
            value={passwords.current}
            onChange={(event) => setPasswords({ ...passwords, current: event.target.value })}
            className="w-full rounded-xl border border-white/10 bg-turf px-4 py-3 outline-none"
          />

          <input
            type="password"
            autoComplete="new-password"
            required
            minLength="8"
            placeholder="New password (8+ characters)"
            value={passwords.next}
            onChange={(event) => setPasswords({ ...passwords, next: event.target.value })}
            className="w-full rounded-xl border border-white/10 bg-turf px-4 py-3 outline-none"
          />

          {passwordError && <p className="text-sm text-red-300">{passwordError}</p>}
          {passwordMessage && <p className="text-sm text-green-300">{passwordMessage}</p>}

          <button
            type="submit"
            disabled={changingPassword}
            className="rounded-xl bg-signal px-4 py-2 font-black text-ink disabled:opacity-50"
          >
            {changingPassword ? "Updating..." : "Update Password"}
          </button>

        </form>

      </section>

      {/* Two Factor */}

      <TwoFactorCard />

      {/* Login Alerts */}

      <section className="rounded-[24px] border border-white/10 bg-pitch p-5">

        <div className="flex items-center justify-between">

          <div>

            <div className="flex items-center gap-2">

              <Lock size={18} />

              <h3 className="font-black">
                Login Alerts
              </h3>

            </div>

            <p className="mt-2 text-sm text-slate-400">
              Email me whenever a new sign-in happens.
            </p>

            {alertError && <p className="mt-2 text-sm text-red-300">{alertError}</p>}

          </div>

          <button
            onClick={toggleLoginAlerts}
            className={`rounded-xl px-4 py-2 font-black ${
              loginAlerts
                ? "bg-signal text-ink"
                : "bg-white/10"
            }`}
          >
            {loginAlerts ? "ON" : "OFF"}
          </button>

        </div>

      </section>

      {/* Active Devices */}

      <section className="rounded-[24px] border border-white/10 bg-pitch p-5">

        <div className="mb-4 flex items-center justify-between">

          <h3 className="font-black">
            Active Devices
          </h3>

          {sessions.length > 1 && (
            <button
              onClick={handleRevokeOthers}
              disabled={revokingOthers}
              className="text-sm font-bold text-red-300 hover:underline disabled:opacity-50"
            >
              {revokingOthers ? "Logging out..." : "Log out other devices"}
            </button>
          )}

        </div>

        {sessionsError && (
          <p className="mb-3 text-sm text-red-300">{sessionsError}</p>
        )}

        {sessionsLoading ? (
          <p className="text-sm text-slate-400">Loading devices...</p>
        ) : sessions.length === 0 ? (
          <p className="text-sm text-slate-400">No active sessions found.</p>
        ) : (
          <div className="space-y-3">
            {sessions.map((session) => (
              <div
                key={session.id}
                className="flex items-center justify-between gap-4"
              >
                <div className="flex items-center gap-4">

                  <div className="rounded-full bg-signal/20 p-3 text-signal">
                    <Laptop size={22} />
                  </div>

                  <div>
                    <p className="font-bold">
                      {session.device}
                      {session.ip_address ? ` · ${session.ip_address}` : ""}
                    </p>

                    <p className="text-sm text-slate-400">
                      {session.is_current ? "Current Session" : "Active"}
                    </p>
                  </div>

                </div>

                {!session.is_current && (
                  <button
                    onClick={() => handleRevoke(session.id)}
                    disabled={revokingId === session.id}
                    title="Revoke this session"
                    className="rounded-lg p-2 text-slate-400 transition hover:bg-red-500/10 hover:text-red-300 disabled:opacity-50"
                  >
                    <X size={18} />
                  </button>
                )}

              </div>
            ))}
          </div>
        )}

      </section>

      {/* Logout */}

      <button
        onClick={logout}
        className="w-full rounded-[20px] bg-red-600 py-4 text-lg font-black transition hover:bg-red-500"
      >
        <div className="flex items-center justify-center gap-2">

          <LogOut size={18} />

          Logout

        </div>
      </button>

    </div>
  );
}
