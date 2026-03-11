from typing import Literal

from pydantic import BaseModel, Field


class ModelParams(BaseModel):
    """Model parameters for LLM inference."""

    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1, le=65536)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    enable_thinking: bool = Field(default=True)


class ChatMessage(BaseModel):
    """A single message in a conversation."""

    role: Literal["user", "assistant", "system"]
    content: str
    reasoning: str | None = None


class ChatRequest(BaseModel):
    """Request to send a message in a conversation."""

    message: str = Field(min_length=1, max_length=65536)
    conversation_id: str | None = None


class ConversationResponse(BaseModel):
    """Response containing conversation details."""

    id: str
    title: str
    system_prompt: str
    model_params: ModelParams
    created_at: str
    updated_at: str


class ConversationUpdate(BaseModel):
    """Request to update conversation settings."""

    title: str | None = None
    system_prompt: str | None = None
    model_params: ModelParams | None = None


class MessageResponse(BaseModel):
    """Response containing a message from the conversation."""

    id: int
    conversation_id: str
    role: str
    content: str
    reasoning: str | None = None
    created_at: str
