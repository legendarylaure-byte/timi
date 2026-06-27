import time
import random
import functools


def retry(max_attempts: int = 3, base_delay: float = 2.0, backoff: float = 2.0, jitter: bool = True,
          exceptions: tuple = (Exception,)):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt < max_attempts - 1:
                        delay = base_delay * (backoff ** attempt)
                        if jitter:
                            delay += random.uniform(0, delay * 0.3)
                        print(f"[RETRY] {func.__name__} failed (attempt {attempt + 1}/{max_attempts}), "
                              f"retrying in {delay:.1f}s: {e}")
                        time.sleep(delay)
            raise last_exc
        return wrapper
    return decorator
