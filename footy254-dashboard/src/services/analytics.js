// ======================================================
// FOOTY254 ANALYTICS SERVICE
// ======================================================

import { getPredictions } from "./predictions";
import { loadDashboard } from "./dashboard";
import { getSyncStatus } from "./sync";

// ======================================================
// LOAD ANALYTICS
// ======================================================

export async function loadAnalytics() {
  try {
    // Predictions are a premium endpoint: a free user gets 403. That must not
    // blank the whole page, so only the dashboard counts are required.
    const [
      dashboard,
      predictionsResult,
    ] = await Promise.all([
      loadDashboard(),
      getPredictions().catch(() => []),
    ]);

    const predictions = Array.isArray(predictionsResult)
      ? predictionsResult
      : [];

    const predictionCount =
      predictions?.length ?? 0;

    const averageConfidence =
      predictionCount > 0
        ? (
            predictions.reduce(
              (sum, prediction) =>
                sum +
                Number(
                  prediction.confidence ?? 0
                ),
              0
            ) / predictionCount
          ).toFixed(1)
        : "0.0";

    return [
      {
        title: "Teams",
        value: dashboard.totalTeams,
        subtitle: "Loaded",
        color: "#1fe6ad",
      },

      {
        title: "Fixtures",
        value: dashboard.totalFixtures,
        subtitle: "Upcoming",
        color: "#38bdf8",
      },

      {
        title: "Predictions",
        value: predictionCount,
        subtitle: "Generated",
        color: "#f7c948",
      },

      {
        title: "Confidence",
        value: `${averageConfidence}%`,
        subtitle: "Average AI",
        color: "#fb7185",
      },
    ];
  } catch (error) {
    console.error(
      "Analytics loading failed:",
      error
    );

    return [
      {
        title: "Teams",
        value: "--",
        subtitle: "Unavailable",
        color: "#1fe6ad",
      },

      {
        title: "Fixtures",
        value: "--",
        subtitle: "Unavailable",
        color: "#38bdf8",
      },

      {
        title: "Predictions",
        value: "--",
        subtitle: "Unavailable",
        color: "#f7c948",
      },

      {
        title: "Confidence",
        value: "--",
        subtitle: "Unavailable",
        color: "#fb7185",
      },
    ];
  }
}

// ======================================================
// ENGINE STATUS
// ======================================================

export async function loadEngineStatus() {
  try {
    const sync =
      await getSyncStatus();

    // The backend reports model artifacts as {name: true/false} and the
    // pipeline as {feature: true/false}; "ready" means every flag is true.
    const allTrue = (flags) =>
      !!flags &&
      typeof flags === "object" &&
      Object.values(flags).length > 0 &&
      Object.values(flags).every(Boolean);

    const modelReady = allTrue(sync.model);

    const pipelineReady = allTrue(sync.pipeline);

    return [
      {
        label: "Backend",
        value:
          sync.status === "running"
            ? "Online"
            : sync.status ?? "Unknown",

        progress:
          sync.status === "running" || sync.status === "ONLINE"
            ? 100
            : 50,

        color: "bg-[#1fe6ad]",
      },

      {
        label: "Prediction Model",
        value:
          modelReady ? "Ready" : "Incomplete",

        progress:
          modelReady
            ? 100
            : 50,

        color: "bg-[#38bdf8]",
      },

      {
        label: "Pipeline",
        value:
          pipelineReady ? "Ready" : "Unknown",

        progress:
          pipelineReady
            ? 100
            : 50,

        color: "bg-[#f7c948]",
      },
    ];
  } catch (error) {
    console.error(error);

    return [
      {
        label: "Backend",
        value: "Offline",
        progress: 0,
        color: "bg-red-500",
      },

      {
        label: "Prediction Model",
        value: "Offline",
        progress: 0,
        color: "bg-red-500",
      },

      {
        label: "Pipeline",
        value: "Offline",
        progress: 0,
        color: "bg-red-500",
      },
    ];
  }
}

// ======================================================
// QUICK SUMMARY
// ======================================================

export async function getAnalyticsSummary() {
  const dashboard =
    await loadDashboard();

  const predictions =
    await getPredictions();

  return {
    teams:
      dashboard.totalTeams,

    fixtures:
      dashboard.totalFixtures,

    live:
      dashboard.liveMatches,

    today:
      dashboard.todaysMatches,

    predictions:
      predictions.length,
  };
}
