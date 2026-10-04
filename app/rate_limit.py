import threading
import time
from collections import defaultdict

from app.config import settings


class LoginAttemptTracker:
    """In-memory sliding-window limiter on failed login attempts, keyed by email.

    Deliberately simple (no Redis) for a single-process deployment. Resets on restart and
    won't coordinate across multiple backend instances -- fine for now, revisit if this ever
    runs behind more than one worker/replica.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._failures: dict[str, list[float]] = defaultdict(list)

    def _recent_failures(self, key: str) -> list[float]:
        window_seconds = settings.login_rate_limit_window_minutes * 60
        cutoff = time.monotonic() - window_seconds
        return [t for t in self._failures[key] if t >= cutoff]

    def is_locked_out(self, key: str) -> bool:
        with self._lock:
            recent = self._recent_failures(key)
            self._failures[key] = recent
            return len(recent) >= settings.login_rate_limit_max_attempts

    def record_failure(self, key: str) -> None:
        with self._lock:
            self._failures[key] = self._recent_failures(key) + [time.monotonic()]

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)


login_attempt_tracker = LoginAttemptTracker()
