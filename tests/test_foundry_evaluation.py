"""Unit tests for NEXORA Foundry evaluation verification."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests.evaluation.run_foundry_evaluation import verify_predictions


CASES = [
    {"expected": "PASS"},
    {"expected": "FAIL"},
]


def make_item(index, passed, status="completed"):
    """Build a minimal mocked Foundry output item."""
    return SimpleNamespace(
        datasource_item_id=index,
        status=status,
        results=[
            SimpleNamespace(status=status, passed=passed)
        ],
    )


def make_client(items):
    """Return a client with mocked evaluation output."""
    client = Mock()
    client.evals.runs.output_items.list.return_value = items
    return client


def test_correct_predictions():
    """Correct classifications must pass."""
    result = verify_predictions(
        make_client([make_item(0, True), make_item(1, False)]),
        "eval-id",
        "run-id",
        CASES,
    )
    assert len(result) == 2
    assert all(item["correct"] for item in result)


def test_wrong_prediction_fails():
    """An incorrect classification must fail the regression."""
    with pytest.raises(AssertionError, match="Incorrect predictions"):
        verify_predictions(
            make_client([make_item(0, False), make_item(1, False)]),
            "eval-id",
            "run-id",
            CASES,
        )


def test_missing_result_fails():
    """Missing evaluations must never count as success."""
    with pytest.raises(AssertionError, match="Expected 2 results"):
        verify_predictions(
            make_client([make_item(0, True)]),
            "eval-id",
            "run-id",
            CASES,
        )


def test_duplicate_result_fails():
    """Duplicate output IDs must be rejected."""
    with pytest.raises(AssertionError, match="Duplicate"):
        verify_predictions(
            make_client([make_item(0, True), make_item(0, False)]),
            "eval-id",
            "run-id",
            CASES,
        )


def test_incomplete_result_fails():
    """Incomplete evaluator results must be rejected."""
    with pytest.raises(AssertionError, match="Incomplete"):
        verify_predictions(
            make_client([
                make_item(0, True, "failed"),
                make_item(1, False),
            ]),
            "eval-id",
            "run-id",
            CASES,
        )
