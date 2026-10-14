import { Activity, ShieldCheck, Target, TrendingUp } from "lucide-react";
import StatCard from "../components/StatCard.jsx";

import { useEffect, useState } from "react";

import { loadAnalytics, loadEngineStatus } from "../services";

export default function Analytics() {
  const [analytics, setAnalytics] = useState([]);
  const [status, setStatus] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [data, engineStatus] = await Promise.all([
          loadAnalytics(),
          loadEngineStatus(),
        ]);

        // transform or guard data into array of stat items
        if (Array.isArray(data)) setAnalytics(data);
        else if (data && typeof data === "object") {
          setAnalytics([
            { title: "Accuracy", value: `${data.accuracy ?? 0}%`, icon: Target },
            { title: "Uptime", value: `${data.uptime ?? "0%"}`, icon: Activity },
            { title: "Stability", value: `${data.stability ?? "0%"}`, icon: ShieldCheck },
            { title: "Growth", value: `${data.growth ?? "0%"}`, icon: TrendingUp }
          ]);
        }

        setStatus(engineStatus);
      } catch (error) {
        console.error(error);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  return (
    <div className="space-y-5">
      <header>
        <p className="text-xs font-bold uppercase tracking-[0.22em] text-signal">Analytics</p>
        <h1 className="mt-2 text-3xl font-black">AI Performance</h1>
      </header>

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {loading ? (
          <div>Loading...</div>
        ) : (
          analytics.map((item) => <StatCard key={item.title} {...item} />)
        )}
      </section>

      <section className="rounded-[28px] border border-white/10 bg-pitch p-4">
        <h2 className="text-xl font-black">Engine Status</h2>
        <div className="mt-5 space-y-5">
          {loading ? (
            <p className="text-sm text-slate-400">Loading...</p>
          ) : (
            status.map((item) => (
              <div key={item.label}>
                <div className="mb-2 flex justify-between text-sm">
                  <span className="text-slate-400">{item.label}</span>
                  <span className="font-bold text-white">{item.value}</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-white/10">
                  <div className={`h-full rounded-full ${item.color}`} style={{ width: `${item.progress}%` }} />
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
