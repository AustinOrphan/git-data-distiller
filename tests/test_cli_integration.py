"""Integration tests for CLI commands."""

import json
import subprocess
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest.mock import patch

import pytest

# Add the src directory to the path so we can import the CLI
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from git_data_distiller.cli import cli


class TestCLIIntegration:
    """Integration tests for CLI commands."""

    def test_cli_help(self):
        """Test that CLI help works."""
        result = subprocess.run(
            [sys.executable, "-m", "git_data_distiller.cli", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent / "src",
        )
        assert result.returncode == 0
        assert "Git Data Distiller" in result.stdout
        assert "extract" in result.stdout
        assert "review" in result.stdout
        assert "bugfix" in result.stdout

    def test_extract_command_help(self):
        """Test extract command help."""
        result = subprocess.run(
            [sys.executable, "-m", "git_data_distiller.cli", "extract", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent / "src",
        )
        assert result.returncode == 0
        assert "Extract data from a GitHub URL" in result.stdout
        assert "--format" in result.stdout
        assert "--output" in result.stdout

    def test_review_command_help(self):
        """Test review command help."""
        result = subprocess.run(
            [sys.executable, "-m", "git_data_distiller.cli", "review", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent / "src",
        )
        assert result.returncode == 0
        assert "Generate a code review prompt" in result.stdout

    def test_bugfix_command_help(self):
        """Test bugfix command help."""
        result = subprocess.run(
            [sys.executable, "-m", "git_data_distiller.cli", "bugfix", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent / "src",
        )
        assert result.returncode == 0
        assert "Generate a bug fix prompt" in result.stdout

    def test_batch_command_help(self):
        """Test batch command help."""
        result = subprocess.run(
            [sys.executable, "-m", "git_data_distiller.cli", "batch", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent / "src",
        )
        assert result.returncode == 0
        assert "Process multiple GitHub URLs" in result.stdout
        assert "--max-workers" in result.stdout

    def test_test_auth_command_help(self):
        """Test test-auth command help."""
        result = subprocess.run(
            [sys.executable, "-m", "git_data_distiller.cli", "test-auth", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent / "src",
        )
        assert result.returncode == 0
        assert "Test GitHub authentication" in result.stdout

    @patch("git_data_distiller.cli.GitHubClient")
    def test_test_auth_success(self, mock_client_class):
        """Test test-auth command with mocked success."""
        # Mock the client and its methods
        mock_client = mock_client_class.return_value
        mock_client.get.return_value = {
            "login": "testuser",
            "name": "Test User",
        }
        mock_client.rate_limiter.remaining = 4999
        mock_client.rate_limiter.limit = 5000

        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(cli, ["test-auth", "--token", "fake_token"])

        assert result.exit_code == 0
        assert "Authentication successful" in result.output
        assert "testuser" in result.output

    @patch("git_data_distiller.cli.GitHubClient")
    def test_extract_invalid_url(self, mock_client_class):
        """Test extract command with invalid URL."""
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(cli, ["extract", "not-a-github-url"])

        assert result.exit_code == 1
        assert "Error:" in result.output

    @patch("git_data_distiller.cli.GitHubExtractor")
    @patch("git_data_distiller.cli.GitHubClient")
    def test_extract_repository_success(self, mock_client_class, mock_extractor_class):
        """Test successful repository extraction."""
        # Mock the extractor
        mock_extractor = mock_extractor_class.return_value
        mock_extractor.client.parse_github_url.return_value = {
            "owner": "octocat",
            "repo": "Hello-World",
            "type": "repository",
        }
        mock_extractor.extract_repository.return_value = type("MockData", (), {
            "name": "Hello-World",
            "description": "Test repo",
            "pull_requests": [],
            "issues": [],
        })()

        from click.testing import CliRunner

        runner = CliRunner()
        with NamedTemporaryFile(mode="w", suffix=".md", delete=False) as tmp:
            result = runner.invoke(
                cli,
                [
                    "extract",
                    "https://github.com/octocat/Hello-World",
                    "--output",
                    tmp.name,
                    "--token",
                    "fake_token",
                ],
            )

        assert result.exit_code == 0
        assert "Prompt saved to:" in result.output

        # Cleanup
        Path(tmp.name).unlink()

    @patch("git_data_distiller.cli.GitHubExtractor")
    @patch("git_data_distiller.cli.GitHubClient")
    def test_review_command_success(self, mock_client_class, mock_extractor_class):
        """Test successful review command."""
        # Mock the extractor
        mock_extractor = mock_extractor_class.return_value
        mock_extractor.extract_for_code_review.return_value = type("MockData", (), {
            "pull_request": type("MockPR", (), {
                "number": 123,
                "title": "Test PR",
            })(),
        })()

        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["review", "octocat", "Hello-World", "123", "--token", "fake_token"],
        )

        assert result.exit_code == 0

    @patch("git_data_distiller.cli.GitHubExtractor")
    @patch("git_data_distiller.cli.GitHubClient")
    def test_bugfix_command_success(self, mock_client_class, mock_extractor_class):
        """Test successful bugfix command."""
        # Mock the extractor
        mock_extractor = mock_extractor_class.return_value
        mock_extractor.extract_for_bug_fix.return_value = type("MockData", (), {
            "issue": type("MockIssue", (), {
                "number": 456,
                "title": "Test Issue",
            })(),
        })()

        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["bugfix", "octocat", "Hello-World", "456", "--token", "fake_token"],
        )

        assert result.exit_code == 0

    @patch("git_data_distiller.cli.GitHubExtractor")
    @patch("git_data_distiller.cli.GitHubClient")
    def test_recent_command_success(self, mock_client_class, mock_extractor_class):
        """Test successful recent command."""
        # Mock the extractor
        mock_extractor = mock_extractor_class.return_value
        mock_extractor.extract_recent_activity.return_value = type("MockData", (), {
            "repository": type("MockRepo", (), {
                "name": "Hello-World",
            })(),
        })()

        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["recent", "octocat", "Hello-World", "--days", "7", "--token", "fake_token"],
        )

        assert result.exit_code == 0

    @patch("git_data_distiller.cli.process_single_url")
    @patch("git_data_distiller.cli.GitHubExtractor")
    @patch("git_data_distiller.cli.GitHubClient")
    def test_batch_command_success(
        self, mock_client_class, mock_extractor_class, mock_process_url
    ):
        """Test successful batch command."""
        # Mock the process_single_url function
        mock_process_url.return_value = {
            "url": "https://github.com/octocat/Hello-World",
            "success": True,
            "prompt": "Test prompt content",
        }

        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "batch",
                "https://github.com/octocat/Hello-World",
                "https://github.com/octocat/Spoon-Knife",
                "--max-workers",
                "2",
                "--token",
                "fake_token",
            ],
        )

        assert result.exit_code == 0
        assert "Batch processing complete" in result.output

    def test_cli_version_info(self):
        """Test that CLI provides version information."""
        result = subprocess.run(
            [sys.executable, "-c", "import git_data_distiller; print('import successful')"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent / "src",
        )
        assert result.returncode == 0
        assert "import successful" in result.stdout

    def test_cli_module_structure(self):
        """Test that the CLI module structure is correct."""
        # Test that we can import the main components
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                """
import sys
from pathlib import Path
sys.path.insert(0, str(Path('src')))

try:
    from git_data_distiller.cli import cli, extract, review, bugfix, batch, test_auth
    from git_data_distiller.github_client import GitHubClient
    from git_data_distiller.extractors import GitHubExtractor
    from git_data_distiller.formatters import get_formatter
    print("All imports successful")
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)
""",
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )
        assert result.returncode == 0
        assert "All imports successful" in result.stdout

    @patch.dict("os.environ", {"GITHUB_TOKEN": ""})
    def test_cli_without_token_warning(self):
        """Test CLI warning when no GitHub token is provided."""
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        # Should still work but might show warning
        assert result.exit_code == 0

    def test_invalid_command(self):
        """Test invalid CLI command."""
        result = subprocess.run(
            [sys.executable, "-m", "git_data_distiller.cli", "invalid-command"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent / "src",
        )
        assert result.returncode != 0
        assert "No such command" in result.stderr or "Usage:" in result.stdout

    @patch("git_data_distiller.cli.GitHubClient")
    def test_error_handling_in_extract(self, mock_client_class):
        """Test error handling in extract command."""
        # Mock client to raise an exception
        mock_client_class.side_effect = Exception("Connection failed")

        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(
            cli, ["extract", "https://github.com/octocat/Hello-World", "--token", "fake"]
        )

        assert result.exit_code == 1
        assert "Error:" in result.output

    def test_config_initialization(self):
        """Test config initialization command."""
        from click.testing import CliRunner

        runner = CliRunner()
        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp:
            # Change to a temporary directory
            with runner.isolated_filesystem():
                result = runner.invoke(cli, ["init-config"])

        assert result.exit_code == 0
        assert "Configuration file created" in result.output


class TestCLIErrorHandling:
    """Test CLI error handling scenarios."""

    def test_missing_required_arguments(self):
        """Test CLI with missing required arguments."""
        from click.testing import CliRunner

        runner = CliRunner()

        # Test review without required arguments
        result = runner.invoke(cli, ["review"])
        assert result.exit_code != 0

        # Test bugfix without required arguments
        result = runner.invoke(cli, ["bugfix"])
        assert result.exit_code != 0

        # Test batch without URLs
        result = runner.invoke(cli, ["batch"])
        assert result.exit_code != 0

    def test_invalid_pr_number(self):
        """Test review command with invalid PR number."""
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(cli, ["review", "owner", "repo", "not-a-number"])
        assert result.exit_code != 0

    def test_invalid_issue_number(self):
        """Test bugfix command with invalid issue number."""
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(cli, ["bugfix", "owner", "repo", "not-a-number"])
        assert result.exit_code != 0

    def test_invalid_format_option(self):
        """Test extract command with invalid format."""
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(
            cli, ["extract", "https://github.com/octocat/Hello-World", "--format", "invalid"]
        )
        assert result.exit_code != 0


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__])