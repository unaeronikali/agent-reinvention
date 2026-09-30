import { useEffect, useState } from "react";
import { api } from "./api";
import type { ReliabilityResponse } from "./types";

const riskTone = {
  LOW: "border-emerald-700 text-emerald-300",
  MEDIUM: "border-amber-700 text-amber-300",
  HIGH: "border-red-700 text-red-300",
};

function durationLabel(minutes: number | null) {
  if (minutes === null) return "No projected burn";
  if (minutes < 60) return `${Math.max(1, Math.round(minutes))} min`;
  if (minutes < 1440) return `${(minutes / 60).toFixed(1)} hr`;
  return `${(minutes / 1440).toFixed(1)} days`;
}

export default function ReliabilityPanel() {
  const [data, setData] = useState<ReliabilityResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const refresh = () => api.getReliability()
      .then((value) => { if (active) { setData(value); setError(null); } })
      .catch((reason: unknown) => { if (active) setError(reason instanceof Error ? reason.message : String(reason)); });
    void refresh();
    const timer = window.setInterval(refresh, 2000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);

  const snapshot = data?.snapshot;
  const remaining = snapshot ? Math.max(0, Math.min(100, snapshot.budget_remaining_pct)) : 0;

  return <section className="overflow-hidden border border-zinc-800 bg-zinc-950">
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 px-4 py-3">
      <div>
        <p className="text-[10px] uppercase tracking-[0.24em] text-emerald-400">SRE / Error Budget Watcher</p>
        <h2 className="mt-1 text-base font-semibold text-zinc-100">{data?.resource.display_name ?? "Customer Storefront"}</h2>
      </div>
      {snapshot && <span className={`border px-3 py-1 text-[10px] font-bold tracking-[0.18em] ${riskTone[snapshot.risk]}`}>{snapshot.risk} RISK</span>}
    </div>
    {snapshot ? <>
      <div className="grid divide-y divide-zinc-800 sm:grid-cols-3 sm:divide-x sm:divide-y-0">
        <div className="px-4 py-4">
          <p className="text-[10px] uppercase tracking-widest text-zinc-500">Availability · SLO {snapshot.slo_target}%</p>
          <p className="mt-2 font-mono text-3xl text-zinc-100">{snapshot.availability.toFixed(2)}<span className="text-base text-zinc-500">%</span></p>
          <p className="mt-1 text-xs text-zinc-500">Error rate {snapshot.error_rate_pct.toFixed(2)}%</p>
        </div>
        <div className="px-4 py-4">
          <div className="flex items-baseline justify-between gap-2">
            <p className="text-[10px] uppercase tracking-widest text-zinc-500">Monthly budget remaining</p>
            <span className="font-mono text-xs text-zinc-400">{remaining.toFixed(1)}%</span>
          </div>
          <p className="mt-2 font-mono text-3xl text-zinc-100">{snapshot.budget_remaining_minutes.toFixed(1)}<span className="text-base text-zinc-500"> min</span></p>
          <div className="mt-3 h-1.5 bg-zinc-800" role="progressbar" aria-label="Error budget remaining" aria-valuemin={0} aria-valuemax={100} aria-valuenow={remaining}>
            <div className={`h-full ${snapshot.risk === "HIGH" ? "bg-red-500" : snapshot.risk === "MEDIUM" ? "bg-amber-400" : "bg-emerald-400"}`} style={{ width: `${remaining}%` }} />
          </div>
          <p className="mt-2 text-[10px] text-zinc-500">{snapshot.budget_consumed_minutes.toFixed(2)} min consumed · {snapshot.budget_total_minutes.toFixed(1)} min allowed</p>
        </div>
        <div className="px-4 py-4">
          <p className="text-[10px] uppercase tracking-widest text-zinc-500">Burn rate · forecast</p>
          <p className="mt-2 font-mono text-3xl text-zinc-100">{snapshot.burn_rate.toFixed(1)}<span className="text-base text-zinc-500">×</span></p>
          <p className="mt-1 text-xs text-zinc-500">Budget exhaustion at current rate: {durationLabel(snapshot.minutes_to_exhaustion)}</p>
        </div>
      </div>
      <div className="grid gap-4 border-t border-zinc-800 px-4 py-4 md:grid-cols-[1fr_1.2fr]">
        <div>
          <p className="text-[10px] uppercase tracking-widest text-zinc-500">Decision evidence</p>
          <p className="mt-2 text-sm text-zinc-300">{snapshot.reasons[0]}</p>
          <p className="mt-2 text-[10px] text-zinc-600">Observed over the retained {data.evidence_window_minutes}-minute simulator window</p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-widest text-zinc-500">Recommended action</p>
          <p className="mt-2 text-sm text-zinc-200">{snapshot.recommendations[0]}</p>
          <div className="mt-4 flex flex-wrap items-center gap-x-2 gap-y-1 text-[9px] font-semibold uppercase tracking-wider text-zinc-500" aria-label="Reliability response stages">
            <span className="text-emerald-300">Metrics</span><span>→</span><span className="text-emerald-300">Budget policy</span><span>→</span><span className={snapshot.risk === "LOW" ? "" : "text-amber-300"}>Forecast</span><span>→</span><span>Incident response</span><span>→</span><span>ServiceNow</span>
          </div>
        </div>
      </div>
    </> : <div className="px-4 py-8 text-sm text-zinc-500">{error ? <>Reliability API unavailable. Restart the backend to load policy data. <span className="text-zinc-600">{error}</span></> : "Loading reliability signals…"}</div>}
  </section>;
}