import {
    useEffect,
    useState,
} from "react";

import {
    useNavigate,
} from "react-router-dom";

import {
    getMySubscription,
    getSubscriptionPlans,
    cancelSubscription,
} from "../services/subscriptions";

import {
  Crown,
  Check,
  ShieldCheck,
} from "lucide-react";

function formatExpiry(value) {
  if (!value) return null;

  try {
    return new Date(value).toLocaleDateString(undefined, {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  } catch {
    return null;
  }
}

export default function Subscriptions() {
  const navigate = useNavigate();

  const [subscription, setSubscription] = useState({
    plan: "FREE",
    status: "FREE",
    is_active: false,
});

  const [loading, setLoading] = useState(true);

  const [plans, setPlans] = useState([]);

  const [cancelling, setCancelling] = useState(false);

  const [cancelError, setCancelError] = useState("");

  useEffect(() => {

      async function loadSubscription() {

          try {

                const [
                    subscriptionResponse,
                    plans,
                ] = await Promise.all([
                    getMySubscription(),
                    getSubscriptionPlans(),
                ]);

                setSubscription(
                    subscriptionResponse ?? {
                        plan: "FREE",
                        status: "FREE",
                        is_active: false,
                    }
                );

                setPlans(plans)

          }

          catch {

              try {

                  const plans = await getSubscriptionPlans();

                  setPlans(plans);

              }

              catch {

                  setPlans([]);

              }

              setSubscription({

                  plan: "FREE",

                  status: "FREE",

              });

          }

          finally {

              setLoading(false);

          }

      }

      loadSubscription();

  }, []);

  const features = [
    "AI Match Predictions",
    "Win Probabilities",
    "Expected Goals (xG)",
    "Confidence Scores",
    "Premium Analytics",
    "Future Premium Features",
  ];

  async function handleCancel() {

    if (
      !window.confirm(
        "Cancel your premium subscription? You'll lose access to premium " +
        "features immediately and this can't be undone."
      )
    ) {
      return;
    }

    try {
      setCancelling(true);
      setCancelError("");
      await cancelSubscription();
      setSubscription((previous) => ({
        ...previous,
        status: "EXPIRED",
        is_active: false,
      }));
    } catch (error) {
      setCancelError(error.message || "Unable to cancel subscription.");
    } finally {
      setCancelling(false);
    }

  }

  if (loading) {

    return (

        <div className="p-8">

            Loading subscription...

        </div>

    );

}

  return (
    <div className="space-y-8">

      {/* Hero */}

      <section className="rounded-3xl bg-gradient-to-r from-turf to-line p-8">

        <div className="flex items-center gap-3">

          <Crown
            className="text-signal"
            size={34}
          />

          <div>

            <h1 className="text-3xl font-black">

              FOOTY254 Premium

            </h1>

            <p className="mt-2 text-slate-300">

              Unlock AI-powered football predictions,
              win probabilities,
              expected goals,
              and premium analytics.

            </p>

          </div>

        </div>

      </section>

      {/* Current Plan */}

      <section className="rounded-3xl border border-white/10 bg-pitch p-6">

        <h2 className="text-xl font-black">

          Current Subscription

        </h2>

        {subscription?.is_active ? (

          <div className="mt-5">

            <span className="rounded-full bg-signal px-4 py-2 font-bold text-ink">

              PREMIUM · {subscription.plan}

            </span>

            {formatExpiry(subscription.expires_at) && (
              <p className="mt-4 text-slate-400">
                Renews/expires on {formatExpiry(subscription.expires_at)}.
              </p>
            )}

            {cancelError && (
              <p className="mt-3 text-sm text-red-300">{cancelError}</p>
            )}

            <button
              onClick={handleCancel}
              disabled={cancelling}
              className="mt-4 text-sm font-bold text-red-300 hover:underline disabled:opacity-50"
            >
              {cancelling ? "Cancelling..." : "Cancel Subscription"}
            </button>

          </div>

        ) : (

          <div className="mt-5">

            <span className="rounded-full bg-signal px-4 py-2 font-bold text-ink">

              FREE

            </span>

            <p className="mt-4 text-slate-400">

              {subscription?.plan && subscription.plan !== "FREE"
                ? "Your premium subscription has expired. Renew to keep access."
                : "Upgrade to unlock all premium features."}

            </p>

          </div>

        )}

      </section>

      {/* Plans */}

      <section>

        <h2 className="mb-5 text-2xl font-black">

          Choose Your Plan

        </h2>

        <div className="grid gap-6 md:grid-cols-3">

          {plans.map(plan => (

            <div
              key={plan.id}
              className="rounded-3xl border border-white/10 bg-pitch p-6"
            >

              {plan.badge && (

                <div className="mb-4 inline-block rounded-full bg-signal px-3 py-1 text-sm font-bold text-ink">

                  {plan.badge}

                </div>

              )}

              <h3 className="text-2xl font-black">

                {plan.name}

              </h3>

              <div className="mt-4 text-4xl font-black text-signal">

                {plan.currency} {plan.price}

              </div>

              <p className="mt-2 text-slate-400">

                {plan.duration_days} Days

              </p>

              <div className="mt-6 space-y-2">

                {features.map(feature => (

                  <div
                    key={feature}
                    className="flex items-center gap-2"
                  >

                    <Check
                      size={18}
                      className="text-signal"
                    />

                    {feature}

                  </div>

                ))}

              </div>

              <button
                className="mt-8 w-full rounded-xl bg-signal py-3 font-black text-ink hover:opacity-90"
                onClick={() =>
                  navigate(`/subscription/checkout/${plan.id}`)
                }
              >

                Choose Plan

              </button>

            </div>

          ))}

        </div>

      </section>

      {/* Comparison */}

      <section className="rounded-3xl border border-white/10 bg-pitch p-6">

        <div className="flex items-center gap-2">

          <ShieldCheck className="text-signal" />

          <h2 className="text-xl font-black">

            Premium Benefits

          </h2>

        </div>

        <div className="mt-6 overflow-auto">

          <table className="w-full">

            <thead>

              <tr className="border-b border-white/10">

                <th className="py-3 text-left">Feature</th>
                <th>Free</th>
                <th>Premium</th>

              </tr>

            </thead>

            <tbody>

              <tr>

                <td className="py-3">Fixtures</td>

                <td>✅</td>

                <td>✅</td>

              </tr>

              <tr>

                <td className="py-3">AI Predictions</td>

                <td>❌</td>

                <td>✅</td>

              </tr>

              <tr>

                <td className="py-3">Expected Goals</td>

                <td>❌</td>

                <td>✅</td>

              </tr>

              <tr>

                <td className="py-3">Confidence Scores</td>

                <td>❌</td>

                <td>✅</td>

              </tr>

              <tr>

                <td className="py-3">Premium Analytics</td>

                <td>❌</td>

                <td>✅</td>

              </tr>

            </tbody>

          </table>

        </div>

      </section>

    </div>
  );
}
