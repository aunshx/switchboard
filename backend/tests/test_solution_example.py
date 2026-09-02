from __future__ import annotations

import unittest

from backend.main import app
from fastapi.testclient import TestClient


class SolutionExampleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_greeting_returns_an_assistant_message_without_tools(self) -> None:
        response = self.client.post(
            "/chat",
            json={"messages": [{"role": "user", "content": "Hello!"}]},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["messages"][-1]["role"], "assistant")
        self.assertTrue(payload["messages"][-1]["content"])
        self.assertEqual(payload["tool_calls"], [])


if __name__ == "__main__":
    unittest.main()
