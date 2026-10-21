# Import pytest for assertions and exception testing.
import pytest

# Import the module so we can replace its clock.
from rag.ingestion import embedding_rate_limiter as limiter_module

# Import the combined quota limiter.
from rag.ingestion.embedding_rate_limiter import EmbeddingQuotaLimiter


# Simulate time without actually waiting.
class FakeClock:

    # Initialize the simulated clock.
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    # Return the current simulated time.
    def monotonic(self):
        return self.now

    # Advance simulated time instead of sleeping.
    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


# Provide an isolated simulated clock for every test.
@pytest.fixture
def clock(monkeypatch):

    # Create the fake clock.
    fake = FakeClock()

    # Replace the real monotonic clock.
    monkeypatch.setattr(limiter_module.time, "monotonic", fake.monotonic)

    # Replace real sleeping.
    monkeypatch.setattr(limiter_module.time, "sleep", fake.sleep)

    # Return the clock for assertions.
    return fake


# Verify that requests within both limits proceed immediately.
def test_allows_requests_within_both_quotas(clock):

    # Configure small limits for testing.
    limiter = EmbeddingQuotaLimiter(
        max_tokens_per_minute=100,
        max_requests_per_10_seconds=2,
    )

    # Submit two requests using 40 tokens each.
    limiter.acquire(40)
    limiter.acquire(40)

    # Neither request should require waiting.
    assert clock.sleeps == []


# Verify that request frequency is limited independently.
def test_enforces_request_limit(clock):

    # Allow plenty of tokens but only two requests per 10 seconds.
    limiter = EmbeddingQuotaLimiter(
        max_tokens_per_minute=1000,
        max_requests_per_10_seconds=2,
    )

    # Use the two available request slots.
    limiter.acquire(10)
    limiter.acquire(10)

    # A third request must wait.
    limiter.acquire(10)

    # Verify that the request limiter waited 10 seconds.
    assert clock.sleeps == [pytest.approx(10.0)]


# Verify that the token budget is enforced independently.
def test_enforces_token_limit(clock):

    # Allow many requests but only 100 tokens per minute.
    limiter = EmbeddingQuotaLimiter(
        max_tokens_per_minute=100,
        max_requests_per_10_seconds=10,
    )

    # Reserve 80 tokens.
    limiter.acquire(80)

    # Request another 30 tokens.
    limiter.acquire(30)

    # The second request must wait until the token window expires.
    assert clock.sleeps == [pytest.approx(60.0)]


# Verify invalid token requests are rejected before reservation.
@pytest.mark.parametrize("tokens", [0, -1, True, 1.5])
def test_rejects_invalid_token_requests(clock, tokens):

    # Create a valid combined limiter.
    limiter = EmbeddingQuotaLimiter()

    # Invalid token requests must fail.
    with pytest.raises(ValueError):
        limiter.acquire(tokens)


# Verify oversized requests cannot exceed the token budget.
def test_rejects_oversized_requests(clock):

    # Configure a small token budget.
    limiter = EmbeddingQuotaLimiter(
        max_tokens_per_minute=100,
    )

    # Reject an individual request requiring too many tokens.
    with pytest.raises(ValueError, match="exceeds"):
        limiter.acquire(101)

    # No capacity should have been reserved.
    assert len(limiter.token_limiter._requests) == 0
    assert len(limiter.request_limiter._requests) == 0
