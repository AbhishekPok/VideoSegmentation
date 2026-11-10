"""Registration, login, logout and session lookup."""
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..core.logging import get_logger
from ..core.security import (
    email_limiter,
    hash_password,
    hash_token,
    ip_limiter,
    needs_rehash,
    new_token,
    verify_password,
)
from ..exceptions import AuthenticationError, ConflictError, RateLimitError
from ..models import AuthSession, User, utcnow
from ..repositories import SessionRepository, UserRepository

log = get_logger(__name__)


@dataclass
class LoginResult:
    user: User
    token: str  # raw token for the cookie; only its hash is stored


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)
        self.sessions = SessionRepository(db)

    def _start_session(self, user: User) -> str:
        token = new_token()
        now = utcnow()
        self.sessions.delete_expired(user.id, now)
        self.sessions.add(
            AuthSession(token_hash=hash_token(token), user_id=user.id, expires_at=now + timedelta(days=settings.session_days))
        )
        self.db.commit()
        return token

    def register(self, email: str, password: str) -> LoginResult:
        user = User(email=email, password_hash=hash_password(password))
        try:
            self.users.add(user)
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ConflictError("An account with this email already exists.")
        log.info("user registered", extra={"user_id": user.id})
        return LoginResult(user, self._start_session(user))

    def login(self, email: str, password: str, client_ip: str) -> LoginResult:
        email = email.strip().lower()
        if email_limiter.blocked(email) or ip_limiter.blocked(client_ip):
            raise RateLimitError("Too many failed attempts. Try again in 15 minutes.")
        user = self.users.get_by_email(email)
        if not verify_password(user.password_hash if user else None, password):
            email_limiter.fail(email)
            ip_limiter.fail(client_ip)
            log.info("login failed", extra={"client_ip": client_ip})
            raise AuthenticationError("Wrong email or password.")
        email_limiter.reset(email)
        if needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)
        return LoginResult(user, self._start_session(user))

    def logout(self, token: str | None) -> None:
        if token:
            self.sessions.delete_by_hash(hash_token(token))
            self.db.commit()

    def user_for_token(self, token: str | None) -> User | None:
        if not token:
            return None
        sess = self.sessions.get_valid(hash_token(token), utcnow())
        return sess.user if sess else None
