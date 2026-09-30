// Shared TypeScript types mirroring the FROZEN GATE D REST + SSE contract.
// Do not add fields that aren't in the contract; if something is missing,
// escalate rather than guessing.

export type ResourceStatus = "Healthy" | "Degraded" | "Critical";

export interface Metric {
  metric_name: string;
  value: number;
  unit: string | null;
  recorded_at: string;
  is_anomaly: number | null; // 0 / 1 / null (not yet evaluated)
}

export interface Resource {
  id: number;
  resource_group_id: number;
  name: string;
  type: string;
  display_name: string | null;
  icon: string | null;
  status: ResourceStatus;
  status_updated_at: string | null;
  metrics: Metric[];
}

export interface ResourceGroup {
  id: number;
  name: string;
  description: string | null;
  resources: Resource[];
}

export interface ResourcesResponse {
  resource_groups: ResourceGroup[];
}

export type Severity = "P1" | "P2" | "P3";

export interface Scenario {
  id: number;
  name: string;
  description: string | null;
  affected_resource_id: number;
  severity: Severity;
}

export interface ScenariosResponse {
  scenarios: Scenario[];
}

export type ReliabilityRisk = "LOW" | "MEDIUM" | "HIGH";

export interface ReliabilitySnapshot {
  slo_target: number;
  window_minutes: number;
  availability: number;
  error_rate_pct: number;
  budget_total_minutes: number;
  budget_consumed_minutes: number;
  budget_remaining_minutes: number;
  budget_remaining_pct: number;
  burn_rate: number;
  risk: ReliabilityRisk;
  reasons: string[];
  minutes_to_exhaustion: number | null;
  recommendations: string[];
  observed_at: string;
}

export interface ReliabilityResponse {
  resource: Pick<Resource, "id" | "name" | "display_name">;
  snapshot: ReliabilitySnapshot;
  evidence_window_minutes: number;
}

export type IncidentStatus =
  | "DETECTING"
  | "ANALYZING"
  | "DIAGNOSING"
  | "AWAITING_FIX_APPROVAL"
  | "FIXING"
  | "AWAITING_TICKET_APPROVAL"
  | "RESOLVED";

export interface Incident {
  id: number;
  scenario_id: number;
  resource_id: number;
  status: IncidentStatus;
  is_active: number;
  detected_at: string;
  resolved_at: string | null;
  rca_summary: string | null;
  ticket_draft: string | null;
  ticket_final: string | null;
  servicenow_ticket_no: string | null;
}

export interface IncidentFix {
  id: number;
  incident_id: number;
  description: string;
  display_order: number | null;
  is_selected: number;
}

export type MessageType = "INFO" | "WARNING" | "ERROR" | "HUMAN";

export interface AgentActivity {
  id: number;
  incident_id: number;
  agent_name: string;
  message_type: MessageType;
  message: string;
  created_at: string;
}

export interface ActiveIncidentResponse {
  incident: Incident | null;
  scenario?: Scenario;
  resource?: Resource;
  activity?: AgentActivity[];
  fixes?: IncidentFix[];
}

// ---------------------------------------------------------------------
// SSE event payloads (server -> client only, via GET /api/stream)
// ---------------------------------------------------------------------
// NOTE: verified against the running backend (main.py's /api/stream) --
// `active_incident` here is the RAW incidents row (or null), i.e.
// db.get_active_incident()'s return value, NOT the wrapped
// {incident, scenario, resource, activity, fixes} shape that
// GET /api/incident/active returns. The GATE D one-liner "connected
// {active_incident}" was ambiguous on this point; runtime behavior wins.
export interface ConnectedEvent {
  active_incident: Incident | null;
}

export type ActivityEvent = AgentActivity;

export interface StatusEvent {
  incident_id: number;
  status: IncidentStatus;
}

export const CANVAS_AGENT_NODES = [
  "Orchestrator",
  "Detect",
  "Analyze",
  "RCA",
  "Suggest",
  "Fix",
  "Ticket",
] as const;

export type CanvasAgentNode = (typeof CANVAS_AGENT_NODES)[number];
export type CanvasNode = CanvasAgentNode | "MCP";
export type CanvasMode = "glow" | "slow_throb" | "idle";

export interface CanvasEdge {
  from: string;
  to: string;
}

export interface CanvasEvent {
  incident_id: number;
  active_node: CanvasNode;
  active_edge: CanvasEdge | null;
  mode: CanvasMode;
  status: IncidentStatus;
}

export interface ToolEvent {
  incident_id: number;
  agent: string;
  tool: string;
  phase: "call" | "result";
  result?: unknown;
}

export interface ResourceStatusEvent {
  incident_id: number;
  resource_id: number;
  status: ResourceStatus;
}

export interface FixOption {
  id: number;
  display_order: number | null;
  description: string;
}

export interface Hitl1Event {
  incident_id: number;
  hitl: 1;
  fix_options: FixOption[];
}

export interface Hitl2Event {
  incident_id: number;
  hitl: 2;
  ticket_draft: string | null;
}

export type HitlEvent = Hitl1Event | Hitl2Event;

export interface ResolvedEvent {
  incident_id: number;
  status: "RESOLVED";
  servicenow_ticket_no: string | null;
}

export interface ErrorEvent {
  incident_id: number | null;
  message: string;
}

// ---------------------------------------------------------------------
// Additive: GET /api/resources/{id}/history?minutes= (new endpoint, not
// part of the original GATE D freeze -- verified against the running
// backend's main.py + db.get_metric_history / db.get_thresholds).
// ---------------------------------------------------------------------
export interface MetricHistoryPoint {
  recorded_at: string;
  value: number;
  unit: string | null;
}

export interface ThresholdInfo {
  normal_min: number | null;
  normal_max: number | null;
  warning_value: number | null;
  critical_value: number | null;
  comparison: "gt" | "lt" | null;
  unit: string | null;
}

export interface ResourceHistoryResponse {
  resource_id: number;
  window_minutes: number;
  metrics: Record<string, MetricHistoryPoint[]>;
  thresholds: Record<string, ThresholdInfo>;
}
