import type { ResourceGroup, ThresholdInfo } from "./types";
import { METRIC_ORDER, metaFor } from "./metricMeta";

export default function LiveMetrics({ groups, thresholdsByResource, onSelectResource }: {
  groups: ResourceGroup[];
  thresholdsByResource: Record<number, Record<string, ThresholdInfo>>;
  onSelectResource: (id: number) => void;
}) {
  const tone = (value: number, threshold?: ThresholdInfo) => {
    if (!threshold?.comparison || threshold.critical_value === null || threshold.warning_value === null) return "text-zinc-200";
    const critical = threshold.comparison === "gt" ? value >= threshold.critical_value : value <= threshold.critical_value;
    const warning = threshold.comparison === "gt" ? value >= threshold.warning_value : value <= threshold.warning_value;
    return critical ? "text-red-400" : warning ? "text-amber-400" : "text-zinc-200";
  };
  return <section className="rounded-lg border border-zinc-800 bg-zinc-950 p-4"><div className="mb-3 flex items-baseline justify-between"><h2 className="text-sm font-bold text-zinc-100">Live Metrics</h2><span className="text-[10px] uppercase tracking-widest text-zinc-600">Live sampler</span></div><div className="overflow-x-auto"><table className="w-full min-w-[900px] border-collapse text-left text-xs"><thead><tr className="border-b border-zinc-800 text-[10px] uppercase tracking-wider text-zinc-500"><th className="px-2 py-2">Resource</th>{METRIC_ORDER.map((name) => <th key={name} className="px-2 py-2">{metaFor(name).label}</th>)}</tr></thead><tbody>{groups.flatMap((group) => group.resources.map((resource) => <tr key={resource.id} onClick={() => onSelectResource(resource.id)} className="cursor-pointer border-b border-zinc-900 hover:bg-zinc-900"><td className="px-2 py-3 font-medium text-zinc-300">{resource.display_name ?? resource.name}</td>{METRIC_ORDER.map((name) => { const metric = resource.metrics.find((item) => item.metric_name === name); return <td key={name} className={`px-2 py-3 font-mono ${tone(metric?.value ?? 0, thresholdsByResource[resource.id]?.[name])}`}>{metric ? `${metric.value.toLocaleString()} ${metric.unit ?? metaFor(name).unitFallback}` : "--"}</td>; })}</tr>))}</tbody></table></div></section>;
}
