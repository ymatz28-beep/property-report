"""Regression tests for run_daily_patrol.py notification triggering.

Guards against the 2026-04-17 incident: suumo_tokyo dropped 148→13 listings
(-91%), diff_properties() flagged it as a source degradation, but the Gmail
notification only fired on step-level failures — so the one-click CTA email
never reached the user.

Run with:
    .venv/bin/python -m pytest tests/test_patrol_notify.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_PROJECTS = _ROOT.parent
if str(_PROJECTS) not in sys.path:
    sys.path.insert(0, str(_PROJECTS))

from run_daily_patrol import _build_failure_details, diff_properties


def test_source_degradation_produces_failure_card():
    details = _build_failure_details(all_steps=[], failed_sources=["suumo_tokyo"])
    assert len(details) == 1
    card = details[0]
    assert card["step"] == "source_degraded:suumo_tokyo"
    assert "suumo_tokyo" in card["label"]
    assert card["reason"] == "source_degraded"
    assert card["fix"]  # must provide an actionable hint


def test_step_failure_and_source_degradation_both_rendered():
    all_steps = [{"step": "deploy", "ok": False, "reason": "crash", "stderr_tail": "boom"}]
    details = _build_failure_details(all_steps, ["suumo_tokyo"])
    steps_seen = {d["step"] for d in details}
    assert "deploy" in steps_seen
    assert "source_degraded:suumo_tokyo" in steps_seen


def test_all_success_with_no_degradation_produces_no_cards():
    details = _build_failure_details(all_steps=[{"step": "deploy", "ok": True}],
                                     failed_sources=[])
    assert details == []


def test_diff_detects_source_degradation_over_70_percent():
    before = {f"url{i}": {"source": "suumo_tokyo", "name": "x", "price": "1000万円",
                           "location": "x"} for i in range(100)}
    before.update({f"o{i}": {"source": "suumo_osaka", "name": "x", "price": "1000万円",
                              "location": "x"} for i in range(50)})
    after = {f"url{i}": {"source": "suumo_tokyo", "name": "x", "price": "1000万円",
                          "location": "x"} for i in range(10)}  # 100→10 = -90%
    after.update({f"o{i}": {"source": "suumo_osaka", "name": "x", "price": "1000万円",
                             "location": "x"} for i in range(50)})
    diff = diff_properties(before, after)
    assert "suumo_tokyo" in diff["failed_sources"]
    assert "suumo_osaka" not in diff["failed_sources"]


def test_diff_ignores_small_sources_below_threshold():
    # Sources with <10 listings are ignored (too noisy)
    before = {f"url{i}": {"source": "tiny_src", "name": "x", "price": "1000万円",
                           "location": "x"} for i in range(5)}
    after: dict = {}
    diff = diff_properties(before, after)
    assert "tiny_src" not in diff["failed_sources"]
