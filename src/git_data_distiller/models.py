"""Data models for GitHub entities."""

from datetime import datetime
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field


class GitHubUser(BaseModel):
    """GitHub user model."""

    login: str
    id: int
    avatar_url: str
    html_url: str
    type: str = "User"


class GitHubLabel(BaseModel):
    """GitHub label model."""

    name: str
    color: str
    description: Optional[str] = None


class GitHubMilestone(BaseModel):
    """GitHub milestone model."""

    title: str
    description: Optional[str] = None
    state: str
    created_at: datetime
    updated_at: datetime
    due_on: Optional[datetime] = None
    closed_at: Optional[datetime] = None


class GitHubComment(BaseModel):
    """GitHub comment model."""

    id: int
    user: GitHubUser
    body: str
    created_at: datetime
    updated_at: datetime
    html_url: str


class GitHubCommit(BaseModel):
    """GitHub commit model."""

    sha: str
    message: str
    author: GitHubUser
    committer: GitHubUser
    date: datetime
    html_url: str
    stats: Optional[Dict[str, int]] = None


class GitHubFile(BaseModel):
    """GitHub file change model."""

    filename: str
    status: str  # added, removed, modified, renamed
    additions: int
    deletions: int
    changes: int
    patch: Optional[str] = None


class GitHubRepository(BaseModel):
    """GitHub repository model."""

    name: str
    full_name: str
    description: Optional[str] = None
    html_url: str
    clone_url: str
    language: Optional[str] = None
    languages: Dict[str, int] = Field(default_factory=dict)
    topics: List[str] = Field(default_factory=list)
    readme: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    pushed_at: datetime
    size: int
    stargazers_count: int
    watchers_count: int
    forks_count: int
    open_issues_count: int
    default_branch: str


class GitHubIssue(BaseModel):
    """GitHub issue model."""

    number: int
    title: str
    body: Optional[str] = None
    state: str
    labels: List[GitHubLabel] = Field(default_factory=list)
    milestone: Optional[GitHubMilestone] = None
    assignees: List[GitHubUser] = Field(default_factory=list)
    user: GitHubUser
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None
    html_url: str
    comments: List[GitHubComment] = Field(default_factory=list)
    comments_count: int = 0


class GitHubPullRequest(BaseModel):
    """GitHub pull request model."""

    number: int
    title: str
    body: Optional[str] = None
    state: str
    draft: bool = False
    merged: bool = False
    merged_at: Optional[datetime] = None
    merge_commit_sha: Optional[str] = None
    head_branch: str
    base_branch: str
    labels: List[GitHubLabel] = Field(default_factory=list)
    milestone: Optional[GitHubMilestone] = None
    assignees: List[GitHubUser] = Field(default_factory=list)
    requested_reviewers: List[GitHubUser] = Field(default_factory=list)
    user: GitHubUser
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None
    html_url: str
    diff_url: str
    patch_url: str
    comments: List[GitHubComment] = Field(default_factory=list)
    review_comments: List[GitHubComment] = Field(default_factory=list)
    commits: List[GitHubCommit] = Field(default_factory=list)
    files: List[GitHubFile] = Field(default_factory=list)
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0


class GitHubDiscussion(BaseModel):
    """GitHub discussion model."""

    number: int
    title: str
    body: Optional[str] = None
    category: str
    state: str
    locked: bool = False
    user: GitHubUser
    created_at: datetime
    updated_at: datetime
    html_url: str
    comments: List[GitHubComment] = Field(default_factory=list)
    comments_count: int = 0


class GitHubBranch(BaseModel):
    """GitHub branch model."""

    name: str
    sha: str
    protected: bool = False
    ahead_by: int = 0
    behind_by: int = 0


class DistilledData(BaseModel):
    """Container for all distilled GitHub data."""

    repository: Optional[GitHubRepository] = None
    issues: List[GitHubIssue] = Field(default_factory=list)
    pull_requests: List[GitHubPullRequest] = Field(default_factory=list)
    discussions: List[GitHubDiscussion] = Field(default_factory=list)
    branches: List[GitHubBranch] = Field(default_factory=list)
    commits: List[GitHubCommit] = Field(default_factory=list)
    metadata: Dict[str, Union[str, int, bool]] = Field(default_factory=dict)
