from __future__ import annotations

import unittest

from backend.gmail_mock import (
    GmailMockError,
    MetadataGmailMessage,
    MinimalGmailMessage,
    PublicGmailMessage,
    get_tool_registry,
    gmail_add_label_to_email,
    gmail_create_email_draft,
    gmail_create_label,
    gmail_delete_draft,
    gmail_delete_message,
    gmail_fetch_emails,
    gmail_fetch_message_by_message_id,
    gmail_fetch_message_by_thread_id,
    gmail_get_attachment,
    gmail_get_contacts,
    gmail_get_people,
    gmail_get_profile,
    gmail_list_drafts,
    gmail_list_labels,
    gmail_list_threads,
    gmail_modify_thread_labels,
    gmail_move_to_trash,
    gmail_patch_label,
    gmail_remove_label,
    gmail_reply_to_thread,
    reset_gmail_mock_state,
)
from backend.main import list_available_tools


class GmailMockTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_gmail_mock_state()

    def test_registry_exposes_all_gmail_tools(self) -> None:
        registry = get_tool_registry()
        self.assertEqual(20, len(registry))
        available_tools = set(list_available_tools())
        self.assertTrue(set(registry).issubset(available_tools))
        self.assertTrue(callable(registry["GMAIL_FETCH_EMAILS"].callable))

    def test_fetch_emails_supports_query_filters_and_pagination(self) -> None:
        revenue_page = gmail_fetch_emails(
            query="revenue", max_results=1, verbose=False, include_payload=False
        )
        self.assertEqual(2, revenue_page.resultSizeEstimate)
        self.assertEqual(1, len(revenue_page.messages))
        self.assertIsNotNone(revenue_page.nextPageToken)
        first = revenue_page.messages[0]
        # verbose=False + include_payload=False should yield a Minimal projection.
        self.assertIsInstance(first, (MinimalGmailMessage, PublicGmailMessage))
        if isinstance(first, PublicGmailMessage):
            self.assertIsNone(first.payload)

        follow_up_page = gmail_fetch_emails(
            query="revenue",
            max_results=1,
            page_token=revenue_page.nextPageToken,
            ids_only=True,
        )
        ids_only_message = follow_up_page.messages[0]
        self.assertEqual({"id", "threadId"}, set(ids_only_message.model_fields_set))

        finance_only = gmail_fetch_emails(label_ids=["Label_101"], max_results=10)
        self.assertEqual(2, finance_only.resultSizeEstimate)

    def test_fetch_message_by_id_supports_formats(self) -> None:
        metadata = gmail_fetch_message_by_message_id(
            message_id="msg_001", format="metadata"
        )
        self.assertIsInstance(metadata, MetadataGmailMessage)
        self.assertTrue(metadata.payload.headers)

        minimal = gmail_fetch_message_by_message_id(
            message_id="msg_001", format="minimal"
        )
        self.assertIsInstance(minimal, MinimalGmailMessage)
        self.assertEqual({"id", "threadId", "labelIds"}, set(minimal.model_fields_set))

        raw = gmail_fetch_message_by_message_id(message_id="msg_001", format="raw")
        self.assertIsInstance(raw, PublicGmailMessage)
        self.assertIn("Revenue finished 8 percent above plan", raw.raw)

    def test_thread_reply_and_fetch_are_stateful(self) -> None:
        before = gmail_fetch_message_by_thread_id(thread_id="thr_001")
        self.assertEqual(2, len(before.messages))

        reply = gmail_reply_to_thread(
            thread_id="thr_001",
            recipient_email="finance@corp.com",
            message_body="Here is the board-ready revenue summary.",
        )
        self.assertIn("SENT", reply.labelIds)
        self.assertEqual("thr_001", reply.threadId)

        after = gmail_fetch_message_by_thread_id(thread_id="thr_001")
        self.assertEqual(3, len(after.messages))
        self.assertEqual(reply.id, after.messages[-1].id)

    def test_attachment_contacts_people_and_profile(self) -> None:
        attachment = gmail_get_attachment(
            message_id="msg_001",
            attachment_id="att_001",
            file_name="q1-revenue.xlsx",
        )
        self.assertEqual(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            attachment.mimeType,
        )

        contacts = gmail_get_contacts()
        self.assertEqual(3, contacts.totalPeople)
        self.assertEqual("people/c1", contacts.connections[0].resourceName)

        me = gmail_get_people()
        self.assertEqual("people/me", me.resourceName)
        other_contacts = gmail_get_people(other_contacts=True, page_size=2)
        self.assertEqual(2, len(other_contacts.otherContacts))

        profile = gmail_get_profile()
        self.assertEqual("me@example.com", profile.emailAddress)
        self.assertEqual(6, profile.messagesTotal)

    def test_draft_lifecycle_updates_drafts_and_threads(self) -> None:
        created = gmail_create_email_draft(
            recipient_email="ops@corp.com",
            subject="Travel approval",
            body="Please approve the travel budget for next week's onsite.",
            attachment={
                "name": "budget.txt",
                "s3key": "travel-budget-v2",
                "mimetype": "text/plain",
            },
        )
        draft_id = created.id
        thread_id = created.message.threadId

        drafts = gmail_list_drafts(verbose=True, max_results=10)
        self.assertTrue(any(draft.id == draft_id for draft in drafts.drafts))

        threads = gmail_list_threads(max_results=20, verbose=True)
        created_thread = next(
            thread for thread in threads.threads if thread.id == thread_id
        )
        self.assertEqual(
            draft_id,
            next(
                draft.id
                for draft in drafts.drafts
                if draft.message.threadId == thread_id
            ),
        )
        self.assertEqual(created.message.id, created_thread.messages[0].id)

        deleted = gmail_delete_draft(draft_id=draft_id)
        self.assertEqual(draft_id, deleted.deletedDraftId)
        remaining = gmail_list_drafts(verbose=True, max_results=10)
        self.assertFalse(any(draft.id == draft_id for draft in remaining.drafts))

    def test_label_lifecycle_and_message_thread_mutations(self) -> None:
        created_label = gmail_create_label(
            label_name="Escalations", background_color="#fed7aa"
        )
        label_id = created_label.id

        updated_label = gmail_patch_label(
            userId="me",
            id=label_id,
            name="Customer Escalations",
            color={"textColor": "#111827", "backgroundColor": "#fb923c"},
        )
        self.assertEqual("Customer Escalations", updated_label.name)

        updated_message = gmail_add_label_to_email(
            message_id="msg_004", add_label_ids=[label_id], remove_label_ids=["STARRED"]
        )
        self.assertIn(label_id, updated_message.labelIds)
        self.assertNotIn("STARRED", updated_message.labelIds)

        updated_thread = gmail_modify_thread_labels(
            thread_id="thr_001", add_label_ids=[label_id], remove_label_ids=["UNREAD"]
        )
        for message in updated_thread.messages:
            self.assertIn(label_id, message.labelIds)
            self.assertNotIn("UNREAD", message.labelIds)

        labels = gmail_list_labels().labels
        self.assertTrue(any(label.id == label_id for label in labels))

        removed = gmail_remove_label(label_id=label_id)
        self.assertEqual(label_id, removed.removedLabelId)
        labels_after = gmail_list_labels().labels
        self.assertFalse(any(label.id == label_id for label in labels_after))

    def test_trash_delete_and_search_visibility(self) -> None:
        trashed = gmail_move_to_trash(message_id="msg_003")
        self.assertIn("TRASH", trashed.labelIds)
        self.assertNotIn("INBOX", trashed.labelIds)

        hidden = gmail_fetch_emails(query="Priya", max_results=10)
        self.assertEqual(0, hidden.resultSizeEstimate)

        visible = gmail_fetch_emails(
            query="Priya", max_results=10, include_spam_trash=True
        )
        self.assertEqual(1, visible.resultSizeEstimate)

        deleted = gmail_delete_message(message_id="msg_006")
        self.assertEqual("msg_006", deleted.deletedMessageId)
        profile = gmail_get_profile()
        self.assertEqual(5, profile.messagesTotal)

    def test_reset_restores_seed_state(self) -> None:
        gmail_create_label(label_name="Temp Label")
        gmail_delete_message(message_id="msg_006")
        mutated = gmail_get_profile()
        self.assertEqual(5, mutated.messagesTotal)

        reset_gmail_mock_state()
        restored = gmail_get_profile()
        self.assertEqual(6, restored.messagesTotal)
        labels = gmail_list_labels().labels
        self.assertFalse(any(label.name == "Temp Label" for label in labels))

    def test_core_errors_are_deterministic(self) -> None:
        with self.assertRaises(GmailMockError):
            gmail_fetch_message_by_message_id(message_id="missing")

        with self.assertRaises(GmailMockError):
            gmail_create_label(label_name="Finance")

        with self.assertRaises(GmailMockError):
            gmail_get_attachment(
                message_id="msg_001",
                attachment_id="att_001",
                file_name="wrong-name.pdf",
            )


if __name__ == "__main__":
    unittest.main()
