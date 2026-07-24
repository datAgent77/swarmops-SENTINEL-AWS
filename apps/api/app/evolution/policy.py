"""EvolutionPolicy — deterministic risk classification for agent improvements.

High-risk categories require human/governance approval before a version can be
activated; low-risk categories may auto-approve. This is the *governed* gate that
guarantees agents never silently change security-relevant behavior.
"""

from __future__ import annotations

from app.domain.enums import RiskLevel

# Changes to any of these require approval before activation.
HIGH_RISK_CATEGORIES: frozenset[str] = frozenset(
    {"system_prompt", "tool_permissions", "allowed_actions", "budget", "security"}
)

# These may auto-approve.
LOW_RISK_CATEGORIES: frozenset[str] = frozenset(
    {"formatting", "communication", "planning", "reasoning", "memory", "tool_preference"}
)


class EvolutionPolicy:
    def classify(self, category: str) -> RiskLevel:
        return RiskLevel.HIGH if category in HIGH_RISK_CATEGORIES else RiskLevel.LOW

    def classify_many(self, categories: list[str]) -> RiskLevel:
        """A version is high-risk if ANY of its improvements is high-risk."""
        return RiskLevel.HIGH if any(self.classify(c) is RiskLevel.HIGH for c in categories) else RiskLevel.LOW

    def requires_approval(self, risk: RiskLevel) -> bool:
        return risk is RiskLevel.HIGH
