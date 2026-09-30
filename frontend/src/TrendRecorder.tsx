/*
 * ====== SKELETON STUB ======  TrendRecorder.tsx  (Phase 7)
 * Popup that polls GET /api/resources/{id}/history?minutes=15 and plots the
 * moving time-series (the sampler keeps ~15 min of data) so the graphs animate
 * live and recover after a fix. onClose() dismisses the popup.
 */
import { useEffect, useState } from "react";
import { LineChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis, ReferenceLine } from "recharts";
import { api } from "./api";
import { METRIC_ORDER, metaFor } from "./metricMeta";
import type { Resource } from "./types";

export default function TrendRecorder({ resourceId, resource, onClose }: {
  resourceId: number;
  resource: Resource | undefined;
  onClose: () => void;
}) {
  const [history, setHistory] = useState<Awaited<ReturnType<typeof api.getResourceHistory>> | null>(null);
  useEffect(() => { const load = () => api.getResourceHistory(resourceId).then(setHistory).catch(() => undefined); void load(); const timer = window.setInterval(load, 2000); const key = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); }; window.addEventListener("keydown", key); return () => { window.clearInterval(timer); window.removeEventListener("keydown", key); }; }, [resourceId, onClose]);
  if (!resource) return null;
  return <div className="fixed inset-0 z-30 flex items-center justify-center bg-black/70 p-4" onClick={onClose}><div className="max-h-[90vh] w-full max-w-5xl overflow-auto rounded-lg border border-zinc-700 bg-zinc-950 p-5" onClick={(event) => event.stopPropagation()}><div className="mb-4 flex justify-between"><div><h2 className="text-lg font-bold text-zinc-100">{resource.display_name ?? resource.name}</h2><p className="text-xs text-zinc-500">15-minute trend recorder</p></div><button onClick={onClose} className="text-zinc-500 hover:text-zinc-100">Close</button></div><div className="grid gap-4 md:grid-cols-2">{METRIC_ORDER.map((name) => { const threshold = history?.thresholds[name]; const data = (history?.metrics[name] ?? []).map((point) => ({ ...point, time: new Date(point.recorded_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) })); return <div key={name} className="border border-zinc-800 p-2"><div className="mb-1 text-xs text-zinc-300">{metaFor(name).label}</div><ResponsiveContainer width="100%" height={160}><LineChart data={data}><XAxis dataKey="time" hide /><YAxis width={35} tick={{ fill: "#71717a", fontSize: 9 }} /><Tooltip /><Line type="monotone" dataKey="value" stroke={metaFor(name).color} dot={false} strokeWidth={2} />{threshold?.normal_max !== null && threshold?.normal_max !== undefined && <ReferenceLine y={threshold.normal_max} stroke="#71717a" strokeDasharray="4 4" />}{threshold?.warning_value !== null && threshold?.warning_value !== undefined && <ReferenceLine y={threshold.warning_value} stroke="#f59e0b" />}{threshold?.critical_value !== null && threshold?.critical_value !== undefined && <ReferenceLine y={threshold.critical_value} stroke="#ef4444" />}</LineChart></ResponsiveContainer></div>; })}</div></div></div>;
}
