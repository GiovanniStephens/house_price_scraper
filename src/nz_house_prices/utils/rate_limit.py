"""Rate limiting for web requests."""

import random
import time


class RateLimiter:
    """Rate limiter to avoid overwhelming target websites."""

    def __init__(self, min_delay: float = 2, max_delay: float = 5):
        """Initialize the rate limiter.

        Args:
            min_delay: Minimum delay between requests in seconds
            max_delay: Maximum delay between requests in seconds
        """
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.last_request_time: float = 0

    def wait_if_needed(self) -> None:
        """Ensure minimum delay between requests."""
        now = time.time()
        time_since_last = now - self.last_request_time

        if self.last_request_time > 0 and time_since_last < self.min_delay:
            delay = random.uniform(self.min_delay, self.max_delay)
            time.sleep(delay)

        self.last_request_time = time.time()
