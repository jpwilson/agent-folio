#!/usr/bin/env python3
"""Generate static/changelog.json from git log + manual overrides.

Usage:
    python scripts/generate_changelog.py

Workflow:
    1. Curate rich descriptions in scripts/changelog_overrides.json
    2. Run this script to regenerate static/changelog.json
    3. Commit the updated JSON file
    CI will verify the file is up to date.
"""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OVERRIDES_PATH = ROOT / "scripts" / "changelog_overrides.json"
OUTPUT_PATH = ROOT / "static" / "changelog.json"


def get_git_entries() -> list[dict]:
    """Parse git log into changelog entry dicts."""
    result = subprocess.run(
        ["git", "log", "--format=%h|%ai|%s", "--no-merges"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    entries = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("|", 2)
        if len(parts) < 3:
            continue
        short_hash, date_str, title = parts
        entries.append(
            {
                "date": date_str.strip()[:10],
                "title": title.strip(),
                "desc": title.strip(),
                "commit": short_hash.strip(),
                "repo": "agent-folio",
            }
        )
    return entries


def load_overrides() -> dict:
    """Load curated overrides and skip list."""
    if OVERRIDES_PATH.exists():
        with open(OVERRIDES_PATH) as f:
            return json.load(f)
    return {"entries": [], "skip_commits": [], "repos": {}}


def main():
    git_entries = get_git_entries()
    overrides = load_overrides()

    # Build lookup of override entries by commit hash
    override_by_commit: dict[str, list[dict]] = {}
    manual_entries = []
    for entry in overrides.get("entries", []):
        commit = entry.get("commit", "")
        if commit:
            override_by_commit.setdefault(commit, []).append(entry)
        else:
            manual_entries.append(entry)

    skip = set(overrides.get("skip_commits", []))
    repos = overrides.get("repos", {})

    merged = []
    seen_commits = set()

    for entry in git_entries:
        h = entry["commit"]
        if h in skip:
            continue
        if h in override_by_commit:
            if h not in seen_commits:
                merged.extend(override_by_commit[h])
                seen_commits.add(h)
        else:
            merged.append(entry)

    # Add manual entries (no commit hash)
    merged.extend(manual_entries)

    # Sort by date descending, then by title for stable ordering within same date
    merged.sort(key=lambda e: (e["date"], e.get("title", "")), reverse=True)

    output = {"entries": merged, "repos": repos}
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Generated {len(merged)} changelog entries -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
