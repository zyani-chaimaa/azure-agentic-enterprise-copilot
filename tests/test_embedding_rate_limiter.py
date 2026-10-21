# Import pytest for parameterized tests and exception assertions.
import pytest

# Import the module so we can replace its clock and sleep functions.
from rag.ingestion import embedding_rate_limiter as limiter_module

# Import the rate limiter we want to test.
from rag.ingestion.embedding_rate_limiter import EmbeddingRateLimiter


# Create a controllable clock for deterministic tests.
class FakeClock:

    # Start the simulated clock at zero seconds.
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    # Return the current simulated time.
    def monotonic(self):
        return self.now

    # Advance time instead of actually sleeping.
    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


# Replace real time functions with our simulated clock.
@pytest.fixture
def clock(monkeypatch):

    # Create an independent clock for each test.
    fake = FakeClock()

    # Replace the monotonic clock used by the limiter.
    monkeypatch.setattr(limiter_module.time, "monotonic", fake.monotonic)

    # Replace sleeping with simulated time advancement.
    monkeypatch.setattr(limiter_module.time, "sleep", fake.sleep)

    # Provide the clock to the test.
    return fake


# Verify requests within the token budget proceed immediately.
def test_allows_requests_within_budget(clock):

    # Configure a 100-token budget over 60 seconds.
    limiter = EmbeddingRateLimiter(max_tokens=100)

    # Reserve 40 tokens.
    limiter.acquire(40)

    # Reserve another 60 tokens.
    limiter.acquire(60)

    # Neither request should require waiting.
    assert clock.sleeps == []


# Verify that exceeding the budget causes a wait.
def test_waits_when_budget_exceeded(clock):

    # Configure a 100-token budget.
    limiter = EmbeddingRateLimiter(max_tokens=100)

    # Consume 80 tokens immediately.
    limiter.acquire(80)

    # Advance five seconds.
    clock.now = 5.0

    # Request another 30 tokens.
    limiter.acquire(30)

    # The second request must wait until the first expires.
    assert clock.sleeps == [pytest.approx(55.0)]

    # Confirm the simulated time advanced to 60 seconds.
    assert clock.now == pytest.approx(60.0)


# Verify capacity is released after the rolling window expires.
def test_releases_expired_reservations(clock):

    # Configure a 100-token budget.
    limiter = EmbeddingRateLimiter(max_tokens=100)

    # Reserve all available tokens.
    limiter.acquire(100)

    # Advance beyond the 60-second window.
    clock.now = 61.0

    # The expired reservation must no longer block requests.
    limiter.acquire(100)

    # No sleeping should have occurred.
    assert clock.sleeps == []


# Verify that a request cannot exceed the entire budget.
def test_rejects_oversized_request(clock):

    # Configure a 100-token budget.
    limiter = EmbeddingRateLimiter(max_tokens=100)

    # Reject a request requiring 101 tokens.
    with pytest.raises(ValueError, match="exceeds"):
        limiter.acquire(101)


# Verify invalid token counts are rejected.
@pytest.mark.parametrize("tokens", [0, -1, True, 1.5, "10"])
def test_rejects_invalid_token_counts(clock, tokens):

    # Create a valid limiter.
    limiter = EmbeddingRateLimiter(max_tokens=100)

    # Reject invalid token reservation values.
    with pytest.raises(ValueError, match="positive integer"):
        limiter.acquire(tokens)


# Verify invalid configuration values are rejected.
@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_tokens": 0},
        {"max_tokens": True},
        {"window_seconds": 0},
        {"window_seconds": -1},
        {"window_seconds": float("inf")},
        {"window_seconds": float("nan")},
        {"window_seconds": True},
    ],
)
def test_rejects_invalid_configuration(kwargs):

    # Reject invalid rate-limiter configuration.
    with pytest.raises(ValueError):
        EmbeddingRateLimiter(**kwargs)
