"""Require a new Scriv fragment for feature and fix commits on a branch."""

import argparse
import os
import re
import subprocess
import sys
from pathlib import PurePosixPath


def git(*args):
    return subprocess.check_output(["git", *args], stderr=subprocess.PIPE)


def default_base():
    try:
        remote_head = (
            git("symbolic-ref", "--quiet", "refs/remotes/origin/HEAD").decode().strip()
        )
    except subprocess.CalledProcessError:
        remote_head = None

    candidates = [remote_head, "origin/main", "origin/master", "main", "master"]
    for ref in candidates:
        if ref is None:
            continue
        try:
            git("rev-parse", "--verify", f"{ref}^{{commit}}")
        except subprocess.CalledProcessError:
            continue
        return ref
    raise ValueError(
        "Cannot determine the base branch. Fetch the default branch or configure "
        "args: [--base-ref, YOUR_BASE_BRANCH] for check-changelog."
    )


def check(base, head):
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
        "This branch contains feat: or fix: commits but no new, non-empty "
        "changelog.d/*.md fragment. Run `uv run scriv create --add --edit` "
        "and commit the fragment.",
        file=sys.stderr,
    )
    return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", help="Override automatic base branch detection")
    args = parser.parse_args()
    try:
        base = os.environ.get("PRE_COMMIT_FROM_REF")
        head = os.environ.get("PRE_COMMIT_TO_REF")
        if os.environ.get("PRE_COMMIT_REMOTE_NAME"):
            # A push range only covers the latest push, not the whole branch.
            # Still use its head: users can push a branch other than HEAD.
            base = args.base_ref or default_base()
            head = head or "HEAD"
        elif base is not None or head is not None:
            if not base or not head:
                raise ValueError(
                    "Both PRE_COMMIT_FROM_REF and PRE_COMMIT_TO_REF must be set."
                )
        else:
            base = args.base_ref or default_base()
            head = "HEAD"
        return check(base, head)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as error:
        print(error.stderr.decode().strip(), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
