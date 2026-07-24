"use client";

import { useEffect, useRef } from "react";
import type { EventItem } from "../lib/types";

// Renders inter-agent conversation (agent.message events) as a chat stream.
export function ConversationPanel({
  events,
  nameOf,
  reducedMotion,
}: {
  events: EventItem[];
  nameOf: (key: string) => string;
  reducedMotion: boolean;
}) {
  const endRef = useRef<HTMLDivElement | null>(null);
  const messages = events.filter((e) => e.type === "agent.message");

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "end" });
  }, [messages.length, reducedMotion]);

  if (messages.length === 0) {
    return <div className="empty">The workforce hasn&apos;t started talking yet.</div>;
  }

  return (
    <div className="chat" aria-label="Agent conversation">
      {messages.map((e) => (
        <div key={e.seq} className={`chat-row ${reducedMotion ? "" : "enter"}`}>
          <div className={`chat-avatar av-${e.actor_id}`} aria-hidden>
            {nameOf(e.actor_id).slice(0, 1)}
          </div>
          <div className="chat-bubble">
            <span className="chat-name">{nameOf(e.actor_id)}</span>
            <p>{e.message}</p>
          </div>
        </div>
      ))}
      <div ref={endRef} />
    </div>
  );
}
