"""
core/auth.py — JWT authentication against the Django backend's tokens.

The Django backend issues access tokens with djangorestframework-simplejwt
(HS256, signed with Django's SECRET_KEY, sent as `Authorization: Bearer <token>`
with a `user_id` claim). We verify them statelessly here by sharing the same
secret — JWT_SECRET MUST equal the backend's SECRET_KEY.
"""
import logging
from dataclasses import dataclass
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(scheme_name="jwtAuth", auto_error=False)


@dataclass
class AuthenticatedUser:
    """The identity decoded from a verified access token."""

    user_id: str
    token_type: Optional[str] = None
    raw_claims: Optional[dict] = None
    access_token: Optional[str] = None


class AuthError(HTTPException):
    """401 with a WWW-Authenticate header, as expected for bearer auth."""

    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


def decode_token(token: str) -> AuthenticatedUser:
    """Verify and decode a backend-issued access token."""
    if not settings.JWT_SECRET:
        logger.error("JWT_SECRET is not set — cannot verify access tokens.")
        raise AuthError("Authentication is not configured on the server.")

    try:
        claims = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Token has expired.") from exc
    except jwt.InvalidTokenError as exc:
        logger.info("Rejected invalid JWT: %s", exc)
        raise AuthError("Invalid authentication token.") from exc

    token_type = claims.get("token_type")
    if token_type and token_type != "access":
        raise AuthError("Invalid token type — an access token is required.")

    user_id = claims.get(settings.JWT_USER_ID_CLAIM)
    if not user_id:
        raise AuthError("Token is missing the user identity claim.")

    return AuthenticatedUser(
        user_id=str(user_id),
        token_type=token_type,
        raw_claims=claims,
        access_token=token,
    )


def require_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> AuthenticatedUser:
    """FastAPI dependency: require a valid Bearer access token.

    With REQUIRE_AUTH=False a missing token is allowed (anonymous), but a
    present token is still verified.
    """
    if credentials is None or not credentials.credentials:
        if settings.REQUIRE_AUTH:
            raise AuthError("Authentication credentials were not provided.")
        return AuthenticatedUser(user_id="anonymous")
    return decode_token(credentials.credentials)
