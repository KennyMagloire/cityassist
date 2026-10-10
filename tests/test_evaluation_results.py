"""Acceptance checks on the recorded 160-message evaluation (tests/evaluation_results.csv).

These turn the results in Part E into minimum standards. If the evaluation is re-run after a
change and the chatbot gets worse, these tests fail.
"""
import json
from pathlib import Path

import pandas as pd

from app import config

HERE = Path(__file__).resolve().parent
RESULTS = pd.read_csv(HERE / "evaluation_results.csv")
EXPECTED = pd.read_csv(HERE / "test_utterances.csv")[["utterance_id", "expected_department"]]
LOOKUP = json.loads(config.LOOKUP_FILE.read_text(encoding="utf-8"))
DATA = RESULTS.merge(EXPECTED, on="utterance_id")
SAME_INTENT = {"greeting": "small_talk", "closing": "small_talk", "out_of_scope": "question"}


def test_all_160_messages_were_evaluated():
    assert len(RESULTS) == 160
    assert RESULTS["utterance_id"].is_unique


def test_no_message_hit_the_fallback():
    """A fallback means an AI service failed during the run, so that result says nothing."""
    assert not RESULTS["reply"].str.startswith("Sorry, I can't answer right now", na=False).any()


def test_intent_accuracy_at_least_85_percent():
    expected = DATA["expected_intent"].replace(SAME_INTENT)
    assert (expected == DATA["got_intent"]).mean() >= 0.85


def test_department_accuracy_at_least_75_percent():
    reports = DATA[DATA["expected_code"].notna() & (DATA["expected_intent"] == "report")]
    got = reports["got_code"].map(lambda c: LOOKUP.get(c, {}).get("department") if isinstance(c, str) else None)
    assert (got == reports["expected_department"]).mean() >= 0.75


def test_every_complete_report_became_a_draft():
    complete = DATA[DATA["expected_behaviour"] == "draft"]
    assert complete["reply"].str.contains("draft request number", na=False).all()


def test_replies_are_fast_enough():
    awake = DATA["seconds"][DATA["seconds"] <= 10]     # leave out waits caused by the quota outage
    assert awake.median() <= 3
