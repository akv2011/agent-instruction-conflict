"""Cost projection and a spend ceiling.

The real guard is a spend limit set on the OpenRouter key itself. This is the
second layer: it refuses to start a batch whose projection would breach the
ceiling, and re-reads measured spend between batches rather than trusting its
own running total.

Prices come from OpenRouter's public table. Caching is ignored, so every figure
is an overestimate. Input cost is quadratic in step count because each step
resends the whole transcript.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path

import urllib.request

PRICES_PATH = Path(__file__).with_name("prices.json")

CEILING_USD = 7.00
TOTAL_BUDGET_USD = 10.00


class BudgetExceeded(RuntimeError):
    """Raised instead of spending money."""


@dataclass(frozen=True)
class Price:
    """Dollars per million tokens."""

    model: str
    per_m_in: float
    per_m_out: float

    def cost(self, tokens_in: int, tokens_out: int) -> float:
        return tokens_in / 1e6 * self.per_m_in + tokens_out / 1e6 * self.per_m_out


def load_prices(path: Path = PRICES_PATH) -> dict[str, Price]:
    """Parse the OpenRouter model list into a price lookup."""
    payload = json.loads(path.read_text())
    entries = payload.get("data", payload if isinstance(payload, list) else [])
    prices: dict[str, Price] = {}
    for entry in entries:
        model = entry.get("id")
        pricing = entry.get("pricing") or {}
        try:
            per_m_in = float(pricing["prompt"]) * 1e6
            per_m_out = float(pricing["completion"]) * 1e6
        except (KeyError, TypeError, ValueError):
            continue
        if model:
            prices[model] = Price(model, per_m_in, per_m_out)
    return prices


@dataclass(frozen=True)
class RolloutShape:
    """Token profile of one agentic rollout."""

    steps: int
    base_prompt_tokens: int = 1800
    context_added_per_step: int = 900
    output_tokens_per_step: int = 1100

    @property
    def tokens_in(self) -> int:
        """Cumulative input across steps: the transcript is resent every step."""
        return sum(
            self.base_prompt_tokens + step * self.context_added_per_step
            for step in range(self.steps)
        )

    @property
    def tokens_out(self) -> int:
        return self.steps * self.output_tokens_per_step


@dataclass(frozen=True)
class Batch:
    """A planned group of identical calls."""

    label: str
    model: str
    count: int
    shape: RolloutShape

    def cost(self, prices: dict[str, Price]) -> float:
        if self.model not in prices:
            raise KeyError("no price for " + self.model + "; refusing to guess")
        price = prices[self.model]
        return self.count * price.cost(self.shape.tokens_in, self.shape.tokens_out)


def project(batches: list[Batch], prices: dict[str, Price] | None = None) -> tuple[float, list[tuple[str, float]]]:
    """Total projected cost and the per-batch breakdown, largest first."""
    prices = prices or load_prices()
    rows = [(b.label + " (" + b.model + " x" + str(b.count) + ")", b.cost(prices)) for b in batches]
    rows.sort(key=lambda r: -r[1])
    return sum(cost for _, cost in rows), rows


def live_spend(timeout: float = 15.0) -> dict:
    """Measured spend on the current key. Requires OPENROUTER_API_KEY."""
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY not set; cannot read live spend")
    request = urllib.request.Request(
        "https://openrouter.ai/api/v1/key",
        headers={"Authorization": "Bearer " + key},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read())
    data = payload.get("data", payload)
    return {
        "usage": float(data.get("usage") or 0.0),
        "limit": data.get("limit"),
        "remaining": (
            None if data.get("limit") is None else float(data["limit"]) - float(data.get("usage") or 0.0)
        ),
    }


def assert_affordable(batches: list[Batch], ceiling: float = CEILING_USD) -> dict:
    """Refuse to run a batch group that could push spend past the ceiling.

    Uses measured spend, not the running total of prior estimates, so an
    estimate that was wrong earlier cannot compound into an overspend.
    """
    projected, rows = project(batches)
    state = live_spend()
    spent = state["usage"]
    if spent + projected > ceiling:
        raise BudgetExceeded(
            "would reach $"
            + format(spent + projected, ".2f")
            + " against a $"
            + format(ceiling, ".2f")
            + " ceiling (spent $"
            + format(spent, ".2f")
            + ", projected $"
            + format(projected, ".2f")
            + "). Shrink count or switch model."
        )
    return {"spent": spent, "projected": projected, "headroom": ceiling - spent - projected, "rows": rows}
