import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowDownCircle, ArrowUpCircle, Plus, RefreshCw, Smartphone, X } from "lucide-react";
import {
  getWallet,
  getWalletTransactions,
  demoTopUp,
  initiateMpesaDeposit,
  getMpesaDepositStatus,
} from "../services/betting";
import BackButton from "../components/BackButton";

const TOPUP_PRESETS = [100, 250, 500, 1000];

function DemoTopUpTab({ onDone }) {
  const [amount, setAmount] = useState("500");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit() {
    setError("");
    const value = Number(amount);
    if (!value || value <= 0) {
      setError("Enter an amount greater than zero.");
      return;
    }
    setSubmitting(true);
    try {
      await demoTopUp(value);
      onDone();
    } catch (err) {
      setError(err?.message || "Could not add funds right now.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <p className="mb-4 rounded-xl border border-gold/20 bg-gold/10 p-3 text-xs text-chalk/80">
        Instant, paper-money only - no real cash moves. Use this for quick testing.
      </p>

      <div className="mb-3 flex flex-wrap gap-2">
        {TOPUP_PRESETS.map((v) => (
          <button
            key={v}
            type="button"
            onClick={() => setAmount(String(v))}
            className={`rounded-lg px-3 py-1.5 text-sm font-bold transition ${
              Number(amount) === v ? "bg-signal text-ink" : "bg-turf text-chalk/70 hover:bg-line"
            }`}
          >
            {v}
          </button>
        ))}
      </div>

      <label className="block text-xs font-semibold uppercase tracking-wide text-chalk/60">
        Amount (KES)
      </label>
      <input
        type="number"
        min="1"
        value={amount}
        onChange={(e) => setAmount(e.target.value)}
        className="mt-1 w-full rounded-xl border border-white/10 bg-ink px-3 py-2 text-chalk outline-none focus:border-signal"
      />

      {error && (
        <p className="mt-2 rounded-lg border border-red-500/30 bg-red-500/10 p-2 text-xs text-red-300">
          {error}
        </p>
      )}

      <button
        type="button"
        disabled={submitting}
        onClick={handleSubmit}
        className="mt-4 w-full rounded-xl bg-signal px-4 py-2.5 text-sm font-bold text-ink hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {submitting ? "Adding..." : `Add KES ${amount || 0}`}
      </button>
    </div>
  );
}

// Polls /betting/wallet/mpesa/status/{id} every 3s, for up to 2 minutes,
// while the user responds to the STK prompt on their phone.
function useStkPolling(checkoutRequestId, onResolved) {
  const pollRef = useRef(null);

  useEffect(() => {
    if (!checkoutRequestId) return undefined;

    let attempts = 0;
    const MAX_ATTEMPTS = 40; // ~2 minutes at 3s intervals

    pollRef.current = setInterval(async () => {
      attempts += 1;
      try {
        const result = await getMpesaDepositStatus(checkoutRequestId);
        if (result.status && result.status !== "PENDING") {
          clearInterval(pollRef.current);
          onResolved(result);
        } else if (attempts >= MAX_ATTEMPTS) {
          clearInterval(pollRef.current);
          onResolved({ status: "TIMEOUT" });
        }
      } catch {
        // transient network error - keep polling, the interval will just
        // try again in 3s; only MAX_ATTEMPTS gives up for good.
      }
    }, 3000);

    return () => clearInterval(pollRef.current);
  }, [checkoutRequestId, onResolved]);
}

function MpesaDepositTab({ onDone }) {
  const [phone, setPhone] = useState("");
  const [amount, setAmount] = useState("500");
  const [stage, setStage] = useState("form"); // form | waiting | success | failed
  const [error, setError] = useState("");
  const [checkoutRequestId, setCheckoutRequestId] = useState(null);

  const handleResolved = useCallback(
    (result) => {
      if (result.status === "SUCCESS") {
        setStage("success");
        setTimeout(onDone, 1200);
      } else if (result.status === "TIMEOUT") {
        setError("No response yet - check your phone, or try again.");
        setStage("form");
      } else {
        setError(result.result_desc || "Payment was not completed.");
        setStage("failed");
      }
    },
    [onDone]
  );

  useStkPolling(stage === "waiting" ? checkoutRequestId : null, handleResolved);

  async function handleSubmit() {
    setError("");
    const value = Number(amount);
    if (!value || value <= 0) {
      setError("Enter an amount greater than zero.");
      return;
    }
    if (!phone.trim()) {
      setError("Enter the phone number to receive the STK prompt.");
      return;
    }
    setStage("waiting");
    try {
      const res = await initiateMpesaDeposit({ phone, amount: value });
      setCheckoutRequestId(res.CheckoutRequestID || res.checkout_request_id);
    } catch (err) {
      setError(err?.message || "Could not start the M-Pesa request.");
      setStage("form");
    }
  }

  if (stage === "waiting") {
    return (
      <div className="py-6 text-center">
        <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-4 border-signal/20 border-t-signal" />
        <p className="font-bold text-chalk">Check your phone</p>
        <p className="mt-1 text-sm text-chalk/60">
          A payment prompt was sent to {phone}. Enter your M-Pesa PIN to complete it.
        </p>
        <p className="mt-3 text-xs text-chalk/40">Sandbox mode - no real money is charged.</p>
      </div>
    );
  }

  if (stage === "success") {
    return (
      <div className="py-6 text-center">
        <p className="text-3xl">✅</p>
        <p className="mt-2 font-bold text-chalk">Payment received</p>
        <p className="mt-1 text-sm text-chalk/60">Your wallet balance will update in a moment.</p>
      </div>
    );
  }

  return (
    <div>
      <p className="mb-4 rounded-xl border border-gold/20 bg-gold/10 p-3 text-xs text-chalk/80">
        This sends a REAL Safaricom STK Push through Daraja's sandbox - a genuine prompt will
        reach the phone number below. It's Safaricom's own test environment, so no real money is
        charged. Use one of Safaricom's published sandbox test numbers if you don't want to use
        your own phone (ask your backend dev for the current one - it's in the Daraja docs).
      </p>

      <label className="block text-xs font-semibold uppercase tracking-wide text-chalk/60">
        M-Pesa phone number
      </label>
      <input
        type="tel"
        placeholder="07XXXXXXXX"
        value={phone}
        onChange={(e) => setPhone(e.target.value)}
        className="mt-1 w-full rounded-xl border border-white/10 bg-ink px-3 py-2 text-chalk outline-none focus:border-signal"
      />

      <label className="mt-3 block text-xs font-semibold uppercase tracking-wide text-chalk/60">
        Amount (KES)
      </label>
      <input
        type="number"
        min="1"
        value={amount}
        onChange={(e) => setAmount(e.target.value)}
        className="mt-1 w-full rounded-xl border border-white/10 bg-ink px-3 py-2 text-chalk outline-none focus:border-signal"
      />

      {error && (
        <p className="mt-2 rounded-lg border border-red-500/30 bg-red-500/10 p-2 text-xs text-red-300">
          {error}
        </p>
      )}

      <button
        type="button"
        onClick={handleSubmit}
        className="mt-4 w-full rounded-xl bg-leaf px-4 py-2.5 text-sm font-bold text-ink hover:opacity-90"
      >
        Send STK Push
      </button>
    </div>
  );
}

function AddFundsModal({ onClose, onDone }) {
  const [tab, setTab] = useState("mpesa");

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="Close"
        onClick={onClose}
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
      />
      <div className="relative z-10 w-full max-w-sm rounded-2xl border border-white/10 bg-pitch p-5">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-black text-chalk">Add funds</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full p-1.5 text-chalk/60 hover:bg-white/10 hover:text-chalk"
          >
            <X size={18} />
          </button>
        </div>

        <div className="mb-4 flex gap-1 rounded-xl bg-ink/60 p-1">
          <button
            type="button"
            onClick={() => setTab("mpesa")}
            className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg py-2 text-xs font-bold transition ${
              tab === "mpesa" ? "bg-leaf text-ink" : "text-chalk/60"
            }`}
          >
            <Smartphone size={14} />
            M-Pesa (sandbox)
          </button>
          <button
            type="button"
            onClick={() => setTab("demo")}
            className={`flex-1 rounded-lg py-2 text-xs font-bold transition ${
              tab === "demo" ? "bg-signal text-ink" : "text-chalk/60"
            }`}
          >
            Demo top-up
          </button>
        </div>

        {tab === "mpesa" ? (
          <MpesaDepositTab onDone={onDone} />
        ) : (
          <DemoTopUpTab onDone={onDone} />
        )}
      </div>
    </div>
  );
}

// Maps a few raw backend `reason` values to something a user reads
// comfortably, rather than a snake_case string. Anything not listed here
// falls back to the raw reason - better than hiding real unknown values.
const REASON_LABELS = {
  demo_topup: "Demo top-up",
  mpesa_sandbox_deposit: "M-Pesa deposit (sandbox)",
  bet_void_refund: "Bet voided - stake refunded",
};

function TransactionRow({ tx }) {
  const amount = Number(tx.amount ?? 0);
  const credit = amount >= 0;
  const when = tx.created_at ? new Date(tx.created_at) : null;
  const label = REASON_LABELS[tx.reason] || tx.reason || tx.type || (credit ? "Credit" : "Debit");

  return (
    <div className="flex items-center justify-between gap-3 border-b border-white/5 py-3 last:border-0">
      <div className="flex min-w-0 items-center gap-3">
        {credit ? (
          <ArrowDownCircle size={20} className="shrink-0 text-leaf" />
        ) : (
          <ArrowUpCircle size={20} className="shrink-0 text-signal" />
        )}
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-chalk">{label}</p>
          {when && (
            <p className="text-xs text-chalk/50">
              {when.toLocaleDateString([], { day: "numeric", month: "short" })}{" "}
              {when.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </p>
          )}
        </div>
      </div>
      <span className={`shrink-0 font-black tabular-nums ${credit ? "text-leaf" : "text-signal"}`}>
        {credit ? "+" : ""}
        {amount.toFixed(2)}
      </span>
    </div>
  );
}

export default function Wallet() {
  const [wallet, setWallet] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showAddFunds, setShowAddFunds] = useState(false);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError("");
      const [w, tx] = await Promise.all([getWallet(), getWalletTransactions()]);
      setWallet(w);
      setTransactions(tx);
    } catch (err) {
      console.error(err);
      setError(
        err?.status === 401
          ? "Sign in to see your wallet."
          : "We couldn't load your wallet right now."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-5">
      <BackButton />
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-3xl font-black">Wallet</h1>
          <p className="mt-1 text-slate-400">
            Paper-money balance for the FOOTY254 betting module. No real deposits or withdrawals.
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          <button
            onClick={() => setShowAddFunds(true)}
            className="flex items-center gap-2 rounded-xl bg-signal px-4 py-2 text-sm font-bold text-ink hover:opacity-90"
          >
            <Plus size={16} />
            Add funds
          </button>
          <button
            onClick={load}
            disabled={loading}
            className="flex items-center gap-2 rounded-xl bg-turf px-4 py-2 text-sm font-semibold hover:bg-line disabled:opacity-50"
          >
            <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
          </button>
        </div>
      </div>

      {showAddFunds && (
        <AddFundsModal
          onClose={() => setShowAddFunds(false)}
          onDone={async () => {
            await load();
            setShowAddFunds(false);
          }}
        />
      )}

      {loading && (
        <div className="rounded-2xl border border-white/10 bg-pitch p-6 text-center text-slate-300">
          Loading wallet...
        </div>
      )}

      {error && (
        <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-5 text-red-300">
          {error}
        </div>
      )}

      {!loading && !error && wallet && (
        <>
          <div className="rounded-2xl border border-white/10 bg-pitch p-6">
            <p className="text-xs font-semibold uppercase tracking-wide text-chalk/60">
              Available balance
            </p>
            <p className="mt-1 text-4xl font-black text-signal">
              KES {Number(wallet.balance ?? 0).toFixed(2)}
            </p>
            <p className="mt-3 text-xs text-chalk/50">
              Real M-Pesa deposits aren't wired up here on purpose - taking actual money
              needs a licensed payment integration (Safaricom Daraja API, a PCI-compliant
              callback handler, reconciliation, the works), which belongs in FOOTY254's own
              payment infrastructure rather than bolted onto a demo. "Add funds" above tops
              up this paper wallet only.
            </p>
          </div>

          <div className="rounded-2xl border border-white/10 bg-pitch p-5">
            <h2 className="mb-2 text-sm font-black uppercase tracking-wide text-chalk/70">
              Recent activity
            </h2>
            {transactions.length === 0 ? (
              <p className="py-6 text-center text-sm text-chalk/50">No transactions yet.</p>
            ) : (
              <div>
                {transactions.map((tx) => (
                  <TransactionRow key={tx.id ?? `${tx.created_at}-${tx.amount}`} tx={tx} />
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
