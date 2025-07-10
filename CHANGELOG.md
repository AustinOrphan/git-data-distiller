# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Cursor-based pagination support for GitHub API to handle large datasets
- Comprehensive test suite with pytest fixtures
- Test coverage for pagination logic and error handling
- Security warnings in git-distiller.yaml.example
- run_tests.sh script for easy test execution
- Proper error handling for 422 pagination errors

### Changed
- Completely rewrote `get_paginated()` method to support both cursor and page-based pagination
- Updated all imports to use explicit imports instead of star imports
- Improved error handling with specific exception types
- Enhanced code quality to meet flake8 standards
- Updated README with current project status and limitations

### Fixed
- GitHub API 422 error: "Pagination with the page parameter is not supported for large datasets"
- Over 70 flake8 code quality violations
- Bare except clauses replaced with specific exception handling
- Line length issues in multiple files
- Import organization and unused imports
- Test failures in pagination handling for cursor-based pagination
- 422 error handling now properly continues to next response in pagination loop

### Security
- Removed exposed GitHub token from git-distiller.yaml
- Added git-distiller.yaml to .gitignore to prevent credential exposure
- Added security warnings to configuration example file

## [0.1.0] - Initial Release

### Added
- CLI tool for extracting GitHub data (repos, PRs, issues, discussions)
- Multiple output formatters (CodeReview, BugFix, Feature, MCP)
- Configuration via YAML files and environment variables
- GitHub API client with rate limiting and caching
- Pydantic models for data validation
- Jinja2 template-based prompt generation
- Rich console output with progress indicators
- Batch processing for multiple URLs