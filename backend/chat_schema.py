from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "tool", "system"] = Field(
        description="The role of the message sender."
    )
    content: str = Field(
        description="Message text. Tool messages may carry serialized JSON."
    )


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(
        min_length=1,
        description="Full conversation so far, oldest first.",
    )


class ToolCallLog(BaseModel):
    name: str = Field(min_length=1, description="Registered tool name.")
    arguments: dict[str, Any] = Field(
        default_factory=dict, description="Arguments passed to the tool."
    )
    result: Any = Field(
        default=None, description="JSON-serializable tool result, or null on error."
    )
    error: str | None = Field(
        default=None, description="Error message if the call failed; null otherwise."
    )


class ChatResponse(BaseModel):
    messages: list[ChatMessage] = Field(
        description="Updated conversation including the assistant's reply."
    )
    tool_calls: list[ToolCallLog] = Field(
        default_factory=list,
        description="Ordered log of tool calls made this turn.",
    )
