# Git Data Distiller - Implementation Plan

## Overview
This document outlines a systematic approach to address critical issues found during testing, prioritized by severity and dependency.

## Phase 1: Critical Security Fix (15 minutes)

### 1.1 Secure the Exposed Token
```bash
# Step 1: Add to .gitignore
echo "git-distiller.yaml" >> .gitignore

# Step 2: Remove from current commit
git rm --cached git-distiller.yaml

# Step 3: Commit the change
git commit -m "Remove sensitive config file and add to .gitignore"
```

### 1.2 Token Rotation
1. Go to GitHub Settings → Developer settings → Personal access tokens
2. Find and revoke token ending in "xJZ2"
3. Generate new token with minimal required scopes:
   - `repo` (for private repos)
   - `read:org` (for organization repos)
4. Store securely using environment variable

### 1.3 Update Example Config
```yaml
# git-distiller.yaml.example
github_token: "YOUR_GITHUB_TOKEN_HERE"  # Or use GITHUB_TOKEN env var
github_base_url: "https://api.github.com"
log_level: INFO
# ... rest of config
```

## Phase 2: Fix GitHub API Pagination (3-4 hours)

### 2.1 Understanding the Problem
GitHub's API now requires cursor-based pagination for large datasets:
- Old: `?page=2&per_page=100`
- New: `?after=cursor_value&per_page=100`

### 2.2 Implementation Strategy

#### Update `github_client.py` - `_paginate()` method:
```python
def _paginate(self, url: str, params: Optional[Dict] = None) -> Iterator[Dict[str, Any]]:
    """
    Paginate through API results using cursor-based pagination.
    Falls back to page-based for backwards compatibility.
    """
    params = params or {}
    params['per_page'] = params.get('per_page', 100)
    
    # Try cursor-based pagination first
    use_cursor = True
    next_url = url
    
    while next_url:
        response = self._make_request(next_url, params=params if next_url == url else None)
        
        if response.status_code == 422 and "cursor based pagination" in response.text:
            # Fallback to page-based if cursor not supported
            use_cursor = False
            params['page'] = 1
            continue
            
        response.raise_for_status()
        data = response.json()
        
        # Yield results
        if isinstance(data, list):
            yield from data
        else:
            yield data
            
        # Get next page URL from Link header
        next_url = self._get_next_url(response.headers.get('Link', ''))
        
        # If no Link header, try page-based pagination
        if not next_url and not use_cursor and isinstance(data, list) and len(data) == params['per_page']:
            params['page'] = params.get('page', 1) + 1
            next_url = url

def _get_next_url(self, link_header: str) -> Optional[str]:
    """Parse Link header to get next page URL."""
    if not link_header:
        return None
        
    # Parse Link header: <url>; rel="next"
    for link in link_header.split(','):
        if 'rel="next"' in link:
            return link.split('<')[1].split('>')[0]
    return None
```

#### Update API methods to remove page parameter:
```python
def get_issues(self, owner: str, repo: str, state: str = "all", 
               labels: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Get repository issues using cursor-based pagination."""
    url = f"{self.base_url}/repos/{owner}/{repo}/issues"
    params = {
        "state": state,
        "per_page": 100  # Remove 'page' parameter
    }
    if labels:
        params["labels"] = ",".join(labels)
    
    return list(self._paginate(url, params))
```

### 2.3 Testing Strategy
1. Test with small repos (< 100 items)
2. Test with octocat/Hello-World (known large dataset)
3. Verify both cursor and page-based fallback work

## Phase 3: Code Quality Fixes (2 hours)

### 3.1 Fix Star Imports
Replace in `github_client.py`:
```python
# Old
from .models import *

# New
from .models import (
    GitHubRepository,
    GitHubIssue,
    GitHubPullRequest,
    GitHubUser,
    GitHubLabel,
    GitHubMilestone,
    GitHubComment,
    GitHubCommit,
    GitHubFile,
    GitHubDiscussion,
    DistilledData
)
```

### 3.2 Remove Unused Imports
Files to clean:
- `cli.py`: Remove `json`, `Optional`
- `config.py`: Remove `List` 
- `extractors.py`: Remove unused model imports
- `formatters.py`: Remove `json`, `List`, `Template`

### 3.3 Fix Line Length
```bash
# Configure black for 88 char limit
black src/ --line-length 88

# Update .flake8 config
[flake8]
max-line-length = 88
extend-ignore = E203, W503
```

### 3.4 Fix Other Issues
- `cache.py:202`: Replace bare except with specific exception
- `cache.py:250`: Add missing List import
- `cli.py:321`: Fix f-string without placeholders

## Phase 4: Test Infrastructure (3 hours)

### 4.1 Create Test Structure
```
tests/
├── __init__.py
├── conftest.py          # Pytest fixtures
├── test_cli.py          # CLI command tests
├── test_github_client.py # API client tests
├── test_pagination.py    # Pagination-specific tests
└── fixtures/            # Mock API responses
    ├── issues.json
    ├── pull_requests.json
    └── repository.json
```

### 4.2 Key Test Cases
```python
# test_pagination.py
import pytest
from unittest.mock import Mock, patch

class TestCursorPagination:
    def test_cursor_pagination_with_link_header(self):
        """Test cursor-based pagination using Link headers."""
        # Mock response with Link header
        
    def test_fallback_to_page_pagination(self):
        """Test fallback when cursor pagination fails."""
        
    def test_empty_results(self):
        """Test handling of empty result sets."""
        
    def test_single_page_results(self):
        """Test when all results fit in one page."""
```

### 4.3 Integration Tests
```python
# test_github_client.py
@pytest.mark.integration
def test_large_repository_pagination():
    """Test with a known large repository."""
    client = GitHubClient()
    issues = client.get_issues("microsoft", "vscode")
    assert len(issues) > 100  # Should handle pagination
```

## Phase 5: Documentation Updates (1 hour)

### 5.1 Update README.md
Add section on pagination:
```markdown
## Known Limitations

### GitHub API Pagination
For repositories with large numbers of issues or pull requests (>1000), 
the tool uses cursor-based pagination which may take longer to process. 
Consider using the `--max-items` flag to limit results:

```bash
git-distiller extract <url> --max-items 100
```
```

### 5.2 Update CLAUDE.md
Add pagination notes for AI assistants.

### 5.3 Create CHANGELOG.md
Document breaking changes and fixes.

## Implementation Timeline

### Day 1 (4 hours)
- [ ] Morning: Security fixes (30 min)
- [ ] Morning: Start pagination implementation (2 hours)
- [ ] Afternoon: Complete pagination + testing (1.5 hours)

### Day 2 (4 hours)
- [ ] Morning: Code quality fixes (2 hours)
- [ ] Afternoon: Test infrastructure setup (2 hours)

### Day 3 (2 hours)
- [ ] Documentation updates (1 hour)
- [ ] Final testing and validation (1 hour)

## Success Metrics

1. **Security**: No exposed tokens in repository
2. **Functionality**: Successfully extract from repos with 1000+ issues
3. **Code Quality**: Zero flake8 violations
4. **Testing**: Core functionality covered with tests
5. **Performance**: Pagination completes within reasonable time

## Rollback Plan

If cursor pagination causes issues:
1. Add feature flag: `--use-legacy-pagination`
2. Limit to smaller datasets by default
3. Document known working repositories

## Notes

- Keep changes backwards compatible where possible
- Add progress indicators for long-running pagination
- Consider implementing async requests for better performance
- Monitor GitHub API changelog for future changes