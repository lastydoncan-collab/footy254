import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import {
  ArrowLeft,
  CheckCircle2,
  CreditCard,
  ShieldCheck,
  Smartphone,
} from "lucide-react";

import {
    getSubscriptionPlans,
    startMpesaPayment,
    getCheckoutStatus,
} from "../services/subscriptions";
import { getCardStatus, startCardCheckout } from "../services/account";

const FEATURES = [
  "AI Match Predictions",
  "Win Probabilities",
  "Expected Goals (xG)",
  "Confidence Scores",
  "Premium Analytics",
  "Future Premium Features",
];

// STK push prompts on the phone time out on their own after roughly 60-90
// seconds. Polling forever past that just leaves the UI stuck "waiting"
// with no useful signal, so we give up and tell the user what to do.
const POLL_INTERVAL_MS = 3000;
const POLL_TIMEOUT_MS = 90000;

// A normalized Kenyan mobile number is 254 followed by 9 digits starting
// with 7 or 1 (Safaricom's ranges) — mirrors the backend's validation so
// obviously-bad numbers are caught before burning an STK push attempt.
function isValidKenyanPhone(value) {
  const digits = value.replace(/[^\d+]/g, "");

  let normalized = digits;

  if (normalized.startsWith("+254")) {
    normalized = normalized.slice(1);
  } else if (normalized.startsWith("0")) {
    normalized = "254" + normalized.slice(1);
  } else if (normalized.startsWith("7") || normalized.startsWith("1")) {
    normalized = "254" + normalized;
  }

  return (
    normalized.length === 12 &&
    normalized.startsWith("254") &&
    /^[71]/.test(normalized[3]) &&
    /^\d+$/.test(normalized)
  );
}

export default function SubscriptionCheckout() {

    const navigate = useNavigate();

    const { planId } = useParams();

    const [plans, setPlans] = useState([]);

    const [paymentMethod, setPaymentMethod] =
        useState("MPESA");

    const [cardEnabled, setCardEnabled] = useState(false);

    useEffect(() => {
      getCardStatus()
        .then((r) => setCardEnabled(!!r.enabled))
        .catch(() => setCardEnabled(false));
    }, []);

    const [phone, setPhone] =
        useState("");

    const [loading, setLoading] =
        useState(false);

    const [error, setError] =
        useState("");

    const [message, setMessage] =
        useState("");

    const [checkoutRequestId, setCheckoutRequestId] =
        useState(null);

    // True while an STK push is out and we're waiting on the callback --
    // this is what actually blocks a second, duplicate push, not `loading`
    // (which only covers the initial request/response round trip).
    const [awaitingConfirmation, setAwaitingConfirmation] =
        useState(false);

    const pollingRef = useRef(null);
    const pollTimeoutRef = useRef(null);

    useEffect(() => {

        async function loadPlans() {

            try {

                const plans =
                    await getSubscriptionPlans();

                setPlans(plans);

            } catch (err) {

                console.error(err);

            }

        }

        loadPlans();

    }, []);

    const plan = useMemo(() => {

        return plans.find(
            (p) => p.id === planId
        );

    }, [plans, planId]);

    useEffect(() => {

        return () => {

            stopPolling();

        };

    }, []);

  //--------------------------------------------------------
  // STOP POLLING
  //--------------------------------------------------------

  function stopPolling() {

    if (pollingRef.current) {

      clearInterval(
        pollingRef.current
      );

      pollingRef.current = null;
    }

    if (pollTimeoutRef.current) {

      clearTimeout(pollTimeoutRef.current);

      pollTimeoutRef.current = null;
    }
  }

  //--------------------------------------------------------
  // START POLLING
  //--------------------------------------------------------

  function startPolling(
    checkoutId,
  ) {

    stopPolling();

    pollingRef.current = setInterval(
      async () => {

        try {

          const status =
            await getCheckoutStatus(
              checkoutId,
            );

          if (
            status.status ===
            "ACTIVE"
          ) {

            stopPolling();

            setAwaitingConfirmation(false);

            setMessage(
              "Payment received successfully."
            );

            setTimeout(() => {

              navigate(
                "/predictions",
              );

            }, 1500);
          }

          if (
            status.status ===
            "EXPIRED" ||
            status.status ===
            "FAILED"
          ) {

            stopPolling();

            setAwaitingConfirmation(false);

            setError(
              "Payment was not completed. You can try again below."
            );
          }

        } catch (err) {

          console.error(err);

        }

      },

      POLL_INTERVAL_MS,
    );

    // Give up after POLL_TIMEOUT_MS rather than polling indefinitely if the
    // user never approves (or ignores) the STK prompt on their phone.
    pollTimeoutRef.current = setTimeout(() => {

      stopPolling();

      setAwaitingConfirmation(false);

      setError(
        "We didn't receive confirmation in time. " +
        "Check your phone for the M-Pesa prompt, or try again."
      );

    }, POLL_TIMEOUT_MS);
  }

  //--------------------------------------------------------
  // CHECKOUT
  //--------------------------------------------------------

  async function handleCheckout() {

    setError("");

    setMessage("");

    if (awaitingConfirmation) {

      // A push is already out — the DB-level duplicate check on the
      // backend would catch this too, but heading it off here avoids
      // burning a second STK prompt on the user's phone for no reason.
      return;

    }

    if (paymentMethod === "CARD") {

      try {

        setLoading(true);

        const result = await startCardCheckout(plan.id);

        // Card details are entered on the payment provider's secure page,
        // never on this site.
        window.location.assign(result.authorization_url);

      } catch (err) {

        setError(
          err?.message ||
          "We couldn't start the card payment. Please try again."
        );

        setLoading(false);

      }

      return;

    }

    if (!phone.trim()) {

      setError(
        "Please enter your M-Pesa phone number."
      );

      return;
    }

    if (!isValidKenyanPhone(phone)) {

      setError(
        "Enter a valid Safaricom number, e.g. 0712345678 or 254712345678."
      );

      return;
    }

    try {

      setLoading(true);

      const response =
        await startMpesaPayment({

          plan: plan.id,

          payment_method:
            paymentMethod,

          phone_number:
            phone,

        });

      setCheckoutRequestId(

        response.checkout_request_id,

      );

      setAwaitingConfirmation(true);

      setMessage(

        response.customer_message ??
        "STK Push sent successfully. Check your phone.",

      );

      startPolling(

        response.checkout_request_id,

      );

    } catch (err) {

      setError(

        err?.response?.data?.detail ||

        err?.message ||

        "Unable to start payment.",

      );

    } finally {

      setLoading(false);

    }
  }

  //--------------------------------------------------------
  // RENDER
  //--------------------------------------------------------
    if (plans.length === 0) {
    return (

      <div className="space-y-8">

          <section className="rounded-3xl border border-white/10 bg-pitch p-8">

              <h1 className="text-2xl font-black">

                  Loading...

              </h1>

              <p className="mt-2 text-slate-400">

                  Loading subscription plans...

              </p>

          </section>

      </div>

    );
  }

  if (!plan) {
    return (
      <div>Invalid subscription plan.</div>
    );
  }

  return (
    <div className="space-y-8">

      <button
        onClick={() => navigate("/subscriptions")}
        className="flex items-center gap-2 text-slate-300 hover:text-white"
      >
        <ArrowLeft size={18} />
        Back
      </button>

      <section className="rounded-3xl border border-white/10 bg-pitch p-8">

        <h1 className="text-3xl font-black">
          Checkout
        </h1>

        <p className="mt-2 text-slate-400">
          Complete your premium subscription.
        </p>

      </section>

      <section className="rounded-3xl border border-white/10 bg-pitch p-8">

        <h2 className="text-2xl font-black">
          {plan.name}
        </h2>

        <div className="mt-4 text-5xl font-black text-signal">

          {plan.currency} {plan.price}

        </div>

        <p className="mt-2 text-slate-400">
          {plan.duration_days} Days
        </p>

      </section>

      <section className="rounded-3xl border border-white/10 bg-pitch p-8">

        <div className="flex items-center gap-2">

          <ShieldCheck className="text-signal" />

          <h2 className="text-xl font-black">
            Included
          </h2>

        </div>

        <div className="mt-6 space-y-3">

          {FEATURES.map((feature) => (

            <div
              key={feature}
              className="flex items-center gap-3"
            >

              <CheckCircle2
                size={18}
                className="text-signal"
              />

              {feature}

            </div>

          ))}

        </div>

      </section>

      <section className="rounded-3xl border border-white/10 bg-pitch p-8">

        <h2 className="text-xl font-black">
          Payment Method
        </h2>

        <div className="mt-6 space-y-4">

          <label className="flex cursor-pointer items-center gap-3 rounded-xl border border-signal bg-turf p-4">

            <input
              type="radio"
              checked={paymentMethod === "MPESA"}
              onChange={() =>
                setPaymentMethod("MPESA")
              }
            />

            <Smartphone size={20} />

            M-Pesa

          </label>

          <label
            className={`flex items-center gap-3 rounded-xl border p-4 ${
              !cardEnabled
                ? "cursor-not-allowed border-white/10 bg-turf opacity-60"
                : paymentMethod === "CARD"
                ? "cursor-pointer border-signal bg-turf"
                : "cursor-pointer border-white/10 bg-turf"
            }`}
          >

            <input
              type="radio"
              disabled={!cardEnabled}
              checked={paymentMethod === "CARD"}
              onChange={() => setPaymentMethod("CARD")}
            />

            <CreditCard size={20} />

            Debit / Credit Card

            {!cardEnabled && (
              <span className="ml-auto text-xs">Not available yet</span>
            )}

          </label>

        </div>

        {paymentMethod === "MPESA" ? (
        <div className="mt-6">

          <label className="block text-sm text-slate-400">

            M-Pesa Phone Number

          </label>

          <input
            type="tel"
            placeholder="254712345678"
            value={phone}
            onChange={(e) =>
              setPhone(e.target.value)
            }
            className="mt-2 w-full rounded-xl border border-white/10 bg-turf px-4 py-3 outline-none"
          />

        </div>
        ) : (
          <p className="mt-6 text-sm text-slate-300">You'll be taken to a secure page to enter your card details, then brought back here.</p>
        )}

      </section>

      <section className="rounded-3xl border border-white/10 bg-pitch p-8">

        <h2 className="text-xl font-black">
          Order Summary
        </h2>

        <div className="mt-6 flex justify-between">

          <span>Plan</span>

          <span>{plan.name}</span>

        </div>

        <div className="mt-3 flex justify-between">

          <span>Price</span>

          <span>{plan.currency} {plan.price}</span>

        </div>

        <div className="mt-3 flex justify-between">

          <span>Tax</span>

          <span>{plan.currency} 0</span>

        </div>

        <hr className="my-5 border-white/10" />

        <div className="flex justify-between text-xl font-black">

          <span>Total</span>

          <span>{plan.currency} {plan.price}</span>

        </div>

      </section>

      {message && (

        <div className="rounded-xl border border-green-500/30 bg-green-500/10 p-4 text-green-300">

          {message}

        </div>

      )}

      {checkoutRequestId && (

        <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 p-4 text-cyan-300">

          Checkout Request ID:

          <div className="mt-2 break-all text-xs">

            {checkoutRequestId}

          </div>

          <div className="mt-3 text-sm">

            Waiting for payment confirmation...

          </div>

        </div>

      )}

      {error && (

        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-300">

          {error}

        </div>

      )}

      <button
        onClick={handleCheckout}
        disabled={loading || awaitingConfirmation}
        className="w-full rounded-2xl bg-signal py-4 text-lg font-black text-ink hover:opacity-90 disabled:opacity-50"
      >

        {loading
          ? "Starting Payment..."
          : awaitingConfirmation
          ? "Waiting for Confirmation..."
          : paymentMethod === "CARD"
          ? "Pay by card"
          : "Proceed to Payment"}

      </button>

    </div>
  );
}
