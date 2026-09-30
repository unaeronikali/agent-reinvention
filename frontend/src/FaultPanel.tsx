/*
 * ====== SKELETON STUB ======  FaultPanel.tsx  (Phase 7)
 * Lists the 5 fault scenarios (GET /api/scenarios) each with an [Inject Fault]
 * button (POST /api/fault/inject) plus a [Restore Normal] button
 * (POST /api/fault/restore). Disable injection while hasActiveIncident. On a
 * successful inject call onInjected(incidentId).
 */
import { useEffect, useState } from "react";
import { api } from "./api";
import type { Scenario } from "./types";

export default function FaultPanel({ hasActiveIncident, onInjected }: {
  hasActiveIncident: boolean;
  onInjected: (incidentId: number | null) => void;
}) {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<string | null>(null);
  useEffect(() => { api.getScenarios().then((data) => setScenarios(data.scenarios)).catch((reason: unknown) => setError(String(reason))); }, []);
  const inject = async (id: number) => {
    setBusy(true);
    setError(null);
    setOutcome(null);
    try {
      const result = await api.injectFault(id);
      onInjected(result.incident_id);
      setOutcome(result.incident_id ? `HIGH risk · Incident #${result.incident_id} started` : `${result.snapshot.risk} risk · Monitoring continues`);
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy(false);
    }
  };
  return <section className="rounded-lg border border-zinc-800 bg-zinc-950 p-4"><div className="mb-3 flex items-center justify-between"><h2 className="text-sm font-bold text-zinc-100">Scenario Injection</h2><button onClick={() => api.restoreNormal().then(() => { setOutcome("Baseline restored"); setError(null); }).catch((reason: unknown) => setError(String(reason)))} className="border border-zinc-700 px-2 py-1 text-[10px] uppercase text-zinc-400 hover:text-zinc-100">Restore</button></div>{hasActiveIncident && <p className="mb-3 text-xs text-amber-400">An incident is active.</p>}<div className="space-y-2">{scenarios.map((scenario) => <div key={scenario.id} className="flex items-center justify-between border-b border-zinc-900 py-2"><div><div className="text-xs text-zinc-200">{scenario.name}</div><div className="text-[10px] text-zinc-600">{scenario.description}</div></div><button disabled={busy || hasActiveIncident} onClick={() => inject(scenario.id)} className="border border-red-800 px-2 py-1 text-[10px] uppercase text-red-400 disabled:cursor-not-allowed disabled:opacity-40">{scenario.severity} · Inject</button></div>)}</div>{outcome && <p className="mt-3 text-xs text-emerald-300">{outcome}</p>}{error && <p className="mt-3 text-xs text-red-400">{error}</p>}</section>;
}
