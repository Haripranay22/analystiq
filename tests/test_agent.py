"""
Phase 2 Tests — Agent Routing Logic

We test the routing function in isolation (no DB, no OpenAI calls needed).
This teaches an important principle: test the decision logic separately
from the side effects (DB queries, API calls).
"""

import json
import pytest
from agent.graph import _route_after_execution


def test_success_routes_to_explain():
    """Clean execution should go straight to explanation."""
    state = {
        "error": "",
        "retry_count": 0,
        "result": json.dumps([{"fraud_count": 42}]),
    }
    assert _route_after_execution(state) == "explain"


def test_first_error_routes_to_correct():
    """First failure should trigger self-correction, not give up."""
    state = {
        "error": 'column "ammount" does not exist',
        "retry_count": 0,
        "result": "",
    }
    assert _route_after_execution(state) == "correct"


def test_second_error_still_corrects():
    """Second failure should still self-correct — we allow up to 3 retries."""
    state = {
        "error": "syntax error at or near FROM",
        "retry_count": 2,
        "result": "",
    }
    assert _route_after_execution(state) == "correct"


def test_max_retries_routes_to_explain():
    """After 3 failed retries, gracefully explain the failure instead of looping."""
    state = {
        "error": "relation does not exist",
        "retry_count": 3,
        "result": "",
    }
    assert _route_after_execution(state) == "explain"
