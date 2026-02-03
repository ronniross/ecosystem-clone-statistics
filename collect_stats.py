#!/usr/bin/env python3
"""
Daily Clone Statistics Collector
Fetches clone traffic data for all repos listed in ASI Ecosystem

Requires GITHUB_TOKEN or TRAFFIC_TRACKER environment variable with repo access
"""

import os
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
import requests
from github import Github, GithubException

# Configuration
ECOSYSTEM_README_URL = "https://raw.githubusercontent.com/ronniross/asi-ecosystem/main/README.md"
BASE_DIR = Path("repos")
GLOBAL_SUMMARY_FILE = Path("global-summary.json")

def get_github_token():
    """Get GitHub token from environment"""
    token = os.environ.get('TRAFFIC_TRACKER') or os.environ.get('GITHUB_TOKEN')
    if not token:
        print(" Error: TRAFFIC_TRACKER or GITHUB_TOKEN not found in environment.")
        sys.exit(1)
    return token

def fetch_ecosystem_repos():
    """Fetch and parse the ASI Ecosystem README to extract repo URLs"""
    print(f"📥 Fetching ASI Ecosystem README from: {ECOSYSTEM_README_URL}")
    try:
        response = requests.get(ECOSYSTEM_README_URL, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f" Failed to download README: {e}")
        sys.exit(1)
    
    content = response.text
    
    # Extract GitHub repo URLs from markdown links
    pattern = r'\[([^\]]+)\]\(https://github\.com/([^/]+)/([^/)]+)\)'
    matches = re.findall(pattern, content)
    
    repos = []
    seen = set()
    for match in matches:
        owner = match[1]
        repo_name = match[2].split('?')[0].split('#')[0] # Clean URL params
        full_name = f"{owner}/{repo_name}"
        
        if full_name not in seen:
            repos.append(full_name)
            seen.add(full_name)
    
    print(f" Found {len(repos)} unique repositories to track")
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
        # Note: You need Push access to the target repo to read traffic stats
        traffic = repo.get_clones_traffic()
        
        if traffic.get('clones'):
            latest = traffic['clones'][-1]
            return {
                'timestamp': latest.timestamp.isoformat(),
                'count': latest.count,
                'uniques': latest.uniques
            }
        return None
    except GithubException as e:
        if e.status == 403:
            print(f"   Access Denied (403): Check TRAFFIC_TRACKER permissions for {repo_full_name}")
        elif e.status == 404:
            print(f"   Repo not found (404): {repo_full_name}")
        else:
            print(f"   GitHub API Error: {e}")
        return None
    except Exception as e:
        print(f"   Unexpected Error fetching {repo_full_name}: {e}")
        return None

def save_daily_run(repo_dir, data):
    """Save today's statistics to a new run file"""
    runs_dir = repo_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    
    today_file = runs_dir / get_today_filename()
    
    with open(today_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"   Saved: {today_file}")

def update_repo_summary(repo_dir, repo_name):
    """Update the summary.json for a specific repo"""
    runs_dir = repo_dir / "runs"
    summary_file = repo_dir / "summary.json"
    
    all_runs = []
    unique_cloners_set = set()
    total_clones = 0
    
    if runs_dir.exists():
        for run_file in sorted(runs_dir.glob("*.json")):
            try:
                with open(run_file, 'r') as f:
                    run_data = json.load(f)
                    all_runs.append({
                        'date': run_file.stem,
                        'clones': run_data.get('count', 0),
                        'unique_cloners': run_data.get('uniques', 0)
                    })
                    total_clones += run_data.get('count', 0)
                    unique_cloners_set.add(run_data.get('uniques', 0))
            except json.JSONDecodeError:
                print(f"   Warning: Corrupt JSON file {run_file}")
    
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
    
    return summary

def update_global_summary():
    """Update the global summary across all repos"""
    print("\n🌎 Updating global summary...")
    
    all_repo_summaries = []
    total_clones_global = 0
    total_repos = 0
    
    if BASE_DIR.exists():
        for repo_dir in BASE_DIR.iterdir():
            if repo_dir.is_dir():
                summary_file = repo_dir / "summary.json"
                if summary_file.exists():
                    try:
                        with open(summary_file, 'r') as f:
                            summary = json.load(f)
                            all_repo_summaries.append(summary)
                            total_clones_global += summary.get('total_clones', 0)
                            total_repos += 1
                    except Exception:
                        continue
    
    global_summary = {
        'last_updated': datetime.now(timezone.utc).isoformat(),
        'total_repos_tracked': total_repos,
        'total_clones_all_repos': total_clones_global,
        'repositories': sorted(all_repo_summaries, key=lambda x: x.get('total_clones', 0), reverse=True)
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
    
    # Verify token validity broadly
    try:
        user = gh.get_user()
        print(f" Authenticated as: {user.login}")
    except Exception as e:
        print(f" Error authenticating with GitHub Token: {e}")
        sys.exit(1)

    # Fetch list of repos to track
    repos_to_track = fetch_ecosystem_repos()
    
    print(f"\n Processing {len(repos_to_track)} repositories...\n")
    
    stats_collected = 0
    stats_skipped = 0
    
    for repo_full_name in repos_to_track:
        print(f" {repo_full_name}")
        
        # Create repo directory
        repo_safe_name = repo_full_name.replace('/', '_')
        repo_dir = BASE_DIR / repo_safe_name
        
        # Check if already ran today
        if check_if_already_ran_today(repo_dir):
            print(f"    Already collected today - skipping")
            stats_skipped += 1
            continue
        
        # Fetch clone traffic
        clone_data = fetch_clone_traffic(gh, repo_full_name)
        
        if clone_data:
            clone_data['repo'] = repo_full_name
            clone_data['collected_at'] = datetime.now(timezone.utc).isoformat()
            
            save_daily_run(repo_dir, clone_data)
            update_repo_summary(repo_dir, repo_full_name)
            stats_collected += 1
        else:
            print(f"   No data available or access denied")
        
    update_global_summary()
    
    print(f"\n Collection complete!")
    print(f"   New stats collected: {stats_collected}")
    print(f"   Skipped (already ran): {stats_skipped}")

if __name__ == "__main__":
    main()
