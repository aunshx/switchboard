from __future__ import annotations

import unittest

from backend.main import app
from fastapi.testclient import TestClient


class ChatEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_chat_endpoint_exists_and_accepts_messages(self) -> None:
        response = self.client.post(
            "/chat",
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
        self.assertNotEqual(
            response.status_code, 404, "POST /chat should be registered"
        )
        self.assertNotEqual(
            response.status_code, 422, "POST /chat should accept the documented schema"
        )

    def test_chat_endpoint_rejects_malformed_payload(self) -> None:
        response = self.client.post("/chat", json={"messages": "nope"})
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
