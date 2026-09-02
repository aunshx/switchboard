from __future__ import annotations

import json
from inspect import Parameter, signature
from typing import Any, NamedTuple

from pydantic import BaseModel, ValidationError

from backend.chat_schema import ToolCallLog
from backend.github_mock import GitHubMockError
from backend.gmail_mock import GmailMockError
from backend.googlecalendar_mock import GoogleCalendarMockError
from backend.googledrive_mock import GoogleDriveMockError
from backend.helpers import catalog
from backend.linear_mock import LinearMockError
from backend.perplexity_mock import PerplexityMockError
from backend.slack_mock import SlackMockError

MOCK_ERRORS: tuple[type[Exception], ...] = (
    GitHubMockError,
    GmailMockError,
    GoogleCalendarMockError,
    GoogleDriveMockError,
    LinearMockError,
    PerplexityMockError,
    SlackMockError,
)

UNKNOWN_TOOL = "unknown_tool"
INVALID_ARGUMENTS = "invalid_arguments"
TOOL_ERROR = "tool_error"
INTERNAL_ERROR = "internal_error"

READ_ONLY: frozenset[str] = frozenset({
    "GMAIL_FETCH_EMAILS", "GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID",
    "GMAIL_FETCH_MESSAGE_BY_THREAD_ID", "GMAIL_GET_ATTACHMENT", "GMAIL_GET_CONTACTS",
    "GMAIL_GET_PEOPLE", "GMAIL_GET_PROFILE", "GMAIL_LIST_DRAFTS", "GMAIL_LIST_LABELS",
    "GMAIL_LIST_THREADS", "GOOGLECALENDAR_EVENTS_INSTANCES",
    "GOOGLECALENDAR_EVENTS_LIST", "GOOGLECALENDAR_FIND_EVENT",
    "GOOGLECALENDAR_FIND_FREE_SLOTS", "GOOGLECALENDAR_FREE_BUSY_QUERY",
    "GOOGLECALENDAR_GET_CALENDAR", "GOOGLECALENDAR_GET_CURRENT_DATE_TIME",
    "GOOGLECALENDAR_LIST_ACL_RULES", "GOOGLECALENDAR_LIST_CALENDARS",
    "GOOGLECALENDAR_SETTINGS_LIST", "GOOGLECALENDAR_SYNC_EVENTS",
    "GOOGLEDRIVE_DOWNLOAD_FILE", "GOOGLEDRIVE_FIND_FILE", "GOOGLEDRIVE_FIND_FOLDER",
    "github_actions_get", "github_actions_list", "github_get_code_scanning_alert",
    "github_get_commit", "github_get_copilot_job_status", "github_get_copilot_space",
    "github_get_dependabot_alert", "github_get_discussion",
    "github_get_discussion_comments", "github_get_file_contents", "github_get_gist",
    "github_get_global_security_advisory", "github_get_job_logs", "github_get_label",
    "github_get_latest_release", "github_get_me", "github_get_notification_details",
    "github_get_release_by_tag", "github_get_repository_tree",
    "github_get_secret_scanning_alert", "github_get_tag", "github_get_team_members",
    "github_get_teams", "github_issue_read", "github_list_branches",
    "github_list_code_scanning_alerts", "github_list_commits", "github_list_copilot_spaces",
    "github_list_dependabot_alerts", "github_list_discussion_categories",
    "github_list_discussions", "github_list_gists",
    "github_list_global_security_advisories", "github_list_issue_types",
    "github_list_issues", "github_list_label", "github_list_notifications",
    "github_list_org_repository_security_advisories", "github_list_pull_requests",
    "github_list_releases", "github_list_repository_security_advisories",
    "github_list_secret_scanning_alerts", "github_list_starred_repositories",
    "github_list_tags", "github_projects_get", "github_projects_list",
    "github_pull_request_read", "github_search_code", "github_search_issues",
    "github_search_orgs", "github_search_pull_requests", "github_search_repositories",
    "github_search_users", "github_support_docs_search", "linear_get_document",
    "linear_get_issue", "linear_get_issue_status", "linear_get_project", "linear_get_team",
    "linear_get_user", "linear_list_comments", "linear_list_cycles",
    "linear_list_documents", "linear_list_issue_labels", "linear_list_issue_statuses",
    "linear_list_issues", "linear_list_project_labels", "linear_list_projects",
    "linear_list_teams", "linear_list_users", "linear_search_documentation",
    "slack_conversations_history", "slack_get_full_conversation", "slack_get_thread",
    "slack_health_check", "slack_list_conversations", "slack_list_users",
    "slack_search_messages", "slack_token_status", "slack_users_info",
})


_DEFAULTED: dict[str, frozenset[str]] = {
    name: frozenset(
        param_name
        for param_name, param in signature(spec.callable).parameters.items()
        if param.default is not Parameter.empty
    )
    for name, spec in catalog.SPECS.items()
}


class Outcome(NamedTuple):
    name: str
    result: Any
    error: str | None
    cached: bool = False

    @property
    def ok(self) -> bool:
        return self.error is None

    def feedback(self) -> Any:
        return {"error": self.error} if self.error else self.result


def cache_key(name: str, args: dict[str, Any]) -> tuple[str, frozenset[tuple[str, str]]]:
    return (
        name,
        frozenset(
            (key, json.dumps(value, sort_keys=True, default=str))
            for key, value in args.items()
        ),
    )


def is_read_only(name: str) -> bool:
    resolved = catalog.canonical(name)
    return resolved is not None and resolved in READ_ONLY


def strip_defaulted_nones(name: str, args: dict[str, Any]) -> dict[str, Any]:
    defaulted = _DEFAULTED.get(name, frozenset())
    return {k: v for k, v in args.items() if not (v is None and k in defaulted)}


def _compact_validation_error(exc: ValidationError) -> str:
    errors = exc.errors()
    parts = []
    for err in errors[:4]:
        loc = ".".join(str(p) for p in err.get("loc", ())) or "<root>"
        parts.append(f"{loc}: {err.get('msg', '')}")
    if len(errors) > 4:
        parts.append(f"(+{len(errors) - 4} more)")
    return "; ".join(parts)


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    return value


def dispatch(
    name: str,
    args: dict[str, Any] | None,
    log: list[ToolCallLog],
    cache: dict[Any, Any] | None = None,
) -> Outcome:
    raw = dict(args or {})
    resolved = catalog.canonical(name)

    if resolved is None:
        error = f"{UNKNOWN_TOOL}: {name!r} is not a registered tool"
        log.append(
            ToolCallLog(name=name or "<unknown>", arguments=raw, result=None, error=error)
        )
        return Outcome(name, None, error)

    clean = strip_defaulted_nones(resolved, raw)
    cacheable = cache is not None and resolved in READ_ONLY
    key = cache_key(resolved, clean) if cacheable else None
    if key is not None and key in cache:
        return Outcome(resolved, cache[key], None, cached=True)

    try:
        envelope = catalog.spec(resolved).invoke(**clean)
    except ValidationError as exc:
        error = f"{INVALID_ARGUMENTS}: {_compact_validation_error(exc)}"
    except MOCK_ERRORS as exc:
        error = f"{TOOL_ERROR}: {exc}"
    except Exception as exc:
        error = f"{INTERNAL_ERROR}: {type(exc).__name__}: {exc}"
    else:
        result = _to_jsonable(envelope.result)
        log.append(ToolCallLog(name=resolved, arguments=clean, result=result, error=None))
        if key is not None:
            cache[key] = result
        elif cache is not None and resolved not in READ_ONLY:
            cache.clear()
        return Outcome(resolved, result, None)

    log.append(ToolCallLog(name=resolved, arguments=clean, result=None, error=error))
    return Outcome(resolved, None, error)
