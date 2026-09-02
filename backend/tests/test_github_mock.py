from __future__ import annotations

import unittest

from backend.github_mock import (
    TOOL_REGISTRY,
    GitHubMockError,
    reset_github_mock_state,
)
from backend.github_mock.tools import (
    github_actions_list,
    github_add_issue_comment,
    github_create_branch,
    github_create_or_update_file,
    github_create_pull_request,
    github_get_commit,
    github_get_file_contents,
    github_get_me,
    github_issue_read,
    github_issue_write,
    github_label_write,
    github_list_branches,
    github_list_issues,
    github_list_pull_requests,
    github_merge_pull_request,
    github_pull_request_read,
    github_search_code,
    github_search_issues,
    github_star_repository,
    github_unstar_repository,
)


class GitHubMockTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_github_mock_state()

    def test_registry_exposes_all_github_tools(self) -> None:
        self.assertEqual(len(TOOL_REGISTRY), 86)
        for spec in TOOL_REGISTRY.values():
            self.assertEqual(spec.service, "github")

    def test_get_me_and_repo_lookups(self) -> None:
        self.assertEqual(github_get_me().user.login, "avery")
        branches = github_list_branches(repo="orchestrator", owner="instalily").branches
        self.assertGreaterEqual(len(branches), 2)

    def test_issue_lifecycle(self) -> None:
        created = github_issue_write(
            repo="orchestrator",
            owner="instalily",
            method="create",
            title="Smoke",
            body="b",
            labels=["bug"],
        ).issue
        fetched = github_issue_read(
            repo="orchestrator",
            owner="instalily",
            issue_number=created.number,
            method="get",
        ).issue
        self.assertEqual(fetched.title, "Smoke")
        github_add_issue_comment(
            repo="orchestrator",
            owner="instalily",
            issue_number=created.number,
            body="Triaging",
        )
        comments = github_issue_read(
            repo="orchestrator",
            owner="instalily",
            issue_number=created.number,
            method="get_comments",
        ).comments
        self.assertEqual(len(comments), 1)
        github_issue_write(
            repo="orchestrator",
            owner="instalily",
            method="update",
            issue_number=created.number,
            state="closed",
        )
        closed = github_issue_read(
            repo="orchestrator",
            owner="instalily",
            issue_number=created.number,
            method="get",
        ).issue
        self.assertEqual(closed.state, "closed")

    def test_pr_create_read_and_merge(self) -> None:
        pr = github_create_pull_request(
            repo="orchestrator",
            owner="instalily",
            base="main",
            head="develop",
            title="Test PR",
        ).pull_request
        listed = github_list_pull_requests(
            repo="orchestrator", owner="instalily"
        ).pull_requests
        self.assertIn(pr.number, [item.number for item in listed])
        merged = github_merge_pull_request(
            repo="orchestrator",
            owner="instalily",
            pullNumber=pr.number,
        ).pull_request
        self.assertTrue(merged.merged)
        details = github_pull_request_read(
            repo="orchestrator",
            owner="instalily",
            pullNumber=pr.number,
            method="get",
        ).pull_request
        self.assertEqual(details.state, "closed")

    def test_files_branches_and_commits(self) -> None:
        github_create_branch(
            repo="orchestrator",
            owner="instalily",
            branch="topic/spike",
            from_branch="main",
        )
        result = github_create_or_update_file(
            repo="orchestrator",
            owner="instalily",
            path="docs/SPIKE.md",
            branch="topic/spike",
            content="# spike\n",
            message="Add spike doc",
        )
        commit = github_get_commit(
            repo="orchestrator",
            owner="instalily",
            sha=result.commit_sha,
            include_diff=True,
        ).commit
        self.assertIsNotNone(commit.diff)
        contents = github_get_file_contents(
            repo="orchestrator",
            owner="instalily",
            path="docs/SPIKE.md",
            ref="topic/spike",
        )
        self.assertEqual(contents.file.content, "# spike\n")

    def test_star_unstar_and_search(self) -> None:
        github_unstar_repository(repo="orchestrator", owner="instalily")
        github_star_repository(repo="orchestrator", owner="instalily")
        results = github_search_code(query="router").items
        self.assertGreaterEqual(len(results), 1)
        issue_results = github_search_issues(query="launch").items
        self.assertGreaterEqual(len(issue_results), 1)

    def test_actions_list_and_label_lifecycle(self) -> None:
        runs = github_actions_list(
            repo="orchestrator",
            owner="instalily",
            method="list_workflow_runs",
        ).workflow_runs
        self.assertGreaterEqual(len(runs), 1)
        github_label_write(
            repo="orchestrator",
            owner="instalily",
            method="create",
            name="release",
            color="00ff00",
        )
        github_label_write(
            repo="orchestrator",
            owner="instalily",
            method="delete",
            name="release",
        )

    def test_errors_are_deterministic(self) -> None:
        with self.assertRaises(GitHubMockError):
            github_get_file_contents(repo="missing", owner="instalily")
        with self.assertRaises(GitHubMockError):
            github_issue_read(
                repo="orchestrator", owner="instalily", issue_number=999, method="get"
            )
        with self.assertRaises(GitHubMockError):
            github_list_issues(repo="orchestrator", owner="instalily", page=0)


if __name__ == "__main__":
    unittest.main()
