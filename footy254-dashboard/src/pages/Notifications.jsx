import { useEffect, useState } from "react";
import { Bell, Trash2, Sparkles, Calendar } from "lucide-react";

import { useAuth } from "../context/AuthContext";
import { getPredictions, getUpcomingFixtures } from "../services";

// Dismissed notifications are tracked by a stable derived id (not stored
// notification objects) so "Clear All" / "Remove" persists across reloads
// even though the notification list itself is recomputed fresh from live
// data each time, rather than ever being fabricated.
const DISMISSED_KEY = "footy254_dismissed_notifications";

const HIGH_CONFIDENCE_THRESHOLD = 75;
const MAX_NOTIFICATIONS = 12;

function getDismissedIds() {
  try {
    const saved = localStorage.getItem(DISMISSED_KEY);
    const parsed = saved ? JSON.parse(saved) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function persistDismissedIds(ids) {
  localStorage.setItem(DISMISSED_KEY, JSON.stringify(ids));
}

function isToday(dateString) {
  if (!dateString) return false;
  const today = new Date().toISOString().split("T")[0];
  return dateString === today;
}

export default function Notifications() {
  const [notifications, setNotifications] = useState([]);

  // Read once per mount (not on every render) via a lazy initializer, and
  // use that same value to seed `loading` correctly from the start — this
  // avoids ever needing to flip `loading` to false inside an effect for
  // the "disabled" path, which would trigger an avoidable extra render.
  const { user } = useAuth();
  const notificationsEnabled = user?.notifications_enabled !== false;
  const [loading, setLoading] = useState(notificationsEnabled);

  useEffect(() => {

    if (!notificationsEnabled) {
      return;
    }

    async function load() {

      try {

        setLoading(true);

        const dismissed = new Set(getDismissedIds());
        const items = [];

        // Predictions require login + an active plan — degrade quietly if
        // unavailable rather than erroring the whole page (mirrors the
        // Live Matches page's approach to the same premium gate).
        try {

          const response = await getPredictions();

          const predictions = Array.isArray(response)
            ? response
            : response?.predictions || [];

          predictions
            .filter(
              (p) =>
                typeof p.confidence === "number" &&
                p.confidence >= HIGH_CONFIDENCE_THRESHOLD
            )
            .forEach((p) => {
              items.push({
                id: `pred-${p.match_id}`,
                icon: Sparkles,
                title: "High Confidence Pick",
                message:
                  `${p.home_team || "TBD"} vs ${p.away_team || "TBD"}: ` +
                  `${p.prediction} at ${p.confidence.toFixed(0)}% confidence.`,
                time: "AI Prediction",
              });
            });

        } catch (predictionError) {
          console.warn(
            "Notifications: predictions unavailable, showing fixture " +
            "alerts only.",
            predictionError
          );
        }

        try {

          const { fixtures } = await getUpcomingFixtures();

          fixtures
            .filter((fixture) => isToday(fixture.match_date))
            .forEach((fixture) => {
              items.push({
                id: `today-${fixture.match_id}`,
                icon: Calendar,
                title: "Match Today",
                message:
                  `${fixture.home_team || "TBD"} vs ` +
                  `${fixture.away_team || "TBD"} kicks off today.`,
                time: fixture.kickoff_time || "Today",
              });
            });

        } catch (fixtureError) {
          console.warn(
            "Notifications: fixtures unavailable.",
            fixtureError
          );
        }

        const visible = items
          .filter((item) => !dismissed.has(item.id))
          .slice(0, MAX_NOTIFICATIONS);

        setNotifications(visible);

      } finally {

        setLoading(false);

      }

    }

    load();

  }, [notificationsEnabled]);

  // ==========================================
  // CLEAR ALL
  // ==========================================

  function clearNotifications() {
    const dismissed = new Set(getDismissedIds());
    notifications.forEach((n) => dismissed.add(n.id));
    persistDismissedIds([...dismissed]);
    setNotifications([]);
  }

  // ==========================================
  // REMOVE SINGLE
  // ==========================================

  function removeNotification(id) {
    const dismissed = new Set(getDismissedIds());
    dismissed.add(id);
    persistDismissedIds([...dismissed]);

    setNotifications((previous) =>
      previous.filter((notification) => notification.id !== id)
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}

      <header className="flex items-center justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.22em] text-signal">
            Alerts
          </p>

          <h1 className="mt-2 text-3xl font-black">
            Notifications
          </h1>

          <p className="mt-2 text-slate-400">
            AI updates and important system alerts.
          </p>
        </div>

        {!loading && notificationsEnabled && notifications.length > 0 && (
          <button
            onClick={clearNotifications}
            className="flex items-center gap-2 rounded-xl bg-red-500/15 px-4 py-2 text-sm font-semibold text-red-300 transition hover:bg-red-500/25"
          >
            <Trash2 size={16} />

            Clear All
          </button>
        )}
      </header>

      {/* Loading */}

      {loading && (
        <div className="rounded-2xl border border-white/10 bg-pitch p-8 text-center">
          <Bell
            className="mx-auto mb-4 animate-pulse text-signal"
            size={34}
          />

          <p className="text-slate-300">
            Loading notifications...
          </p>
        </div>
      )}

      {/* Disabled */}

      {!loading && !notificationsEnabled && (
        <div className="rounded-[28px] border border-white/10 bg-pitch p-8 text-center">
          <Bell
            className="mx-auto mb-4 text-slate-500"
            size={36}
          />

          <h2 className="text-xl font-black">
            Notifications are turned off
          </h2>

          <p className="mt-2 text-slate-400">
            Turn them back on from Settings to see AI and match alerts here.
          </p>
        </div>
      )}

      {/* Empty */}

      {!loading && notificationsEnabled && notifications.length === 0 && (
        <div className="rounded-[28px] border border-white/10 bg-pitch p-8 text-center">
          <Bell
            className="mx-auto mb-4 text-signal"
            size={36}
          />

          <h2 className="text-xl font-black">
            You're all caught up
          </h2>

          <p className="mt-2 text-slate-400">
            New AI predictions and important updates
            will appear here.
          </p>
        </div>
      )}

      {/* Notifications */}

      {!loading && notificationsEnabled && notifications.length > 0 && (
        <div className="space-y-4">
          {notifications.map((notification) => {
            const Icon = notification.icon || Bell;

            return (
              <article
                key={notification.id}
                className="rounded-[22px] border border-white/10 bg-pitch p-5"
              >
                <div className="flex gap-4">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-signal/15 text-signal">
                    <Icon size={18} />
                  </div>

                  <div className="flex-1">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <h2 className="font-black">
                          {notification.title}
                        </h2>

                        <p className="mt-2 text-sm leading-6 text-slate-400">
                          {notification.message}
                        </p>
                      </div>

                      <span className="text-xs text-slate-500 whitespace-nowrap">
                        {notification.time}
                      </span>
                    </div>

                    <button
                      onClick={() =>
                        removeNotification(
                          notification.id
                        )
                      }
                      className="mt-4 text-sm font-semibold text-red-400 transition hover:text-red-300"
                    >
                      Remove
                    </button>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
