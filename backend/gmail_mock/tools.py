from __future__ import annotations

import shlex
from base64 import b64encode
from datetime import UTC, datetime
from typing import TypeVar

from backend.tooling import ToolDefinition, ToolSpec, build_tool_registry
from pydantic import BaseModel, ConfigDict, Field

from .state import (
    AttachmentSeed,
    GmailContact,
    GmailDraft,
    GmailHeader,
    GmailLabel,
    GmailLabelColor,
    GmailMessage,
    GmailMessageBody,
    GmailMessageMeta,
    GmailPayload,
    GmailPayloadPart,
    GmailState,
    StoredAttachment,
    ThreadIndex,
    _build_payload,
    get_state,
    reset_gmail_mock_state,
)


class GmailMockError(ValueError):
    """Raised when a Gmail mock tool receives invalid input or missing resources."""


# ---------------------------------------------------------------------------
# Argument-side Pydantic types (used by some tools as nested input shapes).
# ---------------------------------------------------------------------------


class GmailAttachment(BaseModel):
    """File attachment metadata. All fields required; pass null for unused attachments."""

    model_config = ConfigDict(extra="forbid")

    name: str
    s3key: str
    mimetype: str


# ---------------------------------------------------------------------------
# Public/return models — what callers see (mirrors the Gmail API).
# ---------------------------------------------------------------------------


class PublicGmailMessage(BaseModel):
    """A message with internal mock metadata stripped. payload may be omitted."""

    model_config = ConfigDict(extra="forbid")

    id: str
    threadId: str
    labelIds: list[str]
    snippet: str
    historyId: str
    internalDate: str
    sizeEstimate: int
    payload: GmailPayload | None = None
    raw: str | None = None


class MinimalGmailMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    threadId: str
    labelIds: list[str]


class IdsOnlyMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    threadId: str


# A "metadata" format keeps the payload but with headers + mimeType only.
class GmailMetadataPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headers: list[GmailHeader]
    mimeType: str


class MetadataGmailMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    threadId: str
    labelIds: list[str]
    snippet: str
    historyId: str
    internalDate: str
    sizeEstimate: int
    payload: GmailMetadataPayload


# Union for fetched-message endpoints that support multiple formats.
FetchedMessage = PublicGmailMessage | MinimalGmailMessage | MetadataGmailMessage


T = TypeVar("T")


# ---------------------------------------------------------------------------
# Tool result models
# ---------------------------------------------------------------------------


class FetchEmailsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messages: list[PublicGmailMessage | MinimalGmailMessage | IdsOnlyMessage]
    nextPageToken: str | None
    resultSizeEstimate: int


class FetchThreadResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    threadId: str
    messages: list[PublicGmailMessage]
    nextPageToken: str | None


class AttachmentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messageId: str
    attachmentId: str
    fileName: str
    mimeType: str
    size: int
    data: str


class ContactsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connections: list[GmailContact]
    nextPageToken: str | None
    totalPeople: int


class OtherContactsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    otherContacts: list[GmailContact]
    nextPageToken: str | None


class ProfileResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    emailAddress: str
    messagesTotal: int
    threadsTotal: int
    historyId: str


class PublicGmailDraft(BaseModel):
    """A draft entry. ``message`` is omitted when the caller asked for a lightweight list."""

    model_config = ConfigDict(extra="forbid")

    id: str
    message: PublicGmailMessage | None = None


class ListDraftsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    drafts: list[PublicGmailDraft]
    nextPageToken: str | None
    resultSizeEstimate: int


class PublicGmailLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    type: str
    labelListVisibility: str
    messageListVisibility: str
    color: GmailLabelColor | None = None


class ListLabelsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    labels: list[PublicGmailLabel]


class PublicGmailThread(BaseModel):
    """Thread summary. ``messages`` populated only when verbose=True; otherwise messageIds/subject."""

    model_config = ConfigDict(extra="forbid")

    id: str
    historyId: str
    snippet: str
    messages: list[PublicGmailMessage] | None = None
    messageIds: list[str] | None = None
    subject: str | None = None


class ListThreadsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    threads: list[PublicGmailThread]
    nextPageToken: str | None
    resultSizeEstimate: int


class DeletedDraftResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deletedDraftId: str


class DeletedMessageResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deletedMessageId: str


class RemovedLabelResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    removedLabelId: str


# ---------------------------------------------------------------------------
# Conversion / projection helpers — model → model only, no dicts.
# ---------------------------------------------------------------------------


def _to_public_label(label: GmailLabel) -> PublicGmailLabel:
    return PublicGmailLabel(
        id=label.id,
        name=label.name,
        type=label.type,
        labelListVisibility=label.labelListVisibility,
        messageListVisibility=label.messageListVisibility,
        color=label.color.model_copy() if label.color else None,
    )


def _strip_mock(message: GmailMessage, *, include_payload: bool) -> PublicGmailMessage:
    return PublicGmailMessage(
        id=message.id,
        threadId=message.threadId,
        labelIds=list(message.labelIds),
        snippet=message.snippet,
        historyId=message.historyId,
        internalDate=message.internalDate,
        sizeEstimate=message.sizeEstimate,
        payload=message.payload.model_copy(deep=True) if include_payload else None,
    )


def _project_message(
    message: GmailMessage,
    *,
    include_payload: bool,
    format: str,
) -> FetchedMessage:
    if format == "minimal":
        return MinimalGmailMessage(
            id=message.id, threadId=message.threadId, labelIds=list(message.labelIds)
        )
    if format == "metadata":
        return MetadataGmailMessage(
            id=message.id,
            threadId=message.threadId,
            labelIds=list(message.labelIds),
            snippet=message.snippet,
            historyId=message.historyId,
            internalDate=message.internalDate,
            sizeEstimate=message.sizeEstimate,
            payload=GmailMetadataPayload(
                headers=[h.model_copy() for h in message.payload.headers],
                mimeType=message.payload.mimeType,
            ),
        )
    public = _strip_mock(message, include_payload=include_payload)
    if format == "raw":
        public.raw = message.meta.body
    return public


def _to_public_draft(draft: GmailDraft, *, include_message: bool) -> PublicGmailDraft:
    return PublicGmailDraft(
        id=draft.id,
        message=(
            _strip_mock(draft.message, include_payload=True)
            if include_message
            else None
        ),
    )


def _subject_from_headers(headers: list[GmailHeader]) -> str:
    for header in headers:
        if header.name.lower() == "subject":
            return header.value
    return ""


def _project_thread(thread_id: str, *, verbose: bool) -> PublicGmailThread:
    messages = _thread_messages(thread_id, include_drafts=True)
    first = messages[0]
    base = PublicGmailThread(
        id=thread_id,
        historyId=messages[-1].historyId,
        snippet=first.snippet,
    )
    if verbose:
        base.messages = [_strip_mock(m, include_payload=True) for m in messages]
    else:
        base.messageIds = [m.id for m in messages]
        base.subject = _subject_from_headers(first.payload.headers)
    return base


# ---------------------------------------------------------------------------
# Query helpers — typed-model-only.
# ---------------------------------------------------------------------------


def _parse_query(query: str | None) -> list[str]:
    if not query:
        return []
    return shlex.split(query)


def _label_matches(term: str, label_ids: list[str]) -> bool:
    state = get_state()
    lower_term = term.lower()
    for label_id in label_ids:
        label = state.label(label_id)
        if label is None:
            continue
        if label.id.lower() == lower_term or label.name.lower() == lower_term:
            return True
    return False


def _message_matches_query(message: GmailMessage, query: str | None) -> bool:
    tokens = _parse_query(query)
    if not tokens:
        return True

    meta = message.meta
    searchable = " ".join(
        [
            meta.subject,
            meta.body,
            message.snippet,
            meta.sender,
            " ".join(meta.to),
            " ".join(meta.cc),
            " ".join(meta.bcc),
        ]
    ).lower()

    for token in tokens:
        lower_token = token.lower()
        if lower_token.startswith("from:"):
            if lower_token[5:] not in meta.sender.lower():
                return False
            continue
        if lower_token.startswith("to:"):
            if not any(
                lower_token[3:] in value.lower()
                for value in (*meta.to, *meta.cc, *meta.bcc)
            ):
                return False
            continue
        if lower_token.startswith("subject:"):
            if lower_token[8:] not in meta.subject.lower():
                return False
            continue
        if lower_token.startswith("label:"):
            if not _label_matches(lower_token[6:], message.labelIds):
                return False
            continue
        if lower_token.startswith("in:"):
            mailbox = lower_token[3:]
            required_label = {
                "trash": "TRASH",
                "inbox": "INBOX",
                "sent": "SENT",
                "drafts": "DRAFT",
            }.get(mailbox)
            if required_label and required_label not in message.labelIds:
                return False
            continue
        if lower_token not in searchable:
            return False
    return True


def _filter_messages(
    *,
    query: str | None = None,
    label_ids: list[str] | None = None,
    include_spam_trash: bool = False,
) -> list[GmailMessage]:
    state = get_state()
    label_ids = label_ids or []
    matched: list[GmailMessage] = []
    for message in state.messages:
        if not include_spam_trash and "TRASH" in message.labelIds:
            continue
        if label_ids and not all(
            label_id in message.labelIds for label_id in label_ids
        ):
            continue
        if _message_matches_query(message, query):
            matched.append(message)
    return sorted(matched, key=lambda item: int(item.internalDate), reverse=True)


def _thread_messages(
    thread_id: str, *, include_drafts: bool = True
) -> list[GmailMessage]:
    state = get_state()
    index = state.thread_index(thread_id)
    if index is None:
        return []
    messages: list[GmailMessage] = []
    for message_id in index.message_ids:
        message = state.message(message_id)
        if message is not None:
            messages.append(message)
            continue
        if not include_drafts:
            continue
        for draft in state.drafts:
            if draft.message.id == message_id:
                messages.append(draft.message)
                break
    return sorted(messages, key=lambda item: int(item.internalDate))


def _paginate(
    items: list[T], *, max_results: int, page_token: str | None
) -> tuple[list[T], str | None]:
    if max_results < 1:
        raise GmailMockError("max_results must be at least 1")
    start = int(page_token or "0")
    end = start + max_results
    next_token = str(end) if end < len(items) else None
    return items[start:end], next_token


# ---------------------------------------------------------------------------
# Mutators — id assignment + message construction.
# ---------------------------------------------------------------------------


def _next_id(kind: str) -> str:
    state = get_state()
    current = getattr(state.counters, kind)
    setattr(state.counters, kind, current + 1)
    prefix = {
        "message": "msg",
        "thread": "thr",
        "draft": "drf",
        "label": "Label",
        "attachment": "att",
    }[kind]
    return f"{prefix}_{getattr(state.counters, kind)}"


def _next_history_id() -> str:
    state = get_state()
    state.counters.history += 1
    history_id = str(state.counters.history)
    state.profile.historyId = history_id
    return history_id


def _label_exists_or_raise(label_id: str) -> None:
    if get_state().label(label_id) is None:
        raise GmailMockError(f"Unknown label id: {label_id}")


def _require_message(message_id: str) -> GmailMessage:
    message = get_state().message(message_id)
    if message is None:
        raise GmailMockError(f"Unknown message id: {message_id}")
    return message


def _require_draft(draft_id: str) -> GmailDraft:
    draft = get_state().draft(draft_id)
    if draft is None:
        raise GmailMockError(f"Unknown draft id: {draft_id}")
    return draft


def _require_thread(thread_id: str) -> list[GmailMessage]:
    messages = _thread_messages(thread_id, include_drafts=True)
    if not messages:
        raise GmailMockError(f"Unknown thread id: {thread_id}")
    return messages


def _register_thread_message(thread_id: str, message_id: str) -> None:
    state = get_state()
    index = state.thread_index(thread_id)
    if index is None:
        index = ThreadIndex(thread_id=thread_id, message_ids=[])
        state.threads.append(index)
    if message_id not in index.message_ids:
        index.message_ids.append(message_id)


def _remove_thread_message(thread_id: str, message_id: str) -> None:
    state = get_state()
    index = state.thread_index(thread_id)
    if index is None:
        return
    index.message_ids = [mid for mid in index.message_ids if mid != message_id]
    if not index.message_ids:
        state.threads = [t for t in state.threads if t.thread_id != thread_id]


def _build_attachment_seeds(
    attachment: GmailAttachment | dict | None,
) -> list[AttachmentSeed]:
    if not attachment:
        return []
    if isinstance(attachment, dict):
        attachment = GmailAttachment.model_validate(attachment)
    attachment_id = _next_id("attachment")
    encoded = b64encode(attachment.s3key.encode("utf-8")).decode("ascii")
    return [
        AttachmentSeed(
            attachmentId=attachment_id,
            fileName=attachment.name,
            mimeType=attachment.mimetype,
            size=len(attachment.s3key.encode("utf-8")),
            data=encoded,
        )
    ]


def _construct_message(
    *,
    sender: str,
    to: list[str],
    subject: str,
    body: str,
    label_ids: list[str],
    thread_id: str | None,
    cc: list[str] | None,
    bcc: list[str] | None,
    is_html: bool,
    attachment: GmailAttachment | None,
) -> GmailMessage:
    cc = cc or []
    bcc = bcc or []
    state = get_state()
    message_id = _next_id("message")
    history_id = _next_history_id()
    thread_id = thread_id or _next_id("thread")
    seeds = _build_attachment_seeds(attachment)
    existing_timestamps = [int(m.internalDate) for m in state.messages] + [
        int(d.message.internalDate) for d in state.drafts
    ]
    internal_date = str(max(existing_timestamps, default=1712570400000) + 60000)
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
        attachments=seeds,
    )
    message = GmailMessage(
        id=message_id,
        threadId=thread_id,
        labelIds=list(label_ids),
        snippet=body[:120],
        historyId=history_id,
        internalDate=internal_date,
        sizeEstimate=len(body.encode("utf-8")) + sum(item.size for item in seeds),
        payload=payload,
        meta=GmailMessageMeta(
            sender=sender,
            to=list(to),
            cc=list(cc),
            bcc=list(bcc),
            subject=subject,
            body=body,
            isHtml=is_html,
            attachmentIds=[item.attachmentId for item in seeds],
        ),
    )
    for seed in seeds:
        state.attachments.append(
            StoredAttachment(
                message_id=message_id,
                attachmentId=seed.attachmentId,
                fileName=seed.fileName,
                mimeType=seed.mimeType,
                size=seed.size,
                data=seed.data,
            )
        )
    return message


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def gmail_add_label_to_email(
    user_id: str = "me",
    message_id: str | None = None,
    add_label_ids: list[str] | None = None,
    remove_label_ids: list[str] | None = None,
) -> PublicGmailMessage:
    """Adds and/or removes specified Gmail labels for a message."""
    del user_id
    if not message_id:
        raise GmailMockError("message_id is required")
    message = _require_message(message_id)
    for label_id in (add_label_ids or []) + (remove_label_ids or []):
        _label_exists_or_raise(label_id)
    for label_id in add_label_ids or []:
        if label_id not in message.labelIds:
            message.labelIds.append(label_id)
    if remove_label_ids:
        message.labelIds = [
            lid for lid in message.labelIds if lid not in remove_label_ids
        ]
    message.historyId = _next_history_id()
    return _strip_mock(message, include_payload=True)


def gmail_create_email_draft(
    user_id: str = "me",
    recipient_email: str | None = None,
    extra_recipients: list[str] | None = None,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    subject: str | None = None,
    body: str | None = None,
    is_html: bool = False,
    thread_id: str | None = None,
    attachment: GmailAttachment | None = None,
) -> PublicGmailDraft:
    """Creates a Gmail draft with recipients, subject, body, and optional attachment metadata."""
    sender = get_state().profile.emailAddress if user_id == "me" else user_id
    if not recipient_email or not subject or body is None:
        raise GmailMockError("recipient_email, subject, and body are required")
    message = _construct_message(
        sender=sender,
        to=[recipient_email, *(extra_recipients or [])],
        cc=cc or [],
        bcc=bcc or [],
        subject=subject,
        body=body,
        label_ids=["DRAFT"],
        thread_id=thread_id,
        is_html=is_html,
        attachment=attachment,
    )
    draft = GmailDraft(id=_next_id("draft"), message=message)
    state = get_state()
    state.drafts.append(draft)
    _register_thread_message(message.threadId, message.id)
    return _to_public_draft(draft, include_message=True)


def gmail_create_label(
    user_id: str = "me",
    label_name: str | None = None,
    text_color: str | None = None,
    background_color: str | None = None,
    label_list_visibility: str = "labelShow",
    message_list_visibility: str = "show",
) -> PublicGmailLabel:
    """Creates a new user label in the mailbox."""
    del user_id
    if not label_name:
        raise GmailMockError("label_name is required")
    state = get_state()
    if state.label_by_name(label_name) is not None:
        raise GmailMockError(f"Label already exists: {label_name}")
    label = GmailLabel(
        id=_next_id("label"),
        name=label_name,
        type="user",
        labelListVisibility=label_list_visibility,
        messageListVisibility=message_list_visibility,
        color=(
            GmailLabelColor(
                textColor=text_color or "#000000",
                backgroundColor=background_color or "#ffffff",
            )
            if (text_color or background_color)
            else None
        ),
    )
    state.labels.append(label)
    return _to_public_label(label)


def gmail_delete_draft(
    user_id: str = "me", draft_id: str | None = None
) -> DeletedDraftResult:
    """Permanently deletes a draft by its ID."""
    del user_id
    if not draft_id:
        raise GmailMockError("draft_id is required")
    draft = _require_draft(draft_id)
    state = get_state()
    state.drafts = [d for d in state.drafts if d.id != draft_id]
    state.attachments = [
        a
        for a in state.attachments
        if not (
            a.message_id == draft.message.id
            and a.attachmentId in draft.message.meta.attachmentIds
        )
    ]
    _remove_thread_message(draft.message.threadId, draft.message.id)
    return DeletedDraftResult(deletedDraftId=draft_id)


def gmail_delete_message(
    user_id: str = "me", message_id: str | None = None
) -> DeletedMessageResult:
    """Permanently deletes an email message by its ID."""
    del user_id
    if not message_id:
        raise GmailMockError("message_id is required")
    message = _require_message(message_id)
    state = get_state()
    state.messages = [m for m in state.messages if m.id != message_id]
    state.attachments = [
        a
        for a in state.attachments
        if not (
            a.message_id == message_id and a.attachmentId in message.meta.attachmentIds
        )
    ]
    _remove_thread_message(message.threadId, message_id)
    _next_history_id()
    return DeletedMessageResult(deletedMessageId=message_id)


def gmail_fetch_emails(
    user_id: str = "me",
    query: str | None = None,
    label_ids: list[str] | None = None,
    max_results: int = 1,
    page_token: str | None = None,
    verbose: bool = True,
    ids_only: bool = False,
    include_payload: bool = True,
    include_spam_trash: bool = False,
) -> FetchEmailsResult:
    """Fetches email messages with Gmail-style query, label, and pagination filters."""
    del user_id
    matched = _filter_messages(
        query=query, label_ids=label_ids, include_spam_trash=include_spam_trash
    )
    page, next_token = _paginate(
        matched, max_results=max_results, page_token=page_token
    )
    messages: list[PublicGmailMessage | MinimalGmailMessage | IdsOnlyMessage]
    if ids_only:
        messages = [IdsOnlyMessage(id=m.id, threadId=m.threadId) for m in page]
    elif not verbose:
        messages = (
            [
                MinimalGmailMessage(
                    id=m.id, threadId=m.threadId, labelIds=list(m.labelIds)
                )
                for m in page
            ]
            if include_payload is False
            else [_strip_mock(m, include_payload=include_payload) for m in page]
        )
        # When verbose=False, the old API stripped to a "metadata" projection;
        # tests assert only that payload is absent when include_payload=False.
    else:
        messages = [_strip_mock(m, include_payload=include_payload) for m in page]
    return FetchEmailsResult(
        messages=messages,
        nextPageToken=next_token,
        resultSizeEstimate=len(matched),
    )


def gmail_fetch_message_by_message_id(
    user_id: str = "me",
    message_id: str | None = None,
    format: str = "full",
) -> FetchedMessage:
    """Fetches one email message by message ID in a chosen format."""
    del user_id
    if not message_id:
        raise GmailMockError("message_id is required")
    message = _require_message(message_id)
    return _project_message(message, include_payload=True, format=format)


def gmail_fetch_message_by_thread_id(
    user_id: str = "me",
    thread_id: str | None = None,
    page_token: str = "",
) -> FetchThreadResult:
    """Retrieves messages from a single thread by thread ID."""
    del user_id
    if not thread_id:
        raise GmailMockError("thread_id is required")
    messages = _require_thread(thread_id)
    page, next_token = _paginate(
        messages, max_results=50, page_token=page_token or None
    )
    return FetchThreadResult(
        threadId=thread_id,
        messages=[_strip_mock(m, include_payload=True) for m in page],
        nextPageToken=next_token,
    )


def gmail_get_attachment(
    user_id: str = "me",
    message_id: str | None = None,
    attachment_id: str | None = None,
    file_name: str | None = None,
) -> AttachmentResult:
    """Retrieves one attachment from a message when the message ID, attachment ID, and filename match."""
    del user_id
    if not message_id or not attachment_id or not file_name:
        raise GmailMockError("message_id, attachment_id, and file_name are required")
    attachment = get_state().attachment(message_id, attachment_id)
    if attachment is None:
        raise GmailMockError("Attachment not found for the provided message")
    if attachment.fileName != file_name:
        raise GmailMockError("file_name does not match the attachment metadata")
    return AttachmentResult(
        messageId=message_id,
        attachmentId=attachment_id,
        fileName=attachment.fileName,
        mimeType=attachment.mimeType,
        size=attachment.size,
        data=attachment.data,
    )


def gmail_get_contacts(
    resource_name: str = "people/me",
    person_fields: str = "emailAddresses,names,birthdays,genders",
    page_token: str | None = None,
    include_other_contacts: bool = True,
) -> ContactsResult:
    """Lists contacts for the authenticated account."""
    del resource_name, person_fields, include_other_contacts
    state = get_state()
    page, next_token = _paginate(state.contacts, max_results=10, page_token=page_token)
    return ContactsResult(
        connections=[c.model_copy(deep=True) for c in page],
        nextPageToken=next_token,
        totalPeople=len(state.contacts),
    )


def gmail_get_people(
    resource_name: str = "people/me",
    person_fields: str = "emailAddresses,names,birthdays,genders",
    other_contacts: bool = False,
    page_size: int = 10,
    page_token: str = "",
    sync_token: str = "",
) -> GmailContact | OtherContactsResult:
    """Returns either one person resource or a page of other contacts."""
    del person_fields, sync_token
    state = get_state()
    if other_contacts:
        page, next_token = _paginate(
            state.contacts, max_results=page_size, page_token=page_token or None
        )
        return OtherContactsResult(
            otherContacts=[c.model_copy(deep=True) for c in page],
            nextPageToken=next_token,
        )
    for person in state.people:
        if person.resourceName == resource_name:
            return person.model_copy(deep=True)
    raise GmailMockError(f"Unknown person resource: {resource_name}")


def gmail_get_profile(user_id: str = "me") -> ProfileResult:
    """Retrieves Gmail profile counts and history metadata for the mailbox."""
    del user_id
    state = get_state()
    live_message_ids = {m.id for m in state.messages}
    draft_message_ids = {d.message.id for d in state.drafts}
    threads_total = 0
    for index in state.threads:
        if any(
            mid in live_message_ids or mid in draft_message_ids
            for mid in index.message_ids
        ):
            threads_total += 1
    return ProfileResult(
        emailAddress=state.profile.emailAddress,
        messagesTotal=len(state.messages),
        threadsTotal=threads_total,
        historyId=state.profile.historyId,
    )


def gmail_list_drafts(
    user_id: str = "me",
    verbose: bool = False,
    max_results: int = 1,
    page_token: str = "",
) -> ListDraftsResult:
    """Lists drafts with optional verbose message details."""
    del user_id
    drafts = sorted(
        get_state().drafts,
        key=lambda item: int(item.message.internalDate),
        reverse=True,
    )
    page, next_token = _paginate(
        drafts, max_results=max_results, page_token=page_token or None
    )
    return ListDraftsResult(
        drafts=[_to_public_draft(d, include_message=verbose) for d in page],
        nextPageToken=next_token,
        resultSizeEstimate=len(drafts),
    )


def gmail_list_labels(user_id: str = "me") -> ListLabelsResult:
    """Lists all system and user labels in the mailbox."""
    del user_id
    labels = sorted(get_state().labels, key=lambda item: (item.type, item.name))
    return ListLabelsResult(labels=[_to_public_label(l) for l in labels])


def gmail_list_threads(
    user_id: str = "me",
    query: str = "",
    verbose: bool = False,
    max_results: int = 10,
    page_token: str = "",
) -> ListThreadsResult:
    """Lists mailbox threads with optional query filtering and verbose message expansion."""
    del user_id
    matched_message_ids: set[str] | None = None
    if query:
        matched_message_ids = {
            m.id for m in _filter_messages(query=query, include_spam_trash=True)
        }
    thread_ids: list[str] = []
    for index in get_state().threads:
        messages = _thread_messages(index.thread_id, include_drafts=True)
        if not messages:
            continue
        if matched_message_ids is not None and not any(
            m.id in matched_message_ids for m in messages
        ):
            continue
        thread_ids.append(index.thread_id)
    thread_ids.sort(
        key=lambda item: int(
            _thread_messages(item, include_drafts=True)[-1].internalDate
        ),
        reverse=True,
    )
    page, next_token = _paginate(
        thread_ids, max_results=max_results, page_token=page_token or None
    )
    return ListThreadsResult(
        threads=[_project_thread(tid, verbose=verbose) for tid in page],
        nextPageToken=next_token,
        resultSizeEstimate=len(thread_ids),
    )


def gmail_modify_thread_labels(
    user_id: str = "me",
    thread_id: str | None = None,
    add_label_ids: list[str] | None = None,
    remove_label_ids: list[str] | None = None,
) -> PublicGmailThread:
    """Adds and removes labels across every message in a thread."""
    del user_id
    if not thread_id:
        raise GmailMockError("thread_id is required")
    messages = _require_thread(thread_id)
    for label_id in (add_label_ids or []) + (remove_label_ids or []):
        _label_exists_or_raise(label_id)
    for message in messages:
        for label_id in add_label_ids or []:
            if label_id not in message.labelIds:
                message.labelIds.append(label_id)
        if remove_label_ids:
            message.labelIds = [
                lid for lid in message.labelIds if lid not in remove_label_ids
            ]
        message.historyId = _next_history_id()
    return _project_thread(thread_id, verbose=True)


def gmail_move_to_trash(
    user_id: str = "me", message_id: str | None = None
) -> PublicGmailMessage:
    """Moves a message to trash while preserving the rest of its metadata."""
    del user_id
    if not message_id:
        raise GmailMockError("message_id is required")
    message = _require_message(message_id)
    label_ids = [lid for lid in message.labelIds if lid != "INBOX"]
    if "TRASH" not in label_ids:
        label_ids.append("TRASH")
    message.labelIds = label_ids
    message.historyId = _next_history_id()
    return _strip_mock(message, include_payload=True)


def gmail_patch_label(
    userId: str,
    id: str,
    name: str | None = None,
    labelListVisibility: str | None = None,
    messageListVisibility: str | None = None,
    color: GmailLabelColor | None = None,
) -> PublicGmailLabel:
    """Updates a user label's display properties and colors."""
    del userId
    state = get_state()
    label = state.label(id)
    if label is None:
        raise GmailMockError(f"Unknown label id: {id}")
    if name and any(
        candidate.id != id and candidate.name.lower() == name.lower()
        for candidate in state.labels
    ):
        raise GmailMockError(f"Label already exists: {name}")
    if name:
        label.name = name
    if labelListVisibility:
        label.labelListVisibility = labelListVisibility
    if messageListVisibility:
        label.messageListVisibility = messageListVisibility
    if color:
        if isinstance(color, dict):
            color = GmailLabelColor.model_validate(color)
        label.color = GmailLabelColor(
            textColor=color.textColor,
            backgroundColor=color.backgroundColor,
        )
    return _to_public_label(label)


def gmail_remove_label(
    user_id: str = "me", label_id: str | None = None
) -> RemovedLabelResult:
    """Deletes a user-created label from the mailbox."""
    del user_id
    if not label_id:
        raise GmailMockError("label_id is required")
    state = get_state()
    label = state.label(label_id)
    if label is None:
        raise GmailMockError(f"Unknown label id: {label_id}")
    if label.type != "user":
        raise GmailMockError("System labels cannot be removed")
    state.labels = [l for l in state.labels if l.id != label_id]
    for message in state.messages:
        message.labelIds = [lid for lid in message.labelIds if lid != label_id]
    return RemovedLabelResult(removedLabelId=label_id)


def gmail_reply_to_thread(
    user_id: str = "me",
    thread_id: str | None = None,
    recipient_email: str | None = None,
    extra_recipients: list[str] | None = None,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    message_body: str | None = None,
    is_html: bool = False,
    attachment: GmailAttachment | None = None,
) -> PublicGmailMessage:
    """Sends a reply inside an existing thread using the thread subject."""
    if not thread_id or not recipient_email or message_body is None:
        raise GmailMockError(
            "thread_id, recipient_email, and message_body are required"
        )
    original_messages = _require_thread(thread_id)
    original_subject = original_messages[0].meta.subject
    sender = get_state().profile.emailAddress if user_id == "me" else user_id
    subject = (
        original_subject
        if original_subject.lower().startswith("re:")
        else f"Re: {original_subject}"
    )
    reply = _construct_message(
        sender=sender,
        to=[recipient_email, *(extra_recipients or [])],
        cc=cc or [],
        bcc=bcc or [],
        subject=subject,
        body=message_body,
        label_ids=["SENT"],
        thread_id=thread_id,
        is_html=is_html,
        attachment=attachment,
    )
    state = get_state()
    state.messages.append(reply)
    _register_thread_message(thread_id, reply.id)
    return _strip_mock(reply, include_payload=True)


_TOOL_DEFINITIONS: list[ToolDefinition] = [
    ToolDefinition(
        name="GMAIL_ADD_LABEL_TO_EMAIL",
        callable=gmail_add_label_to_email,
        description="Adds and/or removes specified Gmail labels for a message.",
        required_fields=frozenset({"message_id"}),
    ),
    ToolDefinition(
        name="GMAIL_CREATE_EMAIL_DRAFT",
        callable=gmail_create_email_draft,
        description="Creates a Gmail draft with recipients, subject, body, and optional attachment metadata.",
        required_fields=frozenset({"recipient_email", "subject", "body"}),
    ),
    ToolDefinition(
        name="GMAIL_CREATE_LABEL",
        callable=gmail_create_label,
        description="Creates a new user label in the mailbox.",
        required_fields=frozenset({"label_name"}),
    ),
    ToolDefinition(
        name="GMAIL_DELETE_DRAFT",
        callable=gmail_delete_draft,
        description="Permanently deletes a draft by its ID.",
        required_fields=frozenset({"draft_id"}),
    ),
    ToolDefinition(
        name="GMAIL_DELETE_MESSAGE",
        callable=gmail_delete_message,
        description="Permanently deletes an email message by its ID.",
        required_fields=frozenset({"message_id"}),
    ),
    ToolDefinition(
        name="GMAIL_FETCH_EMAILS",
        callable=gmail_fetch_emails,
        description="Fetches email messages with Gmail-style query, label, and pagination filters.",
    ),
    ToolDefinition(
        name="GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID",
        callable=gmail_fetch_message_by_message_id,
        description="Fetches one email message by message ID in a chosen format.",
        required_fields=frozenset({"message_id"}),
    ),
    ToolDefinition(
        name="GMAIL_FETCH_MESSAGE_BY_THREAD_ID",
        callable=gmail_fetch_message_by_thread_id,
        description="Retrieves messages from a single thread by thread ID.",
        required_fields=frozenset({"thread_id"}),
    ),
    ToolDefinition(
        name="GMAIL_GET_ATTACHMENT",
        callable=gmail_get_attachment,
        description="Retrieves one attachment from a message when the message ID, attachment ID, and filename match.",
        required_fields=frozenset({"message_id", "attachment_id", "file_name"}),
    ),
    ToolDefinition(
        name="GMAIL_GET_CONTACTS",
        callable=gmail_get_contacts,
        description="Lists contacts for the authenticated account.",
    ),
    ToolDefinition(
        name="GMAIL_GET_PEOPLE",
        callable=gmail_get_people,
        description="Returns either one person resource or a page of other contacts.",
    ),
    ToolDefinition(
        name="GMAIL_GET_PROFILE",
        callable=gmail_get_profile,
        description="Retrieves Gmail profile counts and history metadata for the mailbox.",
    ),
    ToolDefinition(
        name="GMAIL_LIST_DRAFTS",
        callable=gmail_list_drafts,
        description="Lists drafts with optional verbose message details.",
    ),
    ToolDefinition(
        name="GMAIL_LIST_LABELS",
        callable=gmail_list_labels,
        description="Lists all system and user labels in the mailbox.",
    ),
    ToolDefinition(
        name="GMAIL_LIST_THREADS",
        callable=gmail_list_threads,
        description="Lists mailbox threads with optional query filtering and verbose message expansion.",
    ),
    ToolDefinition(
        name="GMAIL_MODIFY_THREAD_LABELS",
        callable=gmail_modify_thread_labels,
        description="Adds and removes labels across every message in a thread.",
        required_fields=frozenset({"thread_id"}),
    ),
    ToolDefinition(
        name="GMAIL_MOVE_TO_TRASH",
        callable=gmail_move_to_trash,
        description="Moves a message to trash while preserving the rest of its metadata.",
        required_fields=frozenset({"message_id"}),
    ),
    ToolDefinition(
        name="GMAIL_PATCH_LABEL",
        callable=gmail_patch_label,
        description="Updates a user label's display properties and colors.",
        required_fields=frozenset({"userId", "id"}),
    ),
    ToolDefinition(
        name="GMAIL_REMOVE_LABEL",
        callable=gmail_remove_label,
        description="Deletes a user-created label from the mailbox.",
        required_fields=frozenset({"label_id"}),
    ),
    ToolDefinition(
        name="GMAIL_REPLY_TO_THREAD",
        callable=gmail_reply_to_thread,
        description="Sends a reply inside an existing thread using the thread subject.",
        required_fields=frozenset({"thread_id", "recipient_email", "message_body"}),
    ),
]


TOOL_REGISTRY: dict[str, ToolSpec] = build_tool_registry(
    service="gmail",
    definitions=_TOOL_DEFINITIONS,
)


def get_tool_registry() -> dict[str, ToolSpec]:
    return TOOL_REGISTRY


__all__ = [
    "AttachmentResult",
    "ContactsResult",
    "DeletedDraftResult",
    "DeletedMessageResult",
    "FetchEmailsResult",
    "FetchThreadResult",
    "GmailAttachment",
    "GmailMockError",
    "ListDraftsResult",
    "ListLabelsResult",
    "ListThreadsResult",
    "MetadataGmailMessage",
    "MinimalGmailMessage",
    "OtherContactsResult",
    "ProfileResult",
    "PublicGmailDraft",
    "PublicGmailLabel",
    "PublicGmailMessage",
    "PublicGmailThread",
    "RemovedLabelResult",
    "TOOL_REGISTRY",
    "get_tool_registry",
    "gmail_add_label_to_email",
    "gmail_create_email_draft",
    "gmail_create_label",
    "gmail_delete_draft",
    "gmail_delete_message",
    "gmail_fetch_emails",
    "gmail_fetch_message_by_message_id",
    "gmail_fetch_message_by_thread_id",
    "gmail_get_attachment",
    "gmail_get_contacts",
    "gmail_get_people",
    "gmail_get_profile",
    "gmail_list_drafts",
    "gmail_list_labels",
    "gmail_list_threads",
    "gmail_modify_thread_labels",
    "gmail_move_to_trash",
    "gmail_patch_label",
    "gmail_remove_label",
    "gmail_reply_to_thread",
    "reset_gmail_mock_state",
]
