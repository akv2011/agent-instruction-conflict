## Table 1. Delivery channel decides, not content

Identical prohibition text throughout. gpt-oss-120b.

| Channel | Agent read it | Sided with the repository file |
|---|---|---|
| system prompt | 48/48 (100%) | 40/42 (95%) [0.84, 0.99] |
| pyproject comment | 23/32 (72%) | 0/23 (0%) [0.00, 0.14] |
| AGENTS.md on disk | 0/24 (0%) | n/a |
| controls (no conflict) | n/a | 0/32 (0%) [0.00, 0.11] |

## Table 2. The two models fail by different mechanisms

| Model | With a stated reason | Reason removed | Reason matters? |
|---|---|---|---|
| gpt-oss-120b | 19/20 (95%) [0.76, 0.99] | 21/22 (95%) [0.78, 0.99] | no, p = 0.78 |
| deepseek-v4-flash-0731 | 13/31 (42%) [0.26, 0.59] | 2/30 (7%) [0.02, 0.21] | yes, p = 0.0014 |

## Table 3. Offering an escalation tool helps, partially

gpt-oss-120b, system-prompt channel.

| Condition | Did what the user asked | Sided with the file | Asked the user |
|---|---|---|---|
| no ask tool | 2/42 (5%) | 40/42 (95%) | 0/42 (0%) |
| ask tool offered | 1/12 (8%) | 7/12 (58%) | 4/12 (33%) |
| ask tool, no conflict | 12/12 (100%) | 0/12 (0%) | 0/12 (0%) |
