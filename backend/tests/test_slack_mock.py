from __future__ import annotations

import unittest

from backend.main import list_available_tools
from backend.slack_mock import (
    SlackMockError,
    get_tool_registry,
    reset_slack_mock_state,
    slack_conversations_history,
    slack_get_full_conversation,
    slack_get_thread,
    slack_health_check,
    slack_list_conversations,
    slack_list_users,
    slack_search_messages,
    slack_send_message,
    slack_token_status,
    slack_users_info,
)


class SlackMockTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_slack_mock_state()

    def test_registry_exposes_all_slack_tools(self) -> None:
        registry = get_tool_registry()
        self.assertEqual(10, len(registry))
        available_tools = set(list_available_tools())
        self.assertTrue(set(registry).issubset(available_tools))
        self.assertTrue(callable(registry["slack_send_message"].callable))

    def test_token_status_and_health_are_stable(self) -> None:
        token = slack_token_status()
        self.assertTrue(token.ok)
        self.assertTrue(token.auto_refresh)
        self.assertIn("chat:write", token.scopes)

        health = slack_health_check()
        self.assertEqual("Instalily Internal", health.workspace)
        self.assertEqual(4, health.conversation_count)

    def test_list_conversations_and_users(self) -> None:
        conversations = slack_list_conversations(
            types="public_channel,im", discover_dms=True
        )
        self.assertEqual(2, conversations.result_count)
        names = {item.name for item in conversations.conversations}
        self.assertIn("engineering", names)
        self.assertIn("dm-avery-morgan", names)

        users = slack_list_users(limit=10)
        self.assertEqual(5, users.result_count)
        self.assertEqual("avery", users.members[0].profile.display_name)

        user = slack_users_info(user="U002")
        self.assertEqual("finance@corp.com", user.user.profile.email)

    def test_history_search_and_full_conversation(self) -> None:
        history = slack_conversations_history(channel="C001", limit=10)
        self.assertTrue(
            any("revenue" in message.text.lower() for message in history.messages)
        )

        search = slack_search_messages(query="from:@morgan revenue", count=5)
        self.assertEqual(1, search.result_count)
        self.assertEqual("engineering", search.messages[0].channel_name)

        full = slack_get_full_conversation(
            channel="C001", include_threads=True, max_messages=10
        )
        threaded = next(message for message in full.messages if message.thread)
        self.assertEqual(2, len(threaded.thread))

    def test_send_message_and_thread_reply_are_stateful(self) -> None:
        top_level = slack_send_message(
            channel="C001", text="Posting a fresh launch update."
        )
        self.assertEqual("Posting a fresh launch update.", top_level.text)

        history = slack_conversations_history(channel="C001", limit=20)
        self.assertEqual(top_level.ts, history.messages[-1].ts)

        seeded_thread = next(
            message for message in history.messages if message.reply_count
        )

        reply = slack_send_message(
            channel="C001",
            thread_ts=seeded_thread.ts,
            text="Replying in-thread with the rollback owner.",
        )
        self.assertEqual(seeded_thread.ts, reply.thread_ts)

        thread = slack_get_thread(channel="C001", thread_ts=seeded_thread.ts)
        self.assertEqual(4, len(thread.messages))
        self.assertEqual(reply.ts, thread.messages[-1].ts)

    def test_reset_and_errors_are_deterministic(self) -> None:
        slack_send_message(channel="D001", text="One-off DM")
        history = slack_conversations_history(channel="D001", limit=10)
        self.assertEqual(2, len(history.messages))

        reset_slack_mock_state()
        restored = slack_conversations_history(channel="D001", limit=10)
        self.assertEqual(1, len(restored.messages))

        with self.assertRaises(SlackMockError):
            slack_conversations_history(channel="missing", limit=10)

        with self.assertRaises(SlackMockError):
            slack_search_messages(query=None, count=10)

        with self.assertRaises(SlackMockError):
            slack_get_thread(channel="C001", thread_ts="missing")


if __name__ == "__main__":
    unittest.main()
