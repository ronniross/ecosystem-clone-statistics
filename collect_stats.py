#!/usr/bin/env python3
"""
Daily Clone Statistics Collector
Fetches clone traffic data for all repos listed in ASI Ecosystem

Requires GITHUB_TOKEN or TRAFFIC_TRACKER environment variable with repo access
"""

import os
import json
import re
from datetime import datetime, timezone
from pathlib import Path
import requests
from github import Github

# Configuration
ECOSYSTEM_README_URL = "https://raw.githubusercontent.com/ronniross/asi-ecosystem/main/README.md"
BASE_DIR = Path("repos")
GLOBAL_SUMMARY_FILE = Path("global-summary.json")

def get_github_token():
    """Get GitHub token from environment"""
    token = os.environ.get('GITHUB_TOKEN') or os.environ.get('TRAFFIC_TRACKER')
    if not token:
        raise ValueError("GITHUB_TOKEN or TRAFFIC_TRACKER environment variable not set")
    return token

def fetch_ecosystem_repos():
    """Fetch and parse the ASI Ecosystem README to extract repo URLs"""
    print("📥 Fetching ASI Ecosystem README...")
    response = requests.get(ECOSYSTEM_README_URL)
    response.raise_for_status()
    
    content = response.text
    
    # Extract GitHub repo URLs from markdown links
    # Pattern: [text](https://github.com/owner/repo)
    pattern = r'\[([^\]]+)\]\(https://github\.com/([^/]+)/([^/)]+)\)'
    matches = re.findall(pattern, content)
    
    repos = []
    for match in matches:
        owner = match[1]
        repo = match[2]
        repos.append(f"{owner}/{repo}")
    
    print(f" Found {len(repos)} repositories to track")
    return repos

def get_today_filename():
    """Generate filename for today's run"""
    now = datetime.now(timezone.utc)
    return f"{now.strftime('%Y-%m-%d')}.json"

def check_if_already_ran_today(repo_dir):
    """Check if stats were already collected today"""
    runs_dir = repo_dir / "runs"
    today_file = runs_dir / get_today_filename()
    return today_file.exists()

def fetch_clone_traffic(gh, repo_full_name):
    """Fetch clone traffic data from GitHub API"""
    try:
        repo = gh.get_repo(repo_full_name)
        traffic = repo.get_clones_traffic()
        
        # Get today's data (last entry in the list)
        if traffic.get('clones'):
            latest = traffic['clones'][-1]
            return {
                'timestamp': latest.timestamp.isoformat(),
                'count': latest.count,
                'uniques': latest.uniques
            }
        return None
    except Exception as e:
        print(f"  Error fetching {repo_full_name}: {e}")
        return None

def save_daily_run(repo_dir, data):
    """Save today's statistics to a new run file"""
    runs_dir = repo_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    
    today_file = runs_dir / get_today_filename()
    
    with open(today_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f" Saved: {today_file}")

def update_repo_summary(repo_dir, repo_name):
    """Update the summary.json for a specific repo"""
    runs_dir = repo_dir / "runs"
    summary_file = repo_dir / "summary.json"
    
    # Collect all run data
    all_runs = []
    unique_cloners_set = set()
    total_clones = 0
    
    if runs_dir.exists():
        for run_file in sorted(runs_dir.glob("*.json")):
            with open(run_file, 'r') as f:
                run_data = json.load(f)
                all_runs.append({
                    'date': run_file.stem,
                    'clones': run_data.get('count', 0),
                    'unique_cloners': run_data.get('uniques', 0)
                })
                total_clones += run_data.get('count', 0)
                # Note: We can't truly deduplicate cloners across time windows
                # So we track the maximum unique cloners seen in any day
                unique_cloners_set.add(run_data.get('uniques', 0))
    
    # Calculate summary
    summary = {
        'repo_name': repo_name,
        'last_updated': datetime.now(timezone.utc).isoformat(),
        'total_days_tracked': len(all_runs),
        'total_clones': total_clones,
        'max_unique_cloners_in_window': max(unique_cloners_set) if unique_cloners_set else 0,
        'first_tracked': all_runs[0]['date'] if all_runs else None,
        'last_tracked': all_runs[-1]['date'] if all_runs else None,
        'daily_history': all_runs
    }
    
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"   Updated summary: {summary_file}")
    return summary

def update_global_summary():
    """Update the global summary across all repos"""
    print("\n Updating global summary...")
    
    all_repo_summaries = []
    total_clones_global = 0
    total_repos = 0
    
    if BASE_DIR.exists():
        for repo_dir in BASE_DIR.iterdir():
            if repo_dir.is_dir():
                summary_file = repo_dir / "summary.json"
                if summary_file.exists():
                    with open(summary_file, 'r') as f:
                        summary = json.load(f)
                        all_repo_summaries.append(summary)
                        total_clones_global += summary.get('total_clones', 0)
                        total_repos += 1
    
    global_summary = {
        'last_updated': datetime.now(timezone.utc).isoformat(),
        'total_repos_tracked': total_repos,
        'total_clones_all_repos': total_clones_global,
        'repositories': all_repo_summaries
    }
    
    with open(GLOBAL_SUMMARY_FILE, 'w') as f:
        json.dump(global_summary, f, indent=2)
    
    print(f" Global summary updated: {GLOBAL_SUMMARY_FILE}")
    print(f"   Tracked {total_repos} repos with {total_clones_global} total clones")

def main():
    """Main execution function"""
    print(" Starting clone statistics collection\n")
    
    # Get GitHub client
    token = get_github_token()
    gh = Github(token)
    
    # Fetch list of repos to track
    repos_to_track = fetch_ecosystem_repos()
    
    print(f"\n Processing {len(repos_to_track)} repositories...\n")
    
    stats_collected = 0
    stats_skipped = 0
    
    for repo_full_name in repos_to_track:
        print(f"🔍 {repo_full_name}")
        
        # Create repo directory
        repo_safe_name = repo_full_name.replace('/', '_')
        repo_dir = BASE_DIR / repo_safe_name
        
        # Check if already ran today
        if check_if_already_ran_today(repo_dir):
            print(f"  ⏭️  Already collected today - skipping")
            stats_skipped += 1
            continue
        
        # Fetch clone traffic
        clone_data = fetch_clone_traffic(gh, repo_full_name)
        
        if clone_data:
            # Add metadata
            clone_data['repo'] = repo_full_name
            clone_data['collected_at'] = datetime.now(timezone.utc).isoformat()
            
            # Save daily run
            save_daily_run(repo_dir, clone_data)
            
            # Update repo summary
            update_repo_summary(repo_dir, repo_full_name)
            
            stats_collected += 1
        else:
            print(f"   No data available")
        
        print()  # Blank line between repos
    
    # Update global summary
    update_global_summary()
    
    print(f"\n Collection complete!")
    print(f"   New stats collected: {stats_collected}")
    print(f"   Skipped (already ran): {stats_skipped}")
    print(f"   Total repos: {len(repos_to_track)}")

if __name__ == "__main__":
    main()
