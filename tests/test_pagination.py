"""Test cursor-based pagination implementation."""

import pytest
from unittest.mock import Mock, patch, call

from git_data_distiller.github_client import GitHubClient


class TestCursorPagination:
    """Test cursor-based pagination functionality."""

    def test_parse_link_header(self):
        """Test parsing of Link header for next URL."""
        client = GitHubClient()
        
        # Test with next link
        link_header = '<https://api.github.com/repos/test/repo/issues?after=cursor123>; rel="next", <https://api.github.com/repos/test/repo/issues?after=cursor999>; rel="last"'
        next_url = client._get_next_url_from_link_header(link_header)
        assert next_url == "https://api.github.com/repos/test/repo/issues?after=cursor123"
        
        # Test without next link
        link_header = '<https://api.github.com/repos/test/repo/issues?after=cursor999>; rel="last"'
        next_url = client._get_next_url_from_link_header(link_header)
        assert next_url is None
        
        # Test empty header
        next_url = client._get_next_url_from_link_header("")
        assert next_url is None

    @patch('git_data_distiller.github_client.requests.Session')
    def test_cursor_pagination_with_link_header(self, mock_session_class):
        """Test cursor-based pagination using Link headers."""
        # Setup mock session
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        # Mock the headers update call
        mock_session.headers = Mock()
        mock_session.headers.update = Mock()
        
        # Create responses for pagination
        response1 = Mock()
        response1.status_code = 200
        response1.ok = True
        response1.headers = {
            "Link": '<https://api.github.com/repos/test/repo/issues?after=cursor123>; rel="next"',
            "x-ratelimit-remaining": "5000",
            "x-ratelimit-limit": "5000",
            "x-ratelimit-reset": "1234567890",
        }
        response1.json.return_value = [{"id": 1}, {"id": 2}]
        
        response2 = Mock()
        response2.status_code = 200
        response2.ok = True
        response2.headers = {
            "Link": "",  # No Link header on last page
            "x-ratelimit-remaining": "4999",
            "x-ratelimit-limit": "5000",
            "x-ratelimit-reset": "1234567890",
        }
        response2.json.return_value = [{"id": 3}]  # Last page has fewer items
        
        mock_session.get.side_effect = [response1, response2]
        
        # Test pagination
        client = GitHubClient()
        results = client.get_paginated("repos/test/repo/issues", per_page=2)
        
        assert len(results) == 3
        assert results[0]["id"] == 1
        assert results[1]["id"] == 2
        assert results[2]["id"] == 3
        
        # Verify correct URLs were called
        assert mock_session.get.call_count == 2
        first_call = mock_session.get.call_args_list[0]
        assert "repos/test/repo/issues" in first_call[0][0]
        
        second_call = mock_session.get.call_args_list[1]
        assert second_call[0][0] == "https://api.github.com/repos/test/repo/issues?after=cursor123"

    @patch('git_data_distiller.github_client.requests.Session')
    def test_fallback_to_page_pagination(self, mock_session_class):
        """Test fallback to page-based pagination when cursor fails."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        # First response returns 422 error for cursor pagination
        error_response = Mock()
        error_response.status_code = 422
        error_response.ok = False
        error_response.text = "Pagination with the page parameter is not supported for large datasets, please use cursor based pagination"
        error_response.headers = {"x-ratelimit-remaining": "5000", "x-ratelimit-limit": "5000"}
        error_response.json.return_value = []  # Add json method for error response
        
        # But since this is Hello-World repo, it might still work with page-based for small datasets
        success_response = Mock()
        success_response.status_code = 200
        success_response.ok = True
        success_response.headers = {"x-ratelimit-remaining": "4999", "x-ratelimit-limit": "5000"}
        success_response.json.return_value = [{"id": 1}]
        
        mock_session.get.side_effect = [error_response, success_response]
        
        # Mock the headers update call
        mock_session.headers = Mock()
        mock_session.headers.update = Mock()
        
        client = GitHubClient()
        results = client.get_paginated("repos/test/repo/issues", per_page=1)
        
        # Should handle the error gracefully
        assert len(results) == 1
        assert results[0]["id"] == 1

    @patch('git_data_distiller.github_client.requests.Session')
    def test_empty_results(self, mock_session_class):
        """Test handling of empty result sets."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        response = Mock()
        response.status_code = 200
        response.ok = True
        response.headers = {"x-ratelimit-remaining": "5000", "x-ratelimit-limit": "5000"}
        response.json.return_value = []
        
        mock_session.get.return_value = response
        
        client = GitHubClient()
        results = client.get_paginated("repos/test/repo/issues")
        
        assert results == []
        assert mock_session.get.call_count == 1

    @patch('git_data_distiller.github_client.requests.Session')
    def test_max_pages_limit(self, mock_session_class):
        """Test that max_pages parameter limits pagination."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        # Create responses that would normally paginate forever
        response = Mock()
        response.status_code = 200
        response.ok = True
        response.json.return_value = [{"id": i} for i in range(100)]
        
        # Always return a next link
        response.headers = {
            "Link": '<https://api.github.com/repos/test/repo/issues?page=next>; rel="next"',
            "x-ratelimit-remaining": "5000",
            "x-ratelimit-limit": "5000",
        }
        
        mock_session.get.return_value = response
        
        client = GitHubClient()
        results = client.get_paginated("repos/test/repo/issues", max_pages=2)
        
        # Should only make 2 requests due to max_pages
        assert len(results) == 200  # 2 pages * 100 items
        assert mock_session.get.call_count == 2