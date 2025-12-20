#!/usr/bin/env python3
"""
Index DependEval repositories into Sourcegraph.

Adds 150 DependEval repositories (in owner/repo format) to Sourcegraph
so they become indexed and searchable via the MCP search tool.
"""

import json
import os
import sys
from pathlib import Path
import requests


def load_repos(file_path: str) -> list[str]:
    """Load repositories from dependeval_repos_for_indexing.txt."""
    repos = []
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            # Remove leading quote
            if line.startswith('"'):
                line = line[1:]
            # Remove trailing quote and comma
            if line.endswith('",'):
                line = line[:-2]
            elif line.endswith('"'):
                line = line[:-1]
            if line:
                repos.append(line)
    return repos


def add_repos_via_external_service(
    repos: list[str],
    sourcegraph_url: str,
    sourcegraph_token: str,
    github_token: str
) -> tuple[int, int]:
    """
    Add repositories to Sourcegraph using a GITHUB external service.
    
    Args:
        repos: List of repository paths in format "owner/repo"
        sourcegraph_url: Base URL of Sourcegraph instance
        sourcegraph_token: Sourcegraph access token
        github_token: GitHub access token for auth
        
    Returns:
        Tuple of (success_count, fail_count)
    """
    # Build GitHub external service config with all repos
    github_config = {
        "url": "https://github.com",
        "token": github_token,
        "repos": repos
    }
    
    mutation = """
    mutation AddExternalService($input: AddExternalServiceInput!) {
        addExternalService(input: $input) {
            id
            kind
            displayName
        }
    }
    """
    
    variables = {
        "input": {
            "kind": "GITHUB",
            "displayName": "DependEval Benchmark Repositories",
            "config": json.dumps(github_config)
        }
    }
    
    headers = {
        "Authorization": f"token {sourcegraph_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "query": mutation,
        "variables": variables
    }
    
    try:
        print(f"Adding {len(repos)} repositories via external service...")
        resp = requests.post(
            f"{sourcegraph_url}/.api/graphql",
            json=payload,
            headers=headers,
            timeout=60
        )
        
        if resp.status_code not in [200, 201]:
            print(f"✗ HTTP {resp.status_code}")
            print(f"  Response: {resp.text[:200]}")
            return 0, len(repos)
        
        data = resp.json()
        
        if "errors" in data:
            errors = data["errors"]
            for error in errors:
                msg = error.get("message", "Unknown error")
                print(f"✗ GraphQL error: {msg[:200]}")
            return 0, len(repos)
        
        if "data" in data and data["data"].get("addExternalService"):
            service = data["data"]["addExternalService"]
            print(f"✓ Created external service: {service['id']}")
            print(f"  Kind: {service['kind']}")
            print(f"  Display name: {service['displayName']}")
            return len(repos), 0
        else:
            print(f"✗ Unexpected response: {data}")
            return 0, len(repos)
            
    except requests.RequestException as e:
        print(f"✗ Request failed: {e}")
        return 0, len(repos)


def main():
    """Main entry point."""
    # Load configuration
    repo_file = Path("dependeval_repos_for_indexing.txt")
    if not repo_file.exists():
        print(f"Error: {repo_file} not found")
        sys.exit(1)
    
    sourcegraph_url = os.getenv("SOURCEGRAPH_INSTANCE", "https://sourcegraph.sourcegraph.com")
    sourcegraph_token = os.getenv("SOURCEGRAPH_ACCESS_TOKEN")
    github_token = os.getenv("GITHUB_TOKEN")
    
    if not sourcegraph_token:
        print("Error: SOURCEGRAPH_ACCESS_TOKEN environment variable not set")
        sys.exit(1)
    if not github_token:
        print("Error: GITHUB_TOKEN environment variable not set")
        sys.exit(1)
    
    # Load repos
    repos = load_repos(str(repo_file))
    print(f"Loaded {len(repos)} repositories from {repo_file}")
    print(f"Sourcegraph instance: {sourcegraph_url}")
    print()
    
    # Validate and normalize repos (lowercase for Sourcegraph API compatibility)
    invalid_repos = [r for r in repos if '/' not in r]
    if invalid_repos:
        print(f"Warning: {len(invalid_repos)} invalid repos (missing /):")
        for r in invalid_repos[:5]:
            print(f"  - {r}")
        print()
    
    # Normalize repos to lowercase (GitHub URLs are case-insensitive)
    valid_repos = [r.lower() for r in repos if '/' in r]
    print(f"Valid repos: {len(valid_repos)}/{len(repos)}")
    print()
    
    # Add repos to Sourcegraph
    if not valid_repos:
        print("Error: No valid repos to add")
        sys.exit(1)
    
    success_count, fail_count = add_repos_via_external_service(
        valid_repos, sourcegraph_url, sourcegraph_token, github_token
    )
    
    print()
    print(f"Summary:")
    print(f"  ✓ Indexed: {success_count}")
    print(f"  ✗ Failed: {fail_count}")
    print(f"  Total valid repos: {len(valid_repos)}")
    
    if fail_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
