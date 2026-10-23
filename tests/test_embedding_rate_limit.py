# Import SimpleNamespace to simulate an HTTP response.
from types import SimpleNamespace

# Import pytest to run the same test with different inputs.
import pytest

# Import our embedding module.
from rag.ingestion import embedder


# Test different Azure retry-header scenarios.
@pytest.mark.parametrize(
    "headers, expected_delay",
    [
        ({}, 60.0),
        ({"retry-after": "90"}, 90.0),
        ({"retry-after-ms": "75000"}, 75.0),
        ({"retry-after": "invalid"}, 60.0),
    ],
)
def test_rate_limit_delay(headers, expected_delay):

    # Simulate an Azure error containing an HTTP response.
    error = SimpleNamespace(
        response=SimpleNamespace(headers=headers)
    )

    # Calculate the retry delay without actually sleeping.
    delay = embedder.get_rate_limit_delay(error)

    # Verify that the calculated delay matches expectations.
    assert delay == expected_delay
