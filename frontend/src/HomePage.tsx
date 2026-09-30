/*
 * ====== SKELETON STUB ======  HomePage.tsx  (Phase 7)
 * The Home page: Single-Line Diagram (<SLD>) + <LiveMetrics> table, plus a
 * <TrendRecorder> popup when a resource is selected. Consumes the shared
 * SSEState (resource_status events) and polls /api/resources.
 */
import type { SSEState } from "./useEventStream";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import SLD from "./SLD";
import LiveMetrics from "./LiveMetrics";
import FaultPanel from "./FaultPanel";
import ReliabilityPanel from "./ReliabilityPanel";
import TrendRecorder from "./TrendRecorder";
import { api } from "./api";
import { useResourcesPoll } from "./useResourcesPoll";
import { useActiveIncidentDetail } from "./useActiveIncidentDetail";
import type { ThresholdInfo } from "./types";

export default function HomePage({ sse }: { sse: SSEState }) {
  const { groups } = useResourcesPoll(sse.resourceStatus); const [selected, setSelected] = useState<number | null>(null); const [manualBump, setManualBump] = useState(0); const [thresholdsByResource, setThresholds] = useState<Record<number, Record<string, ThresholdInfo>>>({});
  const versionToken = `${sse.activeIncidentId}-${sse.status?.status}-${sse.resolved?.incident_id}-${manualBump}`; const detail = useActiveIncidentDetail(versionToken);
  useEffect(() => { groups.forEach((group) => group.resources.forEach((resource) => { if (!thresholdsByResource[resource.id]) api.getResourceHistory(resource.id, 1).then((data) => setThresholds((current) => ({ ...current, [resource.id]: data.thresholds }))).catch(() => undefined); })); }, [groups, thresholdsByResource]);
  const resources = groups.flatMap((group) => group.resources); const statusCounts = ["Healthy", "Degraded", "Critical"].map((status) => ({ status, count: resources.filter((resource) => resource.status === status).length }));
  return <div className="space-y-4 p-4"><div className="flex flex-wrap items-end justify-between gap-3"><div><p className="text-[10px] uppercase tracking-[0.3em] text-emerald-400">SRE reliability watch</p><h1 className="text-2xl font-bold text-zinc-100">Error Budget Watcher</h1></div><div className="flex gap-2">{statusCounts.map((item) => <span key={item.status} className="border border-zinc-800 px-3 py-2 text-xs text-zinc-400"><b className="text-zinc-100">{item.count}</b> {item.status}</span>)}</div></div>{detail?.incident && <Link to="/orchestration" className="block border border-red-900 bg-red-950/20 p-3 text-sm text-red-300">Active incident #{detail.incident.id} · {detail.incident.status} · {detail.scenario?.severity ?? ""}</Link>}<ReliabilityPanel /><SLD groups={groups} onSelectResource={setSelected} /><div className="grid gap-4 lg:grid-cols-3"><div className="lg:col-span-2"><LiveMetrics groups={groups} thresholdsByResource={thresholdsByResource} onSelectResource={setSelected} /></div><FaultPanel hasActiveIncident={Boolean(detail?.incident?.is_active)} onInjected={() => setManualBump((value) => value + 1)} /></div>{selected !== null && <TrendRecorder resourceId={selected} resource={resources.find((item) => item.id === selected)} onClose={() => setSelected(null)} />}</div>;
}
