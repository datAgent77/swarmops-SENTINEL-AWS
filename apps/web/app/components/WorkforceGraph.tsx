"use client";

import { useEffect } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
  useReactFlow,
  useNodesInitialized,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { AgentNode } from "./AgentNode";
import { MessageEdge } from "./MessageEdge";
import type { AgentView } from "../lib/types";

const nodeTypes = { agent: AgentNode };
const edgeTypes = { message: MessageEdge };

const POS: Record<string, { x: number; y: number }> = {
  ceo: { x: 300, y: 8 },
  pm: { x: 300, y: 158 },
  developer: { x: 12, y: 320 },
  security: { x: 204, y: 320 },
  qa: { x: 396, y: 320 },
  finance: { x: 588, y: 320 },
};

const LINKS: [string, string][] = [
  ["ceo", "pm"],
  ["pm", "developer"],
  ["pm", "security"],
  ["pm", "qa"],
  ["pm", "finance"],
];

function buildNodes(agents: AgentView[]): Node[] {
  return agents.map((a) => ({
    id: a.key,
    type: "agent",
    position: POS[a.key] ?? { x: 0, y: 0 },
    data: a as unknown as Record<string, unknown>,
    draggable: false,
    selectable: false,
  }));
}

function buildEdges(activeKey: string | null): Edge[] {
  return LINKS.map(([source, target]) => ({
    id: `${source}-${target}`,
    source,
    target,
    type: "message",
    data: { active: target === activeKey || source === activeKey },
  }));
}

function GraphInner({ agents, reducedMotion }: { agents: AgentView[]; reducedMotion: boolean }) {
  const activeKey = agents.find((a) => a.active)?.key ?? null;
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>(buildNodes(agents));
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>(buildEdges(activeKey));
  const initialized = useNodesInitialized();
  const { fitView } = useReactFlow();

  // Refresh node data in place (keeps React Flow's measured sizes intact).
  useEffect(() => {
    setNodes((prev) =>
      agents.map((a) => {
        const existing = prev.find((n) => n.id === a.key);
        return {
          id: a.key,
          type: "agent",
          position: POS[a.key] ?? { x: 0, y: 0 },
          data: a as unknown as Record<string, unknown>,
          draggable: false,
          selectable: false,
          ...(existing?.measured ? { measured: existing.measured, width: existing.width, height: existing.height } : {}),
        };
      }),
    );
  }, [agents, setNodes]);

  useEffect(() => {
    setEdges(buildEdges(activeKey));
  }, [activeKey, setEdges]);

  // Fit the view once nodes have real measured dimensions.
  useEffect(() => {
    if (initialized) fitView({ padding: 0.2, duration: reducedMotion ? 0 : 320, maxZoom: 1.1 });
  }, [initialized, fitView, reducedMotion]);

  // Re-fit on viewport resize / orientation change so the graph never clips on
  // tablet/mobile widths (interaction is disabled, so the user can't recenter).
  useEffect(() => {
    if (!initialized) return;
    let raf = 0;
    const onResize = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => fitView({ padding: 0.2, maxZoom: 1.1 }));
    };
    window.addEventListener("resize", onResize);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
    };
  }, [initialized, fitView]);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      fitView
      fitViewOptions={{ padding: 0.2, maxZoom: 1.1 }}
      minZoom={0.35}
      maxZoom={1.4}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable={false}
      panOnDrag={false}
      panOnScroll={false}
      zoomOnScroll={false}
      zoomOnPinch={false}
      zoomOnDoubleClick={false}
      preventScrolling={false}
      proOptions={{ hideAttribution: true }}
    >
      <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="#1b2333" />
    </ReactFlow>
  );
}

export function WorkforceGraph({ agents, reducedMotion = false }: { agents: AgentView[]; reducedMotion?: boolean }) {
  return (
    <div className="graph-canvas">
      <ReactFlowProvider>
        <GraphInner agents={agents} reducedMotion={reducedMotion} />
      </ReactFlowProvider>
    </div>
  );
}
