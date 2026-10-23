# Import a queue for tracking recent embedding requests.
from collections import deque

# Import time functions for measuring elapsed time and waiting.
import time


# Control token usage within a rolling time window.
class EmbeddingRateLimiter:

    # Configure the token budget and time window.
    def __init__(
        self,
        max_tokens: int = 10000,
        window_seconds: float = 60.0,
    ):

        # Require a positive integer token budget.
        if type(max_tokens) is not int or max_tokens < 1:
            raise ValueError("max_tokens must be a positive integer.")

        # Require a positive time window.
        if (
            isinstance(window_seconds, bool)
            or not isinstance(window_seconds, (int, float))
            or not 0 < window_seconds < float("inf")
        ):
            raise ValueError("window_seconds must be positive and finite.")

        # Save the configured limits.
        self.max_tokens = max_tokens
        self.window_seconds = window_seconds

        # Store recent reservations as (timestamp, token_count).
        self._requests = deque()

    # Reserve tokens before making an embedding API request.
    def acquire(self, token_count: int) -> None:

        # Reject invalid token counts.
        if type(token_count) is not int or token_count < 1:
            raise ValueError("token_count must be a positive integer.")

        # Reject requests larger than the entire available budget.
        if token_count > self.max_tokens:
            raise ValueError("Request exceeds the token-per-minute budget.")

        # Wait until sufficient token capacity becomes available.
        while True:

            # Read the current monotonic time.
            now = time.monotonic()

            # Remove reservations older than the configured window.
            while (
                self._requests
                and now - self._requests[0][0] >= self.window_seconds
            ):
                self._requests.popleft()

            # Calculate tokens already reserved in the window.
            used_tokens = sum(count for _, count in self._requests)

            # Reserve capacity immediately when sufficient.
            if used_tokens + token_count <= self.max_tokens:
                self._requests.append((now, token_count))
                return

            # Identify when the oldest reservation expires.
            oldest_timestamp = self._requests[0][0]

            # Calculate how long we need to wait.
            wait_seconds = (
                self.window_seconds - (now - oldest_timestamp)
            )

            # Sleep until the next reservation expires.
            time.sleep(max(wait_seconds, 0.001))


# Coordinate the independent Azure embedding quotas.
class EmbeddingQuotaLimiter:

    # Configure token and request limits for this ingestion process.
    def __init__(
        self,
        max_tokens_per_minute: int = 10000,
        max_requests_per_10_seconds: int = 10,
    ):

        # Track tokens consumed during a rolling 60-second window.
        self.token_limiter = EmbeddingRateLimiter(
            max_tokens=max_tokens_per_minute,
            window_seconds=60.0,
        )

        # Track requests during a rolling 10-second window.
        self.request_limiter = EmbeddingRateLimiter(
            max_tokens=max_requests_per_10_seconds,
            window_seconds=10.0,
        )

    # Reserve capacity before submitting one embedding API request.
    def acquire(self, token_count: int) -> None:

        # Validate token counts before reserving either quota.
        if type(token_count) is not int or token_count < 1:
            raise ValueError("token_count must be a positive integer.")

        # Reject requests larger than the entire token budget.
        if token_count > self.token_limiter.max_tokens:
            raise ValueError("Request exceeds the token-per-minute budget.")

        # Wait until the token budget can accommodate this request.
        self.token_limiter.acquire(token_count)

        # Wait until one request slot becomes available.
        self.request_limiter.acquire(1)
