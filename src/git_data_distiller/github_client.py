"""GitHub API client with authentication and rate limiting."""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .exceptions import (
    AuthenticationError,
    GitHubAPIError,
    PermissionError,
    RateLimitError,
    ResourceNotFoundError,
)
from .models import (
    GitHubComment,
    GitHubCommit,
    GitHubFile,
    GitHubIssue,
    GitHubLabel,
    GitHubMilestone,
    GitHubPullRequest,
    GitHubRepository,
    GitHubUser,
)

logger = logging.getLogger(__name__)


class GitHubRateLimiter:
    """Handle GitHub API rate limiting."""

    def __init__(self):
        self.reset_time = 0
        self.remaining = 5000
        self.limit = 5000

    def update_from_headers(self, headers: Dict[str, str]) -> None:
        """Update rate limit info from response headers."""
        self.remaining = int(headers.get("x-ratelimit-remaining", self.remaining))
        self.limit = int(headers.get("x-ratelimit-limit", self.limit))
        self.reset_time = int(headers.get("x-ratelimit-reset", self.reset_time))

    def should_wait(self) -> bool:
        """Check if we should wait due to rate limiting."""
        return self.remaining < 10

    def wait_time(self) -> float:
        """Calculate how long to wait."""
        if self.remaining <= 0:
            return max(0, self.reset_time - time.time())
        return 0


class GitHubClient:
    """GitHub API client with authentication and error handling."""

    def __init__(
        self, token: Optional[str] = None, base_url: str = "https://api.github.com"
    ):
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.session = self._create_session()
        self.rate_limiter = GitHubRateLimiter()

    def _create_session(self) -> requests.Session:
        """Create configured requests session with optimized connection pooling."""
        session = requests.Session()

        # Configure retries with improved strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],  # More specific than default
        )

        # Configure HTTPAdapter with connection pooling
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=20,  # Number of connection pools to cache
            pool_maxsize=20,  # Maximum number of connections in each pool
            pool_block=False,  # Don't block when pool is full
        )
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Set headers with keep-alive
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "git-data-distiller/0.1.0",
            "Connection": "keep-alive",  # Enable keep-alive
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"

        session.headers.update(headers)
        return session

    def _handle_rate_limit(self, response: requests.Response) -> None:
        """Handle rate limiting."""
        self.rate_limiter.update_from_headers(response.headers)

        if response.status_code == 429 or self.rate_limiter.should_wait():
            wait_time = self.rate_limiter.wait_time()
            if wait_time > 0:
                logger.warning(f"Rate limited. Waiting {wait_time:.2f} seconds...")
                time.sleep(wait_time)

    def get(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make GET request to GitHub API."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        response = self.session.get(url, params=params)
        self._handle_rate_limit(response)

        if response.status_code == 404:
            raise ResourceNotFoundError(
                f"Resource not found: {url}", response.status_code, response.text
            )
        elif response.status_code == 401:
            raise AuthenticationError(
                f"Authentication failed: {url}", response.status_code, response.text
            )
        elif response.status_code == 403:
            raise PermissionError(
                f"Access forbidden: {url}", response.status_code, response.text
            )
        elif response.status_code == 429:
            reset_time = int(response.headers.get("x-ratelimit-reset", 0))
            raise RateLimitError(f"Rate limit exceeded: {url}", reset_time)
        elif not response.ok:
            raise GitHubAPIError(
                f"API request failed: {response.status_code} - {response.text}",
                response.status_code,
                response.text,
            )

        return response.json()

    def get_paginated(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        per_page: int = 100,
        max_pages: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get all pages of a paginated endpoint using cursor or page-based pagination."""
        all_items = []
        page_count = 0

        if params is None:
            params = {}
        params["per_page"] = per_page

        # Start with the initial URL
        next_url = f"{self.base_url}/{endpoint.lstrip('/')}"

        while next_url:
            if max_pages and page_count >= max_pages:
                break

            # Make request
            if page_count == 0:
                # First request uses params
                response = self.session.get(next_url, params=params)
            else:
                # Subsequent requests use the full URL from Link header
                response = self.session.get(next_url)

            self._handle_rate_limit(response)

            # Handle errors
            if (
                response.status_code == 422
                and "cursor based pagination" in response.text
            ):
                # If cursor pagination is required but we're using page-based,
                # skip this response and continue (API will handle via Link headers)
                page_count += 1
                continue
            elif response.status_code == 404:
                raise ResourceNotFoundError(
                    f"Resource not found: {next_url}",
                    response.status_code,
                    response.text,
                )
            elif response.status_code == 401:
                raise AuthenticationError(
                    f"Authentication failed: {next_url}",
                    response.status_code,
                    response.text,
                )
            elif response.status_code == 403:
                raise PermissionError(
                    f"Access forbidden: {next_url}", response.status_code, response.text
                )
            elif response.status_code == 429:
                reset_time = int(response.headers.get("x-ratelimit-reset", 0))
                raise RateLimitError(f"Rate limit exceeded: {next_url}", reset_time)
            elif not response.ok and response.status_code != 422:
                raise GitHubAPIError(
                    f"API request failed: {response.status_code} - {response.text}",
                    response.status_code,
                    response.text,
                )

            data = response.json()

            # Extract items from response
            if isinstance(data, list):
                all_items.extend(data)
                if len(data) < per_page:
                    break
            else:
                # Handle search results format
                if "items" in data:
                    all_items.extend(data["items"])
                    if len(data["items"]) < per_page:
                        break
                else:
                    all_items.append(data)
                    break

            # Get next URL from Link header (for cursor-based pagination)
            next_url = self._get_next_url_from_link_header(
                response.headers.get("Link", "")
            )

            # If no Link header, try page-based pagination as fallback
            if (
                not next_url
                and page_count == 0
                and isinstance(data, list)
                and len(data) == per_page
            ):
                # Only try page-based if we haven't seen a Link header yet
                params["page"] = 2
                next_url = f"{self.base_url}/{endpoint.lstrip('/')}"

            page_count += 1

        return all_items

    def _get_next_url_from_link_header(self, link_header: str) -> Optional[str]:
        """Parse Link header to get next page URL."""
        if not link_header:
            return None

        # Parse Link header format: <url>; rel="next", <url>; rel="last"

        for link in link_header.split(","):
            link = link.strip()
            if ";" in link:
                url_part, rel_part = link.split(";", 1)
                url = url_part.strip()[1:-1]  # Remove < and >
                rel_match = rel_part.strip()
                if 'rel="next"' in rel_match:
                    return url

        return None

    def parse_github_url(self, url: str) -> Dict[str, str]:
        """Parse GitHub URL to extract owner, repo, and resource info."""
        parsed = urlparse(url)

        if "github.com" not in parsed.netloc:
            raise ValueError(f"Not a GitHub URL: {url}")

        path_parts = [p for p in parsed.path.split("/") if p]

        if len(path_parts) < 2:
            raise ValueError(f"Invalid GitHub URL format: {url}")

        result = {"owner": path_parts[0], "repo": path_parts[1], "type": "repository"}

        if len(path_parts) > 2:
            resource_type = path_parts[2]

            if resource_type == "issues" and len(path_parts) > 3:
                result["type"] = "issue"
                result["number"] = int(path_parts[3])
            elif resource_type == "pull" and len(path_parts) > 3:
                result["type"] = "pull_request"
                result["number"] = int(path_parts[3])
            elif resource_type == "discussions" and len(path_parts) > 3:
                result["type"] = "discussion"
                result["number"] = int(path_parts[3])
            elif resource_type == "tree" and len(path_parts) > 3:
                result["type"] = "branch"
                result["branch"] = path_parts[3]
            elif resource_type == "commit" and len(path_parts) > 3:
                result["type"] = "commit"
                result["sha"] = path_parts[3]
            elif resource_type == "milestone" and len(path_parts) > 3:
                result["type"] = "milestone"
                result["number"] = int(path_parts[3])

        return result

    def get_repository(self, owner: str, repo: str) -> GitHubRepository:
        """Get repository information."""
        repo_data = self.get(f"repos/{owner}/{repo}")

        # Get languages
        languages = self.get(f"repos/{owner}/{repo}/languages")

        # Get topics
        topics_data = self.get(f"repos/{owner}/{repo}/topics")
        topics = topics_data.get("names", [])

        # Get README
        readme = None
        try:
            readme_data = self.get(f"repos/{owner}/{repo}/readme")
            if readme_data.get("content"):
                import base64

                readme = base64.b64decode(readme_data["content"]).decode("utf-8")
        except Exception:
            pass

        return GitHubRepository(
            name=repo_data["name"],
            full_name=repo_data["full_name"],
            description=repo_data.get("description"),
            html_url=repo_data["html_url"],
            clone_url=repo_data["clone_url"],
            language=repo_data.get("language"),
            languages=languages,
            topics=topics,
            readme=readme,
            created_at=repo_data["created_at"],
            updated_at=repo_data["updated_at"],
            pushed_at=repo_data["pushed_at"],
            size=repo_data["size"],
            stargazers_count=repo_data["stargazers_count"],
            watchers_count=repo_data["watchers_count"],
            forks_count=repo_data["forks_count"],
            open_issues_count=repo_data["open_issues_count"],
            default_branch=repo_data["default_branch"],
        )

    def get_repository_parallel(self, owner: str, repo: str) -> GitHubRepository:
        """Get repository information with parallel API calls."""
        import base64

        # Define the API endpoints to fetch
        endpoints = {
            "repo": f"repos/{owner}/{repo}",
            "languages": f"repos/{owner}/{repo}/languages",
            "topics": f"repos/{owner}/{repo}/topics",
            "readme": f"repos/{owner}/{repo}/readme",
        }

        results = {}
        errors = {}

        # Use ThreadPoolExecutor for parallel API calls
        with ThreadPoolExecutor(max_workers=4) as executor:
            # Submit all API calls
            future_to_key = {
                executor.submit(self.get, endpoint): key
                for key, endpoint in endpoints.items()
            }

            # Collect results as they complete
            for future in as_completed(future_to_key):
                key = future_to_key[future]
                try:
                    results[key] = future.result()
                except Exception as e:
                    errors[key] = e
                    logger.debug(f"Error fetching {key}: {e}")

        # Handle required data (repo info)
        if "repo" not in results:
            if "repo" in errors:
                raise errors["repo"]
            raise GitHubAPIError("Failed to fetch repository information")

        repo_data = results["repo"]

        # Extract optional data with defaults
        languages = results.get("languages", {})
        topics = results.get("topics", {}).get("names", [])

        # Process README if available
        readme = None
        if "readme" in results and results["readme"].get("content"):
            try:
                readme = base64.b64decode(results["readme"]["content"]).decode("utf-8")
            except Exception:
                pass

        return GitHubRepository(
            name=repo_data["name"],
            full_name=repo_data["full_name"],
            description=repo_data.get("description"),
            html_url=repo_data["html_url"],
            clone_url=repo_data["clone_url"],
            language=repo_data.get("language"),
            languages=languages,
            topics=topics,
            readme=readme,
            created_at=repo_data["created_at"],
            updated_at=repo_data["updated_at"],
            pushed_at=repo_data["pushed_at"],
            size=repo_data["size"],
            stargazers_count=repo_data["stargazers_count"],
            watchers_count=repo_data["watchers_count"],
            forks_count=repo_data["forks_count"],
            open_issues_count=repo_data["open_issues_count"],
            default_branch=repo_data["default_branch"],
        )

    def get_issues(
        self,
        owner: str,
        repo: str,
        state: str = "all",
        labels: Optional[str] = None,
        milestone: Optional[str] = None,
        assignee: Optional[str] = None,
        include_comments: bool = True,
    ) -> List[GitHubIssue]:
        """Get repository issues."""
        params = {"state": state}
        if labels:
            params["labels"] = labels
        if milestone:
            params["milestone"] = milestone
        if assignee:
            params["assignee"] = assignee

        issues_data = self.get_paginated(f"repos/{owner}/{repo}/issues", params)

        issues = []
        for issue_data in issues_data:
            # Skip pull requests (they appear in issues endpoint)
            if "pull_request" in issue_data:
                continue

            comments = []
            if include_comments and issue_data.get("comments", 0) > 0:
                comments_data = self.get_paginated(
                    f"repos/{owner}/{repo}/issues/{issue_data['number']}/comments"
                )
                comments = [self._parse_comment(c) for c in comments_data]

            issues.append(
                GitHubIssue(
                    number=issue_data["number"],
                    title=issue_data["title"],
                    body=issue_data.get("body"),
                    state=issue_data["state"],
                    labels=[
                        GitHubLabel(**label) for label in issue_data.get("labels", [])
                    ],
                    milestone=(
                        GitHubMilestone(**issue_data["milestone"])
                        if issue_data.get("milestone")
                        else None
                    ),
                    assignees=[
                        GitHubUser(**assignee)
                        for assignee in issue_data.get("assignees", [])
                    ],
                    user=GitHubUser(**issue_data["user"]),
                    created_at=issue_data["created_at"],
                    updated_at=issue_data["updated_at"],
                    closed_at=issue_data.get("closed_at"),
                    html_url=issue_data["html_url"],
                    comments=comments,
                    comments_count=issue_data.get("comments", 0),
                )
            )

        return issues

    def get_issues_parallel(
        self,
        owner: str,
        repo: str,
        state: str = "all",
        labels: Optional[str] = None,
        milestone: Optional[str] = None,
        assignee: Optional[str] = None,
        include_comments: bool = True,
    ) -> List[GitHubIssue]:
        """Get repository issues with parallel comment fetching."""
        params = {"state": state}
        if labels:
            params["labels"] = labels
        if milestone:
            params["milestone"] = milestone
        if assignee:
            params["assignee"] = assignee

        issues_data = self.get_paginated(f"repos/{owner}/{repo}/issues", params)

        # Filter out pull requests (they appear in issues endpoint)
        issues_data = [issue for issue in issues_data if "pull_request" not in issue]

        if not include_comments:
            # Simple case - no comments to fetch
            return [
                GitHubIssue(
                    number=issue_data["number"],
                    title=issue_data["title"],
                    body=issue_data.get("body"),
                    state=issue_data["state"],
                    labels=[
                        GitHubLabel(**label) for label in issue_data.get("labels", [])
                    ],
                    milestone=(
                        GitHubMilestone(**issue_data["milestone"])
                        if issue_data.get("milestone")
                        else None
                    ),
                    assignees=[
                        GitHubUser(**assignee)
                        for assignee in issue_data.get("assignees", [])
                    ],
                    user=GitHubUser(**issue_data["user"]),
                    created_at=issue_data["created_at"],
                    updated_at=issue_data["updated_at"],
                    closed_at=issue_data.get("closed_at"),
                    html_url=issue_data["html_url"],
                    comments=[],
                    comments_count=issue_data.get("comments", 0),
                )
                for issue_data in issues_data
            ]

        # Parallel comment fetching
        issues_with_comments = [
            issue for issue in issues_data if issue.get("comments", 0) > 0
        ]

        comments_map = {}

        if issues_with_comments:
            with ThreadPoolExecutor(
                max_workers=min(10, len(issues_with_comments))
            ) as executor:
                future_to_issue = {
                    executor.submit(
                        self.get_paginated,
                        f"repos/{owner}/{repo}/issues/{issue['number']}/comments",
                    ): issue["number"]
                    for issue in issues_with_comments
                }

                for future in as_completed(future_to_issue):
                    issue_number = future_to_issue[future]
                    try:
                        comments_data = future.result()
                        comments_map[issue_number] = [
                            self._parse_comment(c) for c in comments_data
                        ]
                    except Exception as e:
                        logger.debug(
                            f"Error fetching comments for issue #{issue_number}: {e}"
                        )
                        comments_map[issue_number] = []

        # Build final issues list
        issues = []
        for issue_data in issues_data:
            comments = comments_map.get(issue_data["number"], [])

            issues.append(
                GitHubIssue(
                    number=issue_data["number"],
                    title=issue_data["title"],
                    body=issue_data.get("body"),
                    state=issue_data["state"],
                    labels=[
                        GitHubLabel(**label) for label in issue_data.get("labels", [])
                    ],
                    milestone=(
                        GitHubMilestone(**issue_data["milestone"])
                        if issue_data.get("milestone")
                        else None
                    ),
                    assignees=[
                        GitHubUser(**assignee)
                        for assignee in issue_data.get("assignees", [])
                    ],
                    user=GitHubUser(**issue_data["user"]),
                    created_at=issue_data["created_at"],
                    updated_at=issue_data["updated_at"],
                    closed_at=issue_data.get("closed_at"),
                    html_url=issue_data["html_url"],
                    comments=comments,
                    comments_count=issue_data.get("comments", 0),
                )
            )

        return issues

    def get_issues_by_numbers(
        self, owner: str, repo: str, issue_numbers: List[int]
    ) -> List[GitHubIssue]:
        """Get specific issues by their numbers using parallel API calls."""
        if not issue_numbers:
            return []

        results = {}
        errors = {}

        # Use ThreadPoolExecutor for parallel API calls
        with ThreadPoolExecutor(max_workers=min(10, len(issue_numbers))) as executor:
            # Submit all API calls
            future_to_number = {
                executor.submit(
                    self.get, f"repos/{owner}/{repo}/issues/{number}"
                ): number
                for number in issue_numbers
            }

            # Collect results as they complete
            for future in as_completed(future_to_number):
                issue_number = future_to_number[future]
                try:
                    issue_data = future.result()
                    # Skip if it's actually a pull request
                    if "pull_request" not in issue_data:
                        results[issue_number] = issue_data
                except Exception as e:
                    errors[issue_number] = e
                    logger.debug(f"Error fetching issue #{issue_number}: {e}")

        # Convert to GitHubIssue objects
        issues = []
        for issue_number in issue_numbers:
            if issue_number in results:
                issue_data = results[issue_number]
                issues.append(
                    GitHubIssue(
                        number=issue_data["number"],
                        title=issue_data["title"],
                        body=issue_data.get("body"),
                        state=issue_data["state"],
                        labels=[
                            GitHubLabel(**label)
                            for label in issue_data.get("labels", [])
                        ],
                        milestone=(
                            GitHubMilestone(**issue_data["milestone"])
                            if issue_data.get("milestone")
                            else None
                        ),
                        assignees=[
                            GitHubUser(**assignee)
                            for assignee in issue_data.get("assignees", [])
                        ],
                        user=GitHubUser(**issue_data["user"]),
                        created_at=issue_data["created_at"],
                        updated_at=issue_data["updated_at"],
                        closed_at=issue_data.get("closed_at"),
                        html_url=issue_data["html_url"],
                        comments=[],  # Comments not fetched in this method
                        comments_count=issue_data.get("comments", 0),
                    )
                )

        return issues

    def get_pull_requests(
        self,
        owner: str,
        repo: str,
        state: str = "all",
        include_comments: bool = True,
        include_commits: bool = True,
        include_files: bool = True,
    ) -> List[GitHubPullRequest]:
        """Get repository pull requests."""
        prs_data = self.get_paginated(f"repos/{owner}/{repo}/pulls", {"state": state})

        prs = []
        for pr_data in prs_data:
            comments = []
            review_comments = []
            commits = []
            files = []

            if include_comments:
                if pr_data.get("comments", 0) > 0:
                    comments_data = self.get_paginated(
                        f"repos/{owner}/{repo}/issues/{pr_data['number']}/comments"
                    )
                    comments = [self._parse_comment(c) for c in comments_data]

                if pr_data.get("review_comments", 0) > 0:
                    review_comments_data = self.get_paginated(
                        f"repos/{owner}/{repo}/pulls/{pr_data['number']}/comments"
                    )
                    review_comments = [
                        self._parse_comment(c) for c in review_comments_data
                    ]

            if include_commits and pr_data.get("commits", 0) > 0:
                commits_data = self.get_paginated(
                    f"repos/{owner}/{repo}/pulls/{pr_data['number']}/commits"
                )
                commits = [self._parse_commit(c) for c in commits_data]

            if include_files and pr_data.get("changed_files", 0) > 0:
                files_data = self.get_paginated(
                    f"repos/{owner}/{repo}/pulls/{pr_data['number']}/files"
                )
                files = [self._parse_file(f) for f in files_data]

            prs.append(
                GitHubPullRequest(
                    number=pr_data["number"],
                    title=pr_data["title"],
                    body=pr_data.get("body"),
                    state=pr_data["state"],
                    draft=pr_data.get("draft", False),
                    merged=pr_data.get("merged", False),
                    merged_at=pr_data.get("merged_at"),
                    merge_commit_sha=pr_data.get("merge_commit_sha"),
                    head_branch=pr_data["head"]["ref"],
                    base_branch=pr_data["base"]["ref"],
                    labels=[
                        GitHubLabel(**label) for label in pr_data.get("labels", [])
                    ],
                    milestone=(
                        GitHubMilestone(**pr_data["milestone"])
                        if pr_data.get("milestone")
                        else None
                    ),
                    assignees=[
                        GitHubUser(**assignee)
                        for assignee in pr_data.get("assignees", [])
                    ],
                    requested_reviewers=[
                        GitHubUser(**reviewer)
                        for reviewer in pr_data.get("requested_reviewers", [])
                    ],
                    user=GitHubUser(**pr_data["user"]),
                    created_at=pr_data["created_at"],
                    updated_at=pr_data["updated_at"],
                    closed_at=pr_data.get("closed_at"),
                    html_url=pr_data["html_url"],
                    diff_url=pr_data["diff_url"],
                    patch_url=pr_data["patch_url"],
                    comments=comments,
                    review_comments=review_comments,
                    commits=commits,
                    files=files,
                    additions=pr_data.get("additions", 0),
                    deletions=pr_data.get("deletions", 0),
                    changed_files=pr_data.get("changed_files", 0),
                )
            )

        return prs

    def _parse_comment(self, comment_data: Dict[str, Any]) -> GitHubComment:
        """Parse comment data."""
        return GitHubComment(
            id=comment_data["id"],
            user=GitHubUser(**comment_data["user"]),
            body=comment_data["body"],
            created_at=comment_data["created_at"],
            updated_at=comment_data["updated_at"],
            html_url=comment_data["html_url"],
        )

    def _parse_commit(self, commit_data: Dict[str, Any]) -> GitHubCommit:
        """Parse commit data."""
        return GitHubCommit(
            sha=commit_data["sha"],
            message=commit_data["commit"]["message"],
            author=(
                GitHubUser(**commit_data["author"])
                if commit_data.get("author")
                else GitHubUser(
                    login=commit_data["commit"]["author"]["name"],
                    id=0,
                    avatar_url="",
                    html_url="",
                    type="User",
                )
            ),
            committer=(
                GitHubUser(**commit_data["committer"])
                if commit_data.get("committer")
                else GitHubUser(
                    login=commit_data["commit"]["committer"]["name"],
                    id=0,
                    avatar_url="",
                    html_url="",
                    type="User",
                )
            ),
            date=commit_data["commit"]["author"]["date"],
            html_url=commit_data["html_url"],
            stats=commit_data.get("stats"),
        )

    def _parse_file(self, file_data: Dict[str, Any]) -> GitHubFile:
        """Parse file change data."""
        return GitHubFile(
            filename=file_data["filename"],
            status=file_data["status"],
            additions=file_data["additions"],
            deletions=file_data["deletions"],
            changes=file_data["changes"],
            patch=file_data.get("patch"),
        )
