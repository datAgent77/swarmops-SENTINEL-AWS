"use client";

import { useEffect, useRef } from "react";
import type { EventItem } from "../lib/types";
import { eventMeta } from "../lib/derive";

function clock(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch {
    return "";
  }
}

export function Timeline({
  events,
  nameOf,
  reducedMotion,
}: {
  events: EventItem[];
  nameOf: (key: string) => string;
  reducedMotion: boolean;
}) {
  const endRef = useRef<HTMLDivElement | null>(null);
  const count = events.length;

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "end" });
  }, [count, reducedMotion]);

  if (events.length === 0) {
    return <div className="empty">Launch a mission to stream the governed activity log.</div>;
  }

  return (
    <ol className="timeline" aria-live="polite" aria-label="Mission activity timeline">
      {events.map((e) => {
        const m = eventMeta(e);
        const who = e.actor_id === "system" ? "System" : nameOf(e.actor_id);
        return (
          <li key={e.seq} className={`tl-item sev-${m.severity} k-${m.kind} ${reducedMotion ? "" : "enter"}`}>
            <div className={`tl-icon sev-${m.severity}`} aria-hidden>
              {m.icon}
            </div>
            <div className="tl-body">
              <div className="tl-head">
                <span className="tl-actor">{who}</span>
                {m.governance ? <span className="tl-gov">GOVERNANCE</span> : null}
                {m.kind === "block" ? <span className="tl-sev danger">blocked</span> : null}
                {m.severity === "warning" && m.kind === "approval" ? (
                  <span className="tl-sev warn">needs approval</span>
                ) : null}
                <span className="tl-time">{clock(e.created_at)}</span>
              </div>
              <p className="tl-msg">{e.message}</p>
            </div>
          </li>
        );
      })}
      <div ref={endRef} />
    </ol>
  );
}
