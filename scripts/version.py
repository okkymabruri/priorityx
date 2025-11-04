#!/usr/bin/env python3
"""Simple version management for priorityx."""

import re
import subprocess
import sys
from pathlib import Path


def get_current_version():
    """Read version from pyproject.toml."""
    pyproject = Path("pyproject.toml").read_text()
    match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    if not match:
        sys.exit("Error: version not found in pyproject.toml")
    return match.group(1)


def bump_version(version, part):
    """Bump version number."""
    major, minor, patch = map(int, version.split("."))

    if part == "major":
        return f"{major + 1}.0.0"
    elif part == "minor":
        return f"{major}.{minor + 1}.0"
    else:  # patch
        return f"{major}.{minor}.{patch + 1}"


def update_version_file(new_version):
    """Update version in pyproject.toml."""
    pyproject_path = Path("pyproject.toml")
    content = pyproject_path.read_text()

    # update version line
    new_content = re.sub(
        r'^version\s*=\s*"[^"]+"',
        f'version = "{new_version}"',
        content,
        flags=re.MULTILINE
    )

    pyproject_path.write_text(new_content)
    print(f"Updated pyproject.toml to v{new_version}")


def git_tag_and_push(version):
    """Create git tag and push."""
    tag = f"v{version}"

    # check if tag exists
    result = subprocess.run(
        ["git", "tag", "-l", tag],
        capture_output=True,
        text=True
    )

    if result.stdout.strip():
        print(f"Tag {tag} already exists")
        return

    # create tag
    subprocess.run(["git", "tag", tag], check=True)
    print(f"Created tag {tag}")

    # push
    response = input(f"Push tag {tag} to remote? (y/n): ")
    if response.lower() == "y":
        subprocess.run(["git", "push", "origin", tag], check=True)
        print(f"Pushed {tag}")


def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: python version.py release [--major|--minor|VERSION]")

    if sys.argv[1] != "release":
        sys.exit("Only 'release' command supported")

    current = get_current_version()
    print(f"Current version: {current}")

    # determine new version
    if len(sys.argv) == 2:
        # patch by default
        new_version = bump_version(current, "patch")
    elif sys.argv[2] == "--major":
        new_version = bump_version(current, "major")
    elif sys.argv[2] == "--minor":
        new_version = bump_version(current, "minor")
    else:
        # explicit version
        new_version = sys.argv[2]

    print(f"New version: {new_version}")

    # confirm
    response = input("Continue? (y/n): ")
    if response.lower() != "y":
        print("Cancelled")
        return

    # update files
    update_version_file(new_version)

    # git tag
    git_tag_and_push(new_version)

    print(f"\nDone! Version {new_version} ready.")
    print(f"Next: git push to trigger release workflow")


if __name__ == "__main__":
    main()
