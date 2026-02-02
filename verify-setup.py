#!/usr/bin/env python3
"""
Setup verification script
Run this to check if everything is configured correctly
"""

import os
import sys
import requests
from pathlib import Path

def check_token():
    """Check if GitHub token is available"""
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        print(" GITHUB_TOKEN environment variable not set")
        print("   Set it with: export GITHUB_TOKEN=your_token_here")
        return False
    print(" GitHub token found")
    return True

def check_dependencies():
    """Check if required packages are installed"""
    try:
        import github
        import requests
        print(" Dependencies installed")
        return True
    except ImportError as e:
        print(f" Missing dependency: {e}")
        print("   Install with: pip install -r requirements.txt")
        return False

def check_ecosystem_access():
    """Check if we can access the ecosystem README"""
    url = "https://raw.githubusercontent.com/ronniross/asi-ecosystem/main/README.md"
    try:
        response = requests.get(url)
        response.raise_for_status()
        print(" Can access ASI Ecosystem README")
        print(f"   Found {len(response.text)} characters")
        return True
    except Exception as e:
        print(f" Cannot access ecosystem README: {e}")
        return False

def check_directory_structure():
    """Check if directory structure is correct"""
    required_files = [
        'collect_stats.py',
        'requirements.txt',
        'README.md',
        '.github/workflows/daily-stats.yml'
    ]
    
    all_exist = True
    for file in required_files:
        if Path(file).exists():
            print(f" {file}")
        else:
            print(f" {file} - MISSING")
            all_exist = False
    
    return all_exist

def main():
    print(" Checking ecosystem-clone-statistics setup...\n")
    
    checks = [
        ("Dependencies", check_dependencies()),
        ("GitHub Token", check_token()),
        ("Ecosystem Access", check_ecosystem_access()),
        ("File Structure", check_directory_structure()),
    ]
    
    print("\n" + "="*50)
    all_passed = all(result for _, result in checks)
    
    if all_passed:
        print(" All checks passed! You're ready to go!")
        print("\nNext steps:")
        print("1. Make sure you've added STATS_TOKEN secret in GitHub repo settings")
        print("2. Push this code to GitHub")
        print("3. Enable GitHub Actions in the repo")
        print("4. The workflow will run automatically at midnight UTC")
        print("\nTo test manually: python collect_stats.py")
    else:
        print("  Some checks failed. Please fix the issues above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
