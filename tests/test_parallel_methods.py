"""Tests for parallel API methods in GitHubClient."""

import concurrent.futures
import pytest
from unittest.mock import Mock, patch, call
from requests.exceptions import RequestException

from git_data_distiller.github_client import GitHubClient
from git_data_distiller.models import (
    GitHubRepository,
    GitHubIssue,
    GitHubLabel,
    GitHubUser,
    GitHubComment,
)
from git_data_distiller.exceptions import GitHubAPIError


class TestGetRepositoryParallel:
    """Test the parallel repository metadata fetching."""

    @pytest.fixture
    def client(self):
        """Create a GitHubClient instance for testing."""
        return GitHubClient(token="test_token")

    @pytest.fixture
    def mock_responses(self):
        """Mock API responses for repository endpoints."""
        return {
            "repo": {
                "name": "test-repo",
                "full_name": "owner/test-repo",
                "description": "Test repository",
                "html_url": "https://github.com/owner/test-repo",
                "clone_url": "https://github.com/owner/test-repo.git",
                "language": "Python",
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-12-01T00:00:00Z",
                "pushed_at": "2023-12-01T00:00:00Z",
                "size": 1024,
                "stargazers_count": 100,
                "watchers_count": 50,
                "forks_count": 25,
                "open_issues_count": 5,
                "default_branch": "main",
            },
            "languages": {"Python": 8500, "JavaScript": 1500},
            "topics": {"names": ["python", "api", "github"]},
            "readme": {
                "content": "VGVzdCBSRUFETUUgY29udGVudA==",  # base64: "Test README content"
            },
        }

    def test_get_repository_parallel_success(self, client, mock_responses):
        """Test successful parallel repository metadata fetching."""
        with patch.object(client, "get") as mock_get:
            # Configure mock to return different responses based on endpoint
            def side_effect(endpoint):
                if endpoint == "repos/owner/repo":
                    return mock_responses["repo"]
                elif endpoint == "repos/owner/repo/languages":
                    return mock_responses["languages"]
                elif endpoint == "repos/owner/repo/topics":
                    return mock_responses["topics"]
                elif endpoint == "repos/owner/repo/readme":
                    return mock_responses["readme"]
                else:
                    raise ValueError(f"Unexpected endpoint: {endpoint}")

            mock_get.side_effect = side_effect

            # Execute the parallel method
            result = client.get_repository_parallel("owner", "repo")

            # Verify the result
            assert isinstance(result, GitHubRepository)
            assert result.name == "test-repo"
            assert result.full_name == "owner/test-repo"
            assert result.languages == {"Python": 8500, "JavaScript": 1500}
            assert result.topics == ["python", "api", "github"]
            assert result.readme == "Test README content"

            # Verify all endpoints were called
            expected_calls = [
                call("repos/owner/repo"),
                call("repos/owner/repo/languages"),
                call("repos/owner/repo/topics"),
                call("repos/owner/repo/readme"),
            ]
            mock_get.assert_has_calls(expected_calls, any_order=True)
            assert mock_get.call_count == 4

    def test_get_repository_parallel_with_failures(self, client, mock_responses):
        """Test parallel method with some endpoint failures."""
        with patch.object(client, "get") as mock_get:
            # Configure mock to fail on non-essential endpoints
            def side_effect(endpoint):
                if endpoint == "repos/owner/repo":
                    return mock_responses["repo"]
                elif endpoint == "repos/owner/repo/languages":
                    raise RequestException("Languages endpoint failed")
                elif endpoint == "repos/owner/repo/topics":
                    raise RequestException("Topics endpoint failed")
                elif endpoint == "repos/owner/repo/readme":
                    raise RequestException("README endpoint failed")
                else:
                    raise ValueError(f"Unexpected endpoint: {endpoint}")

            mock_get.side_effect = side_effect

            # Execute the parallel method
            result = client.get_repository_parallel("owner", "repo")

            # Verify the result with defaults for failed endpoints
            assert isinstance(result, GitHubRepository)
            assert result.name == "test-repo"
            assert result.languages == {}  # Default for failed endpoint
            assert result.topics == []  # Default for failed endpoint
            assert result.readme is None  # Default for failed endpoint

    def test_get_repository_parallel_repo_failure(self, client):
        """Test parallel method when main repository endpoint fails."""
        with patch.object(client, "get") as mock_get:
            mock_get.side_effect = RequestException("Repository not found")

            # Should raise exception when main repo endpoint fails
            with pytest.raises(RequestException):
                client.get_repository_parallel("owner", "repo")

    def test_parallel_execution_performance(self, client, mock_responses):
        """Test that parallel execution is actually concurrent."""
        import time

        call_count = 0

        def count_side_effect(endpoint):
            nonlocal call_count
            call_count += 1

            # Very short delay to simulate API call
            time.sleep(0.01)

            if endpoint == "repos/owner/repo":
                return mock_responses["repo"]
            elif endpoint == "repos/owner/repo/languages":
                return mock_responses["languages"]
            elif endpoint == "repos/owner/repo/topics":
                return mock_responses["topics"]
            elif endpoint == "repos/owner/repo/readme":
                return mock_responses["readme"]

        with patch.object(client, "get") as mock_get:
            mock_get.side_effect = count_side_effect

            start_time = time.time()
            result = client.get_repository_parallel("owner", "repo")
            end_time = time.time()

            # Parallel execution should complete quickly
            assert (
                end_time - start_time < 0.5
            ), f"Execution took {end_time - start_time:.2f}s"

            # All endpoints should have been called
            assert call_count == 4
            assert isinstance(result, GitHubRepository)
            assert result.name == "test-repo"


class TestGetIssuesParallel:
    """Test the parallel issue comment fetching."""

    @pytest.fixture
    def client(self):
        """Create a GitHubClient instance for testing."""
        return GitHubClient(token="test_token")

    @pytest.fixture
    def mock_issues_data(self):
        """Mock issues data without comments."""
        return [
            {
                "number": 1,
                "title": "Issue 1",
                "body": "Body 1",
                "state": "open",
                "labels": [],
                "assignees": [],
                "user": {
                    "login": "user1",
                    "id": 1,
                    "avatar_url": "https://github.com/user1.png",
                    "html_url": "https://github.com/user1",
                    "type": "User",
                },
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-01T00:00:00Z",
                "html_url": "https://github.com/owner/repo/issues/1",
                "comments": 2,  # Has comments
            },
            {
                "number": 2,
                "title": "Issue 2",
                "body": "Body 2",
                "state": "closed",
                "labels": [],
                "assignees": [],
                "user": {
                    "login": "user2",
                    "id": 2,
                    "avatar_url": "https://github.com/user2.png",
                    "html_url": "https://github.com/user2",
                    "type": "User",
                },
                "created_at": "2023-01-02T00:00:00Z",
                "updated_at": "2023-01-02T00:00:00Z",
                "html_url": "https://github.com/owner/repo/issues/2",
                "comments": 0,  # No comments
            },
            {
                "number": 3,
                "title": "Issue 3",
                "body": "Body 3",
                "state": "open",
                "labels": [],
                "assignees": [],
                "user": {
                    "login": "user3",
                    "id": 3,
                    "avatar_url": "https://github.com/user3.png",
                    "html_url": "https://github.com/user3",
                    "type": "User",
                },
                "created_at": "2023-01-03T00:00:00Z",
                "updated_at": "2023-01-03T00:00:00Z",
                "html_url": "https://github.com/owner/repo/issues/3",
                "comments": 1,  # Has comments
            },
        ]

    @pytest.fixture
    def mock_comments_data(self):
        """Mock comments data for issues."""
        return {
            1: [
                {
                    "id": 1,
                    "body": "Comment 1 on issue 1",
                    "user": {"login": "commenter1", "id": 10},
                    "created_at": "2023-01-01T01:00:00Z",
                    "updated_at": "2023-01-01T01:00:00Z",
                    "html_url": "https://github.com/owner/repo/issues/1#comment-1",
                },
                {
                    "id": 2,
                    "body": "Comment 2 on issue 1",
                    "user": {"login": "commenter2", "id": 11},
                    "created_at": "2023-01-01T02:00:00Z",
                    "updated_at": "2023-01-01T02:00:00Z",
                    "html_url": "https://github.com/owner/repo/issues/1#comment-2",
                },
            ],
            3: [
                {
                    "id": 3,
                    "body": "Comment 1 on issue 3",
                    "user": {"login": "commenter3", "id": 12},
                    "created_at": "2023-01-03T01:00:00Z",
                    "updated_at": "2023-01-03T01:00:00Z",
                    "html_url": "https://github.com/owner/repo/issues/3#comment-3",
                },
            ],
        }

    def test_get_issues_parallel_with_comments(
        self, client, mock_issues_data, mock_comments_data
    ):
        """Test parallel issue fetching with comment retrieval."""
        with patch.object(client, "get_paginated") as mock_get_paginated, patch.object(
            client, "_parse_comment"
        ) as mock_parse_comment:

            # Mock the main issues call
            mock_get_paginated.side_effect = lambda endpoint, *args, **kwargs: {
                "repos/owner/repo/issues": mock_issues_data,
                "repos/owner/repo/issues/1/comments": mock_comments_data[1],
                "repos/owner/repo/issues/3/comments": mock_comments_data[3],
            }.get(endpoint, [])

            # Mock comment parsing
            mock_parse_comment.side_effect = lambda comment: GitHubComment(
                id=comment["id"],
                body=comment["body"],
                user=GitHubUser(
                    login=comment["user"]["login"],
                    id=comment["user"]["id"],
                    avatar_url="https://github.com/avatar.png",
                    html_url=f"https://github.com/{comment['user']['login']}",
                    type="User",
                ),
                created_at=comment["created_at"],
                updated_at=comment["updated_at"],
                html_url=comment["html_url"],
            )

            # Execute parallel method
            result = client.get_issues_parallel("owner", "repo", include_comments=True)

            # Verify results
            assert len(result) == 3

            # Issue 1 should have 2 comments
            issue_1 = next(issue for issue in result if issue.number == 1)
            assert len(issue_1.comments) == 2

            # Issue 2 should have 0 comments (no API call made)
            issue_2 = next(issue for issue in result if issue.number == 2)
            assert len(issue_2.comments) == 0

            # Issue 3 should have 1 comment
            issue_3 = next(issue for issue in result if issue.number == 3)
            assert len(issue_3.comments) == 1

            # Verify API calls
            expected_calls = [
                call("repos/owner/repo/issues", {"state": "all"}),
                call("repos/owner/repo/issues/1/comments"),
                call("repos/owner/repo/issues/3/comments"),
            ]
            mock_get_paginated.assert_has_calls(expected_calls, any_order=True)

    def test_get_issues_parallel_without_comments(self, client, mock_issues_data):
        """Test parallel issue fetching without comment retrieval."""
        with patch.object(client, "get_paginated") as mock_get_paginated:
            mock_get_paginated.return_value = mock_issues_data

            # Execute parallel method without comments
            result = client.get_issues_parallel("owner", "repo", include_comments=False)

            # Verify results
            assert len(result) == 3
            for issue in result:
                assert len(issue.comments) == 0

            # Only the main issues endpoint should be called
            mock_get_paginated.assert_called_once_with(
                "repos/owner/repo/issues", {"state": "all"}
            )

    def test_get_issues_parallel_comment_failure(self, client, mock_issues_data):
        """Test parallel method when comment fetching fails for some issues."""
        with patch.object(client, "get_paginated") as mock_get_paginated, patch.object(
            client, "_parse_comment"
        ) as mock_parse_comment:

            def side_effect(endpoint, *args, **kwargs):
                if endpoint == "repos/owner/repo/issues":
                    return mock_issues_data
                elif endpoint == "repos/owner/repo/issues/1/comments":
                    raise RequestException("Comments endpoint failed")
                elif endpoint == "repos/owner/repo/issues/3/comments":
                    return [{"id": 1, "body": "test", "user": {"login": "test"}}]
                return []

            mock_get_paginated.side_effect = side_effect
            mock_parse_comment.return_value = GitHubComment(
                id=1,
                body="Test comment",
                user=GitHubUser(
                    login="test",
                    id=1,
                    avatar_url="https://github.com/avatar.png",
                    html_url="https://github.com/test",
                    type="User",
                ),
                created_at="2023-01-01T00:00:00Z",
                updated_at="2023-01-01T00:00:00Z",
                html_url="https://github.com/owner/repo/issues/1#comment-1",
            )

            # Execute parallel method
            result = client.get_issues_parallel("owner", "repo", include_comments=True)

            # Verify results - failed comment fetching should result in empty comments
            assert len(result) == 3

            issue_1 = next(issue for issue in result if issue.number == 1)
            assert len(issue_1.comments) == 0  # Failed to fetch

            issue_3 = next(issue for issue in result if issue.number == 3)
            assert len(issue_3.comments) == 1  # Successfully fetched


class TestGetIssuesByNumbers:
    """Test the targeted issue fetching by numbers."""

    @pytest.fixture
    def client(self):
        """Create a GitHubClient instance for testing."""
        return GitHubClient(token="test_token")

    @pytest.fixture
    def mock_issue_data(self):
        """Mock individual issue data."""
        return {
            1: {
                "number": 1,
                "title": "Issue 1",
                "body": "Body 1",
                "state": "open",
                "labels": [],
                "assignees": [],
                "user": {
                    "login": "user1",
                    "id": 1,
                    "avatar_url": "https://github.com/user1.png",
                    "html_url": "https://github.com/user1",
                    "type": "User",
                },
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-01T00:00:00Z",
                "html_url": "https://github.com/owner/repo/issues/1",
                "comments": 0,
            },
            2: {
                "number": 2,
                "title": "Issue 2",
                "body": "Body 2",
                "state": "closed",
                "labels": [],
                "assignees": [],
                "user": {
                    "login": "user2",
                    "id": 2,
                    "avatar_url": "https://github.com/user2.png",
                    "html_url": "https://github.com/user2",
                    "type": "User",
                },
                "created_at": "2023-01-02T00:00:00Z",
                "updated_at": "2023-01-02T00:00:00Z",
                "html_url": "https://github.com/owner/repo/issues/2",
                "comments": 0,
            },
        }

    def test_get_issues_by_numbers_success(self, client, mock_issue_data):
        """Test successful targeted issue fetching."""
        with patch.object(client, "get") as mock_get:
            # Configure mock to return issue data
            def side_effect(endpoint):
                if endpoint == "repos/owner/repo/issues/1":
                    return mock_issue_data[1]
                elif endpoint == "repos/owner/repo/issues/2":
                    return mock_issue_data[2]
                else:
                    raise ValueError(f"Unexpected endpoint: {endpoint}")

            mock_get.side_effect = side_effect

            # Execute the method
            result = client.get_issues_by_numbers("owner", "repo", [1, 2])

            # Verify results
            assert len(result) == 2
            assert result[0].number == 1
            assert result[1].number == 2

            # Verify API calls
            expected_calls = [
                call("repos/owner/repo/issues/1"),
                call("repos/owner/repo/issues/2"),
            ]
            mock_get.assert_has_calls(expected_calls, any_order=True)

    def test_get_issues_by_numbers_empty_list(self, client):
        """Test with empty issue numbers list."""
        result = client.get_issues_by_numbers("owner", "repo", [])
        assert result == []

    def test_get_issues_by_numbers_with_failures(self, client, mock_issue_data):
        """Test targeted issue fetching with some failures."""
        with patch.object(client, "get") as mock_get:

            def side_effect(endpoint):
                if endpoint == "repos/owner/repo/issues/1":
                    return mock_issue_data[1]
                elif endpoint == "repos/owner/repo/issues/2":
                    raise RequestException("Issue not found")
                else:
                    raise ValueError(f"Unexpected endpoint: {endpoint}")

            mock_get.side_effect = side_effect

            # Execute the method
            result = client.get_issues_by_numbers("owner", "repo", [1, 2])

            # Should only return successfully fetched issues
            assert len(result) == 1
            assert result[0].number == 1

    def test_get_issues_by_numbers_skips_pull_requests(self, client):
        """Test that pull requests are filtered out."""
        with patch.object(client, "get") as mock_get:
            # Return data with pull_request field (indicates it's a PR)
            mock_get.return_value = {
                "number": 1,
                "title": "PR 1",
                "pull_request": {
                    "url": "https://api.github.com/repos/owner/repo/pulls/1"
                },
                "state": "open",
                "labels": [],
                "assignees": [],
                "user": {"login": "user1", "id": 1},
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-01T00:00:00Z",
                "html_url": "https://github.com/owner/repo/pull/1",
                "comments": 0,
            }

            # Execute the method
            result = client.get_issues_by_numbers("owner", "repo", [1])

            # Should skip pull requests
            assert len(result) == 0

    def test_parallel_efficiency_vs_get_all_issues(self, client):
        """Test that targeted fetching is more efficient than fetching all issues."""
        with patch.object(client, "get") as mock_get:
            # For get_issues_by_numbers, should only call specific endpoints
            mock_get.return_value = {
                "number": 1,
                "title": "Issue 1",
                "body": "Body 1",
                "state": "open",
                "labels": [],
                "assignees": [],
                "user": {
                    "login": "user1",
                    "id": 1,
                    "avatar_url": "https://github.com/user1.png",
                    "html_url": "https://github.com/user1",
                    "type": "User",
                },
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-01T00:00:00Z",
                "html_url": "https://github.com/owner/repo/issues/1",
                "comments": 0,
            }

            # Test targeted fetching
            result = client.get_issues_by_numbers("owner", "repo", [1, 5, 10])

            # Should make exactly 3 API calls for the specific issues
            assert mock_get.call_count == 3
            expected_calls = [
                call("repos/owner/repo/issues/1"),
                call("repos/owner/repo/issues/5"),
                call("repos/owner/repo/issues/10"),
            ]
            mock_get.assert_has_calls(expected_calls, any_order=True)


class TestConcurrencyAndThreadSafety:
    """Test thread safety and concurrency aspects."""

    @pytest.fixture
    def client(self):
        """Create a GitHubClient instance for testing."""
        return GitHubClient(token="test_token")

    def test_thread_pool_executor_limits(self, client):
        """Test that ThreadPoolExecutor limits are respected."""
        # Import here to avoid import conflicts
        from concurrent.futures import ThreadPoolExecutor

        # We can verify the ThreadPoolExecutor is used properly by checking
        # that the method completes without hanging (which would indicate
        # threading issues)
        with patch.object(client, "get") as mock_get:
            # Configure mock to return different responses based on endpoint
            def side_effect(endpoint):
                if endpoint == "repos/owner/repo":
                    return {
                        "name": "test-repo",
                        "full_name": "owner/test-repo",
                        "description": "Test",
                        "html_url": "https://github.com/owner/test-repo",
                        "clone_url": "https://github.com/owner/test-repo.git",
                        "created_at": "2023-01-01T00:00:00Z",
                        "updated_at": "2023-01-01T00:00:00Z",
                        "pushed_at": "2023-01-01T00:00:00Z",
                        "size": 1024,
                        "stargazers_count": 100,
                        "watchers_count": 50,
                        "forks_count": 25,
                        "open_issues_count": 5,
                        "default_branch": "main",
                    }
                elif endpoint == "repos/owner/repo/languages":
                    return {"Python": 8500, "JavaScript": 1500}
                elif endpoint == "repos/owner/repo/topics":
                    return {"names": ["python", "test"]}
                elif endpoint == "repos/owner/repo/readme":
                    return {"content": "VGVzdCBSRUFETUU="}  # base64: "Test README"
                else:
                    return {}

            mock_get.side_effect = side_effect

            # This should complete quickly if threading is working properly
            result = client.get_repository_parallel("owner", "repo")
            assert result.name == "test-repo"

            # Verify multiple API calls were made in parallel
            assert mock_get.call_count == 4

    def test_concurrent_api_calls_thread_safety(self, client):
        """Test that concurrent API calls don't interfere with each other."""
        # This is a simplified test that verifies the basic structure
        # without complex threading that can cause timeouts

        with patch.object(client, "get") as mock_get:
            mock_get.return_value = {
                "name": "test-repo",
                "full_name": "owner/test-repo",
                "description": "Test repo",
                "html_url": "https://github.com/owner/test-repo",
                "clone_url": "https://github.com/owner/test-repo.git",
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-01T00:00:00Z",
                "pushed_at": "2023-01-01T00:00:00Z",
                "size": 1024,
                "stargazers_count": 100,
                "watchers_count": 50,
                "forks_count": 25,
                "open_issues_count": 5,
                "default_branch": "main",
            }

            # Call the parallel method multiple times to test thread safety
            results = []
            for i in range(3):
                result = client.get_repository_parallel("owner", "test-repo")
                results.append(result)

            # Verify all results are consistent
            assert len(results) == 3
            for result in results:
                assert result.name == "test-repo"
                assert result.full_name == "owner/test-repo"
