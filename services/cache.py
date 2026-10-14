"""Tiny thread-safe in-process TTL cache for hot, public, read-mostly queries."""

import threading
import time
from functools import wraps


def ttl_cache(seconds: float):
    """Cache a zero-argument function's result for ``seconds``."""

    def decorator(func):
        lock = threading.Lock()
        state = {"expires": 0.0, "value": None}

        @wraps(func)
        def wrapper():
            now = time.monotonic()

            if now < state["expires"]:
                return state["value"]

            value = func()

            with lock:
                state["value"] = value
                state["expires"] = time.monotonic() + seconds

            return value

        def clear():
            with lock:
                state["expires"] = 0.0

        wrapper.cache_clear = clear
        return wrapper

    return decorator
