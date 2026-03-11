import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Cookie, Header, HTTPException, Response, status

from app.config import settings
from app.services.database import (
    create_session,
    delete_session,
    get_api_key_user,
    get_session_user,
)

UserPayload = dict[str, object]


def normalize_username(username: str) -> str:
    return username.strip()


def hash_password(password: str) -> tuple[str, str]:
    salt = secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        600000,
    )
    return password_hash.hex(), salt.hex()


def verify_password(password: str, password_hash: str, password_salt: str) -> bool:
    computed_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(password_salt),
        600000,
    )
    return hmac.compare_digest(computed_hash.hex(), password_hash)


def build_session_expiry() -> datetime:
    return datetime.now(UTC) + timedelta(hours=settings.session_max_age_hours)


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(session_token: str) -> str:
    return hashlib.sha256(session_token.encode("utf-8")).hexdigest()


def generate_api_key() -> str:
    return f"simon_{secrets.token_urlsafe(32)}"


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def api_key_prefix(api_key: str) -> str:
    return api_key[:12]


async def create_user_session(user_id: str) -> str:
    session_token = generate_session_token()
    await create_session(
        session_id=hash_session_token(session_token),
        user_id=user_id,
        expires_at=build_session_expiry().isoformat(),
    )
    return session_token


def set_session_cookie(response: Response, session_token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=settings.session_max_age_hours * 60 * 60,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


async def invalidate_session(session_token: str) -> None:
    _ = await delete_session(hash_session_token(session_token))


async def _get_session_user_payload(session_token: str | None) -> UserPayload | None:
    if session_token is None:
        return None

    session_user = await get_session_user(hash_session_token(session_token))
    if session_user is None:
        return None

    expires_at_raw = session_user["expires_at"]
    if not isinstance(expires_at_raw, str):
        _ = await delete_session(hash_session_token(session_token))
        return None

    expires_at = datetime.fromisoformat(expires_at_raw)
    if expires_at <= datetime.now(UTC):
        _ = await delete_session(hash_session_token(session_token))
        return None

    return {
        "id": session_user["user_id"],
        "username": session_user["username"],
        "created_at": session_user["created_at"],
        "auth_method": "session",
    }


async def get_session_user_or_401(
    session_token: Annotated[str | None, Cookie(alias=settings.session_cookie_name)] = None,
) -> UserPayload:
    session_user = await _get_session_user_payload(session_token)
    if session_user is not None:
        return session_user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )


async def get_current_user(
    session_token: Annotated[str | None, Cookie(alias=settings.session_cookie_name)] = None,
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> UserPayload:
    session_user = await _get_session_user_payload(session_token)
    if session_user is not None:
        return session_user

    api_key = x_api_key
    if api_key is None and authorization is not None and authorization.startswith("Bearer "):
        api_key = authorization[7:].strip()

    if api_key:
        api_key_user = await get_api_key_user(hash_api_key(api_key))
        if api_key_user is not None:
            return {
                "id": api_key_user["id"],
                "username": api_key_user["username"],
                "created_at": api_key_user["created_at"],
                "auth_method": "api_key",
                "api_key_id": api_key_user["api_key_id"],
            }

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )
