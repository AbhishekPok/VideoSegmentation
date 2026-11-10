from datetime import datetime

from sqlalchemy import delete, select

from ..models import AuthSession, User
from .base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    def get_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email))


class SessionRepository(BaseRepository[AuthSession]):
    model = AuthSession

    def get_valid(self, token_hash: str, now: datetime) -> AuthSession | None:
        return self.db.scalar(
            select(AuthSession).where(AuthSession.token_hash == token_hash, AuthSession.expires_at > now)
        )

    def delete_by_hash(self, token_hash: str) -> None:
        self.db.execute(delete(AuthSession).where(AuthSession.token_hash == token_hash))

    def delete_expired(self, user_id: int, now: datetime) -> None:
        self.db.execute(delete(AuthSession).where(AuthSession.user_id == user_id, AuthSession.expires_at <= now))
