// ======================================================
// FOOTY254 Prediction Service
// ======================================================

import {
    get,
    post,
} from "./api";

// ======================================================
// GET SINGLE PREDICTION
// ======================================================

export async function getPrediction(matchId) {
    return get(`/predictions/${matchId}`);
}

// ======================================================
// GET ALL PREDICTIONS
// ======================================================

export async function getPredictions() {
    const data = await get("/predictions");

    return data.predictions ?? [];
}

// ======================================================
// GENERATE NEW PREDICTIONS
// ======================================================

export async function generatePredictions() {
    return post("/predictions/generate");
}