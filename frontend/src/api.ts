/*
 * ============================== SKELETON STUB ==============================
 * api.ts -- typed REST client (fetch wrappers around /api/*)
 *
 *   BUILD PHASE : 7 (frontend)   BUILT BY: the Phase 7 prompt in the Build Guide
 *
 * One function per REST endpoint in backend/main.py (GATE D). Vite proxies
 * /api/* -> :8000 (see vite.config.ts, frozen). Return types come from
 * types.ts (frozen). Endpoints to wrap:
 *   getResources · getResourceHistory · getScenarios · getActiveIncident
 *   getIncident · getActivity · injectFault · restoreNormal · approveFix
 *   submitTicket   (SSE /api/stream is consumed by useEventStream, not here)
 * ===========================================================================
 */

import type {
	ActiveIncidentResponse,
	AgentActivity,
	ResourceHistoryResponse,
	ResourcesResponse,
	ScenariosResponse,
} from "./types";

async function json<T>(res: Response): Promise<T> {
	if (!res.ok) {
		let detail = res.statusText;
		try {
			const body = (await res.json()) as { detail?: string };
			detail = body.detail ?? detail;
		} catch {
			// Preserve the HTTP status when the error body is not JSON.
		}
		throw new Error(`${res.status} ${detail}`);
	}
	return (await res.json()) as T;
}

const get = <T>(path: string) => fetch(path).then((res) => json<T>(res));
const post = <T>(path: string, body: unknown) => fetch(path, {
	method: "POST",
	headers: { "Content-Type": "application/json" },
	body: JSON.stringify(body),
}).then((res) => json<T>(res));

export const api = {
	health: () => get<Record<string, unknown>>("/api/health"),
	getResources: () => get<ResourcesResponse>("/api/resources"),
	getScenarios: () => get<ScenariosResponse>("/api/scenarios"),
	getActiveIncident: () => get<ActiveIncidentResponse>("/api/incident/active"),
	getResourceHistory: (id: number, minutes = 15) => get<ResourceHistoryResponse>(`/api/resources/${id}/history?minutes=${minutes}`),
	getActivity: (incidentId: number) => get<{ activity: AgentActivity[] }>(`/api/activity?incident_id=${incidentId}`),
	injectFault: (scenario_id: number, auto_approve = false) => post<{ incident_id: number }>("/api/fault/inject", { scenario_id, auto_approve }),
	restoreNormal: () => post<Record<string, unknown>>("/api/fault/restore", {}),
	submitFixApproval: (incident_id: number, fix_id: number) => post<Record<string, unknown>>("/api/hitl/fix", { incident_id, fix_id }),
	submitTicket: (incident_id: number, ticket_final: string) => post<Record<string, unknown>>("/api/hitl/ticket", { incident_id, ticket_final }),
};
