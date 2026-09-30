// Canvas: React Flow hub-and-spoke orchestration diagram, laid out per
// others/drawio/orch_002.drawio (boxy, rigid, top-down): Orchestrator on top,
// the Web App Executor (MCP Client) hub in the middle with the MCP Server to
// its right on the same row, and the 6 agents (Detect, Analyze, RCA, Suggest,
// Fix, Ticket) in a single row underneath. The Orchestrator and all 6 agents
// connect ONLY to the hub; the MCP Server connects to the hub via the MCP
// line. No agent<->agent or agent<->MCP edges. Node/edge glow state comes
// ONLY from the `canvas` SSE event (active_node + active_edge + mode) —
// never guessed locally.
import { useEffect, useMemo, useRef, useState } from "react";
import ReactFlow, {
  Background,
  Controls,
  Handle,
  Position,
  type Edge,
  type Node,
  type NodeProps,
  type ReactFlowInstance,
} from "reactflow";
import "reactflow/dist/style.css";
import type { CanvasEvent, CanvasMode, CanvasNode as CanvasNodeId } from "./types";

interface HandleSpec {
  type: "source" | "target";
  position: Position;
  id: string;
}

interface NodeSpec {
  id: string;
  label: string;
  x: number;
  y: number;
  isHub?: boolean;
  handles: HandleSpec[];
}

// Static hub-and-spoke topology (position + handle placement only; glow state
// is applied at render time from the latest `canvas` SSE event). Named handle
// ids let the straight edges attach to a specific side of each box (e.g. the
// 6 agents all fan into the Executor's single bottom handle) WITHOUT changing
// any node id or edge source/target -- purely a visual routing detail.
const NODE_SPECS: NodeSpec[] = [
  {
    id: "Orchestrator",
    label: "Orchestrator",
    x: 438,
    y: 10,
    handles: [{ type: "source", position: Position.Bottom, id: "src-bottom" }],
  },
  {
    id: "Executor",
    label: "MCP Client\n(Web App Server)",
    x: 438,
    y: 150,
    isHub: true,
    handles: [
      { type: "target", position: Position.Top, id: "tgt-top" },
      { type: "target", position: Position.Bottom, id: "tgt-bottom" },
      { type: "source", position: Position.Right, id: "src-right" },
    ],
  },
  {
    id: "MCP",
    label: "MCP Server\n(Tools)",
    x: 838,
    y: 150,
    handles: [{ type: "target", position: Position.Left, id: "tgt-left" }],
  },
  {
    id: "Detect",
    label: "Detect",
    x: 0,
    y: 320,
    handles: [{ type: "source", position: Position.Top, id: "src-top" }],
  },
  {
    id: "Analyze",
    label: "Analyze",
    x: 175,
    y: 320,
    handles: [{ type: "source", position: Position.Top, id: "src-top" }],
  },
  {
    id: "RCA",
    label: "RCA",
    x: 350,
    y: 320,
    handles: [{ type: "source", position: Position.Top, id: "src-top" }],
  },
  {
    id: "Suggest",
    label: "Suggest",
    x: 525,
    y: 320,
    handles: [{ type: "source", position: Position.Top, id: "src-top" }],
  },
  {
    id: "Fix",
    label: "Fix",
    x: 700,
    y: 320,
    handles: [{ type: "source", position: Position.Top, id: "src-top" }],
  },
  {
    id: "Ticket",
    label: "Ticket",
    x: 875,
    y: 320,
    handles: [{ type: "source", position: Position.Top, id: "src-top" }],
  },
];

// Static edges: every spoke connects ONLY to the hub ("Executor"). source/
// target ids mirror executor.py's _canvas_payload exactly so active_edge
// matching works:
//   agent nodes  -> {from: node, to: "Executor"}
//   MCP          -> {from: "Executor", to: "MCP"}
// sourceHandle/targetHandle only pick WHICH side of each box the straight
// line attaches to -- purely visual, same source/target node ids as before.
const EDGE_SPECS: {
  from: string;
  to: string;
  sourceHandle: string;
  targetHandle: string;
}[] = [
  { from: "Orchestrator", to: "Executor", sourceHandle: "src-bottom", targetHandle: "tgt-top" },
  { from: "Detect", to: "Executor", sourceHandle: "src-top", targetHandle: "tgt-bottom" },
  { from: "Analyze", to: "Executor", sourceHandle: "src-top", targetHandle: "tgt-bottom" },
  { from: "RCA", to: "Executor", sourceHandle: "src-top", targetHandle: "tgt-bottom" },
  { from: "Suggest", to: "Executor", sourceHandle: "src-top", targetHandle: "tgt-bottom" },
  { from: "Fix", to: "Executor", sourceHandle: "src-top", targetHandle: "tgt-bottom" },
  { from: "Ticket", to: "Executor", sourceHandle: "src-top", targetHandle: "tgt-bottom" },
  { from: "Executor", to: "MCP", sourceHandle: "src-right", targetHandle: "tgt-left" },
];

function nodeClassName(mode: CanvasMode | null): string {
  if (mode === "glow") return "ns-node-glow";
  if (mode === "slow_throb") return "ns-node-throb";
  return "ns-node-idle";
}

// Handles are attachment points only (for clean straight-line routing) --
// no visible connector dots in this static, read-only diagram.
const HIDDEN_HANDLE_STYLE = {
  opacity: 0,
  width: 1,
  height: 1,
  minWidth: 1,
  minHeight: 1,
  border: "none",
  background: "transparent",
} as const;

function OrchNode({ data }: NodeProps<{ label: string; handles: HandleSpec[] }>) {
  return (
    <>
      {data.handles.map((h) => (
        <Handle key={h.id} id={h.id} type={h.type} position={h.position} style={HIDDEN_HANDLE_STYLE} />
      ))}
      <span>{data.label}</span>
    </>
  );
}

const NODE_TYPES = { orch: OrchNode };

export default function Canvas({ canvas }: { canvas: CanvasEvent | null }) {
  const activeNode: CanvasNodeId | null = canvas?.active_node ?? null;
  const mode: CanvasMode | null = canvas?.mode ?? null;
  const activeEdge = canvas?.active_edge ?? null;

  const containerRef = useRef<HTMLDivElement | null>(null);
  const [rfInstance, setRfInstance] = useState<ReactFlowInstance | null>(null);

  // fitView only runs once on mount by default; the canvas cell's size can
  // change (narrower column, HITL panel expanding/collapsing, window resize)
  // so re-fit whenever the container itself resizes, keeping every node
  // (Orchestrator + Executor hub + 6 agents + MCP) visible without scrolling.
  useEffect(() => {
    if (!rfInstance || !containerRef.current) return;
    const el = containerRef.current;
    let raf = 0;
    const observer = new ResizeObserver((entries) => {
      const cr = entries[0]?.contentRect;
      // Skip 0-size frames during layout reflow (e.g. HITL panel appearing) —
      // calling fitView on a 0-width/height container blanks the graph
      // (React Flow error #004: "parent container needs a width and a height").
      if (!cr || cr.width < 1 || cr.height < 1) return;
      cancelAnimationFrame(raf);
      // Defer to the next frame so the browser has settled the new layout
      // before we re-fit; otherwise fitView measures stale dimensions.
      raf = requestAnimationFrame(() => {
        if (containerRef.current) rfInstance.fitView({ padding: 0.15 });
      });
    });
    observer.observe(el);
    return () => {
      cancelAnimationFrame(raf);
      observer.disconnect();
    };
  }, [rfInstance]);

  const nodes: Node[] = useMemo(
    () =>
      NODE_SPECS.map((spec) => {
        const isActive = activeNode === spec.id;
        return {
          id: spec.id,
          type: "orch",
          position: { x: spec.x, y: spec.y },
          data: { label: spec.label, handles: spec.handles },
          className: `${spec.isHub ? "ns-canvas-hub" : ""} ${
            isActive ? nodeClassName(mode) : "ns-node-idle"
          }`,
          style: {
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            whiteSpace: "pre-line",
            textAlign: "center",
            background: spec.isHub ? "#1e1b2e" : "#18181b",
            color: "#e5e7eb",
            border: spec.isHub ? "2px solid #71717a" : "1.5px solid #3f3f46",
            borderRadius: 3,
            padding: 6,
            fontSize: 14,
            fontWeight: spec.isHub ? 700 : 500,
            width: 150,
            height: 54,
          },
        };
      }),
    [activeNode, mode]
  );

  const edges: Edge[] = useMemo(
    () =>
      EDGE_SPECS.map((spec) => {
        const isActive =
          !!activeEdge &&
          activeEdge.from === spec.from &&
          activeEdge.to === spec.to;
        const cls =
          isActive && mode === "glow"
            ? "ns-edge-glow"
            : isActive && mode === "slow_throb"
              ? "ns-edge-throb"
              : "";
        return {
          id: `${spec.from}->${spec.to}`,
          source: spec.from,
          target: spec.to,
          sourceHandle: spec.sourceHandle,
          targetHandle: spec.targetHandle,
          type: "straight",
          className: cls,
          style: { stroke: "#52525b", strokeWidth: 1.5 },
        };
      }),
    [activeEdge, mode]
  );

  return (
    <section className="flex flex-col rounded-lg border border-zinc-800 bg-zinc-950 p-2">
      <div className="flex items-center justify-between px-2 pb-1">
        <h2 className="text-sm font-bold text-zinc-100">Orchestration Canvas</h2>
        {canvas && (
          <span className="text-[11px] text-zinc-500 font-mono">
            {canvas.status} · {canvas.active_node} ({canvas.mode})
          </span>
        )}
      </div>
      <div ref={containerRef} style={{ height: 440 }} className="rounded border border-zinc-900">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={NODE_TYPES}
          fitView
          fitViewOptions={{ padding: 0.15 }}
          onInit={setRfInstance}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#27272a" gap={20} />
          <Controls showInteractive={false} position="top-left" />
        </ReactFlow>
      </div>
    </section>
  );
}
