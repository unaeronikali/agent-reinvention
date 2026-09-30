/*
 * ============================== SKELETON STUB ==============================
 * useResourcesPoll.ts -- poll GET /api/resources for the dashboard
 *
 *   BUILD PHASE : 7 (frontend)   BUILT BY: the Phase 7 prompt in the Build Guide
 *
 * Polls resource groups + resources + latest metrics on an interval, and
 * re-fetches immediately whenever a `resource_status` SSE event arrives (so
 * the health glow updates without waiting for the next poll tick). Health glow
 * comes from resource.status, NEVER from a metric's is_anomaly.
 * ===========================================================================
 */
import { useEffect, useState } from "react";
import { api } from "./api";
import type { ResourceGroup, ResourceStatusEvent } from "./types";

export function useResourcesPoll(resourceStatusEvent: ResourceStatusEvent | null) {
  const [groups, setGroups] = useState<ResourceGroup[]>([]);
  const [error, setError] = useState<Error | null>(null);
  const [loadedOnce, setLoadedOnce] = useState(false);

  useEffect(() => {
    let active = true;
    const load = () => api.getResources().then((data) => {
      if (active) { setGroups(data.resource_groups); setLoadedOnce(true); setError(null); }
    }).catch((reason: unknown) => { if (active) setError(reason instanceof Error ? reason : new Error(String(reason))); });
    void load();
    const timer = window.setInterval(load, 2000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);

  useEffect(() => {
    if (!resourceStatusEvent) return;
    setGroups((current) => current.map((group) => ({
      ...group,
      resources: group.resources.map((resource) => resource.id === resourceStatusEvent.resource_id ? { ...resource, status: resourceStatusEvent.status } : resource),
    })));
  }, [resourceStatusEvent]);

  return { groups, error, loadedOnce };
}
