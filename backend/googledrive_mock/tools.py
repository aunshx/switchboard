from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import TypeVar
from zoneinfo import ZoneInfo

from backend.tooling import ToolDefinition, ToolSpec, build_tool_registry
from pydantic import BaseModel, ConfigDict, Field

from .state import (
    BASE_NOW,
    BASE_TIMEZONE,
    DOC_MIME,
    FOLDER_MIME,
    ME_USER,
    SHORTCUT_MIME,
    Drive,
    DriveBackgroundImage,
    DriveComment,
    DriveFile,
    DriveFileLabel,
    DriveLabelFieldModification,
    DriveLabelModification,
    DrivePermission,
    DriveReply,
    DriveRequestId,
    DriveState,
    DriveUser,
    _make_comment,
    _make_drive,
    _make_file,
    _make_reply,
    get_state,
    reset_googledrive_mock_state,
)


class GoogleDriveMockError(ValueError):
    """Raised when a Google Drive mock tool receives invalid input or missing resources."""


T = TypeVar("T")


# ---------------------------------------------------------------------------
# Public/return models — strip internal meta.
# ---------------------------------------------------------------------------


class PublicDriveFile(BaseModel):
    """Public projection of a DriveFile (internal meta stripped)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    kind: str
    name: str
    mimeType: str
    description: str | None = None
    parents: list[str]
    starred: bool
    trashed: bool
    createdTime: str
    modifiedTime: str
    owners: list[DriveUser]
    lastModifyingUser: DriveUser
    shared: bool
    webViewLink: str
    iconLink: str
    quotaBytesUsed: str
    size: str
    permissions: list[DrivePermission]
    labels: list[DriveFileLabel] = Field(default_factory=list)
    driveId: str | None = None
    shortcutDetails: dict | None = (
        None  # serialized inline; kept for compatibility — see _to_public_file
    )
    exportLinks: list = Field(default_factory=list)
    content: str | None = None


class PublicDrive(BaseModel):
    """Public projection of a shared Drive (deleted flag stripped)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    kind: str
    name: str
    hidden: bool
    themeId: str | None
    colorRgb: str | None
    backgroundImageFile: DriveBackgroundImage | None
    createdTime: str
    restrictions: dict
    capabilities: dict
    permissions: list[DrivePermission]


def _to_public_file(
    file: DriveFile, *, include_content: bool = False
) -> PublicDriveFile:
    return PublicDriveFile(
        id=file.id,
        kind=file.kind,
        name=file.name,
        mimeType=file.mimeType,
        description=file.description,
        parents=list(file.parents),
        starred=file.starred,
        trashed=file.trashed,
        createdTime=file.createdTime,
        modifiedTime=file.modifiedTime,
        owners=[u.model_copy() for u in file.owners],
        lastModifyingUser=file.lastModifyingUser.model_copy(),
        shared=file.shared,
        webViewLink=file.webViewLink,
        iconLink=file.iconLink,
        quotaBytesUsed=file.quotaBytesUsed,
        size=file.size,
        permissions=[p.model_copy() for p in file.permissions],
        labels=[l.model_copy(deep=True) for l in file.labels],
        driveId=file.driveId,
        shortcutDetails=(
            file.shortcutDetails.model_dump() if file.shortcutDetails else None
        ),
        exportLinks=[link.model_dump() for link in file.exportLinks],
        content=file.meta.content if include_content else None,
    )


def _to_public_drive(drive: Drive) -> PublicDrive:
    return PublicDrive(
        id=drive.id,
        kind=drive.kind,
        name=drive.name,
        hidden=drive.hidden,
        themeId=drive.themeId,
        colorRgb=drive.colorRgb,
        backgroundImageFile=(
            drive.backgroundImageFile.model_copy()
            if drive.backgroundImageFile
            else None
        ),
        createdTime=drive.createdTime,
        restrictions=drive.restrictions.model_dump(),
        capabilities=drive.capabilities.model_dump(),
        permissions=[p.model_copy() for p in drive.permissions],
    )


# ---------------------------------------------------------------------------
# Tool result models
# ---------------------------------------------------------------------------


class AddSharingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: PublicDriveFile
    permission: DrivePermission


class CreateReplyResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: str
    content: str
    createdTime: str
    modifiedTime: str
    action: str | None
    author: DriveUser


class CreateCommentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: str
    content: str
    createdTime: str
    modifiedTime: str
    deleted: bool
    resolved: bool
    author: DriveUser
    replies: list[DriveReply]
    anchor: str | None = None
    quotedFileContent: dict | None = None


class DeletedCommentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deleted: bool
    comment_id: str
    file_id: str


class DeletedReplyResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deleted: bool
    reply_id: str
    comment_id: str
    file_id: str


class DeletedPermissionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deleted: bool
    permission_id: str
    file_id: str


class DeletedDriveResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deleted: bool
    driveId: str
    deletedItemCount: int


class DownloadFileResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: PublicDriveFile
    mimeType: str
    content: str
    size: int


class EmptyTrashResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deletedFileIds: list[str]
    deletedCount: int


class ModifyLabelsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    modifiedLabels: list[DriveFileLabel]


class FindFileResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    files: list[PublicDriveFile]
    nextPageToken: str | None
    incompleteSearch: bool


class FindFolderResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    folders: list[PublicDriveFile]
    resultCount: int


class GenerateIdsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ids: list[str]
    space: str


# ---------------------------------------------------------------------------
# Internal helpers — typed models only.
# ---------------------------------------------------------------------------


def _parse_datetime(value: str | None) -> datetime | None:
    if value in (None, ""):
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=ZoneInfo(BASE_TIMEZONE))
    return parsed


def _next_id(kind: str) -> str:
    state = get_state()
    current = getattr(state.counters, kind)
    setattr(state.counters, kind, current + 1)
    prefix = {
        "file": "file",
        "drive": "drive",
        "permission": "perm",
        "comment": "cmt",
        "reply": "rpl",
        "generated_id": "gid",
    }[kind]
    return f"{prefix}_{getattr(state.counters, kind)}"


def _require_file(file_id: str) -> DriveFile:
    file = get_state().file(file_id)
    if file is None or file.meta.deleted:
        raise GoogleDriveMockError(f"Unknown Google Drive file id: {file_id}")
    return file


def _require_drive(drive_id: str) -> Drive:
    drive = get_state().drive(drive_id)
    if drive is None or drive.deleted:
        raise GoogleDriveMockError(f"Unknown shared drive id: {drive_id}")
    return drive


def _require_comment(file_id: str, comment_id: str) -> DriveComment:
    _require_file(file_id)
    comment = get_state().comment(file_id, comment_id)
    if comment is None or comment.deleted:
        raise GoogleDriveMockError(f"Unknown comment id: {comment_id}")
    return comment


def _require_reply(file_id: str, comment_id: str, reply_id: str) -> DriveReply:
    comment = _require_comment(file_id, comment_id)
    reply = next((r for r in comment.replies if r.id == reply_id), None)
    if reply is None:
        raise GoogleDriveMockError(f"Unknown reply id: {reply_id}")
    return reply


def _permissions_container(resource_id: str) -> list[DrivePermission]:
    state = get_state()
    file = state.file(resource_id)
    if file is not None:
        return file.permissions
    drive = state.drive(resource_id)
    if drive is not None:
        return drive.permissions
    raise GoogleDriveMockError(f"Unknown file or drive id: {resource_id}")


def _touch_file(file: DriveFile, *, content: str | None = None) -> None:
    offset = get_state().counters.file
    file.modifiedTime = (BASE_NOW + timedelta(minutes=offset)).isoformat()
    if content is not None:
        file.meta.content = content
        file.size = str(len(content.encode("utf-8")))
        file.quotaBytesUsed = file.size


def _resolve_parent(parent_id: str | None) -> str:
    if parent_id in (None, "", "root"):
        return "root"
    state = get_state()
    if state.file(parent_id) is not None:
        return parent_id
    for file in state.files:
        if file.mimeType == FOLDER_MIME and file.name == parent_id and not file.trashed:
            return file.id
    raise GoogleDriveMockError(f"Unknown parent folder: {parent_id}")


def _match_simple_q(file: DriveFile, q: str) -> bool:
    lowered = q.lower()
    if "trashed=false" in lowered and file.trashed:
        return False
    if "trashed=true" in lowered and not file.trashed:
        return False
    if "starred=true" in lowered and not file.starred:
        return False
    if "starred=false" in lowered and file.starred:
        return False

    name_contains = re.findall(r"name\s+contains\s+'([^']+)'", q, flags=re.IGNORECASE)
    for value in name_contains:
        if value.lower() not in file.name.lower():
            return False

    mime_equals = re.findall(r"mimeType\s*=\s*'([^']+)'", q, flags=re.IGNORECASE)
    for value in mime_equals:
        if file.mimeType != value:
            return False

    haystack = " ".join(
        filter(None, [file.name, file.description, file.meta.content])
    ).lower()
    full_text_contains = re.findall(
        r"fullText\s+contains\s+'([^']+)'", q, flags=re.IGNORECASE
    )
    for value in full_text_contains:
        if value.lower() not in haystack:
            return False

    tokens = re.findall(r"[a-z0-9._@-]+", lowered)
    ignored = {
        "and",
        "or",
        "contains",
        "name",
        "mimetype",
        "fulltext",
        "trashed",
        "starred",
        "true",
        "false",
    }
    free_tokens = [token for token in tokens if token not in ignored]
    if free_tokens and not all(
        token in haystack or token in file.mimeType.lower() for token in free_tokens
    ):
        return False
    return True


def _find_files(
    *,
    q: str | None,
    corpora: str | None,
    drive_id: str | None,
    include_items_from_all_drives: bool,
) -> list[DriveFile]:
    results: list[DriveFile] = []
    for file in get_state().files:
        if file.meta.deleted:
            continue
        if corpora == "drive" and drive_id and file.meta.driveId != drive_id:
            continue
        if (
            not include_items_from_all_drives
            and corpora != "drive"
            and file.meta.driveId
            and corpora != "allDrives"
        ):
            continue
        if q and not _match_simple_q(file, q):
            continue
        results.append(file)
    return results


def _sort_files(files: list[DriveFile], order_by: str | None) -> list[DriveFile]:
    if order_by == "modifiedTime desc":
        return sorted(files, key=lambda f: f.modifiedTime, reverse=True)
    if order_by == "modifiedTime":
        return sorted(files, key=lambda f: f.modifiedTime)
    return sorted(files, key=lambda f: f.name.lower())


def _paginate(
    items: list[T], page_size: int, page_token: str | None
) -> tuple[list[T], str | None]:
    start = int(page_token or "0")
    end = start + page_size
    next_token = str(end) if end < len(items) else None
    return items[start:end], next_token


def _coerce(model: type, value):
    if value is None or isinstance(value, model):
        return value
    return model.model_validate(value)


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def googledrive_add_file_sharing_preference(
    role: str | None = None,
    type: str | None = None,
    file_id: str | None = None,
    email_address: str | None = None,
    domain: str | None = None,
) -> AddSharingResult:
    """Modifies file sharing permissions for an existing Google Drive file."""
    if not role or not type or not file_id:
        raise GoogleDriveMockError("role, type, and file_id are required")
    file = _require_file(file_id)
    if type in {"user", "group"} and not email_address:
        raise GoogleDriveMockError(
            "email_address is required for user or group permissions"
        )
    if type == "domain" and not domain:
        raise GoogleDriveMockError("domain is required for domain permissions")
    permission = DrivePermission(
        id=_next_id("permission"),
        role=role,
        type=type,
        emailAddress=email_address,
        domain=domain,
        allowFileDiscovery=False if type == "anyone" else None,
    )
    file.permissions.append(permission)
    file.shared = True
    _touch_file(file)
    return AddSharingResult(
        file=_to_public_file(file), permission=permission.model_copy()
    )


def googledrive_copy_file(
    file_id: str | None = None, new_title: str | None = None
) -> PublicDriveFile:
    """Duplicates an existing Google Drive file."""
    if not file_id:
        raise GoogleDriveMockError("file_id is required")
    source = _require_file(file_id)
    copied_id = _next_id("file")
    copied = source.model_copy(deep=True)
    copied.id = copied_id
    copied.name = new_title or f"Copy of {source.name}"
    copied.createdTime = BASE_NOW.isoformat()
    copied.modifiedTime = BASE_NOW.isoformat()
    copied.webViewLink = f"https://drive.google.com/file/d/{copied_id}/view"
    copied.meta.deleted = False
    get_state().files.append(copied)
    return _to_public_file(copied)


def googledrive_create_comment(
    file_id: str | None = None,
    content: str | None = None,
    anchor: str | None = None,
    quoted_file_content_value: str | None = None,
    quoted_file_content_mime_type: str | None = None,
) -> CreateCommentResult:
    """Creates a new comment on a Google Drive file."""
    if not file_id or not content:
        raise GoogleDriveMockError("file_id and content are required")
    _require_file(file_id)
    comment = _make_comment(
        _next_id("comment"),
        content=content,
        anchor=anchor,
        quoted_value=quoted_file_content_value,
        quoted_mime_type=quoted_file_content_mime_type or "text/plain",
    )
    get_state().comment_log(file_id).comments.append(comment)
    return CreateCommentResult(
        id=comment.id,
        kind=comment.kind,
        content=comment.content,
        createdTime=comment.createdTime,
        modifiedTime=comment.modifiedTime,
        deleted=comment.deleted,
        resolved=comment.resolved,
        author=comment.author.model_copy(),
        replies=[r.model_copy() for r in comment.replies],
        anchor=comment.anchor,
        quotedFileContent=(
            comment.quotedFileContent.model_dump()
            if comment.quotedFileContent
            else None
        ),
    )


def googledrive_create_drive(
    name: str | None = None,
    requestId: str | None = None,
    hidden: bool | None = None,
    themeId: str | None = None,
    colorRgb: str | None = None,
    backgroundImageFile: DriveBackgroundImage | None = None,
) -> PublicDrive:
    """Creates a new shared drive."""
    if not name or not requestId:
        raise GoogleDriveMockError("name and requestId are required")
    state = get_state()
    existing = state.request_id(requestId)
    if existing:
        return _to_public_drive(_require_drive(existing.drive_id))
    background_image = _coerce(DriveBackgroundImage, backgroundImageFile)
    drive = _make_drive(
        drive_id=_next_id("drive"),
        name=name,
        hidden=bool(hidden) if hidden is not None else False,
        theme_id=themeId,
        color_rgb=colorRgb,
        background_image_file=background_image,
    )
    state.drives.append(drive)
    state.request_ids.append(DriveRequestId(request_id=requestId, drive_id=drive.id))
    return _to_public_drive(drive)


def googledrive_create_file(
    name: str | None = None,
    mimeType: str | None = None,
    parents: list[str] | None = None,
    starred: bool | None = None,
    description: str | None = None,
    fields: str | None = None,
) -> PublicDriveFile:
    """Creates a new Google Drive file or folder with metadata."""
    del fields
    parent_ids = [_resolve_parent(p) for p in (parents or ["root"])]
    file = _make_file(
        file_id=_next_id("file"),
        name=name or "Untitled",
        mime_type=mimeType or "text/plain",
        parents=parent_ids,
        starred=bool(starred) if starred is not None else False,
        description=description,
        text_content="",
    )
    get_state().files.append(file)
    return _to_public_file(file)


def googledrive_create_file_from_text(
    file_name: str | None = None,
    text_content: str | None = None,
    mime_type: str = "text/plain",
    parent_id: str | None = None,
) -> PublicDriveFile:
    """Creates a new Google Drive file from plain text content."""
    if not file_name or text_content is None:
        raise GoogleDriveMockError("file_name and text_content are required")
    parent = _resolve_parent(parent_id)
    file = _make_file(
        file_id=_next_id("file"),
        name=file_name,
        mime_type=mime_type,
        parents=[parent],
        text_content=text_content,
    )
    get_state().files.append(file)
    return _to_public_file(file, include_content=True)


def googledrive_create_folder(
    folder_name: str | None = None, parent_id: str | None = None
) -> PublicDriveFile:
    """Creates a new Google Drive folder."""
    if not folder_name:
        raise GoogleDriveMockError("folder_name is required")
    parent = _resolve_parent(parent_id)
    folder = _make_file(
        file_id=_next_id("file"),
        name=folder_name,
        mime_type=FOLDER_MIME,
        parents=[parent],
    )
    get_state().files.append(folder)
    return _to_public_file(folder)


def googledrive_create_reply(
    file_id: str | None = None,
    comment_id: str | None = None,
    content: str | None = None,
    action: str | None = None,
    fields: str | None = None,
) -> CreateReplyResult:
    """Creates a reply on an existing Google Drive comment."""
    del fields
    if not file_id or not comment_id or not content:
        raise GoogleDriveMockError("file_id, comment_id, and content are required")
    comment = _require_comment(file_id, comment_id)
    reply = _make_reply(_next_id("reply"), content=content, action=action)
    comment.replies.append(reply)
    if action == "resolve":
        comment.resolved = True
    elif action == "reopen":
        comment.resolved = False
    return CreateReplyResult(
        id=reply.id,
        kind=reply.kind,
        content=reply.content,
        createdTime=reply.createdTime,
        modifiedTime=reply.modifiedTime,
        action=reply.action,
        author=reply.author.model_copy(),
    )


def googledrive_create_shortcut_to_file(
    name: str | None = None,
    target_id: str | None = None,
    target_mime_type: str | None = None,
    includeLabels: str | None = None,
    supportsAllDrives: bool | None = None,
    keepRevisionForever: bool | None = None,
    ignoreDefaultVisibility: bool | None = None,
    includePermissionsForView: str | None = None,
) -> PublicDriveFile:
    """Creates a shortcut to an existing file or folder."""
    del (
        includeLabels,
        supportsAllDrives,
        keepRevisionForever,
        ignoreDefaultVisibility,
        includePermissionsForView,
    )
    if not name or not target_id:
        raise GoogleDriveMockError("name and target_id are required")
    target = _require_file(target_id)
    shortcut = _make_file(
        file_id=_next_id("file"),
        name=name,
        mime_type=SHORTCUT_MIME,
        parents=["root"],
        shortcut_target_id=target_id,
        shortcut_target_mime_type=target_mime_type or target.mimeType,
    )
    get_state().files.append(shortcut)
    return _to_public_file(shortcut)


def googledrive_delete_comment(
    file_id: str | None = None, comment_id: str | None = None
) -> DeletedCommentResult:
    """Deletes a comment from a file."""
    if not file_id or not comment_id:
        raise GoogleDriveMockError("file_id and comment_id are required")
    comment = _require_comment(file_id, comment_id)
    comment.deleted = True
    return DeletedCommentResult(deleted=True, comment_id=comment_id, file_id=file_id)


def googledrive_delete_drive(
    driveId: str | None = None,
    allowItemDeletion: bool | None = None,
    useDomainAdminAccess: bool | None = None,
) -> DeletedDriveResult:
    """Permanently deletes a shared drive and optionally its contents."""
    del useDomainAdminAccess
    if not driveId:
        raise GoogleDriveMockError("driveId is required")
    drive = _require_drive(driveId)
    files_in_drive = [
        f for f in get_state().files if f.meta.driveId == driveId and not f.meta.deleted
    ]
    if files_in_drive and not allowItemDeletion:
        raise GoogleDriveMockError(
            "allowItemDeletion must be true to delete a shared drive with content"
        )
    for file in files_in_drive:
        file.meta.deleted = True
    drive.deleted = True
    return DeletedDriveResult(
        deleted=True, driveId=driveId, deletedItemCount=len(files_in_drive)
    )


def googledrive_delete_permission(
    file_id: str | None = None,
    permission_id: str | None = None,
    supportsAllDrives: bool | None = None,
    useDomainAdminAccess: bool | None = None,
) -> DeletedPermissionResult:
    """Deletes a permission from a file or shared drive."""
    del supportsAllDrives, useDomainAdminAccess
    if not file_id or not permission_id:
        raise GoogleDriveMockError("file_id and permission_id are required")
    permissions = _permissions_container(file_id)
    remaining = [p for p in permissions if p.id != permission_id]
    if len(remaining) == len(permissions):
        raise GoogleDriveMockError(f"Unknown permission id: {permission_id}")
    permissions[:] = remaining
    return DeletedPermissionResult(
        deleted=True, permission_id=permission_id, file_id=file_id
    )


def googledrive_delete_reply(
    file_id: str | None = None,
    comment_id: str | None = None,
    reply_id: str | None = None,
) -> DeletedReplyResult:
    """Deletes a reply from an existing comment."""
    if not file_id or not comment_id or not reply_id:
        raise GoogleDriveMockError("file_id, comment_id, and reply_id are required")
    comment = _require_comment(file_id, comment_id)
    _require_reply(file_id, comment_id, reply_id)
    comment.replies = [r for r in comment.replies if r.id != reply_id]
    return DeletedReplyResult(
        deleted=True, reply_id=reply_id, comment_id=comment_id, file_id=file_id
    )


def googledrive_download_file(
    file_id: str | None = None, mime_type: str | None = None
) -> DownloadFileResult:
    """Downloads a file and optionally exports Google Workspace content."""
    if not file_id:
        raise GoogleDriveMockError("file_id is required")
    file = _require_file(file_id)
    if file.mimeType == FOLDER_MIME:
        raise GoogleDriveMockError("Folders cannot be downloaded")
    output_mime = mime_type or file.mimeType
    content = file.meta.content
    if file.mimeType == DOC_MIME and mime_type:
        content = f"[exported as {mime_type}]\n{content}"
    return DownloadFileResult(
        file=_to_public_file(file),
        mimeType=output_mime,
        content=content,
        size=len(content.encode("utf-8")),
    )


def googledrive_edit_file(
    file_id: str | None = None,
    content: str | None = None,
    mime_type: str = "text/plain",
) -> PublicDriveFile:
    """Overwrites the entire text content of an existing file."""
    if not file_id or content is None:
        raise GoogleDriveMockError("file_id and content are required")
    file = _require_file(file_id)
    if file.mimeType == FOLDER_MIME:
        raise GoogleDriveMockError("Folders cannot be edited as text")
    file.mimeType = mime_type
    _touch_file(file, content=content)
    return _to_public_file(file, include_content=True)


def googledrive_empty_trash(
    driveId: str | None = None,
    enforceSingleParent: bool | None = None,
) -> EmptyTrashResult:
    """Permanently deletes trashed files."""
    del enforceSingleParent
    state = get_state()
    deleted_ids: list[str] = []
    remaining: list[DriveFile] = []
    for file in state.files:
        if not file.trashed:
            remaining.append(file)
            continue
        if driveId is not None and file.meta.driveId != driveId:
            remaining.append(file)
            continue
        deleted_ids.append(file.id)
    state.files = remaining
    return EmptyTrashResult(deletedFileIds=deleted_ids, deletedCount=len(deleted_ids))


def googledrive_files_modify_labels(
    file_id: str | None = None,
    label_modifications: list[DriveLabelModification] | None = None,
    kind: str = "drive#modifyLabelsRequest",
) -> ModifyLabelsResult:
    """Adds, updates, or removes file labels."""
    if not file_id or label_modifications is None:
        raise GoogleDriveMockError("file_id and label_modifications are required")
    file = _require_file(file_id)
    for raw in label_modifications:
        mod = _coerce(DriveLabelModification, raw)
        if not mod.label_id:
            raise GoogleDriveMockError("Each label modification requires label_id")
        if mod.remove_label:
            file.labels = [l for l in file.labels if l.id != mod.label_id]
            continue
        existing = next((l for l in file.labels if l.id == mod.label_id), None)
        if existing is None:
            file.labels.append(
                DriveFileLabel(
                    id=mod.label_id,
                    revisionId=str(len(file.labels) + 1),
                    field_modifications=[
                        fm.model_copy() for fm in mod.field_modifications
                    ],
                )
            )
        else:
            existing.revisionId = str(int(existing.revisionId) + 1)
            existing.field_modifications = [
                fm.model_copy() for fm in mod.field_modifications
            ]
    _touch_file(file)
    return ModifyLabelsResult(
        kind=kind,
        modifiedLabels=[l.model_copy(deep=True) for l in file.labels],
    )


def googledrive_find_file(
    q: str | None = None,
    spaces: str = "drive",
    corpora: str | None = None,
    driveId: str | None = None,
    orderBy: str | None = None,
    pageSize: int = 100,
    pageToken: str | None = None,
    fields: str = "*",
    supportsAllDrives: bool = True,
    includeItemsFromAllDrives: bool = False,
) -> FindFileResult:
    """Lists or searches for Google Drive files and folders."""
    del spaces, fields, supportsAllDrives
    files = _sort_files(
        _find_files(
            q=q,
            corpora=corpora,
            drive_id=driveId,
            include_items_from_all_drives=includeItemsFromAllDrives,
        ),
        orderBy,
    )
    projected = [_to_public_file(file) for file in files]
    page, next_token = _paginate(projected, min(pageSize, 1000), pageToken)
    return FindFileResult(files=page, nextPageToken=next_token, incompleteSearch=False)


def googledrive_find_folder(
    name_exact: str | None = None,
    name_contains: str | None = None,
    name_not_contains: str | None = None,
    modified_after: str | None = None,
    starred: bool | None = None,
    full_text_contains: str | None = None,
    full_text_not_contains: str | None = None,
) -> FindFolderResult:
    """Finds folders using name, star, and content filters."""
    threshold = _parse_datetime(modified_after)
    results: list[DriveFile] = []
    for file in get_state().files:
        if file.meta.deleted or file.mimeType != FOLDER_MIME:
            continue
        if name_exact is not None and file.name != name_exact:
            continue
        if name_contains is not None and name_contains.lower() not in file.name.lower():
            continue
        if (
            name_not_contains is not None
            and name_not_contains.lower() in file.name.lower()
        ):
            continue
        if starred is not None and file.starred != starred:
            continue
        if (
            threshold is not None
            and datetime.fromisoformat(file.modifiedTime) <= threshold
        ):
            continue
        content = file.meta.content.lower()
        if full_text_contains is not None and full_text_contains.lower() not in content:
            continue
        if (
            full_text_not_contains is not None
            and full_text_not_contains.lower() in content
        ):
            continue
        results.append(file)
    results = _sort_files(results, "name")
    return FindFolderResult(
        folders=[_to_public_file(file) for file in results],
        resultCount=len(results),
    )


def googledrive_generate_ids(
    type: str | None = None,
    count: int | None = None,
    space: str | None = None,
) -> GenerateIdsResult:
    """Generates reserved file IDs for later create or copy operations."""
    del type
    requested = max(1, min(count or 10, 1000))
    ids: list[str] = []
    for _ in range(requested):
        ids.append(_next_id("generated_id"))
    get_state().generated_ids.extend(ids)
    return GenerateIdsResult(ids=ids, space=space or "drive")


_TOOL_DEFINITIONS: list[ToolDefinition] = [
    ToolDefinition(
        name="GOOGLEDRIVE_ADD_FILE_SHARING_PREFERENCE",
        callable=googledrive_add_file_sharing_preference,
        description="Modifies file sharing permissions for an existing Google Drive file.",
        required_fields=frozenset({"role", "type", "file_id"}),
    ),
    ToolDefinition(
        name="GOOGLEDRIVE_COPY_FILE",
        callable=googledrive_copy_file,
        description="Duplicates an existing Google Drive file.",
        required_fields=frozenset({"file_id"}),
    ),
    ToolDefinition(
        name="GOOGLEDRIVE_CREATE_COMMENT",
        callable=googledrive_create_comment,
        description="Creates a new comment on a Google Drive file.",
        required_fields=frozenset({"file_id", "content"}),
    ),
    ToolDefinition(
        name="GOOGLEDRIVE_CREATE_DRIVE",
        callable=googledrive_create_drive,
        description="Creates a new shared drive.",
        required_fields=frozenset({"name", "requestId"}),
    ),
    ToolDefinition(
        name="GOOGLEDRIVE_CREATE_FILE",
        callable=googledrive_create_file,
        description="Creates a new Google Drive file or folder with metadata.",
    ),
    ToolDefinition(
        name="GOOGLEDRIVE_CREATE_FILE_FROM_TEXT",
        callable=googledrive_create_file_from_text,
        description="Creates a new Google Drive file from plain text content.",
        required_fields=frozenset({"file_name", "text_content"}),
    ),
    ToolDefinition(
        name="GOOGLEDRIVE_CREATE_FOLDER",
        callable=googledrive_create_folder,
        description="Creates a new Google Drive folder.",
        required_fields=frozenset({"folder_name"}),
    ),
    ToolDefinition(
        name="GOOGLEDRIVE_CREATE_REPLY",
        callable=googledrive_create_reply,
        description="Creates a reply on an existing Google Drive comment.",
        required_fields=frozenset({"file_id", "comment_id", "content"}),
    ),
    ToolDefinition(
        name="GOOGLEDRIVE_CREATE_SHORTCUT_TO_FILE",
        callable=googledrive_create_shortcut_to_file,
        description="Creates a shortcut to an existing file or folder.",
        required_fields=frozenset({"name", "target_id"}),
    ),
    ToolDefinition(
        name="GOOGLEDRIVE_DELETE_COMMENT",
        callable=googledrive_delete_comment,
        description="Deletes a comment from a file.",
        required_fields=frozenset({"file_id", "comment_id"}),
    ),
    ToolDefinition(
        name="GOOGLEDRIVE_DELETE_DRIVE",
        callable=googledrive_delete_drive,
        description="Permanently deletes a shared drive and optionally its contents.",
        required_fields=frozenset({"driveId"}),
    ),
    ToolDefinition(
        name="GOOGLEDRIVE_DELETE_PERMISSION",
        callable=googledrive_delete_permission,
        description="Deletes a permission from a file or shared drive.",
        required_fields=frozenset({"file_id", "permission_id"}),
    ),
    ToolDefinition(
        name="GOOGLEDRIVE_DELETE_REPLY",
        callable=googledrive_delete_reply,
        description="Deletes a reply from an existing comment.",
        required_fields=frozenset({"file_id", "comment_id", "reply_id"}),
    ),
    ToolDefinition(
        name="GOOGLEDRIVE_DOWNLOAD_FILE",
        callable=googledrive_download_file,
        description="Downloads a file and optionally exports Google Workspace content.",
        required_fields=frozenset({"file_id"}),
    ),
    ToolDefinition(
        name="GOOGLEDRIVE_EDIT_FILE",
        callable=googledrive_edit_file,
        description="Overwrites the entire text content of an existing file.",
        required_fields=frozenset({"file_id", "content"}),
    ),
    ToolDefinition(
        name="GOOGLEDRIVE_EMPTY_TRASH",
        callable=googledrive_empty_trash,
        description="Permanently deletes trashed files.",
    ),
    ToolDefinition(
        name="GOOGLEDRIVE_FILES_MODIFY_LABELS",
        callable=googledrive_files_modify_labels,
        description="Adds, updates, or removes file labels.",
        required_fields=frozenset({"file_id", "label_modifications"}),
    ),
    ToolDefinition(
        name="GOOGLEDRIVE_FIND_FILE",
        callable=googledrive_find_file,
        description="Lists or searches for Google Drive files and folders.",
    ),
    ToolDefinition(
        name="GOOGLEDRIVE_FIND_FOLDER",
        callable=googledrive_find_folder,
        description="Finds folders using name, star, and content filters.",
    ),
    ToolDefinition(
        name="GOOGLEDRIVE_GENERATE_IDS",
        callable=googledrive_generate_ids,
        description="Generates reserved file IDs for later create or copy operations.",
    ),
]


TOOL_REGISTRY: dict[str, ToolSpec] = build_tool_registry(
    service="googledrive",
    definitions=_TOOL_DEFINITIONS,
)


def get_tool_registry() -> dict[str, ToolSpec]:
    return TOOL_REGISTRY


__all__ = [
    "AddSharingResult",
    "CreateCommentResult",
    "CreateReplyResult",
    "DeletedCommentResult",
    "DeletedDriveResult",
    "DeletedPermissionResult",
    "DeletedReplyResult",
    "DownloadFileResult",
    "EmptyTrashResult",
    "FindFileResult",
    "FindFolderResult",
    "GenerateIdsResult",
    "GoogleDriveMockError",
    "ModifyLabelsResult",
    "PublicDrive",
    "PublicDriveFile",
    "TOOL_REGISTRY",
    "get_tool_registry",
    "googledrive_add_file_sharing_preference",
    "googledrive_copy_file",
    "googledrive_create_comment",
    "googledrive_create_drive",
    "googledrive_create_file",
    "googledrive_create_file_from_text",
    "googledrive_create_folder",
    "googledrive_create_reply",
    "googledrive_create_shortcut_to_file",
    "googledrive_delete_comment",
    "googledrive_delete_drive",
    "googledrive_delete_permission",
    "googledrive_delete_reply",
    "googledrive_download_file",
    "googledrive_edit_file",
    "googledrive_empty_trash",
    "googledrive_files_modify_labels",
    "googledrive_find_file",
    "googledrive_find_folder",
    "googledrive_generate_ids",
    "reset_googledrive_mock_state",
]
