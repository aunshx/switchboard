from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from backend.mock_service import MockService
from pydantic import BaseModel, ConfigDict, Field

BASE_TIMEZONE = "America/New_York"
BASE_NOW = datetime(2026, 4, 8, 9, 0, tzinfo=ZoneInfo(BASE_TIMEZONE))


def _iso(value: datetime) -> str:
    return value.isoformat()


def _dt(
    year: int,
    month: int,
    day: int,
    hour: int = 0,
    minute: int = 0,
    tz_name: str = BASE_TIMEZONE,
) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=ZoneInfo(tz_name))


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ConferenceProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowedConferenceSolutionTypes: list[str]


class CalendarMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 1


class Calendar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = "calendar#calendar"
    etag: str
    id: str
    summary: str
    description: str | None
    location: str | None
    timeZone: str
    conferenceProperties: ConferenceProperties = Field(
        default_factory=lambda: ConferenceProperties(
            allowedConferenceSolutionTypes=["hangoutsMeet"]
        )
    )
    accessRole: str
    primary: bool = False
    deleted: bool = False
    meta: CalendarMeta = Field(default_factory=CalendarMeta)


class CalendarReminderOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: str
    minutes: int


class CalendarNotification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    method: str


class CalendarNotificationSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notifications: list[CalendarNotification]


class CalendarListEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = "calendar#calendarListEntry"
    etag: str
    id: str
    summary: str
    description: str | None
    location: str | None
    timeZone: str
    accessRole: str
    primary: bool = False
    hidden: bool = False
    selected: bool = True
    deleted: bool = False
    backgroundColor: str
    foregroundColor: str
    summaryOverride: str | None = None
    defaultReminders: list[CalendarReminderOverride]
    notificationSettings: CalendarNotificationSettings
    meta: CalendarMeta = Field(default_factory=CalendarMeta)


class EventDateTime(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dateTime: str | None = None
    date: str | None = None
    timeZone: str | None = None


class EventAttendee(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    responseStatus: str


class EventPerson(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    self: bool = False


class EventReminders(BaseModel):
    model_config = ConfigDict(extra="forbid")

    useDefault: bool = True


class ConferenceEntryPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entryPointType: str
    uri: str
    label: str


class ConferenceSolution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    iconUri: str


class ConferenceData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conferenceId: str
    conferenceSolution: ConferenceSolution
    entryPoints: list[ConferenceEntryPoint]


class EventMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calendarId: str
    version: int = 1
    deleted: bool = False


class CalendarEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = "calendar#event"
    etag: str
    id: str
    status: str = "confirmed"
    htmlLink: str
    created: str
    updated: str
    summary: str
    description: str | None = None
    location: str | None = None
    creator: EventPerson
    organizer: EventPerson
    start: EventDateTime
    end: EventDateTime
    eventType: str = "default"
    visibility: str = "default"
    transparency: str = "opaque"
    guestsCanModify: bool = False
    guestsCanInviteOthers: bool = True
    guestsCanSeeOtherGuests: bool = True
    sequence: int = 0
    reminders: EventReminders = Field(default_factory=EventReminders)
    iCalUID: str
    attendees: list[EventAttendee] = Field(default_factory=list)
    recurrence: list[str] | None = None
    conferenceData: ConferenceData | None = None
    focusTimeProperties: dict[str, str] | None = None
    outOfOfficeProperties: dict[str, str] | None = None
    workingLocationProperties: dict[str, str] | None = None
    birthdayProperties: dict[str, str] | None = None
    recurringEventId: str | None = None
    originalStartTime: EventDateTime | None = None
    meta: EventMeta


class CalendarEventLog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calendar_id: str
    events: list[CalendarEvent]


class AclScope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    value: str | None = None


class AclRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = "calendar#aclRule"
    etag: str
    id: str
    role: str
    scope: AclScope
    deleted: bool = False
    version: int = 1


class CalendarAclLog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calendar_id: str
    rules: list[AclRule]


class CalendarSetting(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = "calendar#setting"
    etag: str
    id: str
    value: str
    version: int = 1


class CalendarChannel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = "api#channel"
    id: str
    type: str
    address: str
    token: str | None = None
    params: dict[str, str]
    resourceId: str
    resourceUri: str
    expiration: str
    payload: bool | None = None
    calendarId: str | None = None


class CalendarChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calendarId: str
    version: int


class EventChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: CalendarEvent


class EventChangeLog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calendar_id: str
    changes: list[CalendarEvent]


class CalendarProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str


class CalendarCounters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calendar: int = 300
    event: int = 1000
    acl: int = 50
    channel: int = 200
    sync: int = 10
    calendar_sync: int = 5


class CalendarState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: CalendarProfile
    calendars: list[Calendar]
    calendar_list: list[CalendarListEntry]
    events: list[CalendarEventLog]
    acl_rules: list[CalendarAclLog]
    settings: list[CalendarSetting]
    event_channels: list[CalendarChannel] = Field(default_factory=list)
    settings_channels: list[CalendarChannel] = Field(default_factory=list)
    event_changes: list[EventChangeLog] = Field(default_factory=list)
    calendar_changes: list[CalendarChange] = Field(default_factory=list)
    counters: CalendarCounters = Field(default_factory=CalendarCounters)

    # ----- lookups ---------------------------------------------------------

    def calendar(self, calendar_id: str) -> Calendar | None:
        return next((c for c in self.calendars if c.id == calendar_id), None)

    def calendar_list_entry(self, calendar_id: str) -> CalendarListEntry | None:
        return next((e for e in self.calendar_list if e.id == calendar_id), None)

    def event_log(self, calendar_id: str) -> CalendarEventLog:
        log = next((l for l in self.events if l.calendar_id == calendar_id), None)
        if log is None:
            log = CalendarEventLog(calendar_id=calendar_id, events=[])
            self.events.append(log)
        return log

    def event(self, calendar_id: str, event_id: str) -> CalendarEvent | None:
        log = next((l for l in self.events if l.calendar_id == calendar_id), None)
        if log is None:
            return None
        return next((e for e in log.events if e.id == event_id), None)

    def acl_log(self, calendar_id: str) -> CalendarAclLog:
        log = next((l for l in self.acl_rules if l.calendar_id == calendar_id), None)
        if log is None:
            log = CalendarAclLog(calendar_id=calendar_id, rules=[])
            self.acl_rules.append(log)
        return log

    def acl_rule(self, calendar_id: str, rule_id: str) -> AclRule | None:
        log = next((l for l in self.acl_rules if l.calendar_id == calendar_id), None)
        if log is None:
            return None
        return next((r for r in log.rules if r.id == rule_id), None)

    def event_change_log(self, calendar_id: str) -> EventChangeLog:
        log = next(
            (l for l in self.event_changes if l.calendar_id == calendar_id), None
        )
        if log is None:
            log = EventChangeLog(calendar_id=calendar_id, changes=[])
            self.event_changes.append(log)
        return log


# ---------------------------------------------------------------------------
# Seed helpers (typed)
# ---------------------------------------------------------------------------


def _make_calendar(
    *,
    calendar_id: str,
    summary: str,
    description: str | None,
    time_zone: str,
    location: str | None,
    access_role: str,
    primary: bool = False,
) -> Calendar:
    return Calendar(
        etag=f'"{calendar_id}-etag"',
        id=calendar_id,
        summary=summary,
        description=description,
        location=location,
        timeZone=time_zone,
        accessRole=access_role,
        primary=primary,
    )


def _make_calendar_list_entry(
    *,
    calendar: Calendar,
    hidden: bool = False,
    selected: bool = True,
    background_color: str | None = None,
    foreground_color: str | None = None,
    summary_override: str | None = None,
    default_reminders: list[CalendarReminderOverride] | None = None,
    notification_settings: CalendarNotificationSettings | None = None,
) -> CalendarListEntry:
    return CalendarListEntry(
        etag=f'"{calendar.id}-list-etag"',
        id=calendar.id,
        summary=calendar.summary,
        description=calendar.description,
        location=calendar.location,
        timeZone=calendar.timeZone,
        accessRole=calendar.accessRole,
        primary=calendar.primary,
        hidden=hidden,
        selected=selected,
        backgroundColor=background_color or "#9a9cff",
        foregroundColor=foreground_color or "#1d1d1d",
        summaryOverride=summary_override,
        defaultReminders=default_reminders
        or [CalendarReminderOverride(method="popup", minutes=10)],
        notificationSettings=notification_settings
        or CalendarNotificationSettings(
            notifications=[CalendarNotification(type="eventCreation", method="email")]
        ),
    )


def _make_conference(event_id: str) -> ConferenceData:
    suffix = event_id.replace("_", "")[-6:]
    return ConferenceData(
        conferenceId=f"mock-{suffix}",
        conferenceSolution=ConferenceSolution(
            name="Google Meet",
            iconUri="https://meet.google.com/icon",
        ),
        entryPoints=[
            ConferenceEntryPoint(
                entryPointType="video",
                uri=f"https://meet.google.com/{suffix[:3]}-{suffix[3:]}",
                label="Join Google Meet",
            )
        ],
    )


def _make_event(
    *,
    event_id: str,
    calendar_id: str,
    summary: str,
    start: datetime,
    end: datetime,
    organizer_email: str,
    event_type: str = "default",
    description: str | None = None,
    location: str | None = None,
    attendees: list[str] | None = None,
    recurrence: list[str] | None = None,
    visibility: str = "default",
    transparency: str = "opaque",
    create_meeting_room: bool = False,
    status: str = "confirmed",
    focus_time_properties: dict[str, str] | None = None,
    out_of_office_properties: dict[str, str] | None = None,
    working_location_properties: dict[str, str] | None = None,
    birthday_properties: dict[str, str] | None = None,
) -> CalendarEvent:
    attendees = attendees or []
    created = start - timedelta(days=2)
    is_self = organizer_email == "me@example.com"
    attendees_models = [
        EventAttendee(
            email=email, responseStatus="accepted" if index == 0 else "needsAction"
        )
        for index, email in enumerate(attendees)
    ]
    return CalendarEvent(
        etag=f'"{event_id}-etag"',
        id=event_id,
        status=status,
        htmlLink=f"https://calendar.google.com/calendar/event?eid={event_id}",
        created=_iso(created),
        updated=_iso(created + timedelta(hours=2)),
        summary=summary,
        description=description,
        location=location,
        creator=EventPerson(email=organizer_email, self=is_self),
        organizer=EventPerson(email=organizer_email, self=is_self),
        start=EventDateTime(
            dateTime=_iso(start),
            timeZone=(
                start.tzinfo.key if hasattr(start.tzinfo, "key") else BASE_TIMEZONE
            ),
        ),
        end=EventDateTime(
            dateTime=_iso(end),
            timeZone=end.tzinfo.key if hasattr(end.tzinfo, "key") else BASE_TIMEZONE,
        ),
        eventType=event_type,
        visibility=visibility,
        transparency=transparency,
        iCalUID=f"{event_id}@mock.calendar.local",
        attendees=attendees_models,
        recurrence=recurrence,
        conferenceData=_make_conference(event_id) if create_meeting_room else None,
        focusTimeProperties=focus_time_properties,
        outOfOfficeProperties=out_of_office_properties,
        workingLocationProperties=working_location_properties,
        birthdayProperties=birthday_properties,
        meta=EventMeta(calendarId=calendar_id, deleted=status == "cancelled"),
    )


def _make_acl_rule(
    rule_id: str, role: str, scope_type: str, scope_value: str | None = None
) -> AclRule:
    return AclRule(
        etag=f'"{rule_id}-etag"',
        id=rule_id,
        role=role,
        scope=AclScope(type=scope_type, value=scope_value),
    )


def _make_setting(setting_id: str, value: str) -> CalendarSetting:
    return CalendarSetting(
        etag=f'"{setting_id}-etag"',
        id=setting_id,
        value=value,
    )


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

CALENDAR_PRIMARY = _make_calendar(
    calendar_id="primary",
    summary="Avery Quinn",
    description="Primary work calendar",
    time_zone=BASE_TIMEZONE,
    location="New York, NY",
    access_role="owner",
    primary=True,
)

CALENDAR_ENGINEERING = _make_calendar(
    calendar_id="engineering@group.calendar.google.com",
    summary="Engineering",
    description="Team calendar for launches and rituals",
    time_zone=BASE_TIMEZONE,
    location="Remote",
    access_role="writer",
)

CALENDAR_PERSONAL = _make_calendar(
    calendar_id="personal-projects@group.calendar.google.com",
    summary="Personal Projects",
    description="Side projects and personal commitments",
    time_zone=BASE_TIMEZONE,
    location=None,
    access_role="owner",
)


SEED_CALENDARS: list[Calendar] = [
    CALENDAR_PRIMARY,
    CALENDAR_ENGINEERING,
    CALENDAR_PERSONAL,
]


SEED_CALENDAR_LIST: list[CalendarListEntry] = [
    _make_calendar_list_entry(
        calendar=CALENDAR_PRIMARY,
        background_color="#0ea5e9",
        foreground_color="#f8fafc",
    ),
    _make_calendar_list_entry(
        calendar=CALENDAR_ENGINEERING,
        background_color="#22c55e",
        foreground_color="#052e16",
    ),
    _make_calendar_list_entry(
        calendar=CALENDAR_PERSONAL,
        hidden=False,
        selected=False,
        background_color="#f59e0b",
        foreground_color="#451a03",
    ),
]


EVT_REVENUE_PREP = _make_event(
    event_id="evt_001",
    calendar_id="primary",
    summary="Revenue board prep",
    start=_dt(2026, 4, 8, 13, 0),
    end=_dt(2026, 4, 8, 14, 0),
    organizer_email="me@example.com",
    description="Review Q1 revenue and finalize board talking points.",
    location="Board Room A",
    attendees=["finance@corp.com", "cfo@corp.com"],
)

EVT_MANAGER_11 = _make_event(
    event_id="evt_002",
    calendar_id="primary",
    summary="Manager 1:1",
    start=_dt(2026, 4, 8, 16, 0),
    end=_dt(2026, 4, 8, 16, 30),
    organizer_email="manager@corp.com",
    attendees=["me@example.com"],
    recurrence=["RRULE:FREQ=WEEKLY;COUNT=6;BYDAY=WE"],
)

EVT_DEEP_WORK = _make_event(
    event_id="evt_003",
    calendar_id="primary",
    summary="Deep work block",
    start=_dt(2026, 4, 9, 9, 0),
    end=_dt(2026, 4, 9, 11, 0),
    organizer_email="me@example.com",
    event_type="focusTime",
    description="Heads-down work for orchestration benchmark.",
    focus_time_properties={"autoDeclineMode": "declineNone"},
)

EVT_RENEWAL_CALL = _make_event(
    event_id="evt_004",
    calendar_id="primary",
    summary="Customer renewal call",
    start=_dt(2026, 4, 10, 11, 0),
    end=_dt(2026, 4, 10, 11, 45),
    organizer_email="me@example.com",
    attendees=["ceo@vip-client.com", "sales@corp.com"],
    create_meeting_room=True,
)


EVT_ENG_STANDUP = _make_event(
    event_id="evt_101",
    calendar_id="engineering@group.calendar.google.com",
    summary="Engineering standup",
    start=_dt(2026, 4, 8, 9, 30),
    end=_dt(2026, 4, 8, 10, 0),
    organizer_email="eng-manager@corp.com",
    attendees=["me@example.com", "alex@corp.com", "sara@corp.com"],
    recurrence=["RRULE:FREQ=DAILY;COUNT=5"],
)

EVT_LAUNCH_PLANNING = _make_event(
    event_id="evt_102",
    calendar_id="engineering@group.calendar.google.com",
    summary="Launch planning",
    start=_dt(2026, 4, 8, 15, 0),
    end=_dt(2026, 4, 8, 16, 0),
    organizer_email="pm@corp.com",
    description="Finalize launch readiness and rollback owner.",
    attendees=["me@example.com", "product@corp.com"],
    create_meeting_room=True,
)


EVT_DENTIST = _make_event(
    event_id="evt_201",
    calendar_id="personal-projects@group.calendar.google.com",
    summary="Dentist appointment",
    start=_dt(2026, 4, 11, 10, 0),
    end=_dt(2026, 4, 11, 11, 0),
    organizer_email="me@example.com",
    location="Union Square Dental",
)

EVT_OLD_WORKSHOP = _make_event(
    event_id="evt_202",
    calendar_id="personal-projects@group.calendar.google.com",
    summary="Old workshop",
    start=_dt(2026, 4, 7, 18, 0),
    end=_dt(2026, 4, 7, 19, 0),
    organizer_email="me@example.com",
    status="cancelled",
)


SEED_EVENTS: list[CalendarEventLog] = [
    CalendarEventLog(
        calendar_id="primary",
        events=[EVT_REVENUE_PREP, EVT_MANAGER_11, EVT_DEEP_WORK, EVT_RENEWAL_CALL],
    ),
    CalendarEventLog(
        calendar_id="engineering@group.calendar.google.com",
        events=[EVT_ENG_STANDUP, EVT_LAUNCH_PLANNING],
    ),
    CalendarEventLog(
        calendar_id="personal-projects@group.calendar.google.com",
        events=[EVT_DENTIST, EVT_OLD_WORKSHOP],
    ),
]


SEED_ACL: list[CalendarAclLog] = [
    CalendarAclLog(
        calendar_id="primary",
        rules=[
            _make_acl_rule("default", "reader", "default"),
            _make_acl_rule(
                "user:finance@corp.com", "reader", "user", "finance@corp.com"
            ),
        ],
    ),
    CalendarAclLog(
        calendar_id="engineering@group.calendar.google.com",
        rules=[
            _make_acl_rule("default", "reader", "default"),
            _make_acl_rule("group:eng@corp.com", "writer", "group", "eng@corp.com"),
        ],
    ),
    CalendarAclLog(
        calendar_id="personal-projects@group.calendar.google.com",
        rules=[
            _make_acl_rule("default", "none", "default"),
        ],
    ),
]


SEED_SETTINGS: list[CalendarSetting] = [
    _make_setting("timezone", BASE_TIMEZONE),
    _make_setting("locale", "en"),
    _make_setting("weekStart", "1"),
    _make_setting("hideWeekends", "false"),
]


def _build_seed_state() -> CalendarState:
    state = CalendarState(
        profile=CalendarProfile(email="me@example.com"),
        calendars=[c.model_copy(deep=True) for c in SEED_CALENDARS],
        calendar_list=[c.model_copy(deep=True) for c in SEED_CALENDAR_LIST],
        events=[l.model_copy(deep=True) for l in SEED_EVENTS],
        acl_rules=[l.model_copy(deep=True) for l in SEED_ACL],
        settings=[s.model_copy(deep=True) for s in SEED_SETTINGS],
        event_channels=[],
        settings_channels=[],
        event_changes=[
            EventChangeLog(calendar_id=c.id, changes=[]) for c in SEED_CALENDARS
        ],
        calendar_changes=[],
    )
    # Record initial event changes (sync seed).
    for log in state.events:
        for event in log.events:
            state.counters.sync += 1
            event_copy = event.model_copy(deep=True)
            event_copy.meta.version = state.counters.sync
            state.event_change_log(log.calendar_id).changes.append(event_copy)
    # Record initial calendar changes.
    for calendar in state.calendars:
        state.counters.calendar_sync += 1
        state.calendar_changes.append(
            CalendarChange(calendarId=calendar.id, version=state.counters.calendar_sync)
        )
    return state


class GoogleCalendarMockState(MockService[CalendarState]):
    def _seed_state(self) -> CalendarState:
        return _build_seed_state()


SERVICE = GoogleCalendarMockState()


def get_state() -> CalendarState:
    return SERVICE.get_state()


def reset_googlecalendar_mock_state() -> None:
    SERVICE.reset()


def snapshot_state() -> CalendarState:
    return SERVICE.snapshot()
