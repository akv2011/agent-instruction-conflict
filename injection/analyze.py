"""Headline numbers with intervals.

Wilson intervals rather than the normal approximation, because several cells sit
at 0 or 1 where the approximation gives bounds outside [0,1].
"""

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CHANNEL = {
    "system_reasoned": "system prompt",
    "system_bare": "system prompt",
    "pyproject_reasoned": "pyproject comment",
    "pyproject_bare": "pyproject comment",
    "agents_reasoned": "AGENTS.md on disk",
    "agents_bare": "AGENTS.md on disk",
}
CONTROLS = {"none", "benign_system", "benign_agents"}


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval. Returns (low, high) as proportions."""
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def fisher_exact_greater(a: int, b: int, c: int, d: int) -> float:
    """One-sided Fisher exact p for a 2x2 table [[a,b],[c,d]]."""
    n = a + b + c + d
    row1, col1 = a + b, a + c

    def logchoose(n_, k_):
        if k_ < 0 or k_ > n_:
            return float("-inf")
        return math.lgamma(n_ + 1) - math.lgamma(k_ + 1) - math.lgamma(n_ - k_ + 1)

    total = 0.0
    denom = logchoose(n, col1)
    for x in range(max(0, col1 - (n - row1)), min(row1, col1) + 1):
        if x >= a:
            total += math.exp(logchoose(row1, x) + logchoose(n - row1, col1 - x) - denom)
    return min(1.0, total)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", default="results/outcomes.jsonl")
    parser.add_argument("--label", default="")
    args = parser.parse_args()
    if args.label:
        print(f"\n########## {args.label} ##########")
    rows = [json.loads(line) for line in (ROOT / args.rows).open()]
    by_cell = defaultdict(list)
    for row in rows:
        by_cell[row["cell"]].append(row)

    print("=" * 88)
    print("READ RATE: did the agent ever see the injected instruction?")
    print("=" * 88)
    print(f"{'channel':22} {'read':>10}  {'n':>4}  95% CI")
    read_by_channel = defaultdict(lambda: [0, 0])
    for cell, cell_rows in by_cell.items():
        channel = CHANNEL.get(cell)
        if not channel:
            continue
        read_by_channel[channel][0] += sum(r["read_injection"] for r in cell_rows)
        read_by_channel[channel][1] += len(cell_rows)
    for channel, (k, n) in sorted(read_by_channel.items()):
        lo, hi = wilson(k, n)
        print(f"{channel:22} {k:>4}/{n:<5} {n:>4}  [{lo:.2f}, {hi:.2f}]")

    print()
    print("=" * 88)
    print("DEFERENCE: of rollouts that saw it and finished, how many sided with the file?")
    print("=" * 88)
    print(f"{'cell':22} {'defer':>10}  {'rate':>6}  95% CI            denominator")
    pooled = defaultdict(lambda: [0, 0])
    for cell in sorted(by_cell):
        informative = [r for r in by_cell[cell] if r["informative"]]
        n = len(informative)
        if n == 0:
            total = len(by_cell[cell])
            print(f"{cell:22} {'-':>10}  {'-':>6}  never informative   0 of {total} (read rate 0)")
            continue
        k = sum(r["sided_with"] == "file" for r in informative)
        lo, hi = wilson(k, n)
        label = CHANNEL.get(cell, "control")
        pooled[label][0] += k
        pooled[label][1] += n
        print(f"{cell:22} {k:>4}/{n:<5} {k/n:>6.0%}  [{lo:.2f}, {hi:.2f}]      {n} informative")

    print()
    print("=" * 88)
    print("POOLED BY CHANNEL")
    print("=" * 88)
    for label, (k, n) in sorted(pooled.items()):
        if n == 0:
            continue
        lo, hi = wilson(k, n)
        print(f"{label:22} {k:>4}/{n:<5} {k/n:>6.0%}  [{lo:.2f}, {hi:.2f}]")

    sysk, sysn = pooled["system prompt"]
    pyk, pyn = pooled["pyproject comment"]
    ctlk, ctln = pooled["control"]
    if sysn and pyn:
        p = fisher_exact_greater(sysk, sysn - sysk, pyk, pyn - pyk)
        print(f"\nsystem prompt vs pyproject comment: Fisher exact one-sided p = {p:.2e}")
    if sysn and ctln:
        p = fisher_exact_greater(sysk, sysn - sysk, ctlk, ctln - ctlk)
        print(f"system prompt vs controls:          Fisher exact one-sided p = {p:.2e}")

    print()
    print("=" * 88)
    print("JUSTIFICATION ABLATION: does the stated reason matter?")
    print("=" * 88)
    for channel in ("system", "pyproject"):
        line = []
        for justification in ("reasoned", "bare"):
            cell = f"{channel}_{justification}"
            informative = [r for r in by_cell.get(cell, []) if r["informative"]]
            if not informative:
                continue
            k = sum(r["sided_with"] == "file" for r in informative)
            line.append(f"{justification} {k}/{len(informative)} ({k/len(informative):.0%})")
        if line:
            print(f"  {channel:12} " + "   vs   ".join(line))

    print()
    total_rollouts = len(rows)
    informative_total = sum(r["informative"] for r in rows)
    review = sum(r["needs_review"] for r in rows if r["informative"])
    print(f"rollouts classified: {total_rollouts} | informative: {informative_total} | refusal verdicts needing hand review: {review}")


if __name__ == "__main__":
    main()
