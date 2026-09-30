/*
 * ====== SKELETON STUB ======  ActivityLog.tsx  (Phase 7)
 * The Sequence-of-Events Recorder (SER): a dark, monospace terminal that
 * streams every executor/agent step from `activity` SSE events. Newest line on
 * top, colour-coded by message_type (INFO/WARNING/ERROR/HUMAN). Shows the
 * connection state and any `error` event. `title` is overridable.
 */
import type { ActivityEvent, ErrorEvent } from "./types";

export default function ActivityLog({ activity, connected, error, title = "Sequence-of-Events Recorder" }: {
  activity: ActivityEvent[];
  connected: boolean;
  error: ErrorEvent | null;
  title?: string;
}) {
  const colors: Record<string, string> = { Orchestrator: "text-fuchsia-400", Detect: "text-cyan-400", Analyze: "text-sky-400", RCA: "text-indigo-400", Suggest: "text-yellow-400", Fix: "text-orange-400", Ticket: "text-lime-400", Human: "text-emerald-400", Executor: "text-red-400" };
  const rows = [...activity].sort((a, b) => b.created_at.localeCompare(a.created_at));
  return <section className="flex min-h-[300px] flex-col rounded-lg border border-zinc-800 bg-black p-4 font-mono"><div className="mb-3 flex justify-between text-xs font-bold text-zinc-300"><span>{title}</span><span className={connected ? "text-emerald-400" : "text-red-400"}>{connected ? "LIVE" : "OFFLINE"}</span></div><div className="overflow-auto text-[11px]">{error && <div className="text-red-400">Executor: {error.message}</div>}{rows.map((item, index) => <div key={item.id}>{index > 0 && rows[index - 1].incident_id !== item.incident_id && <div className="my-2 border-t border-dashed border-zinc-700 py-1 text-center text-[10px] text-zinc-600">Incident #{rows[index - 1].incident_id} / Incident #{item.incident_id}</div>}<div className="py-1"><span className="text-zinc-600">[{new Date(item.created_at).toLocaleTimeString([], { hour12: false })}]</span> <span className={colors[item.agent_name] ?? "text-zinc-300"}>{item.agent_name}</span> <span className={item.message_type === "INFO" ? "text-zinc-400" : item.message_type === "HUMAN" ? "text-emerald-300" : "text-red-400"}>[{item.message_type}]</span> <span className="text-zinc-300">{item.message}</span></div></div>)}</div></section>;
}
