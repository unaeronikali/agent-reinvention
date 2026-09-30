// Per-metric display label + accent color (used by Live Metrics and the
// Trend Recorder charts). Real IT metric names only -- no electrical
// analogy wording ships in the app; that framing was discussion-only.

export interface MetricMeta {
  label: string; // real IT display label, e.g. "Response Time"
  unitFallback: string;
  color: string; // hex accent color for charts/badges
}

export const METRIC_META: Record<string, MetricMeta> = {
  response_time_ms: { label: "Response Time", unitFallback: "ms", color: "#38bdf8" },
  cpu_pct: { label: "CPU Usage", unitFallback: "%", color: "#f97316" },
  memory_pct: { label: "Memory Usage", unitFallback: "%", color: "#facc15" },
  error_rate_pct: { label: "Error Rate", unitFallback: "%", color: "#ef4444" },
  request_count: { label: "Request Count", unitFallback: "count", color: "#a78bfa" },
  connection_count: { label: "Connection Count", unitFallback: "count", color: "#34d399" },
};

// Fixed, stable order for grids/charts regardless of API row order.
export const METRIC_ORDER = [
  "response_time_ms",
  "cpu_pct",
  "memory_pct",
  "error_rate_pct",
  "request_count",
  "connection_count",
];

export function metaFor(metricName: string): MetricMeta {
  return (
    METRIC_META[metricName] ?? {
      label: formatMetricLabel(metricName),
      unitFallback: "",
      color: "#9ca3af",
    }
  );
}

export function formatMetricLabel(metricName: string): string {
  return (
    METRIC_META[metricName]?.label ??
    metricName
      .replace(/_/g, " ")
      .replace(/\bms\b/, "(ms)")
      .replace(/\bpct\b/, "%")
      .replace(/^./, (c) => c.toUpperCase())
  );
}
