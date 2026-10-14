import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { verifyCardPayment } from "../services";

// Where the card page sends the customer back to. We never trust the browser's
// word that it paid: the server asks the payment provider.
export default function CardReturn() {
  const [params] = useSearchParams();
  const reference = params.get("reference") || params.get("trxref");
  const { refreshUser } = useAuth();
  const [state, setState] = useState(reference ? "checking" : "missing");

  useEffect(() => {
    if (!reference) return undefined;

    let cancelled = false;
    let tries = 0;

    async function check() {
      try {
        const { status } = await verifyCardPayment(reference);
        if (cancelled) return;
        if (status === "active") {
          await refreshUser();
          setState("active");
        } else if (status === "pending" && tries++ < 10) {
          setTimeout(check, 3000);
        } else {
          setState(status === "pending" ? "pending" : "failed");
        }
      } catch {
        if (!cancelled) setState("error");
      }
    }

    check();
    return () => {
      cancelled = true;
    };
  }, [reference, refreshUser]);

  const view = {
    checking: [<Loader2 key="i" className="animate-spin text-signal" size={44} />, "Confirming your payment...", "This takes a few seconds."],
    active: [<CheckCircle2 key="i" className="text-leaf" size={44} />, "Payment received", "Premium is now active on your account."],
    pending: [<Loader2 key="i" className="text-signal" size={44} />, "Still waiting for the bank", "If you were charged, Premium will switch on automatically within a few minutes."],
    failed: [<XCircle key="i" className="text-red-400" size={44} />, "The payment didn't go through", "You haven't been charged. You can try again."],
    error: [<XCircle key="i" className="text-red-400" size={44} />, "We couldn't confirm the payment", "If you were charged, Premium will switch on automatically. Otherwise try again shortly."],
    missing: [<XCircle key="i" className="text-red-400" size={44} />, "Nothing to confirm", "Open this page from your payment confirmation."],
  }[state];

  return (
    <div className="mx-auto max-w-md rounded-3xl border border-white/10 bg-pitch p-8 text-center">
      <div className="flex justify-center">{view[0]}</div>
      <h1 className="mt-4 text-2xl font-black">{view[1]}</h1>
      <p className="mt-2 text-slate-300">{view[2]}</p>
      <div className="mt-6 flex justify-center gap-3">
        <Link to="/predictions" className="rounded-xl bg-signal px-5 py-3 font-black text-ink">
          View predictions
        </Link>
        {state !== "active" && state !== "checking" && (
          <Link to="/subscriptions" className="rounded-xl bg-white/10 px-5 py-3 font-bold">
            Back to plans
          </Link>
        )}
      </div>
    </div>
  );
}
