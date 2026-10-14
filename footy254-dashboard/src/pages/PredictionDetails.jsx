import { useEffect, useState } from "react";

import {
  useNavigate,
  useParams,
} from "react-router-dom";

import {
  ArrowLeft,
  Calendar,
  Clock,
  Trophy,
  Target,
  Heart,
} from "lucide-react";

import {
    getPrediction,
} from "../services";

import { isFavorite, toggleFavorite, subscribeFavorites } from "../utils/favorites";

export default function PredictionDetails() {

  const { matchId } = useParams();

  const navigate = useNavigate();

  const [prediction, setPrediction] = useState(null);

  const [loading, setLoading] = useState(true);

  const [error, setError] = useState("");

  const [saved, setSaved] = useState(() => isFavorite(matchId));

  useEffect(() => {
    return subscribeFavorites(() => {
      setSaved(isFavorite(matchId));
    });
  }, [matchId]);

  useEffect(() => {

    async function loadPrediction() {

      try {

        setLoading(true);

        const data = await getPrediction(matchId);

        setPrediction(data);

      } catch (err) {

      console.error(err);

      const status = err?.status;

      if (status === 401) {

        setError("LOGIN_REQUIRED");

      } else if (status === 403) {

        setError("PREMIUM_REQUIRED");

      } else {

        setError(
          err.message || "Prediction could not be loaded."
        );

      }

    } finally {

        setLoading(false);

      }

    }

    loadPrediction();

  }, [matchId]);

  if (loading) {

    return (

      <div className="p-10 text-center">

        Loading prediction...

      </div>

    );

  }

  if (!loading && error === "LOGIN_REQUIRED") {

    return (

      <div className="space-y-5">

        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-2"
        >
          <ArrowLeft size={18} />
          Back
        </button>

        <div className="rounded-2xl border border-yellow-500/30 bg-yellow-500/10 p-8 text-center">

          <h2 className="text-2xl font-black text-yellow-300">

            Login Required

          </h2>

          <p className="mt-3 text-slate-300">

            Please log in to view this prediction.

          </p>

        </div>

      </div>

    );

  }

  if (!loading && error === "PREMIUM_REQUIRED") {

    return (

      <div className="space-y-5">

        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-2"
        >
          <ArrowLeft size={18} />
          Back
        </button>

        <div className="rounded-2xl border border-signal/30 bg-signal/10 p-8 text-center">

          <h2 className="text-3xl font-black text-signal">

            FOOTY254 Premium

          </h2>

          <p className="mt-4 text-slate-300">

            Detailed AI predictions are available only to Premium subscribers.

          </p>

          <div className="mt-6 space-y-2 text-left inline-block">

            <p>✔ Full Match Prediction</p>

            <p>✔ Win Probabilities</p>

            <p>✔ Expected Goals (xG)</p>

            <p>✔ Confidence Score</p>

            <p>✔ Premium Match Analytics</p>

          </div>

          <button
          onClick={() => navigate("/subscriptions")}
          disabled={loading}
           
           className="mt-8 rounded-xl bg-signal px-8 py-3 font-black text-ink hover:opacity-90">

            Upgrade to Premium

          </button>

        </div>

      </div>

    );

  }

  if (!loading && (error || !prediction)) {

    return (

      <div className="space-y-5">

        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-2"
        >
          <ArrowLeft size={18} />
          Back
        </button>

        <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-6 text-red-300">

          {error || "Prediction not found."}

        </div>

      </div>

    );

  }

  const kickoff =
    prediction.kickoff
        ? new Date(prediction.kickoff)
        : null;

  return (

    <div className="space-y-6">

      <button

        onClick={() => navigate(-1)}

        className="flex items-center gap-2 text-slate-300 hover:text-white"

      >

        <ArrowLeft size={18} />

        Back

      </button>

      <section className="rounded-[30px] border border-white/10 bg-pitch p-6 shadow-xl">

        <div className="flex items-center justify-between">

          <div className="flex items-center gap-2 text-signal">

            <Trophy size={18} />

            <span className="font-bold">

              {prediction.competition}

            </span>

          </div>

          <button
            type="button"
            onClick={() =>
              toggleFavorite({ ...prediction, match_id: matchId })
            }
            aria-label={saved ? "Remove from saved" : "Save prediction"}
            aria-pressed={saved}
            className={`rounded-full p-2 transition ${
              saved
                ? "bg-red-500/15 text-red-400 hover:bg-red-500/25"
                : "bg-turf text-slate-400 hover:text-red-400"
            }`}
          >
            <Heart size={18} fill={saved ? "currentColor" : "none"} />
          </button>

        </div>

        <h1 className="mt-5 text-3xl font-black">

          {prediction.home_team}

        </h1>

        <div className="my-2 text-center text-slate-500">

          VS

        </div>

        <h1 className="text-3xl font-black">

          {prediction.away_team}

        </h1>

        <div className="mt-6 grid grid-cols-2 gap-4">

          <div className="rounded-xl bg-turf p-4">

            <div className="mb-2 flex items-center gap-2 text-sm text-slate-400">

              <Calendar size={16} />

              Date

            </div>

            <div className="font-bold">

              {kickoff
                  ? kickoff.toLocaleDateString()
                  : "--"}

            </div>

          </div>

          <div className="rounded-xl bg-turf p-4">

            <div className="mb-2 flex items-center gap-2 text-sm text-slate-400">

              <Clock size={16} />

              Kickoff

            </div>

            <div className="font-bold">

            {kickoff
                ? kickoff.toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                  })
                : "--"}

            </div>

          </div>

        </div>

      </section>

      <section className="rounded-[30px] border border-white/10 bg-pitch p-6">

        <div className="flex items-center gap-2">

          <Target size={18} />

          <h2 className="text-xl font-black">

            AI Prediction

          </h2>

        </div>

        <div className="mt-5 rounded-2xl bg-turf p-5 text-center">

          <div className="text-2xl font-black text-signal">

            {prediction.prediction}

          </div>

          <div className="mt-2 text-slate-400">

            Confidence

          </div>

          <div className="text-4xl font-black">

            {prediction.confidence?.toFixed(1)}%

          </div>

        </div>

      </section>

      <section className="grid grid-cols-3 gap-4">

        <div className="rounded-2xl bg-pitch p-5 text-center">

          <div className="text-slate-400">

            Home

          </div>

          <div className="mt-2 text-2xl font-black">

            {prediction.home_win_probability?.toFixed(1)}%

          </div>

        </div>

        <div className="rounded-2xl bg-pitch p-5 text-center">

          <div className="text-slate-400">

            Draw

          </div>

          <div className="mt-2 text-2xl font-black">

            {prediction.draw_probability?.toFixed(1)}%

          </div>

        </div>

        <div className="rounded-2xl bg-pitch p-5 text-center">

          <div className="text-slate-400">

            Away

          </div>

          <div className="mt-2 text-2xl font-black">

            {prediction.away_win_probability?.toFixed(1)}%

          </div>

        </div>

      </section>

      <section className="grid grid-cols-2 gap-4">

        <div className="rounded-2xl bg-pitch p-5 text-center">

          <div className="text-slate-400">

            Home xG

          </div>

          <div className="mt-2 text-3xl font-black">

            {prediction.expected_home_goals?.toFixed(2)}

          </div>

        </div>

        <div className="rounded-2xl bg-pitch p-5 text-center">

          <div className="text-slate-400">

            Away xG

          </div>

          <div className="mt-2 text-3xl font-black">

            {prediction.expected_away_goals?.toFixed(2)}

          </div>

        </div>

      </section>

      <section className="rounded-2xl bg-pitch p-5">

        <div className="flex justify-between">

          <span>Status</span>

          <span className="font-bold text-signal">

            {prediction.status}

          </span>

        </div>

        <div className="mt-4 flex justify-between">

          <span>Stage</span>

          <span className="font-bold">

            {prediction.stage}

          </span>

        </div>

      </section>

    </div>

  );

}