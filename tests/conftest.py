"""Pytest configuration and fixtures."""

import pytest
from unittest.mock import Mock, patch


@pytest.fixture
def mock_github_client():
    """Mock GitHub client for testing."""
    client = Mock()
    client.base_url = "https://api.github.com"
    client.token = "test_token"
    client.rate_limiter = Mock()
    client.rate_limiter.remaining = 5000
    client.rate_limiter.limit = 5000
    return client


@pytest.fixture
def sample_repository_data():
    """Sample repository data for testing."""
    return {
        "name": "test-repo",
        "full_name": "testuser/test-repo",
        "description": "A test repository",
        "html_url": "https://github.com/testuser/test-repo",
        "clone_url": "https://github.com/testuser/test-repo.git",
        "language": "Python",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-15T00:00:00Z",
        "pushed_at": "2024-01-14T00:00:00Z",
        "size": 1234,
        "stargazers_count": 10,
        "watchers_count": 10,
        "forks_count": 5,
        "open_issues_count": 3,
        "default_branch": "main",
    }


@pytest.fixture
def sample_issue_data():
    """Sample issue data for testing."""
    return {
        "number": 1,
        "title": "Test Issue",
        "body": "This is a test issue",
        "state": "open",
        "labels": [{"name": "bug", "color": "ff0000"}],
        "milestone": None,
        "assignee": {"login": "testuser"},
        "created_at": "2024-01-10T00:00:00Z",
        "updated_at": "2024-01-11T00:00:00Z",
        "closed_at": None,
        "comments": 2,
    }


@pytest.fixture
def sample_pr_data():
    """Sample pull request data for testing."""
    return {
        "number": 2,
        "title": "Test PR",
        "body": "This is a test pull request",
        "state": "open",
        "head": {"ref": "feature-branch"},
        "base": {"ref": "main"},
        "labels": [],
        "milestone": None,
        "assignee": None,
        "created_at": "2024-01-12T00:00:00Z",
        "updated_at": "2024-01-13T00:00:00Z",
        "closed_at": None,
        "merged_at": None,
        "additions": 10,
        "deletions": 5,
        "changed_files": 3,
    }


@pytest.fixture
def mock_response_with_link_header():
    """Mock response with Link header for pagination testing."""
    response = Mock()
    response.status_code = 200
    response.ok = True
    response.headers = {
        "Link": '<https://api.github.com/repos/test/repo/issues?page=2>; rel="next", <https://api.github.com/repos/test/repo/issues?page=5>; rel="last"',
        "x-ratelimit-remaining": "5000",
        "x-ratelimit-limit": "5000",
        "x-ratelimit-reset": "1234567890",
    }
    response.json.return_value = [{"id": 1}, {"id": 2}]
    return response