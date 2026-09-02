from __future__ import annotations

from backend.mock_service import MockService
from pydantic import BaseModel, ConfigDict, Field


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    url: str
    snippet: str


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    citations: list[Citation]


class AnswerCatalog(BaseModel):
    """The fixed set of canned answers the mock knows how to serve.

    Explicit fields (not a dict) so the schema is enforced and the
    resolution logic lives on the model itself.
    """

    model_config = ConfigDict(extra="forbid")

    default: Answer
    launch_delay: Answer
    q3_budget: Answer

    def resolve(self, query: str) -> Answer:
        needle = query.lower()
        if "launch delay" in needle:
            return self.launch_delay
        if "q3 budget" in needle:
            return self.q3_budget
        return self.default


class PerplexityCounters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: int = 0


class PerplexityState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: AnswerCatalog
    counters: PerplexityCounters = Field(default_factory=PerplexityCounters)


# ---------------------------------------------------------------------------
# Seed citations — one named Citation per source.
# ---------------------------------------------------------------------------

CITATION_ANTHROPIC_TOOL_USE = Citation(
    title="Mocked: Anthropic Tool Use Best Practices",
    url="https://example.com/anthropic/tool-use",
    snippet="Pass the smallest set of tools that can solve the task.",
)

CITATION_OPENAI_FUNCTION_CALLING = Citation(
    title="Mocked: OpenAI Function Calling Guide",
    url="https://example.com/openai/function-calling",
    snippet="Use strict mode to enforce schema-conformant tool arguments.",
)

CITATION_SAAS_LAUNCH_RISK = Citation(
    title="Mocked: SaaS Launch Risk Patterns 2025",
    url="https://example.com/saas/launch-risk",
    snippet="70% of launch slips trace to scope creep in the final sprint.",
)

CITATION_PRE_GA_COMPLIANCE = Citation(
    title="Mocked: Pre-GA Compliance Checklists",
    url="https://example.com/compliance/pre-ga",
    snippet="Compliance review must complete two weeks before GA.",
)

CITATION_ONCALL_TEMPLATES = Citation(
    title="Mocked: On-Call Rotation Templates",
    url="https://example.com/oncall/templates",
    snippet="Rotations must be staffed before the launch surface goes live.",
)

CITATION_SAAS_BUDGET_Q3 = Citation(
    title="Mocked: SaaS Budget Benchmarks Q3 2025",
    url="https://example.com/saas/budget-q3",
    snippet="R&D spend at 38-45% of opex is the median for Series B/C SaaS.",
)


# ---------------------------------------------------------------------------
# Seed answers — composed from named citations.
# ---------------------------------------------------------------------------

DEFAULT_ANSWER = Answer(
    answer=(
        "No live web access in the mock environment. The Perplexity stub returns "
        "deterministic, fixture-backed responses so tool orchestration and citation "
        "handling can be tested end-to-end without external network calls."
    ),
    citations=[
        CITATION_ANTHROPIC_TOOL_USE,
        CITATION_OPENAI_FUNCTION_CALLING,
    ],
)

LAUNCH_DELAY_ANSWER = Answer(
    answer=(
        "Recent reporting on launch-delay incidents at mid-stage SaaS companies "
        "highlights three recurring causes: late-arriving compliance reviews, "
        "scope creep in the final week before GA, and missing on-call rotations "
        "for the new surface. Mitigations: cut scope at T-14, lock the freeze "
        "list at T-7, and stand up the on-call schedule before code complete."
    ),
    citations=[
        CITATION_SAAS_LAUNCH_RISK,
        CITATION_PRE_GA_COMPLIANCE,
        CITATION_ONCALL_TEMPLATES,
    ],
)

Q3_BUDGET_ANSWER = Answer(
    answer=(
        "Q3 budget benchmarks across mid-stage SaaS show R&D averaging 38-45% of "
        "operating spend, GTM 30-35%, and G&A 15-22%. Companies tracking ahead of "
        "plan typically reallocate Q4 unspent G&A into focused R&D bets."
    ),
    citations=[CITATION_SAAS_BUDGET_Q3],
)


SEED_CATALOG = AnswerCatalog(
    default=DEFAULT_ANSWER,
    launch_delay=LAUNCH_DELAY_ANSWER,
    q3_budget=Q3_BUDGET_ANSWER,
)


class PerplexityMockState(MockService[PerplexityState]):
    def _seed_state(self) -> PerplexityState:
        # model_copy(deep=True) so the singleton's seed objects are never mutated
        # by code that holds references to live state.
        return PerplexityState(answers=SEED_CATALOG.model_copy(deep=True))


SERVICE = PerplexityMockState()


def get_state() -> PerplexityState:
    return SERVICE.get_state()


def reset_perplexity_mock_state() -> None:
    SERVICE.reset()


def snapshot_state() -> PerplexityState:
    return SERVICE.snapshot()
