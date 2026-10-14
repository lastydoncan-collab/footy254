import { useState } from "react";
import {
  Link,
  useNavigate,
  useSearchParams,
} from "react-router-dom";

import { Eye, EyeOff } from "lucide-react";

import { useAuth } from "../context/AuthContext";

export default function ResetPassword() {

  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") || "";

  const { resetPassword } = useAuth();

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event) {

    event.preventDefault();
    setError("");

    if (!token) {
      setError("This reset link is missing its token. Request a new one.");
      return;
    }

    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);

    try {

      await resetPassword(token, password);

      navigate("/login", {
        replace: true,
        state: { registrationSuccess: false, passwordResetSuccess: true },
      });

    } catch (err) {

      setError(
        err?.detail ||
        err?.message ||
        "This reset link is invalid or has expired."
      );

    } finally {

      setLoading(false);

    }

  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-ink px-6">
      <div className="w-full max-w-md rounded-3xl border border-white/10 bg-pitch p-8 shadow-2xl">
        <div className="flex justify-center">
          <img
            src="/footy254-icon.png"
            alt="FOOTY254"
            width="64"
            height="64"
            className="h-16 w-16 rounded-full object-cover ring-2 ring-signal/40 drop-shadow-[0_0_16px_rgba(31,230,173,.25)]"
          />
        </div>

        <h1 className="mt-6 text-3xl font-black text-white">
          Set a New Password
        </h1>
        <p className="mt-2 text-slate-400">
          Choose a new password for your account.
        </p>

        {error && (
          <div className="mt-5 rounded-xl border border-red-500/30 bg-red-500/20 p-3 text-red-300">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-6 space-y-5">
          <div>
            <label className="text-sm font-semibold text-slate-300">
              New Password
            </label>
            <div className="relative mt-2">
              <input
                type={showPassword ? "text" : "password"}
                name="password"
                autoComplete="new-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="At least 8 characters"
                className="w-full rounded-xl border border-white/10 bg-turf px-4 py-3 pr-14 text-white outline-none transition focus:border-signal"
              />
              <button
                type="button"
                onClick={() => setShowPassword((previous) => !previous)}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 transition hover:text-white"
              >
                {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
              </button>
            </div>
          </div>

          <div>
            <label className="text-sm font-semibold text-slate-300">
              Confirm New Password
            </label>
            <input
              type={showPassword ? "text" : "password"}
              name="confirmPassword"
              autoComplete="new-password"
              required
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              placeholder="Re-enter your new password"
              className="mt-2 w-full rounded-xl border border-white/10 bg-turf px-4 py-3 text-white outline-none transition focus:border-signal"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-xl bg-signal py-3 font-black text-ink transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? "Updating..." : "Update Password"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-slate-400">
          <Link
            to="/login"
            className="font-bold text-signal hover:underline"
          >
            Back to Login
          </Link>
        </p>
      </div>
    </div>
  );
}
