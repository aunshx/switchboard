from __future__ import annotations

from datetime import UTC, datetime

from backend.tooling import ToolDefinition, ToolSpec, build_tool_registry
from pydantic import BaseModel, ConfigDict

from .state import Citation, get_state, reset_perplexity_mock_state


class PerplexityMockError(ValueError):
    """Raised when a Perplexity mock tool receives invalid input."""


_VALID_RECENCY: frozenset[str] = frozenset({"hour", "day", "week", "month"})


class PerplexitySearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    search_recency_filter: str | None
    answer: str
    citations: list[Citation]
    issued_at: str
    model: str


def perplexity_search(
    query: str | None = None,
    search_recency_filter: str | None = None,
) -> PerplexitySearchResult:
    """Performs a mocked Perplexity-style web search and returns answer text with citations."""
    if not query or not query.strip():
        raise PerplexityMockError("query is required")
    if (
        search_recency_filter is not None
        and search_recency_filter not in _VALID_RECENCY
    ):
        raise PerplexityMockError(
            f"search_recency_filter must be one of {sorted(_VALID_RECENCY)} when provided"
        )

    state = get_state()
    state.counters.query += 1
    payload = state.answers.resolve(query)

    return PerplexitySearchResult(
        query=query,
        search_recency_filter=search_recency_filter,
        answer=payload.answer,
        citations=[citation.model_copy() for citation in payload.citations],
        issued_at=datetime.now(UTC).isoformat(),
        model="perplexity-mock-1",
    )


_TOOL_DEFINITIONS: list[ToolDefinition] = [
    ToolDefinition(
        name="perplexity_search",
        callable=perplexity_search,
        description=(
            "Performs a Perplexity-style web search and returns an answer with citations. "
            "Mock returns deterministic content; recognises 'launch delay' and 'q3 budget' phrases."
        ),
        required_fields=frozenset({"query"}),
    ),
]


TOOL_REGISTRY: dict[str, ToolSpec] = build_tool_registry(
    service="perplexity",
    definitions=_TOOL_DEFINITIONS,
)


def get_tool_registry() -> dict[str, ToolSpec]:
    return TOOL_REGISTRY


__all__ = [
    "PerplexityMockError",
    "PerplexitySearchResult",
    "TOOL_REGISTRY",
    "get_tool_registry",
    "perplexity_search",
    "reset_perplexity_mock_state",
]
