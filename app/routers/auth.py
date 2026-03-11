from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.config import settings
from app.models.auth import (
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    ApiKeyResponse,
    AuthSessionResponse,
    LoginRequest,
    SignupRequest,
    UserResponse,
)
from app.services.auth import (
    api_key_prefix,
    clear_session_cookie,
    create_user_session,
    generate_api_key,
    get_current_user,
    get_session_user_or_401,
    hash_api_key,
    hash_password,
    invalidate_session,
    normalize_username,
    set_session_cookie,
    verify_password,
)
from app.services.database import (
    create_api_key,
    create_user,
    get_user_by_username,
    list_api_keys,
    revoke_api_key,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
CurrentUser = Annotated[dict[str, object], Depends(get_current_user)]
SessionUser = Annotated[dict[str, object], Depends(get_session_user_or_401)]


def _to_api_key_response(row: dict[str, object]) -> ApiKeyResponse:
    return ApiKeyResponse(
        id=str(row["id"]),
        name=str(row["name"]),
        key_prefix=str(row["key_prefix"]),
        created_at=str(row["created_at"]),
        last_used_at=str(row["last_used_at"]) if row.get("last_used_at") is not None else None,
        revoked_at=str(row["revoked_at"]) if row.get("revoked_at") is not None else None,
    )


def _to_user_response(row: dict[str, object]) -> UserResponse:
    return UserResponse(
        id=str(row["id"]),
        username=str(row["username"]),
        created_at=str(row["created_at"]),
    )


@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(body: SignupRequest, response: Response) -> AuthSessionResponse:
    username = normalize_username(body.username)
    password_hash, password_salt = hash_password(body.password)

    try:
        user = await create_user(
            username=username,
            password_hash=password_hash,
            password_salt=password_salt,
        )
    except aiosqlite.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username is already taken",
        ) from exc

    session_token = await create_user_session(str(user["id"]))
    set_session_cookie(response, session_token)
    return AuthSessionResponse(user=_to_user_response(user))


@router.post("/login")
async def login(body: LoginRequest, response: Response) -> AuthSessionResponse:
    username = normalize_username(body.username)
    user = await get_user_by_username(username)
    if user is None or not verify_password(
        body.password,
        str(user["password_hash"]),
        str(user["password_salt"]),
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    session_token = await create_user_session(str(user["id"]))
    set_session_cookie(response, session_token)
    return AuthSessionResponse(user=_to_user_response(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    current_user: SessionUser,
) -> Response:
    _ = current_user
    session_token = request.cookies.get(settings.session_cookie_name)
    if session_token is not None:
        await invalidate_session(session_token)

    cleared_response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_session_cookie(cleared_response)
    return cleared_response


@router.get("/me")
async def get_me(
    current_user: CurrentUser,
) -> AuthSessionResponse:
    return AuthSessionResponse(user=_to_user_response(current_user))


@router.get("/api-keys")
async def list_api_keys_endpoint(current_user: SessionUser) -> list[ApiKeyResponse]:
    rows = await list_api_keys(str(current_user["id"]))
    return [_to_api_key_response(row) for row in rows]


@router.post("/api-keys", status_code=status.HTTP_201_CREATED)
async def create_api_key_endpoint(
    body: ApiKeyCreateRequest,
    current_user: SessionUser,
) -> ApiKeyCreateResponse:
    name = body.name.strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="API key name cannot be empty",
        )

    plain_api_key = generate_api_key()
    row = await create_api_key(
        user_id=str(current_user["id"]),
        name=name,
        key_hash=hash_api_key(plain_api_key),
        key_prefix=api_key_prefix(plain_api_key),
    )
    return ApiKeyCreateResponse(api_key=plain_api_key, key=_to_api_key_response(row))


@router.delete("/api-keys/{api_key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key_endpoint(api_key_id: str, current_user: SessionUser) -> Response:
    revoked = await revoke_api_key(str(current_user["id"]), api_key_id)
    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API key {api_key_id} not found",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
