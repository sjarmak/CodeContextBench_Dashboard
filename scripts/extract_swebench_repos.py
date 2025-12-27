#!/usr/bin/env python3
"""
Extract unique repository names from SWE-bench Pro and SWE-bench Verified datasets.
Output format: "org/repo",\n"org/repo",\n...
"""

from datasets import load_dataset

def extract_repos_from_swebench_pro():
    """Extract repos from SWE-bench Pro (ScaleAI)."""
    print("Loading SWE-bench Pro dataset...")
    ds = load_dataset("ScaleAI/SWE-bench_Pro", split="test")
    repos = sorted(set(ex["repo"] for ex in ds))
    return repos

def extract_repos_from_swebench_verified():
    """Extract repos from SWE-bench Verified (princeton-nlp)."""
    print("Loading SWE-bench Verified dataset...")
    ds = load_dataset("princeton-nlp/SWE-bench_Verified", split="test")
    repos = sorted(set(ex["repo"] for ex in ds))
    return repos

def main():
    # Get repos from both datasets
    pro_repos = extract_repos_from_swebench_pro()
    verified_repos = extract_repos_from_swebench_verified()

    # Combine and deduplicate
    all_repos = sorted(set(pro_repos + verified_repos))

    print("\n" + "="*80)
    print("SWE-bench Pro repositories:")
    print("="*80)
    for repo in pro_repos:
        print(f'"{repo}",')

    print("\n" + "="*80)
    print("SWE-bench Verified repositories:")
    print("="*80)
    for repo in verified_repos:
        print(f'"{repo}",')

    print("\n" + "="*80)
    print("All unique repositories (combined):")
    print("="*80)
    # Print in requested format
    for i, repo in enumerate(all_repos):
        if i < len(all_repos) - 1:
            print(f'"{repo}",')
        else:
            print(f'"{repo}"')

    print("\n" + "="*80)
    print(f"Total: {len(all_repos)} unique repositories")
    print(f"  - SWE-bench Pro: {len(pro_repos)}")
    print(f"  - SWE-bench Verified: {len(verified_repos)}")
    print("="*80)

if __name__ == "__main__":
    main()
