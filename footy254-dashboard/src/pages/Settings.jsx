import { useState } from "react";
import { Check } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { updateProfile, updatePreferences } from "../services";

const LEAGUES = [
  "All Leagues",
  "Premier League",
  "La Liga",
  "Serie A",
  "Bundesliga",
  "Ligue 1",
  "Champions League",
];

function Toggle({ label, hint, checked, onChange, disabled }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-[24px] border border-white/10 bg-pitch p-4">
      <div>
        <h2 className="font-black">{label}</h2>
        <p className="mt-1 text-sm text-slate-400">{hint}</p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={`min-h-11 shrink-0 rounded-2xl px-5 text-sm font-black disabled:opacity-50 ${
          checked ? "bg-signal text-ink" : "bg-white/10 text-white"
        }`}
      >
        {checked ? "ON" : "OFF"}
      </button>
    </div>
  );
}

export default function Settings() {
  const { user, setUser } = useAuth();

  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({
    first_name: user?.first_name || "",
    last_name: user?.last_name || "",
    username: user?.username || "",
    phone_number: user?.phone_number || "",
  });
  const [profileBusy, setProfileBusy] = useState(false);
  const [profileError, setProfileError] = useState("");
  const [profileSaved, setProfileSaved] = useState(false);

  const [prefError, setPrefError] = useState("");
  const [prefSaving, setPrefSaving] = useState(false);

  const prefs = {
    notifications_enabled: user?.notifications_enabled !== false,
    match_alerts: user?.match_alerts !== false,
    login_alerts: user?.login_alerts !== false,
    favorite_league: user?.favorite_league || "All Leagues",
    refresh_rate_seconds: user?.refresh_rate_seconds || 30,
  };

  async function savePrefs(change) {
    setPrefError("");
    setPrefSaving(true);
    try {
      const response = await updatePreferences({ ...prefs, ...change });
      setUser(response.user);
    } catch (error) {
      setPrefError(error.message || "Couldn't save that setting.");
    } finally {
      setPrefSaving(false);
    }
  }

  async function saveProfile(event) {
    event.preventDefault();
    setProfileError("");
    setProfileSaved(false);
    setProfileBusy(true);
    try {
      const response = await updateProfile({
        ...form,
        phone_number: form.phone_number.trim() || null,
      });
      setUser(response.user);
      setProfileSaved(true);
      setEditing(false);
    } catch (error) {
      setProfileError(error.message || "Couldn't update your profile.");
    } finally {
      setProfileBusy(false);
    }
  }

  const field = (name, label, props = {}) => (
    <div>
      <label htmlFor={name} className="text-xs text-slate-400">
        {label}
      </label>
      <input
        id={name}
        value={form[name]}
        onChange={(e) => setForm({ ...form, [name]: e.target.value })}
        className="mt-1 w-full rounded-xl px-4 py-3 outline-none"
        {...props}
      />
    </div>
  );

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-3xl font-black">Settings</h1>
        <p className="mt-2 text-slate-400">
          Your profile and how FOOTY254 works for you. Changes are saved to your
          account and follow you to every device.
        </p>
      </header>

      <section className="rounded-[24px] border border-white/10 bg-pitch p-5">
        <h2 className="mb-4 text-lg font-black">Profile</h2>

        {editing ? (
          <form onSubmit={saveProfile} className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2">
              {field("first_name", "First name", { required: true, maxLength: 100 })}
              {field("last_name", "Last name", { required: true, maxLength: 100 })}
              {field("username", "Username", {
                required: true,
                minLength: 3,
                maxLength: 30,
                autoComplete: "username",
              })}
              {field("phone_number", "Phone (optional)", {
                type: "tel",
                autoComplete: "tel",
                placeholder: "0712345678",
              })}
            </div>

            <p className="text-xs text-slate-400">
              Your email ({user?.email}) can't be changed here.
            </p>

            {profileError && <p className="text-sm text-red-300">{profileError}</p>}

            <div className="flex gap-3">
              <button
                disabled={profileBusy}
                className="rounded-2xl bg-signal px-5 py-3 font-black text-ink disabled:opacity-50"
              >
                {profileBusy ? "Saving..." : "Save changes"}
              </button>
              <button
                type="button"
                onClick={() => {
                  setEditing(false);
                  setProfileError("");
                }}
                className="rounded-2xl bg-white/10 px-5 py-3 font-bold"
              >
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <div className="space-y-4">
            {[
              ["Name", `${user?.first_name ?? ""} ${user?.last_name ?? ""}`.trim() || "-"],
              ["Username", user?.username ?? "-"],
              ["Email", user?.email ?? "-"],
              ["Phone", user?.phone_number || "Not added"],
            ].map(([label, value]) => (
              <div key={label}>
                <p className="text-xs text-slate-400">{label}</p>
                <p className="mt-1 break-all font-semibold">{value}</p>
              </div>
            ))}

            {profileSaved && (
              <p className="flex items-center gap-1.5 text-sm text-green-300">
                <Check size={14} /> Profile updated.
              </p>
            )}

            <button
              type="button"
              onClick={() => {
                setForm({
                  first_name: user?.first_name || "",
                  last_name: user?.last_name || "",
                  username: user?.username || "",
                  phone_number: user?.phone_number || "",
                });
                setProfileSaved(false);
                setEditing(true);
              }}
              className="rounded-2xl bg-signal px-5 py-3 font-black text-ink"
            >
              Edit profile
            </button>
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-black">Preferences</h2>

        {prefError && <p className="text-sm text-red-300">{prefError}</p>}

        <label className="block rounded-[24px] border border-white/10 bg-pitch p-4">
          <span className="text-base font-black">Prediction refresh</span>
          <select
            value={prefs.refresh_rate_seconds}
            disabled={prefSaving}
            onChange={(e) => savePrefs({ refresh_rate_seconds: Number(e.target.value) })}
            className="mt-3 min-h-12 w-full rounded-2xl px-4"
          >
            <option value={15}>Every 15 seconds</option>
            <option value={30}>Every 30 seconds</option>
            <option value={60}>Every minute</option>
          </select>
        </label>

        <label className="block rounded-[24px] border border-white/10 bg-pitch p-4">
          <span className="text-base font-black">Favourite league</span>
          <select
            value={prefs.favorite_league}
            disabled={prefSaving}
            onChange={(e) => savePrefs({ favorite_league: e.target.value })}
            className="mt-3 min-h-12 w-full rounded-2xl px-4"
          >
            {LEAGUES.map((league) => (
              <option key={league}>{league}</option>
            ))}
          </select>
          <p className="mt-2 text-xs text-slate-400">
            Predict and Live show this league first.
          </p>
        </label>

        <Toggle
          label="Notifications"
          hint="Show the notifications page and bell."
          checked={prefs.notifications_enabled}
          disabled={prefSaving}
          onChange={(v) => savePrefs({ notifications_enabled: v })}
        />

        <Toggle
          label="Match alerts"
          hint="Kick-off and result alerts for your saved matches."
          checked={prefs.match_alerts}
          disabled={prefSaving || !prefs.notifications_enabled}
          onChange={(v) => savePrefs({ match_alerts: v })}
        />

        <Toggle
          label="Sign-in alerts"
          hint="Email me when a new device signs in."
          checked={prefs.login_alerts}
          disabled={prefSaving}
          onChange={(v) => savePrefs({ login_alerts: v })}
        />
      </section>
    </div>
  );
}
