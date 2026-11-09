import { useCallback, useEffect, useState } from "react";
import { ArrowDownCircle, ArrowUpCircle, RefreshCw } from "lucide-react";
import { getWallet, getWalletTransactions } from "../services/betting";

function TransactionRow({ tx }) {
  const amount = Number(tx.amount ?? 0);
  const credit = amount >= 0;
  const when = tx.created_at ? new Date(tx.created_at) : null;

  return (
    <div className="flex items-center justify-between gap-3 border-b border-white/5 py-3 last:border-0">
      <div className="flex min-w-0 items-center gap-3">
        {credit ? (
          <ArrowDownCircle size={20} className="shrink-0 text-leaf" />
        ) : (
          <ArrowUpCircle size={20} className="shrink-0 text-signal" />
        )}
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-chalk">
            {tx.reason || tx.type || (credit ? "Credit" : "Debit")}
          </p>
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
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-3xl font-black">Wallet</h1>
          <p className="mt-1 text-slate-400">
            Paper-money balance for the FOOTY254 betting module. No real deposits or withdrawals.
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-2 rounded-xl bg-turf px-4 py-2 text-sm font-semibold hover:bg-line disabled:opacity-50"
        >
          <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

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
