# Git Data Distiller - Fix TODO List

## 🚨 Critical - Security & Functionality

### 1. **URGENT: Rotate Exposed GitHub Token**
- [ ] Immediately revoke the exposed token via GitHub settings
- [ ] Generate a new token with appropriate permissions
- [ ] Update local environment variables

### 2. **Fix GitHub API Pagination** 
- [ ] Update `github_client.py` to use cursor-based pagination
  - [ ] Replace `page` parameter with `after`/`before` cursors
  - [ ] Implement pagination loop with cursor tracking
  - [ ] Update all methods: `get_issues()`, `get_pull_requests()`, `get_commits()`
- [ ] Test with large repositories (1000+ issues/PRs)
- [ ] Update error handling for new pagination format

### 3. **Secure Configuration Files**
- [ ] Add `git-distiller.yaml` to `.gitignore`
- [ ] Remove tracked `git-distiller.yaml` from git history
- [ ] Update `git-distiller.yaml.example` with placeholder values
- [ ] Add documentation about secure token storage

## 🔧 Code Quality Fixes

### 4. **Fix Flake8 Violations**
- [ ] Run `black src/ --line-length 88` to fix formatting
- [ ] Fix star imports in `github_client.py`:
  ```python
  # Replace: from .models import *
  # With explicit imports:
  from .models import (
      GitHubRepository, GitHubIssue, GitHubPullRequest,
      GitHubUser, GitHubLabel, GitHubMilestone,
      GitHubComment, GitHubCommit, GitHubFile
  )
  ```
- [ ] Remove unused imports from:
  - [ ] `cli.py` - Remove `json`, `Optional`
  - [ ] `config.py` - Remove `List`
  - [ ] `extractors.py` - Remove unused model imports
  - [ ] `formatters.py` - Remove `json`, `List`, `Template`
- [ ] Fix bare except in `cache.py:202`
- [ ] Add missing import for `List` in `cache.py:250`
- [ ] Fix f-string without placeholders in `cli.py:321`

### 5. **Fix Line Length Issues**
- [ ] Configure flake8 with 88 character limit to match black
- [ ] Or refactor long lines in:
  - [ ] `cache.py` - 4 instances
  - [ ] `cli.py` - 13 instances
  - [ ] `config.py` - 5 instances
  - [ ] `extractors.py` - 8 instances
  - [ ] `formatters.py` - Multiple instances

## 🧪 Testing Infrastructure

### 6. **Create Test Suite Structure**
- [ ] Create `tests/` directory
- [ ] Add `tests/__init__.py`
- [ ] Create test files:
  - [ ] `test_cli.py` - CLI command tests
  - [ ] `test_github_client.py` - API client tests
  - [ ] `test_extractors.py` - Data extraction tests
  - [ ] `test_formatters.py` - Output formatting tests
  - [ ] `test_config.py` - Configuration tests
  - [ ] `test_cache.py` - Caching logic tests

### 7. **Implement Core Tests**
- [ ] Authentication tests
  - [ ] Valid token
  - [ ] Invalid token
  - [ ] No token
- [ ] CLI command tests
  - [ ] Extract command with various formats
  - [ ] Review command
  - [ ] Bugfix command
  - [ ] Recent command
  - [ ] Batch command
- [ ] Error handling tests
  - [ ] Invalid URLs
  - [ ] Non-existent repositories
  - [ ] Rate limiting
  - [ ] Network errors
- [ ] Pagination tests
  - [ ] Small datasets
  - [ ] Large datasets requiring cursor pagination

## 📚 Documentation Updates

### 8. **Update Documentation**
- [ ] Add "Known Issues" section to README
- [ ] Document cursor-based pagination requirements
- [ ] Add troubleshooting guide for common errors
- [ ] Update installation instructions with token setup
- [ ] Add examples of working with large repositories

### 9. **API Documentation**
- [ ] Document the pagination changes
- [ ] Add code examples for cursor-based pagination
- [ ] Update docstrings in affected methods

## 🔄 Refactoring Suggestions

### 10. **Improve Error Handling**
- [ ] Create custom exception for pagination errors
- [ ] Add retry logic with exponential backoff
- [ ] Improve error messages with actionable suggestions

### 11. **Optimize Performance**
- [ ] Implement concurrent API requests where possible
- [ ] Add progress bars for long operations
- [ ] Optimize cache key generation
- [ ] Consider implementing request pooling

## 📋 Implementation Order

1. **Day 1**: Critical Security & API Fixes
   - Rotate token (30 min)
   - Fix `.gitignore` (15 min)
   - Start pagination implementation (4 hours)

2. **Day 2**: Complete Pagination & Code Quality
   - Finish pagination implementation (4 hours)
   - Fix all flake8 violations (2 hours)
   - Test with large repositories (2 hours)

3. **Day 3**: Testing Infrastructure
   - Set up test structure (1 hour)
   - Write authentication tests (2 hours)
   - Write CLI command tests (3 hours)
   - Write error handling tests (2 hours)

4. **Day 4**: Documentation & Cleanup
   - Update all documentation (3 hours)
   - Add code examples (2 hours)
   - Final testing and validation (3 hours)

## 🎯 Success Criteria

- [ ] All commands work with repositories containing 1000+ issues/PRs
- [ ] No flake8 violations
- [ ] Test coverage > 80%
- [ ] No exposed credentials in repository
- [ ] Clear documentation of limitations and workarounds
- [ ] All error messages are helpful and actionable

## 📝 Notes

- Consider using GitHub's GraphQL API for more efficient data fetching
- May need to implement rate limit handling more robustly
- Consider adding a `--no-cache` option for debugging
- Future: Add support for GitHub Enterprise installations