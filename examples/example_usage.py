#!/usr/bin/env python3
"""
Example usage of Git Data Distiller programmatically.
"""

import os
from git_data_distiller.github_client import GitHubClient
from git_data_distiller.extractors import GitHubExtractor
from git_data_distiller.formatters import get_formatter
from git_data_distiller.config import load_config

def main():
    # Load configuration
    config = load_config()
    
    # Initialize GitHub client
    token = os.getenv('GITHUB_TOKEN') or config.github_token
    if not token:
        print("Error: No GitHub token found. Set GITHUB_TOKEN environment variable.")
        return
    
    client = GitHubClient(token=token)
    extractor = GitHubExtractor(client)
    
    # Example 1: Extract repository data
    print("=== Repository Analysis ===")
    try:
        repo_data = extractor.extract_repository(
            "microsoft", "vscode", 
            max_issues=10, 
            max_prs=5
        )
        
        formatter = get_formatter("analysis")
        prompt = formatter.format(repo_data)
        print(prompt[:500] + "...")
        
    except Exception as e:
        print(f"Error: {e}")
    
    # Example 2: Code review for a specific PR
    print("\n=== Code Review Example ===")
    try:
        # Replace with actual PR number
        pr_data = extractor.extract_for_code_review("microsoft", "vscode", 123456)
        
        formatter = get_formatter("code_review")
        prompt = formatter.format(pr_data, include_file_contents=False)
        print(prompt[:500] + "...")
        
    except Exception as e:
        print(f"Error: {e}")
    
    # Example 3: Bug fix analysis
    print("\n=== Bug Fix Analysis ===")
    try:
        # Replace with actual issue number
        bug_data = extractor.extract_for_bug_fix("microsoft", "vscode", 123456)
        
        formatter = get_formatter("bug_fix")
        prompt = formatter.format(bug_data)
        print(prompt[:500] + "...")
        
    except Exception as e:
        print(f"Error: {e}")
    
    # Example 4: Recent activity
    print("\n=== Recent Activity ===")
    try:
        recent_data = extractor.extract_recent_activity("microsoft", "vscode", days=7)
        
        formatter = get_formatter("analysis")
        prompt = formatter.format(recent_data)
        print(f"Found {len(recent_data.issues)} recent issues and {len(recent_data.pull_requests)} recent PRs")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()