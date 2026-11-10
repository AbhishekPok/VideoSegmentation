"""Generic repository: data access only. Services own transactions (commit/rollback)."""
from typing import Any, Generic, TypeVar

from sqlalchemy.orm import Session

from ..models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, db: Session):
        self.db = db

    def get(self, pk: Any) -> ModelT | None:
        return self.db.get(self.model, pk)

    def add(self, obj: ModelT) -> ModelT:
        self.db.add(obj)
        self.db.flush()  # assigns primary keys; commit happens in the service
        return obj

    def delete(self, obj: ModelT) -> None:
        self.db.delete(obj)
        self.db.flush()
