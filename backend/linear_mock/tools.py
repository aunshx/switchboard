from __future__ import annotations

from datetime import UTC, datetime
from typing import Iterable, TypeVar

from backend.tooling import ToolDefinition, ToolSpec, build_tool_registry
from pydantic import BaseModel, ConfigDict

from .state import (
    LinearComment,
    LinearCycle,
    LinearDocument,
    LinearInitiative,
    LinearIssue,
    LinearIssueLink,
    LinearIssueStatus,
    LinearLabel,
    LinearProject,
    LinearProjectLabel,
    LinearState,
    LinearTeam,
    LinearUser,
    get_state,
    reset_linear_mock_state,
)


class LinearMockError(ValueError):
    """Raised when a Linear mock tool receives invalid input or missing resources."""


T = TypeVar("T", bound=BaseModel)


# ---------------------------------------------------------------------------
# Public projections
# ---------------------------------------------------------------------------


class PublicLinearUser(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    email: str
    displayName: str
    active: bool
    isMe: bool


class PublicLinearTeam(BaseModel):
    """Team without internal memberIds."""

    model_config = ConfigDict(extra="forbid")

    id: str
    key: str
    name: str
    description: str
    createdAt: str
    updatedAt: str


class PublicLinearIssue(BaseModel):
    """Linear issue projection. Relations may be omitted when includeRelations=False."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    description: str
    team: str
    state: str
    assignee: str | None
    delegate: str | None
    cycle: str | None
    project: str | None
    milestone: str | None
    parentId: str | None
    priority: int
    dueDate: str | None
    labels: list[str]
    links: list[LinearIssueLink]
    blocks: list[str] | None = None
    blockedBy: list[str] | None = None
    relatedTo: list[str] | None = None
    duplicateOf: str | None = None
    comments: list[str]
    createdAt: str
    updatedAt: str
    archived: bool


# ---------------------------------------------------------------------------
# Tool result models
# ---------------------------------------------------------------------------


class PageInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hasNextPage: bool
    hasPreviousPage: bool
    endCursor: str | None
    startCursor: str | None


class ListCommentsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issueId: str
    comments: list[LinearComment]
    count: int


class CreateCommentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comment: LinearComment


class ListCyclesResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    team: str
    cycles: list[LinearCycle]
    count: int


class GetDocumentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document: LinearDocument


class ListDocumentsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    documents: list[LinearDocument]
    pageInfo: PageInfo
    totalCount: int


class GetIssueResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue: PublicLinearIssue


class ListIssuesResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issues: list[PublicLinearIssue]
    pageInfo: PageInfo
    totalCount: int


class ListIssueStatusesResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    team: str
    statuses: list[LinearIssueStatus]
    count: int


class GetIssueStatusResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: LinearIssueStatus


class ListIssueLabelsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    labels: list[LinearLabel]
    pageInfo: PageInfo
    totalCount: int


class CreateLabelResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: LinearLabel


class ListProjectsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projects: list[LinearProject]
    pageInfo: PageInfo
    totalCount: int


class GetProjectResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project: LinearProject


class ListProjectLabelsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projectLabels: list[LinearProjectLabel]
    pageInfo: PageInfo
    totalCount: int


class ListTeamsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    teams: list[PublicLinearTeam]
    pageInfo: PageInfo
    totalCount: int


class GetTeamResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    team: PublicLinearTeam
    memberIds: list[str]


class ListUsersResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    users: list[PublicLinearUser]
    count: int


class GetUserResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user: PublicLinearUser


class DocumentationArticle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    url: str
    snippet: str


class SearchDocumentationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    page: int
    results: list[DocumentationArticle]


# ---------------------------------------------------------------------------
# Resolvers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _resolve_team(query: str | None) -> LinearTeam:
    if query is None:
        raise LinearMockError("team is required")
    state = get_state()
    direct = state.team(query)
    if direct is not None:
        return direct
    needle = query.lower()
    for team in state.teams:
        if team.key.lower() == needle or team.name.lower() == needle:
            return team
    raise LinearMockError(f"Unknown Linear team: {query}")


def _maybe_resolve_team(query: str | None) -> LinearTeam | None:
    if query is None or query == "":
        return None
    return _resolve_team(query)


def _resolve_user(query: str | None) -> LinearUser:
    if query is None:
        raise LinearMockError("user is required")
    state = get_state()
    if query == "me":
        me = state.user("user_me")
        if me is None:
            raise LinearMockError("'me' user not configured")
        return me
    direct = state.user(query)
    if direct is not None:
        return direct
    needle = query.lower()
    for user in state.users:
        if (
            user.email.lower() == needle
            or user.name.lower() == needle
            or user.displayName.lower() == needle
        ):
            return user
    raise LinearMockError(f"Unknown Linear user: {query}")


def _maybe_resolve_user(query: str | None) -> LinearUser | None:
    if query is None or query == "":
        return None
    return _resolve_user(query)


def _resolve_project(query: str | None) -> LinearProject:
    if query is None:
        raise LinearMockError("project is required")
    state = get_state()
    direct = state.project(query)
    if direct is not None:
        return direct
    needle = query.lower()
    for project in state.projects:
        if project.name.lower() == needle:
            return project
    raise LinearMockError(f"Unknown Linear project: {query}")


def _maybe_resolve_project(query: str | None) -> LinearProject | None:
    if query is None or query == "":
        return None
    return _resolve_project(query)


def _resolve_status(
    *, status_id: str | None, name: str | None, team_id: str | None
) -> LinearIssueStatus:
    state = get_state()
    if status_id:
        direct = state.status(status_id)
        if direct is not None:
            return direct
    if name and team_id:
        needle = name.lower()
        for status in state.statuses:
            if status.team == team_id and status.name.lower() == needle:
                return status
    if name and not team_id:
        needle = name.lower()
        matches = [s for s in state.statuses if s.name.lower() == needle]
        if len(matches) == 1:
            return matches[0]
        if matches:
            raise LinearMockError(
                f"Status name {name!r} is ambiguous across teams; supply team explicitly"
            )
    raise LinearMockError("Unable to resolve issue status from given parameters")


def _resolve_label(query: str, *, team_id: str | None = None) -> LinearLabel:
    state = get_state()
    direct = state.label(query)
    if direct is not None:
        return direct
    needle = query.lower()
    for label in state.labels:
        if label.name.lower() == needle and (
            team_id is None or label.team in (None, team_id)
        ):
            return label
    raise LinearMockError(f"Unknown Linear label: {query}")


def _resolve_initiative(query: str) -> LinearInitiative:
    state = get_state()
    direct = state.initiative(query)
    if direct is not None:
        return direct
    needle = query.lower()
    for initiative in state.initiatives:
        if initiative.name.lower() == needle:
            return initiative
    raise LinearMockError(f"Unknown Linear initiative: {query}")


def _resolve_cycle(query: str) -> LinearCycle:
    state = get_state()
    direct = state.cycle(query)
    if direct is None:
        raise LinearMockError(f"Unknown Linear cycle: {query}")
    return direct


# ---------------------------------------------------------------------------
# Public projections
# ---------------------------------------------------------------------------


def _to_public_user(user: LinearUser) -> PublicLinearUser:
    return PublicLinearUser(
        id=user.id,
        name=user.name,
        email=user.email,
        displayName=user.displayName,
        active=user.active,
        isMe=user.isMe,
    )


def _to_public_team(team: LinearTeam) -> PublicLinearTeam:
    return PublicLinearTeam(
        id=team.id,
        key=team.key,
        name=team.name,
        description=team.description,
        createdAt=team.createdAt,
        updatedAt=team.updatedAt,
    )


def _to_public_issue(
    issue: LinearIssue, *, include_relations: bool = True
) -> PublicLinearIssue:
    return PublicLinearIssue(
        id=issue.id,
        title=issue.title,
        description=issue.description,
        team=issue.team,
        state=issue.state,
        assignee=issue.assignee,
        delegate=issue.delegate,
        cycle=issue.cycle,
        project=issue.project,
        milestone=issue.milestone,
        parentId=issue.parentId,
        priority=issue.priority,
        dueDate=issue.dueDate,
        labels=list(issue.labels),
        links=[l.model_copy() for l in issue.links],
        blocks=list(issue.blocks) if include_relations else None,
        blockedBy=list(issue.blockedBy) if include_relations else None,
        relatedTo=list(issue.relatedTo) if include_relations else None,
        duplicateOf=issue.duplicateOf if include_relations else None,
        comments=list(issue.comments),
        createdAt=issue.createdAt,
        updatedAt=issue.updatedAt,
        archived=issue.archived,
    )


# ---------------------------------------------------------------------------
# Pagination / sort
# ---------------------------------------------------------------------------


def _paginate(
    items: list[T], *, after: str | None, before: str | None, limit: int
) -> tuple[list[T], PageInfo]:
    if limit < 1 or limit > 250:
        raise LinearMockError("limit must be between 1 and 250")
    start = 0
    end = len(items)
    if after is not None:
        ids = [item.id for item in items]  # type: ignore[attr-defined]
        if after not in ids:
            raise LinearMockError(f"Unknown pagination cursor 'after': {after}")
        start = ids.index(after) + 1
    if before is not None:
        ids = [item.id for item in items]  # type: ignore[attr-defined]
        if before not in ids:
            raise LinearMockError(f"Unknown pagination cursor 'before': {before}")
        end = ids.index(before)
    page = (
        items[start : start + limit]
        if before is None
        else items[max(start, end - limit) : end]
    )
    return page, PageInfo(
        hasNextPage=start + limit < end,
        hasPreviousPage=start > 0,
        endCursor=page[-1].id if page else None,  # type: ignore[attr-defined]
        startCursor=page[0].id if page else None,  # type: ignore[attr-defined]
    )


def _sort_by(items: Iterable[T], order_by: str) -> list[T]:
    if order_by not in {"createdAt", "updatedAt"}:
        raise LinearMockError("orderBy must be 'createdAt' or 'updatedAt'")
    return sorted(items, key=lambda item: getattr(item, order_by) or "", reverse=True)


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def linear_list_comments(issueId: str | None = None) -> ListCommentsResult:
    """Lists comments on a Linear issue, oldest first."""
    if not issueId:
        raise LinearMockError("issueId is required")
    state = get_state()
    issue = state.issue(issueId)
    if issue is None:
        raise LinearMockError(f"Unknown Linear issue: {issueId}")
    comments = [state.comment(cid) for cid in issue.comments]
    comments = [c for c in comments if c is not None]
    comments.sort(key=lambda c: c.createdAt)
    return ListCommentsResult(
        issueId=issueId,
        comments=[c.model_copy() for c in comments],
        count=len(comments),
    )


def linear_create_comment(
    body: str | None = None,
    issueId: str | None = None,
    parentId: str | None = None,
) -> CreateCommentResult:
    """Creates a comment on a Linear issue, optionally as a reply to an existing comment."""
    if not body or not issueId:
        raise LinearMockError("body and issueId are required")
    state = get_state()
    issue = state.issue(issueId)
    if issue is None:
        raise LinearMockError(f"Unknown Linear issue: {issueId}")
    if parentId is not None and state.comment(parentId) is None:
        raise LinearMockError(f"Unknown parent comment: {parentId}")
    state.counters.comment += 1
    cid = f"comment_{state.counters.comment}"
    now = _now_iso()
    comment = LinearComment(
        id=cid,
        issueId=issueId,
        parentId=parentId,
        body=body,
        userId="user_me",
        createdAt=now,
        updatedAt=now,
    )
    state.comments.append(comment)
    issue.comments.append(cid)
    issue.updatedAt = now
    return CreateCommentResult(comment=comment.model_copy())


def linear_list_cycles(
    teamId: str | None = None, type: str | None = None
) -> ListCyclesResult:
    """Lists cycles for a Linear team, optionally filtered to current/previous/next."""
    if not teamId:
        raise LinearMockError("teamId is required")
    team = _resolve_team(teamId)
    cycles = [c for c in get_state().cycles if c.team == team.id]
    if type is not None:
        if type not in {"current", "previous", "next"}:
            raise LinearMockError("type must be one of: current, previous, next")
        cycles = [c for c in cycles if c.type == type]
    cycles.sort(key=lambda c: c.number)
    return ListCyclesResult(
        team=team.id, cycles=[c.model_copy() for c in cycles], count=len(cycles)
    )


def linear_get_document(id: str | None = None) -> GetDocumentResult:
    """Fetches a Linear document by id or slug."""
    if not id:
        raise LinearMockError("id is required")
    state = get_state()
    direct = state.document(id)
    if direct is not None:
        return GetDocumentResult(document=direct.model_copy())
    for document in state.documents:
        if document.slug == id:
            return GetDocumentResult(document=document.model_copy())
    raise LinearMockError(f"Unknown Linear document: {id}")


def linear_list_documents(
    after: str | None = None,
    before: str | None = None,
    limit: int = 50,
    query: str | None = None,
    orderBy: str = "updatedAt",
    createdAt: str | None = None,
    updatedAt: str | None = None,
    creatorId: str | None = None,
    projectId: str | None = None,
    initiativeId: str | None = None,
    includeArchived: bool = False,
) -> ListDocumentsResult:
    """Lists Linear documents with text search, filters, and pagination."""
    documents = list(get_state().documents)
    if not includeArchived:
        documents = [d for d in documents if not d.archived]
    if creatorId:
        documents = [d for d in documents if d.creatorId == creatorId]
    if projectId:
        documents = [d for d in documents if d.project == projectId]
    if initiativeId:
        documents = [d for d in documents if d.initiativeId == initiativeId]
    if createdAt:
        documents = [d for d in documents if d.createdAt >= createdAt]
    if updatedAt:
        documents = [d for d in documents if d.updatedAt >= updatedAt]
    if query:
        needle = query.lower()
        documents = [
            d
            for d in documents
            if needle in d.title.lower() or needle in d.content.lower()
        ]
    documents = _sort_by(documents, orderBy)
    page, info = _paginate(documents, after=after, before=before, limit=limit)
    return ListDocumentsResult(
        documents=[d.model_copy() for d in page],
        pageInfo=info,
        totalCount=len(documents),
    )


def linear_create_document(
    title: str | None = None,
    content: str | None = None,
    icon: str | None = None,
    color: str | None = None,
    project: str | None = None,
) -> GetDocumentResult:
    """Creates a new Linear document, optionally inside a project."""
    if not title:
        raise LinearMockError("title is required")
    state = get_state()
    state.counters.document += 1
    did = f"doc_{state.counters.document}"
    project_obj = _maybe_resolve_project(project)
    now = _now_iso()
    document = LinearDocument(
        id=did,
        slug=title.lower().replace(" ", "-"),
        title=title,
        content=content or "",
        icon=icon,
        color=color,
        project=project_obj.id if project_obj else None,
        creatorId="user_me",
        initiativeId=None,
        createdAt=now,
        updatedAt=now,
    )
    state.documents.append(document)
    return GetDocumentResult(document=document.model_copy())


def linear_update_document(
    id: str | None = None,
    title: str | None = None,
    content: str | None = None,
    icon: str | None = None,
    color: str | None = None,
    project: str | None = None,
) -> GetDocumentResult:
    """Updates an existing Linear document. Provide only the fields you want to change."""
    if not id:
        raise LinearMockError("id is required")
    state = get_state()
    document = state.document(id)
    if document is None:
        raise LinearMockError(f"Unknown Linear document: {id}")
    if title is not None:
        document.title = title
        document.slug = title.lower().replace(" ", "-")
    if content is not None:
        document.content = content
    if icon is not None:
        document.icon = icon
    if color is not None:
        document.color = color
    if project is not None:
        project_obj = _maybe_resolve_project(project)
        document.project = project_obj.id if project_obj else None
    document.updatedAt = _now_iso()
    return GetDocumentResult(document=document.model_copy())


def linear_get_issue(
    id: str | None = None, includeRelations: bool = False
) -> GetIssueResult:
    """Fetches a Linear issue by ID, optionally including blocking/related/duplicate relations."""
    if not id:
        raise LinearMockError("id is required")
    issue = get_state().issue(id)
    if issue is None:
        raise LinearMockError(f"Unknown Linear issue: {id}")
    return GetIssueResult(
        issue=_to_public_issue(issue, include_relations=includeRelations)
    )


def linear_list_issues(
    team: str | None = None,
    cycle: str | None = None,
    label: str | None = None,
    state: str | None = None,
    project: str | None = None,
    assignee: str | None = None,
    delegate: str | None = None,
    parentId: str | None = None,
    after: str | None = None,
    before: str | None = None,
    limit: int = 50,
    query: str | None = None,
    orderBy: str = "updatedAt",
    createdAt: str | None = None,
    updatedAt: str | None = None,
    includeArchived: bool = True,
) -> ListIssuesResult:
    """Lists issues in the workspace with filters by team, cycle, label, state, project, assignee, etc."""
    issues = list(get_state().issues)
    if not includeArchived:
        issues = [i for i in issues if not i.archived]
    team_obj = None
    if team is not None:
        team_obj = _resolve_team(team)
        issues = [i for i in issues if i.team == team_obj.id]
    if cycle is not None:
        cycle_obj = _resolve_cycle(cycle)
        issues = [i for i in issues if i.cycle == cycle_obj.id]
    if label is not None:
        label_obj = _resolve_label(label)
        issues = [i for i in issues if label_obj.id in i.labels]
    if state is not None:
        team_id = team_obj.id if team_obj is not None else None
        status_obj = _resolve_status(
            status_id=state if state.startswith("status_") else None,
            name=None if state.startswith("status_") else state,
            team_id=team_id,
        )
        issues = [i for i in issues if i.state == status_obj.id]
    if project is not None:
        project_obj = _resolve_project(project)
        issues = [i for i in issues if i.project == project_obj.id]
    if assignee is not None:
        user_obj = _resolve_user(assignee)
        issues = [i for i in issues if i.assignee == user_obj.id]
    if delegate is not None:
        user_obj = _resolve_user(delegate)
        issues = [i for i in issues if i.delegate == user_obj.id]
    if parentId is not None:
        issues = [i for i in issues if i.parentId == parentId]
    if createdAt:
        issues = [i for i in issues if i.createdAt >= createdAt]
    if updatedAt:
        issues = [i for i in issues if i.updatedAt >= updatedAt]
    if query:
        needle = query.lower()
        issues = [
            i
            for i in issues
            if needle in i.title.lower() or needle in (i.description or "").lower()
        ]
    issues = _sort_by(issues, orderBy)
    page, info = _paginate(issues, after=after, before=before, limit=limit)
    return ListIssuesResult(
        issues=[_to_public_issue(i) for i in page],
        pageInfo=info,
        totalCount=len(issues),
    )


def _next_issue_id(team: LinearTeam) -> str:
    counters = get_state().counters
    counter_key = f"issue_{team.id[5:]}"
    current = getattr(counters, counter_key, 0) + 1
    setattr(counters, counter_key, current)
    return f"{team.key}-{current}"


def linear_create_issue(
    title: str | None = None,
    team: str | None = None,
    description: str | None = None,
    state: str | None = None,
    assignee: str | None = None,
    delegate: str | None = None,
    cycle: str | None = None,
    project: str | None = None,
    milestone: str | None = None,
    parentId: str | None = None,
    priority: int | None = None,
    dueDate: str | None = None,
    labels: list[str] | None = None,
    links: list[LinearIssueLink] | None = None,
    blocks: list[str] | None = None,
    blockedBy: list[str] | None = None,
    relatedTo: list[str] | None = None,
    duplicateOf: str | None = None,
) -> GetIssueResult:
    """Creates a new Linear issue. Title and team are required."""
    if not title or not team:
        raise LinearMockError("title and team are required")
    team_obj = _resolve_team(team)
    status_obj = (
        _resolve_status(status_id=None, name=state, team_id=team_obj.id)
        if state
        else _resolve_status(status_id=None, name="Triage", team_id=team_obj.id)
    )
    assignee_id = _maybe_resolve_user(assignee).id if assignee else None
    delegate_id = _maybe_resolve_user(delegate).id if delegate else None
    cycle_id = _resolve_cycle(cycle).id if cycle else None
    project_id = _maybe_resolve_project(project).id if project else None
    label_ids: list[str] = []
    for label_query in labels or []:
        label_obj = _resolve_label(label_query, team_id=team_obj.id)
        label_ids.append(label_obj.id)
    iid = _next_issue_id(team_obj)
    now = _now_iso()
    issue = LinearIssue(
        id=iid,
        title=title,
        description=description or "",
        team=team_obj.id,
        state=status_obj.id,
        assignee=assignee_id,
        delegate=delegate_id,
        cycle=cycle_id,
        project=project_id,
        milestone=milestone,
        parentId=parentId,
        priority=priority if priority is not None else 0,
        dueDate=dueDate,
        labels=label_ids,
        links=[_coerce_link(l) for l in (links or [])],
        blocks=list(blocks or []),
        blockedBy=list(blockedBy or []),
        relatedTo=list(relatedTo or []),
        duplicateOf=duplicateOf,
        comments=[],
        createdAt=now,
        updatedAt=now,
        archived=False,
    )
    get_state().issues.append(issue)
    return GetIssueResult(issue=_to_public_issue(issue))


def _coerce_link(link) -> LinearIssueLink:
    if isinstance(link, LinearIssueLink):
        return link
    return LinearIssueLink.model_validate(link)


def linear_update_issue(
    id: str | None = None,
    title: str | None = None,
    description: str | None = None,
    state: str | None = None,
    assignee: str | None = None,
    delegate: str | None = None,
    cycle: str | None = None,
    project: str | None = None,
    milestone: str | None = None,
    parentId: str | None = None,
    priority: int | None = None,
    dueDate: str | None = None,
    labels: list[str] | None = None,
    links: list[LinearIssueLink] | None = None,
    blocks: list[str] | None = None,
    blockedBy: list[str] | None = None,
    relatedTo: list[str] | None = None,
    duplicateOf: str | None = None,
) -> GetIssueResult:
    """Updates an existing Linear issue. Replaces blocks/blockedBy/relatedTo when supplied."""
    if not id:
        raise LinearMockError("id is required")
    state_obj = get_state()
    issue = state_obj.issue(id)
    if issue is None:
        raise LinearMockError(f"Unknown Linear issue: {id}")
    team_obj = state_obj.team(issue.team)
    if team_obj is None:
        raise LinearMockError(f"Issue {id} references unknown team {issue.team}")
    if title is not None:
        issue.title = title
    if description is not None:
        issue.description = description
    if state is not None:
        status_obj = _resolve_status(status_id=None, name=state, team_id=team_obj.id)
        issue.state = status_obj.id
    if assignee is not None:
        issue.assignee = _maybe_resolve_user(assignee).id if assignee else None
    if delegate is not None:
        issue.delegate = _maybe_resolve_user(delegate).id if delegate else None
    if cycle is not None:
        issue.cycle = _resolve_cycle(cycle).id if cycle else None
    if project is not None:
        issue.project = _maybe_resolve_project(project).id if project else None
    if milestone is not None:
        issue.milestone = milestone
    if parentId is not None:
        issue.parentId = parentId
    if priority is not None:
        issue.priority = priority
    if dueDate is not None:
        issue.dueDate = dueDate
    if labels is not None:
        issue.labels = [_resolve_label(q, team_id=team_obj.id).id for q in labels]
    if links is not None:
        issue.links = [_coerce_link(l) for l in links]
    if blocks is not None:
        issue.blocks = list(blocks)
    if blockedBy is not None:
        issue.blockedBy = list(blockedBy)
    if relatedTo is not None:
        issue.relatedTo = list(relatedTo)
    if duplicateOf is not None:
        issue.duplicateOf = duplicateOf or None
    issue.updatedAt = _now_iso()
    return GetIssueResult(issue=_to_public_issue(issue))


def linear_list_issue_statuses(team: str | None = None) -> ListIssueStatusesResult:
    """Lists issue statuses for a Linear team."""
    if not team:
        raise LinearMockError("team is required")
    team_obj = _resolve_team(team)
    statuses = [s for s in get_state().statuses if s.team == team_obj.id]
    statuses.sort(key=lambda s: s.position)
    return ListIssueStatusesResult(
        team=team_obj.id,
        statuses=[s.model_copy() for s in statuses],
        count=len(statuses),
    )


def linear_get_issue_status(
    id: str | None = None,
    name: str | None = None,
    team: str | None = None,
) -> GetIssueStatusResult:
    """Looks up a Linear issue status by ID, by name (and optional team), or by name across teams."""
    if not (id or name):
        raise LinearMockError("id or name is required")
    team_obj = _maybe_resolve_team(team)
    status = _resolve_status(
        status_id=id, name=name, team_id=team_obj.id if team_obj else None
    )
    return GetIssueStatusResult(status=status.model_copy())


def linear_list_issue_labels(
    name: str | None = None,
    team: str | None = None,
    after: str | None = None,
    before: str | None = None,
    limit: int = 50,
    orderBy: str = "updatedAt",
) -> ListIssueLabelsResult:
    """Lists issue labels in the workspace or scoped to a team."""
    labels = list(get_state().labels)
    if name is not None:
        needle = name.lower()
        labels = [l for l in labels if needle in l.name.lower()]
    if team is not None:
        team_obj = _resolve_team(team)
        labels = [l for l in labels if l.team in (None, team_obj.id)]
    labels = _sort_by(labels, orderBy)
    page, info = _paginate(labels, after=after, before=before, limit=limit)
    return ListIssueLabelsResult(
        labels=[l.model_copy() for l in page],
        pageInfo=info,
        totalCount=len(labels),
    )


def linear_create_issue_label(
    name: str | None = None,
    color: str | None = None,
    teamId: str | None = None,
    isGroup: bool = False,
    parentId: str | None = None,
    description: str | None = None,
) -> CreateLabelResult:
    """Creates a new issue label, scoped to a team or to the entire workspace."""
    if not name:
        raise LinearMockError("name is required")
    state = get_state()
    if teamId is not None and state.team(teamId) is None:
        raise LinearMockError(f"Unknown Linear team: {teamId}")
    if parentId is not None and state.label(parentId) is None:
        raise LinearMockError(f"Unknown parent label: {parentId}")
    state.counters.label += 1
    lid = f"label_{state.counters.label}"
    now = _now_iso()
    label = LinearLabel(
        id=lid,
        name=name,
        color=color,
        team=teamId,
        isGroup=isGroup,
        parentId=parentId,
        description=description or "",
        createdAt=now,
        updatedAt=now,
    )
    state.labels.append(label)
    return CreateLabelResult(label=label.model_copy())


def linear_list_projects(
    team: str | None = None,
    state: str | None = None,
    member: str | None = None,
    initiative: str | None = None,
    after: str | None = None,
    before: str | None = None,
    limit: int = 50,
    query: str | None = None,
    orderBy: str = "updatedAt",
    createdAt: str | None = None,
    updatedAt: str | None = None,
    includeArchived: bool = False,
) -> ListProjectsResult:
    """Lists Linear projects with optional filters by team, state, member, initiative, and free-text query."""
    del includeArchived
    projects = list(get_state().projects)
    if team is not None:
        team_obj = _resolve_team(team)
        projects = [p for p in projects if p.team == team_obj.id]
    if state is not None:
        projects = [p for p in projects if p.state == state]
    if member is not None:
        user_obj = _resolve_user(member)
        projects = [p for p in projects if p.lead == user_obj.id]
    if initiative is not None:
        initiative_obj = _resolve_initiative(initiative)
        projects = [p for p in projects if initiative_obj.id in p.initiatives]
    if createdAt:
        projects = [p for p in projects if p.createdAt >= createdAt]
    if updatedAt:
        projects = [p for p in projects if p.updatedAt >= updatedAt]
    if query:
        needle = query.lower()
        projects = [p for p in projects if needle in p.name.lower()]
    projects = _sort_by(projects, orderBy)
    page, info = _paginate(projects, after=after, before=before, limit=limit)
    return ListProjectsResult(
        projects=[p.model_copy(deep=True) for p in page],
        pageInfo=info,
        totalCount=len(projects),
    )


def linear_get_project(query: str | None = None) -> GetProjectResult:
    """Fetches a Linear project by ID or name."""
    if not query:
        raise LinearMockError("query is required")
    return GetProjectResult(project=_resolve_project(query).model_copy(deep=True))


def linear_create_project(
    name: str | None = None,
    team: str | None = None,
    lead: str | None = None,
    summary: str | None = None,
    description: str | None = None,
    state: str | None = None,
    priority: int | None = None,
    icon: str | None = None,
    color: str | None = None,
    labels: list[str] | None = None,
    startDate: str | None = None,
    targetDate: str | None = None,
    initiative: str | None = None,
) -> GetProjectResult:
    """Creates a new Linear project on a team."""
    if not name or not team:
        raise LinearMockError("name and team are required")
    team_obj = _resolve_team(team)
    if summary is not None and len(summary) > 255:
        raise LinearMockError("summary must be 255 characters or fewer")
    lead_id = _maybe_resolve_user(lead).id if lead else None
    initiative_obj = _resolve_initiative(initiative) if initiative else None
    project_state = get_state()
    project_state.counters.project += 1
    pid = f"proj_{project_state.counters.project}"
    now = _now_iso()
    project = LinearProject(
        id=pid,
        name=name,
        team=team_obj.id,
        lead=lead_id,
        summary=summary or "",
        description=description or "",
        state=state or "planned",
        priority=priority if priority is not None else 0,
        icon=icon,
        color=color,
        labels=list(labels or []),
        startDate=startDate,
        targetDate=targetDate,
        initiatives=[initiative_obj.id] if initiative_obj else [],
        createdAt=now,
        updatedAt=now,
    )
    project_state.projects.append(project)
    return GetProjectResult(project=project.model_copy(deep=True))


def linear_update_project(
    id: str | None = None,
    name: str | None = None,
    team: str | None = None,
    lead: str | None = None,
    summary: str | None = None,
    description: str | None = None,
    state: str | None = None,
    priority: int | None = None,
    icon: str | None = None,
    color: str | None = None,
    labels: list[str] | None = None,
    startDate: str | None = None,
    targetDate: str | None = None,
    initiatives: list[str] | None = None,
) -> GetProjectResult:
    """Updates an existing Linear project. The initiatives list, when supplied, replaces existing initiatives."""
    if not id:
        raise LinearMockError("id is required")
    project = get_state().project(id)
    if project is None:
        raise LinearMockError(f"Unknown Linear project: {id}")
    if name is not None:
        project.name = name
    if team is not None:
        project.team = _resolve_team(team).id
    if lead is not None:
        project.lead = _maybe_resolve_user(lead).id if lead else None
    if summary is not None:
        if len(summary) > 255:
            raise LinearMockError("summary must be 255 characters or fewer")
        project.summary = summary
    if description is not None:
        project.description = description
    if state is not None:
        project.state = state
    if priority is not None:
        project.priority = priority
    if icon is not None:
        project.icon = icon
    if color is not None:
        project.color = color
    if labels is not None:
        project.labels = list(labels)
    if startDate is not None:
        project.startDate = startDate
    if targetDate is not None:
        project.targetDate = targetDate
    if initiatives is not None:
        project.initiatives = [_resolve_initiative(q).id for q in initiatives]
    project.updatedAt = _now_iso()
    return GetProjectResult(project=project.model_copy(deep=True))


def linear_list_project_labels(
    name: str | None = None,
    after: str | None = None,
    before: str | None = None,
    limit: int = 50,
    orderBy: str = "updatedAt",
) -> ListProjectLabelsResult:
    """Lists workspace project labels."""
    labels = list(get_state().project_labels)
    if name is not None:
        needle = name.lower()
        labels = [l for l in labels if needle in l.name.lower()]
    labels = _sort_by(labels, orderBy)
    page, info = _paginate(labels, after=after, before=before, limit=limit)
    return ListProjectLabelsResult(
        projectLabels=[l.model_copy() for l in page],
        pageInfo=info,
        totalCount=len(labels),
    )


def linear_list_teams(
    after: str | None = None,
    before: str | None = None,
    limit: int = 50,
    query: str | None = None,
    orderBy: str = "updatedAt",
    createdAt: str | None = None,
    updatedAt: str | None = None,
    includeArchived: bool = False,
) -> ListTeamsResult:
    """Lists Linear teams in the workspace."""
    del includeArchived
    teams = list(get_state().teams)
    if query:
        needle = query.lower()
        teams = [
            t for t in teams if needle in t.name.lower() or needle in t.key.lower()
        ]
    if createdAt:
        teams = [t for t in teams if t.createdAt >= createdAt]
    if updatedAt:
        teams = [t for t in teams if t.updatedAt >= updatedAt]
    teams = _sort_by(teams, orderBy)
    page, info = _paginate(teams, after=after, before=before, limit=limit)
    return ListTeamsResult(
        teams=[_to_public_team(t) for t in page],
        pageInfo=info,
        totalCount=len(teams),
    )


def linear_get_team(query: str | None = None) -> GetTeamResult:
    """Fetches a Linear team by UUID, key, or name."""
    if not query:
        raise LinearMockError("query is required")
    team = _resolve_team(query)
    return GetTeamResult(team=_to_public_team(team), memberIds=list(team.memberIds))


def linear_list_users(
    team: str | None = None, query: str | None = None
) -> ListUsersResult:
    """Lists workspace users with optional team and free-text filters."""
    users = list(get_state().users)
    if team is not None:
        team_obj = _resolve_team(team)
        users = [u for u in users if u.id in team_obj.memberIds]
    if query:
        needle = query.lower()
        users = [
            u
            for u in users
            if needle in u.name.lower()
            or needle in u.email.lower()
            or needle in u.displayName.lower()
        ]
    users.sort(key=lambda u: u.name)
    return ListUsersResult(users=[_to_public_user(u) for u in users], count=len(users))


def linear_get_user(query: str | None = None) -> GetUserResult:
    """Fetches a Linear user by ID, name, email, or 'me'."""
    if not query:
        raise LinearMockError("query is required")
    return GetUserResult(user=_to_public_user(_resolve_user(query)))


_DOC_ARTICLES = [
    DocumentationArticle(
        title="Mocked: Issue lifecycles in Linear",
        url="https://example.com/linear/issue-lifecycle",
        snippet="Linear issues move through Triage → Backlog → Todo → In Progress → In Review → Done.",
    ),
    DocumentationArticle(
        title="Mocked: Cycles vs. projects",
        url="https://example.com/linear/cycles-projects",
        snippet="Cycles are time-boxed sprints; projects are scope-boxed deliverables.",
    ),
    DocumentationArticle(
        title="Mocked: Linear API rate limits",
        url="https://example.com/linear/rate-limits",
        snippet="Default plan: 1500 requests/hour per workspace.",
    ),
]


def linear_search_documentation(
    query: str | None = None, page: int = 0
) -> SearchDocumentationResult:
    """Mocked Linear documentation search; returns deterministic articles for any query."""
    if not query:
        raise LinearMockError("query is required")
    if page < 0:
        raise LinearMockError("page must be >= 0")
    return SearchDocumentationResult(
        query=query,
        page=page,
        results=[a.model_copy() for a in _DOC_ARTICLES],
    )


_TOOL_DEFINITIONS: list[ToolDefinition] = [
    ToolDefinition(
        name="linear_list_comments",
        callable=linear_list_comments,
        description="Lists comments on a Linear issue.",
        required_fields=frozenset({"issueId"}),
    ),
    ToolDefinition(
        name="linear_create_comment",
        callable=linear_create_comment,
        description="Creates a comment on a Linear issue, optionally as a reply.",
        required_fields=frozenset({"body", "issueId"}),
    ),
    ToolDefinition(
        name="linear_list_cycles",
        callable=linear_list_cycles,
        description="Lists cycles for a Linear team.",
        required_fields=frozenset({"teamId"}),
    ),
    ToolDefinition(
        name="linear_get_document",
        callable=linear_get_document,
        description="Fetches a Linear document by ID or slug.",
        required_fields=frozenset({"id"}),
    ),
    ToolDefinition(
        name="linear_list_documents",
        callable=linear_list_documents,
        description="Lists Linear documents with text search and filters.",
    ),
    ToolDefinition(
        name="linear_create_document",
        callable=linear_create_document,
        description="Creates a new Linear document.",
        required_fields=frozenset({"title"}),
    ),
    ToolDefinition(
        name="linear_update_document",
        callable=linear_update_document,
        description="Updates an existing Linear document.",
        required_fields=frozenset({"id"}),
    ),
    ToolDefinition(
        name="linear_get_issue",
        callable=linear_get_issue,
        description="Fetches a Linear issue by ID, optionally with relations.",
        required_fields=frozenset({"id"}),
    ),
    ToolDefinition(
        name="linear_list_issues",
        callable=linear_list_issues,
        description="Lists Linear issues with rich filtering and free-text search.",
    ),
    ToolDefinition(
        name="linear_create_issue",
        callable=linear_create_issue,
        description="Creates a new Linear issue on a team.",
        required_fields=frozenset({"title", "team"}),
    ),
    ToolDefinition(
        name="linear_update_issue",
        callable=linear_update_issue,
        description="Updates an existing Linear issue. Replaces relations when supplied.",
        required_fields=frozenset({"id"}),
    ),
    ToolDefinition(
        name="linear_list_issue_statuses",
        callable=linear_list_issue_statuses,
        description="Lists issue statuses for a Linear team.",
        required_fields=frozenset({"team"}),
    ),
    ToolDefinition(
        name="linear_get_issue_status",
        callable=linear_get_issue_status,
        description="Looks up a Linear issue status by ID, by name, or by name+team.",
    ),
    ToolDefinition(
        name="linear_list_issue_labels",
        callable=linear_list_issue_labels,
        description="Lists Linear issue labels in workspace or team.",
    ),
    ToolDefinition(
        name="linear_create_issue_label",
        callable=linear_create_issue_label,
        description="Creates a new Linear issue label.",
        required_fields=frozenset({"name"}),
    ),
    ToolDefinition(
        name="linear_list_projects",
        callable=linear_list_projects,
        description="Lists Linear projects with filters.",
    ),
    ToolDefinition(
        name="linear_get_project",
        callable=linear_get_project,
        description="Fetches a Linear project by ID or name.",
        required_fields=frozenset({"query"}),
    ),
    ToolDefinition(
        name="linear_create_project",
        callable=linear_create_project,
        description="Creates a new Linear project.",
        required_fields=frozenset({"name", "team"}),
    ),
    ToolDefinition(
        name="linear_update_project",
        callable=linear_update_project,
        description="Updates an existing Linear project.",
        required_fields=frozenset({"id"}),
    ),
    ToolDefinition(
        name="linear_list_project_labels",
        callable=linear_list_project_labels,
        description="Lists workspace project labels.",
    ),
    ToolDefinition(
        name="linear_list_teams",
        callable=linear_list_teams,
        description="Lists Linear teams in the workspace.",
    ),
    ToolDefinition(
        name="linear_get_team",
        callable=linear_get_team,
        description="Fetches a Linear team by UUID, key, or name.",
        required_fields=frozenset({"query"}),
    ),
    ToolDefinition(
        name="linear_list_users",
        callable=linear_list_users,
        description="Lists workspace users with optional filters.",
    ),
    ToolDefinition(
        name="linear_get_user",
        callable=linear_get_user,
        description="Fetches a Linear user by ID, name, email, or 'me'.",
        required_fields=frozenset({"query"}),
    ),
    ToolDefinition(
        name="linear_search_documentation",
        callable=linear_search_documentation,
        description="Searches mocked Linear documentation; returns deterministic articles.",
        required_fields=frozenset({"query"}),
    ),
]


TOOL_REGISTRY: dict[str, ToolSpec] = build_tool_registry(
    service="linear",
    definitions=_TOOL_DEFINITIONS,
)


def get_tool_registry() -> dict[str, ToolSpec]:
    return TOOL_REGISTRY


__all__ = [
    "CreateCommentResult",
    "CreateLabelResult",
    "DocumentationArticle",
    "GetDocumentResult",
    "GetIssueResult",
    "GetIssueStatusResult",
    "GetProjectResult",
    "GetTeamResult",
    "GetUserResult",
    "LinearIssueLink",
    "LinearMockError",
    "ListCommentsResult",
    "ListCyclesResult",
    "ListDocumentsResult",
    "ListIssueLabelsResult",
    "ListIssueStatusesResult",
    "ListIssuesResult",
    "ListProjectLabelsResult",
    "ListProjectsResult",
    "ListTeamsResult",
    "ListUsersResult",
    "PageInfo",
    "PublicLinearIssue",
    "PublicLinearTeam",
    "PublicLinearUser",
    "SearchDocumentationResult",
    "TOOL_REGISTRY",
    "get_tool_registry",
    "linear_create_comment",
    "linear_create_document",
    "linear_create_issue",
    "linear_create_issue_label",
    "linear_create_project",
    "linear_get_document",
    "linear_get_issue",
    "linear_get_issue_status",
    "linear_get_project",
    "linear_get_team",
    "linear_get_user",
    "linear_list_comments",
    "linear_list_cycles",
    "linear_list_documents",
    "linear_list_issue_labels",
    "linear_list_issue_statuses",
    "linear_list_issues",
    "linear_list_project_labels",
    "linear_list_projects",
    "linear_list_teams",
    "linear_list_users",
    "linear_search_documentation",
    "linear_update_document",
    "linear_update_issue",
    "linear_update_project",
    "reset_linear_mock_state",
]
