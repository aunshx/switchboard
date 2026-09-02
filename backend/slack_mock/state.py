from __future__ import annotations

from datetime import UTC, datetime, timedelta

from backend.mock_service import MockService
from pydantic import BaseModel, ConfigDict, Field

BASE_TIME = datetime(2026, 4, 8, 13, 0, tzinfo=UTC)


def _ts(offset_minutes: int) -> str:
    instant = BASE_TIME + timedelta(minutes=offset_minutes)
    return f"{instant.timestamp():.6f}"


def _display_handle(name: str) -> str:
    return name.lower().replace(" ", "-")


class SlackUserProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    real_name: str
    display_name: str
    title: str
    email: str


class SlackUser(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    real_name: str
    deleted: bool
    is_bot: bool
    tz: str
    profile: SlackUserProfile


class SlackTopic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str


class SlackConversation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    conversation_type: str
    topic: SlackTopic
    member_ids: list[str]
    is_archived: bool = False


class SlackReply(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user: str
    ts: str


class SlackMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = "message"
    user: str
    text: str
    ts: str
    channel: str
    thread_ts: str | None = None
    reply_count: int = 0
    replies: list[SlackReply] = Field(default_factory=list)


class SlackWorkspace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str


class SlackToken(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    workspace: str
    auto_refresh: bool
    issued_at: str
    scopes: list[str]


class ChannelMessages(BaseModel):
    """All top-level messages in a single channel."""

    model_config = ConfigDict(extra="forbid")

    channel: str
    messages: list[SlackMessage]


class SlackThread(BaseModel):
    """A thread's reply chain. Parent message lives in the channel log only."""

    model_config = ConfigDict(extra="forbid")

    channel: str
    parent_ts: str
    replies: list[SlackMessage]


class SlackCounters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: int = 2000


class SlackState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace: SlackWorkspace
    bot_user_id: str
    token: SlackToken
    users: list[SlackUser]
    conversations: list[SlackConversation]
    channel_messages: list[ChannelMessages]
    threads: list[SlackThread]
    counters: SlackCounters = Field(default_factory=SlackCounters)

    def user(self, user_id: str) -> SlackUser | None:
        return next((u for u in self.users if u.id == user_id), None)

    def conversation(self, channel: str) -> SlackConversation | None:
        return next((c for c in self.conversations if c.id == channel), None)

    def channel_log(self, channel: str) -> ChannelMessages:
        existing = next(
            (cm for cm in self.channel_messages if cm.channel == channel), None
        )
        if existing is None:
            existing = ChannelMessages(channel=channel, messages=[])
            self.channel_messages.append(existing)
        return existing

    def thread(self, channel: str, parent_ts: str) -> SlackThread | None:
        return next(
            (
                t
                for t in self.threads
                if t.channel == channel and t.parent_ts == parent_ts
            ),
            None,
        )


# ---------------------------------------------------------------------------
# Seed users
# ---------------------------------------------------------------------------

USER_AVERY = SlackUser(
    id="U001",
    name=_display_handle("avery"),
    real_name="Avery Quinn",
    deleted=False,
    is_bot=False,
    tz="America/New_York",
    profile=SlackUserProfile(
        real_name="Avery Quinn",
        display_name="avery",
        title="Staff Engineer",
        email="avery@corp.com",
    ),
)

USER_MORGAN = SlackUser(
    id="U002",
    name=_display_handle("morgan"),
    real_name="Morgan Lee",
    deleted=False,
    is_bot=False,
    tz="America/New_York",
    profile=SlackUserProfile(
        real_name="Morgan Lee",
        display_name="morgan",
        title="Finance Lead",
        email="finance@corp.com",
    ),
)

USER_NADIA = SlackUser(
    id="U003",
    name=_display_handle("nadia"),
    real_name="Nadia Patel",
    deleted=False,
    is_bot=False,
    tz="America/New_York",
    profile=SlackUserProfile(
        real_name="Nadia Patel",
        display_name="nadia",
        title="Recruiting",
        email="recruiting@corp.com",
    ),
)

USER_OPS_BOT = SlackUser(
    id="U004",
    name=_display_handle("ops-bot"),
    real_name="Ops Bot",
    deleted=False,
    is_bot=True,
    tz="America/New_York",
    profile=SlackUserProfile(
        real_name="Ops Bot",
        display_name="ops-bot",
        title="Automation",
        email="ops-bot@corp.com",
    ),
)

USER_JORDAN = SlackUser(
    id="U005",
    name=_display_handle("jordan"),
    real_name="Jordan Rivera",
    deleted=False,
    is_bot=False,
    tz="America/New_York",
    profile=SlackUserProfile(
        real_name="Jordan Rivera",
        display_name="jordan",
        title="Account Executive",
        email="sales@corp.com",
    ),
)

SEED_USERS: list[SlackUser] = [
    USER_AVERY,
    USER_MORGAN,
    USER_NADIA,
    USER_OPS_BOT,
    USER_JORDAN,
]


# ---------------------------------------------------------------------------
# Seed conversations
# ---------------------------------------------------------------------------

CONV_ENGINEERING = SlackConversation(
    id="C001",
    name="engineering",
    conversation_type="public_channel",
    topic=SlackTopic(value="Engineering planning and launches"),
    member_ids=["U001", "U002", "U004", "U005"],
)

CONV_LEADERSHIP = SlackConversation(
    id="C002",
    name="leadership-private",
    conversation_type="private_channel",
    topic=SlackTopic(value="Leadership coordination"),
    member_ids=["U001", "U002", "U005"],
)

CONV_DM_AVERY_MORGAN = SlackConversation(
    id="D001",
    name="dm-avery-morgan",
    conversation_type="im",
    topic=SlackTopic(value="Direct messages between Avery and Morgan"),
    member_ids=["U001", "U002"],
)

CONV_LAUNCH_WAR_ROOM = SlackConversation(
    id="G001",
    name="launch-war-room",
    conversation_type="mpim",
    topic=SlackTopic(value="Launch war room"),
    member_ids=["U001", "U002", "U004", "U005"],
)

SEED_CONVERSATIONS: list[SlackConversation] = [
    CONV_ENGINEERING,
    CONV_LEADERSHIP,
    CONV_DM_AVERY_MORGAN,
    CONV_LAUNCH_WAR_ROOM,
]


# ---------------------------------------------------------------------------
# Seed messages
# ---------------------------------------------------------------------------

MSG_DEPLOY_DONE = SlackMessage(
    user="U004",
    text="Deployment completed for the orchestrator benchmark preview.",
    ts=_ts(-120),
    channel="C001",
)

MSG_REVENUE_REQUEST = SlackMessage(
    user="U001",
    text="Need a volunteer to summarize the revenue findings before the board prep.",
    ts=_ts(-90),
    channel="C001",
)

MSG_REVENUE_OFFER = SlackMessage(
    user="U002",
    text="I can summarize revenue deltas and attach the final workbook.",
    ts=_ts(-60),
    channel="C001",
)

MSG_RENEWAL_RISK = SlackMessage(
    user="U005",
    text="Renewal risk is still elevated. We should align before the customer call.",
    ts=_ts(-45),
    channel="C002",
)

MSG_BOARD_REVIEW_DM = SlackMessage(
    user="U002",
    text="Can you review the board summary before 3pm?",
    ts=_ts(-30),
    channel="D001",
)

MSG_WAR_ROOM_CHECKLIST = SlackMessage(
    user="U004",
    text="Launch checklist is green except for webinar QA.",
    ts=_ts(-75),
    channel="G001",
)


# Thread: rollback checklist
_THREAD_PARENT_TS = _ts(-50)
_THREAD_REPLY_1_TS = _ts(-49)
_THREAD_REPLY_2_TS = _ts(-48)

THREAD_PARENT_ROLLBACK = SlackMessage(
    user="U001",
    text="Who owns the final launch rollback checklist?",
    ts=_THREAD_PARENT_TS,
    channel="C001",
    reply_count=2,
    replies=[
        SlackReply(user="U004", ts=_THREAD_REPLY_1_TS),
        SlackReply(user="U005", ts=_THREAD_REPLY_2_TS),
    ],
)

THREAD_REPLY_OPS_BOT = SlackMessage(
    user="U004",
    text="Ops bot suggests Jordan is on point for the rollback checklist.",
    ts=_THREAD_REPLY_1_TS,
    channel="C001",
    thread_ts=_THREAD_PARENT_TS,
)

THREAD_REPLY_JORDAN = SlackMessage(
    user="U005",
    text="Confirmed. I own the rollback checklist and final approver list.",
    ts=_THREAD_REPLY_2_TS,
    channel="C001",
    thread_ts=_THREAD_PARENT_TS,
)


SEED_CHANNEL_MESSAGES: list[ChannelMessages] = [
    ChannelMessages(
        channel="C001",
        messages=[
            MSG_DEPLOY_DONE,
            MSG_REVENUE_REQUEST,
            MSG_REVENUE_OFFER,
            THREAD_PARENT_ROLLBACK,
        ],
    ),
    ChannelMessages(channel="C002", messages=[MSG_RENEWAL_RISK]),
    ChannelMessages(channel="D001", messages=[MSG_BOARD_REVIEW_DM]),
    ChannelMessages(channel="G001", messages=[MSG_WAR_ROOM_CHECKLIST]),
]

SEED_THREADS: list[SlackThread] = [
    SlackThread(
        channel="C001",
        parent_ts=_THREAD_PARENT_TS,
        replies=[
            THREAD_REPLY_OPS_BOT,
            THREAD_REPLY_JORDAN,
        ],
    ),
]


# ---------------------------------------------------------------------------
# Seed workspace + token
# ---------------------------------------------------------------------------

SEED_WORKSPACE = SlackWorkspace(id="T001", name="Instalily Internal")

SEED_TOKEN = SlackToken(
    status="active",
    workspace="Instalily Internal",
    auto_refresh=True,
    issued_at=(BASE_TIME - timedelta(days=14)).isoformat(),
    scopes=[
        "channels:history",
        "chat:write",
        "channels:read",
        "groups:read",
        "im:history",
        "users:read",
    ],
)


SEED_STATE = SlackState(
    workspace=SEED_WORKSPACE,
    bot_user_id="U004",
    token=SEED_TOKEN,
    users=SEED_USERS,
    conversations=SEED_CONVERSATIONS,
    channel_messages=SEED_CHANNEL_MESSAGES,
    threads=SEED_THREADS,
)


class SlackMockState(MockService[SlackState]):
    def _seed_state(self) -> SlackState:
        return SEED_STATE.model_copy(deep=True)


SERVICE = SlackMockState()


def get_state() -> SlackState:
    return SERVICE.get_state()


def reset_slack_mock_state() -> None:
    SERVICE.reset()


def snapshot_state() -> SlackState:
    return SERVICE.snapshot()
