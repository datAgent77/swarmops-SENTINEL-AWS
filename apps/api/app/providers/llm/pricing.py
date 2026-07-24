"""Token → cost estimation, isolated so pricing is easy to adjust."""

from __future__ import annotations

from decimal import Decimal

from app.providers.llm.base import LLMUsage

# USD per 1M tokens. Defaults approximate Gemini 1.5 Flash; the Mock provider
# reuses these so token/cost tracking is demonstrable even without a real key.
_PRICES: dict[str, tuple[Decimal, Decimal]] = {
    "gemini-2.5-flash": (Decimal("0.30"), Decimal("2.50")),
    "gemini-2.5-flash-lite": (Decimal("0.10"), Decimal("0.40")),
    "gemini-2.5-pro": (Decimal("1.25"), Decimal("10.00")),
    "gemini-1.5-flash": (Decimal("0.075"), Decimal("0.30")),
    "gemini-1.5-pro": (Decimal("1.25"), Decimal("5.00")),
    "claude-3-5-sonnet-latest": (Decimal("3.00"), Decimal("15.00")),
    "claude-3-5-haiku-latest": (Decimal("0.80"), Decimal("4.00")),
    "gpt-4o": (Decimal("2.50"), Decimal("10.00")),
    "gpt-4o-mini": (Decimal("0.15"), Decimal("0.60")),
    "mock-1": (Decimal("0.075"), Decimal("0.30")),
}

_DEFAULT = (Decimal("0.075"), Decimal("0.30"))
_PER_MILLION = Decimal(1_000_000)


def estimate_cost(model: str, usage: LLMUsage) -> Decimal:
    price_in, price_out = _PRICES.get(model, _DEFAULT)
    cost = (Decimal(usage.input_tokens) * price_in + Decimal(usage.output_tokens) * price_out) / _PER_MILLION
    # Round to 6 dp for storage; per-call costs are tiny.
    return cost.quantize(Decimal("0.000001"))
