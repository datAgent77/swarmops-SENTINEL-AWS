"""Mission memory — shared, structured working memory passed between agents.

This is deliberately an abstraction, not prompt string-concatenation: agents read
and write typed fields (summary, prior reasoning, completed tasks, known risks,
handoffs, conversation, structured outputs). A compact projection is rendered
into each agent's prompt, but the source of truth is the structured object.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MissionMemory:
    objective: str
    mission_summary: str = ""
    reasoning_log: list[dict[str, str]] = field(default_factory=list)   # {agent, summary}
    completed_tasks: list[str] = field(default_factory=list)
    known_risks: list[str] = field(default_factory=list)
    handoffs: list[dict[str, str]] = field(default_factory=list)        # {from, to}
    conversation: list[dict[str, str]] = field(default_factory=list)    # {agent, message}
    outputs: dict[str, dict[str, Any]] = field(default_factory=dict)    # agent -> last output
    context_hint: str = ""  # verified context retrieved from the context layer (Senso)

    # --- writes ------------------------------------------------------------
    def add_reasoning(self, agent: str, summary: str) -> None:
        self.reasoning_log.append({"agent": agent, "summary": summary})

    def add_message(self, agent: str, message: str) -> None:
        self.conversation.append({"agent": agent, "message": message})

    def add_risks(self, risks: list[str]) -> None:
        for r in risks:
            if r and r not in self.known_risks:
                self.known_risks.append(r)

    def add_tasks(self, tasks: list[str]) -> None:
        for t in tasks:
            if t and t not in self.completed_tasks:
                self.completed_tasks.append(t)

    def record_handoff(self, from_agent: str, to_agent: str | None) -> None:
        self.handoffs.append({"from": from_agent, "to": to_agent or "-"})

    def record_output(self, agent: str, output: dict[str, Any]) -> None:
        self.outputs[agent] = output

    # --- reads -------------------------------------------------------------
    def prompt_context(self) -> str:
        """Compact text projection of memory for an agent's user prompt."""
        lines = [f"Mission objective: {self.objective}"]
        if self.mission_summary:
            lines.append(f"Summary so far: {self.mission_summary}")
        if self.reasoning_log:
            recent = self.reasoning_log[-4:]
            lines.append("Recent reasoning:")
            lines += [f"  - {r['agent']}: {r['summary']}" for r in recent]
        if self.known_risks:
            lines.append("Known risks: " + "; ".join(self.known_risks[:6]))
        if self.completed_tasks:
            lines.append("Tasks: " + "; ".join(self.completed_tasks[:6]))
        if self.conversation:
            last = self.conversation[-3:]
            lines.append("Recent messages:")
            lines += [f"  - {c['agent']}: {c['message']}" for c in last]
        if self.context_hint:
            lines.append(f"Verified context (Senso): {self.context_hint}")
        return "\n".join(lines)

    def snapshot(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "mission_summary": self.mission_summary,
            "reasoning_log": list(self.reasoning_log),
            "completed_tasks": list(self.completed_tasks),
            "known_risks": list(self.known_risks),
            "handoffs": list(self.handoffs),
            "conversation": list(self.conversation),
        }
