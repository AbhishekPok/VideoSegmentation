from fastapi import APIRouter, Depends, Request, Response, status

from ...config import settings
from ...dependencies import AuthServiceDep, CurrentUser, client_ip, session_token
from ...schemas import LoginIn, RegisterIn, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        settings.cookie_name,
        token,
        max_age=settings.session_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, response: Response, auth: AuthServiceDep):
    result = auth.register(body.email, body.password)
    _set_cookie(response, result.token)
    return UserOut(id=result.user.id, email=result.user.email)


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, response: Response, auth: AuthServiceDep, ip: str = Depends(client_ip)):
    result = auth.login(body.email, body.password, ip)
    _set_cookie(response, result.token)
    return UserOut(id=result.user.id, email=result.user.email)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, auth: AuthServiceDep):
    auth.logout(session_token(request))
    response.delete_cookie(settings.cookie_name, path="/", httponly=True, secure=settings.cookie_secure, samesite="lax")


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return UserOut(id=user.id, email=user.email)
