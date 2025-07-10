"""Tests for GitHubClient."""

import pytest
from unittest.mock import Mock, patch

from git_data_distiller.github_client import GitHubClient, GitHubRateLimiter
from git_data_distiller.exceptions import (
    AuthenticationError,
    GitHubAPIError,
    PermissionError,
    RateLimitError,
    ResourceNotFoundError,
)


class TestGitHubRateLimiter:
    """Test rate limiter functionality."""
    
    def test_update_from_headers(self):
        """Test updating rate limit info from headers."""
        limiter = GitHubRateLimiter()
        
        headers = {
            "x-ratelimit-remaining": "100",
            "x-ratelimit-limit": "5000",
            "x-ratelimit-reset": "1234567890",
        }
        
        limiter.update_from_headers(headers)
        
        assert limiter.remaining == 100
        assert limiter.limit == 5000
        assert limiter.reset_time == 1234567890
    
    def test_should_wait(self):
        """Test when we should wait for rate limiting."""
        limiter = GitHubRateLimiter()
        
        # Should not wait with plenty remaining
        limiter.remaining = 100
        assert not limiter.should_wait()
        
        # Should wait when low on remaining
        limiter.remaining = 5
        assert limiter.should_wait()


class TestGitHubClient:
    """Test GitHubClient functionality."""
    
    def test_init_with_token(self):
        """Test client initialization with token."""
        client = GitHubClient(token="test_token")
        assert client.token == "test_token"
        assert client.base_url == "https://api.github.com"
    
    def test_init_with_custom_base_url(self):
        """Test client initialization with custom base URL."""
        client = GitHubClient(base_url="https://github.enterprise.com/api/v3/")
        assert client.base_url == "https://github.enterprise.com/api/v3"
    
    def test_parse_github_url_repository(self):
        """Test parsing repository URL."""
        client = GitHubClient()
        result = client.parse_github_url("https://github.com/octocat/Hello-World")
        
        assert result["owner"] == "octocat"
        assert result["repo"] == "Hello-World"
        assert result["type"] == "repository"
    
    def test_parse_github_url_issue(self):
        """Test parsing issue URL."""
        client = GitHubClient()
        result = client.parse_github_url("https://github.com/octocat/Hello-World/issues/123")
        
        assert result["owner"] == "octocat"
        assert result["repo"] == "Hello-World"
        assert result["type"] == "issue"
        assert result["number"] == 123
    
    def test_parse_github_url_pull_request(self):
        """Test parsing pull request URL."""
        client = GitHubClient()
        result = client.parse_github_url("https://github.com/octocat/Hello-World/pull/456")
        
        assert result["owner"] == "octocat"
        assert result["repo"] == "Hello-World"
        assert result["type"] == "pull_request"
        assert result["number"] == 456
    
    def test_parse_github_url_invalid(self):
        """Test parsing invalid URL."""
        client = GitHubClient()
        
        with pytest.raises(ValueError, match="Not a GitHub URL"):
            client.parse_github_url("https://example.com/test")
        
        with pytest.raises(ValueError, match="Invalid GitHub URL format"):
            client.parse_github_url("https://github.com/")
    
    @patch('git_data_distiller.github_client.requests.Session')
    def test_get_handles_404(self, mock_session_class):
        """Test handling 404 responses."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        response = Mock()
        response.status_code = 404
        response.text = "Not found"
        response.headers = {
            "x-ratelimit-remaining": "5000",
            "x-ratelimit-limit": "5000",
            "x-ratelimit-reset": "0"
        }
        
        mock_session.get.return_value = response
        
        client = GitHubClient()
        with pytest.raises(ResourceNotFoundError):
            client.get("repos/test/notfound")
    
    @patch('git_data_distiller.github_client.requests.Session')
    def test_get_handles_401(self, mock_session_class):
        """Test handling 401 authentication errors."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        response = Mock()
        response.status_code = 401
        response.text = "Bad credentials"
        response.headers = {
            "x-ratelimit-remaining": "5000",
            "x-ratelimit-limit": "5000",
            "x-ratelimit-reset": "0"
        }
        
        mock_session.get.return_value = response
        
        client = GitHubClient()
        with pytest.raises(AuthenticationError):
            client.get("user")
    
    @patch('git_data_distiller.github_client.requests.Session')
    def test_get_handles_403(self, mock_session_class):
        """Test handling 403 permission errors."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        response = Mock()
        response.status_code = 403
        response.text = "Forbidden"
        response.headers = {
            "x-ratelimit-remaining": "5000",
            "x-ratelimit-limit": "5000",
            "x-ratelimit-reset": "0"
        }
        
        mock_session.get.return_value = response
        
        client = GitHubClient()
        with pytest.raises(PermissionError):
            client.get("repos/private/repo")
    
    @patch('git_data_distiller.github_client.requests.Session')
    def test_get_handles_429(self, mock_session_class):
        """Test handling 429 rate limit errors."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        response = Mock()
        response.status_code = 429
        response.text = "Rate limit exceeded"
        response.headers = {"x-ratelimit-reset": "1234567890"}
        
        mock_session.get.return_value = response
        
        client = GitHubClient()
        with pytest.raises(RateLimitError) as exc_info:
            client.get("repos/test/repo")
        
        assert exc_info.value.reset_time == 1234567890