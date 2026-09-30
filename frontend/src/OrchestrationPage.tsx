/*
 * ====== SKELETON STUB ======  OrchestrationPage.tsx  (Phase 7)
 * The Orchestration page: the React Flow <Canvas> (frozen) hub-and-spoke graph
 * driven by `canvas` SSE events, the <ActivityLog> SER terminal, and the
 * <HitlPanel> for the two Human-in-the-Loop pauses. Consumes shared SSEState.
 */
import type { SSEState } from "./useEventStream";
import Canvas from "./Canvas";
import ActivityLog from "./ActivityLog";
import HitlPanel from "./HitlPanel";

export default function OrchestrationPage({ sse }: { sse: SSEState }) {
  return <div className="grid gap-4 p-4 lg:grid-cols-3"><div className="space-y-4 lg:col-span-2"><Canvas canvas={sse.canvas} /><ActivityLog activity={sse.activity} connected={sse.connected} error={sse.error} title="Sequence-of-Events Recorder (SER)" /></div><HitlPanel hitl={sse.hitl} onResolved={() => undefined} /></div>;
}
