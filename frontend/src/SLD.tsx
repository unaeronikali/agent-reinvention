import type { ResourceGroup } from "./types";
import { glowClass, STATUS_DOT, worstStatus } from "./statusStyles";

export default function SLD({ groups, onSelectResource }: {
  groups: ResourceGroup[];
  onSelectResource: (id: number) => void;
}) {
  return (
    <section className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
      <div className="mb-4 flex items-center gap-3"><h2 className="text-sm font-bold text-zinc-100">NorthStar Production</h2><div className="h-px flex-1 bg-red-900" /><span className="h-3 w-3 rounded-full bg-red-500 shadow-[0_0_10px_#ef4444]" /></div>
      <div className="grid gap-5 md:grid-cols-2">
        {groups.map((group) => {
          const status = worstStatus(group.resources.map((resource) => resource.status));
          return <div key={group.id} className="relative border-l-2 border-zinc-700 pl-5"><div className="absolute -left-[7px] top-2 h-3 w-3 rounded-full bg-zinc-500" />
            <div className="mb-3 flex items-center justify-between"><span className="text-xs font-bold uppercase tracking-widest text-zinc-300">{group.name}</span><span className={`rounded border px-2 py-0.5 text-[10px] ${glowClass(status).replace("ns-node-glow ", "")}`}>{status}</span></div>
            <div className="space-y-2">{group.resources.map((resource) => <button key={resource.id} onClick={() => onSelectResource(resource.id)} className={`flex w-full items-center justify-between border bg-zinc-900/80 px-3 py-2 text-left transition hover:bg-zinc-800 ${glowClass(resource.status)}`}><span className="text-xs text-zinc-200">{resource.display_name ?? resource.name}</span><span className="flex items-center gap-2 text-[10px] text-zinc-500"><span className={`h-2 w-2 rounded-full ${STATUS_DOT[resource.status]}`} />{resource.status}</span></button>)}</div>
          </div>;
        })}
      </div>
    </section>
  );
}
