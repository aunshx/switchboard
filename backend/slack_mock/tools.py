from __future__ import annotations

from backend.tooling import ToolDefinition, ToolSpec, build_tool_registry
from pydantic import BaseModel, ConfigDict, Field

from .state import (
    SlackConversation,
    SlackMessage,
    SlackReply,
    SlackUser,
    SlackUserProfile,
    get_state,
    reset_slack_mock_state,
)


class SlackMockError(ValueError):
    """Raised when a Slack mock tool receives invalid input or missing resources."""


# ---------------------------------------------------------------------------
# Public / enriched models — what tools return to callers.
# ---------------------------------------------------------------------------


class PublicSlackUser(BaseModel):
    """A user with all internal fields preserved (mirrors SlackUser)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    real_name: str
    deleted: bool
    is_bot: bool
    tz: str
    profile: SlackUserProfile

    @classmethod
    def from_user(cls, user: SlackUser) -> "PublicSlackUser":
        return cls(**user.model_dump())


class PublicSlackConversation(BaseModel):
    """A conversation enriched with resolved member display names."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    conversation_type: str
    topic_value: str
    member_ids: list[str]
    member_names: list[str]
    is_archived: bool


class PublicSlackMessage(BaseModel):
    """A message enriched with the author's display + real name."""

    model_config = ConfigDict(extra="forbid")

    type: str
    user: str
    text: str
    ts: str
    channel: str
    thread_ts: str | None
    reply_count: int
    replies: list[SlackReply]
    user_name: str
    real_name: str
    channel_name: str | None = None
    thread: list["PublicSlackMessage"] | None = None


# ---------------------------------------------------------------------------
# Internal helpers — typed-model-only, no dicts.
# ---------------------------------------------------------------------------


def _require_conversation(channel: str) -> SlackConversation:
    conversation = get_state().conversation(channel)
    if conversation is None:
        raise SlackMockError(f"Unknown Slack channel or DM: {channel}")
    return conversation


def _require_user(user_id: str) -> SlackUser:
    user = get_state().user(user_id)
    if user is None:
        raise SlackMockError(f"Unknown Slack user: {user_id}")
    return user


def _enrich_user(user: SlackUser) -> PublicSlackUser:
    return PublicSlackUser.from_user(user)


def _enrich_conversation(conversation: SlackConversation) -> PublicSlackConversation:
    member_names = [
        _require_user(uid).profile.display_name for uid in conversation.member_ids
    ]
    return PublicSlackConversation(
        id=conversation.id,
        name=conversation.name,
        conversation_type=conversation.conversation_type,
        topic_value=conversation.topic.value,
        member_ids=list(conversation.member_ids),
        member_names=member_names,
        is_archived=conversation.is_archived,
    )


def _enrich_message(
    message: SlackMessage,
    *,
    channel_name: str | None = None,
    thread: list[PublicSlackMessage] | None = None,
) -> PublicSlackMessage:
    author = _require_user(message.user)
    return PublicSlackMessage(
        type=message.type,
        user=message.user,
        text=message.text,
        ts=message.ts,
        channel=message.channel,
        thread_ts=message.thread_ts,
        reply_count=message.reply_count,
        replies=[reply.model_copy() for reply in message.replies],
        user_name=author.profile.display_name,
        real_name=author.real_name,
        channel_name=channel_name,
        thread=thread,
    )


def _filter_by_time(
    messages: list[SlackMessage],
    *,
    oldest: str | None,
    latest: str | None,
) -> list[SlackMessage]:
    out: list[SlackMessage] = []
    for message in messages:
        ts = float(message.ts)
        if oldest is not None and ts < float(oldest):
            continue
        if latest is not None and ts > float(latest):
            continue
        out.append(message)
    return out


def _sort_by_ts(messages: list[SlackMessage]) -> list[SlackMessage]:
    return sorted(messages, key=lambda item: float(item.ts))


def _next_ts() -> str:
    state = get_state()
    state.counters.message += 1
    existing = [float(msg.ts) for log in state.channel_messages for msg in log.messages]
    next_value = max(existing, default=1712581200.0) + 0.001
    return f"{next_value:.6f}"


# ---------------------------------------------------------------------------
# Tool result models
# ---------------------------------------------------------------------------


class SlackTokenStatusResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    status: str
    workspace: str
    auto_refresh: bool
    issued_at: str
    scopes: list[str]


class SlackHealthCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    workspace: str
    workspace_id: str
    bot_user_id: str
    user_count: int
    conversation_count: int


class SlackListConversationsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversations: list[PublicSlackConversation]
    result_count: int


class SlackConversationHistoryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: str
    messages: list[PublicSlackMessage]
    has_more: bool


class SlackFullConversationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: str
    messages: list[PublicSlackMessage]
    message_count: int


class SlackSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messages: list[PublicSlackMessage]
    result_count: int


class SlackThreadResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: str
    thread_ts: str
    messages: list[PublicSlackMessage]


class SlackUserInfoResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user: PublicSlackUser


class SlackListUsersResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    members: list[PublicSlackUser]
    result_count: int


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def slack_token_status() -> SlackTokenStatusResult:
    """Checks Slack token health, scopes, and auto-refresh status for the mock workspace."""
    token = get_state().token
    return SlackTokenStatusResult(
        ok=True,
        status=token.status,
        workspace=token.workspace,
        auto_refresh=token.auto_refresh,
        issued_at=token.issued_at,
        scopes=list(token.scopes),
    )


def slack_health_check() -> SlackHealthCheckResult:
    """Verifies the mock Slack workspace is reachable and summarizes workspace health."""
    state = get_state()
    return SlackHealthCheckResult(
        ok=True,
        workspace=state.workspace.name,
        workspace_id=state.workspace.id,
        bot_user_id=state.bot_user_id,
        user_count=len(state.users),
        conversation_count=len(state.conversations),
    )


def slack_list_conversations(
    limit: int = 100,
    types: str = "public_channel,private_channel,mpim,im",
    discover_dms: bool = False,
) -> SlackListConversationsResult:
    """Lists workspace conversations and DMs filtered by Slack conversation types."""
    state = get_state()
    requested_types = {item.strip() for item in types.split(",") if item.strip()}
    selected: list[SlackConversation] = []
    for conversation in state.conversations:
        if conversation.conversation_type not in requested_types:
            continue
        if (
            conversation.conversation_type == "im"
            and not discover_dms
            and conversation.id != "D001"
        ):
            continue
        selected.append(conversation)
    selected.sort(key=lambda item: item.name)
    capped = selected[:limit]
    return SlackListConversationsResult(
        conversations=[_enrich_conversation(c) for c in capped],
        result_count=len(capped),
    )


def slack_conversations_history(
    limit: int = 50,
    latest: str | None = None,
    oldest: str | None = None,
    channel: str | None = None,
) -> SlackConversationHistoryResult:
    """Returns channel or DM message history with user names resolved."""
    if not channel:
        raise SlackMockError("channel is required")
    _require_conversation(channel)
    log = get_state().channel_log(channel)
    filtered = _sort_by_ts(_filter_by_time(log.messages, oldest=oldest, latest=latest))
    return SlackConversationHistoryResult(
        channel=channel,
        messages=[_enrich_message(message) for message in filtered[-limit:]],
        has_more=len(filtered) > limit,
    )


def slack_get_full_conversation(
    latest: str | None = None,
    oldest: str | None = None,
    channel: str | None = None,
    max_messages: int = 2000,
    include_threads: bool = True,
) -> SlackFullConversationResult:
    """Exports a full conversation with optional thread expansion."""
    if not channel:
        raise SlackMockError("channel is required")
    _require_conversation(channel)
    state = get_state()
    log = state.channel_log(channel)
    history = _sort_by_ts(_filter_by_time(log.messages, oldest=oldest, latest=latest))[
        :max_messages
    ]
    enriched: list[PublicSlackMessage] = []
    for message in history:
        thread_payload: list[PublicSlackMessage] | None = None
        if include_threads and message.reply_count:
            thread = state.thread(channel, message.ts)
            if thread is not None:
                thread_payload = [_enrich_message(reply) for reply in thread.replies]
        enriched.append(_enrich_message(message, thread=thread_payload))
    return SlackFullConversationResult(
        channel=channel,
        messages=enriched,
        message_count=len(enriched),
    )


def slack_search_messages(
    count: int = 20,
    query: str | None = None,
) -> SlackSearchResult:
    """Searches messages across the mock Slack workspace with simple channel and user filters."""
    if not query:
        raise SlackMockError("query is required")
    state = get_state()
    tokens = query.split()
    channel_filter: str | None = None
    user_filter: str | None = None
    free_text: list[str] = []
    for token in tokens:
        lowered = token.lower()
        if lowered.startswith("in:#"):
            channel_name = lowered[4:]
            conversation = next(
                (c for c in state.conversations if c.name.lower() == channel_name),
                None,
            )
            channel_filter = conversation.id if conversation else None
            continue
        if lowered.startswith("from:@"):
            display_name = lowered[6:]
            user = next(
                (
                    u
                    for u in state.users
                    if u.profile.display_name.lower() == display_name
                ),
                None,
            )
            user_filter = user.id if user else None
            continue
        free_text.append(lowered)

    matches: list[PublicSlackMessage] = []
    for log in state.channel_messages:
        if channel_filter and log.channel != channel_filter:
            continue
        conversation = state.conversation(log.channel)
        channel_name = conversation.name if conversation else None
        for message in log.messages:
            if user_filter and message.user != user_filter:
                continue
            searchable = message.text.lower()
            if all(term in searchable for term in free_text):
                matches.append(_enrich_message(message, channel_name=channel_name))
    matches.sort(key=lambda item: float(item.ts), reverse=True)
    capped = matches[:count]
    return SlackSearchResult(messages=capped, result_count=len(capped))


def slack_send_message(
    text: str | None = None,
    channel: str | None = None,
    thread_ts: str | None = None,
) -> PublicSlackMessage:
    """Sends a message to a channel or posts a reply inside a thread."""
    if not text or not channel:
        raise SlackMockError("text and channel are required")
    _require_conversation(channel)
    state = get_state()
    ts = _next_ts()
    message = SlackMessage(
        user="U001",
        text=text,
        ts=ts,
        channel=channel,
        thread_ts=thread_ts,
    )
    state.channel_log(channel).messages.append(message)
    if thread_ts:
        thread = state.thread(channel, thread_ts)
        if thread is None:
            raise SlackMockError("Unknown thread_ts for the supplied channel")
        thread.replies.append(message)
        # Keep the parent in the channel log in sync.
        parent = next(
            (m for m in state.channel_log(channel).messages if m.ts == thread_ts),
            None,
        )
        if parent is not None:
            parent.reply_count += 1
            parent.replies.append(SlackReply(user="U001", ts=ts))
    return _enrich_message(message)


def slack_get_thread(
    channel: str | None = None,
    thread_ts: str | None = None,
) -> SlackThreadResult:
    """Returns the parent message and replies for one thread."""
    if not channel or not thread_ts:
        raise SlackMockError("channel and thread_ts are required")
    _require_conversation(channel)
    state = get_state()
    thread = state.thread(channel, thread_ts)
    if thread is None:
        raise SlackMockError("Unknown thread_ts for the supplied channel")
    parent = next(
        (m for m in state.channel_log(channel).messages if m.ts == thread_ts),
        None,
    )
    if parent is None:
        raise SlackMockError("Thread parent missing from channel log")
    messages = [parent, *thread.replies]
    return SlackThreadResult(
        channel=channel,
        thread_ts=thread_ts,
        messages=[_enrich_message(message) for message in messages],
    )


def slack_users_info(user: str | None = None) -> SlackUserInfoResult:
    """Returns one Slack user's profile details."""
    if not user:
        raise SlackMockError("user is required")
    return SlackUserInfoResult(user=_enrich_user(_require_user(user)))


def slack_list_users(limit: int = 500) -> SlackListUsersResult:
    """Lists workspace users with their profiles."""
    members = sorted(
        (_enrich_user(u) for u in get_state().users),
        key=lambda u: u.profile.display_name,
    )
    capped = members[:limit]
    return SlackListUsersResult(members=capped, result_count=len(capped))


_TOOL_DEFINITIONS: list[ToolDefinition] = [
    ToolDefinition(
        name="slack_token_status",
        callable=slack_token_status,
        description="Checks Slack token health, age, scopes, and auto-refresh status.",
    ),
    ToolDefinition(
        name="slack_health_check",
        callable=slack_health_check,
        description="Checks that the Slack workspace is reachable and returns workspace metadata.",
    ),
    ToolDefinition(
        name="slack_list_conversations",
        callable=slack_list_conversations,
        description="Lists channels and DMs in the workspace with resolved member names.",
    ),
    ToolDefinition(
        name="slack_conversations_history",
        callable=slack_conversations_history,
        description="Returns message history for a channel or DM.",
        required_fields=frozenset({"channel"}),
    ),
    ToolDefinition(
        name="slack_get_full_conversation",
        callable=slack_get_full_conversation,
        description="Exports a full conversation history with optional thread expansion.",
        required_fields=frozenset({"channel"}),
    ),
    ToolDefinition(
        name="slack_search_messages",
        callable=slack_search_messages,
        description="Searches Slack messages across the workspace.",
        required_fields=frozenset({"query"}),
    ),
    ToolDefinition(
        name="slack_send_message",
        callable=slack_send_message,
        description="Sends a new channel message or thread reply.",
        required_fields=frozenset({"text", "channel"}),
    ),
    ToolDefinition(
        name="slack_get_thread",
        callable=slack_get_thread,
        description="Returns every reply in a thread.",
        required_fields=frozenset({"channel", "thread_ts"}),
    ),
    ToolDefinition(
        name="slack_users_info",
        callable=slack_users_info,
        description="Gets detailed profile information for one Slack user.",
        required_fields=frozenset({"user"}),
    ),
    ToolDefinition(
        name="slack_list_users",
        callable=slack_list_users,
        description="Lists Slack users in the workspace.",
    ),
]


TOOL_REGISTRY: dict[str, ToolSpec] = build_tool_registry(
    service="slack",
    definitions=_TOOL_DEFINITIONS,
)


def get_tool_registry() -> dict[str, ToolSpec]:
    return TOOL_REGISTRY


__all__ = [
    "PublicSlackConversation",
    "PublicSlackMessage",
    "PublicSlackUser",
    "SlackConversationHistoryResult",
    "SlackFullConversationResult",
    "SlackHealthCheckResult",
    "SlackListConversationsResult",
    "SlackListUsersResult",
    "SlackMockError",
    "SlackSearchResult",
    "SlackThreadResult",
    "SlackTokenStatusResult",
    "SlackUserInfoResult",
    "TOOL_REGISTRY",
    "get_tool_registry",
    "reset_slack_mock_state",
    "slack_conversations_history",
    "slack_get_full_conversation",
    "slack_get_thread",
    "slack_health_check",
    "slack_list_conversations",
    "slack_list_users",
    "slack_search_messages",
    "slack_send_message",
    "slack_token_status",
    "slack_users_info",
]
