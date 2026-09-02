from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from backend.mock_service import MockService
from pydantic import BaseModel, ConfigDict, Field

BASE_TIMEZONE = "America/New_York"
BASE_NOW = datetime(2026, 4, 8, 9, 30, tzinfo=ZoneInfo(BASE_TIMEZONE))

FOLDER_MIME = "application/vnd.google-apps.folder"
DOC_MIME = "application/vnd.google-apps.document"
SHORTCUT_MIME = "application/vnd.google-apps.shortcut"


def _iso(value: datetime) -> str:
    return value.isoformat()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class DriveUser(BaseModel):
    model_config = ConfigDict(extra="forbid")

    displayName: str
    emailAddress: str
    me: bool = False


class DrivePermission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: str = "drive#permission"
    role: str
    type: str
    emailAddress: str | None = None
    domain: str | None = None
    allowFileDiscovery: bool | None = None


class DriveShortcutDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    targetId: str
    targetMimeType: str


class DriveExportLink(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mimeType: str
    url: str


class DriveLabelFieldModification(BaseModel):
    """Field-level change inside a label modification request."""

    model_config = ConfigDict(extra="forbid")

    field_id: str
    kind: str
    set_text_values: list[str]


class DriveLabelModification(BaseModel):
    """One label modification for a Drive file."""

    model_config = ConfigDict(extra="forbid")

    label_id: str
    remove_label: bool
    field_modifications: list[DriveLabelFieldModification]


class DriveFileLabel(BaseModel):
    """A label attached to a file."""

    model_config = ConfigDict(extra="forbid")

    id: str
    revisionId: str
    field_modifications: list[DriveLabelFieldModification] = Field(default_factory=list)


class DriveFileMeta(BaseModel):
    """Internal-only metadata kept alongside a file."""

    model_config = ConfigDict(extra="forbid")

    driveId: str | None = None
    content: str = ""
    deleted: bool = False


class DriveFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: str = "drive#file"
    name: str
    mimeType: str
    description: str | None = None
    parents: list[str]
    starred: bool = False
    trashed: bool = False
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
    shortcutDetails: DriveShortcutDetails | None = None
    exportLinks: list[DriveExportLink] = Field(default_factory=list)
    meta: DriveFileMeta = Field(default_factory=DriveFileMeta)


class DriveBackgroundImage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    xCoordinate: float
    yCoordinate: float
    width: float


class DriveRestrictions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adminManagedRestrictions: bool = False
    copyRequiresWriterPermission: bool = False
    domainUsersOnly: bool = False
    driveMembersOnly: bool = False
    sharingFoldersRequiresOrganizerPermission: bool = False


class DriveCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canAddChildren: bool = True
    canComment: bool = True
    canDeleteDrive: bool = True
    canDownload: bool = True
    canListChildren: bool = True
    canManageMembers: bool = True


class Drive(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: str = "drive#drive"
    name: str
    hidden: bool = False
    themeId: str | None = None
    colorRgb: str | None = None
    backgroundImageFile: DriveBackgroundImage | None = None
    createdTime: str
    restrictions: DriveRestrictions = Field(default_factory=DriveRestrictions)
    capabilities: DriveCapabilities = Field(default_factory=DriveCapabilities)
    permissions: list[DrivePermission]
    deleted: bool = False


class DriveReply(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: str = "drive#reply"
    content: str
    createdTime: str
    modifiedTime: str
    action: str | None = None
    author: DriveUser


class DriveQuotedFileContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    mimeType: str = "text/plain"


class DriveComment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: str = "drive#comment"
    content: str
    createdTime: str
    modifiedTime: str
    deleted: bool = False
    resolved: bool = False
    author: DriveUser
    replies: list[DriveReply] = Field(default_factory=list)
    anchor: str | None = None
    quotedFileContent: DriveQuotedFileContent | None = None


class FileCommentLog(BaseModel):
    """All comments on one Drive file."""

    model_config = ConfigDict(extra="forbid")

    file_id: str
    comments: list[DriveComment]


class DriveRequestId(BaseModel):
    """Maps a client-supplied requestId to the drive that was created for it."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    drive_id: str


class DriveProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    displayName: str


class DriveCounters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: int = 100
    drive: int = 10
    permission: int = 20
    comment: int = 50
    reply: int = 80
    generated_id: int = 300


class DriveState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: DriveProfile
    drives: list[Drive]
    files: list[DriveFile]
    comments: list[FileCommentLog]
    request_ids: list[DriveRequestId]
    generated_ids: list[str] = Field(default_factory=list)
    counters: DriveCounters = Field(default_factory=DriveCounters)

    # ----- lookups ---------------------------------------------------------

    def file(self, file_id: str) -> DriveFile | None:
        return next((f for f in self.files if f.id == file_id), None)

    def drive(self, drive_id: str) -> Drive | None:
        return next((d for d in self.drives if d.id == drive_id), None)

    def comment_log(self, file_id: str) -> FileCommentLog:
        existing = next((c for c in self.comments if c.file_id == file_id), None)
        if existing is None:
            existing = FileCommentLog(file_id=file_id, comments=[])
            self.comments.append(existing)
        return existing

    def comment(self, file_id: str, comment_id: str) -> DriveComment | None:
        log = next((c for c in self.comments if c.file_id == file_id), None)
        if log is None:
            return None
        return next((c for c in log.comments if c.id == comment_id), None)

    def request_id(self, request_id: str) -> DriveRequestId | None:
        return next((r for r in self.request_ids if r.request_id == request_id), None)


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


ME_USER = DriveUser(displayName="Avery Quinn", emailAddress="me@example.com", me=True)


def _make_file(
    *,
    file_id: str,
    name: str,
    mime_type: str,
    parents: list[str] | None = None,
    description: str | None = None,
    starred: bool = False,
    trashed: bool = False,
    drive_id: str | None = None,
    text_content: str = "",
    shortcut_target_id: str | None = None,
    shortcut_target_mime_type: str | None = None,
    permissions: list[DrivePermission] | None = None,
    labels: list[DriveFileLabel] | None = None,
    created_offset_days: int = 0,
    modified_offset_hours: int = 0,
) -> DriveFile:
    created_time = BASE_NOW - timedelta(days=created_offset_days)
    modified_time = created_time + timedelta(hours=modified_offset_hours)
    perms = permissions or [
        DrivePermission(
            id="perm_owner", role="owner", type="user", emailAddress="me@example.com"
        )
    ]
    shared = any(p.type != "user" or p.emailAddress != "me@example.com" for p in perms)
    export_links: list[DriveExportLink] = []
    if mime_type == DOC_MIME:
        export_links = [
            DriveExportLink(
                mimeType="application/pdf",
                url=f"https://drive.google.com/export/{file_id}.pdf",
            ),
            DriveExportLink(
                mimeType="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                url=f"https://drive.google.com/export/{file_id}.docx",
            ),
            DriveExportLink(
                mimeType="text/plain",
                url=f"https://drive.google.com/export/{file_id}.txt",
            ),
        ]
    shortcut = None
    if mime_type == SHORTCUT_MIME and shortcut_target_id:
        shortcut = DriveShortcutDetails(
            targetId=shortcut_target_id,
            targetMimeType=shortcut_target_mime_type or "application/octet-stream",
        )
    return DriveFile(
        id=file_id,
        name=name,
        mimeType=mime_type,
        description=description,
        parents=list(parents or ["root"]),
        starred=starred,
        trashed=trashed,
        createdTime=_iso(created_time),
        modifiedTime=_iso(modified_time),
        owners=[ME_USER.model_copy()],
        lastModifyingUser=ME_USER.model_copy(),
        shared=shared,
        webViewLink=f"https://drive.google.com/file/d/{file_id}/view",
        iconLink="https://drive-thirdparty.googleusercontent.com/16/type/application/octet-stream",
        quotaBytesUsed=str(max(len(text_content.encode("utf-8")), 1)),
        size=str(len(text_content.encode("utf-8"))),
        permissions=[p.model_copy() for p in perms],
        labels=list(labels or []),
        driveId=drive_id,
        shortcutDetails=shortcut,
        exportLinks=export_links,
        meta=DriveFileMeta(driveId=drive_id, content=text_content),
    )


def _make_drive(
    *,
    drive_id: str,
    name: str,
    hidden: bool = False,
    theme_id: str | None = None,
    color_rgb: str | None = None,
    background_image_file: DriveBackgroundImage | None = None,
) -> Drive:
    return Drive(
        id=drive_id,
        name=name,
        hidden=hidden,
        themeId=theme_id,
        colorRgb=color_rgb,
        backgroundImageFile=background_image_file,
        createdTime=_iso(BASE_NOW - timedelta(days=20)),
        permissions=[
            DrivePermission(
                id="perm_drive_owner",
                role="organizer",
                type="user",
                emailAddress="me@example.com",
            )
        ],
    )


def _make_reply(
    reply_id: str, *, content: str, action: str | None = None
) -> DriveReply:
    return DriveReply(
        id=reply_id,
        content=content,
        createdTime=_iso(BASE_NOW),
        modifiedTime=_iso(BASE_NOW),
        action=action,
        author=ME_USER.model_copy(),
    )


def _make_comment(
    comment_id: str,
    *,
    content: str,
    anchor: str | None = None,
    quoted_value: str | None = None,
    quoted_mime_type: str = "text/plain",
    replies: list[DriveReply] | None = None,
    author: DriveUser | None = None,
) -> DriveComment:
    return DriveComment(
        id=comment_id,
        content=content,
        createdTime=_iso(BASE_NOW),
        modifiedTime=_iso(BASE_NOW),
        author=author
        or DriveUser(displayName="Morgan Lee", emailAddress="morgan@corp.com"),
        replies=list(replies or []),
        anchor=anchor,
        quotedFileContent=(
            DriveQuotedFileContent(value=quoted_value, mimeType=quoted_mime_type)
            if quoted_value
            else None
        ),
    )


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

DRIVE_PRODUCT_LAUNCH = _make_drive(
    drive_id="drive_001",
    name="Product Launch",
    hidden=False,
    theme_id="blue",
    color_rgb="#4F8EF7",
)

FOLDER_BOARD_DOCS = _make_file(
    file_id="fld_001",
    name="Board Docs",
    mime_type=FOLDER_MIME,
    description="Quarterly board materials",
    starred=True,
    created_offset_days=12,
)

FOLDER_LAUNCH_ASSETS = _make_file(
    file_id="fld_002",
    name="Launch Assets",
    mime_type=FOLDER_MIME,
    parents=["root"],
    drive_id="drive_001",
    created_offset_days=8,
)

FILE_BOARD_DOC = _make_file(
    file_id="file_001",
    name="Q1 Board Summary",
    mime_type=DOC_MIME,
    parents=["fld_001"],
    description="Board narrative for quarterly revenue review",
    starred=True,
    text_content=(
        "Revenue finished 8 percent above plan. Enterprise upsell led the quarter "
        "and renewal risk fell below forecast."
    ),
    permissions=[
        DrivePermission(
            id="perm_owner", role="owner", type="user", emailAddress="me@example.com"
        ),
        DrivePermission(
            id="perm_finance",
            role="reader",
            type="user",
            emailAddress="finance@corp.com",
        ),
    ],
    labels=[
        DriveFileLabel(
            id="LBL_REVENUE",
            revisionId="1",
            field_modifications=[
                DriveLabelFieldModification(
                    field_id="stage",
                    kind="drive#fieldModification",
                    set_text_values=["approved"],
                )
            ],
        )
    ],
    created_offset_days=10,
    modified_offset_hours=5,
)

FILE_MODEL_CSV = _make_file(
    file_id="file_002",
    name="Revenue Model.csv",
    mime_type="text/csv",
    parents=["fld_001"],
    text_content="region,revenue\nwest,1280000\neast,1040000\nenterprise,2120000\n",
    created_offset_days=9,
    modified_offset_hours=4,
)

FILE_LAUNCH_BRIEF = _make_file(
    file_id="file_003",
    name="Launch Brief.md",
    mime_type="text/markdown",
    parents=["fld_002"],
    drive_id="drive_001",
    text_content=(
        "# Launch Brief\nRollback owner: Avery Quinn\nWebinar QA remains the main launch risk.\n"
    ),
    permissions=[
        DrivePermission(
            id="perm_owner_launch",
            role="owner",
            type="user",
            emailAddress="me@example.com",
        ),
        DrivePermission(
            id="perm_anyone_launch",
            role="reader",
            type="anyone",
            allowFileDiscovery=False,
        ),
    ],
    created_offset_days=5,
    modified_offset_hours=3,
)

FILE_OLD_NOTES = _make_file(
    file_id="file_004",
    name="Old Notes.txt",
    mime_type="text/plain",
    parents=["root"],
    trashed=True,
    text_content="Deprecated launch checklist draft.",
    created_offset_days=40,
    modified_offset_hours=1,
)

REPLY_BOARD_SUMMARY = _make_reply(
    "rpl_001",
    content="Yes, I will revise the narrative and add more enterprise detail.",
)

COMMENT_BOARD_TIGHTEN = _make_comment(
    "cmt_001",
    content="Can we tighten the board summary before Friday?",
    anchor='{"type":"line","line":12}',
    quoted_value="Revenue finished 8 percent above plan.",
    replies=[REPLY_BOARD_SUMMARY],
)

COMMENT_LAUNCH_ROLLBACK = _make_comment(
    "cmt_002",
    content="Please confirm the rollback owner in this brief.",
)


SEED_FILES: list[DriveFile] = [
    FOLDER_BOARD_DOCS,
    FOLDER_LAUNCH_ASSETS,
    FILE_BOARD_DOC,
    FILE_MODEL_CSV,
    FILE_LAUNCH_BRIEF,
    FILE_OLD_NOTES,
]

SEED_DRIVES: list[Drive] = [DRIVE_PRODUCT_LAUNCH]

SEED_COMMENTS: list[FileCommentLog] = [
    FileCommentLog(file_id="file_001", comments=[COMMENT_BOARD_TIGHTEN]),
    FileCommentLog(file_id="file_003", comments=[COMMENT_LAUNCH_ROLLBACK]),
]

SEED_REQUEST_IDS: list[DriveRequestId] = [
    DriveRequestId(request_id="drive-create-001", drive_id="drive_001"),
]


SEED_PROFILE = DriveProfile(email="me@example.com", displayName="Avery Quinn")


SEED_STATE = DriveState(
    profile=SEED_PROFILE,
    drives=SEED_DRIVES,
    files=SEED_FILES,
    comments=SEED_COMMENTS,
    request_ids=SEED_REQUEST_IDS,
)


class GoogleDriveMockState(MockService[DriveState]):
    def _seed_state(self) -> DriveState:
        return SEED_STATE.model_copy(deep=True)


SERVICE = GoogleDriveMockState()


def get_state() -> DriveState:
    return SERVICE.get_state()


def reset_googledrive_mock_state() -> None:
    SERVICE.reset()


def snapshot_state() -> DriveState:
    return SERVICE.snapshot()
