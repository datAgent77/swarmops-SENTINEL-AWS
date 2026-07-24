"use client";

import { BaseEdge, getBezierPath, type EdgeProps } from "@xyflow/react";

// A hierarchy edge that, when `active`, sends a light particle travelling from
// parent to child to visualize a message/handoff. Uses SVG animateMotion so the
// motion runs on the compositor and stays smooth. Respects reduced-motion via a
// css class toggle handled on <html>.
export function MessageEdge(props: EdgeProps) {
  const { sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data, markerEnd } = props;
  const [path] = getBezierPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition });
  const active = Boolean((data as { active?: boolean } | undefined)?.active);

  return (
    <>
      <BaseEdge
        id={props.id}
        path={path}
        markerEnd={markerEnd}
        style={{
          stroke: active ? "var(--accent)" : "var(--edge)",
          strokeWidth: active ? 2 : 1.25,
          transition: "stroke 240ms ease, stroke-width 240ms ease",
        }}
      />
      {active ? (
        <circle r="3.4" fill="var(--accent)" className="edge-particle">
          <animateMotion dur="1.1s" repeatCount="indefinite" path={path} />
        </circle>
      ) : null}
    </>
  );
}
