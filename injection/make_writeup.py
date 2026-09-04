"""Generates the write-up tables and the random transcript sample.

Every number is generated from the classified rows, so a rerun regenerates all of
them. Six detector bugs changed headline numbers after the fact, and hand-copied
tables would have preserved the stale ones.

The transcript sample uses a fixed seed, printed in the output, so the claim that
it is not cherry-picked is checkable.
"""

import json
import random
from collections import defaultdict
from pathlib import Path

from injection.analyze import fisher_exact_greater, wilson

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/writeup"
SEED = 20260903
SAMPLE = 10

SOURCES = {
    "gpt-oss-120b": "results/outcomes.jsonl",
    "deepseek-v4-flash-0731": "results/outcomes_deepseek.jsonl",
    "gpt-oss-120b +ask": "results/outcomes_ask.jsonl",
}
CHANNEL = {
    "system_reasoned": "system prompt",
    "system_bare": "system prompt",
    "pyproject_reasoned": "pyproject comment",
    "pyproject_bare": "pyproject comment",
    "agents_reasoned": "AGENTS.md on disk",
    "agents_bare": "AGENTS.md on disk",
}


def load() -> dict[str, list[dict]]:
    out = {}
    for label, path in SOURCES.items():
        file = ROOT / path
        if file.exists():
            out[label] = [json.loads(line) for line in file.open()]
    return out


def rate(rows: list[dict], key="file") -> tuple[int, int]:
    informative = [r for r in rows if r["informative"]]
    return sum(r["sided_with"] == key for r in informative), len(informative)


def ci(k: int, n: int) -> str:
    if n == 0:
        return "n/a"
    lo, hi = wilson(k, n)
    return f"{k}/{n} ({k/n:.0%}) [{lo:.2f}, {hi:.2f}]"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = load()
    lines: list[str] = []

    lines.append("## Table 1. Delivery channel decides, not content\n")
    lines.append("Identical prohibition text throughout. gpt-oss-120b.\n")
    lines.append("| Channel | Agent read it | Sided with the repository file |")
    lines.append("|---|---|---|")
    rows = data.get("gpt-oss-120b", [])
    by_channel = defaultdict(list)
    for row in rows:
        if row["cell"] in CHANNEL:
            by_channel[CHANNEL[row["cell"]]].append(row)
    for channel in ("system prompt", "pyproject comment", "AGENTS.md on disk"):
        group = by_channel.get(channel, [])
        read = sum(r["read_injection"] for r in group)
        k, n = rate(group)
        read_cell = f"{read}/{len(group)} ({read/len(group):.0%})" if group else "n/a"
        lines.append(f"| {channel} | {read_cell} | {ci(k, n)} |")
    ctl = [r for r in rows if r["cell"] in ("none", "benign_system")]
    k, n = rate(ctl)
    lines.append(f"| controls (no conflict) | n/a | {ci(k, n)} |")

    lines.append("\n## Table 2. The two models fail by different mechanisms\n")
    lines.append("| Model | With a stated reason | Reason removed | Reason matters? |")
    lines.append("|---|---|---|---|")
    for label in ("gpt-oss-120b", "deepseek-v4-flash-0731"):
        rows = data.get(label, [])
        kr, nr = rate([r for r in rows if r["cell"] == "system_reasoned"])
        kb, nb = rate([r for r in rows if r["cell"] == "system_bare"])
        if not nr or not nb:
            continue
        p = fisher_exact_greater(kr, nr - kr, kb, nb - kb)
        verdict = f"yes, p = {p:.4f}" if p < 0.05 else f"no, p = {p:.2f}"
        lines.append(f"| {label} | {ci(kr, nr)} | {ci(kb, nb)} | {verdict} |")

    lines.append("\n## Table 3. Offering an escalation tool helps, partially\n")
    lines.append("gpt-oss-120b, system-prompt channel.\n")
    lines.append("| Condition | Did what the user asked | Sided with the file | Asked the user |")
    lines.append("|---|---|---|---|")
    for label, source, cells in (
        ("no ask tool", "gpt-oss-120b", ("system_reasoned", "system_bare")),
        ("ask tool offered", "gpt-oss-120b +ask", ("system_reasoned",)),
        ("ask tool, no conflict", "gpt-oss-120b +ask", ("none",)),
    ):
        rows = [r for r in data.get(source, []) if r["cell"] in cells and r["informative"]]
        if not rows:
            continue
        n = len(rows)
        counts = {k: sum(r["sided_with"] == k for r in rows) for k in ("user", "file", "asked")}
        cells_out = " | ".join(f"{counts[k]}/{n} ({counts[k]/n:.0%})" for k in ("user", "file", "asked"))
        lines.append(f"| {label} | {cells_out} |")

    (OUT / "tables.md").write_text("\n".join(lines) + "\n")

    # Random transcript sample, seeded and stated.
    random.seed(SEED)
    pool = [r for r in data.get("gpt-oss-120b", []) if r["cell"] == "system_reasoned" and r["informative"]]
    picked = random.sample(pool, min(SAMPLE, len(pool)))
    doc = [
        f"# Randomly selected transcripts (seed {SEED})\n",
        f"{len(picked)} of {len(pool)} informative rollouts from the system-prompt conflict cell,",
        "drawn with the seed above. Not cherry-picked; rerunning reproduces this exact set.\n",
    ]
    for row in picked:
        doc.append(f"\n## {row['cell']} / {row['run']}\n")
        doc.append(f"- created `src/py.typed`: **{row['created_marker']}** (from the filesystem snapshot)")
        doc.append(f"- cited the prohibition: {row['cited_injection']}")
        doc.append(f"- classified as siding with: **{row['sided_with']}**")
        doc.append(f"- commands issued: {row['n_commands']}\n")
        doc.append("```")
        doc.append(row["final_text"][:1200])
        doc.append("```")
    (OUT / "transcripts.md").write_text("\n".join(doc) + "\n")

    print(f"wrote {OUT / 'tables.md'}")
    print(f"wrote {OUT / 'transcripts.md'} ({len(picked)} transcripts, seed {SEED})")


if __name__ == "__main__":
    main()
