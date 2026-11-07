"""Reject tracked files that match repository .gitignore rules."""

import os
import subprocess
import sys


def main():
    try:
        root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], stderr=subprocess.PIPE
        ).rstrip(b"\n")
        ignored = subprocess.check_output(
            [
                "git",
                "ls-files",
                "--cached",
                "--ignored",
                "--exclude-per-directory=.gitignore",
                "--full-name",
                "-z",
            ],
            cwd=os.fsdecode(root),
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as error:
        print(
            "Cannot check tracked files: "
            + error.stderr.decode(errors="replace").strip(),
            file=sys.stderr,
        )
        return 2
    except OSError as error:
        print(f"Cannot check tracked files: {error}", file=sys.stderr)
        return 2

    paths = sorted(set(ignored.split(b"\0")) - {b""})
    if not paths:
        return 0

    print("Tracked files match repository .gitignore rules:", file=sys.stderr)
    for path in paths:
        print(f"  {os.fsdecode(path)!r}", file=sys.stderr)
    print(
        "Remove them from tracking with `git rm --cached -- <path>` and commit "
        "the removal, or adjust the .gitignore rules to keep them tracked.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
