"""Configuration management for Git Data Distiller."""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import BaseModel, Field


class OutputConfig(BaseModel):
    """Output formatting configuration."""

    max_file_size: int = Field(
        default=10000, description="Maximum file size to include in output"
    )
    max_comments: int = Field(
        default=20, description="Maximum number of comments to include"
    )
    max_commits: int = Field(
        default=10, description="Maximum number of commits to include"
    )
    truncate_length: int = Field(
        default=1000, description="Default text truncation length"
    )
    include_patches: bool = Field(
        default=False, description="Include code patches in output"
    )
    include_file_contents: bool = Field(
        default=False, description="Include full file contents"
    )


class ExtractionConfig(BaseModel):
    """Data extraction configuration."""

    max_issues: int = Field(
        default=50, description="Maximum number of issues to extract"
    )
    max_prs: int = Field(
        default=20, description="Maximum number of pull requests to extract"
    )
    include_closed: bool = Field(default=True, description="Include closed issues/PRs")
    include_comments: bool = Field(
        default=True, description="Include comments in extraction"
    )
    include_commits: bool = Field(
        default=True, description="Include commit information"
    )
    include_files: bool = Field(
        default=True, description="Include file change information"
    )
    recent_days: int = Field(
        default=30, description="Default number of days for recent activity"
    )


class CacheConfig(BaseModel):
    """Caching configuration."""

    enabled: bool = Field(default=True, description="Enable caching")
    ttl_seconds: int = Field(default=3600, description="Cache time-to-live in seconds")
    cache_dir: str = Field(
        default=".git-distiller-cache", description="Cache directory"
    )
    max_size_mb: int = Field(default=100, description="Maximum cache size in MB")


class TemplateConfig(BaseModel):
    """Custom template configuration."""

    template_dir: Optional[str] = Field(
        default=None, description="Custom template directory"
    )
    custom_templates: Dict[str, str] = Field(
        default_factory=dict, description="Custom template mappings"
    )


class Config(BaseModel):
    """Main configuration class."""

    github_token: Optional[str] = Field(
        default=None, description="GitHub personal access token"
    )
    github_base_url: str = Field(
        default="https://api.github.com", description="GitHub API base URL"
    )

    # Sub-configurations
    output: OutputConfig = Field(default_factory=OutputConfig)
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    templates: TemplateConfig = Field(default_factory=TemplateConfig)

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: Optional[str] = Field(default=None, description="Log file path")

    # Rate limiting
    respect_rate_limits: bool = Field(
        default=True, description="Respect GitHub rate limits"
    )
    requests_per_second: float = Field(
        default=10.0, description="Maximum requests per second"
    )

    # Custom settings
    custom_settings: Dict[str, Any] = Field(
        default_factory=dict, description="Custom user settings"
    )

    class Config:
        """Pydantic configuration."""

        env_prefix = "GIT_DISTILLER_"
        case_sensitive = False

    @classmethod
    def from_file(cls, file_path: str) -> "Config":
        """Load configuration from YAML file."""
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")

        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}

        return cls(**data)

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        return cls()

    def save_to_file(self, file_path: str) -> None:
        """Save configuration to YAML file."""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict and remove None values
        data = self.dict(exclude_none=True)

        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, indent=2)

    def get_cache_dir(self) -> Path:
        """Get cache directory path."""
        cache_dir = Path(self.cache.cache_dir)
        if not cache_dir.is_absolute():
            cache_dir = Path.cwd() / cache_dir
        return cache_dir

    def get_template_dir(self) -> Optional[Path]:
        """Get template directory path."""
        if not self.templates.template_dir:
            return None

        template_dir = Path(self.templates.template_dir)
        if not template_dir.is_absolute():
            template_dir = Path.cwd() / template_dir
        return template_dir

    def merge_with_env(self) -> "Config":
        """Merge configuration with environment variables."""
        env_vars = {}

        # GitHub token from environment
        if github_token := os.getenv("GITHUB_TOKEN"):
            env_vars["github_token"] = github_token

        # GitHub Enterprise URL
        if github_url := os.getenv("GITHUB_API_URL"):
            env_vars["github_base_url"] = github_url

        # Log level
        if log_level := os.getenv("LOG_LEVEL"):
            env_vars["log_level"] = log_level

        # Create new config with merged values
        merged_data = self.dict()
        merged_data.update(env_vars)

        return Config(**merged_data)


def load_config(config_path: Optional[str] = None) -> Config:
    """Load configuration from file or environment."""
    if config_path and Path(config_path).exists():
        config = Config.from_file(config_path)
    else:
        # Look for default config files
        default_paths = [
            Path.cwd() / "git-distiller.yaml",
            Path.cwd() / "git-distiller.yml",
            Path.cwd() / ".git-distiller.yaml",
            Path.cwd() / ".git-distiller.yml",
            Path.home() / ".config" / "git-distiller" / "config.yaml",
            Path.home() / ".git-distiller.yaml",
        ]

        config = None
        for path in default_paths:
            if path.exists():
                config = Config.from_file(str(path))
                break

        if not config:
            config = Config()

    # Merge with environment variables
    return config.merge_with_env()


def create_default_config_file(path: str) -> None:
    """Create a default configuration file."""
    config = Config()
    config.save_to_file(path)


# Default configuration template
DEFAULT_CONFIG_YAML = """# Git Data Distiller Configuration

# GitHub API Configuration
github_token: null  # Set your GitHub personal access token here or use GITHUB_TOKEN env var
github_base_url: "https://api.github.com"  # Use GitHub Enterprise URL if needed

# Output Formatting
output:
  max_file_size: 10000      # Maximum file size to include in output (bytes)
  max_comments: 20          # Maximum number of comments to include
  max_commits: 10           # Maximum number of commits to include
  truncate_length: 1000     # Default text truncation length
  include_patches: false    # Include code patches in output
  include_file_contents: false  # Include full file contents

# Data Extraction
extraction:
  max_issues: 50           # Maximum number of issues to extract
  max_prs: 20              # Maximum number of pull requests to extract
  include_closed: true     # Include closed issues/PRs
  include_comments: true   # Include comments in extraction
  include_commits: true    # Include commit information
  include_files: true      # Include file change information
  recent_days: 30          # Default number of days for recent activity

# Caching
cache:
  enabled: true            # Enable caching
  ttl_seconds: 3600        # Cache time-to-live in seconds (1 hour)
  cache_dir: ".git-distiller-cache"  # Cache directory
  max_size_mb: 100         # Maximum cache size in MB

# Custom Templates
templates:
  template_dir: null       # Custom template directory
  custom_templates: {}     # Custom template mappings

# Logging
log_level: "INFO"          # Logging level (DEBUG, INFO, WARNING, ERROR)
log_file: null             # Log file path (null for console only)

# Rate Limiting
respect_rate_limits: true  # Respect GitHub rate limits
requests_per_second: 10.0  # Maximum requests per second

# Custom Settings
custom_settings: {}        # Add your custom settings here
"""
