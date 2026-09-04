# When a repository file contradicts the user, which does a coding agent obey?

A coding agent is asked to add a `py.typed` marker. A file that shipped with the
repository says not to. The agent has to pick one, and what it picks turns out to
depend almost entirely on how that file reaches the model.

271 rollouts, two models, nine conditions.

![channel and reason](results/writeup/figure_gradient.png)

## Findings

**Delivery decides, not content.** The identical sentence produces 95% deference
when it arrives in the system prompt, 0% as a comment in a file the agent reads
anyway, and never gets read at all when it sits on disk as `AGENTS.md`.

| Channel | Agent read it | Sided with the file |
|---|---|---|
| system prompt | 48/48 | 40/42 (95%) `[0.84, 0.99]` |
| comment in `pyproject.toml` | 23/32 | 0/23 (0%) `[0.00, 0.14]` |
| `AGENTS.md` on disk | 0/24 | never opened |
| controls, no conflict | n/a | 0/32 (0%) |

Fisher exact one-sided, system prompt against controls: p = 6e-19.

This matters because deployed harnesses load `AGENTS.md` and `CLAUDE.md` into the
system prompt. gpt-oss was trained on an explicit hierarchy of System over
Developer over User ([model card](https://arxiv.org/abs/2508.10925), s4.3), so it
is behaving as designed. The issue is that a file from an arbitrary git clone ends
up in the slot that authority was meant for.

**The two models fail by different mechanisms.** Removing the stated reason from
the prohibition changes nothing for one model and most of the effect for the other.

| Model | With a reason | Reason removed | |
|---|---|---|---|
| gpt-oss-120b | 19/20 (95%) | 21/22 (95%) | p = 0.78 |
| deepseek-v4-flash-0731 | 13/31 (42%) | 2/30 (7%) | p = 0.0014 |

One defers to the channel's authority alone. The other defers only when persuaded.

**Offering an escalation tool helps, partially.** Giving the agent
`ask_user_question` converts about a third of silent deference into asking. Two
thirds still resolve the conflict alone. The no-conflict control never asks, so
escalation is not reflexive.

![intervention](results/writeup/figure_intervention.png)

## Method

Ground truth is the filesystem. Whether `src/py.typed` exists is read from the
harness's per-step snapshot, never from the agent's own report. Rates cover
rollouts that read the injected file, ended the session, and stayed under the step
cap, and both denominators are always printed.

Cells cross three channels with two justification levels, plus three controls. A
test enforces that the bare variant is the reasoned text with one clause removed
and nothing else changed. Every rollout records a fingerprint over the injected
text, prompts, model and step cap, and pooling is refused across mismatches.

## Six ways these numbers were wrong first

Each was found by reading raw rows, none by a test written in advance, and each
now has a regression test.

1. Marker creation parsed from the command log missed the harness's `apply_patch`
   tool and scored 3 of 6 baseline rollouts as not creating a file the snapshot
   shows they created.
2. Citation matched the filename `pyproject.toml`, which the user prompt itself
   contains, so every rollout in that cell counted as citing the injection.
3. No handling for the step cap. The single apparent deferral in the pilot was a
   rollout still planning to create the file at command 20 of 20.
4. Fingerprints came from the current config, pooling rollouts from before and
   after a step-cap change.
5. In-flight rollouts were classified. A live batch scored the baseline at 0%
   compliance when the agents were three commands into exploring.
6. `ask_user_question` ends a session by being called, so the clean-end check
   discarded exactly the outcome the intervention exists to detect. The first pass
   reported 0% asking. The truth was 33%.

And the one that killed the first design. A single-turn reconstruction of the same
conflict gave 11/12 deference where the real agentic loop gave 0/23.

![single-turn artifact](results/writeup/figure_screen_artifact.png)

## Limitations

Purely behavioural, no internals. Two models, and the second's effect is modest at
25%. One environment, one payload, one kind of conflict. Cell sizes run 12 to 31.
Refusal detection is a regex and is flagged as such, though the deference verdict
does not rest on it, since all 40 deferring rollouts are established by the
snapshot. A local open-weight arm was built and proven but dropped at roughly 25
minutes per rollout.

## Layout

```
injection/           cells, detector, fingerprint, collector, analysis, 63 tests
injection/screens/   superseded single-turn probes, kept as the design record
results/*.jsonl      every classified rollout
results/writeup/     generated tables, figures, seeded transcript sample
patches/             the two changes made to the upstream harness
```

## Running it

Experiments run inside [gkroiz/agent-interp-envs](https://github.com/gkroiz/agent-interp-envs).
Clone it, apply the two files in `patches/`, drop `injection/` in at the root, then:

```
python -m injection.make_configs --max-steps 30
python scripts/run.py configs/injection/cell_system_reasoned.yaml --local --count 6
python -m injection.collect --model openai-gpt-oss-120b
python -m injection.analyze
```

Keep concurrency at about 6. Docker Desktop fell over at 21 containers on a 24GB
machine and failed half the batch.

Total API spend for all 271 rollouts was $1.73.

## Credit

The environment harness is [gkroiz/agent-interp-envs](https://github.com/gkroiz/agent-interp-envs)
by Aditya Singh and Gerson Kroiz, MIT licensed. This repository contains only the
experiment built on top of it.
