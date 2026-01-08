"""Retry logic with exponential backoff."""

import random
import time
from functools import wraps
from typing import Callable, TypeVar

from playwright.sync_api import Error as PlaywrightError

T = TypeVar("T")


def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 1,
    max_delay: float = 60,
    backoff_factor: float = 2,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for retry logic with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        backoff_factor: Multiplier for delay after each attempt

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except (ConnectionError, TimeoutError, PlaywrightError) as e:
                    last_exception = e
                    if attempt == max_attempts - 1:
                        raise e

                    delay = min(base_delay * (backoff_factor**attempt), max_delay)
                    jitter = random.uniform(0.1, 0.5) * delay
                    total_delay = delay + jitter

                    print(f"Attempt {attempt + 1} failed: {e}. Retrying in {total_delay:.1f}s")
                    time.sleep(total_delay)
                except Exception as e:
                    last_exception = e
                    if attempt == max_attempts - 1:
                        raise e

                    delay = min(base_delay * (backoff_factor**attempt), max_delay)
                    jitter = random.uniform(0.1, 0.5) * delay
                    total_delay = delay + jitter

                    print(f"Attempt {attempt + 1} failed: {e}. Retrying in {total_delay:.1f}s")
                    time.sleep(total_delay)

            if last_exception:
                raise last_exception
            return None  # type: ignore

        return wrapper

    return decorator
