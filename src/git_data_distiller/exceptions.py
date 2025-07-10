"""Custom exceptions for Git Data Distiller."""


class GitDataDistillerError(Exception):
    """Base exception for Git Data Distiller."""

    pass


class GitHubAPIError(GitDataDistillerError):
    """GitHub API related errors."""

    def __init__(
        self, message: str, status_code: int = None, response_text: str = None
    ):
        self.status_code = status_code
        self.response_text = response_text
        super().__init__(message)


class AuthenticationError(GitHubAPIError):
    """Authentication related errors."""

    pass


class RateLimitError(GitHubAPIError):
    """Rate limiting errors."""

    def __init__(self, message: str, reset_time: int = None):
        self.reset_time = reset_time
        super().__init__(message)


class ResourceNotFoundError(GitHubAPIError):
    """Resource not found errors."""

    pass


class PermissionError(GitHubAPIError):
    """Permission/access errors."""

    pass


class ConfigurationError(GitDataDistillerError):
    """Configuration related errors."""

    pass


class ExtractionError(GitDataDistillerError):
    """Data extraction errors."""

    pass


class FormattingError(GitDataDistillerError):
    """Prompt formatting errors."""

    pass


class CacheError(GitDataDistillerError):
    """Cache related errors."""

    pass
