#!/usr/bin/env python3
"""
Sentry Project Bootstrapper

Creates a Sentry project and configures DSNs for the dashboard and agents.

Usage:
  python3 scripts/setup_sentry.py --org <org> --token <auth-token>
  
If you don't have a Sentry account:
  1. Sign up at https://sentry.io/signup/
  2. Create an organization
  3. Generate an auth token at https://sentry.io/settings/account/api/auth-tokens/
     (needs: project:write, project:admin)
  4. Run this script with your org slug and token
"""
import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse


SENTRY_API = "https://sentry.io/api/0/"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)


def api_request(method, path, token, data=None):
    url = f"{SENTRY_API}{path.lstrip('/')}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  ❌ HTTP {e.code}: {e.read().decode()}")
        return None


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Bootstrap Sentry project")
    parser.add_argument("--org", help="Sentry organization slug")
    parser.add_argument("--token", help="Sentry auth token")
    args = parser.parse_args()

    if not args.org or not args.token:
        print("Usage: python3 scripts/setup_sentry.py --org <org> --token <token>")
        return 1

    token = args.token
    org = args.org

    print(f"Connecting to Sentry org '{org}'...")

    # Verify token by listing projects
    projects = api_request("GET", f"organizations/{org}/projects/", token)
    if projects is None:
        print("  Could not list projects. Check your org slug and token permissions.")
        return 1
    print(f"  Found {len(projects)} existing project(s)")
    for p in projects:
        print(f"    - {p['slug']}")

    # Check if our projects already exist
    agent_project_slug = "timi-pipeline"
    dashboard_project_slug = "timi-dashboard"

    existing_slugs = {p["slug"] for p in projects}

    for slug in [agent_project_slug, dashboard_project_slug]:
        if slug in existing_slugs:
            print(f"\n✅ Project '{slug}' already exists")
            continue

        print(f"\nCreating project '{slug}'...")
        team_slug = org  # default team is org name
        data = {
            "name": slug.replace("-", " ").title(),
            "slug": slug,
            "platform": "python" if "pipeline" in slug else "javascript-nextjs",
        }
        result = api_request("POST", f"teams/{org}/{team_slug}/projects/", token, data)
        if result:
            dsn = result.get("dsn", {}).get("public", "")
            print(f"  ✅ Created! DSN: {dsn}")
        else:
            print(f"  ❌ Failed to create project. Try creating it manually.")
            return 1

    # Get DSNs
    for slug in [agent_project_slug, dashboard_project_slug]:
        result = api_request("GET", f"projects/{org}/{slug}/keys/", token)
        if result and len(result) > 0:
            dsn = result[0].get("dsn", {}).get("public", "")
            print(f"\n{slug} DSN: {dsn}")
        else:
            print(f"\n{slug}: could not retrieve DSN")

    print()
    print("Set these environment variables in your deployment:")
    print(f"  SENTRY_DSN=<agent DSN>")
    print(f"  NEXT_PUBLIC_SENTRY_DSN=<dashboard DSN>")
    print(f"  SENTRY_ENVIRONMENT=production")
    print()
    print("Or update agents/.env and dashboard/.env.local")

    return 0


if __name__ == "__main__":
    sys.exit(main())
