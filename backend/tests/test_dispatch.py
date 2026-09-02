from __future__ import annotations

import unittest

from backend.chat_schema import ToolCallLog
from backend.helpers.dispatch import (
    INVALID_ARGUMENTS,
    TOOL_ERROR,
    UNKNOWN_TOOL,
    dispatch,
    strip_defaulted_nones,
)
from backend.main import reset_all_mock_state


class DispatchTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_all_mock_state()
        self.log: list[ToolCallLog] = []

    def tearDown(self) -> None:
        reset_all_mock_state()

    def test_clean_call_logs_result_and_no_error(self) -> None:
        outcome = dispatch("slack_list_conversations", {"limit": 100}, self.log)

        self.assertTrue(outcome.ok)
        self.assertIsNone(outcome.error)
        self.assertEqual(1, len(self.log))
        entry = self.log[0]
        self.assertEqual("slack_list_conversations", entry.name)
        self.assertIsNone(entry.error)
        self.assertEqual(4, entry.result["result_count"])
        self.assertEqual(
            ["dm-avery-morgan", "engineering", "launch-war-room", "leadership-private"],
            [c["name"] for c in entry.result["conversations"]],
        )

    def test_logged_value_is_envelope_result_not_envelope(self) -> None:
        dispatch("GMAIL_FETCH_EMAILS", {"query": "revenue", "max_results": 5}, self.log)

        result = self.log[0].result
        self.assertIsInstance(result, dict)
        self.assertNotIn("result", result)
        self.assertIn("messages", result)
        self.assertIn("resultSizeEstimate", result)
        self.assertEqual(2, len(result["messages"]))

    def test_unknown_tool_logs_error_and_does_not_raise(self) -> None:
        outcome = dispatch("gmail_send_message", {"to": "a@b.com"}, self.log)

        self.assertFalse(outcome.ok)
        self.assertTrue(outcome.error.startswith(UNKNOWN_TOOL))
        self.assertEqual(1, len(self.log))
        self.assertEqual("gmail_send_message", self.log[0].name)
        self.assertIsNone(self.log[0].result)
        self.assertEqual({"to": "a@b.com"}, self.log[0].arguments)

    def test_casing_is_repaired_and_logged_under_registered_name(self) -> None:
        outcome = dispatch("gmail_fetch_emails", {"query": "revenue"}, self.log)

        self.assertTrue(outcome.ok)
        self.assertEqual("GMAIL_FETCH_EMAILS", outcome.name)
        self.assertEqual("GMAIL_FETCH_EMAILS", self.log[0].name)

    def test_bad_args_logs_validation_error(self) -> None:
        outcome = dispatch(
            "GMAIL_FETCH_EMAILS", {"query": "revenue", "max_results": "two"}, self.log
        )

        self.assertFalse(outcome.ok)
        self.assertTrue(outcome.error.startswith(INVALID_ARGUMENTS))
        self.assertIn("max_results", outcome.error)
        self.assertIsNone(self.log[0].result)
        self.assertEqual(outcome.error, self.log[0].error)

    def test_unknown_keyword_logs_validation_error(self) -> None:
        outcome = dispatch("slack_list_users", {"bogus": 1}, self.log)

        self.assertTrue(outcome.error.startswith(INVALID_ARGUMENTS))
        self.assertIn("bogus", outcome.error)

    def test_mock_error_is_distinguishable_from_validation_error(self) -> None:
        outcome = dispatch(
            "GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID", {"message_id": "msg_999"}, self.log
        )

        self.assertFalse(outcome.ok)
        self.assertTrue(outcome.error.startswith(TOOL_ERROR))
        self.assertIn("Unknown message id: msg_999", outcome.error)
        self.assertEqual(1, len(self.log))
        self.assertEqual("GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID", self.log[0].name)
        self.assertIsNone(self.log[0].result)

    def test_null_required_arg_is_stripped_and_surfaces_as_validation_error(self) -> None:
        outcome = dispatch(
            "GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID", {"message_id": None}, self.log
        )

        self.assertTrue(outcome.error.startswith(INVALID_ARGUMENTS))
        self.assertEqual({}, self.log[0].arguments)

    def test_strip_removes_only_defaulted_nones(self) -> None:
        clean = strip_defaulted_nones(
            "GMAIL_FETCH_EMAILS",
            {"query": "revenue", "label_ids": None, "page_token": None, "max_results": 5},
        )

        self.assertEqual({"query": "revenue", "max_results": 5}, clean)

    def test_stripped_args_are_what_gets_logged(self) -> None:
        dispatch(
            "GMAIL_FETCH_EMAILS",
            {
                "user_id": "me",
                "query": "revenue",
                "label_ids": None,
                "max_results": 5,
                "page_token": None,
                "verbose": True,
                "ids_only": False,
                "include_payload": True,
                "include_spam_trash": False,
            },
            self.log,
        )

        self.assertNotIn("label_ids", self.log[0].arguments)
        self.assertNotIn("page_token", self.log[0].arguments)
        self.assertEqual("revenue", self.log[0].arguments["query"])

    def test_every_path_appends_exactly_one_entry(self) -> None:
        dispatch("slack_list_users", None, self.log)
        dispatch("not_a_tool", {}, self.log)
        dispatch("slack_list_users", {"bogus": 1}, self.log)
        dispatch("GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID", {"message_id": "nope"}, self.log)

        self.assertEqual(4, len(self.log))
        self.assertEqual([None], [e.error for e in self.log[:1]])
        self.assertTrue(all(e.error for e in self.log[1:]))

    def test_write_tool_mutates_state_and_logs_result(self) -> None:
        outcome = dispatch(
            "slack_send_message",
            {"channel": "C001", "text": "hello from dispatch", "thread_ts": None},
            self.log,
        )

        self.assertTrue(outcome.ok)
        self.assertEqual("hello from dispatch", self.log[0].result["text"])

        from backend.slack_mock.state import get_state

        texts = [m.text for m in get_state().channel_log("C001").messages]
        self.assertIn("hello from dispatch", texts)


class DedupCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_all_mock_state()
        self.log: list[ToolCallLog] = []
        self.cache: dict = {}

    def tearDown(self) -> None:
        reset_all_mock_state()

    def test_identical_read_is_served_from_cache_without_a_second_log_entry(self) -> None:
        first = dispatch("slack_list_conversations", {"limit": 100}, self.log, self.cache)
        second = dispatch("slack_list_conversations", {"limit": 100}, self.log, self.cache)

        self.assertFalse(first.cached)
        self.assertTrue(second.cached)
        self.assertEqual(first.result, second.result)
        self.assertEqual(1, len(self.log))

    def test_different_args_are_not_deduped(self) -> None:
        dispatch("slack_list_conversations", {"limit": 100}, self.log, self.cache)
        second = dispatch("slack_list_conversations", {"limit": 50}, self.log, self.cache)

        self.assertFalse(second.cached)
        self.assertEqual(2, len(self.log))

    def test_writes_are_never_deduped(self) -> None:
        args = {"channel": "C001", "text": "hello"}
        dispatch("slack_send_message", args, self.log, self.cache)
        second = dispatch("slack_send_message", args, self.log, self.cache)

        self.assertFalse(second.cached)
        self.assertEqual(2, len(self.log))

    def test_successful_write_invalidates_cached_reads(self) -> None:
        dispatch("slack_conversations_history", {"channel": "C001"}, self.log, self.cache)
        self.assertEqual(1, len(self.cache))

        dispatch("slack_send_message", {"channel": "C001", "text": "x"}, self.log, self.cache)
        self.assertEqual(0, len(self.cache))

        after = dispatch("slack_conversations_history", {"channel": "C001"}, self.log, self.cache)
        self.assertFalse(after.cached)
        self.assertEqual(5, len(after.result["messages"]))

    def test_errors_are_not_cached(self) -> None:
        args = {"message_id": "msg_999"}
        dispatch("GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID", args, self.log, self.cache)
        second = dispatch("GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID", args, self.log, self.cache)

        self.assertFalse(second.cached)
        self.assertEqual(2, len(self.log))

    def test_no_cache_argument_means_no_dedup(self) -> None:
        dispatch("slack_list_conversations", {"limit": 100}, self.log)
        second = dispatch("slack_list_conversations", {"limit": 100}, self.log)

        self.assertFalse(second.cached)
        self.assertEqual(2, len(self.log))


if __name__ == "__main__":
    unittest.main()
