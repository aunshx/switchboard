from __future__ import annotations

from datetime import UTC, datetime, timedelta

from backend.mock_service import MockService
from pydantic import BaseModel, ConfigDict, Field

BASE_TIME = datetime(2026, 4, 8, 13, 0, tzinfo=UTC)


def _iso(offset_minutes: int) -> str:
    return (BASE_TIME + timedelta(minutes=offset_minutes)).isoformat()


# ---------------------------------------------------------------------------
# Entity models
# ---------------------------------------------------------------------------


class LinearWorkspace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    url_key: str


class LinearUser(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    email: str
    displayName: str
    active: bool
    isMe: bool


class LinearTeam(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    key: str
    name: str
    description: str
    createdAt: str
    updatedAt: str
    memberIds: list[str]


class LinearIssueStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    team: str
    type: str
    position: float


class LinearLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    color: str | None = None
    team: str | None = None
    isGroup: bool = False
    parentId: str | None = None
    description: str
    createdAt: str
    updatedAt: str


class LinearProjectLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    color: str | None = None
    createdAt: str
    updatedAt: str


class LinearCycle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    team: str
    number: int
    startsAt: str
    endsAt: str
    type: str


class LinearInitiative(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: str
    createdAt: str
    updatedAt: str


class LinearProject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    team: str
    lead: str | None = None
    summary: str
    description: str
    state: str
    priority: int
    icon: str | None = None
    color: str | None = None
    labels: list[str]
    startDate: str | None = None
    targetDate: str | None = None
    initiatives: list[str]
    createdAt: str
    updatedAt: str


class LinearIssueLink(BaseModel):
    """External link attached to a Linear issue."""

    model_config = ConfigDict(extra="forbid")

    url: str
    title: str


class LinearIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    description: str
    team: str
    state: str
    assignee: str | None = None
    delegate: str | None = None
    cycle: str | None = None
    project: str | None = None
    milestone: str | None = None
    parentId: str | None = None
    priority: int
    dueDate: str | None = None
    labels: list[str]
    links: list[LinearIssueLink]
    blocks: list[str]
    blockedBy: list[str]
    relatedTo: list[str]
    duplicateOf: str | None = None
    comments: list[str]
    createdAt: str
    updatedAt: str
    archived: bool = False


class LinearComment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    issueId: str
    parentId: str | None
    body: str
    userId: str
    createdAt: str
    updatedAt: str


class LinearDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    slug: str
    title: str
    content: str
    icon: str | None = None
    color: str | None = None
    project: str | None = None
    creatorId: str
    initiativeId: str | None = None
    createdAt: str
    updatedAt: str
    archived: bool = False


class LinearCounters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue_eng: int = 5
    issue_gro: int = 2
    comment: int = 100
    label: int = 100
    project: int = 100
    document: int = 100


class LinearState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace: LinearWorkspace
    users: list[LinearUser]
    teams: list[LinearTeam]
    statuses: list[LinearIssueStatus]
    labels: list[LinearLabel]
    project_labels: list[LinearProjectLabel]
    cycles: list[LinearCycle]
    initiatives: list[LinearInitiative]
    projects: list[LinearProject]
    issues: list[LinearIssue]
    comments: list[LinearComment]
    documents: list[LinearDocument]
    counters: LinearCounters = Field(default_factory=LinearCounters)

    # ----- lookups ---------------------------------------------------------

    def user(self, user_id: str) -> LinearUser | None:
        return next((u for u in self.users if u.id == user_id), None)

    def team(self, team_id: str) -> LinearTeam | None:
        return next((t for t in self.teams if t.id == team_id), None)

    def status(self, status_id: str) -> LinearIssueStatus | None:
        return next((s for s in self.statuses if s.id == status_id), None)

    def label(self, label_id: str) -> LinearLabel | None:
        return next((l for l in self.labels if l.id == label_id), None)

    def cycle(self, cycle_id: str) -> LinearCycle | None:
        return next((c for c in self.cycles if c.id == cycle_id), None)

    def project(self, project_id: str) -> LinearProject | None:
        return next((p for p in self.projects if p.id == project_id), None)

    def initiative(self, initiative_id: str) -> LinearInitiative | None:
        return next((i for i in self.initiatives if i.id == initiative_id), None)

    def issue(self, issue_id: str) -> LinearIssue | None:
        return next((i for i in self.issues if i.id == issue_id), None)

    def comment(self, comment_id: str) -> LinearComment | None:
        return next((c for c in self.comments if c.id == comment_id), None)

    def document(self, doc_id: str) -> LinearDocument | None:
        return next((d for d in self.documents if d.id == doc_id), None)


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

SEED_WORKSPACE = LinearWorkspace(
    id="ws_instalily", name="Instalily", url_key="instalily"
)

USER_AVERY = LinearUser(
    id="user_me",
    name="Avery Quinn",
    email="avery@corp.com",
    displayName="avery",
    active=True,
    isMe=True,
)
USER_MORGAN = LinearUser(
    id="user_morgan",
    name="Morgan Lee",
    email="morgan@corp.com",
    displayName="morgan",
    active=True,
    isMe=False,
)
USER_NADIA = LinearUser(
    id="user_nadia",
    name="Nadia Patel",
    email="nadia@corp.com",
    displayName="nadia",
    active=True,
    isMe=False,
)
USER_JORDAN = LinearUser(
    id="user_jordan",
    name="Jordan Rivera",
    email="jordan@corp.com",
    displayName="jordan",
    active=True,
    isMe=False,
)
USER_SAM = LinearUser(
    id="user_sam",
    name="Sam Chen",
    email="sam@corp.com",
    displayName="sam",
    active=True,
    isMe=False,
)

SEED_USERS: list[LinearUser] = [
    USER_AVERY,
    USER_MORGAN,
    USER_NADIA,
    USER_JORDAN,
    USER_SAM,
]


TEAM_ENG = LinearTeam(
    id="team_eng",
    key="ENG",
    name="Engineering",
    description="Platform and product engineering",
    createdAt=_iso(-60 * 24 * 90),
    updatedAt=_iso(-60 * 24),
    memberIds=["user_me", "user_morgan", "user_jordan"],
)

TEAM_GRO = LinearTeam(
    id="team_gro",
    key="GRO",
    name="Growth",
    description="Growth, lifecycle, and onboarding",
    createdAt=_iso(-60 * 24 * 60),
    updatedAt=_iso(-60 * 12),
    memberIds=["user_nadia", "user_sam", "user_me"],
)

SEED_TEAMS: list[LinearTeam] = [TEAM_ENG, TEAM_GRO]


_STATUS_NAMES = [
    "Triage",
    "Backlog",
    "Todo",
    "In Progress",
    "In Review",
    "Done",
    "Canceled",
]


def _build_statuses_for(team: LinearTeam) -> list[LinearIssueStatus]:
    statuses: list[LinearIssueStatus] = []
    for index, name in enumerate(_STATUS_NAMES):
        sid = f"status_{team.id[5:]}_{name.lower().replace(' ', '_')}"
        status_type = (
            "completed"
            if name == "Done"
            else (
                "canceled"
                if name == "Canceled"
                else "started" if name in {"In Progress", "In Review"} else "unstarted"
            )
        )
        statuses.append(
            LinearIssueStatus(
                id=sid, name=name, team=team.id, type=status_type, position=float(index)
            )
        )
    return statuses


SEED_STATUSES: list[LinearIssueStatus] = [
    *_build_statuses_for(TEAM_ENG),
    *_build_statuses_for(TEAM_GRO),
]


LABEL_BUG = LinearLabel(
    id="label_bug",
    name="bug",
    color="#e11d48",
    team=None,
    isGroup=False,
    parentId=None,
    description="Defects in shipped functionality",
    createdAt=_iso(-60 * 24 * 30),
    updatedAt=_iso(-60 * 24),
)
LABEL_FEATURE = LinearLabel(
    id="label_feature",
    name="feature",
    color="#0ea5e9",
    team=None,
    isGroup=False,
    parentId=None,
    description="New product capabilities",
    createdAt=_iso(-60 * 24 * 30),
    updatedAt=_iso(-60 * 24),
)
LABEL_ENG_INFRA = LinearLabel(
    id="label_eng_infra",
    name="infra",
    color="#22c55e",
    team="team_eng",
    isGroup=False,
    parentId=None,
    description="Infrastructure and tooling",
    createdAt=_iso(-60 * 24 * 20),
    updatedAt=_iso(-60 * 24),
)
LABEL_GRO_LIFECYCLE = LinearLabel(
    id="label_gro_lifecycle",
    name="lifecycle",
    color="#a855f7",
    team="team_gro",
    isGroup=False,
    parentId=None,
    description="Lifecycle email and onboarding",
    createdAt=_iso(-60 * 24 * 14),
    updatedAt=_iso(-60 * 6),
)
SEED_LABELS: list[LinearLabel] = [
    LABEL_BUG,
    LABEL_FEATURE,
    LABEL_ENG_INFRA,
    LABEL_GRO_LIFECYCLE,
]


PROJECT_LABEL_LAUNCH = LinearProjectLabel(
    id="plabel_launch",
    name="launch",
    color="#f59e0b",
    createdAt=_iso(-60 * 24 * 10),
    updatedAt=_iso(-60 * 4),
)
SEED_PROJECT_LABELS: list[LinearProjectLabel] = [PROJECT_LABEL_LAUNCH]


CYCLE_ENG_PREV = LinearCycle(
    id="cycle_eng_previous",
    team="team_eng",
    number=12,
    startsAt=_iso(-60 * 24 * 21),
    endsAt=_iso(-60 * 24 * 7),
    type="previous",
)
CYCLE_ENG_CURRENT = LinearCycle(
    id="cycle_eng_current",
    team="team_eng",
    number=13,
    startsAt=_iso(-60 * 24 * 7),
    endsAt=_iso(60 * 24 * 7),
    type="current",
)
CYCLE_ENG_NEXT = LinearCycle(
    id="cycle_eng_next",
    team="team_eng",
    number=14,
    startsAt=_iso(60 * 24 * 7),
    endsAt=_iso(60 * 24 * 21),
    type="next",
)
CYCLE_GRO_CURRENT = LinearCycle(
    id="cycle_gro_current",
    team="team_gro",
    number=7,
    startsAt=_iso(-60 * 24 * 5),
    endsAt=_iso(60 * 24 * 9),
    type="current",
)
SEED_CYCLES: list[LinearCycle] = [
    CYCLE_ENG_PREV,
    CYCLE_ENG_CURRENT,
    CYCLE_ENG_NEXT,
    CYCLE_GRO_CURRENT,
]


INITIATIVE_H1_PLATFORM = LinearInitiative(
    id="init_h1_platform",
    name="H1 Platform Hardening",
    description="Reliability, latency, observability for the platform.",
    createdAt=_iso(-60 * 24 * 60),
    updatedAt=_iso(-60 * 24 * 4),
)
SEED_INITIATIVES: list[LinearInitiative] = [INITIATIVE_H1_PLATFORM]


PROJECT_ORCHESTRATOR = LinearProject(
    id="proj_orchestrator",
    name="Tool Orchestrator",
    team="team_eng",
    lead="user_me",
    summary="Multi-tool chat harness backed by 191 mock tools.",
    description="Owns the orchestration layer, routing strategy, and test harness.",
    state="started",
    priority=1,
    icon="🤖",
    color="#6366f1",
    labels=["plabel_launch"],
    startDate=_iso(-60 * 24 * 14)[:10],
    targetDate=_iso(60 * 24 * 14)[:10],
    initiatives=["init_h1_platform"],
    createdAt=_iso(-60 * 24 * 14),
    updatedAt=_iso(-60 * 2),
)
PROJECT_ONBOARDING = LinearProject(
    id="proj_onboarding",
    name="Onboarding Refresh",
    team="team_gro",
    lead="user_nadia",
    summary="Refresh new-hire onboarding flow.",
    description="Lifecycle emails, onboarding tasks, and welcome assets.",
    state="planned",
    priority=2,
    icon="🎉",
    color="#22c55e",
    labels=[],
    startDate=_iso(60 * 24 * 7)[:10],
    targetDate=_iso(60 * 24 * 28)[:10],
    initiatives=[],
    createdAt=_iso(-60 * 24 * 7),
    updatedAt=_iso(-60 * 12),
)
PROJECT_RENEWALS = LinearProject(
    id="proj_renewals",
    name="Renewals Risk",
    team="team_gro",
    lead="user_jordan",
    summary="Reduce churn on at-risk renewals.",
    description="Outreach playbooks, retention dashboards, customer-success workflows.",
    state="started",
    priority=1,
    icon="📉",
    color="#ef4444",
    labels=[],
    startDate=_iso(-60 * 24 * 21)[:10],
    targetDate=_iso(60 * 24 * 30)[:10],
    initiatives=[],
    createdAt=_iso(-60 * 24 * 21),
    updatedAt=_iso(-60 * 8),
)
SEED_PROJECTS: list[LinearProject] = [
    PROJECT_ORCHESTRATOR,
    PROJECT_ONBOARDING,
    PROJECT_RENEWALS,
]


ISSUE_ENG_1 = LinearIssue(
    id="ENG-1",
    title="Wire /chat endpoint to orchestrator",
    description="Implement POST /chat to drive the multi-tool harness. Required for case study.",
    team="team_eng",
    state="status_eng_in_progress",
    assignee="user_me",
    cycle="cycle_eng_current",
    project="proj_orchestrator",
    priority=1,
    dueDate=_iso(60 * 24 * 3)[:10],
    labels=["label_feature", "label_eng_infra"],
    links=[],
    blocks=["ENG-2"],
    blockedBy=[],
    relatedTo=[],
    duplicateOf=None,
    comments=["comment_eng1_1"],
    createdAt=_iso(-60 * 24 * 3),
    updatedAt=_iso(-60 * 1),
)
ISSUE_ENG_2 = LinearIssue(
    id="ENG-2",
    title="Tool routing strategy decision doc",
    description="Pick between two-stage routing, semantic retrieval, or service-first.",
    team="team_eng",
    state="status_eng_todo",
    assignee="user_morgan",
    cycle="cycle_eng_current",
    project="proj_orchestrator",
    priority=2,
    dueDate=_iso(60 * 24 * 7)[:10],
    labels=["label_eng_infra"],
    links=[],
    blocks=[],
    blockedBy=["ENG-1"],
    relatedTo=[],
    duplicateOf=None,
    comments=[],
    createdAt=_iso(-60 * 24 * 2),
    updatedAt=_iso(-60 * 4),
)
ISSUE_ENG_3 = LinearIssue(
    id="ENG-3",
    title="Launch delay: orchestrator latency spike",
    description="Tool dispatch p95 jumped from 320ms to 1.4s after the registry refactor.",
    team="team_eng",
    state="status_eng_in_review",
    assignee="user_jordan",
    cycle="cycle_eng_current",
    project="proj_orchestrator",
    priority=1,
    dueDate=_iso(60 * 24 * 1)[:10],
    labels=["label_bug", "label_eng_infra"],
    links=[LinearIssueLink(url="https://example.com/perf-report", title="Perf report")],
    blocks=[],
    blockedBy=[],
    relatedTo=["ENG-1"],
    duplicateOf=None,
    comments=[],
    createdAt=_iso(-60 * 12),
    updatedAt=_iso(-60 * 2),
)
ISSUE_ENG_4 = LinearIssue(
    id="ENG-4",
    title="Add Datadog dashboard for tool calls",
    description="Per-tool latency, error rate, and call count.",
    team="team_eng",
    state="status_eng_backlog",
    assignee=None,
    cycle=None,
    project="proj_orchestrator",
    priority=3,
    dueDate=None,
    labels=["label_eng_infra"],
    links=[],
    blocks=[],
    blockedBy=[],
    relatedTo=[],
    duplicateOf=None,
    comments=[],
    createdAt=_iso(-60 * 24 * 5),
    updatedAt=_iso(-60 * 24 * 5),
)
ISSUE_ENG_5 = LinearIssue(
    id="ENG-5",
    title="Resolved last cycle: harness skeleton",
    description="Initial scaffolding committed last cycle.",
    team="team_eng",
    state="status_eng_done",
    assignee="user_me",
    cycle="cycle_eng_previous",
    project="proj_orchestrator",
    priority=2,
    dueDate=None,
    labels=["label_feature"],
    links=[],
    blocks=[],
    blockedBy=[],
    relatedTo=[],
    duplicateOf=None,
    comments=[],
    createdAt=_iso(-60 * 24 * 18),
    updatedAt=_iso(-60 * 24 * 8),
)
ISSUE_GRO_1 = LinearIssue(
    id="GRO-1",
    title="Lifecycle: welcome email v3",
    description="Refresh subject lines and CTA. Owner: Nadia.",
    team="team_gro",
    state="status_gro_in_progress",
    assignee="user_nadia",
    cycle="cycle_gro_current",
    project="proj_onboarding",
    priority=2,
    dueDate=_iso(60 * 24 * 5)[:10],
    labels=["label_gro_lifecycle"],
    links=[],
    blocks=[],
    blockedBy=[],
    relatedTo=[],
    duplicateOf=None,
    comments=[],
    createdAt=_iso(-60 * 24 * 6),
    updatedAt=_iso(-60 * 12),
)
ISSUE_GRO_2 = LinearIssue(
    id="GRO-2",
    title="Renewal risk dashboard",
    description="Surface at-risk customers from CRM signals.",
    team="team_gro",
    state="status_gro_todo",
    assignee="user_jordan",
    cycle="cycle_gro_current",
    project="proj_renewals",
    priority=1,
    dueDate=_iso(60 * 24 * 9)[:10],
    labels=[],
    links=[],
    blocks=[],
    blockedBy=[],
    relatedTo=[],
    duplicateOf=None,
    comments=[],
    createdAt=_iso(-60 * 24 * 4),
    updatedAt=_iso(-60 * 6),
)
SEED_ISSUES: list[LinearIssue] = [
    ISSUE_ENG_1,
    ISSUE_ENG_2,
    ISSUE_ENG_3,
    ISSUE_ENG_4,
    ISSUE_ENG_5,
    ISSUE_GRO_1,
    ISSUE_GRO_2,
]


COMMENT_ENG1_1 = LinearComment(
    id="comment_eng1_1",
    issueId="ENG-1",
    parentId=None,
    body="Routing strategy still TBD — see ENG-2.",
    userId="user_morgan",
    createdAt=_iso(-60 * 24 * 2),
    updatedAt=_iso(-60 * 24 * 2),
)
SEED_COMMENTS: list[LinearComment] = [COMMENT_ENG1_1]


DOC_LAUNCH_PLAN = LinearDocument(
    id="doc_launch_plan",
    slug="launch-plan",
    title="Orchestrator Launch Plan",
    content="# Launch Plan\n\n- T-14: Cut scope.\n- T-7: Freeze list.\n- T-0: GA.",
    icon="🚀",
    color="#6366f1",
    project="proj_orchestrator",
    creatorId="user_me",
    initiativeId="init_h1_platform",
    createdAt=_iso(-60 * 24 * 10),
    updatedAt=_iso(-60 * 24 * 1),
)
DOC_RENEWAL_PLAY = LinearDocument(
    id="doc_renewal_play",
    slug="renewal-playbook",
    title="Renewal Risk Playbook",
    content="# Renewal Playbook\n\nFlag at-risk accounts 60 days before renewal.",
    icon="📒",
    color="#ef4444",
    project="proj_renewals",
    creatorId="user_jordan",
    initiativeId=None,
    createdAt=_iso(-60 * 24 * 7),
    updatedAt=_iso(-60 * 12),
)
SEED_DOCUMENTS: list[LinearDocument] = [DOC_LAUNCH_PLAN, DOC_RENEWAL_PLAY]


SEED_STATE = LinearState(
    workspace=SEED_WORKSPACE,
    users=SEED_USERS,
    teams=SEED_TEAMS,
    statuses=SEED_STATUSES,
    labels=SEED_LABELS,
    project_labels=SEED_PROJECT_LABELS,
    cycles=SEED_CYCLES,
    initiatives=SEED_INITIATIVES,
    projects=SEED_PROJECTS,
    issues=SEED_ISSUES,
    comments=SEED_COMMENTS,
    documents=SEED_DOCUMENTS,
)


class LinearMockState(MockService[LinearState]):
    def _seed_state(self) -> LinearState:
        return SEED_STATE.model_copy(deep=True)


SERVICE = LinearMockState()


def get_state() -> LinearState:
    return SERVICE.get_state()


def reset_linear_mock_state() -> None:
    SERVICE.reset()


def snapshot_state() -> LinearState:
    return SERVICE.snapshot()
