"""Print key validity, measured spend, and the projected cost of the full run.

Run this before any batch and again between batches. It reads spend from
OpenRouter rather than from a local tally, so a wrong estimate cannot compound.
"""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from injection.budget import (  # noqa: E402
    CEILING_USD,
    TOTAL_BUDGET_USD,
    Batch,
    RolloutShape,
    live_spend,
    load_prices,
    project,
)

ROLLOUT = RolloutShape(steps=15)
JUDGE = RolloutShape(steps=1, base_prompt_tokens=3000, context_added_per_step=0, output_tokens_per_step=250)
ASK = RolloutShape(steps=1, base_prompt_tokens=1200, context_added_per_step=0, output_tokens_per_step=500)

CHEAP = "openai/gpt-oss-120b"
SECOND = "deepseek/deepseek-v4-flash-0731"
EXPENSIVE = "anthropic/claude-haiku-4.5"

PLAN = [
    Batch("2x2 + controls, model A", CHEAP, 300, ROLLOUT),
    Batch("2x2 + controls, model B", SECOND, 300, ROLLOUT),
    Batch("third-person asks", CHEAP, 600, ASK),
    Batch("CoT coding judge", CHEAP, 600, JUDGE),
]


def main() -> None:
    prices = load_prices()
    print(f"price table: {len(prices)} models\n")

    print("=== one 15-step rollout, cost by model ===")
    for model in (CHEAP, "openai/gpt-oss-20b", SECOND, EXPENSIVE):
        if model not in prices:
            print(f"  {model:34} NOT PRICED")
            continue
        per = prices[model].cost(ROLLOUT.tokens_in, ROLLOUT.tokens_out)
        print(f"  {model:34} ${per:.5f}/rollout    600 rollouts = ${per * 600:8.2f}")
    print(f"\n  (a rollout is {ROLLOUT.tokens_in:,} input + {ROLLOUT.tokens_out:,} output tokens)")

    total, rows = project(PLAN, prices)
    print("\n=== projected full run ===")
    for label, cost in rows:
        print(f"  ${cost:6.3f}  {label}")
    print(f"  ------")
    print(f"  ${total:6.3f}  TOTAL   (ceiling ${CEILING_USD:.2f}, budget ${TOTAL_BUDGET_USD:.2f})")

    try:
        state = live_spend()
    except Exception as exc:
        print(f"\nlive spend unavailable: {type(exc).__name__}: {str(exc)[:160]}")
        return
    limit = "NONE SET (uncapped)" if state["limit"] is None else f"${float(state['limit']):.2f}"
    print("\n=== live key state ===")
    print(f"  measured spend : ${state['usage']:.4f}")
    print(f"  key spend cap  : {limit}")
    print(f"  headroom to ceiling after this run: ${CEILING_USD - state['usage'] - total:.2f}")


if __name__ == "__main__":
    main()
