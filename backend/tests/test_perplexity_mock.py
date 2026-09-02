from __future__ import annotations

import unittest

from backend.perplexity_mock import (
    TOOL_REGISTRY,
    PerplexityMockError,
    PerplexitySearchResult,
    perplexity_search,
    reset_perplexity_mock_state,
)


class PerplexityMockTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_perplexity_mock_state()

    def test_registry_exposes_single_tool(self) -> None:
        self.assertEqual(set(TOOL_REGISTRY), {"perplexity_search"})

    def test_search_returns_default_payload_with_citations(self) -> None:
        result = perplexity_search(query="anything")
        self.assertIsInstance(result, PerplexitySearchResult)
        self.assertTrue(result.answer)
        self.assertGreaterEqual(len(result.citations), 1)
        self.assertEqual(result.model, "perplexity-mock-1")

    def test_search_recognizes_canned_phrases(self) -> None:
        result = perplexity_search(query="What is the latest on launch delay?")
        self.assertIn("launch", result.answer.lower())
        self.assertGreaterEqual(len(result.citations), 2)

    def test_invalid_inputs_raise(self) -> None:
        with self.assertRaises(PerplexityMockError):
            perplexity_search(query="")
        with self.assertRaises(PerplexityMockError):
            perplexity_search(query="hello", search_recency_filter="year")


if __name__ == "__main__":
    unittest.main()
