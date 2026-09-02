from __future__ import annotations

import unittest

from backend.googlecalendar_mock import (
    GoogleCalendarMockError,
    get_tool_registry,
    googlecalendar_acl_patch,
    googlecalendar_calendar_list_update,
    googlecalendar_calendars_delete,
    googlecalendar_calendars_update,
    googlecalendar_create_event,
    googlecalendar_delete_event,
    googlecalendar_duplicate_calendar,
    googlecalendar_events_instances,
    googlecalendar_events_list,
    googlecalendar_events_move,
    googlecalendar_events_watch,
    googlecalendar_find_event,
    googlecalendar_find_free_slots,
    googlecalendar_free_busy_query,
    googlecalendar_get_calendar,
    googlecalendar_get_current_date_time,
    googlecalendar_list_acl_rules,
    googlecalendar_list_calendars,
    googlecalendar_patch_calendar,
    googlecalendar_patch_event,
    googlecalendar_quick_add,
    googlecalendar_remove_attendee,
    googlecalendar_settings_list,
    googlecalendar_settings_watch,
    googlecalendar_sync_events,
    googlecalendar_update_acl_rule,
    googlecalendar_update_event,
    reset_googlecalendar_mock_state,
)
from backend.main import list_available_tools


class GoogleCalendarMockTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_googlecalendar_mock_state()

    def test_registry_exposes_all_calendar_tools(self) -> None:
        registry = get_tool_registry()
        self.assertEqual(29, len(registry))
        self.assertIn("GOOGLECALENDAR_CREATE_EVENT", registry)
        self.assertEqual(191, len(list_available_tools()))

    def test_calendar_lifecycle_and_calendar_list_visibility(self) -> None:
        initial = googlecalendar_list_calendars(showHidden=False)
        self.assertEqual(3, len(initial.items))

        duplicate = googlecalendar_duplicate_calendar(summary="Candidate Loop")
        duplicate_id = duplicate.id
        self.assertIn("Candidate Loop", duplicate.summary)

        updated = googlecalendar_calendars_update(
            summary="Candidate Loop - Interviewing",
            calendarId=duplicate_id,
            location="Remote",
            description="Interview schedule",
            timeZone="America/Los_Angeles",
        )
        self.assertEqual("America/Los_Angeles", updated.timeZone)

        patched = googlecalendar_patch_calendar(
            calendar_id=duplicate_id,
            summary="Candidate Loop - Final",
            description="Final interview plan",
        )
        self.assertEqual("Candidate Loop - Final", patched.summary)

        hidden_entry = googlecalendar_calendar_list_update(
            calendar_id="personal-projects@group.calendar.google.com",
            hidden=True,
            selected=False,
            summaryOverride="Private",
        )
        self.assertTrue(hidden_entry.hidden)

        visible = googlecalendar_list_calendars(showHidden=False)
        self.assertEqual(3, len(visible.items))
        visible_ids = {item.id for item in visible.items}
        self.assertNotIn("personal-projects@group.calendar.google.com", visible_ids)
        self.assertIn(duplicate_id, visible_ids)

        deleted = googlecalendar_calendars_delete(calendar_id=duplicate_id)
        self.assertEqual(duplicate_id, deleted.deletedCalendarId)
        with_deleted = googlecalendar_list_calendars(showDeleted=True, showHidden=True)
        deleted_entry = next(
            item for item in with_deleted.items if item.id == duplicate_id
        )
        self.assertTrue(deleted_entry.deleted)

    def test_event_lifecycle_across_create_patch_move_update_delete_and_quick_add(
        self,
    ) -> None:
        created = googlecalendar_create_event(
            calendar_id="primary",
            summary="Orchestration interview debrief",
            start_datetime="2026-04-08T17:00:00",
            event_duration_minutes=45,
            attendees=["ops@corp.com", "finance@corp.com"],
            create_meeting_room=True,
            description="Review candidate approach and tradeoffs.",
        )
        event_id = created.id
        self.assertIsNotNone(created.conferenceData)

        found = googlecalendar_find_event(
            calendar_id="primary", query="interview debrief", max_results=10
        )
        self.assertTrue(any(event.id == event_id for event in found.events))

        patched = googlecalendar_patch_event(
            calendar_id="primary",
            event_id=event_id,
            location="Zoom",
            attendees=["ops@corp.com", "finance@corp.com", "ceo@vip-client.com"],
            rsvp_response="accepted",
        )
        self.assertEqual("Zoom", patched.location)
        self.assertEqual(3, len(patched.attendees))

        attendee_removed = googlecalendar_remove_attendee(
            calendar_id="primary",
            event_id=event_id,
            attendee_email="finance@corp.com",
        )
        self.assertEqual(2, len(attendee_removed.attendees))

        moved = googlecalendar_events_move(
            event_id=event_id,
            calendar_id="primary",
            destination="engineering@group.calendar.google.com",
        )
        self.assertEqual("engineering@group.calendar.google.com", moved.organizer.email)

        replaced = googlecalendar_update_event(
            calendar_id="engineering@group.calendar.google.com",
            event_id=event_id,
            summary="Orchestration interview final review",
            start_datetime="2026-04-08T18:30:00",
            event_duration_hour=1,
            attendees=["ops@corp.com"],
            create_meeting_room=True,
        )
        self.assertEqual("Orchestration interview final review", replaced.summary)
        self.assertEqual("2026-04-08T18:30:00-04:00", replaced.start.dateTime)

        quick_added = googlecalendar_quick_add(
            text="Prep takehome review tomorrow at 3pm for 45m",
            calendar_id="primary",
        )
        self.assertEqual("Prep takehome review", quick_added.summary)
        self.assertEqual("2026-04-09T15:00:00-04:00", quick_added.start.dateTime)

        deleted = googlecalendar_delete_event(
            event_id=event_id,
            calendar_id="engineering@group.calendar.google.com",
        )
        self.assertEqual(event_id, deleted.deletedEventId)
        self.assertEqual("engineering@group.calendar.google.com", deleted.calendarId)
        engineering_events = googlecalendar_events_list(
            calendarId="engineering@group.calendar.google.com",
            q="final review",
        )
        self.assertEqual(0, len(engineering_events.items))

    def test_recurrence_instances_list_free_busy_and_free_slots(self) -> None:
        instances = googlecalendar_events_instances(
            eventId="evt_002",
            calendarId="primary",
            timeMin="2026-04-08T00:00:00-04:00",
            timeMax="2026-05-31T23:59:00-04:00",
            maxResults=10,
        )
        self.assertEqual(6, len(instances.items))
        self.assertEqual("evt_002", instances.items[0].recurringEventId)

        standups = googlecalendar_events_list(
            calendarId="engineering@group.calendar.google.com",
            q="standup",
            singleEvents=True,
            timeMin="2026-04-08T00:00:00-04:00",
            timeMax="2026-04-12T00:00:00-04:00",
        )
        self.assertEqual(4, len(standups.items))

        free_busy = googlecalendar_free_busy_query(
            items=[{"id": "primary"}],
            timeMin="2026-04-08T12:00:00-04:00",
            timeMax="2026-04-08T18:00:00-04:00",
            timeZone="America/New_York",
        )
        primary_busy = free_busy.calendars["primary"].busy
        self.assertEqual(2, len(primary_busy))
        self.assertEqual("2026-04-08T13:00:00-04:00", primary_busy[0].start)

        free_slots = googlecalendar_find_free_slots(
            items=["primary"],
            time_min="2026-04-08T12:00:00-04:00",
            time_max="2026-04-08T18:00:00-04:00",
            timezone="America/New_York",
        )
        self.assertTrue(
            any(
                slot.start == "2026-04-08T14:00:00-04:00"
                for slot in free_slots.freeSlots
            )
        )

    def test_acl_settings_watch_sync_and_reset_are_stateful(self) -> None:
        acl_rules = googlecalendar_list_acl_rules(calendar_id="primary")
        self.assertEqual(2, len(acl_rules.items))

        patched_acl = googlecalendar_acl_patch(
            calendar_id="primary",
            rule_id="user:finance@corp.com",
            role="writer",
        )
        self.assertEqual("writer", patched_acl.role)

        updated_acl = googlecalendar_update_acl_rule(
            calendar_id="primary",
            rule_id="default",
            role="freeBusyReader",
        )
        self.assertEqual("freeBusyReader", updated_acl.role)

        settings = googlecalendar_settings_list()
        self.assertTrue(any(item.id == "timezone" for item in settings.items))

        settings_watch = googlecalendar_settings_watch(
            id="settings-channel-1",
            type="web_hook",
            address="https://example.com/settings",
        )
        self.assertEqual("settings-channel-1", settings_watch.id)

        events_watch = googlecalendar_events_watch(
            calendarId="primary",
            id="events-channel-1",
            address="https://example.com/events",
        )
        self.assertEqual("primary", events_watch.calendarId)

        initial_sync = googlecalendar_sync_events(
            calendar_id="primary", single_events=True
        )
        self.assertIsNotNone(initial_sync.nextSyncToken)
        sync_token = initial_sync.nextSyncToken

        created = googlecalendar_create_event(
            calendar_id="primary",
            summary="Sync me",
            start_datetime="2026-04-12T10:00:00",
            event_duration_minutes=30,
        )
        incremental = googlecalendar_sync_events(
            calendar_id="primary", sync_token=sync_token
        )
        self.assertTrue(any(item.id == created.id for item in incremental.items))

        reset_googlecalendar_mock_state()
        after_reset = googlecalendar_find_event(
            calendar_id="primary", query="Sync me", max_results=10
        )
        self.assertEqual(0, after_reset.resultSizeEstimate)

    def test_current_time_and_core_errors_are_deterministic(self) -> None:
        current = googlecalendar_get_current_date_time(timezone=2)
        self.assertEqual("2026-04-08T15:00:00+02:00", current.dateTime)

        calendar = googlecalendar_get_calendar("primary")
        self.assertEqual("Avery Quinn", calendar.summary)

        with self.assertRaises(GoogleCalendarMockError):
            googlecalendar_calendars_delete(calendar_id="primary")

        with self.assertRaises(GoogleCalendarMockError):
            googlecalendar_remove_attendee(
                calendar_id="primary",
                event_id="evt_001",
                attendee_email="missing@example.com",
            )

        with self.assertRaises(GoogleCalendarMockError):
            googlecalendar_get_calendar("missing")


if __name__ == "__main__":
    unittest.main()
