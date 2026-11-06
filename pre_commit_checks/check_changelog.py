"""Require a new Scriv fragment for feature and fix commits in a pull request."""

import os
import re
import subprocess
import sys
from pathlib import PurePosixPath


def git(*args):
    return subprocess.check_output(["git", *args])


def main():
    base = os.environ.get("PRE_COMMIT_FROM_REF")
    head = os.environ.get("PRE_COMMIT_TO_REF")
    if not base or not head:
        print("Pass --from-ref BASE --to-ref HEAD to pre-commit.", file=sys.stderr)
        return 1

    subjects = git("log", "--format=%s", f"{base}..{head}").decode().splitlines()
    if not any(re.match(r"^(feat|fix)(\([^()\r\n]+\))?!?:", s) for s in subjects):
        return 0

    ancestor = git("merge-base", base, head).decode().strip()
    added = git(
        "diff", "--no-renames", "--diff-filter=A", "--name-only", "-z", ancestor, head
    )
    for name in added.decode().split("\0"):
        path = PurePosixPath(name)
        if path.parent == PurePosixPath("changelog.d") and path.suffix == ".md":
            if git("show", f"{head}:{name}").strip():
                return 0

    print(
        "This pull request contains feat: or fix: commits but no new, non-empty "
        "changelog.d/*.md fragment. Run `uv run scriv create --add --edit` "
        "and commit the fragment.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
