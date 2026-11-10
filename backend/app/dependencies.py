"""Shared FastAPI dependencies: DB session, current user, services."""
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .exceptions import AuthenticationError
from .models import User
from .services.auth_service import AuthService
from .services.plan_service import PlanService

DbSession = Annotated[Session, Depends(get_db)]


def get_auth_service(db: DbSession) -> AuthService:
    return AuthService(db)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


def session_token(request: Request) -> str | None:
    return request.cookies.get(settings.cookie_name)


def client_ip(request: Request) -> str:
    # Behind nginx/ALB later, configure uvicorn --proxy-headers so this is the real client.
    return request.client.host if request.client else "unknown"


def get_current_user(request: Request, auth: AuthServiceDep) -> User:
    user = auth.user_for_token(session_token(request))
    if not user:
        raise AuthenticationError("Not logged in")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_plan_service(db: DbSession, user: CurrentUser) -> PlanService:
    return PlanService(db, user)


PlanServiceDep = Annotated[PlanService, Depends(get_plan_service)]
