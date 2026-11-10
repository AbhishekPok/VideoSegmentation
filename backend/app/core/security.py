"""Password hashing (Argon2), opaque session tokens, and a login rate limiter.

Sessions are server-side (a row per login, token stored hashed) rather than JWT,
so logging out or deleting a user revokes access immediately.
"""
import hashlib
import secrets
import threading
import time

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_ph = PasswordHasher()
# Verified against when the email is unknown, so response time doesn't reveal which emails exist.
_DUMMY_HASH = _ph.hash("not-a-real-password")


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _ph.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _ph.check_needs_rehash(password_hash)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class LoginLimiter:
    """Counts failed logins per key in a sliding window (in-process memory).

    Good enough for a single server process. With several workers or servers,
    move this to Redis or the database.
    """

    def __init__(self, max_failures: int, window_sec: int):
        self.max = max_failures
        self.window = window_sec
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _recent(self, key: str, now: float) -> list[float]:
        hits = [t for t in self._hits.get(key, []) if now - t < self.window]
        if hits:
            self._hits[key] = hits
        else:
            self._hits.pop(key, None)
        return hits

    def blocked(self, key: str) -> bool:
        with self._lock:
            return len(self._recent(key, time.monotonic())) >= self.max

    def fail(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            self._hits[key] = self._recent(key, now) + [now]

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()


email_limiter = LoginLimiter(max_failures=10, window_sec=15 * 60)
ip_limiter = LoginLimiter(max_failures=50, window_sec=15 * 60)
