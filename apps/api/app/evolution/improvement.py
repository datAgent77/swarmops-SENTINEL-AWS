"""ImprovementEngine — turns detected weaknesses into structured suggestions.

Deterministic, rule-based mapping (weakness → suggestion, expected impact,
category, stored non-code change, and projected metric delta). The category
drives risk classification in EvolutionPolicy; the stored `changes` are DATA
(prompts, planning heuristics, tool preferences) — never executable code.
"""

from __future__ import annotations

from app.evolution.policy import EvolutionPolicy

# weakness code -> suggestion template
_RULES: dict[str, dict] = {
    "high_deployment_approval_rate": {
        "suggestion": "Always generate a rollback plan before requesting a production deploy.",
        "expected_impact": "Lower approval risk and faster human sign-off.",
        "category": "planning",
        "changes": {"planning_heuristics": ["Generate a rollback plan before every production deploy"]},
        "projected": {"score": 3.0, "approval_count": -1},
    },
    "poor_task_decomposition": {
        "suggestion": "Split authentication and authorization into separate tasks.",
        "expected_impact": "Clearer ownership and better testability.",
        "category": "planning",
        "changes": {"planning_heuristics": ["Split auth into authentication + authorization tasks"]},
        "projected": {"score": 3.0, "task_success_rate": 0.05},
    },
    "too_many_retries": {
        "suggestion": "Add an assumption-check step before acting to reduce retries.",
        "expected_impact": "Fewer failed attempts and lower latency.",
        "category": "reasoning",
        "changes": {"reasoning_heuristics": ["Verify assumptions before acting"]},
        "projected": {"score": 4.0, "retry_count": -2},
    },
    "repeated_qa_failures": {
        "suggestion": "Expand regression coverage for authentication edge cases.",
        "expected_impact": "Fewer escaped defects.",
        "category": "planning",
        "changes": {"planning_heuristics": ["Add auth regression tests to the QA plan"]},
        "projected": {"score": 4.0},
    },
    "high_security_violations": {
        "suggestion": "Never request customer_database.export directly; route data needs "
                      "through an authorized security review first.",
        "expected_impact": "Eliminate blocked, unauthorized data-access attempts.",
        "category": "security",  # HIGH-risk → requires approval
        "changes": {"tool_preferences": {"avoid": ["customer_database.export"]}},
        "projected": {"score": 5.0, "blocked_actions": -1},
    },
    "budget_overrun": {
        "suggestion": "Prefer a cheaper model tier for routine reasoning steps.",
        "expected_impact": "Lower cost per mission with equivalent quality.",
        "category": "budget",  # HIGH-risk → requires approval
        "changes": {"budget": {"prefer_tier": "flash-lite"}},
        "projected": {"score": 3.0, "estimated_cost": -0.10},
    },
    "low_reasoning_confidence": {
        "suggestion": "Gather one more supporting data point before committing to a plan.",
        "expected_impact": "Higher decision confidence.",
        "category": "reasoning",
        "changes": {"reasoning_heuristics": ["Seek one corroborating signal before deciding"]},
        "projected": {"score": 3.0, "reasoning_quality": 0.1},
    },
}


class ImprovementEngine:
    def __init__(self, policy: EvolutionPolicy | None = None) -> None:
        self.policy = policy or EvolutionPolicy()

    def suggest(self, weaknesses: list[dict]) -> list[dict]:
        """Return structured improvement suggestions for the detected weaknesses."""
        suggestions: list[dict] = []
        seen: set[str] = set()
        for weakness in weaknesses:
            code = weakness.get("code")
            if code in seen or code not in _RULES:
                continue
            seen.add(code)
            rule = _RULES[code]
            suggestions.append({
                "weakness": code,
                "suggestion": rule["suggestion"],
                "expected_impact": rule["expected_impact"],
                "risk": self.policy.classify(rule["category"]).value,
                "category": rule["category"],
                "changes": rule["changes"],
                "projected": rule["projected"],
            })
        return suggestions

    @staticmethod
    def merge_changes(suggestions: list[dict]) -> dict:
        merged: dict = {}
        for s in suggestions:
            for key, value in s.get("changes", {}).items():
                if isinstance(value, list):
                    merged.setdefault(key, [])
                    merged[key].extend(v for v in value if v not in merged[key])
                elif isinstance(value, dict):
                    merged.setdefault(key, {})
                    merged[key].update(value)
                else:
                    merged[key] = value
        return merged

    @staticmethod
    def projected_delta(current_score: float, suggestions: list[dict]) -> dict:
        score_gain = round(sum(float(s["projected"].get("score", 0.0)) for s in suggestions), 2)
        metric_proj: dict = {}
        for s in suggestions:
            for key, value in s["projected"].items():
                if key == "score":
                    continue
                metric_proj[key] = round(metric_proj.get(key, 0.0) + float(value), 4)
        after = round(min(100.0, current_score + score_gain), 2)
        return {"score_before": current_score, "score_after": after,
                "score_gain": score_gain, "metric_projections": metric_proj}
