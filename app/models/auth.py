from pydantic import BaseModel, Field


class SignupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_\-.]+$")
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: str
    username: str
    created_at: str


class AuthSessionResponse(BaseModel):
    user: UserResponse


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=50)


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    key_prefix: str
    created_at: str
    last_used_at: str | None = None
    revoked_at: str | None = None


class ApiKeyCreateResponse(BaseModel):
    api_key: str
    key: ApiKeyResponse
