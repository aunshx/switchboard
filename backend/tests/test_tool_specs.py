from __future__ import annotations

import unittest

from backend.main import (
    get_all_tool_specs,
    get_openai_tools,
    get_tool_callable,
    get_tool_catalog,
    get_tool_spec,
    health_check,
    list_available_tools,
    list_tools,
    reset_all_mock_state,
    reset_tools,
)
from backend.tooling import ToolSpec
from pydantic import BaseModel


class ToolSpecTests(unittest.TestCase):
    def test_unified_registry_exposes_all_tools_as_specs(self) -> None:
        specs = get_all_tool_specs()
        self.assertEqual(set(specs), set(list_available_tools()))
        self.assertIsInstance(specs["GMAIL_FETCH_EMAILS"], ToolSpec)
        self.assertIsInstance(specs["GOOGLECALENDAR_CREATE_EVENT"], ToolSpec)
        self.assertIsInstance(specs["GOOGLEDRIVE_FIND_FILE"], ToolSpec)
        self.assertIsInstance(specs["slack_send_message"], ToolSpec)
        self.assertIs(get_tool_spec("GMAIL_FETCH_EMAILS"), specs["GMAIL_FETCH_EMAILS"])

    def test_every_tool_has_docstrings_and_typed_models(self) -> None:
        for name, spec in get_all_tool_specs().items():
            self.assertTrue(spec.description.strip(), name)
            self.assertTrue(spec.docstring.strip(), name)
            self.assertTrue(spec.callable.__doc__, name)
            self.assertTrue(spec.callable.__doc__.startswith(spec.description), name)
            self.assertTrue(issubclass(spec.args_model, BaseModel), name)
            self.assertTrue(issubclass(spec.result_model, BaseModel), name)
            self.assertTrue(spec.args_model.__doc__, name)
            self.assertTrue(spec.result_model.__doc__, name)

            field_descriptions = [
                field.description for field in spec.args_model.model_fields.values()
            ]
            self.assertTrue(
                all(
                    description and description.strip()
                    for description in field_descriptions
                ),
                name,
            )
            self.assertIn("result", spec.result_model.model_fields, name)
            self.assertTrue(spec.result_model.model_fields["result"].description, name)

    def test_specs_can_validate_and_invoke_tools(self) -> None:
        gmail_result = get_tool_spec("GMAIL_FETCH_EMAILS").invoke(
            query="revenue", max_results=1
        )
        self.assertEqual(1, len(gmail_result.result.messages))

        calendar_result = get_tool_spec("GOOGLECALENDAR_GET_CALENDAR").invoke(
            calendar_id="primary"
        )
        self.assertEqual("primary", calendar_result.result.id)

        drive_result = get_tool_spec("GOOGLEDRIVE_FIND_FILE").invoke(
            q="revenue", pageSize=5
        )
        self.assertTrue(drive_result.result.files)

        slack_result = get_tool_spec("slack_health_check").invoke()
        self.assertEqual("Instalily Internal", slack_result.result.workspace)

    def test_main_module_exposes_importable_callables_and_catalog(self) -> None:
        callable_tool = get_tool_callable("GOOGLEDRIVE_FIND_FILE")
        spec = get_tool_spec("GOOGLEDRIVE_FIND_FILE")
        self.assertIs(callable_tool, spec.callable)

        catalog = get_tool_catalog()
        self.assertEqual(len(list_available_tools()), len(catalog))
        entry = next(item for item in catalog if item["name"] == "GMAIL_FETCH_EMAILS")
        self.assertEqual("gmail", entry["service"])
        self.assertIn("argsSchema", entry)
        self.assertIn("resultSchema", entry)

        openai_tools = get_openai_tools(
            ["slack_search_messages", "GOOGLECALENDAR_EVENTS_LIST"]
        )
        self.assertEqual(2, len(openai_tools))
        self.assertEqual("function", openai_tools[0]["type"])
        self.assertTrue(openai_tools[0]["strict"])
        self.assertIn("parameters", openai_tools[0])
        self.assertEqual(
            set(openai_tools[0]["parameters"]["properties"].keys()),
            set(openai_tools[0]["parameters"]["required"]),
        )

    def test_reset_helpers_and_http_utility_routes_are_neutral(self) -> None:
        draft_creator = get_tool_callable("GMAIL_CREATE_EMAIL_DRAFT")
        draft_creator(
            recipient_email="finance@corp.com",
            subject="Board follow-up",
            body="Send the latest deck.",
        )
        before_reset = get_tool_spec("GMAIL_LIST_DRAFTS").invoke().result
        self.assertGreater(before_reset.resultSizeEstimate, 1)

        reset_response = reset_tools()
        self.assertTrue(reset_response["ok"])
        self.assertEqual(7, reset_response["serviceCount"])
        self.assertEqual(len(list_available_tools()), reset_response["toolCount"])

        after_reset = get_tool_spec("GMAIL_LIST_DRAFTS").invoke().result
        self.assertEqual(1, after_reset.resultSizeEstimate)

        self.assertEqual({"status": "ok"}, health_check())
        listed = list_tools()
        self.assertEqual(len(list_available_tools()), len(listed["tools"]))

        reset_all_mock_state()

    def test_openai_tool_schemas_satisfy_strict_mode_invariants(self) -> None:
        """Every object schema (including nested) must declare additionalProperties=false
        and list all property names in required. OpenAI rejects strict-mode tools that
        violate either rule, so this test prevents the regression that the strict-mode
        fix in _openai_tool_entry was written to address.
        """
        problems: list[str] = []

        def walk(node: object, path: str) -> None:
            if isinstance(node, dict):
                if node.get("type") == "object":
                    if node.get("additionalProperties") is not False:
                        problems.append(f"{path}: additionalProperties != false")
                    properties = node.get("properties", {})
                    required = set(node.get("required", []))
                    missing = set(properties) - required
                    if missing:
                        problems.append(
                            f"{path}: missing from required: {sorted(missing)}"
                        )
                    for key, value in properties.items():
                        walk(value, f"{path}.{key}")
                for combinator in ("anyOf", "oneOf", "allOf"):
                    for index, sub in enumerate(node.get(combinator) or []):
                        walk(sub, f"{path}.{combinator}[{index}]")
                if "items" in node:
                    walk(node["items"], f"{path}.items")
                for defs_key in ("$defs", "definitions"):
                    for sub_name, sub in (node.get(defs_key) or {}).items():
                        walk(sub, f"{path}.{defs_key}.{sub_name}")

        tools = get_openai_tools()
        self.assertEqual(len(tools), len(list_available_tools()))
        for tool in tools:
            self.assertTrue(tool["strict"], f"{tool['name']} must declare strict=true")
            walk(tool["parameters"], tool["name"])

        if problems:
            self.fail(
                f"{len(problems)} strict-mode schema violations; first few:\n  "
                + "\n  ".join(problems[:8])
            )


if __name__ == "__main__":
    unittest.main()
