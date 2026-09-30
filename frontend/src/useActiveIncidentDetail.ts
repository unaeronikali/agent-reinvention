/*
 * ============================== SKELETON STUB ==============================
 * useActiveIncidentDetail.ts -- fetch the active incident's detail
 *
 *   BUILD PHASE : 7 (frontend)   BUILT BY: the Phase 7 prompt in the Build Guide
 *
 * Loads GET /api/incident/active (and /api/incident/{id}) so the Orchestration
 * page can show incident status, RCA, fix options and the ticket draft. Takes
 * a `versionToken` string and re-fetches whenever it changes (bump the token
 * from status/hitl/resolved SSE events to refresh).
 * ===========================================================================
 */
import { useEffect, useState } from "react";
import { api } from "./api";
import type { ActiveIncidentResponse } from "./types";

export function useActiveIncidentDetail(versionToken: string): ActiveIncidentResponse | null {
  const [detail, setDetail] = useState<ActiveIncidentResponse | null>(null);
  useEffect(() => {
    let active = true;
    api.getActiveIncident().then((value) => { if (active) setDetail(value); }).catch(() => { if (active) setDetail(null); });
    return () => { active = false; };
  }, [versionToken]);
  return detail;
}
