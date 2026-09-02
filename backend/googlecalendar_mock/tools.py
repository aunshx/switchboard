from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime, time, timedelta, timezone
from typing import Any, TypeVar
from zoneinfo import ZoneInfo

from backend.tooling import ToolDefinition, ToolSpec, build_tool_registry
from pydantic import BaseModel, ConfigDict, Field

from .state import (
    BASE_NOW,
    BASE_TIMEZONE,
    AclRule,
    AclScope,
    Calendar,
    CalendarAclLog,
    CalendarChange,
    CalendarChannel,
    CalendarEvent,
    CalendarEventLog,
    CalendarListEntry,
    CalendarNotification,
    CalendarNotificationSettings,
    CalendarReminderOverride,
    CalendarSetting,
    EventAttendee,
    EventChangeLog,
    EventDateTime,
    EventMeta,
    EventPerson,
    _make_acl_rule,
    _make_calendar,
    _make_calendar_list_entry,
    _make_event,
    get_state,
    reset_googlecalendar_mock_state,
)


class GoogleCalendarMockError(ValueError):
    """Raised when a Google Calendar mock tool receives invalid input or missing resources."""


T = TypeVar("T")


# ---------------------------------------------------------------------------
# Argument-side models
# ---------------------------------------------------------------------------


class CalendarAclScope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    value: str


class CalendarFreeBusyRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str


# ---------------------------------------------------------------------------
# Public projections (strip internal meta)
# ---------------------------------------------------------------------------


class PublicCalendar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    etag: str
    id: str
    summary: str
    description: str | None
    location: str | None
    timeZone: str
    conferenceProperties: dict
    accessRole: str
    primary: bool
    deleted: bool


class PublicCalendarListEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    etag: str
    id: str
    summary: str
    description: str | None
    location: str | None
    timeZone: str
    accessRole: str
    primary: bool
    hidden: bool
    selected: bool
    deleted: bool
    backgroundColor: str
    foregroundColor: str
    summaryOverride: str | None
    defaultReminders: list[CalendarReminderOverride]
    notificationSettings: CalendarNotificationSettings


class PublicAclRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    etag: str
    id: str
    role: str
    scope: AclScope


class PublicCalendarSetting(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    etag: str
    id: str
    value: str


class PublicEvent(BaseModel):
    """Public event projection — meta stripped, optional fields omitted when None."""

    model_config = ConfigDict(extra="forbid")

    kind: str
    etag: str
    id: str
    status: str
    htmlLink: str
    created: str
    updated: str
    summary: str
    description: str | None
    location: str | None
    creator: EventPerson
    organizer: EventPerson
    start: EventDateTime
    end: EventDateTime
    eventType: str
    visibility: str
    transparency: str
    guestsCanModify: bool
    guestsCanInviteOthers: bool
    guestsCanSeeOtherGuests: bool
    sequence: int
    reminders: dict
    iCalUID: str
    attendees: list[EventAttendee] = Field(default_factory=list)
    recurrence: list[str] | None = None
    conferenceData: dict | None = None
    focusTimeProperties: dict | None = None
    outOfOfficeProperties: dict | None = None
    workingLocationProperties: dict | None = None
    birthdayProperties: dict | None = None
    recurringEventId: str | None = None
    originalStartTime: EventDateTime | None = None


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


class EventsListResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = "calendar#events"
    items: list[PublicEvent]
    nextPageToken: str | None
    nextSyncToken: str | None = None


class CalendarsListResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = "calendar#calendarList"
    items: list[PublicCalendarListEntry]
    nextPageToken: str | None
    nextSyncToken: str | None = None


class AclListResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = "calendar#acl"
    items: list[PublicAclRule]
    nextPageToken: str | None


class SettingsListResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = "calendar#settings"
    items: list[PublicCalendarSetting]
    nextPageToken: str | None


class DeletedCalendarResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deletedCalendarId: str


class DeletedEventResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deletedEventId: str
    calendarId: str


class ClearCalendarResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clearedCalendarId: str
    clearedEvents: int


class FindEventsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: list[PublicEvent]
    nextPageToken: str | None
    resultSizeEstimate: int


class FreeBusyTimePeriod(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: str
    end: str


class CalendarBusy(BaseModel):
    """One calendar's busy entries inside a free/busy response."""

    model_config = ConfigDict(extra="forbid")

    id: str
    busy: list[FreeBusyTimePeriod]
    timeZone: str | None = None


class FreeBusyCalendarsMap(BaseModel):
    """Map-like helper exposing per-calendar busy lookup as subscript access."""

    model_config = ConfigDict(extra="forbid")

    entries: list[CalendarBusy]

    def __getitem__(self, calendar_id: str) -> CalendarBusy:
        for entry in self.entries:
            if entry.id == calendar_id:
                return entry
        raise KeyError(calendar_id)


class FreeBusyResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = "calendar#freeBusy"
    timeMin: str
    timeMax: str
    calendars: FreeBusyCalendarsMap


class FreeSlot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: str
    end: str


class FindFreeSlotsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timeMin: str
    timeMax: str
    calendars: FreeBusyCalendarsMap
    freeSlots: list[FreeSlot]


class CurrentDateTimeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dateTime: str
    timezoneOffsetHours: int


class PublicChannel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    id: str
    type: str
    address: str
    token: str | None
    params: dict[str, str]
    resourceId: str
    resourceUri: str
    expiration: str
    payload: bool | None = None
    calendarId: str | None = None


# ---------------------------------------------------------------------------
# Projection helpers
# ---------------------------------------------------------------------------


def _to_public_calendar(calendar: Calendar) -> PublicCalendar:
    return PublicCalendar(
        kind=calendar.kind,
        etag=calendar.etag,
        id=calendar.id,
        summary=calendar.summary,
        description=calendar.description,
        location=calendar.location,
        timeZone=calendar.timeZone,
        conferenceProperties=calendar.conferenceProperties.model_dump(),
        accessRole=calendar.accessRole,
        primary=calendar.primary,
        deleted=calendar.deleted,
    )


def _to_public_calendar_list_entry(entry: CalendarListEntry) -> PublicCalendarListEntry:
    return PublicCalendarListEntry(
        kind=entry.kind,
        etag=entry.etag,
        id=entry.id,
        summary=entry.summary,
        description=entry.description,
        location=entry.location,
        timeZone=entry.timeZone,
        accessRole=entry.accessRole,
        primary=entry.primary,
        hidden=entry.hidden,
        selected=entry.selected,
        deleted=entry.deleted,
        backgroundColor=entry.backgroundColor,
        foregroundColor=entry.foregroundColor,
        summaryOverride=entry.summaryOverride,
        defaultReminders=[r.model_copy() for r in entry.defaultReminders],
        notificationSettings=entry.notificationSettings.model_copy(deep=True),
    )


def _to_public_acl_rule(rule: AclRule) -> PublicAclRule:
    return PublicAclRule(
        kind=rule.kind,
        etag=rule.etag,
        id=rule.id,
        role=rule.role,
        scope=rule.scope.model_copy(),
    )


def _to_public_setting(setting: CalendarSetting) -> PublicCalendarSetting:
    return PublicCalendarSetting(
        kind=setting.kind,
        etag=setting.etag,
        id=setting.id,
        value=setting.value,
    )


def _to_public_event(
    event: CalendarEvent, *, max_attendees: int | None = None
) -> PublicEvent:
    attendees = (
        event.attendees if max_attendees is None else event.attendees[:max_attendees]
    )
    return PublicEvent(
        kind=event.kind,
        etag=event.etag,
        id=event.id,
        status=event.status,
        htmlLink=event.htmlLink,
        created=event.created,
        updated=event.updated,
        summary=event.summary,
        description=event.description,
        location=event.location,
        creator=event.creator.model_copy(),
        organizer=event.organizer.model_copy(),
        start=event.start.model_copy(),
        end=event.end.model_copy(),
        eventType=event.eventType,
        visibility=event.visibility,
        transparency=event.transparency,
        guestsCanModify=event.guestsCanModify,
        guestsCanInviteOthers=event.guestsCanInviteOthers,
        guestsCanSeeOtherGuests=event.guestsCanSeeOtherGuests,
        sequence=event.sequence,
        reminders=event.reminders.model_dump(),
        iCalUID=event.iCalUID,
        attendees=[a.model_copy() for a in attendees],
        recurrence=list(event.recurrence) if event.recurrence else None,
        conferenceData=(
            event.conferenceData.model_dump() if event.conferenceData else None
        ),
        focusTimeProperties=(
            dict(event.focusTimeProperties) if event.focusTimeProperties else None
        ),
        outOfOfficeProperties=(
            dict(event.outOfOfficeProperties) if event.outOfOfficeProperties else None
        ),
        workingLocationProperties=(
            dict(event.workingLocationProperties)
            if event.workingLocationProperties
            else None
        ),
        birthdayProperties=(
            dict(event.birthdayProperties) if event.birthdayProperties else None
        ),
        recurringEventId=event.recurringEventId,
        originalStartTime=(
            event.originalStartTime.model_copy() if event.originalStartTime else None
        ),
    )


def _to_public_channel(channel: CalendarChannel) -> PublicChannel:
    return PublicChannel(
        kind=channel.kind,
        id=channel.id,
        type=channel.type,
        address=channel.address,
        token=channel.token,
        params=dict(channel.params),
        resourceId=channel.resourceId,
        resourceUri=channel.resourceUri,
        expiration=channel.expiration,
        payload=channel.payload,
        calendarId=channel.calendarId,
    )


# ---------------------------------------------------------------------------
# Datetime + query helpers
# ---------------------------------------------------------------------------


def parse_datetime(
    value: str | None, default_tz: str = BASE_TIMEZONE, *, end_of_day: bool = False
) -> datetime | None:
    if value in (None, ""):
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise GoogleCalendarMockError(f"Invalid datetime value: {value}") from exc
    if parsed.tzinfo is None:
        if "T" in normalized:
            parsed = parsed.replace(tzinfo=ZoneInfo(default_tz))
        else:
            parsed = datetime.combine(
                parsed.date(),
                time.max if end_of_day else time.min,
                tzinfo=ZoneInfo(default_tz),
            )
    elif "T" not in value:
        parsed = datetime.combine(
            parsed.date(),
            time.max if end_of_day else time.min,
            tzinfo=parsed.tzinfo,
        )
    return parsed


def format_datetime(value: datetime) -> str:
    return value.isoformat()


def _event_bounds(event: CalendarEvent) -> tuple[datetime, datetime]:
    start_value = event.start.dateTime or event.start.date
    end_value = event.end.dateTime or event.end.date
    start = parse_datetime(start_value, event.start.timeZone or BASE_TIMEZONE)
    end = parse_datetime(end_value, event.end.timeZone or BASE_TIMEZONE)
    if start is None or end is None:
        raise GoogleCalendarMockError(f"Event {event.id} missing start or end")
    return start, end


def _overlaps(
    event: CalendarEvent, time_min: datetime | None, time_max: datetime | None
) -> bool:
    start, end = _event_bounds(event)
    if time_min and end <= time_min:
        return False
    if time_max and start >= time_max:
        return False
    return True


def _event_matches_text(event: CalendarEvent, query: str | None) -> bool:
    if not query:
        return True
    searchable = " ".join(
        filter(
            None,
            [
                event.summary,
                event.description,
                event.location,
                " ".join(a.email for a in event.attendees),
            ],
        )
    ).lower()
    return all(token.lower() in searchable for token in query.split())


_DAY_TO_INDEX = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}


def _parse_rrule(recurrence: list[str]) -> dict[str, str]:
    rule = next((item for item in recurrence if item.startswith("RRULE:")), "")
    if not rule:
        return {}
    payload = rule.split(":", 1)[1]
    parsed: dict[str, str] = {}
    for segment in payload.split(";"):
        if "=" in segment:
            key, value = segment.split("=", 1)
            parsed[key] = value
    return parsed


def _step_for_rule(rule: dict[str, str]) -> timedelta:
    interval = int(rule.get("INTERVAL", "1"))
    freq = rule.get("FREQ", "DAILY")
    if freq == "WEEKLY":
        return timedelta(weeks=interval)
    return timedelta(days=interval)


def _align_to_byday(start: datetime, byday: str | None) -> datetime:
    if not byday:
        return start
    targets = [
        _DAY_TO_INDEX[token] for token in byday.split(",") if token in _DAY_TO_INDEX
    ]
    if not targets:
        return start
    current = start
    for _ in range(7):
        if current.weekday() in targets:
            return current
        current += timedelta(days=1)
    return start


def _expand_event_instances(
    event: CalendarEvent,
    *,
    time_min: datetime | None = None,
    time_max: datetime | None = None,
    original_start: str | None = None,
) -> list[CalendarEvent]:
    if not event.recurrence:
        return [event] if _overlaps(event, time_min, time_max) else []
    rule = _parse_rrule(event.recurrence)
    if not rule:
        return [event] if _overlaps(event, time_min, time_max) else []
    start, end = _event_bounds(event)
    duration = end - start
    current_start = _align_to_byday(start, rule.get("BYDAY"))
    count = int(rule.get("COUNT", "10"))
    step = _step_for_rule(rule)
    instances: list[CalendarEvent] = []
    for _ in range(count):
        instance_end = current_start + duration
        if (time_min is None or instance_end > time_min) and (
            time_max is None or current_start < time_max
        ):
            stamp = current_start.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
            instance = event.model_copy(deep=True)
            instance.id = f"{event.id}_{stamp}"
            instance.recurringEventId = event.id
            tz = event.start.timeZone or BASE_TIMEZONE
            instance.originalStartTime = EventDateTime(
                dateTime=format_datetime(current_start), timeZone=tz
            )
            instance.start = EventDateTime(
                dateTime=format_datetime(current_start), timeZone=tz
            )
            instance.end = EventDateTime(
                dateTime=format_datetime(instance_end),
                timeZone=event.end.timeZone or BASE_TIMEZONE,
            )
            if original_start and instance.originalStartTime.dateTime != original_start:
                current_start += step
                continue
            instances.append(instance)
        current_start += step
    return instances


def _list_calendar_events(
    calendar_id: str,
    *,
    show_deleted: bool = False,
    single_events: bool = False,
    time_min: datetime | None = None,
    time_max: datetime | None = None,
    query: str | None = None,
    i_cal_uid: str | None = None,
    updated_min: datetime | None = None,
    event_types: list[str] | None = None,
    max_attendees: int | None = None,
) -> list[CalendarEvent]:
    state = get_state()
    log = state.event_log(calendar_id)
    out: list[CalendarEvent] = []
    for event in log.events:
        if not show_deleted and event.status == "cancelled":
            continue
        if i_cal_uid and event.iCalUID != i_cal_uid:
            continue
        if event_types and event.eventType not in event_types:
            continue
        if updated_min:
            updated = parse_datetime(
                event.updated, event.start.timeZone or BASE_TIMEZONE
            )
            if updated and updated < updated_min:
                continue
        expanded = (
            _expand_event_instances(event, time_min=time_min, time_max=time_max)
            if single_events
            else [event]
        )
        for candidate in expanded:
            if not _overlaps(candidate, time_min, time_max):
                continue
            if not _event_matches_text(candidate, query):
                continue
            if max_attendees is not None:
                trimmed = candidate.model_copy(deep=True)
                trimmed.attendees = trimmed.attendees[:max_attendees]
                out.append(trimmed)
            else:
                out.append(candidate)
    return out


def _sort_events(
    events: list[CalendarEvent], order_by: str | None
) -> list[CalendarEvent]:
    if order_by == "updated":
        return sorted(events, key=lambda item: item.updated)
    return sorted(
        events,
        key=lambda item: (item.start.dateTime or item.start.date or ""),
    )


def _paginate(
    items: list[T], max_results: int | None, page_token: str | None
) -> tuple[list[T], str | None]:
    limit = max_results or len(items) or 1
    start = int(page_token or "0")
    end = start + limit
    next_token = str(end) if end < len(items) else None
    return items[start:end], next_token


def _merge_busy_slots(
    busy_slots: list[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    if not busy_slots:
        return []
    ordered = sorted(busy_slots, key=lambda item: item[0])
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _compute_free_slots(
    busy_slots: list[tuple[datetime, datetime]],
    time_min: datetime,
    time_max: datetime,
) -> list[FreeSlot]:
    merged = _merge_busy_slots(busy_slots)
    cursor = time_min
    free: list[FreeSlot] = []
    for start, end in merged:
        if cursor < start:
            free.append(
                FreeSlot(start=format_datetime(cursor), end=format_datetime(start))
            )
        cursor = max(cursor, end)
    if cursor < time_max:
        free.append(
            FreeSlot(start=format_datetime(cursor), end=format_datetime(time_max))
        )
    return free


def _build_free_busy(
    calendar_ids: list[str],
    *,
    time_min: datetime,
    time_max: datetime,
    time_zone: str | None = None,
) -> tuple[FreeBusyCalendarsMap, list[tuple[datetime, datetime]]]:
    entries: list[CalendarBusy] = []
    busy_slots: list[tuple[datetime, datetime]] = []
    for calendar_id in calendar_ids:
        events = _list_calendar_events(
            calendar_id,
            show_deleted=False,
            single_events=True,
            time_min=time_min,
            time_max=time_max,
        )
        calendar_busy: list[FreeBusyTimePeriod] = []
        for event in events:
            start, end = _event_bounds(event)
            calendar_busy.append(
                FreeBusyTimePeriod(
                    start=format_datetime(start), end=format_datetime(end)
                )
            )
            busy_slots.append((start, end))
        entries.append(
            CalendarBusy(id=calendar_id, busy=calendar_busy, timeZone=time_zone)
        )
    return FreeBusyCalendarsMap(entries=entries), busy_slots


def _min_access_rank(role: str) -> int:
    return {"freeBusyReader": 0, "reader": 1, "writer": 2, "owner": 3}.get(role, -1)


def _parse_quick_add_text(text: str) -> tuple[str, datetime, datetime]:
    base = BASE_NOW
    lowered = text.lower()
    event_date = base.date()
    if "tomorrow" in lowered:
        event_date = base.date() + timedelta(days=1)
    elif match := re.search(r"on (\d{4}-\d{2}-\d{2})", lowered):
        event_date = date.fromisoformat(match.group(1))

    time_match = re.search(r"at (\d{1,2})(?::(\d{2}))?\s*(am|pm)?", lowered)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2) or "0")
        meridiem = time_match.group(3)
        if meridiem == "pm" and hour != 12:
            hour += 12
        if meridiem == "am" and hour == 12:
            hour = 0
    else:
        hour, minute = 12, 0

    duration_match = re.search(r"for (\d+)\s*(m|minutes|h|hour|hours)", lowered)
    if duration_match:
        quantity = int(duration_match.group(1))
        unit = duration_match.group(2)
        duration = (
            timedelta(hours=quantity)
            if unit.startswith("h")
            else timedelta(minutes=quantity)
        )
    else:
        duration = timedelta(hours=1)

    summary = re.split(
        r"\b(?:tomorrow|today|on \d{4}-\d{2}-\d{2}|at \d{1,2}(?::\d{2})?\s*(?:am|pm)?|for \d+\s*(?:m|minutes|h|hour|hours))\b",
        text,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip(" ,")
    if not summary:
        summary = text.strip() or "Quick add event"
    start = datetime.combine(
        event_date, time(hour, minute), tzinfo=ZoneInfo(BASE_TIMEZONE)
    )
    return summary, start, start + duration


def _coerce_dict_or_json(value: Any, *, what: str) -> dict[str, str]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return {str(k): str(v) for k, v in value.items()}
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise GoogleCalendarMockError(
                f"{what} must be a JSON object string: {exc}"
            ) from exc
        if not isinstance(parsed, dict):
            raise GoogleCalendarMockError(f"{what} must encode a JSON object")
        return {str(k): str(v) for k, v in parsed.items()}
    raise GoogleCalendarMockError(f"{what} must be an object or JSON string")


# ---------------------------------------------------------------------------
# Mutators / state helpers
# ---------------------------------------------------------------------------


def _next_id(kind: str) -> str:
    state = get_state()
    current = getattr(state.counters, kind)
    setattr(state.counters, kind, current + 1)
    prefix = {
        "calendar": "calendar",
        "event": "evt",
        "acl": "rule",
        "channel": "channel",
    }[kind]
    return f"{prefix}_{getattr(state.counters, kind)}"


def _require_calendar(calendar_id: str) -> Calendar:
    calendar = get_state().calendar(calendar_id)
    if calendar is None or calendar.deleted:
        raise GoogleCalendarMockError(f"Unknown calendar id: {calendar_id}")
    return calendar


def _require_calendar_list_entry(calendar_id: str) -> CalendarListEntry:
    entry = get_state().calendar_list_entry(calendar_id)
    if entry is None or entry.deleted:
        raise GoogleCalendarMockError(
            f"Calendar is not present in calendar list: {calendar_id}"
        )
    return entry


def _require_event(calendar_id: str, event_id: str) -> CalendarEvent:
    _require_calendar(calendar_id)
    event = get_state().event(calendar_id, event_id)
    if event is None:
        raise GoogleCalendarMockError(f"Unknown event id: {event_id}")
    return event


def _require_acl_rule(calendar_id: str, rule_id: str) -> AclRule:
    _require_calendar(calendar_id)
    rule = get_state().acl_rule(calendar_id, rule_id)
    if rule is None:
        raise GoogleCalendarMockError(f"Unknown ACL rule id: {rule_id}")
    return rule


def _record_calendar_change(calendar_id: str) -> None:
    state = get_state()
    state.counters.calendar_sync += 1
    state.calendar_changes.append(
        CalendarChange(calendarId=calendar_id, version=state.counters.calendar_sync)
    )
    calendar = state.calendar(calendar_id)
    if calendar is not None:
        calendar.meta.version = state.counters.calendar_sync
    entry = state.calendar_list_entry(calendar_id)
    if entry is not None:
        entry.meta.version = state.counters.calendar_sync


def _record_event_change(calendar_id: str, event: CalendarEvent) -> None:
    state = get_state()
    state.counters.sync += 1
    # Replace-or-append in the calendar's event log.
    log = state.event_log(calendar_id)
    log.events = [e for e in log.events if e.id != event.id]
    log.events.append(event)
    event.meta.version = state.counters.sync
    state.event_change_log(calendar_id).changes.append(event.model_copy(deep=True))


def _record_event_tombstone(
    calendar_id: str, event_id: str, base_event: CalendarEvent
) -> None:
    state = get_state()
    state.counters.sync += 1
    tombstone = base_event.model_copy(deep=True)
    tombstone.status = "cancelled"
    tombstone.updated = format_datetime(
        BASE_NOW + timedelta(minutes=state.counters.sync)
    )
    tombstone.meta = EventMeta(
        calendarId=calendar_id, version=state.counters.sync, deleted=True
    )
    state.event_change_log(calendar_id).changes.append(tombstone)


def _build_channel(
    *,
    channel_id: str,
    channel_type: str,
    address: str,
    token: str | None,
    params: str | dict | None,
    payload: bool | None = None,
) -> CalendarChannel:
    expiration = BASE_NOW + timedelta(days=7)
    return CalendarChannel(
        id=channel_id,
        type=channel_type,
        address=address,
        token=token,
        params=_coerce_dict_or_json(params, what="params"),
        resourceId=_next_id("channel"),
        resourceUri="https://calendar.google.com/mock/watch",
        expiration=str(int(expiration.timestamp() * 1000)),
        payload=payload,
    )


def _event_payload(
    *,
    calendar_id: str,
    summary: str | None,
    start_datetime: str,
    event_duration_hour: int = 0,
    event_duration_minutes: int = 30,
    location: str | None = None,
    description: str | None = None,
    timezone_name: str | None = None,
    attendees: list[str] | None = None,
    event_type: str = "default",
    recurrence: list[str] | None = None,
    visibility: str = "default",
    transparency: str = "opaque",
    create_meeting_room: bool | None = None,
    guests_can_modify: bool = False,
    guests_can_invite_others: bool | None = None,
    guests_can_see_other_guests: bool | None = None,
    birthday_properties: str | dict | None = None,
    focus_time_properties: str | dict | None = None,
    out_of_office_properties: str | dict | None = None,
    working_location_properties: str | dict | None = None,
) -> CalendarEvent:
    calendar = _require_calendar(calendar_id)
    birthday = (
        _coerce_dict_or_json(birthday_properties, what="birthday_properties") or None
    )
    focus = (
        _coerce_dict_or_json(focus_time_properties, what="focus_time_properties")
        or None
    )
    oof = (
        _coerce_dict_or_json(out_of_office_properties, what="out_of_office_properties")
        or None
    )
    working = (
        _coerce_dict_or_json(
            working_location_properties, what="working_location_properties"
        )
        or None
    )
    tz_name = timezone_name or calendar.timeZone
    start = parse_datetime(start_datetime, tz_name)
    if start is None:
        raise GoogleCalendarMockError("start_datetime is required")
    duration = timedelta(hours=event_duration_hour, minutes=event_duration_minutes)
    end = start + duration
    event_id = _next_id("event")
    event = _make_event(
        event_id=event_id,
        calendar_id=calendar_id,
        summary=summary or "Untitled event",
        start=start,
        end=end,
        organizer_email=get_state().profile.email,
        event_type=event_type,
        description=description,
        location=location,
        attendees=attendees,
        recurrence=recurrence,
        visibility=visibility,
        transparency=transparency,
        create_meeting_room=bool(create_meeting_room),
        focus_time_properties=focus,
        out_of_office_properties=oof,
        working_location_properties=working,
        birthday_properties=birthday,
    )
    event.guestsCanModify = guests_can_modify
    if guests_can_invite_others is not None:
        event.guestsCanInviteOthers = guests_can_invite_others
    if guests_can_see_other_guests is not None:
        event.guestsCanSeeOtherGuests = guests_can_see_other_guests
    return event


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def googlecalendar_acl_patch(
    role: str | None = None,
    scope: CalendarAclScope | None = None,
    rule_id: str | None = None,
    calendar_id: str | None = None,
    send_notifications: bool | None = None,
) -> PublicAclRule:
    """Updates an ACL rule using patch semantics."""
    del send_notifications
    if not rule_id or not calendar_id:
        raise GoogleCalendarMockError("rule_id and calendar_id are required")
    rule = _require_acl_rule(calendar_id, rule_id)
    if role is not None:
        rule.role = role
    if scope is not None:
        if isinstance(scope, dict):
            scope = CalendarAclScope.model_validate(scope)
        rule.scope = AclScope(type=scope.type, value=scope.value)
    return _to_public_acl_rule(rule)


def googlecalendar_calendar_list_insert(
    id: str | None = None,
    hidden: bool | None = None,
    color_id: str | None = None,
    selected: bool | None = None,
    background_color: str | None = None,
    color_rgb_format: bool | None = None,
    foreground_color: str | None = None,
    summary_override: str | None = None,
    default_reminders: list[CalendarReminderOverride] | None = None,
    notification_settings: CalendarNotificationSettings | None = None,
) -> PublicCalendarListEntry:
    """Adds an existing calendar to the user's calendar list."""
    del color_id, color_rgb_format
    if not id:
        raise GoogleCalendarMockError("id is required")
    calendar = _require_calendar(id)
    state = get_state()
    reminders = (
        [_coerce_model(CalendarReminderOverride, r) for r in default_reminders]
        if default_reminders is not None
        else None
    )
    notifications = (
        _coerce_model(CalendarNotificationSettings, notification_settings)
        if notification_settings
        else None
    )
    entry = _make_calendar_list_entry(
        calendar=calendar,
        hidden=bool(hidden) if hidden is not None else False,
        selected=True if selected is None else selected,
        background_color=background_color,
        foreground_color=foreground_color,
        summary_override=summary_override,
        default_reminders=reminders,
        notification_settings=notifications,
    )
    state.calendar_list = [e for e in state.calendar_list if e.id != id]
    state.calendar_list.append(entry)
    _record_calendar_change(id)
    return _to_public_calendar_list_entry(entry)


def _coerce_model(model: type, value):
    if value is None or isinstance(value, model):
        return value
    if isinstance(value, list):
        return [_coerce_model(model, item) for item in value]
    return model.model_validate(value)


def googlecalendar_calendar_list_update(
    calendar_id: str | None = None,
    hidden: bool | None = None,
    colorId: str | None = None,
    selected: bool | None = None,
    colorRgbFormat: bool | None = None,
    backgroundColor: str | None = None,
    foregroundColor: str | None = None,
    summaryOverride: str | None = None,
    defaultReminders: list[CalendarReminderOverride] | None = None,
    notificationSettings: CalendarNotificationSettings | None = None,
) -> PublicCalendarListEntry:
    """Updates one calendar-list entry."""
    del colorId, colorRgbFormat
    if not calendar_id:
        raise GoogleCalendarMockError("calendar_id is required")
    entry = _require_calendar_list_entry(calendar_id)
    if hidden is not None:
        entry.hidden = hidden
    if selected is not None:
        entry.selected = selected
    if backgroundColor is not None:
        entry.backgroundColor = backgroundColor
    if foregroundColor is not None:
        entry.foregroundColor = foregroundColor
    if summaryOverride is not None:
        entry.summaryOverride = summaryOverride
    if defaultReminders is not None:
        entry.defaultReminders = [
            _coerce_model(CalendarReminderOverride, r) for r in defaultReminders
        ]
    if notificationSettings is not None:
        entry.notificationSettings = _coerce_model(
            CalendarNotificationSettings, notificationSettings
        )
    _record_calendar_change(calendar_id)
    return _to_public_calendar_list_entry(entry)


def googlecalendar_calendars_delete(
    calendar_id: str | None = None,
) -> DeletedCalendarResult:
    """Deletes a secondary calendar resource."""
    if not calendar_id:
        raise GoogleCalendarMockError("calendar_id is required")
    calendar = _require_calendar(calendar_id)
    if calendar.primary:
        raise GoogleCalendarMockError(
            "Primary calendars cannot be deleted with calendars.delete"
        )
    calendar.deleted = True
    entry = get_state().calendar_list_entry(calendar_id)
    if entry is not None:
        entry.deleted = True
    _record_calendar_change(calendar_id)
    return DeletedCalendarResult(deletedCalendarId=calendar_id)


def googlecalendar_calendars_update(
    summary: str | None = None,
    calendarId: str | None = None,
    location: str | None = None,
    timeZone: str | None = None,
    description: str | None = None,
) -> PublicCalendar:
    """Updates a calendar resource with replacement semantics."""
    if not summary or not calendarId:
        raise GoogleCalendarMockError("summary and calendarId are required")
    calendar = _require_calendar(calendarId)
    calendar.summary = summary
    calendar.location = location
    calendar.timeZone = timeZone or calendar.timeZone
    calendar.description = description
    entry = get_state().calendar_list_entry(calendarId)
    if entry is not None:
        entry.summary = summary
        entry.location = location
        entry.timeZone = calendar.timeZone
        entry.description = description
    _record_calendar_change(calendarId)
    return _to_public_calendar(calendar)


def googlecalendar_clear_calendar(
    calendar_id: str | None = None,
) -> ClearCalendarResult:
    """Clears all events from a calendar."""
    if not calendar_id:
        raise GoogleCalendarMockError("calendar_id is required")
    _require_calendar(calendar_id)
    log = get_state().event_log(calendar_id)
    existing = list(log.events)
    for event in existing:
        _record_event_tombstone(calendar_id, event.id, event)
    log.events = []
    return ClearCalendarResult(
        clearedCalendarId=calendar_id, clearedEvents=len(existing)
    )


def googlecalendar_create_event(
    summary: str | None = None,
    location: str | None = None,
    timezone: str | None = None,
    attendees: list[str] | None = None,
    eventType: str = "default",
    recurrence: list[str] | None = None,
    visibility: str = "default",
    calendar_id: str = "primary",
    description: str | None = None,
    send_updates: bool | None = None,
    transparency: str = "opaque",
    start_datetime: str | None = None,
    exclude_organizer: bool = False,
    guests_can_modify: bool = False,
    event_duration_hour: int = 0,
    event_duration_minutes: int = 30,
    create_meeting_room: bool | None = None,
    birthdayProperties: str | None = None,
    focusTimeProperties: str | None = None,
    outOfOfficeProperties: str | None = None,
    workingLocationProperties: str | None = None,
    guestsCanInviteOthers: bool | None = None,
    guestsCanSeeOtherGuests: bool | None = None,
) -> PublicEvent:
    """Creates a calendar event from structured scheduling fields."""
    del send_updates, exclude_organizer
    if not start_datetime:
        raise GoogleCalendarMockError("start_datetime is required")
    event = _event_payload(
        calendar_id=calendar_id,
        summary=summary,
        start_datetime=start_datetime,
        event_duration_hour=event_duration_hour,
        event_duration_minutes=event_duration_minutes,
        location=location,
        description=description,
        timezone_name=timezone,
        attendees=attendees,
        event_type=eventType,
        recurrence=recurrence,
        visibility=visibility,
        transparency=transparency,
        create_meeting_room=create_meeting_room,
        guests_can_modify=guests_can_modify,
        guests_can_invite_others=guestsCanInviteOthers,
        guests_can_see_other_guests=guestsCanSeeOtherGuests,
        birthday_properties=birthdayProperties,
        focus_time_properties=focusTimeProperties,
        out_of_office_properties=outOfOfficeProperties,
        working_location_properties=workingLocationProperties,
    )
    _record_event_change(calendar_id, event)
    return _to_public_event(event)


def googlecalendar_delete_event(
    event_id: str | None = None,
    calendar_id: str = "primary",
) -> DeletedEventResult:
    """Deletes an event by ID from a calendar."""
    if not event_id:
        raise GoogleCalendarMockError("event_id is required")
    event = _require_event(calendar_id, event_id)
    log = get_state().event_log(calendar_id)
    log.events = [e for e in log.events if e.id != event_id]
    _record_event_tombstone(calendar_id, event_id, event)
    return DeletedEventResult(deletedEventId=event_id, calendarId=calendar_id)


def googlecalendar_duplicate_calendar(summary: str | None = None) -> PublicCalendar:
    """Creates a new empty calendar shell with the requested summary."""
    if not summary:
        raise GoogleCalendarMockError("summary is required")
    state = get_state()
    calendar_id = f"{summary.lower().replace(' ', '-')}-{_next_id('calendar')}@group.calendar.google.com"
    calendar = _make_calendar(
        calendar_id=calendar_id,
        summary=summary,
        description=f"Duplicate calendar for {summary}",
        time_zone=BASE_TIMEZONE,
        location=None,
        access_role="owner",
    )
    state.calendars.append(calendar)
    state.events.append(CalendarEventLog(calendar_id=calendar_id, events=[]))
    state.acl_rules.append(
        CalendarAclLog(
            calendar_id=calendar_id,
            rules=[
                AclRule(
                    etag=f'"default-{calendar_id}"',
                    id="default",
                    role="owner",
                    scope=AclScope(type="user", value=get_state().profile.email),
                )
            ],
        )
    )
    state.event_changes.append(EventChangeLog(calendar_id=calendar_id, changes=[]))
    state.calendar_list.append(
        _make_calendar_list_entry(calendar=calendar, selected=True)
    )
    _record_calendar_change(calendar_id)
    return _to_public_calendar(calendar)


def googlecalendar_events_instances(
    eventId: str | None = None,
    calendarId: str | None = None,
    timeMin: str | None = None,
    timeMax: str | None = None,
    timeZone: str | None = None,
    maxResults: int | None = None,
    pageToken: str | None = None,
    showDeleted: bool | None = None,
    maxAttendees: int | None = None,
    originalStart: str | None = None,
) -> EventsListResult:
    """Lists instances of a recurring event."""
    del timeZone, showDeleted
    if not eventId or not calendarId:
        raise GoogleCalendarMockError("eventId and calendarId are required")
    event = _require_event(calendarId, eventId)
    expanded = _expand_event_instances(
        event,
        time_min=parse_datetime(timeMin, event.start.timeZone or BASE_TIMEZONE),
        time_max=parse_datetime(timeMax, event.end.timeZone or BASE_TIMEZONE),
        original_start=originalStart,
    )
    items = [_to_public_event(i, max_attendees=maxAttendees) for i in expanded]
    page, next_token = _paginate(items, maxResults, pageToken)
    return EventsListResult(items=page, nextPageToken=next_token)


def googlecalendar_events_list(
    calendarId: str | None = None,
    q: str | None = None,
    iCalUID: str | None = None,
    orderBy: str | None = None,
    timeMin: str | None = None,
    timeMax: str | None = None,
    timeZone: str | None = None,
    maxResults: int | None = None,
    pageToken: str | None = None,
    syncToken: str | None = None,
    eventTypes: str | None = None,
    updatedMin: str | None = None,
    showDeleted: bool | None = None,
    maxAttendees: int | None = None,
    singleEvents: bool | None = None,
    alwaysIncludeEmail: bool | None = None,
    showHiddenInvitations: bool | None = None,
    sharedExtendedProperty: str | None = None,
    privateExtendedProperty: str | None = None,
) -> EventsListResult:
    """Lists events from a calendar with filtering, sync, and recurrence expansion options."""
    del (
        timeZone,
        alwaysIncludeEmail,
        showHiddenInvitations,
        sharedExtendedProperty,
        privateExtendedProperty,
    )
    if not calendarId:
        raise GoogleCalendarMockError("calendarId is required")
    state = get_state()
    if syncToken:
        version = int(syncToken)
        items = [
            _to_public_event(change, max_attendees=maxAttendees)
            for change in state.event_change_log(calendarId).changes
            if change.meta.version > version
        ]
    else:
        event_types = [eventTypes] if eventTypes else None
        calendar = _require_calendar(calendarId)
        events = _list_calendar_events(
            calendarId,
            show_deleted=bool(showDeleted),
            single_events=bool(singleEvents),
            time_min=parse_datetime(timeMin, calendar.timeZone),
            time_max=parse_datetime(timeMax, calendar.timeZone),
            query=q,
            i_cal_uid=iCalUID,
            updated_min=parse_datetime(updatedMin, calendar.timeZone),
            event_types=event_types,
            max_attendees=maxAttendees,
        )
        events = _sort_events(events, orderBy)
        items = [_to_public_event(e) for e in events]
    page, next_token = _paginate(items, maxResults, pageToken)
    next_sync_token = str(state.counters.sync) if next_token is None else None
    return EventsListResult(
        items=page, nextPageToken=next_token, nextSyncToken=next_sync_token
    )


def googlecalendar_events_move(
    event_id: str | None = None,
    calendar_id: str | None = None,
    destination: str | None = None,
    send_updates: str | None = None,
) -> PublicEvent:
    """Moves an event between calendars."""
    del send_updates
    if not event_id or not calendar_id or not destination:
        raise GoogleCalendarMockError(
            "event_id, calendar_id, and destination are required"
        )
    event = _require_event(calendar_id, event_id)
    _require_calendar(destination)
    moved = event.model_copy(deep=True)
    # Remove from source
    src_log = get_state().event_log(calendar_id)
    src_log.events = [e for e in src_log.events if e.id != event_id]
    _record_event_tombstone(calendar_id, event_id, event)
    # Update meta + organizer
    moved.meta.calendarId = destination
    new_organizer_email = (
        destination if destination != "primary" else get_state().profile.email
    )
    moved.organizer = EventPerson(
        email=new_organizer_email,
        self=new_organizer_email == get_state().profile.email,
    )
    get_state().event_log(destination).events.append(moved)
    _record_event_change(destination, moved)
    return _to_public_event(moved)


def googlecalendar_events_watch(
    calendarId: str | None = None,
    id: str | None = None,
    type: str = "web_hook",
    address: str | None = None,
    token: str | None = None,
    params: str | None = None,
    payload: bool | None = None,
) -> PublicChannel:
    """Creates a watch channel for calendar event changes."""
    if not calendarId or not id or not address:
        raise GoogleCalendarMockError("calendarId, id, and address are required")
    _require_calendar(calendarId)
    channel = _build_channel(
        channel_id=id,
        channel_type=type,
        address=address,
        token=token,
        params=params,
        payload=payload,
    )
    channel.calendarId = calendarId
    get_state().event_channels.append(channel)
    return _to_public_channel(channel)


def googlecalendar_find_event(
    calendar_id: str = "primary",
    query: str | None = None,
    timeMin: str | None = None,
    timeMax: str | None = None,
    order_by: str | None = None,
    event_types: list[str] | None = None,
    max_results: int = 10,
    page_token: str | None = None,
    updated_min: str | None = None,
    show_deleted: bool | None = None,
    single_events: bool = True,
) -> FindEventsResult:
    """Finds events by text, time range, and event type."""
    calendar = _require_calendar(calendar_id)
    events = _list_calendar_events(
        calendar_id,
        show_deleted=bool(show_deleted),
        single_events=single_events,
        time_min=parse_datetime(timeMin, calendar.timeZone),
        time_max=parse_datetime(timeMax, calendar.timeZone),
        query=query,
        updated_min=parse_datetime(updated_min, calendar.timeZone),
        event_types=event_types,
    )
    events = _sort_events(events, order_by)
    items = [_to_public_event(e) for e in events]
    page, next_token = _paginate(items, max_results, page_token)
    return FindEventsResult(
        events=page, nextPageToken=next_token, resultSizeEstimate=len(items)
    )


def googlecalendar_find_free_slots(
    items: list[str] | None = None,
    time_min: str | None = None,
    time_max: str | None = None,
    timezone: str = "UTC",
    group_expansion_max: int = 100,
    calendar_expansion_max: int = 50,
) -> FindFreeSlotsResult:
    """Computes free slots across one or more calendars."""
    del group_expansion_max, calendar_expansion_max
    calendar_ids = items or ["primary"]
    min_dt = parse_datetime(time_min, timezone) or BASE_NOW.astimezone(
        ZoneInfo(timezone)
    )
    max_dt = parse_datetime(time_max, timezone) or (min_dt + timedelta(hours=8))
    calendars, busy_slots = _build_free_busy(
        calendar_ids, time_min=min_dt, time_max=max_dt, time_zone=timezone
    )
    return FindFreeSlotsResult(
        timeMin=format_datetime(min_dt),
        timeMax=format_datetime(max_dt),
        calendars=calendars,
        freeSlots=_compute_free_slots(busy_slots, min_dt, max_dt),
    )


def googlecalendar_free_busy_query(
    items: list[CalendarFreeBusyRef] | None = None,
    timeMin: str | None = None,
    timeMax: str | None = None,
    timeZone: str | None = None,
    groupExpansionMax: int | None = None,
    calendarExpansionMax: int | None = None,
) -> FreeBusyResult:
    """Returns free/busy blocks for one or more calendars."""
    del groupExpansionMax, calendarExpansionMax
    if not items or not timeMin or not timeMax:
        raise GoogleCalendarMockError("items, timeMin, and timeMax are required")
    calendar_ids: list[str] = []
    for item in items:
        if isinstance(item, dict):
            calendar_ids.append(item["id"])
        elif isinstance(item, CalendarFreeBusyRef):
            calendar_ids.append(item.id)
        else:
            calendar_ids.append(item.id)
    min_dt = parse_datetime(timeMin, timeZone or BASE_TIMEZONE)
    max_dt = parse_datetime(timeMax, timeZone or BASE_TIMEZONE)
    if min_dt is None or max_dt is None:
        raise GoogleCalendarMockError("timeMin and timeMax must be valid datetimes")
    calendars, _ = _build_free_busy(
        calendar_ids, time_min=min_dt, time_max=max_dt, time_zone=timeZone
    )
    return FreeBusyResult(
        timeMin=format_datetime(min_dt),
        timeMax=format_datetime(max_dt),
        calendars=calendars,
    )


def googlecalendar_get_calendar(calendar_id: str = "primary") -> PublicCalendar:
    """Gets one calendar resource by calendar ID."""
    return _to_public_calendar(_require_calendar(calendar_id))


def googlecalendar_get_current_date_time(timezone: int = 0) -> CurrentDateTimeResult:
    """Returns the mocked current date and time for a UTC offset."""
    current = BASE_NOW.astimezone(_offset_timezone(timezone))
    return CurrentDateTimeResult(
        dateTime=format_datetime(current), timezoneOffsetHours=timezone
    )


def _offset_timezone(offset_hours: int):
    return timezone(timedelta(hours=offset_hours))


def googlecalendar_list_acl_rules(
    calendar_id: str | None = None,
    max_results: int | None = 100,
    page_token: str | None = None,
    sync_token: str | None = None,
    show_deleted: bool | None = None,
) -> AclListResult:
    """Lists ACL rules for a calendar."""
    del sync_token
    if not calendar_id:
        raise GoogleCalendarMockError("calendar_id is required")
    rules = []
    log = next((l for l in get_state().acl_rules if l.calendar_id == calendar_id), None)
    if log is not None:
        for rule in log.rules:
            if not show_deleted and rule.deleted:
                continue
            rules.append(_to_public_acl_rule(rule))
    page, next_token = _paginate(rules, max_results, page_token)
    return AclListResult(items=page, nextPageToken=next_token)


def googlecalendar_list_calendars(
    maxResults: int = 100,
    pageToken: str | None = None,
    syncToken: str | None = None,
    showHidden: bool = False,
    showDeleted: bool = False,
    minAccessRole: str | None = None,
) -> CalendarsListResult:
    """Lists calendar-list entries for the authenticated user."""
    state = get_state()
    if syncToken:
        version = int(syncToken)
        changed_ids = {
            ch.calendarId for ch in state.calendar_changes if ch.version > version
        }
        entries = [state.calendar_list_entry(cid) for cid in changed_ids]
        entries = [e for e in entries if e is not None]
    else:
        entries = list(state.calendar_list)
    filtered: list[PublicCalendarListEntry] = []
    for entry in entries:
        if not showDeleted and entry.deleted:
            continue
        if not showHidden and entry.hidden:
            continue
        if minAccessRole and _min_access_rank(entry.accessRole) < _min_access_rank(
            minAccessRole
        ):
            continue
        filtered.append(_to_public_calendar_list_entry(entry))
    filtered.sort(key=lambda item: item.id)
    page, next_token = _paginate(filtered, maxResults, pageToken)
    next_sync = str(state.counters.calendar_sync) if next_token is None else None
    return CalendarsListResult(
        items=page, nextPageToken=next_token, nextSyncToken=next_sync
    )


def googlecalendar_patch_calendar(
    calendar_id: str | None = None,
    summary: str | None = None,
    description: str | None = None,
    location: str | None = None,
    timezone: str | None = None,
) -> PublicCalendar:
    """Patches selected fields on a calendar resource."""
    if not calendar_id or not summary:
        raise GoogleCalendarMockError("calendar_id and summary are required")
    calendar = _require_calendar(calendar_id)
    calendar.summary = summary
    if description is not None:
        calendar.description = description
    if location is not None:
        calendar.location = location
    if timezone is not None:
        calendar.timeZone = timezone
    entry = get_state().calendar_list_entry(calendar_id)
    if entry is not None:
        entry.summary = calendar.summary
        entry.description = calendar.description
        entry.location = calendar.location
        entry.timeZone = calendar.timeZone
    _record_calendar_change(calendar_id)
    return _to_public_calendar(calendar)


def googlecalendar_patch_event(
    calendar_id: str | None = None,
    event_id: str | None = None,
    summary: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    location: str | None = None,
    description: str | None = None,
    attendees: list[str] | None = None,
    timezone: str | None = None,
    send_updates: str | None = None,
    max_attendees: int | None = None,
    rsvp_response: str | None = None,
    supports_attachments: bool | None = None,
    conference_data_version: int | None = None,
) -> PublicEvent:
    """Patches selected fields on an event resource."""
    del send_updates, supports_attachments, conference_data_version
    if not calendar_id or not event_id:
        raise GoogleCalendarMockError("calendar_id and event_id are required")
    event = _require_event(calendar_id, event_id)
    if summary is not None:
        event.summary = summary
    if location is not None:
        event.location = location
    if description is not None:
        event.description = description
    tz_name = timezone or event.start.timeZone or BASE_TIMEZONE
    if start_time is not None:
        start = parse_datetime(start_time, tz_name)
        if start is None:
            raise GoogleCalendarMockError("start_time invalid")
        event.start = EventDateTime(dateTime=format_datetime(start), timeZone=tz_name)
    if end_time is not None:
        end = parse_datetime(end_time, tz_name)
        if end is None:
            raise GoogleCalendarMockError("end_time invalid")
        event.end = EventDateTime(dateTime=format_datetime(end), timeZone=tz_name)
    if attendees is not None:
        event.attendees = [
            EventAttendee(email=email, responseStatus=rsvp_response or "needsAction")
            for email in attendees
        ]
    event.updated = format_datetime(
        BASE_NOW + timedelta(minutes=get_state().counters.sync + 1)
    )
    _record_event_change(calendar_id, event)
    return _to_public_event(event, max_attendees=max_attendees)


def googlecalendar_quick_add(
    text: str = "",
    calendar_id: str = "primary",
    send_updates: str | None = None,
) -> PublicEvent:
    """Parses natural language into a basic event."""
    del send_updates
    summary, start, end = _parse_quick_add_text(text)
    event = _make_event(
        event_id=_next_id("event"),
        calendar_id=calendar_id,
        summary=summary,
        start=start,
        end=end,
        organizer_email=get_state().profile.email,
    )
    _record_event_change(calendar_id, event)
    return _to_public_event(event)


def googlecalendar_remove_attendee(
    calendar_id: str = "primary",
    event_id: str | None = None,
    attendee_email: str | None = None,
) -> PublicEvent:
    """Removes one attendee from an event."""
    if not event_id or not attendee_email:
        raise GoogleCalendarMockError("event_id and attendee_email are required")
    event = _require_event(calendar_id, event_id)
    if not any(a.email == attendee_email for a in event.attendees):
        raise GoogleCalendarMockError("Attendee not found on event")
    event.attendees = [a for a in event.attendees if a.email != attendee_email]
    event.updated = format_datetime(
        BASE_NOW + timedelta(minutes=get_state().counters.sync + 1)
    )
    _record_event_change(calendar_id, event)
    return _to_public_event(event)


def googlecalendar_settings_list(
    maxResults: int | None = None,
    pageToken: str | None = None,
    syncToken: str | None = None,
) -> SettingsListResult:
    """Lists user Calendar settings."""
    del syncToken
    items = [_to_public_setting(s) for s in get_state().settings]
    items.sort(key=lambda item: item.id)
    page, next_token = _paginate(items, maxResults, pageToken)
    return SettingsListResult(items=page, nextPageToken=next_token)


def googlecalendar_settings_watch(
    id: str | None = None,
    type: str | None = None,
    address: str | None = None,
    token: str | None = None,
    params: str | None = None,
) -> PublicChannel:
    """Creates a watch channel for settings changes."""
    if not id or not type or not address:
        raise GoogleCalendarMockError("id, type, and address are required")
    channel = _build_channel(
        channel_id=id, channel_type=type, address=address, token=token, params=params
    )
    get_state().settings_channels.append(channel)
    return _to_public_channel(channel)


def googlecalendar_sync_events(
    calendar_id: str = "primary",
    sync_token: str | None = None,
    pageToken: str | None = None,
    event_types: list[str] | None = None,
    max_results: int | None = None,
    single_events: bool | None = None,
) -> EventsListResult:
    """Performs a full or incremental event sync for a calendar."""
    state = get_state()
    if sync_token:
        version = int(sync_token)
        events = [
            _to_public_event(change)
            for change in state.event_change_log(calendar_id).changes
            if change.meta.version > version
        ]
    else:
        events_raw = _list_calendar_events(
            calendar_id,
            show_deleted=False,
            single_events=bool(single_events),
            event_types=event_types,
        )
        events_raw = _sort_events(events_raw, "startTime")
        events = [_to_public_event(e) for e in events_raw]
    page, next_token = _paginate(events, max_results, pageToken)
    next_sync = str(state.counters.sync) if next_token is None else None
    return EventsListResult(
        items=page, nextPageToken=next_token, nextSyncToken=next_sync
    )


def googlecalendar_update_acl_rule(
    calendar_id: str | None = None,
    rule_id: str | None = None,
    role: str | None = None,
    send_notifications: bool | None = True,
) -> PublicAclRule:
    """Replaces an ACL rule's role."""
    del send_notifications
    if not calendar_id or not rule_id or not role:
        raise GoogleCalendarMockError("calendar_id, rule_id, and role are required")
    rule = _require_acl_rule(calendar_id, rule_id)
    rule.role = role
    return _to_public_acl_rule(rule)


def googlecalendar_update_event(
    calendar_id: str = "primary",
    event_id: str | None = None,
    summary: str | None = None,
    start_datetime: str | None = None,
    location: str | None = None,
    description: str | None = None,
    timezone: str | None = None,
    attendees: list[str] | None = None,
    eventType: str = "default",
    recurrence: list[str] | None = None,
    visibility: str = "default",
    transparency: str = "opaque",
    send_updates: bool | None = None,
    guests_can_modify: bool = False,
    event_duration_hour: int = 0,
    event_duration_minutes: int = 30,
    create_meeting_room: bool | None = None,
    birthdayProperties: str | None = None,
    focusTimeProperties: str | None = None,
    outOfOfficeProperties: str | None = None,
    workingLocationProperties: str | None = None,
    guestsCanInviteOthers: bool | None = None,
    guestsCanSeeOtherGuests: bool | None = None,
) -> PublicEvent:
    """Replaces an event resource with a new event payload."""
    del send_updates
    if not event_id or not start_datetime:
        raise GoogleCalendarMockError("event_id and start_datetime are required")
    current = _require_event(calendar_id, event_id)
    replacement = _event_payload(
        calendar_id=calendar_id,
        summary=summary or current.summary,
        start_datetime=start_datetime,
        event_duration_hour=event_duration_hour,
        event_duration_minutes=event_duration_minutes,
        location=location,
        description=description,
        timezone_name=timezone,
        attendees=attendees,
        event_type=eventType,
        recurrence=recurrence,
        visibility=visibility,
        transparency=transparency,
        create_meeting_room=create_meeting_room,
        guests_can_modify=guests_can_modify,
        guests_can_invite_others=guestsCanInviteOthers,
        guests_can_see_other_guests=guestsCanSeeOtherGuests,
        birthday_properties=birthdayProperties,
        focus_time_properties=focusTimeProperties,
        out_of_office_properties=outOfOfficeProperties,
        working_location_properties=workingLocationProperties,
    )
    replacement.id = event_id
    replacement.iCalUID = current.iCalUID
    replacement.created = current.created
    replacement.updated = format_datetime(
        BASE_NOW + timedelta(minutes=get_state().counters.sync + 1)
    )
    _record_event_change(calendar_id, replacement)
    return _to_public_event(replacement)


_TOOL_DEFINITIONS: list[ToolDefinition] = [
    ToolDefinition(
        name="GOOGLECALENDAR_ACL_PATCH",
        callable=googlecalendar_acl_patch,
        description="Updates an ACL rule using patch semantics.",
        required_fields=frozenset({"rule_id", "calendar_id"}),
    ),
    ToolDefinition(
        name="GOOGLECALENDAR_CALENDAR_LIST_INSERT",
        callable=googlecalendar_calendar_list_insert,
        description="Adds an existing calendar to the user's calendar list.",
        required_fields=frozenset({"id"}),
    ),
    ToolDefinition(
        name="GOOGLECALENDAR_CALENDAR_LIST_UPDATE",
        callable=googlecalendar_calendar_list_update,
        description="Updates one calendar-list entry.",
        required_fields=frozenset({"calendar_id"}),
    ),
    ToolDefinition(
        name="GOOGLECALENDAR_CALENDARS_DELETE",
        callable=googlecalendar_calendars_delete,
        description="Deletes a secondary calendar resource.",
        required_fields=frozenset({"calendar_id"}),
    ),
    ToolDefinition(
        name="GOOGLECALENDAR_CALENDARS_UPDATE",
        callable=googlecalendar_calendars_update,
        description="Updates a calendar resource with replacement semantics.",
        required_fields=frozenset({"summary", "calendarId"}),
    ),
    ToolDefinition(
        name="GOOGLECALENDAR_CLEAR_CALENDAR",
        callable=googlecalendar_clear_calendar,
        description="Clears all events from a calendar.",
        required_fields=frozenset({"calendar_id"}),
    ),
    ToolDefinition(
        name="GOOGLECALENDAR_CREATE_EVENT",
        callable=googlecalendar_create_event,
        description="Creates a calendar event from structured scheduling fields.",
        required_fields=frozenset({"start_datetime"}),
    ),
    ToolDefinition(
        name="GOOGLECALENDAR_DELETE_EVENT",
        callable=googlecalendar_delete_event,
        description="Deletes an event by ID from a calendar.",
        required_fields=frozenset({"event_id"}),
    ),
    ToolDefinition(
        name="GOOGLECALENDAR_DUPLICATE_CALENDAR",
        callable=googlecalendar_duplicate_calendar,
        description="Creates a new empty calendar shell with the requested summary.",
        required_fields=frozenset({"summary"}),
    ),
    ToolDefinition(
        name="GOOGLECALENDAR_EVENTS_INSTANCES",
        callable=googlecalendar_events_instances,
        description="Lists instances of a recurring event.",
        required_fields=frozenset({"eventId", "calendarId"}),
    ),
    ToolDefinition(
        name="GOOGLECALENDAR_EVENTS_LIST",
        callable=googlecalendar_events_list,
        description="Lists events from a calendar with filtering, sync, and recurrence expansion options.",
        required_fields=frozenset({"calendarId"}),
    ),
    ToolDefinition(
        name="GOOGLECALENDAR_EVENTS_MOVE",
        callable=googlecalendar_events_move,
        description="Moves an event between calendars.",
        required_fields=frozenset({"event_id", "calendar_id", "destination"}),
    ),
    ToolDefinition(
        name="GOOGLECALENDAR_EVENTS_WATCH",
        callable=googlecalendar_events_watch,
        description="Creates a watch channel for calendar event changes.",
        required_fields=frozenset({"calendarId", "id", "address"}),
    ),
    ToolDefinition(
        name="GOOGLECALENDAR_FIND_EVENT",
        callable=googlecalendar_find_event,
        description="Finds events by text, time range, and event type.",
    ),
    ToolDefinition(
        name="GOOGLECALENDAR_FIND_FREE_SLOTS",
        callable=googlecalendar_find_free_slots,
        description="Computes free slots across one or more calendars.",
    ),
    ToolDefinition(
        name="GOOGLECALENDAR_FREE_BUSY_QUERY",
        callable=googlecalendar_free_busy_query,
        description="Returns free/busy blocks for one or more calendars.",
        required_fields=frozenset({"items", "timeMin", "timeMax"}),
    ),
    ToolDefinition(
        name="GOOGLECALENDAR_GET_CALENDAR",
        callable=googlecalendar_get_calendar,
        description="Gets one calendar resource by calendar ID.",
    ),
    ToolDefinition(
        name="GOOGLECALENDAR_GET_CURRENT_DATE_TIME",
        callable=googlecalendar_get_current_date_time,
        description="Returns the mocked current date and time for a UTC offset.",
    ),
    ToolDefinition(
        name="GOOGLECALENDAR_LIST_ACL_RULES",
        callable=googlecalendar_list_acl_rules,
        description="Lists ACL rules for a calendar.",
        required_fields=frozenset({"calendar_id"}),
    ),
    ToolDefinition(
        name="GOOGLECALENDAR_LIST_CALENDARS",
        callable=googlecalendar_list_calendars,
        description="Lists calendar-list entries for the authenticated user.",
    ),
    ToolDefinition(
        name="GOOGLECALENDAR_PATCH_CALENDAR",
        callable=googlecalendar_patch_calendar,
        description="Patches selected fields on a calendar resource.",
        required_fields=frozenset({"calendar_id", "summary"}),
    ),
    ToolDefinition(
        name="GOOGLECALENDAR_PATCH_EVENT",
        callable=googlecalendar_patch_event,
        description="Patches selected fields on an event resource.",
        required_fields=frozenset({"calendar_id", "event_id"}),
    ),
    ToolDefinition(
        name="GOOGLECALENDAR_QUICK_ADD",
        callable=googlecalendar_quick_add,
        description="Parses natural language into a basic event.",
    ),
    ToolDefinition(
        name="GOOGLECALENDAR_REMOVE_ATTENDEE",
        callable=googlecalendar_remove_attendee,
        description="Removes one attendee from an event.",
        required_fields=frozenset({"event_id", "attendee_email"}),
    ),
    ToolDefinition(
        name="GOOGLECALENDAR_SETTINGS_LIST",
        callable=googlecalendar_settings_list,
        description="Lists user Calendar settings.",
    ),
    ToolDefinition(
        name="GOOGLECALENDAR_SETTINGS_WATCH",
        callable=googlecalendar_settings_watch,
        description="Creates a watch channel for settings changes.",
        required_fields=frozenset({"id", "type", "address"}),
    ),
    ToolDefinition(
        name="GOOGLECALENDAR_SYNC_EVENTS",
        callable=googlecalendar_sync_events,
        description="Performs a full or incremental event sync for a calendar.",
    ),
    ToolDefinition(
        name="GOOGLECALENDAR_UPDATE_ACL_RULE",
        callable=googlecalendar_update_acl_rule,
        description="Replaces an ACL rule's role.",
        required_fields=frozenset({"calendar_id", "rule_id", "role"}),
    ),
    ToolDefinition(
        name="GOOGLECALENDAR_UPDATE_EVENT",
        callable=googlecalendar_update_event,
        description="Replaces an event resource with a new event payload.",
        required_fields=frozenset({"event_id", "start_datetime"}),
    ),
]


TOOL_REGISTRY: dict[str, ToolSpec] = build_tool_registry(
    service="googlecalendar",
    definitions=_TOOL_DEFINITIONS,
)


def get_tool_registry() -> dict[str, ToolSpec]:
    return TOOL_REGISTRY


__all__ = [
    "AclListResult",
    "CalendarAclScope",
    "CalendarFreeBusyRef",
    "CalendarsListResult",
    "ClearCalendarResult",
    "CurrentDateTimeResult",
    "DeletedCalendarResult",
    "DeletedEventResult",
    "EventsListResult",
    "FindEventsResult",
    "FindFreeSlotsResult",
    "FreeBusyCalendarsMap",
    "FreeBusyResult",
    "FreeBusyTimePeriod",
    "GoogleCalendarMockError",
    "PublicAclRule",
    "PublicCalendar",
    "PublicCalendarListEntry",
    "PublicCalendarSetting",
    "PublicChannel",
    "PublicEvent",
    "SettingsListResult",
    "TOOL_REGISTRY",
    "get_tool_registry",
    "googlecalendar_acl_patch",
    "googlecalendar_calendar_list_insert",
    "googlecalendar_calendar_list_update",
    "googlecalendar_calendars_delete",
    "googlecalendar_calendars_update",
    "googlecalendar_clear_calendar",
    "googlecalendar_create_event",
    "googlecalendar_delete_event",
    "googlecalendar_duplicate_calendar",
    "googlecalendar_events_instances",
    "googlecalendar_events_list",
    "googlecalendar_events_move",
    "googlecalendar_events_watch",
    "googlecalendar_find_event",
    "googlecalendar_find_free_slots",
    "googlecalendar_free_busy_query",
    "googlecalendar_get_calendar",
    "googlecalendar_get_current_date_time",
    "googlecalendar_list_acl_rules",
    "googlecalendar_list_calendars",
    "googlecalendar_patch_calendar",
    "googlecalendar_patch_event",
    "googlecalendar_quick_add",
    "googlecalendar_remove_attendee",
    "googlecalendar_settings_list",
    "googlecalendar_settings_watch",
    "googlecalendar_sync_events",
    "googlecalendar_update_acl_rule",
    "googlecalendar_update_event",
    "reset_googlecalendar_mock_state",
]
