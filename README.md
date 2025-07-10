# Git Data Distiller

Extract and format GitHub repository data into AI-optimized prompts for code reviews, bug fixes, and feature development.

## Features

- **Multi-source extraction**: Pull data from repositories, issues, pull requests, and discussions
- **AI-optimized formatting**: Generate prompts tailored for Claude, GPT-4, and other AI assistants
- **Smart caching**: Reduce API calls with intelligent caching and rate limit handling
- **Multiple output formats**: Code review, bug fix, feature request, analysis, and MCP formats
- **Batch processing**: Process multiple GitHub URLs efficiently
- **Cursor-based pagination**: Full support for GitHub's latest API requirements

## Installation

```bash
# Install from source
pip install -e .

# Install with development dependencies
pip install -e ".[dev]"
```

## Configuration

1. Create a GitHub Personal Access Token:
   - Go to GitHub Settings → Developer settings → Personal access tokens
   - Generate a new token with `repo` scope (and `read:org` for organization repos)

2. Set up configuration:
   ```bash
   # Option 1: Environment variable
   export GITHUB_TOKEN=your_token_here
   
   # Option 2: Configuration file
   cp git-distiller.yaml.example git-distiller.yaml
   # Edit git-distiller.yaml and add your token
   ```

## Usage

### Basic Commands

```bash
# Test authentication
git-distiller test-auth

# Extract repository data
git-distiller extract https://github.com/owner/repo

# Generate code review prompt
git-distiller review owner repo 123

# Generate bug fix prompt
git-distiller bugfix owner repo 456

# Get recent repository activity
git-distiller recent owner repo --days 7

# Batch process multiple URLs
git-distiller batch url1 url2 url3 --output-dir ./prompts/
```

### Output Formats

Use the `--format` option with the extract command:

- `code_review`: Optimized for code review tasks
- `bug_fix`: Focused on debugging and fixes
- `feature`: For feature development
- `analysis`: General repository analysis
- `mcp`: Model Context Protocol format

### Advanced Options

```bash
# Include file contents in code review
git-distiller review owner repo 123 --include-files

# Limit extraction scope
git-distiller extract <url> --max-items 50

# Save output to file
git-distiller extract <url> --output analysis.md

# Use custom configuration
git-distiller --config custom-config.yaml extract <url>
```

## Known Limitations

- **Large Datasets**: GitHub requires cursor-based pagination for repositories with 1000+ issues/PRs. The tool handles this automatically but extraction may take longer.
- **Rate Limits**: Without authentication, you're limited to 60 requests/hour. With a token, this increases to 5000/hour.
- **API Changes**: GitHub's API evolves; some features may require updates.

## Development

### Code Quality

```bash
# Format code
black src/ --line-length 88

# Sort imports
isort src/

# Type checking
mypy src/

# Linting
flake8 src/ --max-line-length 88

# Run tests
pytest tests/
```

### Project Structure

```
src/git_data_distiller/
├── cli.py              # Command-line interface
├── github_client.py    # GitHub API client with pagination
├── extractors.py       # Data extraction logic
├── formatters.py       # Output formatting
├── models.py          # Pydantic data models
├── config.py          # Configuration management
├── cache.py           # Caching system
└── exceptions.py      # Custom exceptions
```

## Recent Updates

- **Cursor-based Pagination**: Full support for GitHub's latest pagination requirements
- **Security**: Improved token handling and configuration
- **Code Quality**: Comprehensive flake8 compliance
- **Testing**: Basic test infrastructure with pytest

## Contributing

1. Fork the repository
2. Create a feature branch
3. Run code quality checks
4. Submit a pull request

## License

[Add your license here]

## Support

For issues and feature requests, please use the GitHub issue tracker.