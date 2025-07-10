"""Command-line interface for Git Data Distiller."""

import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import click
from dotenv import load_dotenv

from .config import Config
from .extractors import GitHubExtractor
from .formatters import get_formatter
from .github_client import GitHubClient

# Load environment variables
load_dotenv()

import functools


def handle_cli_errors(operation_name="operation"):
    """Decorator to handle common CLI errors with consistent logging and output."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error during {operation_name}: {e}")
                click.echo(f"Error: {e}", err=True)
                sys.exit(1)

        return wrapper

    return decorator


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@click.group()
@click.option(
    "--config", "-c", type=click.Path(exists=True), help="Path to configuration file"
)
@click.option("--token", "-t", help="GitHub personal access token")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.pass_context
def cli(ctx, config, token, verbose):
    """Git Data Distiller - Convert GitHub data into AI-optimized prompts."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load configuration
    if config:
        config_obj = Config.from_file(config)
    else:
        config_obj = Config()

    # Set up GitHub token
    if token:
        github_token = token
    else:
        github_token = os.getenv("GITHUB_TOKEN") or config_obj.github_token

    if not github_token:
        click.echo(
            "Warning: No GitHub token provided. API rate limits will be restrictive.",
            err=True,
        )

    # Initialize clients
    github_client = GitHubClient(token=github_token)
    extractor = GitHubExtractor(github_client)

    # Store in context
    ctx.ensure_object(dict)
    ctx.obj["config"] = config_obj
    ctx.obj["client"] = github_client
    ctx.obj["extractor"] = extractor


@cli.command()
@click.argument("url")
@click.option(
    "--format",
    "-f",
    type=click.Choice(["code_review", "bug_fix", "feature", "analysis", "mcp"]),
    default="analysis",
    help="Output format type",
)
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.option(
    "--include-files", is_flag=True, help="Include file contents in code review format"
)
@click.option(
    "--max-items", type=int, default=50, help="Maximum number of items to extract"
)
@click.pass_context
@handle_cli_errors("data extraction")
def extract(ctx, url, format, output, include_files, max_items):
    """Extract data from a GitHub URL and format it for AI consumption."""
    extractor = ctx.obj["extractor"]

    click.echo(f"Extracting data from: {url}")

    # Extract data based on URL type
    if "/pull/" in url:
        # Extract specific PR
        url_info = extractor.client.parse_github_url(url)
        data = extractor.extract_pull_request(
            url_info["owner"], url_info["repo"], url_info["number"]
        )
    elif "/issues/" in url:
        # Extract specific issue
        url_info = extractor.client.parse_github_url(url)
        data = extractor.extract_issue(
            url_info["owner"], url_info["repo"], url_info["number"]
        )
    else:
        # Extract repository
        url_info = extractor.client.parse_github_url(url)
        data = extractor.extract_repository(
            url_info["owner"],
            url_info["repo"],
            max_issues=max_items,
            max_prs=max_items,
        )

    # Format data
    formatter = get_formatter(format)

    if format == "code_review":
        formatted_prompt = formatter.format(data, include_file_contents=include_files)
    elif format == "mcp":
        # Determine the base format type
        if data.pull_requests:
            base_format = "code_review"
        elif data.issues and any(
            "bug" in label.name.lower()
            for issue in data.issues
            for label in issue.labels
        ):
            base_format = "bug_fix"
        else:
            base_format = "analysis"
        formatted_prompt = formatter.format(data, format_type=base_format)
    else:
        formatted_prompt = formatter.format(data)

    # Output results
    if output:
        Path(output).write_text(formatted_prompt)
        click.echo(f"Prompt saved to: {output}")
    else:
        click.echo(formatted_prompt)


@cli.command()
@click.argument("owner")
@click.argument("repo")
@click.argument("pr_number", type=int)
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.option("--include-files", is_flag=True, help="Include file contents in output")
@click.pass_context
@handle_cli_errors("code review generation")
def review(ctx, owner, repo, pr_number, output, include_files):
    """Generate a code review prompt for a specific pull request."""
    extractor = ctx.obj["extractor"]

    click.echo(f"Generating code review for PR #{pr_number} in {owner}/{repo}")

    data = extractor.extract_for_code_review(owner, repo, pr_number)
    formatter = get_formatter("code_review")
    prompt = formatter.format(data, include_file_contents=include_files)

    if output:
        Path(output).write_text(prompt)
        click.echo(f"Code review prompt saved to: {output}")
    else:
        click.echo(prompt)


@cli.command()
@click.argument("owner")
@click.argument("repo")
@click.argument("issue_number", type=int)
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.pass_context
@handle_cli_errors("bug fix prompt generation")
def bugfix(ctx, owner, repo, issue_number, output):
    """Generate a bug fix prompt for a specific issue."""
    extractor = ctx.obj["extractor"]

    click.echo(f"Generating bug fix prompt for issue #{issue_number} in {owner}/{repo}")

    data = extractor.extract_for_bug_fix(owner, repo, issue_number)
    formatter = get_formatter("bug_fix")
    prompt = formatter.format(data)

    if output:
        Path(output).write_text(prompt)
        click.echo(f"Bug fix prompt saved to: {output}")
    else:
        click.echo(prompt)


@cli.command()
@click.argument("owner")
@click.argument("repo")
@click.option("--days", type=int, default=7, help="Number of days to look back")
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.pass_context
@handle_cli_errors("recent activity extraction")
def recent(ctx, owner, repo, days, output):
    """Generate a prompt for recent repository activity."""
    extractor = ctx.obj["extractor"]

    click.echo(f"Extracting recent activity for {owner}/{repo} (last {days} days)")

    data = extractor.extract_recent_activity(owner, repo, days)
    formatter = get_formatter("analysis")
    prompt = formatter.format(data)

    if output:
        Path(output).write_text(prompt)
        click.echo(f"Recent activity prompt saved to: {output}")
    else:
        click.echo(prompt)


def process_single_url(url, extractor, format_type, output_dir):
    """Process a single URL - helper function for parallel processing."""
    try:
        # Extract data
        data = extractor.extract_from_url(url)

        # Format data
        formatter = get_formatter(format_type)
        prompt = formatter.format(data)

        result = {"url": url, "success": True, "prompt": prompt}

        # Save to file if output directory specified
        if output_dir:
            # Generate filename from URL
            url_info = extractor.client.parse_github_url(url)
            filename = f"{url_info['owner']}_{url_info['repo']}"
            if url_info.get("number"):
                filename += f"_{url_info['type']}_{url_info['number']}"
            filename += ".md"

            output_file = output_dir / filename
            output_file.write_text(prompt)
            result["output_file"] = str(output_file)

        return result

    except Exception as e:
        logger.error(f"Error processing {url}: {e}")
        return {"url": url, "success": False, "error": str(e)}


@cli.command()
@click.argument("urls", nargs=-1, required=True)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["code_review", "bug_fix", "feature", "analysis", "mcp"]),
    default="analysis",
    help="Output format type",
)
@click.option(
    "--output-dir",
    "-d",
    type=click.Path(),
    help="Output directory for batch processing",
)
@click.option(
    "--max-workers",
    "-w",
    type=int,
    default=4,
    help="Maximum number of concurrent workers (default: 4)",
)
@click.pass_context
def batch(ctx, urls, format, output_dir, max_workers):
    """Process multiple GitHub URLs in batch with parallel processing."""
    extractor = ctx.obj["extractor"]

    output_path = None
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

    # Process URLs in parallel
    click.echo(f"Processing {len(urls)} URLs with {max_workers} workers...")

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_url = {
            executor.submit(
                process_single_url, url, extractor, format, output_path
            ): url
            for url in urls
        }

        # Process completed tasks as they finish
        for i, future in enumerate(as_completed(future_to_url), 1):
            url = future_to_url[future]
            try:
                result = future.result()
                results.append(result)

                if result["success"]:
                    click.echo(f"✓ {i}/{len(urls)}: {url}")
                    if output_path:
                        click.echo(f"  Saved to: {result['output_file']}")
                    elif not output_path:
                        # Display result if not saving to files
                        click.echo(f"\n--- {url} ---")
                        click.echo(result["prompt"])
                        click.echo("=" * 80)
                else:
                    click.echo(
                        f"✗ {i}/{len(urls)}: {url} - {result['error']}", err=True
                    )

            except Exception as e:
                click.echo(
                    f"✗ {i}/{len(urls)}: {url} - Unexpected error: {e}", err=True
                )
                results.append({"url": url, "success": False, "error": str(e)})

    # Summary
    successful = sum(1 for r in results if r["success"])
    click.echo(
        f"\nBatch processing complete: {successful}/{len(urls)} URLs processed successfully"
    )

    if successful < len(urls):
        failed_urls = [r["url"] for r in results if not r["success"]]
        click.echo(f"Failed URLs: {', '.join(failed_urls)}", err=True)


@cli.command()
@click.option("--token", help="GitHub personal access token to test")
@click.pass_context
@handle_cli_errors("authentication test")
def test_auth(ctx, token):
    """Test GitHub authentication."""
    if token:
        test_token = token
    else:
        test_token = os.getenv("GITHUB_TOKEN") or ctx.obj["config"].github_token

    if not test_token:
        click.echo(
            "No token provided. Set GITHUB_TOKEN environment variable or use --token option.",
            err=True,
        )
        sys.exit(1)

    client = GitHubClient(token=test_token)
    user_info = client.get("user")

    click.echo("✓ Authentication successful!")
    click.echo(f"  User: {user_info['login']}")
    click.echo(f"  Name: {user_info.get('name', 'Not set')}")
    click.echo(
        f"  Rate limit: {client.rate_limiter.remaining}/{client.rate_limiter.limit}"
    )


@cli.command()
def init_config():
    """Initialize a configuration file."""
    config_path = Path.cwd() / "git-distiller.yaml"

    if config_path.exists():
        click.echo(f"Configuration file already exists: {config_path}")
        if not click.confirm("Overwrite?"):
            return

    config = Config()
    config.save_to_file(str(config_path))

    click.echo(f"Configuration file created: {config_path}")
    click.echo("Edit the file to customize your settings.")


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
