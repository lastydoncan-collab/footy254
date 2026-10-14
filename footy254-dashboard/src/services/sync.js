// ======================================================
// FOOTY254 SYNCHRONIZATION SERVICE
// ======================================================

import {
  get,
  post,
} from "./api";

// ======================================================
// SYNCHRONIZATION STATUS
// ======================================================

export async function getSyncStatus() {

  return await get(
    "/sync/status"
  );

}

// ======================================================
// SYNCHRONIZE FIXTURES
// ======================================================

export async function syncFixtures(
  daysAhead = 7
) {

  return await post(
    `/sync/fixtures?days_ahead=${daysAhead}`
  );

}

// ======================================================
// FULL SYNCHRONIZATION
// ======================================================

export async function synchronize(
  daysAhead = 7
) {

  const status =
    await getSyncStatus();

  const fixtures =
    await syncFixtures(daysAhead);

  return {

    status,

    fixtures,

  };

}

// ======================================================
// PIPELINE HEALTH
// ======================================================

export async function getPipelineHealth() {

  const status =
    await getSyncStatus();

  return {

    running:
      status.status === "running",

    model:
      status.model,

    pipeline:
      status.pipeline,

    description:
      status.description,

  };

}

// ======================================================
// MODEL STATUS
// ======================================================

export async function getModelStatus() {

  const status =
    await getSyncStatus();

  return status.model;

}