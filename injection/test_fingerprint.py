"""Pooling must break exactly when behaviour could have changed."""

import copy

from injection.fingerprint import fingerprint, poolable
from injection.variants import BY_NAME

CELL = BY_NAME["agents_reasoned"]
CONFIG = {
    "agent": {"provider": "openrouter", "model": "openai/gpt-oss-120b", "max_steps": 20},
    "task": {"target_errors": 0, "tools": ["execute_command"]},
    "prompts": {"system_prompt": "sys", "user_prompt": "usr"},
}


def test_stable_across_calls():
    assert fingerprint(CELL, CONFIG) == fingerprint(CELL, copy.deepcopy(CONFIG))


def test_tool_order_does_not_split_the_pool():
    other = copy.deepcopy(CONFIG)
    other["task"]["tools"] = ["execute_command"]
    assert fingerprint(CELL, other) == fingerprint(CELL, CONFIG)


def test_retuning_the_injected_text_breaks_pooling():
    from dataclasses import replace

    retuned = replace(CELL, injection_content=CELL.injection_content + "- Be quick.\n")
    assert fingerprint(retuned, CONFIG) != fingerprint(CELL, CONFIG)


def test_moving_the_injection_to_another_file_breaks_pooling():
    from dataclasses import replace

    moved = replace(CELL, injection_path="CONTRIBUTING.md")
    assert fingerprint(moved, CONFIG) != fingerprint(CELL, CONFIG)


def test_changing_model_breaks_pooling():
    other = copy.deepcopy(CONFIG)
    other["agent"]["model"] = "deepseek/deepseek-v4-flash-0731"
    assert fingerprint(CELL, other) != fingerprint(CELL, CONFIG)


def test_changing_step_cap_breaks_pooling():
    other = copy.deepcopy(CONFIG)
    other["agent"]["max_steps"] = 30
    assert fingerprint(CELL, other) != fingerprint(CELL, CONFIG)


def test_changing_error_variant_breaks_pooling():
    other = copy.deepcopy(CONFIG)
    other["task"]["target_errors"] = 258
    assert fingerprint(CELL, other) != fingerprint(CELL, CONFIG)


def test_cells_differ_from_each_other():
    digests = {fingerprint(c, CONFIG) for c in BY_NAME.values()}
    assert len(digests) == len(BY_NAME)


def test_poolable_detects_a_mixed_pool():
    a, b = fingerprint(CELL, CONFIG), fingerprint(CELL, {**CONFIG, "agent": {**CONFIG["agent"], "max_steps": 30}})
    ok, counts = poolable([{"fingerprint": a}] * 10 + [{"fingerprint": b}] * 3)
    assert ok is False
    assert counts == {a: 10, b: 3}


def test_poolable_accepts_a_clean_pool():
    a = fingerprint(CELL, CONFIG)
    ok, counts = poolable([{"fingerprint": a}] * 50)
    assert ok is True
    assert counts == {a: 50}
