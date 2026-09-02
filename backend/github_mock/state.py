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


class GitHubUser(BaseModel):
    model_config = ConfigDict(extra="forbid")

    login: str
    id: int
    name: str
    email: str | None
    type: str = "User"
    html_url: str


class GitHubLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    color: str
    description: str


class CommitPerson(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    date: str


class CommitMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    author: CommitPerson
    committer: CommitPerson


class CommitParent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sha: str


class GitHubCommit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sha: str
    commit: CommitMessage
    author: str
    parents: list[CommitParent]
    diff: str


class GitHubBranch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    commit_sha: str
    protected: bool


class GitHubFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    content: str
    sha: str
    size: int
    type: str = "file"


class BranchFiles(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branch: str
    files: list[GitHubFile]


class GitHubIssue(BaseModel):
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


class IssueComment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    user: str
    body: str
    created_at: str
    updated_at: str


class IssueCommentLog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue_number: int
    comments: list[IssueComment]


class PullRequest(BaseModel):
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


class PRReviewComment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    user: str
    body: str
    path: str
    line: int
    side: str
    in_reply_to_id: int | None
    pull_number: int
    created_at: str
    updated_at: str


class PRReviewCommentLog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pull_number: int
    comments: list[PRReviewComment]


class PRIssueCommentLog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pull_number: int
    comments: list[IssueComment]


class PRReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    user: str
    state: str
    body: str
    submitted_at: str


class PRReviewLog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pull_number: int
    reviews: list[PRReview]


class PRPendingReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pull_number: int
    user: str
    body: str
    comments: list[PRReviewComment] = Field(default_factory=list)


class CheckRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    status: str
    conclusion: str


class PRCheckRunLog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pull_number: int
    checks: list[CheckRun]


class GitHubTag(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    commit_sha: str
    tagger: str
    tagged_at: str


class GitHubRelease(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    tag_name: str
    name: str
    body: str
    draft: bool
    prerelease: bool
    created_at: str
    published_at: str
    assets: list[str] = Field(default_factory=list)


class DiscussionCategory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    slug: str
    emoji: str


class DiscussionComment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    user: str
    body: str
    created_at: str


class Discussion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: int
    title: str
    body: str
    category: str
    user: str
    created_at: str
    updated_at: str
    comments: list[DiscussionComment]


class Workflow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    path: str
    state: str


class WorkflowRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    workflow_id: int
    name: str
    status: str
    conclusion: str
    head_branch: str
    head_sha: str
    created_at: str
    updated_at: str


class WorkflowJob(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    run_id: int
    name: str
    status: str
    conclusion: str


class WorkflowArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    run_id: int
    name: str
    size_in_bytes: int
    expired: bool


class JobLog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: int
    log: str


class SecurityAlert(BaseModel):
    """A unified alert envelope covering code scanning / dependabot / secret scanning."""

    model_config = ConfigDict(extra="forbid")

    number: int
    severity: str
    state: str
    summary: str
    created_at: str
    updated_at: str
    tool_name: str | None = None
    ref: str | None = None
    ecosystem: str | None = None
    secret_type: str | None = None
    resolution: str | None = None


class SecurityAdvisory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ghsa_id: str
    summary: str
    severity: str
    state: str
    published_at: str


class ProjectField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    options: list[str]


class ProjectItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    type: str
    issue_number: int
    status: str
    priority: str


class ProjectStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    body: str
    created_at: str


class GitHubProject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    title: str
    fields: list[ProjectField]
    items: list[ProjectItem]
    status_updates: list[ProjectStatusUpdate]


class Subscription(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subscribed: bool
    ignored: bool
    reason: str


class RepoCounters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    next_number: int
    comment: int = 5000
    review: int = 60000
    release: int = 1
    discussion: int = 1
    alert: int = 100
    project_item: int = 8000


class GitHubRepo(BaseModel):
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
    branches: list[GitHubBranch]
    commits: list[GitHubCommit]
    files: list[BranchFiles]
    issues: list[GitHubIssue]
    issue_comments: list[IssueCommentLog]
    pulls: list[PullRequest]
    pr_issue_comments: list[PRIssueCommentLog]
    pr_review_comments: list[PRReviewCommentLog]
    pr_reviews: list[PRReviewLog]
    pr_pending_reviews: list[PRPendingReview] = Field(default_factory=list)
    pr_check_runs: list[PRCheckRunLog]
    labels: list[GitHubLabel]
    tags: list[GitHubTag]
    releases: list[GitHubRelease]
    discussion_categories: list[DiscussionCategory]
    discussions: list[Discussion]
    workflows: list[Workflow]
    workflow_runs: list[WorkflowRun]
    workflow_jobs: list[WorkflowJob]
    workflow_artifacts: list[WorkflowArtifact]
    job_logs: list[JobLog]
    code_scanning: list[SecurityAlert]
    dependabot: list[SecurityAlert]
    secret_scanning: list[SecurityAlert]
    security_advisories: list[SecurityAdvisory]
    projects: list[GitHubProject]
    subscription: Subscription
    counters: RepoCounters

    # ----- lookups ---------------------------------------------------------

    def branch(self, name: str) -> GitHubBranch | None:
        return next((b for b in self.branches if b.name == name), None)

    def commit(self, sha: str) -> GitHubCommit | None:
        return next((c for c in self.commits if c.sha == sha), None)

    def branch_files(self, branch: str) -> BranchFiles:
        existing = next((f for f in self.files if f.branch == branch), None)
        if existing is None:
            existing = BranchFiles(branch=branch, files=[])
            self.files.append(existing)
        return existing

    def file(self, branch: str, path: str) -> GitHubFile | None:
        log = next((f for f in self.files if f.branch == branch), None)
        if log is None:
            return None
        return next((file for file in log.files if file.path == path), None)

    def issue(self, number: int) -> GitHubIssue | None:
        return next((i for i in self.issues if i.number == number), None)

    def pull(self, number: int) -> PullRequest | None:
        return next((p for p in self.pulls if p.number == number), None)

    def issue_comment_log(self, issue_number: int) -> IssueCommentLog:
        existing = next(
            (c for c in self.issue_comments if c.issue_number == issue_number), None
        )
        if existing is None:
            existing = IssueCommentLog(issue_number=issue_number, comments=[])
            self.issue_comments.append(existing)
        return existing

    def pr_review_comment_log(self, pull_number: int) -> PRReviewCommentLog:
        existing = next(
            (c for c in self.pr_review_comments if c.pull_number == pull_number), None
        )
        if existing is None:
            existing = PRReviewCommentLog(pull_number=pull_number, comments=[])
            self.pr_review_comments.append(existing)
        return existing

    def pr_issue_comment_log(self, pull_number: int) -> PRIssueCommentLog:
        existing = next(
            (c for c in self.pr_issue_comments if c.pull_number == pull_number), None
        )
        if existing is None:
            existing = PRIssueCommentLog(pull_number=pull_number, comments=[])
            self.pr_issue_comments.append(existing)
        return existing

    def pr_review_log(self, pull_number: int) -> PRReviewLog:
        existing = next(
            (r for r in self.pr_reviews if r.pull_number == pull_number), None
        )
        if existing is None:
            existing = PRReviewLog(pull_number=pull_number, reviews=[])
            self.pr_reviews.append(existing)
        return existing

    def pr_check_log(self, pull_number: int) -> PRCheckRunLog:
        existing = next(
            (c for c in self.pr_check_runs if c.pull_number == pull_number), None
        )
        if existing is None:
            existing = PRCheckRunLog(pull_number=pull_number, checks=[])
            self.pr_check_runs.append(existing)
        return existing

    def pr_pending_review(self, pull_number: int, user: str) -> PRPendingReview | None:
        return next(
            (
                p
                for p in self.pr_pending_reviews
                if p.pull_number == pull_number and p.user == user
            ),
            None,
        )

    def workflow(self, workflow_id: int) -> Workflow | None:
        return next((w for w in self.workflows if w.id == workflow_id), None)

    def workflow_run(self, run_id: int) -> WorkflowRun | None:
        return next((r for r in self.workflow_runs if r.id == run_id), None)

    def workflow_job(self, job_id: int) -> WorkflowJob | None:
        return next((j for j in self.workflow_jobs if j.id == job_id), None)

    def workflow_artifact(self, artifact_id: int) -> WorkflowArtifact | None:
        return next((a for a in self.workflow_artifacts if a.id == artifact_id), None)

    def job_log(self, job_id: int) -> JobLog | None:
        return next((l for l in self.job_logs if l.job_id == job_id), None)

    def label(self, name: str) -> GitHubLabel | None:
        return next((l for l in self.labels if l.name == name), None)

    def discussion(self, number: int) -> Discussion | None:
        return next((d for d in self.discussions if d.number == number), None)

    def project(self, project_id: int) -> GitHubProject | None:
        return next((p for p in self.projects if p.id == project_id), None)

    def release_by_tag(self, tag: str) -> GitHubRelease | None:
        return next((r for r in self.releases if r.tag_name == tag), None)

    def tag(self, name: str) -> GitHubTag | None:
        return next((t for t in self.tags if t.name == name), None)


class IssueType(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str


class GitHubOrg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    login: str
    id: int
    description: str
    html_url: str
    type: str = "Organization"
    issue_types: list[IssueType]


class GitHubTeam(BaseModel):
    model_config = ConfigDict(extra="forbid")

    org: str
    slug: str
    name: str
    description: str
    members: list[str]


class NotificationSubject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    url: str
    type: str


class Notification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thread_id: str
    id: str
    subject: NotificationSubject
    repository: str
    reason: str
    unread: bool
    updated_at: str


class GlobalAdvisory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ghsa_id: str
    cve_id: str
    summary: str
    severity: str
    ecosystem: str
    cwes: list[str]
    published_at: str


class GistFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str
    content: str
    language: str


class GistFileEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    file: GistFile


class Gist(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    description: str
    public: bool
    owner: str
    files: list[GistFileEntry]
    html_url: str
    created_at: str
    updated_at: str


class CopilotJob(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    owner: str
    repo: str
    status: str
    summary: str
    pull_request: int
    created_at: str
    updated_at: str


class CopilotSpace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    name: str
    owner: str
    description: str
    files: list[str]
    summary: str


class GitHubCounters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gist: int = 100
    notification: int = 200000


class GitHubState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    me: GitHubUser
    users: list[GitHubUser]
    orgs: list[GitHubOrg]
    teams: list[GitHubTeam]
    repos: list[GitHubRepo]
    starred: list[str]
    notifications: list[Notification]
    global_advisories: list[GlobalAdvisory]
    gists: list[Gist]
    copilot_jobs: list[CopilotJob]
    copilot_spaces: list[CopilotSpace]
    counters: GitHubCounters = Field(default_factory=GitHubCounters)

    # ----- lookups ---------------------------------------------------------

    def user(self, login: str) -> GitHubUser | None:
        return next((u for u in self.users if u.login == login), None)

    def org(self, login: str) -> GitHubOrg | None:
        return next((o for o in self.orgs if o.login == login), None)

    def repo(self, owner: str, name: str) -> GitHubRepo | None:
        full = f"{owner}/{name}"
        return next((r for r in self.repos if r.full_name == full), None)

    def team(self, org: str, slug: str) -> GitHubTeam | None:
        return next((t for t in self.teams if t.org == org and t.slug == slug), None)

    def notification(self, thread_id: str) -> Notification | None:
        return next((n for n in self.notifications if n.thread_id == thread_id), None)

    def gist(self, gist_id: str) -> Gist | None:
        return next((g for g in self.gists if g.id == gist_id), None)

    def copilot_job(self, job_id: str) -> CopilotJob | None:
        return next((j for j in self.copilot_jobs if j.id == job_id), None)

    def copilot_space(self, key: str) -> CopilotSpace | None:
        return next((s for s in self.copilot_spaces if s.key == key), None)


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _make_user(
    login: str, *, name: str, email: str, identifier: int, type: str = "User"
) -> GitHubUser:
    return GitHubUser(
        login=login,
        id=identifier,
        name=name,
        email=email,
        type=type,
        html_url=f"https://github.com/{login}",
    )


def _make_commit(
    *, sha: str, message: str, author: str, parents: list[str], offset_minutes: int
) -> GitHubCommit:
    return GitHubCommit(
        sha=sha,
        commit=CommitMessage(
            message=message,
            author=CommitPerson(name=author, date=_iso(offset_minutes)),
            committer=CommitPerson(name=author, date=_iso(offset_minutes)),
        ),
        author=author,
        parents=[CommitParent(sha=p) for p in parents],
        diff=(
            f"diff --git a/CHANGELOG.md b/CHANGELOG.md\n"
            f"--- a/CHANGELOG.md\n+++ b/CHANGELOG.md\n@@\n+ {message}\n"
        ),
    )


def _make_alert(
    *,
    number: int,
    severity: str,
    state: str,
    summary: str,
    tool_name: str | None = None,
    ref: str | None = None,
    ecosystem: str | None = None,
    secret_type: str | None = None,
    resolution: str | None = None,
) -> SecurityAlert:
    return SecurityAlert(
        number=number,
        severity=severity,
        state=state,
        summary=summary,
        created_at=_iso(-60 * 24 * 7),
        updated_at=_iso(-60 * 24 * 1),
        tool_name=tool_name,
        ref=ref,
        ecosystem=ecosystem,
        secret_type=secret_type,
        resolution=resolution,
    )


def _seed_repo(
    *,
    owner: str,
    name: str,
    description: str,
    default_branch: str,
    private: bool,
    visibility: str,
) -> GitHubRepo:
    full_name = f"{owner}/{name}"
    main_sha = f"sha_{name}_main"
    feature_sha = f"sha_{name}_feature"
    branches = [
        GitHubBranch(name=default_branch, commit_sha=main_sha, protected=True),
        GitHubBranch(name="develop", commit_sha=main_sha, protected=False),
    ]
    if name == "orchestrator":
        branches.append(
            GitHubBranch(name="feature/router", commit_sha=feature_sha, protected=False)
        )

    commits = [
        _make_commit(
            sha=main_sha,
            message=f"chore({name}): initial commit",
            author="avery",
            parents=[],
            offset_minutes=-60 * 24 * 7,
        ),
        _make_commit(
            sha=feature_sha,
            message=f"feat({name}): tool router prototype",
            author="morgan",
            parents=[main_sha],
            offset_minutes=-60 * 12,
        ),
    ]

    files: list[BranchFiles] = [
        BranchFiles(
            branch=default_branch,
            files=[
                GitHubFile(
                    path="README.md",
                    content=f"# {full_name}\n\n{description}\n",
                    sha=f"sha_{name}_readme",
                    size=80,
                ),
                GitHubFile(
                    path="src/main.py",
                    content=f"def main():\n    print('hello from {name}')\n",
                    sha=f"sha_{name}_src_main",
                    size=64,
                ),
            ],
        ),
        BranchFiles(
            branch="develop",
            files=[
                GitHubFile(
                    path="README.md",
                    content=f"# {full_name} (develop)\n",
                    sha=f"sha_{name}_readme_dev",
                    size=40,
                ),
            ],
        ),
    ]
    if name == "orchestrator":
        files.append(
            BranchFiles(
                branch="feature/router",
                files=[
                    GitHubFile(
                        path="src/router.py",
                        content="# routing prototype\n",
                        sha=f"sha_{name}_router",
                        size=32,
                    )
                ],
            )
        )

    issues = [
        GitHubIssue(
            number=1,
            title=f"[{name}] Tool routing strategy",
            body="Decide between two-stage routing or semantic retrieval for 191 tools.",
            state="open",
            state_reason=None,
            labels=["enhancement", "discussion"],
            assignees=["avery"],
            milestone=None,
            type="Feature",
            user="avery",
            comments_count=1,
            sub_issues=[2],
            created_at=_iso(-60 * 24 * 6),
            updated_at=_iso(-60 * 4),
            html_url=f"https://github.com/{full_name}/issues/1",
        ),
        GitHubIssue(
            number=2,
            title=f"[{name}] Add tool latency dashboard",
            body="Per-tool latency, error rate, and call count.",
            state="open",
            state_reason=None,
            labels=["enhancement"],
            assignees=[],
            milestone=None,
            type="Task",
            user="morgan",
            comments_count=0,
            sub_issues=[],
            created_at=_iso(-60 * 24 * 3),
            updated_at=_iso(-60 * 24 * 3),
            html_url=f"https://github.com/{full_name}/issues/2",
        ),
        GitHubIssue(
            number=3,
            title=f"[{name}] Launch delay: cold start regression",
            body="Cold start regressed from 1.1s to 3.4s after dependency bump.",
            state="closed",
            state_reason="completed",
            labels=["bug"],
            assignees=["avery"],
            milestone=None,
            type="Bug",
            user="jordan",
            comments_count=2,
            sub_issues=[],
            created_at=_iso(-60 * 24 * 14),
            updated_at=_iso(-60 * 24 * 8),
            closed_at=_iso(-60 * 24 * 8),
            closed_by_pr=5,
            html_url=f"https://github.com/{full_name}/issues/3",
        ),
    ]

    issue_comments = [
        IssueCommentLog(
            issue_number=1,
            comments=[
                IssueComment(
                    id=1001,
                    user="morgan",
                    body="Leaning two-stage. Cheaper at routing time, easier to reason about.",
                    created_at=_iso(-60 * 6),
                    updated_at=_iso(-60 * 6),
                ),
            ],
        ),
        IssueCommentLog(issue_number=2, comments=[]),
        IssueCommentLog(
            issue_number=3,
            comments=[
                IssueComment(
                    id=1101,
                    user="avery",
                    body="Bisected to commit feature/router. Reverting.",
                    created_at=_iso(-60 * 24 * 9),
                    updated_at=_iso(-60 * 24 * 9),
                ),
                IssueComment(
                    id=1102,
                    user="jordan",
                    body="Closed by #5.",
                    created_at=_iso(-60 * 24 * 8),
                    updated_at=_iso(-60 * 24 * 8),
                ),
            ],
        ),
    ]

    pulls = [
        PullRequest(
            number=4,
            title=f"[{name}] Tool router prototype",
            body="Initial pass at the routing layer. Closes #1 once we land it.",
            state="open",
            draft=False,
            head="feature/router" if name == "orchestrator" else "develop",
            base=default_branch,
            user="morgan",
            merge_method_preferred="squash",
            merged=False,
            mergeable_state="clean",
            labels=["enhancement"],
            assignees=["avery"],
            requested_reviewers=["jordan"],
            comments_count=1,
            review_comments_count=0,
            commits_count=1,
            additions=80,
            deletions=4,
            changed_files=2,
            created_at=_iso(-60 * 12),
            updated_at=_iso(-60 * 1),
            html_url=f"https://github.com/{full_name}/pull/4",
        ),
        PullRequest(
            number=5,
            title=f"[{name}] Fix cold start regression",
            body="Reverts dependency bump that caused cold-start spike. Closes #3.",
            state="closed",
            draft=False,
            head="develop",
            base=default_branch,
            user="avery",
            merge_method_preferred="merge",
            merged=True,
            mergeable_state="unknown",
            labels=["bug"],
            assignees=["avery"],
            requested_reviewers=[],
            comments_count=0,
            review_comments_count=1,
            commits_count=1,
            additions=12,
            deletions=18,
            changed_files=1,
            created_at=_iso(-60 * 24 * 9),
            updated_at=_iso(-60 * 24 * 8),
            merged_at=_iso(-60 * 24 * 8),
            html_url=f"https://github.com/{full_name}/pull/5",
        ),
    ]

    return GitHubRepo(
        owner=owner,
        name=name,
        full_name=full_name,
        description=description,
        default_branch=default_branch,
        private=private,
        visibility=visibility,
        html_url=f"https://github.com/{full_name}",
        stars=12,
        forks=1,
        topics=["ai", "tooling", "agents"],
        branches=branches,
        commits=commits,
        files=files,
        issues=issues,
        issue_comments=issue_comments,
        pulls=pulls,
        pr_issue_comments=[
            PRIssueCommentLog(
                pull_number=4,
                comments=[
                    IssueComment(
                        id=4001,
                        user="jordan",
                        body="Will review tomorrow.",
                        created_at=_iso(-60 * 6),
                        updated_at=_iso(-60 * 6),
                    ),
                ],
            ),
            PRIssueCommentLog(pull_number=5, comments=[]),
        ],
        pr_review_comments=[
            PRReviewCommentLog(pull_number=4, comments=[]),
            PRReviewCommentLog(
                pull_number=5,
                comments=[
                    PRReviewComment(
                        id=5001,
                        user="morgan",
                        body="LGTM",
                        path="src/main.py",
                        line=4,
                        side="RIGHT",
                        in_reply_to_id=None,
                        pull_number=5,
                        created_at=_iso(-60 * 24 * 8),
                        updated_at=_iso(-60 * 24 * 8),
                    ),
                ],
            ),
        ],
        pr_reviews=[
            PRReviewLog(pull_number=4, reviews=[]),
            PRReviewLog(
                pull_number=5,
                reviews=[
                    PRReview(
                        id=50001,
                        user="morgan",
                        state="APPROVED",
                        body="Approved.",
                        submitted_at=_iso(-60 * 24 * 8),
                    ),
                ],
            ),
        ],
        pr_pending_reviews=[],
        pr_check_runs=[
            PRCheckRunLog(
                pull_number=4,
                checks=[
                    CheckRun(
                        id=7001,
                        name="ci/lint",
                        status="completed",
                        conclusion="success",
                    ),
                    CheckRun(
                        id=7002,
                        name="ci/test",
                        status="completed",
                        conclusion="success",
                    ),
                ],
            ),
            PRCheckRunLog(
                pull_number=5,
                checks=[
                    CheckRun(
                        id=7101,
                        name="ci/lint",
                        status="completed",
                        conclusion="success",
                    ),
                    CheckRun(
                        id=7102,
                        name="ci/test",
                        status="completed",
                        conclusion="success",
                    ),
                ],
            ),
        ],
        labels=[
            GitHubLabel(name="enhancement", color="0e8a16", description="New features"),
            GitHubLabel(
                name="bug", color="d73a4a", description="Something isn't working"
            ),
            GitHubLabel(
                name="discussion", color="cccccc", description="Decision discussion"
            ),
        ],
        tags=[
            GitHubTag(
                name="v1.0.0",
                commit_sha=main_sha,
                tagger="avery",
                tagged_at=_iso(-60 * 24 * 21),
            )
        ],
        releases=[
            GitHubRelease(
                id=1,
                tag_name="v1.0.0",
                name="1.0.0",
                body="Initial release.",
                draft=False,
                prerelease=False,
                created_at=_iso(-60 * 24 * 21),
                published_at=_iso(-60 * 24 * 21),
            )
        ],
        discussion_categories=[
            DiscussionCategory(id=1, name="General", slug="general", emoji="💬"),
            DiscussionCategory(id=2, name="Q&A", slug="q-a", emoji="🙏"),
        ],
        discussions=[
            Discussion(
                number=1,
                title=f"[{name}] Q3 launch retro thread",
                body="Share what worked, what didn't, and the one change for Q4.",
                category="General",
                user="avery",
                created_at=_iso(-60 * 24 * 9),
                updated_at=_iso(-60 * 24 * 7),
                comments=[
                    DiscussionComment(
                        id=9001,
                        user="morgan",
                        body="Routing decision needs to land before Q4.",
                        created_at=_iso(-60 * 24 * 8),
                    )
                ],
            )
        ],
        workflows=[
            Workflow(
                id=100, name="CI", path=".github/workflows/ci.yml", state="active"
            ),
            Workflow(
                id=101,
                name="Release",
                path=".github/workflows/release.yml",
                state="active",
            ),
        ],
        workflow_runs=[
            WorkflowRun(
                id=9001,
                workflow_id=100,
                name="CI",
                status="completed",
                conclusion="success",
                head_branch=default_branch,
                head_sha=main_sha,
                created_at=_iso(-60 * 6),
                updated_at=_iso(-60 * 5),
            ),
            WorkflowRun(
                id=9002,
                workflow_id=101,
                name="Release",
                status="completed",
                conclusion="failure",
                head_branch=default_branch,
                head_sha=main_sha,
                created_at=_iso(-60 * 24 * 1),
                updated_at=_iso(-60 * 24 * 1 + 30),
            ),
        ],
        workflow_jobs=[
            WorkflowJob(
                id=80001,
                run_id=9001,
                name="lint",
                status="completed",
                conclusion="success",
            ),
            WorkflowJob(
                id=80002,
                run_id=9001,
                name="test",
                status="completed",
                conclusion="success",
            ),
            WorkflowJob(
                id=80003,
                run_id=9002,
                name="publish",
                status="completed",
                conclusion="failure",
            ),
        ],
        workflow_artifacts=[
            WorkflowArtifact(
                id=70001,
                run_id=9001,
                name="test-output",
                size_in_bytes=2048,
                expired=False,
            ),
        ],
        job_logs=[
            JobLog(
                job_id=80003,
                log="Step 'publish' failed: missing NPM_TOKEN. Re-run after rotating secret.",
            ),
            JobLog(job_id=80001, log="lint: ok\n"),
            JobLog(job_id=80002, log="test: 36 passed, 0 failed\n"),
        ],
        code_scanning=[
            _make_alert(
                number=11,
                severity="medium",
                state="open",
                summary="Use of eval() detected",
                tool_name="codeql",
                ref=f"refs/heads/{default_branch}",
            )
        ],
        dependabot=[
            _make_alert(
                number=21,
                severity="high",
                state="open",
                summary="Vulnerable dependency: starlette < 0.36",
                ecosystem="pip",
            )
        ],
        secret_scanning=[
            _make_alert(
                number=31,
                severity="critical",
                state="resolved",
                summary="OpenAI API key found in commit log",
                secret_type="openai_api_key",
                resolution="revoked",
            )
        ],
        security_advisories=[
            SecurityAdvisory(
                ghsa_id=f"GHSA-fake-{name}-001",
                summary=f"Mocked advisory in {full_name}",
                severity="high",
                state="published",
                published_at=_iso(-60 * 24 * 30),
            )
        ],
        projects=[
            GitHubProject(
                id=500,
                title=f"{name} roadmap",
                fields=[
                    ProjectField(
                        id=5500, name="Status", options=["Todo", "In Progress", "Done"]
                    ),
                    ProjectField(id=5501, name="Priority", options=["P0", "P1", "P2"]),
                ],
                items=[
                    ProjectItem(
                        id=7700,
                        type="issue",
                        issue_number=1,
                        status="In Progress",
                        priority="P0",
                    ),
                    ProjectItem(
                        id=7701,
                        type="issue",
                        issue_number=2,
                        status="Todo",
                        priority="P1",
                    ),
                ],
                status_updates=[
                    ProjectStatusUpdate(
                        id=8800,
                        body="Routing prototype almost ready for review.",
                        created_at=_iso(-60 * 4),
                    )
                ],
            )
        ],
        subscription=Subscription(subscribed=True, ignored=False, reason="manual"),
        counters=RepoCounters(
            next_number=max([*(i.number for i in issues), *(p.number for p in pulls)])
        ),
    )


def _build_seed_state() -> GitHubState:
    me = _make_user("avery", name="Avery Quinn", email="avery@corp.com", identifier=1)
    users = [
        me,
        _make_user("morgan", name="Morgan Lee", email="morgan@corp.com", identifier=2),
        _make_user(
            "jordan", name="Jordan Rivera", email="jordan@corp.com", identifier=3
        ),
        _make_user("nadia", name="Nadia Patel", email="nadia@corp.com", identifier=4),
        _make_user(
            "octocat",
            name="Mona Lisa Octocat",
            email="octocat@github.com",
            identifier=99,
        ),
    ]
    orgs = [
        GitHubOrg(
            login="instalily",
            id=100,
            description="Instalily org",
            html_url="https://github.com/instalily",
            issue_types=[
                IssueType(id=1, name="Bug"),
                IssueType(id=2, name="Feature"),
                IssueType(id=3, name="Task"),
            ],
        ),
        GitHubOrg(
            login="octo-org",
            id=200,
            description="Sample org",
            html_url="https://github.com/octo-org",
            issue_types=[
                IssueType(id=4, name="Bug"),
                IssueType(id=5, name="Enhancement"),
            ],
        ),
    ]
    teams = [
        GitHubTeam(
            org="instalily",
            slug="platform",
            name="Platform",
            description="Platform engineering",
            members=["avery", "morgan"],
        ),
        GitHubTeam(
            org="instalily",
            slug="growth",
            name="Growth",
            description="Growth and lifecycle",
            members=["nadia", "jordan"],
        ),
    ]
    repos = [
        _seed_repo(
            owner="instalily",
            name="orchestrator",
            description="Multi-tool chat harness powering the case study.",
            default_branch="main",
            private=True,
            visibility="internal",
        ),
        _seed_repo(
            owner="instalily",
            name="web-frontend",
            description="Customer-facing web app.",
            default_branch="main",
            private=True,
            visibility="internal",
        ),
        _seed_repo(
            owner="octocat",
            name="hello-world",
            description="My first repository on GitHub!",
            default_branch="main",
            private=False,
            visibility="public",
        ),
    ]
    return GitHubState(
        me=me,
        users=users,
        orgs=orgs,
        teams=teams,
        repos=repos,
        starred=["instalily/orchestrator", "octocat/hello-world"],
        notifications=[
            Notification(
                thread_id="100001",
                id="100001",
                subject=NotificationSubject(
                    title="PR review requested",
                    url="https://github.com/instalily/orchestrator/pull/4",
                    type="PullRequest",
                ),
                repository="instalily/orchestrator",
                reason="review_requested",
                unread=True,
                updated_at=_iso(-60 * 1),
            ),
            Notification(
                thread_id="100002",
                id="100002",
                subject=NotificationSubject(
                    title="Issue mentioned",
                    url="https://github.com/instalily/orchestrator/issues/1",
                    type="Issue",
                ),
                repository="instalily/orchestrator",
                reason="mention",
                unread=False,
                updated_at=_iso(-60 * 24 * 1),
            ),
        ],
        global_advisories=[
            GlobalAdvisory(
                ghsa_id="GHSA-aaaa-bbbb-cccc",
                cve_id="CVE-2025-1234",
                summary="Mocked global advisory",
                severity="high",
                ecosystem="pip",
                cwes=["CWE-89"],
                published_at=_iso(-60 * 24 * 90),
            )
        ],
        gists=[
            Gist(
                id="gist_demo",
                description="Tool routing scratchpad",
                public=True,
                owner="avery",
                files=[
                    GistFileEntry(
                        name="router.py",
                        file=GistFile(
                            filename="router.py",
                            content="# routing scratch\n",
                            language="Python",
                        ),
                    )
                ],
                html_url="https://gist.github.com/avery/gist_demo",
                created_at=_iso(-60 * 24 * 4),
                updated_at=_iso(-60 * 24 * 4),
            )
        ],
        copilot_jobs=[
            CopilotJob(
                id="cj_001",
                owner="instalily",
                repo="orchestrator",
                status="completed",
                summary="Implemented router prototype.",
                pull_request=4,
                created_at=_iso(-60 * 24 * 1),
                updated_at=_iso(-60 * 12),
            )
        ],
        copilot_spaces=[
            CopilotSpace(
                key="instalily/orchestrator-routing",
                name="orchestrator-routing",
                owner="instalily",
                description="Context for the routing decision.",
                files=["src/main.py", "src/router.py"],
                summary="Two-stage vs. semantic retrieval discussion.",
            )
        ],
    )


class GithubMockState(MockService[GitHubState]):
    def _seed_state(self) -> GitHubState:
        return _build_seed_state()


SERVICE = GithubMockState()


def get_state() -> GitHubState:
    return SERVICE.get_state()


def reset_github_mock_state() -> None:
    SERVICE.reset()


def snapshot_state() -> GitHubState:
    return SERVICE.snapshot()
