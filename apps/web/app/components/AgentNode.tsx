"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { AgentView } from "../lib/types";

const STATE_LABEL: Record<string, string> = {
  idle: "Idle",
  working: "Working",
  waiting_approval: "Awaiting approval",
  completed: "Done",
  blocked: "Blocked",
  quarantined: "Quarantined",
};

function scoreTone(score: number | null): string {
  if (score == null) return "";
  if (score >= 85) return "good";
  if (score >= 70) return "ok";
  return "low";
}

function AgentNodeInner({ data }: NodeProps) {
  const a = data as unknown as AgentView;
  const cls = [
    "agent-node",
    `s-${a.status}`,
    a.active ? "active" : "",
    a.pending ? "pending-gov" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={cls} role="group" aria-label={`${a.name}, ${a.role}, status ${STATE_LABEL[a.status] ?? a.status}`}>
      <Handle type="target" position={Position.Top} className="node-handle" />
      <div className="node-top">
        <div className="node-avatar" aria-hidden>
          {a.name.slice(0, 1)}
          <span className="node-status-dot" />
        </div>
        <div className="node-id">
          <strong title={a.name}>{a.name}</strong>
          <span title={a.role}>{a.role}</span>
        </div>
        <div className="node-ver" title={`Version ${a.version}`}>v{a.version}</div>
      </div>

      <div className="node-task" title={a.task ?? undefined}>
        {a.task ?? <span className="node-idle-text">Standing by</span>}
      </div>

      <div className="node-foot">
        <span className={`node-state st-${a.status}`}>{STATE_LABEL[a.status] ?? a.status}</span>
        {a.score != null ? (
          <span className={`node-score ${scoreTone(a.score)}`} title="Performance score">
            {a.score.toFixed(0)}
            <em>
              {a.trend === "up" ? "▲" : a.trend === "down" ? "▼" : ""}
            </em>
          </span>
        ) : null}
      </div>

      <div className="node-meta">
        <span className="node-model" title={a.provider ? `${a.provider} · ${a.model}` : "model"}>
          {a.model ? a.model : "—"}
        </span>
        <span className="node-cost" title="Cost this mission">${a.costUsd.toFixed(2)}</span>
      </div>

      {a.pending ? <span className="node-gov-flag" title="Upgrade pending governance">⚖ upgrade</span> : null}
      <Handle type="source" position={Position.Bottom} className="node-handle" />
    </div>
  );
}

export const AgentNode = memo(AgentNodeInner);
