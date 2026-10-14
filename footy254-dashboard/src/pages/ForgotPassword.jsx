import { useState } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../context/AuthContext";

export default function ForgotPassword() {

  const { forgotPassword } = useAuth();

  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [submitted, setSubmitted] = useState(false);

  async function handleSubmit(event) {

    event.preventDefault();
    setError("");
    setLoading(true);

    try {

      await forgotPassword(email.trim());

      // Always show the same confirmation, whether or not the email is
      // registered — the backend intentionally doesn't reveal that either.
      setSubmitted(true);

    } catch (err) {

      setError(
        err?.detail ||
        err?.message ||
        "Something went wrong. Please try again."
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
          Reset Your Password
        </h1>
        <p className="mt-2 text-slate-400">
          Enter the email on your account and we'll send you a reset link.
        </p>

        {error && (
          <div className="mt-5 rounded-xl border border-red-500/30 bg-red-500/20 p-3 text-red-300">
            {error}
          </div>
        )}

        {submitted ? (
          <div className="mt-6 rounded-xl border border-green-500/30 bg-green-500/10 p-4 text-green-300">
            If an account exists for that email, a reset link is on its way.
            Check your inbox (and spam folder).
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="mt-6 space-y-5">
            <div>
              <label className="text-sm font-semibold text-slate-300">
                Email
              </label>
              <input
                type="email"
                name="email"
                autoComplete="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="Enter your email"
                className="mt-2 w-full rounded-xl border border-white/10 bg-turf px-4 py-3 text-white outline-none transition focus:border-signal"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-xl bg-signal py-3 font-black text-ink transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? "Sending..." : "Send Reset Link"}
            </button>
          </form>
        )}

        <p className="mt-6 text-center text-sm text-slate-400">
          Remembered your password?
          <Link
            to="/login"
            className="ml-2 font-bold text-signal hover:underline"
          >
            Back to Login
          </Link>
        </p>
      </div>
    </div>
  );
}
