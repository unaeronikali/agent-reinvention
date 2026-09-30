// Shared status -> style helpers. Health/glow is ALWAYS derived from
// resource.status (Healthy/Degraded/Critical, from GET /api/resources and
// the `resource_status` SSE event) -- never from a sampler row's is_anomaly,
// which stays NULL by design on the continuously-appended live-sampler rows.
import type { ResourceStatus } from "./types";

export const STATUS_BADGE: Record<ResourceStatus, string> = {
  Healthy: "bg-emerald-950 text-emerald-400 border-emerald-700",
  Degraded: "bg-amber-950 text-amber-400 border-amber-700",
  Critical: "bg-red-950 text-red-400 border-red-700",
};

export const STATUS_DOT: Record<ResourceStatus, string> = {
  Healthy: "bg-emerald-400",
  Degraded: "bg-amber-400",
  Critical: "bg-red-500 animate-pulse",
};

// Block/feeder glow classes for the SLD (Critical pulses red; Degraded is a
// steady amber warning; Healthy has no glow).
export function glowClass(status: ResourceStatus): string {
  if (status === "Critical") return "ns-node-glow border-red-500";
  if (status === "Degraded") return "border-amber-500";
  return "border-zinc-700";
}

// Worst-of rollup for a resource group's Health Status pill.
export function worstStatus(statuses: ResourceStatus[]): ResourceStatus {
  if (statuses.includes("Critical")) return "Critical";
  if (statuses.includes("Degraded")) return "Degraded";
  return "Healthy";
}
