import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from ...infrastructure.config import get_settings

_basic = HTTPBasic(auto_error=False)


def require_admin(creds: HTTPBasicCredentials | None = Depends(_basic)) -> None:
    settings = get_settings()
    if not settings.admin_password:
        return
    ok = (
        creds is not None
        and secrets.compare_digest(creds.username, settings.admin_user)
        and secrets.compare_digest(creds.password, settings.admin_password)
    )
    if not ok:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, headers={"WWW-Authenticate": "Basic"})
