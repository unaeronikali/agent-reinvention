/*
 * ============================== SKELETON STUB ==============================
 * useEventStream.ts -- the ONE EventSource for the whole app
 *
 *   BUILD PHASE : 7 (frontend)   BUILT BY: the Phase 7 prompt in the Build Guide
 *
 * App.tsx opens a single useEventStream() and shares its SSEState with BOTH
 * the Home page and the Orchestration page. Subscribe to /api/stream and fan
 * the executor's SSE events into state. Event types (from executor.py):
 *   activity | canvas | status | tool | hitl | resource_status | resolved | error
 * Event payload types live in types.ts (frozen).
 * ===========================================================================
 */

import { useEffect, useState } from "react";
import { api } from "./api";
import type { ActivityEvent, CanvasEvent, ErrorEvent, HitlEvent, Incident, ResourceStatusEvent, ResolvedEvent, StatusEvent } from "./types";

export interface SSEState {
  connected: boolean;
  activity: ActivityEvent[];
  status: StatusEvent | null;
  canvas: CanvasEvent | null;
  hitl: HitlEvent | null;
  resolved: ResolvedEvent | null;
  error: ErrorEvent | null;
  resourceStatus: ResourceStatusEvent | null;
  activeIncidentId: number | null;
}

export function useEventStream(): SSEState {
  const [state, setState] = useState<SSEState>({ connected: false, activity: [], status: null, canvas: null, hitl: null, resolved: null, error: null, resourceStatus: null, activeIncidentId: null });

  useEffect(() => {
    const source = new EventSource("/api/stream");
    const listen = <T,>(name: string, handler: (payload: T) => void) => {
      source.addEventListener(name, (event) => handler(JSON.parse((event as MessageEvent<string>).data) as T));
    };
    listen<{ active_incident: Incident | null }>("connected", (payload) => {
      const incidentId = payload.active_incident?.id ?? null;
      setState((current) => ({ ...current, connected: true, activeIncidentId: incidentId }));
      if (incidentId !== null) api.getActivity(incidentId).then((response) => setState((current) => ({ ...current, activity: response.activity }))).catch(() => undefined);
    });
    listen<ActivityEvent>("activity", (activity) => setState((current) => ({ ...current, activity: [activity, ...current.activity], activeIncidentId: activity.incident_id })));
    listen<StatusEvent>("status", (status) => setState((current) => ({ ...current, status, activeIncidentId: status.incident_id })));
    listen<CanvasEvent>("canvas", (canvas) => setState((current) => ({ ...current, canvas, activeIncidentId: canvas.incident_id })));
    listen<HitlEvent>("hitl", (hitl) => setState((current) => ({ ...current, hitl, activeIncidentId: hitl.incident_id })));
    listen<ResolvedEvent>("resolved", (resolved) => setState((current) => ({ ...current, resolved, hitl: null, activeIncidentId: resolved.incident_id })));
    listen<ResourceStatusEvent>("resource_status", (resourceStatus) => setState((current) => ({ ...current, resourceStatus })));
    source.addEventListener("heartbeat", () => undefined);
    source.addEventListener("error", (event) => {
      try {
        const payload = JSON.parse((event as MessageEvent<string>).data) as ErrorEvent;
        setState((current) => ({ ...current, error: payload, hitl: null }));
      } catch {
        setState((current) => ({ ...current, connected: false }));
      }
    });
    return () => source.close();
  }, []);
  return state;
}
