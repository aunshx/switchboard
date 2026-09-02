from __future__ import annotations

from typing import Any

from backend.chat_schema import ChatMessage, ChatRequest, ChatResponse, ToolCallLog
from backend.github_mock import TOOL_REGISTRY as GITHUB_TOOL_REGISTRY
from backend.github_mock import reset_github_mock_state
from backend.gmail_mock import TOOL_REGISTRY as GMAIL_TOOL_REGISTRY
from backend.gmail_mock import reset_gmail_mock_state
from backend.googlecalendar_mock import TOOL_REGISTRY as GOOGLECALENDAR_TOOL_REGISTRY
from backend.googlecalendar_mock import (
    reset_googlecalendar_mock_state,
)
from backend.googledrive_mock import TOOL_REGISTRY as GOOGLEDRIVE_TOOL_REGISTRY
from backend.googledrive_mock import (
    reset_googledrive_mock_state,
)
from backend.linear_mock import TOOL_REGISTRY as LINEAR_TOOL_REGISTRY
from backend.linear_mock import reset_linear_mock_state
from backend.perplexity_mock import TOOL_REGISTRY as PERPLEXITY_TOOL_REGISTRY
from backend.perplexity_mock import (
    reset_perplexity_mock_state,
)
from backend.slack_mock import TOOL_REGISTRY as SLACK_TOOL_REGISTRY
from backend.slack_mock import reset_slack_mock_state
from backend.solution import chat
from backend.tooling import ToolCallable, ToolSpec
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def _combined_registry() -> dict[str, ToolSpec]:
    return {
        **GMAIL_TOOL_REGISTRY,
        **GOOGLECALENDAR_TOOL_REGISTRY,
        **GOOGLEDRIVE_TOOL_REGISTRY,
        **SLACK_TOOL_REGISTRY,
        **LINEAR_TOOL_REGISTRY,
        **PERPLEXITY_TOOL_REGISTRY,
        **GITHUB_TOOL_REGISTRY,
    }


def list_available_tools() -> list[str]:
    return sorted(_combined_registry())


def get_all_tool_specs() -> dict[str, ToolSpec]:
    return dict(_combined_registry())


def get_tool_spec(name: str) -> ToolSpec:
    registry = _combined_registry()
    return registry[name]


def get_tool_callable(name: str) -> ToolCallable:
    return get_tool_spec(name).callable


def get_openai_tools(names: list[str] | None = None) -> list[dict[str, Any]]:
    selected = names or list_available_tools()
    return [_openai_tool_entry(get_tool_spec(name)) for name in selected]


def get_tool_catalog() -> list[dict[str, Any]]:
    return [
        _tool_catalog_entry(spec) for _, spec in sorted(get_all_tool_specs().items())
    ]


def reset_all_mock_state() -> None:
    reset_gmail_mock_state()
    reset_googlecalendar_mock_state()
    reset_googledrive_mock_state()
    reset_slack_mock_state()
    reset_linear_mock_state()
    reset_perplexity_mock_state()
    reset_github_mock_state()


def _tool_catalog_entry(spec: ToolSpec) -> dict[str, Any]:
    return {
        "name": spec.name,
        "service": spec.service,
        "description": spec.description,
        "docstring": spec.docstring,
        "argsSchema": spec.args_model.model_json_schema(),
        "resultSchema": spec.result_model.model_json_schema(),
    }


def _openai_tool_entry(spec: ToolSpec) -> dict[str, Any]:
    """Render a ToolSpec as an OpenAI strict-mode function entry.

    Pydantic emits a strict-compliant schema *natively* when every nested
    object is itself a BaseModel with ``extra='forbid'`` and every field is
    required (no defaults). The only OpenAI-specific adaptation is that
    strict mode wants every top-level property name listed in ``required``
    even though some are nullable — the model is expected to pass null for
    unused optionals. We do that one line here and nothing else.
    """
    parameters = spec.args_model.model_json_schema()
    parameters["required"] = list(parameters.get("properties", {}).keys())
    return {
        "type": "function",
        "name": spec.name,
        "description": spec.docstring,
        "parameters": parameters,
        "strict": True,
    }


reset_all_mock_state()

app = FastAPI(title="mcp-casestudy tool server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/tools")
def list_tools() -> dict[str, Any]:
    return {"tools": get_tool_catalog()}


@app.post("/reset")
def reset_tools() -> dict[str, Any]:
    reset_all_mock_state()
    return {"ok": True, "serviceCount": 7, "toolCount": len(list_available_tools())}


@app.get("/state")
def dump_state() -> dict[str, Any]:
    """Read-only snapshot of every mock service's in-memory state.

    Automated checks run in a separate process from this server, so they cannot
    read the mock state directly. They call this endpoint after a scenario to
    assert that the agent's tool calls produced the correct end-state.
    """
    from backend.github_mock.state import snapshot_state as _github_state
    from backend.gmail_mock.state import snapshot_state as _gmail_state
    from backend.googlecalendar_mock.state import (
        snapshot_state as _googlecalendar_state,
    )
    from backend.googledrive_mock.state import snapshot_state as _googledrive_state
    from backend.linear_mock.state import snapshot_state as _linear_state
    from backend.perplexity_mock.state import snapshot_state as _perplexity_state
    from backend.slack_mock.state import snapshot_state as _slack_state

    return {
        "gmail": _gmail_state(),
        "googlecalendar": _googlecalendar_state(),
        "googledrive": _googledrive_state(),
        "slack": _slack_state(),
        "linear": _linear_state(),
        "perplexity": _perplexity_state(),
        "github": _github_state(),
    }


app.post("/chat", response_model=ChatResponse)(chat)


__all__ = [
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "ToolCallLog",
    "app",
    "chat",
    "get_all_tool_specs",
    "get_tool_callable",
    "get_tool_catalog",
    "get_openai_tools",
    "get_tool_spec",
    "health_check",
    "list_available_tools",
    "list_tools",
    "reset_all_mock_state",
    "reset_tools",
]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=False)
