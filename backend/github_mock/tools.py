from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, TypeVar

from backend.tooling import ToolDefinition, ToolSpec, build_tool_registry
from pydantic import BaseModel, ConfigDict, Field

from .state import (
    CheckRun,
    CommitMessage,
    CommitParent,
    CommitPerson,
    CopilotJob,
    CopilotSpace,
    Discussion,
    DiscussionCategory,
    DiscussionComment,
    Gist,
    GistFile,
    GistFileEntry,
    GitHubBranch,
    GitHubCommit,
    GitHubFile,
    GitHubIssue,
    GitHubLabel,
    GitHubOrg,
    GitHubProject,
    GitHubRelease,
    GitHubRepo,
    GitHubState,
    GitHubTag,
    GitHubUser,
    GlobalAdvisory,
    IssueComment,
    IssueType,
    JobLog,
    Notification,
    NotificationSubject,
    ProjectField,
    ProjectItem,
    ProjectStatusUpdate,
    PRPendingReview,
    PRReview,
    PRReviewComment,
    PullRequest,
    SecurityAdvisory,
    SecurityAlert,
    Subscription,
    Workflow,
    WorkflowArtifact,
    WorkflowJob,
    WorkflowRun,
    _seed_repo,
    get_state,
    reset_github_mock_state,
)


class GitHubMockError(ValueError):
    """Raised when a GitHub mock tool receives invalid input or missing resources."""


T = TypeVar("T")


# ---------------------------------------------------------------------------
# Argument-side models
# ---------------------------------------------------------------------------


class GitHubFileEntry(BaseModel):
    """A path/content pair for repository file uploads."""

    model_config = ConfigDict(extra="forbid")

    path: str
    content: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_json_object(value: str | None, *, what: str) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise GitHubMockError(f"{what} must be a JSON object string: {exc}") from exc
    if not isinstance(parsed, dict):
        raise GitHubMockError(
            f"{what} must encode a JSON object, got {type(parsed).__name__}"
        )
    return parsed


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _require_repo(owner: str | None, name: str | None) -> GitHubRepo:
    if not owner or not name:
        raise GitHubMockError("owner and repo are required")
    repo = get_state().repo(owner, name)
    if repo is None:
        raise GitHubMockError(f"Unknown GitHub repository: {owner}/{name}")
    return repo


def _require_user(login: str | None) -> GitHubUser:
    if not login:
        raise GitHubMockError("user login is required")
    user = get_state().user(login)
    if user is None:
        raise GitHubMockError(f"Unknown GitHub user: {login}")
    return user


def _require_org(login: str | None) -> GitHubOrg:
    if not login:
        raise GitHubMockError("org login is required")
    org = get_state().org(login)
    if org is None:
        raise GitHubMockError(f"Unknown GitHub organization: {login}")
    return org


def _require_pr(repo: GitHubRepo, number: int) -> PullRequest:
    pr = repo.pull(number)
    if pr is None:
        raise GitHubMockError(f"Unknown PR #{number} in {repo.full_name}")
    return pr


def _require_issue(repo: GitHubRepo, number: int) -> GitHubIssue:
    issue = repo.issue(number)
    if issue is None:
        raise GitHubMockError(f"Unknown issue #{number} in {repo.full_name}")
    return issue


def _paginate(items: list[T], *, page: int = 1, per_page: int = 30) -> list[T]:
    if page < 1:
        raise GitHubMockError("page must be >= 1")
    if per_page < 1 or per_page > 100:
        raise GitHubMockError("perPage must be between 1 and 100")
    start = (page - 1) * per_page
    return items[start : start + per_page]


def _public_user(login: str) -> GitHubUser:
    user = get_state().user(login)
    if user is not None:
        return user.model_copy()
    return GitHubUser(
        login=login,
        id=-1,
        name=login,
        email=None,
        type="User",
        html_url=f"https://github.com/{login}",
    )


# ---------------------------------------------------------------------------
# Public/return models
# ---------------------------------------------------------------------------


class PublicGitHubRepo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner: str
    name: str
    full_name: str
    description: str
    default_branch: str
    private: bool
    visibility: str
    html_url: str
    stars: int
    forks: int
    topics: list[str]


def _to_public_repo(repo: GitHubRepo) -> PublicGitHubRepo:
    return PublicGitHubRepo(
        owner=repo.owner,
        name=repo.name,
        full_name=repo.full_name,
        description=repo.description,
        default_branch=repo.default_branch,
        private=repo.private,
        visibility=repo.visibility,
        html_url=repo.html_url,
        stars=repo.stars,
        forks=repo.forks,
        topics=list(repo.topics),
    )


# ---------------------------------------------------------------------------
# Generic envelopes
# ---------------------------------------------------------------------------


class ActionsResult(BaseModel):
    """Flexible Actions response envelope (different methods populate different fields)."""

    model_config = ConfigDict(extra="forbid")

    workflow: Workflow | None = None
    run: WorkflowRun | None = None
    job: WorkflowJob | None = None
    artifact: WorkflowArtifact | None = None
    download_url: str | None = None
    run_id: int | str | None = None
    billable_minutes: int | None = None
    billable_unit: str | None = None
    logs_url: str | None = None
    total_count: int | None = None
    workflows: list[Workflow] | None = None
    workflow_runs: list[WorkflowRun] | None = None
    jobs: list[WorkflowJob] | None = None
    artifacts: list[WorkflowArtifact] | None = None
    requeued_jobs: list[int] | None = None
    logs_deleted: bool | None = None


class PRReadResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pull_request: PullRequest | None = None
    pull_number: int | None = None
    diff: str | None = None
    state: str | None = None
    checks: list[CheckRun] | None = None
    files: list["PRFileChange"] | None = None
    comments: list[PRReviewComment] | list[IssueComment] | None = None
    reviews: list[PRReview] | None = None
    check_runs: list[CheckRun] | None = None


class PRFileChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str
    additions: int
    deletions: int
    changes: int


class PRWriteResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pull_request: PullRequest | None = None
    merge_method: str | None = None
    copilot_job_id: str | None = None
    head: str | None = None
    base: str | None = None
    mergeable_state: str | None = None
    pull_number: int | None = None
    pending_review: PRPendingReview | None = None
    review: PRReview | None = None
    comment_count: int | None = None
    deleted: bool | None = None
    comment: PRReviewComment | None = None
    reply: PRReviewComment | None = None


class IssueWriteResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue: GitHubIssue


class IssueReadResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue: GitHubIssue | None = None
    issue_number: int | None = None
    comments: list[IssueComment] | None = None
    sub_issues: list[GitHubIssue] | None = None
    labels: list[str] | None = None


class ListIssuesResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_count: int
    issues: list[GitHubIssue]


class ListPRsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_count: int
    pull_requests: list[PullRequest]


class CommentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comment: IssueComment


class CopilotJobResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job: CopilotJob | dict


class SubIssueResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parent: int
    sub_issues: list[int]


class IssueTypesResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    org: str
    issue_types: list[IssueType]


class BranchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branch: GitHubBranch


class FileWriteResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: GitHubFile
    commit_sha: str


class DeleteFileResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deleted: bool
    path: str
    commit_sha: str


class TreeEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    sha: str
    size: int
    type: str


class FileContentsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: GitHubFile | None = None
    ref: str
    path: str | None = None
    entries: list[TreeEntry] | None = None


class RepoTreeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ref: str
    recursive: bool
    entries: list[TreeEntry]
    truncated: bool


class PushFilesResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branch: str
    commit_sha: str
    files: list[GitHubFile]


class CodeSearchItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: str
    branch: str
    path: str
    sha: str
    snippet: str


class CodeSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_count: int
    items: list[CodeSearchItem]


class RepositoryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: PublicGitHubRepo


class ForkResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fork: PublicGitHubRepo


class StarToggleResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    starred: bool
    repository: str


class ListStarredResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_count: int
    repositories: list[PublicGitHubRepo]


class ReleaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    release: GitHubRelease


class NotificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notification: Notification


class ListNotificationsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_count: int
    notifications: list[Notification]


class NotificationDeletedResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deleted: bool
    thread_id: str


class RepoSubscriptionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: str
    subscription: Subscription


class MarkReadResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    marked_read: int
    lastReadAt: str


class AlertResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alert: SecurityAlert


class ListAlertsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_count: int
    alerts: list[SecurityAlert]


class SecretFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    secret_type: str
    severity: str


class SecretScanResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: str
    findings: list[SecretFinding]
    scanned_files: int


class ListReleasesResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_count: int
    releases: list[GitHubRelease]


class TagResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tag: GitHubTag


class ListTagsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_count: int
    tags: list[GitHubTag]


class PublicCommit(BaseModel):
    """Commit projection. ``diff`` is omitted when not requested."""

    model_config = ConfigDict(extra="forbid")

    sha: str
    commit: CommitMessage
    author: str
    parents: list[CommitParent]
    diff: str | None = None


class CommitResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    commit: PublicCommit


class ListCommitsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_count: int
    commits: list[PublicCommit]


class DiscussionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    discussion: Discussion


class DiscussionCommentsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    discussion_number: int
    comments: list[DiscussionComment]


class DiscussionEntry(BaseModel):
    """Discussion projection with repository tag."""

    model_config = ConfigDict(extra="forbid")

    number: int
    title: str
    body: str
    category: str
    user: str
    created_at: str
    updated_at: str
    comments: list[DiscussionComment]
    repository: str


class ListDiscussionsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_count: int
    discussions: list[DiscussionEntry]


class DiscussionCategoriesResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: str
    categories: list[DiscussionCategory]


class GistResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gist: Gist


class ListGistsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_count: int
    gists: list[Gist]


class IssueSearchItem(BaseModel):
    """Issue with repo tag for search results."""

    model_config = ConfigDict(extra="forbid")

    number: int
    title: str
    body: str
    state: str
    state_reason: str | None
    labels: list[str]
    assignees: list[str]
    milestone: str | None
    type: str
    user: str
    comments_count: int
    sub_issues: list[int]
    created_at: str
    updated_at: str
    closed_at: str | None = None
    closed_by_pr: int | None = None
    html_url: str
    repository: str


class IssueSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_count: int
    items: list[IssueSearchItem]


class PRSearchItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: int
    title: str
    body: str
    state: str
    draft: bool
    head: str
    base: str
    user: str
    merge_method_preferred: str
    merged: bool
    mergeable_state: str
    labels: list[str]
    assignees: list[str]
    requested_reviewers: list[str]
    comments_count: int
    review_comments_count: int
    commits_count: int
    additions: int
    deletions: int
    changed_files: int
    created_at: str
    updated_at: str
    merged_at: str | None = None
    html_url: str
    repository: str


class PRSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_count: int
    items: list[PRSearchItem]


class RepoSearchItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = None
    stars: int | None = None
    owner: str | None = None
    name: str | None = None
    description: str | None = None
    default_branch: str | None = None
    private: bool | None = None
    visibility: str | None = None
    html_url: str | None = None
    forks: int | None = None
    topics: list[str] | None = None


class RepoSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_count: int
    items: list[RepoSearchItem]


class UserSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_count: int
    items: list[GitHubUser]


class OrgSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_count: int
    items: list[GitHubOrg]


class LabelResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: GitHubLabel


class ListLabelsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_count: int
    labels: list[GitHubLabel]


class LabelWriteResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: GitHubLabel | None = None
    deleted: bool | None = None
    name: str | None = None


class GlobalAdvisoryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    advisory: GlobalAdvisory


class ListGlobalAdvisoriesResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_count: int
    advisories: list[GlobalAdvisory]


class RepoAdvisoryEntry(BaseModel):
    """Security advisory with optional repository tag."""

    model_config = ConfigDict(extra="forbid")

    ghsa_id: str
    summary: str
    severity: str
    state: str
    published_at: str
    repository: str | None = None


class ListRepoAdvisoriesResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_count: int
    advisories: list[RepoAdvisoryEntry]


class ProjectGetResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project: GitHubProject | None = None
    field: ProjectField | None = None
    item: ProjectItem | None = None
    status_update: ProjectStatusUpdate | None = None


class ProjectListResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projects: list[GitHubProject] | None = None
    project_id: int | None = None
    fields: list[ProjectField] | None = None
    items: list[ProjectItem] | None = None
    status_updates: list[ProjectStatusUpdate] | None = None


class ProjectWriteResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item: ProjectItem | None = None
    status_update: ProjectStatusUpdate | None = None
    deleted: bool | None = None
    item_id: int | None = None


class MeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user: GitHubUser


class TeamMembership(BaseModel):
    model_config = ConfigDict(extra="forbid")

    org: str
    slug: str
    name: str
    description: str


class TeamsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user: str
    teams: list[TeamMembership]


class TeamMembersResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    org: str
    team_slug: str
    members: list[str]


class ListBranchesResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_count: int
    branches: list[GitHubBranch]


class CopilotSpaceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    space: CopilotSpace


class ListCopilotSpacesResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    spaces: list[CopilotSpace]


class JobLogsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: int
    logs: str


class DocSearchArticle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    url: str
    snippet: str


class DocSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    results: list[DocSearchArticle]


# ---------------------------------------------------------------------------
# Helpers for mutation
# ---------------------------------------------------------------------------


def _make_commit(
    *, sha: str, message: str, parents: list[str], diff: str
) -> GitHubCommit:
    me = get_state().me.login
    now = _now_iso()
    return GitHubCommit(
        sha=sha,
        commit=CommitMessage(
            message=message,
            author=CommitPerson(name=me, date=now),
            committer=CommitPerson(name=me, date=now),
        ),
        author=me,
        parents=[CommitParent(sha=p) for p in parents],
        diff=diff,
    )


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------


def github_actions_get(
    repo: str | None = None,
    owner: str | None = None,
    method: str | None = None,
    resource_id: str | None = None,
) -> ActionsResult:
    """Retrieves GitHub Actions resources: workflows, runs, jobs, artifacts, run logs."""
    repository = _require_repo(owner, repo)
    if not method:
        raise GitHubMockError("method is required")
    if method == "get_workflow":
        if not resource_id:
            raise GitHubMockError("resource_id is required for get_workflow")
        wf = repository.workflow(int(resource_id))
        if wf is None:
            raise GitHubMockError(f"Unknown workflow: {resource_id}")
        return ActionsResult(workflow=wf.model_copy())
    if method == "get_workflow_run":
        if not resource_id:
            raise GitHubMockError("resource_id is required for get_workflow_run")
        run = repository.workflow_run(int(resource_id))
        if run is None:
            raise GitHubMockError(f"Unknown workflow run: {resource_id}")
        return ActionsResult(run=run.model_copy())
    if method == "get_workflow_job":
        if not resource_id:
            raise GitHubMockError("resource_id is required for get_workflow_job")
        job = repository.workflow_job(int(resource_id))
        if job is None:
            raise GitHubMockError(f"Unknown workflow job: {resource_id}")
        return ActionsResult(job=job.model_copy())
    if method == "download_workflow_run_artifact":
        if not resource_id:
            raise GitHubMockError(
                "resource_id is required for download_workflow_run_artifact"
            )
        artifact = repository.workflow_artifact(int(resource_id))
        if artifact is None:
            raise GitHubMockError(f"Unknown artifact: {resource_id}")
        return ActionsResult(
            artifact=artifact.model_copy(),
            download_url=f"https://example.com/artifacts/{resource_id}",
        )
    if method == "get_workflow_run_usage":
        return ActionsResult(
            run_id=resource_id, billable_minutes=4, billable_unit="UBUNTU"
        )
    if method == "get_workflow_run_logs_url":
        return ActionsResult(
            run_id=resource_id, logs_url=f"https://example.com/logs/{resource_id}"
        )
    raise GitHubMockError(f"Unsupported method: {method}")


def github_actions_list(
    repo: str | None = None,
    owner: str | None = None,
    method: str | None = None,
    resource_id: str | None = None,
    page: int = 1,
    per_page: int = 30,
    workflow_jobs_filter: str | None = None,
    workflow_runs_filter: str | None = None,
) -> ActionsResult:
    """Lists GitHub Actions resources with pagination and optional filters."""
    repository = _require_repo(owner, repo)
    if not method:
        raise GitHubMockError("method is required")
    if method == "list_workflows":
        items = [w.model_copy() for w in repository.workflows]
        return ActionsResult(
            total_count=len(items),
            workflows=_paginate(items, page=page, per_page=per_page),
        )
    if method == "list_workflow_runs":
        items = [r.model_copy() for r in repository.workflow_runs]
        if workflow_runs_filter:
            items = [
                r
                for r in items
                if workflow_runs_filter in (r.conclusion or "") + (r.status or "")
            ]
        return ActionsResult(
            total_count=len(items),
            workflow_runs=_paginate(items, page=page, per_page=per_page),
        )
    if method == "list_workflow_jobs":
        if not resource_id:
            raise GitHubMockError(
                "resource_id (run id) is required for list_workflow_jobs"
            )
        items = [
            j.model_copy()
            for j in repository.workflow_jobs
            if j.run_id == int(resource_id)
        ]
        if workflow_jobs_filter:
            items = [
                j
                for j in items
                if workflow_jobs_filter in (j.conclusion or "") + (j.status or "")
            ]
        return ActionsResult(
            total_count=len(items), jobs=_paginate(items, page=page, per_page=per_page)
        )
    if method == "list_workflow_run_artifacts":
        if not resource_id:
            raise GitHubMockError(
                "resource_id (run id) is required for list_workflow_run_artifacts"
            )
        items = [
            a.model_copy()
            for a in repository.workflow_artifacts
            if a.run_id == int(resource_id)
        ]
        return ActionsResult(
            total_count=len(items),
            artifacts=_paginate(items, page=page, per_page=per_page),
        )
    raise GitHubMockError(f"Unsupported method: {method}")


def github_actions_run_trigger(
    repo: str | None = None,
    owner: str | None = None,
    workflow_id: str | None = None,
    ref: str | None = None,
    run_id: str | None = None,
    inputs: str | None = None,
    method: str | None = None,
) -> ActionsResult:
    """Executes workflow operations: run, rerun, cancel, delete logs."""
    repository = _require_repo(owner, repo)
    if not method:
        raise GitHubMockError("method is required")
    if method == "run_workflow":
        if not workflow_id or not ref:
            raise GitHubMockError("workflow_id and ref are required for run_workflow")
        wf_id = int(workflow_id)
        wf = repository.workflow(wf_id)
        if wf is None:
            raise GitHubMockError(f"Unknown workflow: {workflow_id}")
        _parse_json_object(inputs, what="inputs")
        new_run_id = max((r.id for r in repository.workflow_runs), default=9000) + 1
        branch = repository.branch(ref)
        run = WorkflowRun(
            id=new_run_id,
            workflow_id=wf_id,
            name=wf.name,
            status="queued",
            conclusion="",
            head_branch=ref,
            head_sha=branch.commit_sha if branch else "unknown",
            created_at=_now_iso(),
            updated_at=_now_iso(),
        )
        repository.workflow_runs.append(run)
        return ActionsResult(run=run.model_copy())
    if method == "rerun_workflow_run":
        if not run_id:
            raise GitHubMockError("run_id is required for rerun_workflow_run")
        run = repository.workflow_run(int(run_id))
        if run is None:
            raise GitHubMockError(f"Unknown workflow run: {run_id}")
        run.status = "queued"
        run.conclusion = ""
        run.updated_at = _now_iso()
        return ActionsResult(run=run.model_copy())
    if method == "rerun_failed_jobs":
        if not run_id:
            raise GitHubMockError("run_id is required for rerun_failed_jobs")
        affected = [
            j
            for j in repository.workflow_jobs
            if j.run_id == int(run_id) and j.conclusion == "failure"
        ]
        for job in affected:
            job.status = "queued"
            job.conclusion = ""
        return ActionsResult(requeued_jobs=[j.id for j in affected])
    if method == "cancel_workflow_run":
        if not run_id:
            raise GitHubMockError("run_id is required for cancel_workflow_run")
        run = repository.workflow_run(int(run_id))
        if run is None:
            raise GitHubMockError(f"Unknown workflow run: {run_id}")
        run.status = "completed"
        run.conclusion = "cancelled"
        run.updated_at = _now_iso()
        return ActionsResult(run=run.model_copy())
    if method == "delete_workflow_run_logs":
        if not run_id:
            raise GitHubMockError("run_id is required for delete_workflow_run_logs")
        return ActionsResult(run_id=int(run_id), logs_deleted=True)
    raise GitHubMockError(f"Unsupported method: {method}")


# ---------------------------------------------------------------------------
# Pull Requests
# ---------------------------------------------------------------------------


def github_add_comment_to_pending_review(
    repo: str | None = None,
    owner: str | None = None,
    pullNumber: int | None = None,
    path: str | None = None,
    line: int | None = None,
    body: str | None = None,
    side: str | None = None,
) -> PRWriteResult:
    """Adds a comment to an existing pending PR review draft owned by the current user."""
    if (
        pullNumber is None
        or path is None
        or line is None
        or not body
        or side not in {"LEFT", "RIGHT"}
    ):
        raise GitHubMockError(
            "pullNumber, path, line, body, and side are required (side must be LEFT or RIGHT)"
        )
    repository = _require_repo(owner, repo)
    pr = _require_pr(repository, pullNumber)
    me = get_state().me.login
    draft = repository.pr_pending_review(pr.number, me)
    if draft is None:
        raise GitHubMockError(
            "No pending review draft for this PR. Start a review first."
        )
    repository.counters.review += 1
    comment = PRReviewComment(
        id=repository.counters.review,
        user=me,
        body=body,
        path=path,
        line=line,
        side=side,
        in_reply_to_id=None,
        pull_number=pr.number,
        created_at=_now_iso(),
        updated_at=_now_iso(),
    )
    draft.comments.append(comment)
    return PRWriteResult(comment=comment.model_copy())


def github_add_reply_to_pull_request_comment(
    repo: str | None = None,
    owner: str | None = None,
    pullNumber: int | None = None,
    commentId: int | None = None,
    body: str | None = None,
) -> PRWriteResult:
    """Replies to a specific PR review comment."""
    if pullNumber is None or commentId is None or not body:
        raise GitHubMockError("pullNumber, commentId, and body are required")
    repository = _require_repo(owner, repo)
    pr = _require_pr(repository, pullNumber)
    log = repository.pr_review_comment_log(pr.number)
    parent = next((c for c in log.comments if c.id == commentId), None)
    if parent is None:
        raise GitHubMockError(f"Unknown review comment: {commentId}")
    repository.counters.review += 1
    reply = PRReviewComment(
        id=repository.counters.review,
        user=get_state().me.login,
        body=body,
        path=parent.path,
        line=parent.line,
        side=parent.side,
        in_reply_to_id=parent.id,
        pull_number=pr.number,
        created_at=_now_iso(),
        updated_at=_now_iso(),
    )
    log.comments.append(reply)
    return PRWriteResult(reply=reply.model_copy())


def github_create_pull_request(
    repo: str | None = None,
    owner: str | None = None,
    base: str | None = None,
    head: str | None = None,
    title: str | None = None,
    body: str | None = None,
    draft: bool = False,
    maintainer_can_modify: bool = True,
) -> PRWriteResult:
    """Creates a new pull request."""
    del maintainer_can_modify
    if not base or not head or not title:
        raise GitHubMockError("base, head, and title are required")
    repository = _require_repo(owner, repo)
    if repository.branch(base) is None:
        raise GitHubMockError(f"Unknown base branch: {base}")
    if repository.branch(head) is None:
        raise GitHubMockError(f"Unknown head branch: {head}")
    repository.counters.next_number += 1
    pr_number = repository.counters.next_number
    pr = PullRequest(
        number=pr_number,
        title=title,
        body=body or "",
        state="open",
        draft=draft,
        head=head,
        base=base,
        user=get_state().me.login,
        merge_method_preferred="squash",
        merged=False,
        mergeable_state="unknown",
        labels=[],
        assignees=[],
        requested_reviewers=[],
        comments_count=0,
        review_comments_count=0,
        commits_count=1,
        additions=0,
        deletions=0,
        changed_files=0,
        created_at=_now_iso(),
        updated_at=_now_iso(),
        html_url=f"{repository.html_url}/pull/{pr_number}",
    )
    repository.pulls.append(pr)
    return PRWriteResult(pull_request=pr.model_copy())


def github_create_pull_request_with_copilot(
    repo: str | None = None,
    owner: str | None = None,
    title: str | None = None,
    problem_statement: str | None = None,
    base_ref: str | None = None,
) -> PRWriteResult:
    """Delegates implementation to GitHub Copilot agent and returns the resulting PR stub."""
    if not title or not problem_statement:
        raise GitHubMockError("title and problem_statement are required")
    repository = _require_repo(owner, repo)
    base_branch = base_ref or repository.default_branch
    base = repository.branch(base_branch)
    if base is None:
        raise GitHubMockError(f"Unknown base branch: {base_branch}")
    head_branch = f"copilot/{title.lower().replace(' ', '-')[:32]}"
    repository.branches.append(
        GitHubBranch(name=head_branch, commit_sha=base.commit_sha, protected=False)
    )
    repository.counters.next_number += 1
    pr_number = repository.counters.next_number
    pr = PullRequest(
        number=pr_number,
        title=f"[copilot] {title}",
        body=problem_statement,
        state="open",
        draft=True,
        head=head_branch,
        base=base_branch,
        user="octocat",
        merge_method_preferred="squash",
        merged=False,
        mergeable_state="unknown",
        labels=["copilot"],
        assignees=[get_state().me.login],
        requested_reviewers=[],
        comments_count=0,
        review_comments_count=0,
        commits_count=1,
        additions=0,
        deletions=0,
        changed_files=0,
        created_at=_now_iso(),
        updated_at=_now_iso(),
        html_url=f"{repository.html_url}/pull/{pr_number}",
    )
    repository.pulls.append(pr)
    job_id = "cj_" + head_branch
    get_state().copilot_jobs.append(
        CopilotJob(
            id=job_id,
            owner=repository.owner,
            repo=repository.name,
            status="in_progress",
            summary=problem_statement,
            pull_request=pr_number,
            created_at=_now_iso(),
            updated_at=_now_iso(),
        )
    )
    return PRWriteResult(pull_request=pr.model_copy(), copilot_job_id=job_id)


def github_merge_pull_request(
    repo: str | None = None,
    owner: str | None = None,
    pullNumber: int | None = None,
    merge_method: str | None = None,
    commit_title: str | None = None,
    commit_message: str | None = None,
) -> PRWriteResult:
    """Merges a pull request using the specified merge strategy."""
    del commit_title, commit_message
    if pullNumber is None:
        raise GitHubMockError("pullNumber is required")
    repository = _require_repo(owner, repo)
    pr = _require_pr(repository, pullNumber)
    if pr.merged:
        raise GitHubMockError(f"PR #{pullNumber} is already merged")
    if pr.state != "open":
        raise GitHubMockError(f"PR #{pullNumber} is not open")
    method = merge_method or pr.merge_method_preferred
    if method not in {"merge", "squash", "rebase"}:
        raise GitHubMockError("merge_method must be one of: merge, squash, rebase")
    pr.merged = True
    pr.state = "closed"
    pr.merged_at = _now_iso()
    pr.updated_at = pr.merged_at
    return PRWriteResult(pull_request=pr.model_copy(), merge_method=method)


def github_pull_request_read(
    repo: str | None = None,
    owner: str | None = None,
    pullNumber: int | None = None,
    method: str | None = None,
) -> PRReadResult:
    """Retrieves PR data: get, get_diff, get_status, get_files, get_review_comments, get_reviews, get_comments, get_check_runs."""
    if pullNumber is None or not method:
        raise GitHubMockError("pullNumber and method are required")
    repository = _require_repo(owner, repo)
    pr = _require_pr(repository, pullNumber)
    if method == "get":
        return PRReadResult(pull_request=pr.model_copy())
    if method == "get_diff":
        return PRReadResult(
            pull_number=pr.number,
            diff=f"--- a\n+++ b\n@@\n+ stub diff for PR #{pr.number}\n",
        )
    if method == "get_status":
        runs = repository.pr_check_log(pr.number).checks
        statuses = {run.conclusion or run.status for run in runs}
        overall = (
            "success"
            if statuses == {"success"}
            else ("failure" if "failure" in statuses else "pending")
        )
        return PRReadResult(
            pull_number=pr.number, state=overall, checks=[r.model_copy() for r in runs]
        )
    if method == "get_files":
        return PRReadResult(
            pull_number=pr.number,
            files=[
                PRFileChange(
                    filename="src/main.py",
                    additions=pr.additions,
                    deletions=pr.deletions,
                    changes=pr.changed_files or 1,
                )
            ],
        )
    if method == "get_review_comments":
        return PRReadResult(
            pull_number=pr.number,
            comments=[
                c.model_copy()
                for c in repository.pr_review_comment_log(pr.number).comments
            ],
        )
    if method == "get_reviews":
        return PRReadResult(
            pull_number=pr.number,
            reviews=[
                r.model_copy() for r in repository.pr_review_log(pr.number).reviews
            ],
        )
    if method == "get_comments":
        return PRReadResult(
            pull_number=pr.number,
            comments=[
                c.model_copy()
                for c in repository.pr_issue_comment_log(pr.number).comments
            ],
        )
    if method == "get_check_runs":
        return PRReadResult(
            pull_number=pr.number,
            check_runs=[
                c.model_copy() for c in repository.pr_check_log(pr.number).checks
            ],
        )
    raise GitHubMockError(f"Unsupported method: {method}")


def github_pull_request_review_write(
    repo: str | None = None,
    owner: str | None = None,
    pullNumber: int | None = None,
    method: str | None = None,
) -> PRWriteResult:
    """Creates, submits, or deletes a pending PR review."""
    if pullNumber is None or not method:
        raise GitHubMockError("pullNumber and method are required")
    repository = _require_repo(owner, repo)
    pr = _require_pr(repository, pullNumber)
    me = get_state().me.login
    existing = repository.pr_pending_review(pr.number, me)
    if method == "create":
        if existing is not None:
            raise GitHubMockError("A pending review already exists for this PR.")
        draft = PRPendingReview(pull_number=pr.number, user=me, body="", comments=[])
        repository.pr_pending_reviews.append(draft)
        return PRWriteResult(pending_review=draft.model_copy(deep=True))
    if method == "submit_pending":
        if existing is None:
            raise GitHubMockError("No pending review to submit.")
        repository.pr_pending_reviews = [
            p
            for p in repository.pr_pending_reviews
            if not (p.pull_number == pr.number and p.user == me)
        ]
        repository.counters.review += 1
        review = PRReview(
            id=repository.counters.review,
            user=me,
            state="COMMENTED",
            body="",
            submitted_at=_now_iso(),
        )
        repository.pr_review_log(pr.number).reviews.append(review)
        for comment in existing.comments:
            repository.pr_review_comment_log(pr.number).comments.append(
                comment.model_copy()
            )
        return PRWriteResult(
            review=review.model_copy(), comment_count=len(existing.comments)
        )
    if method == "delete_pending":
        if existing is None:
            raise GitHubMockError("No pending review to delete.")
        repository.pr_pending_reviews = [
            p
            for p in repository.pr_pending_reviews
            if not (p.pull_number == pr.number and p.user == me)
        ]
        return PRWriteResult(deleted=True)
    raise GitHubMockError(f"Unsupported method: {method}")


def github_update_pull_request(
    repo: str | None = None,
    owner: str | None = None,
    pullNumber: int | None = None,
    title: str | None = None,
    body: str | None = None,
    state: str | None = None,
    base: str | None = None,
    draft: bool | None = None,
    reviewers: list[str] | None = None,
    maintainer_can_modify: bool | None = None,
) -> PRWriteResult:
    """Modifies properties on an existing PR."""
    del maintainer_can_modify
    if pullNumber is None:
        raise GitHubMockError("pullNumber is required")
    repository = _require_repo(owner, repo)
    pr = _require_pr(repository, pullNumber)
    if title is not None:
        pr.title = title
    if body is not None:
        pr.body = body
    if state is not None:
        if state not in {"open", "closed"}:
            raise GitHubMockError("state must be 'open' or 'closed'")
        pr.state = state
    if base is not None:
        if repository.branch(base) is None:
            raise GitHubMockError(f"Unknown base branch: {base}")
        pr.base = base
    if draft is not None:
        pr.draft = draft
    if reviewers is not None:
        pr.requested_reviewers = list(reviewers)
    pr.updated_at = _now_iso()
    return PRWriteResult(pull_request=pr.model_copy())


def github_update_pull_request_branch(
    repo: str | None = None,
    owner: str | None = None,
    pullNumber: int | None = None,
) -> PRWriteResult:
    """Syncs the PR's head branch with the latest base branch."""
    if pullNumber is None:
        raise GitHubMockError("pullNumber is required")
    repository = _require_repo(owner, repo)
    pr = _require_pr(repository, pullNumber)
    pr.mergeable_state = "clean"
    pr.updated_at = _now_iso()
    return PRWriteResult(
        pull_number=pr.number, head=pr.head, base=pr.base, mergeable_state="clean"
    )


def github_list_pull_requests(
    repo: str | None = None,
    owner: str | None = None,
    state: str | None = "open",
    head: str | None = None,
    base: str | None = None,
    sort: str | None = None,
    direction: str | None = None,
    page: int = 1,
    perPage: int = 30,
) -> ListPRsResult:
    """Lists pull requests with optional state, head, and base filters."""
    repository = _require_repo(owner, repo)
    prs = list(repository.pulls)
    if state and state != "all":
        prs = [p for p in prs if p.state == state]
    if head is not None:
        prs = [p for p in prs if p.head == head]
    if base is not None:
        prs = [p for p in prs if p.base == base]
    sort_key = sort or "updated"
    reverse = (direction or "desc") == "desc"
    key_attr = {"created": "created_at", "updated": "updated_at"}.get(
        sort_key, "updated_at"
    )
    prs.sort(key=lambda p: getattr(p, key_attr) or "", reverse=reverse)
    return ListPRsResult(
        total_count=len(prs),
        pull_requests=[
            p.model_copy() for p in _paginate(prs, page=page, per_page=perPage)
        ],
    )


# ---------------------------------------------------------------------------
# Issues
# ---------------------------------------------------------------------------


def github_add_issue_comment(
    repo: str | None = None,
    owner: str | None = None,
    issue_number: int | None = None,
    body: str | None = None,
) -> CommentResult:
    """Posts a comment on an issue or PR thread."""
    if issue_number is None or not body:
        raise GitHubMockError("issue_number and body are required")
    repository = _require_repo(owner, repo)
    pr = repository.pull(issue_number)
    issue = repository.issue(issue_number)
    if pr is None and issue is None:
        raise GitHubMockError(f"Unknown issue or PR #{issue_number}")
    repository.counters.comment += 1
    comment = IssueComment(
        id=repository.counters.comment,
        user=get_state().me.login,
        body=body,
        created_at=_now_iso(),
        updated_at=_now_iso(),
    )
    if pr is not None:
        repository.pr_issue_comment_log(issue_number).comments.append(comment)
        pr.comments_count += 1
        pr.updated_at = comment.updated_at
    else:
        repository.issue_comment_log(issue_number).comments.append(comment)
        issue.comments_count += 1
        issue.updated_at = comment.updated_at
    return CommentResult(comment=comment.model_copy())


def github_assign_copilot_to_issue(
    repo: str | None = None,
    owner: str | None = None,
    issue_number: int | None = None,
    base_ref: str | None = None,
    custom_instructions: str | None = None,
) -> CopilotJobResult:
    """Delegates issue resolution to Copilot agent and returns a job handle."""
    del custom_instructions
    if issue_number is None:
        raise GitHubMockError("issue_number is required")
    repository = _require_repo(owner, repo)
    issue = _require_issue(repository, issue_number)
    job_id = f"cj_issue_{repository.name}_{issue_number}"
    job = CopilotJob(
        id=job_id,
        owner=repository.owner,
        repo=repository.name,
        status="queued",
        summary=issue.title,
        pull_request=0,
        created_at=_now_iso(),
        updated_at=_now_iso(),
    )
    get_state().copilot_jobs.append(job)
    del base_ref
    return CopilotJobResult(job=job.model_copy())


def github_issue_read(
    repo: str | None = None,
    owner: str | None = None,
    issue_number: int | None = None,
    method: str | None = None,
) -> IssueReadResult:
    """Retrieves issue info: get, get_comments, get_sub_issues, get_labels."""
    if issue_number is None or not method:
        raise GitHubMockError("issue_number and method are required")
    repository = _require_repo(owner, repo)
    issue = _require_issue(repository, issue_number)
    if method == "get":
        return IssueReadResult(issue=issue.model_copy())
    if method == "get_comments":
        return IssueReadResult(
            issue_number=issue_number,
            comments=[
                c.model_copy()
                for c in repository.issue_comment_log(issue_number).comments
            ],
        )
    if method == "get_sub_issues":
        subs = [repository.issue(n) for n in issue.sub_issues]
        return IssueReadResult(
            issue_number=issue_number,
            sub_issues=[s.model_copy() for s in subs if s is not None],
        )
    if method == "get_labels":
        return IssueReadResult(issue_number=issue_number, labels=list(issue.labels))
    raise GitHubMockError(f"Unsupported method: {method}")


def github_issue_write(
    repo: str | None = None,
    owner: str | None = None,
    method: str | None = None,
    title: str | None = None,
    body: str | None = None,
    labels: list[str] | None = None,
    assignees: list[str] | None = None,
    milestone: int | None = None,
    state: str | None = None,
    state_reason: str | None = None,
    type: str | None = None,
    issue_number: int | None = None,
) -> IssueWriteResult:
    """Creates or updates an issue. method must be 'create' or 'update' (update requires issue_number)."""
    if not method:
        raise GitHubMockError("method is required")
    repository = _require_repo(owner, repo)
    if method == "create":
        if not title:
            raise GitHubMockError("title is required for create")
        repository.counters.next_number += 1
        number = repository.counters.next_number
        issue = GitHubIssue(
            number=number,
            title=title,
            body=body or "",
            state="open",
            state_reason=None,
            labels=list(labels or []),
            assignees=list(assignees or []),
            milestone=str(milestone) if milestone is not None else None,
            type=type or "Task",
            user=get_state().me.login,
            comments_count=0,
            sub_issues=[],
            created_at=_now_iso(),
            updated_at=_now_iso(),
            html_url=f"{repository.html_url}/issues/{number}",
        )
        repository.issues.append(issue)
        return IssueWriteResult(issue=issue.model_copy())
    if method == "update":
        if issue_number is None:
            raise GitHubMockError("issue_number is required for update")
        issue = _require_issue(repository, issue_number)
        if title is not None:
            issue.title = title
        if body is not None:
            issue.body = body
        if labels is not None:
            issue.labels = list(labels)
        if assignees is not None:
            issue.assignees = list(assignees)
        if milestone is not None:
            issue.milestone = str(milestone)
        if state is not None:
            if state not in {"open", "closed"}:
                raise GitHubMockError("state must be 'open' or 'closed'")
            issue.state = state
            if state == "closed":
                issue.closed_at = _now_iso()
        if state_reason is not None:
            issue.state_reason = state_reason
        if type is not None:
            issue.type = type
        issue.updated_at = _now_iso()
        return IssueWriteResult(issue=issue.model_copy())
    raise GitHubMockError(f"Unsupported method: {method}")


def github_list_issues(
    repo: str | None = None,
    owner: str | None = None,
    state: str = "open",
    labels: str | None = None,
    sort: str | None = None,
    direction: str | None = None,
    page: int = 1,
    perPage: int = 30,
) -> ListIssuesResult:
    """Lists repository issues, excluding PRs, with optional filtering."""
    repository = _require_repo(owner, repo)
    issues = list(repository.issues)
    if state and state != "all":
        issues = [i for i in issues if i.state == state]
    if labels:
        wanted = {label.strip().lower() for label in labels.split(",") if label.strip()}
        issues = [i for i in issues if wanted.issubset({l.lower() for l in i.labels})]
    sort_key = sort or "updated"
    reverse = (direction or "desc") == "desc"
    key_attr = {"created": "created_at", "updated": "updated_at"}.get(
        sort_key, "updated_at"
    )
    issues.sort(key=lambda i: getattr(i, key_attr) or "", reverse=reverse)
    return ListIssuesResult(
        total_count=len(issues),
        issues=[i.model_copy() for i in _paginate(issues, page=page, per_page=perPage)],
    )


def github_sub_issue_write(
    repo: str | None = None,
    owner: str | None = None,
    issue_number: int | None = None,
    method: str | None = None,
    sub_issue_number: int | None = None,
    new_position: int | None = None,
) -> SubIssueResult:
    """Manages sub-issue hierarchies: add, remove, reprioritize."""
    if issue_number is None or not method:
        raise GitHubMockError("issue_number and method are required")
    repository = _require_repo(owner, repo)
    parent = _require_issue(repository, issue_number)
    if method == "add":
        if sub_issue_number is None:
            raise GitHubMockError("sub_issue_number is required for add")
        _require_issue(repository, sub_issue_number)
        parent.sub_issues.append(sub_issue_number)
        return SubIssueResult(parent=issue_number, sub_issues=list(parent.sub_issues))
    if method == "remove":
        if sub_issue_number is None:
            raise GitHubMockError("sub_issue_number is required for remove")
        if sub_issue_number not in parent.sub_issues:
            raise GitHubMockError(
                f"#{sub_issue_number} is not a sub-issue of #{issue_number}"
            )
        parent.sub_issues.remove(sub_issue_number)
        return SubIssueResult(parent=issue_number, sub_issues=list(parent.sub_issues))
    if method == "reprioritize":
        if sub_issue_number is None or new_position is None:
            raise GitHubMockError(
                "sub_issue_number and new_position are required for reprioritize"
            )
        if sub_issue_number not in parent.sub_issues:
            raise GitHubMockError(
                f"#{sub_issue_number} is not a sub-issue of #{issue_number}"
            )
        parent.sub_issues.remove(sub_issue_number)
        parent.sub_issues.insert(
            max(0, min(len(parent.sub_issues), new_position)), sub_issue_number
        )
        return SubIssueResult(parent=issue_number, sub_issues=list(parent.sub_issues))
    raise GitHubMockError(f"Unsupported method: {method}")


def github_triage_issue(
    repo: str | None = None,
    owner: str | None = None,
    issue_number: int | None = None,
    triage_rationale: str | None = None,
    labels: list[str] | None = None,
    type: str | None = None,
    fields: str | None = None,
) -> IssueWriteResult:
    """Triage-categorizes an issue with rationale and metadata."""
    del triage_rationale, fields
    if issue_number is None:
        raise GitHubMockError("issue_number is required")
    repository = _require_repo(owner, repo)
    issue = _require_issue(repository, issue_number)
    if labels is not None:
        issue.labels = list(labels)
    if type is not None:
        issue.type = type
    issue.updated_at = _now_iso()
    return IssueWriteResult(issue=issue.model_copy())


def github_list_issue_types(owner: str | None = None) -> IssueTypesResult:
    """Lists organization-defined issue types."""
    org = _require_org(owner)
    return IssueTypesResult(
        org=org.login, issue_types=[t.model_copy() for t in org.issue_types]
    )


# ---------------------------------------------------------------------------
# Code & Files
# ---------------------------------------------------------------------------


def github_create_branch(
    repo: str | None = None,
    owner: str | None = None,
    branch: str | None = None,
    from_branch: str | None = None,
) -> BranchResult:
    """Creates a new branch from another branch (defaults to default branch)."""
    if not branch:
        raise GitHubMockError("branch is required")
    repository = _require_repo(owner, repo)
    if repository.branch(branch) is not None:
        raise GitHubMockError(f"Branch already exists: {branch}")
    source_name = from_branch or repository.default_branch
    source = repository.branch(source_name)
    if source is None:
        raise GitHubMockError(f"Unknown source branch: {source_name}")
    new_branch = GitHubBranch(
        name=branch, commit_sha=source.commit_sha, protected=False
    )
    repository.branches.append(new_branch)
    # Copy source branch files to new branch.
    source_files = repository.branch_files(source_name).files
    repository.branch_files(branch).files.extend(f.model_copy() for f in source_files)
    return BranchResult(branch=new_branch.model_copy())


def github_create_or_update_file(
    repo: str | None = None,
    owner: str | None = None,
    path: str | None = None,
    branch: str | None = None,
    content: str | None = None,
    message: str | None = None,
    sha: str | None = None,
) -> FileWriteResult:
    """Creates or updates a single file in the repository on a specific branch."""
    if not path or not branch or content is None or not message:
        raise GitHubMockError("path, branch, content, and message are required")
    repository = _require_repo(owner, repo)
    branch_obj = repository.branch(branch)
    if branch_obj is None:
        raise GitHubMockError(f"Unknown branch: {branch}")
    log = repository.branch_files(branch)
    existing = next((f for f in log.files if f.path == path), None)
    if existing is not None and sha is None:
        raise GitHubMockError("sha is required when updating an existing file")
    if existing is not None and sha and sha != existing.sha:
        raise GitHubMockError("sha mismatch — file has changed")
    new_sha = f"sha_{branch}_{path.replace('/', '_')}"
    file_record = GitHubFile(path=path, content=content, sha=new_sha, size=len(content))
    if existing is not None:
        log.files = [f for f in log.files if f.path != path]
    log.files.append(file_record)
    commit_sha = f"sha_{branch}_{repository.counters.next_number}_{len(log.files)}"
    repository.commits.append(
        _make_commit(
            sha=commit_sha,
            message=message,
            parents=[branch_obj.commit_sha],
            diff=f"+ {path}\n",
        )
    )
    branch_obj.commit_sha = commit_sha
    return FileWriteResult(content=file_record.model_copy(), commit_sha=commit_sha)


def github_delete_file(
    repo: str | None = None,
    owner: str | None = None,
    path: str | None = None,
    branch: str | None = None,
    message: str | None = None,
) -> DeleteFileResult:
    """Deletes a file from the repository on a specific branch."""
    if not path or not branch or not message:
        raise GitHubMockError("path, branch, and message are required")
    repository = _require_repo(owner, repo)
    branch_obj = repository.branch(branch)
    if branch_obj is None:
        raise GitHubMockError(f"Unknown branch: {branch}")
    log = repository.branch_files(branch)
    if not any(f.path == path for f in log.files):
        raise GitHubMockError(f"Unknown file on {branch}: {path}")
    log.files = [f for f in log.files if f.path != path]
    commit_sha = f"sha_{branch}_delete_{path.replace('/', '_')}"
    repository.commits.append(
        _make_commit(
            sha=commit_sha,
            message=message,
            parents=[branch_obj.commit_sha],
            diff=f"- {path}\n",
        )
    )
    branch_obj.commit_sha = commit_sha
    return DeleteFileResult(deleted=True, path=path, commit_sha=commit_sha)


def github_get_file_contents(
    repo: str | None = None,
    owner: str | None = None,
    path: str | None = None,
    ref: str | None = None,
    sha: str | None = None,
) -> FileContentsResult:
    """Retrieves a single file or directory listing from a branch or specific ref."""
    repository = _require_repo(owner, repo)
    branch_name = ref or repository.default_branch
    if repository.branch(branch_name) is None:
        raise GitHubMockError(f"Unknown ref: {branch_name}")
    log = repository.branch_files(branch_name)
    if not path:
        return FileContentsResult(
            path="",
            ref=branch_name,
            entries=[
                TreeEntry(path=f.path, sha=f.sha, size=f.size, type=f.type)
                for f in log.files
            ],
        )
    direct = next((f for f in log.files if f.path == path), None)
    if direct is not None:
        if sha and sha != direct.sha:
            raise GitHubMockError("sha mismatch")
        return FileContentsResult(file=direct.model_copy(), ref=branch_name)
    matched = [f for f in log.files if f.path.startswith(f"{path}/")]
    if not matched:
        raise GitHubMockError(f"Unknown path: {path}")
    return FileContentsResult(
        path=path,
        ref=branch_name,
        entries=[
            TreeEntry(path=f.path, sha=f.sha, size=f.size, type=f.type) for f in matched
        ],
    )


def github_get_repository_tree(
    repo: str | None = None,
    owner: str | None = None,
    tree_sha: str | None = None,
    recursive: bool = False,
    path_filter: str | None = None,
) -> RepoTreeResult:
    """Returns the repository file tree, with optional recursion and path prefix filter."""
    repository = _require_repo(owner, repo)
    branch_name = tree_sha or repository.default_branch
    log = repository.branch_files(branch_name)
    items = list(log.files)
    if path_filter:
        items = [f for f in items if f.path.startswith(path_filter)]
    return RepoTreeResult(
        ref=branch_name,
        recursive=recursive,
        entries=[
            TreeEntry(path=f.path, sha=f.sha, size=f.size, type=f.type) for f in items
        ],
        truncated=False,
    )


def github_push_files(
    repo: str | None = None,
    owner: str | None = None,
    branch: str | None = None,
    message: str | None = None,
    files: list[GitHubFileEntry] | None = None,
) -> PushFilesResult:
    """Commits multiple files to a branch in a single commit."""
    if not branch or not message or not files:
        raise GitHubMockError("branch, message, and files are required")
    repository = _require_repo(owner, repo)
    branch_obj = repository.branch(branch)
    if branch_obj is None:
        raise GitHubMockError(f"Unknown branch: {branch}")
    log = repository.branch_files(branch)
    written: list[GitHubFile] = []
    for raw in files:
        entry = (
            raw
            if isinstance(raw, GitHubFileEntry)
            else GitHubFileEntry.model_validate(raw)
        )
        if not entry.path or entry.content is None:
            raise GitHubMockError("each file requires path and content")
        new_sha = f"sha_{branch}_{entry.path.replace('/', '_')}"
        record = GitHubFile(
            path=entry.path, content=entry.content, sha=new_sha, size=len(entry.content)
        )
        log.files = [f for f in log.files if f.path != entry.path]
        log.files.append(record)
        written.append(record)
    commit_sha = f"sha_{branch}_push_{len(written)}"
    repository.commits.append(
        _make_commit(
            sha=commit_sha,
            message=message,
            parents=[branch_obj.commit_sha],
            diff="+ " + "\n+ ".join(file.path for file in written),
        )
    )
    branch_obj.commit_sha = commit_sha
    return PushFilesResult(
        branch=branch, commit_sha=commit_sha, files=[f.model_copy() for f in written]
    )


def github_search_code(
    query: str | None = None,
    page: int = 1,
    perPage: int = 30,
    sort: str | None = None,
    order: str | None = None,
) -> CodeSearchResult:
    """Searches across all mocked repositories for matching file content."""
    del sort, order
    if not query:
        raise GitHubMockError("query is required")
    needle = query.lower()
    results: list[CodeSearchItem] = []
    for repository in get_state().repos:
        for log in repository.files:
            for f in log.files:
                if needle in (f.content or "").lower() or needle in f.path.lower():
                    results.append(
                        CodeSearchItem(
                            repository=repository.full_name,
                            branch=log.branch,
                            path=f.path,
                            sha=f.sha,
                            snippet=f.content[:120],
                        )
                    )
    return CodeSearchResult(
        total_count=len(results), items=_paginate(results, page=page, per_page=perPage)
    )


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


def github_create_repository(
    name: str | None = None,
    private: bool = False,
    description: str | None = None,
    autoInit: bool = False,
    organization: str | None = None,
) -> RepositoryResult:
    """Creates a new repository under the current user or an organization."""
    if not name:
        raise GitHubMockError("name is required")
    state = get_state()
    owner = organization or state.me.login
    if state.repo(owner, name) is not None:
        raise GitHubMockError(f"Repository already exists: {owner}/{name}")
    repository = _seed_repo(
        owner=owner,
        name=name,
        description=description or "",
        default_branch="main",
        private=private,
        visibility="private" if private else "public",
    )
    if not autoInit:
        # Empty out the seed files.
        repository.files = [
            type(repository.files[0])(branch=repository.default_branch, files=[])
        ]
    state.repos.append(repository)
    return RepositoryResult(repository=_to_public_repo(repository))


def github_fork_repository(
    repo: str | None = None,
    owner: str | None = None,
    organization: str | None = None,
) -> ForkResult:
    """Forks a repository into the current user or a specified organization."""
    repository = _require_repo(owner, repo)
    state = get_state()
    fork_owner = organization or state.me.login
    fork = repository.model_copy(deep=True)
    fork.owner = fork_owner
    fork.full_name = f"{fork_owner}/{repository.name}"
    fork.html_url = f"https://github.com/{fork.full_name}"
    fork.forks = 0
    state.repos.append(fork)
    repository.forks += 1
    return ForkResult(fork=_to_public_repo(fork))


def github_star_repository(
    repo: str | None = None, owner: str | None = None
) -> StarToggleResult:
    """Stars a repository."""
    repository = _require_repo(owner, repo)
    state = get_state()
    if repository.full_name not in state.starred:
        state.starred.append(repository.full_name)
        repository.stars += 1
    return StarToggleResult(starred=True, repository=repository.full_name)


def github_unstar_repository(
    repo: str | None = None, owner: str | None = None
) -> StarToggleResult:
    """Removes a star from a repository."""
    repository = _require_repo(owner, repo)
    state = get_state()
    if repository.full_name in state.starred:
        state.starred.remove(repository.full_name)
        repository.stars = max(0, repository.stars - 1)
    return StarToggleResult(starred=False, repository=repository.full_name)


def github_list_starred_repositories(
    sort: str | None = None,
    direction: str | None = None,
    page: int = 1,
    perPage: int = 30,
) -> ListStarredResult:
    """Lists the current user's starred repositories."""
    del sort
    state = get_state()
    repos: list[GitHubRepo] = []
    for full in state.starred:
        owner, _, name = full.partition("/")
        repo = state.repo(owner, name)
        if repo is not None:
            repos.append(repo)
    reverse = (direction or "desc") == "desc"
    repos.sort(key=lambda r: r.name, reverse=reverse)
    return ListStarredResult(
        total_count=len(repos),
        repositories=[
            _to_public_repo(r) for r in _paginate(repos, page=page, per_page=perPage)
        ],
    )


def github_get_latest_release(
    repo: str | None = None, owner: str | None = None
) -> ReleaseResult:
    """Returns the most recent release for a repository."""
    repository = _require_repo(owner, repo)
    if not repository.releases:
        raise GitHubMockError(f"No releases for {repository.full_name}")
    latest = max(
        repository.releases, key=lambda r: r.published_at or r.created_at or ""
    )
    return ReleaseResult(release=latest.model_copy())


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


def _find_notification(thread_id: str) -> Notification:
    notification = get_state().notification(thread_id)
    if notification is None:
        # Also try by .id
        notification = next(
            (n for n in get_state().notifications if n.id == thread_id), None
        )
    if notification is None:
        raise GitHubMockError(f"Unknown notification thread: {thread_id}")
    return notification


def github_dismiss_notification(
    threadID: str | None = None, state: str | None = None
) -> NotificationResult:
    """Marks a notification thread as read or done."""
    if not threadID or state not in {"read", "done"}:
        raise GitHubMockError("threadID and state ('read' or 'done') are required")
    notification = _find_notification(threadID)
    notification.unread = False
    notification.updated_at = _now_iso()
    return NotificationResult(notification=notification.model_copy())


def github_get_notification_details(
    notificationID: str | None = None,
) -> NotificationResult:
    """Retrieves details for a specific notification."""
    if not notificationID:
        raise GitHubMockError("notificationID is required")
    return NotificationResult(
        notification=_find_notification(notificationID).model_copy()
    )


def github_list_notifications(
    repo: str | None = None,
    owner: str | None = None,
    since: str | None = None,
    before: str | None = None,
    filter: str | None = None,
    perPage: int = 30,
    page: int = 1,
) -> ListNotificationsResult:
    """Lists notifications with optional repository, time range, and filter."""
    notifications = list(get_state().notifications)
    if owner and repo:
        full = f"{owner}/{repo}"
        notifications = [n for n in notifications if n.repository == full]
    if since:
        notifications = [n for n in notifications if n.updated_at >= since]
    if before:
        notifications = [n for n in notifications if n.updated_at <= before]
    if filter == "include_read_notifications":
        pass
    elif filter == "only_participating":
        notifications = [
            n
            for n in notifications
            if n.reason in {"author", "comment", "mention", "review_requested"}
        ]
    elif filter is not None and filter != "default":
        raise GitHubMockError("Unsupported filter")
    return ListNotificationsResult(
        total_count=len(notifications),
        notifications=[
            n.model_copy()
            for n in _paginate(notifications, page=page, per_page=perPage)
        ],
    )


def github_manage_notification_subscription(
    notificationID: str | None = None, action: str | None = None
) -> NotificationResult | NotificationDeletedResult:
    """Controls a thread's subscription: ignore, watch, or delete."""
    if not notificationID or action not in {"ignore", "watch", "delete"}:
        raise GitHubMockError(
            "notificationID and action ('ignore', 'watch', 'delete') are required"
        )
    notification = _find_notification(notificationID)
    if action == "delete":
        get_state().notifications = [
            n for n in get_state().notifications if n is not notification
        ]
        return NotificationDeletedResult(deleted=True, thread_id=notificationID)
    return NotificationResult(notification=notification.model_copy())


def github_manage_repository_notification_subscription(
    repo: str | None = None, owner: str | None = None, action: str | None = None
) -> RepoSubscriptionResult:
    """Controls a repository's notification subscription."""
    if action not in {"ignore", "watch", "unwatch"}:
        raise GitHubMockError("action must be one of: ignore, watch, unwatch")
    repository = _require_repo(owner, repo)
    if action == "watch":
        repository.subscription = Subscription(
            subscribed=True, ignored=False, reason="manual"
        )
    elif action == "ignore":
        repository.subscription = Subscription(
            subscribed=False, ignored=True, reason="manual"
        )
    else:
        repository.subscription = Subscription(
            subscribed=False, ignored=False, reason="manual"
        )
    return RepoSubscriptionResult(
        repository=repository.full_name,
        subscription=repository.subscription.model_copy(),
    )


def github_mark_all_notifications_read(
    repo: str | None = None, owner: str | None = None, lastReadAt: str | None = None
) -> MarkReadResult:
    """Marks all notifications (or all in a single repo) as read."""
    full = f"{owner}/{repo}" if owner and repo else None
    cutoff = lastReadAt or _now_iso()
    affected = 0
    for notification in get_state().notifications:
        if full is not None and notification.repository != full:
            continue
        if notification.updated_at > cutoff:
            continue
        if notification.unread:
            notification.unread = False
            affected += 1
    return MarkReadResult(marked_read=affected, lastReadAt=cutoff)


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------


def _require_alert(alerts: list[SecurityAlert], number: int) -> SecurityAlert:
    for alert in alerts:
        if alert.number == number:
            return alert
    raise GitHubMockError(f"Unknown alert: {number}")


def github_get_code_scanning_alert(
    repo: str | None = None, owner: str | None = None, alertNumber: int | None = None
) -> AlertResult:
    """Retrieves a single code scanning alert by number."""
    if alertNumber is None:
        raise GitHubMockError("alertNumber is required")
    repository = _require_repo(owner, repo)
    return AlertResult(
        alert=_require_alert(repository.code_scanning, alertNumber).model_copy()
    )


def github_list_code_scanning_alerts(
    repo: str | None = None,
    owner: str | None = None,
    ref: str | None = None,
    state: str | None = None,
    severity: str | None = None,
    tool_name: str | None = None,
) -> ListAlertsResult:
    """Lists code scanning alerts with optional ref, state, severity, and tool filters."""
    repository = _require_repo(owner, repo)
    alerts = list(repository.code_scanning)
    if ref is not None:
        alerts = [a for a in alerts if a.ref == ref]
    if state is not None:
        alerts = [a for a in alerts if a.state == state]
    if severity is not None:
        alerts = [a for a in alerts if a.severity == severity]
    if tool_name is not None:
        alerts = [a for a in alerts if a.tool_name == tool_name]
    return ListAlertsResult(
        total_count=len(alerts), alerts=[a.model_copy() for a in alerts]
    )


def github_get_dependabot_alert(
    repo: str | None = None, owner: str | None = None, alertNumber: int | None = None
) -> AlertResult:
    """Retrieves a Dependabot alert by number."""
    if alertNumber is None:
        raise GitHubMockError("alertNumber is required")
    repository = _require_repo(owner, repo)
    return AlertResult(
        alert=_require_alert(repository.dependabot, alertNumber).model_copy()
    )


def github_list_dependabot_alerts(
    repo: str | None = None,
    owner: str | None = None,
    state: str | None = None,
    severity: str | None = None,
) -> ListAlertsResult:
    """Lists Dependabot alerts with optional state and severity filters."""
    repository = _require_repo(owner, repo)
    alerts = list(repository.dependabot)
    if state is not None:
        alerts = [a for a in alerts if a.state == state]
    if severity is not None:
        alerts = [a for a in alerts if a.severity == severity]
    return ListAlertsResult(
        total_count=len(alerts), alerts=[a.model_copy() for a in alerts]
    )


def github_get_secret_scanning_alert(
    repo: str | None = None, owner: str | None = None, alertNumber: int | None = None
) -> AlertResult:
    """Retrieves a secret scanning alert by number."""
    if alertNumber is None:
        raise GitHubMockError("alertNumber is required")
    repository = _require_repo(owner, repo)
    return AlertResult(
        alert=_require_alert(repository.secret_scanning, alertNumber).model_copy()
    )


def github_list_secret_scanning_alerts(
    repo: str | None = None,
    owner: str | None = None,
    state: str | None = None,
    resolution: str | None = None,
    secret_type: str | None = None,
) -> ListAlertsResult:
    """Lists secret scanning alerts with optional state, resolution, and type filters."""
    repository = _require_repo(owner, repo)
    alerts = list(repository.secret_scanning)
    if state is not None:
        alerts = [a for a in alerts if a.state == state]
    if resolution is not None:
        alerts = [a for a in alerts if a.resolution == resolution]
    if secret_type is not None:
        alerts = [a for a in alerts if a.secret_type == secret_type]
    return ListAlertsResult(
        total_count=len(alerts), alerts=[a.model_copy() for a in alerts]
    )


def github_run_secret_scanning(
    repo: str | None = None,
    owner: str | None = None,
    files: list[GitHubFileEntry] | None = None,
) -> SecretScanResult:
    """Runs an ad-hoc secret scan on supplied file content; returns mocked findings."""
    if not files:
        raise GitHubMockError("files is required")
    repository = _require_repo(owner, repo)
    findings: list[SecretFinding] = []
    coerced: list[GitHubFileEntry] = []
    for raw in files:
        coerced.append(
            raw
            if isinstance(raw, GitHubFileEntry)
            else GitHubFileEntry.model_validate(raw)
        )
    for entry in coerced:
        if "openai_api_key" in entry.content.lower() or "sk-" in entry.content:
            findings.append(
                SecretFinding(
                    path=entry.path, secret_type="openai_api_key", severity="critical"
                )
            )
        if "aws_access_key_id" in entry.content.lower():
            findings.append(
                SecretFinding(
                    path=entry.path, secret_type="aws_access_key_id", severity="high"
                )
            )
    return SecretScanResult(
        repository=repository.full_name, findings=findings, scanned_files=len(coerced)
    )


# ---------------------------------------------------------------------------
# Releases & Tags
# ---------------------------------------------------------------------------


def github_get_release_by_tag(
    repo: str | None = None, owner: str | None = None, tag: str | None = None
) -> ReleaseResult:
    """Retrieves a release by its tag name."""
    if not tag:
        raise GitHubMockError("tag is required")
    repository = _require_repo(owner, repo)
    release = repository.release_by_tag(tag)
    if release is None:
        raise GitHubMockError(f"Unknown release tag: {tag}")
    return ReleaseResult(release=release.model_copy())


def github_list_releases(
    repo: str | None = None, owner: str | None = None, page: int = 1, perPage: int = 30
) -> ListReleasesResult:
    """Lists releases for a repository, newest first."""
    repository = _require_repo(owner, repo)
    releases = sorted(
        repository.releases, key=lambda r: r.published_at or "", reverse=True
    )
    return ListReleasesResult(
        total_count=len(releases),
        releases=[
            r.model_copy() for r in _paginate(releases, page=page, per_page=perPage)
        ],
    )


def github_get_tag(
    repo: str | None = None, owner: str | None = None, tag: str | None = None
) -> TagResult:
    """Retrieves tag metadata."""
    if not tag:
        raise GitHubMockError("tag is required")
    repository = _require_repo(owner, repo)
    found = repository.tag(tag)
    if found is None:
        raise GitHubMockError(f"Unknown tag: {tag}")
    return TagResult(tag=found.model_copy())


def github_list_tags(
    repo: str | None = None, owner: str | None = None, page: int = 1, perPage: int = 30
) -> ListTagsResult:
    """Lists repository tags."""
    repository = _require_repo(owner, repo)
    tags = list(repository.tags)
    return ListTagsResult(
        total_count=len(tags),
        tags=[t.model_copy() for t in _paginate(tags, page=page, per_page=perPage)],
    )


# ---------------------------------------------------------------------------
# Commits
# ---------------------------------------------------------------------------


def _to_public_commit(commit: GitHubCommit, *, include_diff: bool) -> PublicCommit:
    return PublicCommit(
        sha=commit.sha,
        commit=commit.commit.model_copy(deep=True),
        author=commit.author,
        parents=[p.model_copy() for p in commit.parents],
        diff=commit.diff if include_diff else None,
    )


def github_get_commit(
    repo: str | None = None,
    owner: str | None = None,
    sha: str | None = None,
    include_diff: bool = False,
    page: int = 1,
    perPage: int = 30,
) -> CommitResult:
    """Retrieves a commit by SHA, with optional diff."""
    del page, perPage
    if not sha:
        raise GitHubMockError("sha is required")
    repository = _require_repo(owner, repo)
    commit = repository.commit(sha)
    if commit is None:
        raise GitHubMockError(f"Unknown commit: {sha}")
    return CommitResult(commit=_to_public_commit(commit, include_diff=include_diff))


def github_list_commits(
    repo: str | None = None,
    owner: str | None = None,
    sha: str | None = None,
    author: str | None = None,
    page: int = 1,
    perPage: int = 30,
) -> ListCommitsResult:
    """Lists commits with optional branch/SHA and author filters."""
    repository = _require_repo(owner, repo)
    commits = list(repository.commits)
    if sha is not None and repository.branch(sha) is not None:
        head = repository.branch(sha).commit_sha  # type: ignore[union-attr]
        commits = [
            c for c in commits if c.sha == head or any(p.sha == head for p in c.parents)
        ]
    if author is not None:
        commits = [c for c in commits if c.author == author]
    commits.sort(key=lambda c: c.commit.author.date, reverse=True)
    return ListCommitsResult(
        total_count=len(commits),
        commits=[
            _to_public_commit(c, include_diff=True)
            for c in _paginate(commits, page=page, per_page=perPage)
        ],
    )


# ---------------------------------------------------------------------------
# Discussions
# ---------------------------------------------------------------------------


def github_get_discussion(
    repo: str | None = None,
    owner: str | None = None,
    discussionNumber: int | None = None,
) -> DiscussionResult:
    """Retrieves a single discussion thread."""
    if discussionNumber is None:
        raise GitHubMockError("discussionNumber is required")
    repository = _require_repo(owner, repo)
    discussion = repository.discussion(discussionNumber)
    if discussion is None:
        raise GitHubMockError(f"Unknown discussion: {discussionNumber}")
    return DiscussionResult(discussion=discussion.model_copy(deep=True))


def github_get_discussion_comments(
    repo: str | None = None,
    owner: str | None = None,
    discussionNumber: int | None = None,
    after: str | None = None,
    perPage: int = 30,
) -> DiscussionCommentsResult:
    """Retrieves comments on a discussion."""
    if discussionNumber is None:
        raise GitHubMockError("discussionNumber is required")
    repository = _require_repo(owner, repo)
    discussion = repository.discussion(discussionNumber)
    if discussion is None:
        raise GitHubMockError(f"Unknown discussion: {discussionNumber}")
    comments = list(discussion.comments)
    if after:
        ids = [str(c.id) for c in comments]
        if after not in ids:
            raise GitHubMockError(f"Unknown cursor: {after}")
        comments = comments[ids.index(after) + 1 :]
    return DiscussionCommentsResult(
        discussion_number=discussionNumber,
        comments=[c.model_copy() for c in comments[:perPage]],
    )


def github_list_discussions(
    repo: str | None = None,
    owner: str | None = None,
    category: str | None = None,
    orderBy: str | None = None,
    direction: str | None = None,
    perPage: int = 30,
    after: str | None = None,
) -> ListDiscussionsResult:
    """Lists discussions for a repository (or all repos when omitted)."""
    if owner and repo:
        repos = [_require_repo(owner, repo)]
    else:
        repos = list(get_state().repos)
    entries: list[DiscussionEntry] = []
    for repository in repos:
        for discussion in repository.discussions:
            entries.append(
                DiscussionEntry(
                    number=discussion.number,
                    title=discussion.title,
                    body=discussion.body,
                    category=discussion.category,
                    user=discussion.user,
                    created_at=discussion.created_at,
                    updated_at=discussion.updated_at,
                    comments=[c.model_copy() for c in discussion.comments],
                    repository=repository.full_name,
                )
            )
    if category is not None:
        entries = [e for e in entries if e.category == category]
    sort_key = orderBy or "updated_at"
    reverse = (direction or "desc") == "desc"
    entries.sort(key=lambda e: getattr(e, sort_key, ""), reverse=reverse)
    if after:
        numbers = [str(e.number) for e in entries]
        if after not in numbers:
            raise GitHubMockError(f"Unknown cursor: {after}")
        entries = entries[numbers.index(after) + 1 :]
    return ListDiscussionsResult(
        total_count=len(entries), discussions=entries[:perPage]
    )


def github_list_discussion_categories(
    repo: str | None = None, owner: str | None = None
) -> DiscussionCategoriesResult:
    """Lists discussion categories for a repository."""
    repository = _require_repo(owner, repo)
    return DiscussionCategoriesResult(
        repository=repository.full_name,
        categories=[c.model_copy() for c in repository.discussion_categories],
    )


# ---------------------------------------------------------------------------
# Gists
# ---------------------------------------------------------------------------


def github_create_gist(
    content: str | None = None,
    filename: str | None = None,
    description: str | None = None,
    public: bool = False,
) -> GistResult:
    """Creates a gist with a single file."""
    if content is None or not filename:
        raise GitHubMockError("content and filename are required")
    state = get_state()
    state.counters.gist += 1
    gist_id = f"gist_{state.counters.gist}"
    gist = Gist(
        id=gist_id,
        description=description or "",
        public=public,
        owner=state.me.login,
        files=[
            GistFileEntry(
                name=filename,
                file=GistFile(filename=filename, content=content, language=""),
            )
        ],
        html_url=f"https://gist.github.com/{state.me.login}/{gist_id}",
        created_at=_now_iso(),
        updated_at=_now_iso(),
    )
    state.gists.append(gist)
    return GistResult(gist=gist.model_copy(deep=True))


def github_get_gist(gist_id: str | None = None) -> GistResult:
    """Retrieves a gist by ID."""
    if not gist_id:
        raise GitHubMockError("gist_id is required")
    gist = get_state().gist(gist_id)
    if gist is None:
        raise GitHubMockError(f"Unknown gist: {gist_id}")
    return GistResult(gist=gist.model_copy(deep=True))


def github_list_gists(
    username: str | None = None,
    since: str | None = None,
    perPage: int = 30,
    page: int = 1,
) -> ListGistsResult:
    """Lists gists, optionally filtered by user or since timestamp."""
    gists = list(get_state().gists)
    if username is not None:
        gists = [g for g in gists if g.owner == username]
    if since is not None:
        gists = [g for g in gists if g.updated_at >= since]
    gists.sort(key=lambda g: g.updated_at, reverse=True)
    return ListGistsResult(
        total_count=len(gists),
        gists=[
            g.model_copy(deep=True)
            for g in _paginate(gists, page=page, per_page=perPage)
        ],
    )


def github_update_gist(
    gist_id: str | None = None,
    filename: str | None = None,
    content: str | None = None,
    description: str | None = None,
) -> GistResult:
    """Updates an existing gist's filename, content, or description."""
    if not gist_id or not filename or content is None:
        raise GitHubMockError("gist_id, filename, and content are required")
    gist = get_state().gist(gist_id)
    if gist is None:
        raise GitHubMockError(f"Unknown gist: {gist_id}")
    entry = next((f for f in gist.files if f.name == filename), None)
    if entry is None:
        gist.files.append(
            GistFileEntry(
                name=filename,
                file=GistFile(filename=filename, content=content, language=""),
            )
        )
    else:
        entry.file.content = content
    if description is not None:
        gist.description = description
    gist.updated_at = _now_iso()
    return GistResult(gist=gist.model_copy(deep=True))


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def github_search_issues(
    repo: str | None = None,
    owner: str | None = None,
    query: str | None = None,
    sort: str | None = None,
    order: str | None = None,
    page: int = 1,
    perPage: int = 30,
) -> IssueSearchResult:
    """Searches issues across mocked repositories using a free-text query."""
    needle = (query or "").lower()
    matches: list[IssueSearchItem] = []
    for repository in get_state().repos:
        if owner and repo and repository.full_name != f"{owner}/{repo}":
            continue
        for issue in repository.issues:
            if (
                needle
                and needle not in issue.title.lower()
                and needle not in (issue.body or "").lower()
            ):
                continue
            matches.append(
                IssueSearchItem(
                    number=issue.number,
                    title=issue.title,
                    body=issue.body,
                    state=issue.state,
                    state_reason=issue.state_reason,
                    labels=list(issue.labels),
                    assignees=list(issue.assignees),
                    milestone=issue.milestone,
                    type=issue.type,
                    user=issue.user,
                    comments_count=issue.comments_count,
                    sub_issues=list(issue.sub_issues),
                    created_at=issue.created_at,
                    updated_at=issue.updated_at,
                    closed_at=issue.closed_at,
                    closed_by_pr=issue.closed_by_pr,
                    html_url=issue.html_url,
                    repository=repository.full_name,
                )
            )
    sort_attr = sort or "updated_at"
    matches.sort(
        key=lambda item: getattr(item, sort_attr, ""),
        reverse=(order or "desc") == "desc",
    )
    return IssueSearchResult(
        total_count=len(matches), items=_paginate(matches, page=page, per_page=perPage)
    )


def github_search_pull_requests(
    repo: str | None = None,
    owner: str | None = None,
    query: str | None = None,
    sort: str | None = None,
    order: str | None = None,
    page: int = 1,
    perPage: int = 30,
) -> PRSearchResult:
    """Searches pull requests across mocked repositories."""
    needle = (query or "").lower()
    matches: list[PRSearchItem] = []
    for repository in get_state().repos:
        if owner and repo and repository.full_name != f"{owner}/{repo}":
            continue
        for pr in repository.pulls:
            if (
                needle
                and needle not in pr.title.lower()
                and needle not in (pr.body or "").lower()
            ):
                continue
            matches.append(
                PRSearchItem(
                    **pr.model_dump(),
                    repository=repository.full_name,
                )
            )
    sort_attr = sort or "updated_at"
    matches.sort(
        key=lambda item: getattr(item, sort_attr, ""),
        reverse=(order or "desc") == "desc",
    )
    return PRSearchResult(
        total_count=len(matches), items=_paginate(matches, page=page, per_page=perPage)
    )


def github_search_repositories(
    query: str | None = None,
    sort: str | None = None,
    order: str | None = None,
    page: int = 1,
    perPage: int = 30,
    minimal_output: bool = False,
) -> RepoSearchResult:
    """Searches repositories by name, description, or topic."""
    del sort
    if not query:
        raise GitHubMockError("query is required")
    needle = query.lower()
    matches: list[GitHubRepo] = []
    for repository in get_state().repos:
        haystacks = [
            repository.name,
            repository.description or "",
            " ".join(repository.topics),
        ]
        if any(needle in h.lower() for h in haystacks):
            matches.append(repository)
    matches.sort(key=lambda r: r.stars, reverse=(order or "desc") == "desc")
    page_items = _paginate(matches, page=page, per_page=perPage)
    if minimal_output:
        items = [
            RepoSearchItem(full_name=r.full_name, stars=r.stars) for r in page_items
        ]
    else:
        items = [
            RepoSearchItem(
                full_name=r.full_name,
                stars=r.stars,
                owner=r.owner,
                name=r.name,
                description=r.description,
                default_branch=r.default_branch,
                private=r.private,
                visibility=r.visibility,
                html_url=r.html_url,
                forks=r.forks,
                topics=list(r.topics),
            )
            for r in page_items
        ]
    return RepoSearchResult(total_count=len(matches), items=items)


def github_search_users(
    query: str | None = None,
    sort: str | None = None,
    order: str | None = None,
    page: int = 1,
    perPage: int = 30,
) -> UserSearchResult:
    """Searches users by login, name, or email."""
    del sort, order
    if not query:
        raise GitHubMockError("query is required")
    needle = query.lower()
    matches = [
        u
        for u in get_state().users
        if needle in u.login.lower()
        or needle in u.name.lower()
        or needle in (u.email or "").lower()
    ]
    return UserSearchResult(
        total_count=len(matches),
        items=[u.model_copy() for u in _paginate(matches, page=page, per_page=perPage)],
    )


def github_search_orgs(
    query: str | None = None,
    sort: str | None = None,
    order: str | None = None,
    page: int = 1,
    perPage: int = 30,
) -> OrgSearchResult:
    """Searches organizations."""
    del sort, order
    if not query:
        raise GitHubMockError("query is required")
    needle = query.lower()
    matches = [
        o
        for o in get_state().orgs
        if needle in o.login.lower() or needle in (o.description or "").lower()
    ]
    return OrgSearchResult(
        total_count=len(matches),
        items=[
            o.model_copy(deep=True)
            for o in _paginate(matches, page=page, per_page=perPage)
        ],
    )


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------


def github_get_label(
    repo: str | None = None, owner: str | None = None, name: str | None = None
) -> LabelResult:
    """Retrieves a single repository label by name."""
    if not name:
        raise GitHubMockError("name is required")
    repository = _require_repo(owner, repo)
    label = repository.label(name)
    if label is None:
        raise GitHubMockError(f"Unknown label: {name}")
    return LabelResult(label=label.model_copy())


def github_list_label(
    repo: str | None = None, owner: str | None = None
) -> ListLabelsResult:
    """Lists all labels on a repository."""
    repository = _require_repo(owner, repo)
    return ListLabelsResult(
        total_count=len(repository.labels),
        labels=[l.model_copy() for l in repository.labels],
    )


def github_label_write(
    repo: str | None = None,
    owner: str | None = None,
    method: str | None = None,
    name: str | None = None,
    color: str | None = None,
    description: str | None = None,
    new_name: str | None = None,
) -> LabelWriteResult:
    """Creates, updates, or deletes a repository label."""
    if not method or not name:
        raise GitHubMockError("method and name are required")
    repository = _require_repo(owner, repo)
    if method == "create":
        if repository.label(name) is not None:
            raise GitHubMockError(f"Label already exists: {name}")
        label = GitHubLabel(
            name=name, color=color or "ededed", description=description or ""
        )
        repository.labels.append(label)
        return LabelWriteResult(label=label.model_copy())
    if method == "update":
        label = repository.label(name)
        if label is None:
            raise GitHubMockError(f"Unknown label: {name}")
        if color is not None:
            label.color = color
        if description is not None:
            label.description = description
        if new_name is not None and new_name != name:
            label.name = new_name
        return LabelWriteResult(label=label.model_copy())
    if method == "delete":
        label = repository.label(name)
        if label is None:
            raise GitHubMockError(f"Unknown label: {name}")
        repository.labels = [l for l in repository.labels if l.name != name]
        return LabelWriteResult(deleted=True, name=name)
    raise GitHubMockError(f"Unsupported method: {method}")


# ---------------------------------------------------------------------------
# Security advisories
# ---------------------------------------------------------------------------


def github_get_global_security_advisory(
    ghsaId: str | None = None,
) -> GlobalAdvisoryResult:
    """Retrieves a global security advisory by GHSA ID."""
    if not ghsaId:
        raise GitHubMockError("ghsaId is required")
    advisory = next(
        (a for a in get_state().global_advisories if a.ghsa_id == ghsaId), None
    )
    if advisory is None:
        raise GitHubMockError(f"Unknown advisory: {ghsaId}")
    return GlobalAdvisoryResult(advisory=advisory.model_copy(deep=True))


def github_list_global_security_advisories(
    ghsaId: str | None = None,
    cveId: str | None = None,
    cwes: list[str] | None = None,
    ecosystem: str | None = None,
    severity: str | None = None,
) -> ListGlobalAdvisoriesResult:
    """Lists global security advisories with optional filters."""
    advisories = list(get_state().global_advisories)
    if ghsaId is not None:
        advisories = [a for a in advisories if a.ghsa_id == ghsaId]
    if cveId is not None:
        advisories = [a for a in advisories if a.cve_id == cveId]
    if cwes:
        wanted = set(cwes)
        advisories = [a for a in advisories if wanted.issubset(set(a.cwes))]
    if ecosystem is not None:
        advisories = [a for a in advisories if a.ecosystem == ecosystem]
    if severity is not None:
        advisories = [a for a in advisories if a.severity == severity]
    return ListGlobalAdvisoriesResult(
        total_count=len(advisories),
        advisories=[a.model_copy(deep=True) for a in advisories],
    )


def github_list_repository_security_advisories(
    repo: str | None = None,
    owner: str | None = None,
    sort: str | None = None,
    state: str | None = None,
    direction: str | None = None,
) -> ListRepoAdvisoriesResult:
    """Lists repository-specific security advisories."""
    repository = _require_repo(owner, repo)
    advisories = list(repository.security_advisories)
    if state is not None:
        advisories = [a for a in advisories if a.state == state]
    sort_attr = sort or "published_at"
    advisories.sort(
        key=lambda a: getattr(a, sort_attr, ""), reverse=(direction or "desc") == "desc"
    )
    return ListRepoAdvisoriesResult(
        total_count=len(advisories),
        advisories=[RepoAdvisoryEntry(**a.model_dump()) for a in advisories],
    )


def github_list_org_repository_security_advisories(
    org: str | None = None,
    sort: str | None = None,
    state: str | None = None,
    direction: str | None = None,
) -> ListRepoAdvisoriesResult:
    """Lists organization-wide security advisories across repos."""
    organization = _require_org(org)
    entries: list[RepoAdvisoryEntry] = []
    for repository in get_state().repos:
        if repository.owner != organization.login:
            continue
        for advisory in repository.security_advisories:
            entries.append(
                RepoAdvisoryEntry(
                    **advisory.model_dump(), repository=repository.full_name
                )
            )
    if state is not None:
        entries = [e for e in entries if e.state == state]
    sort_attr = sort or "published_at"
    entries.sort(
        key=lambda e: getattr(e, sort_attr, ""), reverse=(direction or "desc") == "desc"
    )
    return ListRepoAdvisoriesResult(total_count=len(entries), advisories=entries)


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


def _require_project(repository: GitHubRepo, project_id: int) -> GitHubProject:
    project = repository.project(project_id)
    if project is None:
        raise GitHubMockError(f"Unknown project: {project_id}")
    return project


def github_projects_get(
    repo: str | None = None,
    owner: str | None = None,
    method: str | None = None,
    project_id: int | None = None,
    field_id: int | None = None,
    item_id: int | None = None,
    status_update_id: int | None = None,
) -> ProjectGetResult:
    """Retrieves project resources via method dispatch."""
    if not method:
        raise GitHubMockError("method is required")
    repository = _require_repo(owner, repo)
    if project_id is None:
        raise GitHubMockError("project_id is required")
    project = _require_project(repository, project_id)
    if method == "get_project":
        return ProjectGetResult(project=project.model_copy(deep=True))
    if method == "get_project_field":
        if field_id is None:
            raise GitHubMockError("field_id is required for get_project_field")
        field = next((f for f in project.fields if f.id == field_id), None)
        if field is None:
            raise GitHubMockError(f"Unknown field: {field_id}")
        return ProjectGetResult(field=field.model_copy(deep=True))
    if method == "get_project_item":
        if item_id is None:
            raise GitHubMockError("item_id is required for get_project_item")
        item = next((i for i in project.items if i.id == item_id), None)
        if item is None:
            raise GitHubMockError(f"Unknown item: {item_id}")
        return ProjectGetResult(item=item.model_copy())
    if method == "get_project_status_update":
        if status_update_id is None:
            raise GitHubMockError(
                "status_update_id is required for get_project_status_update"
            )
        update = next(
            (u for u in project.status_updates if u.id == status_update_id), None
        )
        if update is None:
            raise GitHubMockError(f"Unknown status update: {status_update_id}")
        return ProjectGetResult(status_update=update.model_copy())
    raise GitHubMockError(f"Unsupported method: {method}")


def github_projects_list(
    repo: str | None = None,
    owner: str | None = None,
    method: str | None = None,
    project_id: int | None = None,
) -> ProjectListResult:
    """Lists project resources via method dispatch."""
    if not method:
        raise GitHubMockError("method is required")
    repository = _require_repo(owner, repo)
    if method == "list_projects":
        return ProjectListResult(
            projects=[p.model_copy(deep=True) for p in repository.projects]
        )
    if project_id is None:
        raise GitHubMockError("project_id is required")
    project = _require_project(repository, project_id)
    if method == "list_project_fields":
        return ProjectListResult(
            project_id=project_id,
            fields=[f.model_copy(deep=True) for f in project.fields],
        )
    if method == "list_project_items":
        return ProjectListResult(
            project_id=project_id, items=[i.model_copy() for i in project.items]
        )
    if method == "list_project_status_updates":
        return ProjectListResult(
            project_id=project_id,
            status_updates=[u.model_copy() for u in project.status_updates],
        )
    raise GitHubMockError(f"Unsupported method: {method}")


def github_projects_write(
    repo: str | None = None,
    owner: str | None = None,
    method: str | None = None,
    project_id: int | None = None,
    item_id: int | None = None,
    item: str | None = None,
    body: str | None = None,
) -> ProjectWriteResult:
    """Modifies project items or status updates."""
    if not method:
        raise GitHubMockError("method is required")
    repository = _require_repo(owner, repo)
    if project_id is None:
        raise GitHubMockError("project_id is required")
    project = _require_project(repository, project_id)
    if method == "add_project_item":
        if not item:
            raise GitHubMockError("item is required for add_project_item")
        payload = _parse_json_object(item, what="item")
        repository.counters.project_item += 1
        new_item = ProjectItem(
            id=repository.counters.project_item,
            type=payload.get("type", "issue"),
            issue_number=int(payload.get("issue_number", 0)),
            status=payload.get("status", "Todo"),
            priority=payload.get("priority", "P2"),
        )
        project.items.append(new_item)
        return ProjectWriteResult(item=new_item.model_copy())
    if method == "update_project_item":
        if item_id is None or not item:
            raise GitHubMockError(
                "item_id and item are required for update_project_item"
            )
        payload = _parse_json_object(item, what="item")
        existing = next((i for i in project.items if i.id == item_id), None)
        if existing is None:
            raise GitHubMockError(f"Unknown item: {item_id}")
        for key, value in payload.items():
            if hasattr(existing, key):
                setattr(existing, key, value)
        return ProjectWriteResult(item=existing.model_copy())
    if method == "delete_project_item":
        if item_id is None:
            raise GitHubMockError("item_id is required for delete_project_item")
        before = len(project.items)
        project.items = [i for i in project.items if i.id != item_id]
        if len(project.items) == before:
            raise GitHubMockError(f"Unknown item: {item_id}")
        return ProjectWriteResult(deleted=True, item_id=item_id)
    if method == "create_project_status_update":
        if not body:
            raise GitHubMockError("body is required for create_project_status_update")
        next_id = max((u.id for u in project.status_updates), default=8800) + 1
        update = ProjectStatusUpdate(id=next_id, body=body, created_at=_now_iso())
        project.status_updates.append(update)
        return ProjectWriteResult(status_update=update.model_copy())
    raise GitHubMockError(f"Unsupported method: {method}")


# ---------------------------------------------------------------------------
# User & Org
# ---------------------------------------------------------------------------


def github_get_me() -> MeResult:
    """Returns the authenticated mock user's profile."""
    return MeResult(user=get_state().me.model_copy())


def github_get_teams(user: str | None = None) -> TeamsResult:
    """Lists teams for a user (defaults to the authenticated user)."""
    login = user or get_state().me.login
    teams = [
        TeamMembership(
            org=team.org, slug=team.slug, name=team.name, description=team.description
        )
        for team in get_state().teams
        if login in team.members
    ]
    return TeamsResult(user=login, teams=teams)


def github_get_team_members(
    org: str | None = None, team_slug: str | None = None
) -> TeamMembersResult:
    """Lists members of a specific organization team."""
    if not org or not team_slug:
        raise GitHubMockError("org and team_slug are required")
    team = get_state().team(org, team_slug)
    if team is None:
        raise GitHubMockError(f"Unknown team: {org}/{team_slug}")
    return TeamMembersResult(org=org, team_slug=team_slug, members=list(team.members))


def github_list_branches(
    repo: str | None = None,
    owner: str | None = None,
    page: int = 1,
    perPage: int = 30,
) -> ListBranchesResult:
    """Lists branches in a repository."""
    repository = _require_repo(owner, repo)
    branches = list(repository.branches)
    return ListBranchesResult(
        total_count=len(branches),
        branches=[
            b.model_copy() for b in _paginate(branches, page=page, per_page=perPage)
        ],
    )


# ---------------------------------------------------------------------------
# Copilot
# ---------------------------------------------------------------------------


def github_get_copilot_job_status(
    id: str | None = None, repo: str | None = None, owner: str | None = None
) -> CopilotJobResult:
    """Retrieves the status of a Copilot agent job."""
    if not id:
        raise GitHubMockError("id is required")
    repository = _require_repo(owner, repo)
    job = get_state().copilot_job(id)
    if job is None:
        raise GitHubMockError(f"Unknown copilot job: {id}")
    if job.repo != repository.name or job.owner != repository.owner:
        raise GitHubMockError(f"Job {id} does not belong to {repository.full_name}")
    return CopilotJobResult(job=job.model_copy())


def github_get_copilot_space(
    name: str | None = None, owner: str | None = None
) -> CopilotSpaceResult:
    """Returns context from a Copilot space."""
    if not name or not owner:
        raise GitHubMockError("name and owner are required")
    key = f"{owner}/{name}"
    space = get_state().copilot_space(key)
    if space is None:
        raise GitHubMockError(f"Unknown Copilot space: {key}")
    return CopilotSpaceResult(space=space.model_copy(deep=True))


def github_list_copilot_spaces() -> ListCopilotSpacesResult:
    """Lists accessible Copilot spaces."""
    return ListCopilotSpacesResult(
        spaces=[s.model_copy(deep=True) for s in get_state().copilot_spaces]
    )


def github_request_copilot_review(
    repo: str | None = None, owner: str | None = None, pullNumber: int | None = None
) -> CopilotJobResult:
    """Requests an automated Copilot review on a PR."""
    if pullNumber is None:
        raise GitHubMockError("pullNumber is required")
    repository = _require_repo(owner, repo)
    pr = _require_pr(repository, pullNumber)
    job_id = f"cj_review_{repository.name}_{pullNumber}"
    job = CopilotJob(
        id=job_id,
        owner=repository.owner,
        repo=repository.name,
        status="queued",
        summary=pr.title,
        pull_request=pullNumber,
        created_at=_now_iso(),
        updated_at=_now_iso(),
    )
    get_state().copilot_jobs.append(job)
    if "github-copilot" not in pr.requested_reviewers:
        pr.requested_reviewers.append("github-copilot")
    pr.updated_at = _now_iso()
    return CopilotJobResult(job=job.model_copy())


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------


def github_get_job_logs(
    repo: str | None = None,
    owner: str | None = None,
    job_id: int | None = None,
) -> JobLogsResult:
    """Retrieves text logs for a specific workflow job."""
    if job_id is None:
        raise GitHubMockError("job_id is required")
    repository = _require_repo(owner, repo)
    if repository.workflow_job(job_id) is None:
        raise GitHubMockError(f"Unknown workflow job: {job_id}")
    log = repository.job_log(job_id)
    return JobLogsResult(job_id=job_id, logs=log.log if log else "")


def github_support_docs_search(query: str | None = None) -> DocSearchResult:
    """Mocked GitHub documentation search."""
    if not query:
        raise GitHubMockError("query is required")
    needle = query.lower()
    catalog = [
        DocSearchArticle(
            title="Mocked: GitHub REST overview",
            url="https://example.com/docs/rest",
            snippet="REST API basics.",
        ),
        DocSearchArticle(
            title="Mocked: Branch protection",
            url="https://example.com/docs/branches",
            snippet="Configure required reviews and checks.",
        ),
        DocSearchArticle(
            title="Mocked: Code scanning",
            url="https://example.com/docs/code-scanning",
            snippet="Enable CodeQL on a repository.",
        ),
        DocSearchArticle(
            title="Mocked: Copilot agent",
            url="https://example.com/docs/copilot",
            snippet="Delegate tasks to Copilot.",
        ),
    ]
    results = [
        a for a in catalog if needle in a.title.lower() or needle in a.snippet.lower()
    ] or catalog[:2]
    return DocSearchResult(query=query, results=results)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


_TOOL_DEFINITIONS: list[ToolDefinition] = [
    ToolDefinition(
        name="github_actions_get",
        callable=github_actions_get,
        description="Retrieves GitHub Actions resources (workflows, runs, jobs, artifacts).",
    ),
    ToolDefinition(
        name="github_actions_list",
        callable=github_actions_list,
        description="Lists GitHub Actions resources with filtering and pagination.",
    ),
    ToolDefinition(
        name="github_actions_run_trigger",
        callable=github_actions_run_trigger,
        description="Triggers workflow operations: run, rerun, cancel, delete logs.",
    ),
    ToolDefinition(
        name="github_add_comment_to_pending_review",
        callable=github_add_comment_to_pending_review,
        description="Adds a comment to a pending PR review draft.",
        required_fields=frozenset(
            {"repo", "owner", "pullNumber", "path", "line", "body", "side"}
        ),
    ),
    ToolDefinition(
        name="github_add_reply_to_pull_request_comment",
        callable=github_add_reply_to_pull_request_comment,
        description="Replies to a PR review comment.",
        required_fields=frozenset({"repo", "owner", "pullNumber", "commentId", "body"}),
    ),
    ToolDefinition(
        name="github_create_pull_request",
        callable=github_create_pull_request,
        description="Creates a new pull request.",
        required_fields=frozenset({"repo", "owner", "base", "head", "title"}),
    ),
    ToolDefinition(
        name="github_create_pull_request_with_copilot",
        callable=github_create_pull_request_with_copilot,
        description="Delegates implementation to GitHub Copilot.",
        required_fields=frozenset({"repo", "owner", "title", "problem_statement"}),
    ),
    ToolDefinition(
        name="github_merge_pull_request",
        callable=github_merge_pull_request,
        description="Merges a pull request.",
        required_fields=frozenset({"repo", "owner", "pullNumber"}),
    ),
    ToolDefinition(
        name="github_pull_request_read",
        callable=github_pull_request_read,
        description="Retrieves PR data and metadata via method dispatch.",
        required_fields=frozenset({"repo", "owner", "pullNumber"}),
    ),
    ToolDefinition(
        name="github_pull_request_review_write",
        callable=github_pull_request_review_write,
        description="Creates, submits, or deletes a PR review draft.",
        required_fields=frozenset({"repo", "owner", "pullNumber"}),
    ),
    ToolDefinition(
        name="github_update_pull_request",
        callable=github_update_pull_request,
        description="Modifies properties on an existing PR.",
        required_fields=frozenset({"repo", "owner", "pullNumber"}),
    ),
    ToolDefinition(
        name="github_update_pull_request_branch",
        callable=github_update_pull_request_branch,
        description="Syncs a PR branch with its base branch.",
        required_fields=frozenset({"repo", "owner", "pullNumber"}),
    ),
    ToolDefinition(
        name="github_list_pull_requests",
        callable=github_list_pull_requests,
        description="Lists pull requests with filtering.",
        required_fields=frozenset({"repo", "owner"}),
    ),
    ToolDefinition(
        name="github_add_issue_comment",
        callable=github_add_issue_comment,
        description="Posts a comment on an issue or PR.",
        required_fields=frozenset({"repo", "owner", "issue_number", "body"}),
    ),
    ToolDefinition(
        name="github_assign_copilot_to_issue",
        callable=github_assign_copilot_to_issue,
        description="Delegates issue resolution to a Copilot agent.",
        required_fields=frozenset({"repo", "owner", "issue_number"}),
    ),
    ToolDefinition(
        name="github_issue_read",
        callable=github_issue_read,
        description="Retrieves issue info via method dispatch.",
        required_fields=frozenset({"repo", "owner", "issue_number"}),
    ),
    ToolDefinition(
        name="github_issue_write",
        callable=github_issue_write,
        description="Creates or updates an issue.",
        required_fields=frozenset({"repo", "owner", "method"}),
    ),
    ToolDefinition(
        name="github_list_issues",
        callable=github_list_issues,
        description="Lists repository issues with filtering.",
        required_fields=frozenset({"repo", "owner"}),
    ),
    ToolDefinition(
        name="github_sub_issue_write",
        callable=github_sub_issue_write,
        description="Manages issue hierarchies.",
        required_fields=frozenset({"repo", "owner", "issue_number"}),
    ),
    ToolDefinition(
        name="github_triage_issue",
        callable=github_triage_issue,
        description="Triage-categorizes an issue.",
        required_fields=frozenset(
            {"repo", "owner", "issue_number", "triage_rationale"}
        ),
    ),
    ToolDefinition(
        name="github_list_issue_types",
        callable=github_list_issue_types,
        description="Lists organization issue types.",
        required_fields=frozenset({"owner"}),
    ),
    ToolDefinition(
        name="github_create_branch",
        callable=github_create_branch,
        description="Creates a new repository branch.",
        required_fields=frozenset({"repo", "owner", "branch"}),
    ),
    ToolDefinition(
        name="github_create_or_update_file",
        callable=github_create_or_update_file,
        description="Creates or updates a file with a commit.",
        required_fields=frozenset(
            {"repo", "owner", "path", "branch", "content", "message"}
        ),
    ),
    ToolDefinition(
        name="github_delete_file",
        callable=github_delete_file,
        description="Deletes a file from a branch.",
        required_fields=frozenset({"repo", "owner", "path", "branch", "message"}),
    ),
    ToolDefinition(
        name="github_get_file_contents",
        callable=github_get_file_contents,
        description="Retrieves a file or directory listing.",
        required_fields=frozenset({"repo", "owner"}),
    ),
    ToolDefinition(
        name="github_get_repository_tree",
        callable=github_get_repository_tree,
        description="Retrieves the repository file tree.",
        required_fields=frozenset({"repo", "owner"}),
    ),
    ToolDefinition(
        name="github_push_files",
        callable=github_push_files,
        description="Commits multiple files in one operation.",
        required_fields=frozenset({"repo", "owner", "branch", "message", "files"}),
    ),
    ToolDefinition(
        name="github_search_code",
        callable=github_search_code,
        description="Searches code across mocked repositories.",
        required_fields=frozenset({"query"}),
    ),
    ToolDefinition(
        name="github_create_repository",
        callable=github_create_repository,
        description="Creates a new repository.",
        required_fields=frozenset({"name"}),
    ),
    ToolDefinition(
        name="github_fork_repository",
        callable=github_fork_repository,
        description="Forks a repository.",
        required_fields=frozenset({"repo", "owner"}),
    ),
    ToolDefinition(
        name="github_star_repository",
        callable=github_star_repository,
        description="Stars a repository.",
        required_fields=frozenset({"repo", "owner"}),
    ),
    ToolDefinition(
        name="github_unstar_repository",
        callable=github_unstar_repository,
        description="Removes a repository's star.",
        required_fields=frozenset({"repo", "owner"}),
    ),
    ToolDefinition(
        name="github_list_starred_repositories",
        callable=github_list_starred_repositories,
        description="Lists the user's starred repositories.",
    ),
    ToolDefinition(
        name="github_get_latest_release",
        callable=github_get_latest_release,
        description="Returns the latest release for a repository.",
        required_fields=frozenset({"repo", "owner"}),
    ),
    ToolDefinition(
        name="github_dismiss_notification",
        callable=github_dismiss_notification,
        description="Marks a notification as read or done.",
        required_fields=frozenset({"threadID", "state"}),
    ),
    ToolDefinition(
        name="github_get_notification_details",
        callable=github_get_notification_details,
        description="Retrieves notification details.",
        required_fields=frozenset({"notificationID"}),
    ),
    ToolDefinition(
        name="github_list_notifications",
        callable=github_list_notifications,
        description="Lists notifications with filtering.",
    ),
    ToolDefinition(
        name="github_manage_notification_subscription",
        callable=github_manage_notification_subscription,
        description="Controls a notification thread subscription.",
        required_fields=frozenset({"notificationID", "action"}),
    ),
    ToolDefinition(
        name="github_manage_repository_notification_subscription",
        callable=github_manage_repository_notification_subscription,
        description="Controls a repository's notification subscription.",
        required_fields=frozenset({"repo", "owner", "action"}),
    ),
    ToolDefinition(
        name="github_mark_all_notifications_read",
        callable=github_mark_all_notifications_read,
        description="Marks notifications as read.",
    ),
    ToolDefinition(
        name="github_get_code_scanning_alert",
        callable=github_get_code_scanning_alert,
        description="Retrieves a code scanning alert.",
        required_fields=frozenset({"repo", "owner", "alertNumber"}),
    ),
    ToolDefinition(
        name="github_list_code_scanning_alerts",
        callable=github_list_code_scanning_alerts,
        description="Lists code scanning alerts.",
        required_fields=frozenset({"repo", "owner"}),
    ),
    ToolDefinition(
        name="github_get_dependabot_alert",
        callable=github_get_dependabot_alert,
        description="Retrieves a Dependabot alert.",
        required_fields=frozenset({"repo", "owner", "alertNumber"}),
    ),
    ToolDefinition(
        name="github_list_dependabot_alerts",
        callable=github_list_dependabot_alerts,
        description="Lists Dependabot alerts.",
        required_fields=frozenset({"repo", "owner"}),
    ),
    ToolDefinition(
        name="github_get_secret_scanning_alert",
        callable=github_get_secret_scanning_alert,
        description="Retrieves a secret scanning alert.",
        required_fields=frozenset({"repo", "owner", "alertNumber"}),
    ),
    ToolDefinition(
        name="github_list_secret_scanning_alerts",
        callable=github_list_secret_scanning_alerts,
        description="Lists secret scanning alerts.",
        required_fields=frozenset({"repo", "owner"}),
    ),
    ToolDefinition(
        name="github_run_secret_scanning",
        callable=github_run_secret_scanning,
        description="Runs an ad-hoc secret scan over supplied content.",
        required_fields=frozenset({"repo", "owner", "files"}),
    ),
    ToolDefinition(
        name="github_get_release_by_tag",
        callable=github_get_release_by_tag,
        description="Retrieves a release by tag name.",
        required_fields=frozenset({"repo", "owner", "tag"}),
    ),
    ToolDefinition(
        name="github_list_releases",
        callable=github_list_releases,
        description="Lists releases.",
        required_fields=frozenset({"repo", "owner"}),
    ),
    ToolDefinition(
        name="github_get_tag",
        callable=github_get_tag,
        description="Retrieves tag metadata.",
        required_fields=frozenset({"repo", "owner", "tag"}),
    ),
    ToolDefinition(
        name="github_list_tags",
        callable=github_list_tags,
        description="Lists repository tags.",
        required_fields=frozenset({"repo", "owner"}),
    ),
    ToolDefinition(
        name="github_get_commit",
        callable=github_get_commit,
        description="Retrieves a commit by SHA.",
        required_fields=frozenset({"repo", "owner", "sha"}),
    ),
    ToolDefinition(
        name="github_list_commits",
        callable=github_list_commits,
        description="Lists commits with filtering.",
        required_fields=frozenset({"repo", "owner"}),
    ),
    ToolDefinition(
        name="github_get_discussion",
        callable=github_get_discussion,
        description="Retrieves a discussion.",
        required_fields=frozenset({"repo", "owner", "discussionNumber"}),
    ),
    ToolDefinition(
        name="github_get_discussion_comments",
        callable=github_get_discussion_comments,
        description="Retrieves discussion comments.",
        required_fields=frozenset({"repo", "owner", "discussionNumber"}),
    ),
    ToolDefinition(
        name="github_list_discussions",
        callable=github_list_discussions,
        description="Lists discussions with filtering.",
    ),
    ToolDefinition(
        name="github_list_discussion_categories",
        callable=github_list_discussion_categories,
        description="Lists discussion categories.",
        required_fields=frozenset({"repo", "owner"}),
    ),
    ToolDefinition(
        name="github_create_gist",
        callable=github_create_gist,
        description="Creates a gist.",
        required_fields=frozenset({"content", "filename"}),
    ),
    ToolDefinition(
        name="github_get_gist",
        callable=github_get_gist,
        description="Retrieves a gist.",
        required_fields=frozenset({"gist_id"}),
    ),
    ToolDefinition(
        name="github_list_gists", callable=github_list_gists, description="Lists gists."
    ),
    ToolDefinition(
        name="github_update_gist",
        callable=github_update_gist,
        description="Updates a gist.",
        required_fields=frozenset({"gist_id", "filename", "content"}),
    ),
    ToolDefinition(
        name="github_search_issues",
        callable=github_search_issues,
        description="Searches issues across mocked repositories.",
    ),
    ToolDefinition(
        name="github_search_pull_requests",
        callable=github_search_pull_requests,
        description="Searches pull requests.",
    ),
    ToolDefinition(
        name="github_search_repositories",
        callable=github_search_repositories,
        description="Searches repositories.",
        required_fields=frozenset({"query"}),
    ),
    ToolDefinition(
        name="github_search_users",
        callable=github_search_users,
        description="Searches users.",
        required_fields=frozenset({"query"}),
    ),
    ToolDefinition(
        name="github_search_orgs",
        callable=github_search_orgs,
        description="Searches organizations.",
        required_fields=frozenset({"query"}),
    ),
    ToolDefinition(
        name="github_get_label",
        callable=github_get_label,
        description="Retrieves a repository label.",
        required_fields=frozenset({"repo", "owner", "name"}),
    ),
    ToolDefinition(
        name="github_list_label",
        callable=github_list_label,
        description="Lists repository labels.",
        required_fields=frozenset({"repo", "owner"}),
    ),
    ToolDefinition(
        name="github_label_write",
        callable=github_label_write,
        description="Creates, updates, or deletes a repository label.",
        required_fields=frozenset({"repo", "owner", "method", "name"}),
    ),
    ToolDefinition(
        name="github_get_global_security_advisory",
        callable=github_get_global_security_advisory,
        description="Retrieves a global security advisory.",
        required_fields=frozenset({"ghsaId"}),
    ),
    ToolDefinition(
        name="github_list_global_security_advisories",
        callable=github_list_global_security_advisories,
        description="Lists global security advisories with filters.",
    ),
    ToolDefinition(
        name="github_list_repository_security_advisories",
        callable=github_list_repository_security_advisories,
        description="Lists repository-specific security advisories.",
        required_fields=frozenset({"repo", "owner"}),
    ),
    ToolDefinition(
        name="github_list_org_repository_security_advisories",
        callable=github_list_org_repository_security_advisories,
        description="Lists organizational security advisories.",
        required_fields=frozenset({"org"}),
    ),
    ToolDefinition(
        name="github_projects_get",
        callable=github_projects_get,
        description="Retrieves project resources via method dispatch.",
    ),
    ToolDefinition(
        name="github_projects_list",
        callable=github_projects_list,
        description="Lists project resources via method dispatch.",
    ),
    ToolDefinition(
        name="github_projects_write",
        callable=github_projects_write,
        description="Modifies project items or status updates.",
    ),
    ToolDefinition(
        name="github_get_me",
        callable=github_get_me,
        description="Returns the authenticated mock user's profile.",
    ),
    ToolDefinition(
        name="github_get_teams",
        callable=github_get_teams,
        description="Lists team memberships for a user.",
    ),
    ToolDefinition(
        name="github_get_team_members",
        callable=github_get_team_members,
        description="Lists members of an organization team.",
        required_fields=frozenset({"org", "team_slug"}),
    ),
    ToolDefinition(
        name="github_list_branches",
        callable=github_list_branches,
        description="Lists branches in a repository.",
        required_fields=frozenset({"repo", "owner"}),
    ),
    ToolDefinition(
        name="github_get_copilot_job_status",
        callable=github_get_copilot_job_status,
        description="Retrieves a Copilot job's status.",
        required_fields=frozenset({"id", "repo", "owner"}),
    ),
    ToolDefinition(
        name="github_get_copilot_space",
        callable=github_get_copilot_space,
        description="Retrieves a Copilot space.",
        required_fields=frozenset({"name", "owner"}),
    ),
    ToolDefinition(
        name="github_list_copilot_spaces",
        callable=github_list_copilot_spaces,
        description="Lists accessible Copilot spaces.",
    ),
    ToolDefinition(
        name="github_request_copilot_review",
        callable=github_request_copilot_review,
        description="Requests a Copilot-driven review on a PR.",
        required_fields=frozenset({"repo", "owner", "pullNumber"}),
    ),
    ToolDefinition(
        name="github_get_job_logs",
        callable=github_get_job_logs,
        description="Retrieves logs for a workflow job.",
        required_fields=frozenset({"repo", "owner", "job_id"}),
    ),
    ToolDefinition(
        name="github_support_docs_search",
        callable=github_support_docs_search,
        description="Searches mocked GitHub documentation.",
        required_fields=frozenset({"query"}),
    ),
]


TOOL_REGISTRY: dict[str, ToolSpec] = build_tool_registry(
    service="github",
    definitions=_TOOL_DEFINITIONS,
)


def get_tool_registry() -> dict[str, ToolSpec]:
    return TOOL_REGISTRY


__all__ = [
    "GitHubFileEntry",
    "GitHubMockError",
    "TOOL_REGISTRY",
    "get_tool_registry",
    "reset_github_mock_state",
] + sorted(d.name for d in _TOOL_DEFINITIONS)
