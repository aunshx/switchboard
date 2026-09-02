from __future__ import annotations

import unittest

from backend.linear_mock import (
    TOOL_REGISTRY,
    LinearMockError,
    linear_create_comment,
    linear_create_issue,
    linear_get_issue,
    linear_get_team,
    linear_list_comments,
    linear_list_cycles,
    linear_list_issue_statuses,
    linear_list_issues,
    linear_list_projects,
    linear_list_users,
    linear_search_documentation,
    linear_update_issue,
    reset_linear_mock_state,
)


class LinearMockTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_linear_mock_state()

    def test_registry_exposes_all_linear_tools(self) -> None:
        self.assertEqual(len(TOOL_REGISTRY), 25)
        for spec in TOOL_REGISTRY.values():
            self.assertEqual(spec.service, "linear")

    def test_team_resolution_and_status_listing(self) -> None:
        team = linear_get_team(query="ENG").team
        self.assertEqual(team.id, "team_eng")
        statuses = linear_list_issue_statuses(team="ENG").statuses
        self.assertGreater(len(statuses), 0)
        self.assertEqual(statuses[0].name, "Triage")

    def test_issue_filters_and_relations(self) -> None:
        issues = linear_list_issues(team="ENG", state="In Progress").issues
        self.assertEqual([issue.id for issue in issues], ["ENG-1"])
        with_relations = linear_get_issue(id="ENG-1", includeRelations=True).issue
        self.assertIsNotNone(with_relations.blocks)
        without_relations = linear_get_issue(id="ENG-1", includeRelations=False).issue
        self.assertIsNone(without_relations.blocks)

    def test_create_issue_assigns_next_team_id(self) -> None:
        result = linear_create_issue(title="Smoke", team="ENG", labels=["bug"])
        self.assertTrue(result.issue.id.startswith("ENG-"))
        self.assertNotEqual(result.issue.id, "ENG-1")

    def test_update_issue_changes_state_by_name(self) -> None:
        before = linear_get_issue(id="ENG-2").issue
        self.assertEqual(before.state, "status_eng_todo")
        after = linear_update_issue(id="ENG-2", state="In Progress").issue
        self.assertEqual(after.state, "status_eng_in_progress")

    def test_comments_create_and_list(self) -> None:
        before = linear_list_comments(issueId="ENG-1").count
        comment = linear_create_comment(body="Looks good", issueId="ENG-1").comment
        self.assertEqual(comment.issueId, "ENG-1")
        after = linear_list_comments(issueId="ENG-1")
        self.assertEqual(after.count, before + 1)

    def test_cycles_users_projects_and_docs(self) -> None:
        cycles = linear_list_cycles(teamId="ENG", type="current").cycles
        self.assertEqual(len(cycles), 1)
        users = linear_list_users(team="ENG").users
        self.assertGreaterEqual(len(users), 1)
        projects = linear_list_projects(team="ENG").projects
        self.assertEqual({project.id for project in projects}, {"proj_orchestrator"})
        docs = linear_search_documentation(query="cycles").results
        self.assertGreaterEqual(len(docs), 1)

    def test_errors_are_deterministic(self) -> None:
        with self.assertRaises(LinearMockError):
            linear_get_issue(id="MISSING-99")
        with self.assertRaises(LinearMockError):
            linear_create_issue(title="x", team="UNKNOWN")
        with self.assertRaises(LinearMockError):
            linear_list_comments(issueId="")


if __name__ == "__main__":
    unittest.main()
