#!/usr/bin/env python
"""
Script to prepare project for Git - checks for sensitive files.
"""
import os
from pathlib import Path

def check_sensitive_files():
    """Check for sensitive files that shouldn't be committed."""
    project_root = Path(__file__).parent.parent
    
    sensitive_files = [
        '.env',
        'logs/',
        'venv/',
        '__pycache__/',
    ]
    
    issues = []
    
    # Check .env
    env_file = project_root / '.env'
    if env_file.exists():
        # Check if .env is in .gitignore
        gitignore = project_root / '.gitignore'
        if gitignore.exists():
            gitignore_content = gitignore.read_text()
            if '.env' not in gitignore_content:
                issues.append("⚠️  .env file exists but not in .gitignore!")
            else:
                print("✅ .env is in .gitignore")
        else:
            issues.append("⚠️  .gitignore file not found!")
    
    # Check if .env.example exists
    env_example = project_root / '.env.example'
    if not env_example.exists():
        issues.append("⚠️  .env.example not found (should be in repository)")
    else:
        print("✅ .env.example exists")
    
    # Check for secrets in code
    code_files = [
        'config.py',
        'main.py',
    ]
    
    for code_file in code_files:
        file_path = project_root / code_file
        if file_path.exists():
            content = file_path.read_text()
            if 'your_bot_token' in content or 'TELEGRAM_BOT_TOKEN' in content:
                # Check if it's just a placeholder
                if 'your_bot_token' in content.lower():
                    print(f"✅ {code_file} uses placeholder values")
                else:
                    # Check if real token might be there
                    if len([line for line in content.split('\n') if 'TELEGRAM_BOT_TOKEN' in line and 'your' not in line.lower()]) > 0:
                        issues.append(f"⚠️  {code_file} might contain real token - check manually")
    
    print("\n" + "=" * 50)
    if issues:
        print("⚠️  ISSUES FOUND:")
        for issue in issues:
            print(f"  {issue}")
        print("\n❌ DO NOT COMMIT until these are fixed!")
    else:
        print("✅ All checks passed! Safe to commit.")
    print("=" * 50)
    
    return len(issues) == 0


if __name__ == "__main__":
    check_sensitive_files()
