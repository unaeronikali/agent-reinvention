import { NavLink } from "react-router-dom";

export default function NavBar({ connected }: { connected: boolean }) {
  const linkClass = ({ isActive }: { isActive: boolean }) => `border-b-2 px-3 py-4 text-xs font-semibold uppercase tracking-widest ${isActive ? "border-emerald-400 text-zinc-100" : "border-transparent text-zinc-500 hover:text-zinc-200"}`;
  return (
    <nav className="sticky top-0 z-20 flex items-center justify-between border-b border-zinc-800 bg-[#0a0a0d]/95 px-4 backdrop-blur">
      <div className="flex items-center gap-6">
        <div className="text-sm font-bold tracking-tight text-zinc-100">Error Budget <span className="text-emerald-400">Watcher</span></div>
        <div className="flex gap-1"><NavLink to="/" className={linkClass}>Dashboard</NavLink><NavLink to="/orchestration" className={linkClass}>Orchestration</NavLink></div>
      </div>
      <div className={`flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider ${connected ? "text-emerald-400" : "text-red-400"}`}>
        <span className={`h-2 w-2 rounded-full ${connected ? "bg-emerald-400" : "animate-pulse bg-red-500"}`} />
        {connected ? "Stream connected" : "Stream disconnected"}
      </div>
    </nav>
  );
}
