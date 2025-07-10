"""Prompt formatters for different AI coding tasks."""

from datetime import datetime
from typing import Dict, Optional, Union

from jinja2 import BaseLoader, Environment

from .exceptions import FormattingError
from .models import DistilledData


class PromptFormatter:
    """Base class for formatting GitHub data into AI prompts."""

    def __init__(self):
        self.env = Environment(loader=BaseLoader())
        self.env.filters["truncate_text"] = self._truncate_text
        self.env.filters["format_datetime"] = self._format_datetime
        self.env.filters["extract_language"] = self._extract_language
        self.env.filters["count_lines"] = self._count_lines

    def _truncate_text(self, text: Optional[str], max_length: int = 500) -> str:
        """Truncate text to specified length."""
        if not text:
            return ""
        if len(text) <= max_length:
            return text
        return text[: max_length - 3] + "..."

    def _format_datetime(self, dt: Union[str, datetime]) -> str:
        """Format datetime for display."""
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M UTC")

    def _extract_language(self, languages: Dict[str, int]) -> str:
        """Extract primary language from languages dict."""
        if not languages:
            return "Unknown"
        return max(languages.keys(), key=lambda k: languages[k])

    def _count_lines(self, text: Optional[str]) -> int:
        """Count lines in text."""
        if not text:
            return 0
        return len(text.split("\n"))

    def format(self, data: DistilledData, **kwargs) -> str:
        """Format data into prompt. Override in subclasses."""
        raise NotImplementedError


class CodeReviewFormatter(PromptFormatter):
    """Format data for code review tasks."""

    TEMPLATE = """# Code Review Request

## Repository Context
**Repository:** {{ data.repository.full_name }}
**Description:** {{ data.repository.description or "No description" }}
**Primary Language:** {{ data.repository.languages | extract_language }}
**Last Updated:** {{ data.repository.updated_at | format_datetime }}

## Pull Request Details
**PR #{{ pr.number }}:** {{ pr.title }}
**Author:** {{ pr.user.login }}
**Status:** {{ pr.state }}{% if pr.draft %} (Draft){% endif %}
**Created:** {{ pr.created_at | format_datetime }}
**Updated:** {{ pr.updated_at | format_datetime }}
**Branch:** {{ pr.head_branch }} → {{ pr.base_branch }}

### Description
{{ pr.body | truncate_text(1000) if pr.body else "No description provided" }}

### Changes Summary
- **Files Changed:** {{ pr.changed_files }}
- **Additions:** +{{ pr.additions }}
- **Deletions:** -{{ pr.deletions }}

### Modified Files
{% for file in pr.files[:10] %}
- `{{ file.filename }}` ({{ file.status }}) +{{ file.additions }}/-{{ file.deletions }}
{% endfor %}
{% if pr.files|length > 10 %}
... and {{ pr.files|length - 10 }} more files
{% endif %}

### Recent Commits
{% for commit in pr.commits[:5] %}
- `{{ commit.sha[:8] }}` {{ commit.message.split('\n')[0] | truncate_text(80) }}
{% endfor %}
{% if pr.commits|length > 5 %}
... and {{ pr.commits|length - 5 }} more commits
{% endif %}

{% if pr.comments %}
### Discussion
{% for comment in pr.comments[:5] %}
**{{ comment.user.login }}** ({{ comment.created_at | format_datetime }}):
{{ comment.body | truncate_text(300) }}

{% endfor %}
{% if pr.comments|length > 5 %}
... and {{ pr.comments|length - 5 }} more comments
{% endif %}
{% endif %}

{% if pr.review_comments %}
### Code Review Comments
{% for comment in pr.review_comments[:5] %}
**{{ comment.user.login }}** ({{ comment.created_at | format_datetime }}):
{{ comment.body | truncate_text(300) }}

{% endfor %}
{% if pr.review_comments|length > 5 %}
... and {{ pr.review_comments|length - 5 }} more review comments
{% endif %}
{% endif %}

## Instructions for AI
Please provide a thorough code review focusing on:
1. **Code Quality:** Check for best practices, readability, and maintainability
2. **Security:** Identify potential security vulnerabilities
3. **Performance:** Highlight performance concerns or optimizations
4. **Testing:** Assess test coverage and quality
5. **Documentation:** Check if changes are properly documented
6. **Architecture:** Evaluate architectural decisions and patterns

For each file with significant changes, provide specific feedback with line references where possible.

{% if include_file_contents %}
## File Contents
{% for file in pr.files[:5] %}
{% if file.patch %}
### {{ file.filename }}
```diff
{{ file.patch }}
```

{% endif %}
{% endfor %}
{% endif %}

{% if data.issues %}
## Related Issues
{% for issue in data.issues %}
- **Issue #{{ issue.number }}:** {{ issue.title }} ({{ issue.state }})
{% endfor %}
{% endif %}
"""

    def format(
        self, data: DistilledData, include_file_contents: bool = False, **kwargs
    ) -> str:
        """Format data for code review."""
        if not data.pull_requests:
            raise FormattingError("No pull request data found for code review")

        pr = data.pull_requests[0]  # Use first PR
        template = self.env.from_string(self.TEMPLATE)

        return template.render(
            data=data, pr=pr, include_file_contents=include_file_contents, **kwargs
        )


class BugFixFormatter(PromptFormatter):
    """Format data for bug fixing tasks."""

    TEMPLATE = """# Bug Fix Request

## Repository Context
**Repository:** {{ data.repository.full_name }}
**Description:** {{ data.repository.description or "No description" }}
**Primary Language:** {{ data.repository.languages | extract_language }}
**Stars:** {{ data.repository.stargazers_count }}
**Open Issues:** {{ data.repository.open_issues_count }}

## Issue Details
**Issue #{{ issue.number }}:** {{ issue.title }}
**Reporter:** {{ issue.user.login }}
**Status:** {{ issue.state }}
**Created:** {{ issue.created_at | format_datetime }}
**Updated:** {{ issue.updated_at | format_datetime }}

### Labels
{% for label in issue.labels %}
- `{{ label.name }}` ({{ label.description or "No description" }})
{% endfor %}

### Description
{{ issue.body | truncate_text(1500) if issue.body else "No description provided" }}

{% if issue.comments %}
### Discussion Thread
{% for comment in issue.comments %}
**{{ comment.user.login }}** ({{ comment.created_at | format_datetime }}):
{{ comment.body | truncate_text(500) }}

{% endfor %}
{% endif %}

{% if data.pull_requests %}
## Related Pull Requests
{% for pr in data.pull_requests %}
- **PR #{{ pr.number }}:** {{ pr.title }} ({{ pr.state }})
  - Branch: {{ pr.head_branch }} → {{ pr.base_branch }}
  - Changes: +{{ pr.additions }}/-{{ pr.deletions }} in {{ pr.changed_files }} files
{% endfor %}
{% endif %}

## Instructions for AI
Please help fix this bug by:

1. **Analysis:** Carefully analyze the issue description and comments to understand the problem
2. **Root Cause:** Identify the likely root cause based on the information provided
3. **Solution:** Propose a concrete solution with code changes if applicable
4. **Testing:** Suggest how to test the fix
5. **Prevention:** Recommend how to prevent similar issues in the future

If you need to see specific files or code sections, please ask for them using the repository context provided above.

## Repository Structure Context
**Default Branch:** {{ data.repository.default_branch }}
**Main Language:** {{ data.repository.language or "Not specified" }}
**Size:** {{ data.repository.size }} KB
**Last Push:** {{ data.repository.pushed_at | format_datetime }}

{% if data.repository.readme %}
### README Summary
{{ data.repository.readme[:800] | truncate_text(800) }}
{% endif %}
"""

    def format(self, data: DistilledData, **kwargs) -> str:
        """Format data for bug fixing."""
        if not data.issues:
            raise FormattingError("No issue data found for bug fix")

        issue = data.issues[0]  # Use first issue
        template = self.env.from_string(self.TEMPLATE)

        return template.render(data=data, issue=issue, **kwargs)


class FeatureRequestFormatter(PromptFormatter):
    """Format data for feature implementation tasks."""

    TEMPLATE = """# Feature Implementation Request

## Repository Context
**Repository:** {{ data.repository.full_name }}
**Description:** {{ data.repository.description or "No description" }}
**Primary Language:** {{ data.repository.languages | extract_language }}
**Framework/Stack:** {{ data.repository.topics | join(", ") if data.repository.topics else "Not specified" }}

## Feature Request
{% if data.issues %}
{% set issue = data.issues[0] %}
**Issue #{{ issue.number }}:** {{ issue.title }}
**Requester:** {{ issue.user.login }}
**Status:** {{ issue.state }}
**Created:** {{ issue.created_at | format_datetime }}

### Description
{{ issue.body if issue.body else "No description provided" }}

{% if issue.comments %}
### Discussion
{% for comment in issue.comments %}
**{{ comment.user.login }}** ({{ comment.created_at | format_datetime }}):
{{ comment.body | truncate_text(400) }}

{% endfor %}
{% endif %}
{% endif %}

## Repository Architecture
**Languages:**
{% for lang, bytes in data.repository.languages.items() %}
- {{ lang }}: {{ "%.1f"|format(bytes / data.repository.languages.values()|sum * 100) }}%
{% endfor %}

**Key Topics:** {{ data.repository.topics | join(", ") if data.repository.topics else "None specified" }}

{% if data.repository.readme %}
### README Overview
{{ data.repository.readme[:1000] | truncate_text(1000) }}
{% endif %}

## Instructions for AI
Please implement this feature by:

1. **Requirements Analysis:** Break down the feature request into specific requirements
2. **Design:** Propose an architectural approach that fits the existing codebase
3. **Implementation Plan:** Outline the files that need to be created or modified
4. **Code Generation:** Provide the actual code implementation
5. **Testing Strategy:** Suggest how to test the new feature
6. **Documentation:** Update relevant documentation

Consider the existing codebase structure, coding patterns, and technologies used in the repository.

{% if data.pull_requests %}
## Recent Pull Requests (for context)
{% for pr in data.pull_requests[:3] %}
- **PR #{{ pr.number }}:** {{ pr.title }} ({{ pr.state }})
  - {{ pr.changed_files }} files, +{{ pr.additions }}/-{{ pr.deletions }}
{% endfor %}
{% endif %}
"""

    def format(self, data: DistilledData, **kwargs) -> str:
        """Format data for feature implementation."""
        template = self.env.from_string(self.TEMPLATE)

        return template.render(data=data, **kwargs)


class GeneralAnalysisFormatter(PromptFormatter):
    """Format data for general repository analysis."""

    TEMPLATE = """# Repository Analysis

## Repository Overview
**Name:** {{ data.repository.full_name }}
**Description:** {{ data.repository.description or "No description provided" }}
**Created:** {{ data.repository.created_at | format_datetime }}
**Last Updated:** {{ data.repository.updated_at | format_datetime }}
**Last Push:** {{ data.repository.pushed_at | format_datetime }}

## Statistics
- **Stars:** {{ data.repository.stargazers_count }}
- **Forks:** {{ data.repository.forks_count }}
- **Watchers:** {{ data.repository.watchers_count }}
- **Open Issues:** {{ data.repository.open_issues_count }}
- **Size:** {{ data.repository.size }} KB

## Technology Stack
{% if data.repository.languages %}
**Languages:**
{% for lang, bytes in data.repository.languages.items() %}
- {{ lang }}: {{ "%.1f"|format(bytes / data.repository.languages.values()|sum * 100) }}%
{% endfor %}
{% endif %}

{% if data.repository.topics %}
**Topics/Tags:** {{ data.repository.topics | join(", ") }}
{% endif %}

## Recent Activity

{% if data.issues %}
### Issues ({{ data.issues | length }})
{% for issue in data.issues[:5] %}
- **#{{ issue.number }}** {{ issue.title }} ({{ issue.state }}) - {{ issue.user.login }}
  Last updated: {{ issue.updated_at | format_datetime }}
{% endfor %}
{% if data.issues | length > 5 %}
... and {{ data.issues | length - 5 }} more issues
{% endif %}
{% endif %}

{% if data.pull_requests %}
### Pull Requests ({{ data.pull_requests | length }})
{% for pr in data.pull_requests[:5] %}
- **#{{ pr.number }}** {{ pr.title }} ({{ pr.state }}) - {{ pr.user.login }}
  {{ pr.head_branch }} → {{ pr.base_branch }}
  Changes: +{{ pr.additions }}/-{{ pr.deletions }} in {{ pr.changed_files }} files
{% endfor %}
{% if data.pull_requests | length > 5 %}
... and {{ data.pull_requests | length - 5 }} more PRs
{% endif %}
{% endif %}

{% if data.repository.readme %}
## README
{{ data.repository.readme | truncate_text(2000) }}
{% endif %}

## Instructions for AI
This is a comprehensive overview of the repository. Please analyze the data and provide insights on:

1. **Code Quality:** Overall assessment based on activity patterns
2. **Maintenance:** How well-maintained the project appears to be
3. **Community:** Level of community engagement and contribution
4. **Architecture:** Inferences about the technical architecture
5. **Opportunities:** Potential areas for improvement or contribution

Use this information to provide helpful analysis or answer specific questions about the repository.
"""

    def format(self, data: DistilledData, **kwargs) -> str:
        """Format data for general analysis."""
        template = self.env.from_string(self.TEMPLATE)

        return template.render(data=data, **kwargs)


class MCPSourcesFormatter(PromptFormatter):
    """Format data with MCP tool integration for source access."""

    def format(
        self, data: DistilledData, format_type: str = "general", **kwargs
    ) -> str:
        """Format data with MCP tool integration."""

        # Generate the main prompt based on type
        if format_type == "code_review":
            main_prompt = CodeReviewFormatter().format(data, **kwargs)
        elif format_type == "bug_fix":
            main_prompt = BugFixFormatter().format(data, **kwargs)
        elif format_type == "feature":
            main_prompt = FeatureRequestFormatter().format(data, **kwargs)
        else:
            main_prompt = GeneralAnalysisFormatter().format(data, **kwargs)

        # Add MCP tool integration section
        mcp_section = self._generate_mcp_section(data)

        return f"{main_prompt}\n\n{mcp_section}"

    def _generate_mcp_section(self, data: DistilledData) -> str:
        """Generate MCP tools integration section."""

        mcp_tools = []

        if data.repository:
            repo_info = data.repository

            # GitHub API endpoints for MCP tools
            mcp_tools.extend(
                [
                    f"GET /repos/{repo_info.full_name}",
                    f"GET /repos/{repo_info.full_name}/contents/",
                    f"GET /repos/{repo_info.full_name}/languages",
                    f"GET /repos/{repo_info.full_name}/topics",
                ]
            )

            if data.issues:
                for issue in data.issues[:3]:  # Limit to first 3
                    mcp_tools.append(
                        f"GET /repos/{repo_info.full_name}/issues/{issue.number}"
                    )
                    mcp_tools.append(
                        f"GET /repos/{repo_info.full_name}/issues/{issue.number}/comments"
                    )

            if data.pull_requests:
                for pr in data.pull_requests[:3]:  # Limit to first 3
                    mcp_tools.extend(
                        [
                            f"GET /repos/{repo_info.full_name}/pulls/{pr.number}",
                            f"GET /repos/{repo_info.full_name}/pulls/{pr.number}/files",
                            f"GET /repos/{repo_info.full_name}/pulls/{pr.number}/commits",
                            f"GET /repos/{repo_info.full_name}/pulls/{pr.number}/comments",
                        ]
                    )

        mcp_section = """
## MCP Tool Integration

If you have access to MCP (Model Context Protocol) tools, you can use the following endpoints to get additional real-time information:

### Available API Endpoints:
"""

        for tool in mcp_tools:
            mcp_section += f"- `{tool}`\n"

        mcp_section += """
### Usage Instructions:
1. Use the GitHub MCP tool to fetch real-time data from these endpoints
2. The data above provides context, but live data may be more current
3. For file contents, use the repository contents endpoints
4. For detailed diff information, use the pull request files endpoints

### Authentication:
- These endpoints require GitHub API authentication
- Use your configured GitHub token with appropriate repository permissions
"""

        return mcp_section


def get_formatter(format_type: str) -> PromptFormatter:
    """Factory function to get appropriate formatter."""
    formatters = {
        "code_review": CodeReviewFormatter,
        "bug_fix": BugFixFormatter,
        "feature": FeatureRequestFormatter,
        "analysis": GeneralAnalysisFormatter,
        "mcp": MCPSourcesFormatter,
    }

    formatter_class = formatters.get(format_type)
    if not formatter_class:
        raise FormattingError(f"Unknown format type: {format_type}")

    return formatter_class()
