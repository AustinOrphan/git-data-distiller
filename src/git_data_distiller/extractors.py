"""Data extraction orchestrator for different GitHub resources."""

import logging
from typing import Dict, Optional

from .exceptions import ResourceNotFoundError
from .github_client import GitHubClient
from .models import DistilledData

logger = logging.getLogger(__name__)


class GitHubExtractor:
    """Main extractor class that orchestrates data collection."""

    def __init__(self, client: GitHubClient):
        self.client = client

    def extract_from_url(self, url: str, **options) -> DistilledData:
        """Extract data from a GitHub URL."""
        url_info = self.client.parse_github_url(url)

        if url_info["type"] == "repository":
            return self.extract_repository(
                url_info["owner"], url_info["repo"], **options
            )
        elif url_info["type"] == "issue":
            return self.extract_issue(
                url_info["owner"], url_info["repo"], url_info["number"], **options
            )
        elif url_info["type"] == "pull_request":
            return self.extract_pull_request(
                url_info["owner"], url_info["repo"], url_info["number"], **options
            )
        else:
            raise ValueError(f"Unsupported URL type: {url_info['type']}")

    def extract_repository(
        self,
        owner: str,
        repo: str,
        include_issues: bool = True,
        include_prs: bool = True,
        include_discussions: bool = False,
        issue_filters: Optional[Dict] = None,
        pr_filters: Optional[Dict] = None,
        max_issues: Optional[int] = None,
        max_prs: Optional[int] = None,
    ) -> DistilledData:
        """Extract complete repository data."""
        logger.info(f"Extracting repository data for {owner}/{repo}")

        # Get basic repository info
        repository = self.client.get_repository_parallel(owner, repo)

        data = DistilledData(
            repository=repository,
            metadata={
                "extraction_type": "repository",
                "owner": owner,
                "repo": repo,
                "timestamp": repository.updated_at.isoformat(),
            },
        )

        # Extract issues if requested
        if include_issues:
            issue_filters = issue_filters or {}
            issues = self.client.get_issues_parallel(owner, repo, **issue_filters)
            if max_issues:
                issues = issues[:max_issues]
            data.issues = issues
            logger.info(f"Extracted {len(issues)} issues")

        # Extract pull requests if requested
        if include_prs:
            pr_filters = pr_filters or {}
            prs = self.client.get_pull_requests(owner, repo, **pr_filters)
            if max_prs:
                prs = prs[:max_prs]
            data.pull_requests = prs
            logger.info(f"Extracted {len(prs)} pull requests")

        return data

    def extract_issue(
        self,
        owner: str,
        repo: str,
        number: int,
        include_repository_context: bool = True,
    ) -> DistilledData:
        """Extract specific issue with context."""
        logger.info(f"Extracting issue #{number} from {owner}/{repo}")

        # Get the specific issue
        issues = self.client.get_issues_by_numbers(owner, repo, [number])
        issue = issues[0] if issues else None

        if not issue:
            raise ResourceNotFoundError(f"Issue #{number} not found in {owner}/{repo}")

        data = DistilledData(
            issues=[issue],
            metadata={
                "extraction_type": "issue",
                "owner": owner,
                "repo": repo,
                "issue_number": number,
                "timestamp": issue.updated_at.isoformat(),
            },
        )

        # Add repository context if requested
        if include_repository_context:
            data.repository = self.client.get_repository_parallel(owner, repo)

        return data

    def extract_pull_request(
        self,
        owner: str,
        repo: str,
        number: int,
        include_repository_context: bool = True,
    ) -> DistilledData:
        """Extract specific pull request with context."""
        logger.info(f"Extracting PR #{number} from {owner}/{repo}")

        # Get the specific PR
        prs = self.client.get_pull_requests(owner, repo, state="all")
        pr = next((p for p in prs if p.number == number), None)

        if not pr:
            raise ResourceNotFoundError(
                f"Pull request #{number} not found in {owner}/{repo}"
            )

        data = DistilledData(
            pull_requests=[pr],
            metadata={
                "extraction_type": "pull_request",
                "owner": owner,
                "repo": repo,
                "pr_number": number,
                "timestamp": pr.updated_at.isoformat(),
            },
        )

        # Add repository context if requested
        if include_repository_context:
            data.repository = self.client.get_repository_parallel(owner, repo)

        return data

    def extract_for_code_review(
        self, owner: str, repo: str, pr_number: int
    ) -> DistilledData:
        """Extract data optimized for code review tasks."""
        logger.info(
            f"Extracting code review data for PR #{pr_number} in {owner}/{repo}"
        )

        # Get PR with full details
        prs = self.client.get_pull_requests(
            owner,
            repo,
            state="all",
            include_comments=True,
            include_commits=True,
            include_files=True,
        )
        pr = next((p for p in prs if p.number == pr_number), None)

        if not pr:
            raise ResourceNotFoundError(f"Pull request #{pr_number} not found")

        # Get repository context
        repository = self.client.get_repository_parallel(owner, repo)

        # Get related issues if PR references them
        related_issues = []
        if pr.body:
            # Simple pattern matching for issue references
            import re

            issue_refs = re.findall(r"#(\d+)", pr.body)
            if issue_refs:
                issue_numbers = [int(ref) for ref in issue_refs]
                related_issues = self.client.get_issues_by_numbers(
                    owner, repo, issue_numbers
                )

        return DistilledData(
            repository=repository,
            pull_requests=[pr],
            issues=related_issues,
            metadata={
                "extraction_type": "code_review",
                "owner": owner,
                "repo": repo,
                "pr_number": pr_number,
                "timestamp": pr.updated_at.isoformat(),
                "files_changed": len(pr.files),
                "total_additions": pr.additions,
                "total_deletions": pr.deletions,
            },
        )

    def extract_for_bug_fix(
        self, owner: str, repo: str, issue_number: int
    ) -> DistilledData:
        """Extract data optimized for bug fixing tasks."""
        logger.info(
            f"Extracting bug fix data for issue #{issue_number} in {owner}/{repo}"
        )

        # Get issue with full details
        issues = self.client.get_issues_by_numbers(owner, repo, [issue_number])
        issue = issues[0] if issues else None

        if not issue:
            raise ResourceNotFoundError(f"Issue #{issue_number} not found")

        # Get repository context
        repository = self.client.get_repository_parallel(owner, repo)

        # Get related PRs
        related_prs = []
        prs = self.client.get_pull_requests(owner, repo, state="all")
        for pr in prs:
            if pr.body and f"#{issue_number}" in pr.body:
                related_prs.append(pr)

        return DistilledData(
            repository=repository,
            issues=[issue],
            pull_requests=related_prs,
            metadata={
                "extraction_type": "bug_fix",
                "owner": owner,
                "repo": repo,
                "issue_number": issue_number,
                "timestamp": issue.updated_at.isoformat(),
                "related_prs": len(related_prs),
            },
        )

    def extract_recent_activity(
        self, owner: str, repo: str, days: int = 7
    ) -> DistilledData:
        """Extract recent repository activity."""
        logger.info(f"Extracting recent activity for {owner}/{repo} (last {days} days)")

        from datetime import datetime, timedelta

        cutoff_date = datetime.now() - timedelta(days=days)

        # Get repository
        repository = self.client.get_repository_parallel(owner, repo)

        # Get recent issues
        issues = self.client.get_issues_parallel(owner, repo, state="all")
        recent_issues = [i for i in issues if i.updated_at >= cutoff_date]

        # Get recent PRs
        prs = self.client.get_pull_requests(owner, repo, state="all")
        recent_prs = [p for p in prs if p.updated_at >= cutoff_date]

        return DistilledData(
            repository=repository,
            issues=recent_issues,
            pull_requests=recent_prs,
            metadata={
                "extraction_type": "recent_activity",
                "owner": owner,
                "repo": repo,
                "days": days,
                "cutoff_date": cutoff_date.isoformat(),
                "recent_issues": len(recent_issues),
                "recent_prs": len(recent_prs),
            },
        )
