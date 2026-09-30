/*
 * ====== SKELETON STUB ======  HitlPanel.tsx  (Phase 7)
 * The two Human-in-the-Loop pauses:
 *   HITL #1 (hitl.hitl === 1): show fix_options; user picks one and clicks
 *            [Apply Fix]  -> POST /api/hitl/fix {incident_id, fix_id}.
 *   HITL #2 (hitl.hitl === 2): show the editable ticket_draft; user edits and
 *            clicks [Submit Ticket] -> POST /api/hitl/ticket {incident_id, ticket_final}.
 * Call onResolved() after a successful POST. hitl === null => render nothing.
 */
import { useEffect, useState } from "react";
import { api } from "./api";
import type { HitlEvent } from "./types";

export default function HitlPanel({ hitl, onResolved }: {
  hitl: HitlEvent | null;
  onResolved: () => void;
}) {
  const [selected, setSelected] = useState<number | null>(null);
  const [ticket, setTicket] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { setSelected(null); setTicket(hitl?.hitl === 2 ? hitl.ticket_draft ?? "" : ""); }, [hitl]);
  if (!hitl) return <section className="rounded-lg border border-zinc-800 bg-zinc-950 p-4 text-sm text-zinc-600">No action required.</section>;
  const submit = () => {
    setBusy(true);
    const request = hitl.hitl === 1 ? api.submitFixApproval(hitl.incident_id, selected as number) : api.submitTicket(hitl.incident_id, ticket);
    request.then(onResolved).catch((error: Error) => {
      if (error.message.startsWith("409 ")) onResolved();
    }).finally(() => setBusy(false));
  };
  return <section className="rounded-lg border border-red-900 bg-red-950/20 p-4"><h2 className="mb-3 text-sm font-bold text-red-300">Human approval required</h2>{hitl.hitl === 1 ? <div className="space-y-2">{[...hitl.fix_options].sort((a, b) => (a.display_order ?? 99) - (b.display_order ?? 99)).map((option) => <label key={option.id} className="flex gap-2 text-xs text-zinc-300"><input type="radio" name="fix" checked={selected === option.id} onChange={() => setSelected(option.id)} />{option.description}</label>)}<button disabled={busy || selected === null} onClick={submit} className="mt-3 bg-red-600 px-3 py-2 text-xs font-bold text-white disabled:opacity-40">Apply Fix</button></div> : <div><textarea value={ticket} onChange={(event) => setTicket(event.target.value)} className="h-32 w-full border border-zinc-700 bg-zinc-950 p-2 text-xs text-zinc-200" /><button disabled={busy || !ticket.trim()} onClick={submit} className="mt-3 bg-red-600 px-3 py-2 text-xs font-bold text-white disabled:opacity-40">Submit Ticket</button></div>}</section>;
}
