import { useState } from "react";
import { ShieldCheck } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import {
  startTwoFactorSetup,
  enableTwoFactor,
  disableTwoFactor,
} from "../services";

// Two-factor enrolment with any authenticator app (Google Authenticator,
// Microsoft Authenticator, Authy, ...). Everything here talks to the backend;
// nothing is stored in the browser.
export default function TwoFactorCard() {
  const { user, refreshUser } = useAuth();
  const enabled = !!user?.two_factor_enabled;

  const [step, setStep] = useState("idle"); // idle | password | scan | codes | disable
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [setup, setSetup] = useState(null);
  const [recoveryCodes, setRecoveryCodes] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  function reset() {
    setStep("idle");
    setPassword("");
    setCode("");
    setSetup(null);
    setError("");
  }

  async function run(action) {
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (err) {
      setError(err?.message || "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  const begin = (e) => {
    e.preventDefault();
    run(async () => {
      setSetup(await startTwoFactorSetup(password));
      setPassword("");
      setStep("scan");
    });
  };

  const confirm = (e) => {
    e.preventDefault();
    run(async () => {
      const result = await enableTwoFactor(code.trim());
      setRecoveryCodes(result.recovery_codes || []);
      setStep("codes");
      setCode("");
      setSetup(null);
      await refreshUser();
    });
  };

  const turnOff = (e) => {
    e.preventDefault();
    run(async () => {
      await disableTwoFactor(password, code.trim());
      setMessage("Two-factor authentication is off.");
      reset();
      await refreshUser();
    });
  };

  return (
    <section className="rounded-[24px] border border-white/10 bg-pitch p-5">
      <div className="flex items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <ShieldCheck size={18} />
            <h3 className="font-black">Two-Factor Authentication</h3>
          </div>
          <p className="mt-2 text-sm text-slate-400">
            {enabled
              ? "On. You'll enter a code from your authenticator app each time you sign in."
              : "Add a second step at sign-in using an authenticator app."}
          </p>
        </div>

        {step === "idle" && (
          <button
            type="button"
            onClick={() => {
              setMessage("");
              setStep(enabled ? "disable" : "password");
            }}
            className={`shrink-0 rounded-xl px-4 py-2 font-black ${
              enabled ? "bg-signal text-ink" : "bg-white/10"
            }`}
          >
            {enabled ? "ON" : "OFF"}
          </button>
        )}
      </div>

      {message && step === "idle" && (
        <p className="mt-3 text-sm text-green-300">{message}</p>
      )}

      {error && <p className="mt-3 text-sm text-red-300">{error}</p>}

      {step === "password" && (
        <form onSubmit={begin} className="mt-4 space-y-3">
          <p className="text-sm text-slate-300">
            Confirm your password to start.
          </p>
          <input
            type="password"
            required
            autoComplete="current-password"
            placeholder="Your password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-xl px-4 py-3 outline-none"
          />
          <div className="flex gap-3">
            <button
              disabled={busy}
              className="rounded-xl bg-signal px-4 py-2 font-black text-ink disabled:opacity-50"
            >
              {busy ? "Checking..." : "Continue"}
            </button>
            <button type="button" onClick={reset} className="text-sm text-slate-400">
              Cancel
            </button>
          </div>
        </form>
      )}

      {step === "scan" && setup && (
        <form onSubmit={confirm} className="mt-4 space-y-3">
          <p className="text-sm text-slate-300">
            1. In your authenticator app choose “Add account” and enter this key
            (or tap the link on your phone):
          </p>
          <code className="block break-all rounded-xl bg-ink px-4 py-3 text-sm tracking-wider text-chalk">
            {setup.secret}
          </code>
          <a
            href={setup.otpauth_uri}
            className="inline-block text-sm font-semibold text-signal hover:underline"
          >
            Open in authenticator app
          </a>
          <p className="text-sm text-slate-300">
            2. Enter the 6-digit code the app shows:
          </p>
          <input
            inputMode="numeric"
            autoComplete="one-time-code"
            required
            placeholder="123456"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            className="w-full rounded-xl px-4 py-3 text-center text-lg tracking-widest outline-none"
          />
          <div className="flex gap-3">
            <button
              disabled={busy}
              className="rounded-xl bg-signal px-4 py-2 font-black text-ink disabled:opacity-50"
            >
              {busy ? "Verifying..." : "Turn on"}
            </button>
            <button type="button" onClick={reset} className="text-sm text-slate-400">
              Cancel
            </button>
          </div>
        </form>
      )}

      {step === "codes" && (
        <div className="mt-4 space-y-3">
          <p className="text-sm font-bold text-green-300">
            Two-factor authentication is on.
          </p>
          <p className="text-sm text-slate-300">
            Save these recovery codes somewhere safe. Each works once if you lose
            your phone. They won't be shown again.
          </p>
          <div className="grid grid-cols-2 gap-2 rounded-xl bg-ink p-4 font-mono text-sm text-chalk">
            {recoveryCodes.map((c) => (
              <span key={c}>{c}</span>
            ))}
          </div>
          <button
            type="button"
            onClick={() => {
              setRecoveryCodes([]);
              reset();
            }}
            className="rounded-xl bg-signal px-4 py-2 font-black text-ink"
          >
            I've saved them
          </button>
        </div>
      )}

      {step === "disable" && (
        <form onSubmit={turnOff} className="mt-4 space-y-3">
          <p className="text-sm text-slate-300">
            To turn it off, confirm your password and a current code (or a
            recovery code).
          </p>
          <input
            type="password"
            required
            autoComplete="current-password"
            placeholder="Your password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-xl px-4 py-3 outline-none"
          />
          <input
            required
            autoComplete="one-time-code"
            placeholder="Authenticator or recovery code"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            className="w-full rounded-xl px-4 py-3 outline-none"
          />
          <div className="flex gap-3">
            <button
              disabled={busy}
              className="rounded-xl bg-red-600 px-4 py-2 font-black disabled:opacity-50"
            >
              {busy ? "Turning off..." : "Turn off"}
            </button>
            <button type="button" onClick={reset} className="text-sm text-slate-400">
              Cancel
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
