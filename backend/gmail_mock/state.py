from __future__ import annotations

from base64 import b64encode
from datetime import UTC, datetime, timedelta

from backend.mock_service import MockService
from pydantic import BaseModel, ConfigDict, Field

BASE_TIME = datetime(2026, 4, 8, 9, 0, tzinfo=UTC)


def _encode_text(value: str) -> str:
    return b64encode(value.encode("utf-8")).decode("ascii")


def _timestamp(offset_minutes: int) -> str:
    instant = BASE_TIME + timedelta(minutes=offset_minutes)
    return str(int(instant.timestamp() * 1000))


# ---------------------------------------------------------------------------
# Core Pydantic models — these mirror the Gmail API shapes.
# ---------------------------------------------------------------------------


class GmailHeader(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    value: str


class GmailLabelColor(BaseModel):
    """Gmail label color overrides expressed as hex codes."""

    model_config = ConfigDict(extra="forbid")

    textColor: str
    backgroundColor: str


class GmailLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    type: str  # "system" or "user"
    labelListVisibility: str = "labelShow"
    messageListVisibility: str = "show"
    color: GmailLabelColor | None = None


class GmailMessageBody(BaseModel):
    """Body of a payload part. ``data`` is base64; ``attachmentId`` refers to a stored blob."""

    model_config = ConfigDict(extra="forbid")

    size: int
    data: str | None = None
    attachmentId: str | None = None


class GmailPayloadPart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    partId: str
    mimeType: str
    filename: str
    headers: list[GmailHeader] = Field(default_factory=list)
    body: GmailMessageBody


class GmailPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    partId: str = ""
    mimeType: str
    filename: str = ""
    headers: list[GmailHeader]
    body: GmailMessageBody
    parts: list[GmailPayloadPart] = Field(default_factory=list)


class GmailMessageMeta(BaseModel):
    """Internal-only metadata kept alongside a message for search/build operations."""

    model_config = ConfigDict(extra="forbid")

    sender: str
    to: list[str]
    cc: list[str] = Field(default_factory=list)
    bcc: list[str] = Field(default_factory=list)
    subject: str
    body: str
    isHtml: bool = False
    attachmentIds: list[str] = Field(default_factory=list)


class GmailMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    threadId: str
    labelIds: list[str]
    snippet: str
    historyId: str
    internalDate: str
    sizeEstimate: int
    payload: GmailPayload
    meta: GmailMessageMeta


class GmailDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    message: GmailMessage


class StoredAttachment(BaseModel):
    """An attachment blob stored against a (message_id, attachment_id) key."""

    model_config = ConfigDict(extra="forbid")

    message_id: str
    attachmentId: str
    fileName: str
    mimeType: str
    size: int
    data: str


class ThreadIndex(BaseModel):
    """The ordered message ids that compose a thread."""

    model_config = ConfigDict(extra="forbid")

    thread_id: str
    message_ids: list[str]


class GmailContactName(BaseModel):
    model_config = ConfigDict(extra="forbid")

    displayName: str
    givenName: str
    familyName: str


class GmailEmailAddress(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str


class GmailContact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resourceName: str
    etag: str
    names: list[GmailContactName]
    emailAddresses: list[GmailEmailAddress]


class GmailProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    emailAddress: str
    historyId: str


class GmailCounters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: int = 1000
    thread: int = 100
    draft: int = 100
    label: int = 200
    attachment: int = 300
    history: int = 9010


class GmailState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: GmailProfile
    labels: list[GmailLabel]
    messages: list[GmailMessage]
    drafts: list[GmailDraft]
    contacts: list[GmailContact]
    people: list[GmailContact]
    attachments: list[StoredAttachment]
    threads: list[ThreadIndex]
    counters: GmailCounters = Field(default_factory=GmailCounters)

    # ----- lookups ---------------------------------------------------------

    def message(self, message_id: str) -> GmailMessage | None:
        return next((m for m in self.messages if m.id == message_id), None)

    def label(self, label_id: str) -> GmailLabel | None:
        return next((l for l in self.labels if l.id == label_id), None)

    def label_by_name(self, name: str) -> GmailLabel | None:
        lower = name.lower()
        return next((l for l in self.labels if l.name.lower() == lower), None)

    def draft(self, draft_id: str) -> GmailDraft | None:
        return next((d for d in self.drafts if d.id == draft_id), None)

    def thread_index(self, thread_id: str) -> ThreadIndex | None:
        return next((t for t in self.threads if t.thread_id == thread_id), None)

    def attachment(
        self, message_id: str, attachment_id: str
    ) -> StoredAttachment | None:
        return next(
            (
                a
                for a in self.attachments
                if a.message_id == message_id and a.attachmentId == attachment_id
            ),
            None,
        )


# ---------------------------------------------------------------------------
# Helpers for building seed messages
# ---------------------------------------------------------------------------


def _header(name: str, value: str) -> GmailHeader:
    return GmailHeader(name=name, value=value)


def _build_payload(
    *,
    sender: str,
    to: list[str],
    cc: list[str],
    bcc: list[str],
    subject: str,
    body: str,
    internal_date: str,
    message_id: str,
    is_html: bool,
    attachments: list["AttachmentSeed"],
) -> GmailPayload:
    mime_type = "text/html" if is_html else "text/plain"
    parts: list[GmailPayloadPart] = [
        GmailPayloadPart(
            partId="0",
            mimeType=mime_type,
            filename="",
            headers=[],
            body=GmailMessageBody(
                size=len(body.encode("utf-8")), data=_encode_text(body)
            ),
        )
    ]
    for index, attachment in enumerate(attachments, start=1):
        parts.append(
            GmailPayloadPart(
                partId=str(index),
                mimeType=attachment.mimeType,
                filename=attachment.fileName,
                headers=[],
                body=GmailMessageBody(
                    size=attachment.size, attachmentId=attachment.attachmentId
                ),
            )
        )

    headers = [
        _header("From", sender),
        _header("To", ", ".join(to)),
        _header("Subject", subject),
        _header(
            "Date",
            datetime.fromtimestamp(int(internal_date) / 1000, tz=UTC).isoformat(),
        ),
        _header("Message-ID", f"<{message_id}@mock.gmail.local>"),
    ]
    if cc:
        headers.append(_header("Cc", ", ".join(cc)))
    if bcc:
        headers.append(_header("Bcc", ", ".join(bcc)))

    return GmailPayload(
        partId="",
        mimeType="multipart/mixed" if attachments else mime_type,
        filename="",
        headers=headers,
        body=GmailMessageBody(size=0),
        parts=parts,
    )


class AttachmentSeed(BaseModel):
    """Seed-time attachment description before it lands in the StoredAttachment table."""

    model_config = ConfigDict(extra="forbid")

    attachmentId: str
    fileName: str
    mimeType: str
    size: int
    data: str


def _attachment_seed(
    attachment_id: str, file_name: str, mime_type: str, content: str
) -> AttachmentSeed:
    encoded = _encode_text(content)
    return AttachmentSeed(
        attachmentId=attachment_id,
        fileName=file_name,
        mimeType=mime_type,
        size=len(content.encode("utf-8")),
        data=encoded,
    )


def _seed_message(
    *,
    message_id: str,
    thread_id: str,
    history_id: int,
    offset_minutes: int,
    sender: str,
    to: list[str],
    subject: str,
    body: str,
    snippet: str,
    label_ids: list[str],
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    attachments: list[AttachmentSeed] | None = None,
    is_html: bool = False,
) -> GmailMessage:
    cc = cc or []
    bcc = bcc or []
    attachments = attachments or []
    internal_date = _timestamp(offset_minutes)
    payload = _build_payload(
        sender=sender,
        to=to,
        cc=cc,
        bcc=bcc,
        subject=subject,
        body=body,
        internal_date=internal_date,
        message_id=message_id,
        is_html=is_html,
        attachments=attachments,
    )
    return GmailMessage(
        id=message_id,
        threadId=thread_id,
        labelIds=list(label_ids),
        snippet=snippet,
        historyId=str(history_id),
        internalDate=internal_date,
        sizeEstimate=len(body.encode("utf-8")) + sum(item.size for item in attachments),
        payload=payload,
        meta=GmailMessageMeta(
            sender=sender,
            to=list(to),
            cc=list(cc),
            bcc=list(bcc),
            subject=subject,
            body=body,
            isHtml=is_html,
            attachmentIds=[item.attachmentId for item in attachments],
        ),
    )


# ---------------------------------------------------------------------------
# Seed attachments
# ---------------------------------------------------------------------------

ATTACHMENT_FINANCE_SHEET = _attachment_seed(
    "att_001",
    "q1-revenue.xlsx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "Q1 revenue workbook with projections and regional breakout.",
)

ATTACHMENT_LAUNCH_DECK = _attachment_seed(
    "att_002",
    "launch-plan.pdf",
    "application/pdf",
    "Launch plan covering timing, channels, and messaging pillars.",
)


# ---------------------------------------------------------------------------
# Seed labels
# ---------------------------------------------------------------------------

LABEL_INBOX = GmailLabel(id="INBOX", name="INBOX", type="system")
LABEL_SENT = GmailLabel(id="SENT", name="SENT", type="system")
LABEL_DRAFT = GmailLabel(id="DRAFT", name="DRAFT", type="system")
LABEL_TRASH = GmailLabel(id="TRASH", name="TRASH", type="system")
LABEL_UNREAD = GmailLabel(id="UNREAD", name="UNREAD", type="system")
LABEL_IMPORTANT = GmailLabel(id="IMPORTANT", name="IMPORTANT", type="system")
LABEL_STARRED = GmailLabel(id="STARRED", name="STARRED", type="system")
LABEL_CATEGORY_UPDATES = GmailLabel(
    id="CATEGORY_UPDATES", name="CATEGORY_UPDATES", type="system"
)

LABEL_FINANCE = GmailLabel(
    id="Label_101",
    name="Finance",
    type="user",
    color=GmailLabelColor(textColor="#ffffff", backgroundColor="#0f766e"),
)
LABEL_HIRING = GmailLabel(
    id="Label_102",
    name="Hiring",
    type="user",
    color=GmailLabelColor(textColor="#111827", backgroundColor="#fde68a"),
)
LABEL_VIP = GmailLabel(
    id="Label_103",
    name="VIP",
    type="user",
    color=GmailLabelColor(textColor="#ffffff", backgroundColor="#b91c1c"),
)

SEED_LABELS: list[GmailLabel] = [
    LABEL_INBOX,
    LABEL_SENT,
    LABEL_DRAFT,
    LABEL_TRASH,
    LABEL_UNREAD,
    LABEL_IMPORTANT,
    LABEL_STARRED,
    LABEL_CATEGORY_UPDATES,
    LABEL_FINANCE,
    LABEL_HIRING,
    LABEL_VIP,
]


# ---------------------------------------------------------------------------
# Seed messages
# ---------------------------------------------------------------------------

MSG_Q1_REVENUE = _seed_message(
    message_id="msg_001",
    thread_id="thr_001",
    history_id=9001,
    offset_minutes=-320,
    sender="finance@corp.com",
    to=["me@example.com"],
    subject="Q1 revenue review",
    body=(
        "Revenue finished 8 percent above plan. The west region led growth, "
        "and the board packet is attached for review before Friday."
    ),
    snippet="Revenue finished 8 percent above plan. The west region led growth.",
    label_ids=["INBOX", "IMPORTANT", "UNREAD", "Label_101"],
    attachments=[ATTACHMENT_FINANCE_SHEET],
)

MSG_REVENUE_REPLY = _seed_message(
    message_id="msg_002",
    thread_id="thr_001",
    history_id=9002,
    offset_minutes=-280,
    sender="cfo@corp.com",
    to=["me@example.com"],
    subject="Re: Q1 revenue review",
    body=(
        "Please summarize the revenue deltas for the board meeting. "
        "Focus on enterprise upsell and new logo pipeline."
    ),
    snippet="Please summarize the revenue deltas for the board meeting.",
    label_ids=["INBOX", "Label_101"],
)

MSG_PRIYA_ONSITE = _seed_message(
    message_id="msg_003",
    thread_id="thr_002",
    history_id=9003,
    offset_minutes=-190,
    sender="recruiting@corp.com",
    to=["me@example.com"],
    subject="Candidate onsite loop for Priya Shah",
    body=(
        "Priya is available next Tuesday for a backend onsite. "
        "Please confirm interview availability and preferred panel."
    ),
    snippet="Priya is available next Tuesday for a backend onsite.",
    label_ids=["INBOX", "UNREAD", "Label_102"],
)

MSG_RENEWAL_CONCERN = _seed_message(
    message_id="msg_004",
    thread_id="thr_003",
    history_id=9004,
    offset_minutes=-120,
    sender="ceo@vip-client.com",
    to=["me@example.com"],
    subject="Renewal concern for enterprise contract",
    body=(
        "Our procurement team is stuck on pricing. I need a revised proposal "
        "today or the renewal may slip into next month."
    ),
    snippet="Our procurement team is stuck on pricing.",
    label_ids=["INBOX", "IMPORTANT", "STARRED", "Label_103"],
)

MSG_LAUNCH_CHECKPOINT = _seed_message(
    message_id="msg_005",
    thread_id="thr_004",
    history_id=9005,
    offset_minutes=-70,
    sender="launch@corp.com",
    to=["me@example.com", "product@corp.com"],
    subject="Product launch checkpoint",
    body=(
        "The launch plan is attached. We still need final copy approval, "
        "paid media confirmation, and the webinar landing page QA signoff."
    ),
    snippet="The launch plan is attached. We still need final copy approval.",
    label_ids=["INBOX", "CATEGORY_UPDATES"],
    attachments=[ATTACHMENT_LAUNCH_DECK],
)

MSG_OFFICE_MOVE = _seed_message(
    message_id="msg_006",
    thread_id="thr_005",
    history_id=9006,
    offset_minutes=-25,
    sender="me@example.com",
    to=["ops@corp.com"],
    subject="Office move checklist",
    body=(
        "Sharing the office move checklist. Please confirm facilities timing "
        "and badge access before the weekend."
    ),
    snippet="Sharing the office move checklist.",
    label_ids=["SENT"],
)

SEED_MESSAGES: list[GmailMessage] = [
    MSG_Q1_REVENUE,
    MSG_REVENUE_REPLY,
    MSG_PRIYA_ONSITE,
    MSG_RENEWAL_CONCERN,
    MSG_LAUNCH_CHECKPOINT,
    MSG_OFFICE_MOVE,
]


# ---------------------------------------------------------------------------
# Seed drafts
# ---------------------------------------------------------------------------

DRAFT_REVENUE_FOLLOWUP_MESSAGE = _seed_message(
    message_id="msg_drf_001",
    thread_id="thr_006",
    history_id=9007,
    offset_minutes=-10,
    sender="me@example.com",
    to=["finance@corp.com"],
    subject="Follow-up on revenue assumptions",
    body=(
        "Can you break out the revenue assumptions by segment and include "
        "the revised enterprise churn estimate?"
    ),
    snippet="Can you break out the revenue assumptions by segment",
    label_ids=["DRAFT"],
)

DRAFT_REVENUE_FOLLOWUP = GmailDraft(
    id="drf_001", message=DRAFT_REVENUE_FOLLOWUP_MESSAGE
)

SEED_DRAFTS: list[GmailDraft] = [DRAFT_REVENUE_FOLLOWUP]


# ---------------------------------------------------------------------------
# Seed contacts + people
# ---------------------------------------------------------------------------

CONTACT_MORGAN = GmailContact(
    resourceName="people/c1",
    etag="%EgUBAi43PCo=",
    names=[
        GmailContactName(displayName="Morgan Lee", givenName="Morgan", familyName="Lee")
    ],
    emailAddresses=[GmailEmailAddress(value="finance@corp.com")],
)

CONTACT_NADIA = GmailContact(
    resourceName="people/c2",
    etag="%EgUBAi43PCp=",
    names=[
        GmailContactName(
            displayName="Nadia Patel", givenName="Nadia", familyName="Patel"
        )
    ],
    emailAddresses=[GmailEmailAddress(value="recruiting@corp.com")],
)

CONTACT_JORDAN = GmailContact(
    resourceName="people/c3",
    etag="%EgUBAi43PCq=",
    names=[
        GmailContactName(
            displayName="Jordan Rivera", givenName="Jordan", familyName="Rivera"
        )
    ],
    emailAddresses=[GmailEmailAddress(value="ceo@vip-client.com")],
)

PERSON_ME = GmailContact(
    resourceName="people/me",
    etag="%EgUBAi43PCm=",
    names=[
        GmailContactName(
            displayName="Avery Quinn", givenName="Avery", familyName="Quinn"
        )
    ],
    emailAddresses=[GmailEmailAddress(value="me@example.com")],
)

SEED_CONTACTS: list[GmailContact] = [CONTACT_MORGAN, CONTACT_NADIA, CONTACT_JORDAN]
SEED_PEOPLE: list[GmailContact] = [PERSON_ME, *SEED_CONTACTS]


# ---------------------------------------------------------------------------
# Seed attachments + threads
# ---------------------------------------------------------------------------


def _stored(message_id: str, seed: AttachmentSeed) -> StoredAttachment:
    return StoredAttachment(
        message_id=message_id,
        attachmentId=seed.attachmentId,
        fileName=seed.fileName,
        mimeType=seed.mimeType,
        size=seed.size,
        data=seed.data,
    )


SEED_ATTACHMENTS: list[StoredAttachment] = [
    _stored("msg_001", ATTACHMENT_FINANCE_SHEET),
    _stored("msg_005", ATTACHMENT_LAUNCH_DECK),
]


SEED_THREADS: list[ThreadIndex] = [
    ThreadIndex(thread_id="thr_001", message_ids=["msg_001", "msg_002"]),
    ThreadIndex(thread_id="thr_002", message_ids=["msg_003"]),
    ThreadIndex(thread_id="thr_003", message_ids=["msg_004"]),
    ThreadIndex(thread_id="thr_004", message_ids=["msg_005"]),
    ThreadIndex(thread_id="thr_005", message_ids=["msg_006"]),
    ThreadIndex(thread_id="thr_006", message_ids=["msg_drf_001"]),
]


SEED_PROFILE = GmailProfile(emailAddress="me@example.com", historyId="9007")


SEED_STATE = GmailState(
    profile=SEED_PROFILE,
    labels=SEED_LABELS,
    messages=SEED_MESSAGES,
    drafts=SEED_DRAFTS,
    contacts=SEED_CONTACTS,
    people=SEED_PEOPLE,
    attachments=SEED_ATTACHMENTS,
    threads=SEED_THREADS,
)


class GmailMockState(MockService[GmailState]):
    def _seed_state(self) -> GmailState:
        return SEED_STATE.model_copy(deep=True)


SERVICE = GmailMockState()


def get_state() -> GmailState:
    return SERVICE.get_state()


def reset_gmail_mock_state() -> None:
    SERVICE.reset()


def snapshot_state() -> GmailState:
    return SERVICE.snapshot()
