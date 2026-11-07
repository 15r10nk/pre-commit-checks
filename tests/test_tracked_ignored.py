import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_changelog import GitRepositoryTest

SCRIPT = (
    Path(__file__).resolve().parents[1] / "pre_commit_checks/check_tracked_ignored.py"
)


class TrackedIgnoredTests(GitRepositoryTest):
    def check(self, expected, cwd=None):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=self.root if cwd is None else cwd,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def test_clean_index_passes(self):
        self.check(0)

    def test_new_ignore_rule_catches_unchanged_tracked_file(self):
        self.write("cache.tmp", "keep this local data\n")
        self.commit("chore: add file")
        self.write(".gitignore", "*.tmp\n")
        self.git("add", ".gitignore")
        before = self.git("diff", "--cached", "--name-status")
        result = self.check(1)
        self.assertIn("cache.tmp", result.stderr)
        self.assertIn("git rm --cached", result.stderr)
        self.assertEqual(self.git("diff", "--cached", "--name-status"), before)
        self.assertEqual(
            (self.root / "cache.tmp").read_text(), "keep this local data\n"
        )

    def test_forced_staged_file_is_checked_before_first_commit(self):
        self.write(".gitignore", "*.tmp\n")
        self.write("new.tmp", "data")
        self.git("add", ".gitignore")
        self.git("add", "--force", "new.tmp")
        result = self.check(1)
        self.assertIn("new.tmp", result.stderr)

    def test_untracked_ignored_files_are_allowed(self):
        self.write(".gitignore", "*.tmp\n")
        self.write("untracked.tmp", "data")
        self.git("add", ".gitignore")
        self.check(0)

    def test_staged_removal_resolves_problem_and_keeps_local_file(self):
        self.write("cache.tmp", "data")
        self.commit("chore: add file")
        self.write(".gitignore", "*.tmp\n")
        self.git("add", ".gitignore")
        self.git("rm", "--cached", "--", "cache.tmp")
        self.check(0)
        self.assertTrue((self.root / "cache.tmp").exists())

    def test_nested_ignore_and_negation(self):
        self.write(".gitignore", "*.log\n")
        self.write("logs/.gitignore", "!keep.log\n")
        self.write("logs/keep.log", "fixture")
        self.git("add", ".gitignore", "logs/.gitignore", "logs/keep.log")
        self.check(0)
        self.write("logs/drop.log", "generated")
        self.git("add", "--force", "logs/drop.log")
        result = self.check(1)
        self.assertIn("logs/drop.log", result.stderr)
        self.assertNotIn("logs/keep.log", result.stderr)

    def test_nested_directory_pattern(self):
        self.write("nested/.gitignore", "cache/\n")
        self.write("nested/cache/data.txt", "data")
        self.write("cache/data.txt", "tracked fixture")
        self.git("add", "nested/.gitignore", "cache/data.txt")
        self.git("add", "--force", "nested/cache/data.txt")
        result = self.check(1)
        self.assertIn("'nested/cache/data.txt'", result.stderr)
        self.assertNotIn("  'cache/data.txt'", result.stderr)

    def test_personal_ignore_rules_do_not_affect_result(self):
        self.write("personal.tmp", "data")
        self.write("local.tmp", "data")
        self.git("add", "personal.tmp", "local.tmp")
        with tempfile.TemporaryDirectory() as directory:
            global_ignore = Path(directory) / "ignore"
            global_ignore.write_text("personal.tmp\n")
            self.git("config", "core.excludesFile", str(global_ignore))
            (self.root / ".git/info/exclude").write_text("local.tmp\n")
            self.check(0)

    def test_subdirectory_invocation_checks_whole_repository(self):
        self.write("cache.tmp", "data")
        self.commit("chore: add file")
        self.write(".gitignore", "*.tmp\n")
        subdirectory = self.root / "nested"
        subdirectory.mkdir()
        result = self.check(1, cwd=subdirectory)
        self.assertIn("cache.tmp", result.stderr)

    def test_file_missing_from_working_tree_is_still_checked(self):
        self.write("cache.tmp", "data")
        self.commit("chore: add file")
        (self.root / "cache.tmp").unlink()
        self.write(".gitignore", "*.tmp\n")
        self.check(1)

    def test_gitignore_itself_has_no_implicit_exemption(self):
        self.write(".gitignore", ".*\n")
        self.git("add", "--force", ".gitignore")
        result = self.check(1)
        self.assertIn("'.gitignore'", result.stderr)

    def test_special_filenames_are_not_split(self):
        names = ["with spaces.tmp", "-leading.tmp", "caf\u00e9.tmp"]
        if os.name != "nt":
            names.extend(['quote"name.tmp', "line\nbreak.tmp", "back\\slash.tmp"])
        self.write(".gitignore", "*.tmp\n")
        for name in names:
            self.write(name, "data")
            self.git("add", "--force", "--", name)
        result = self.check(1)
        for name in names:
            self.assertIn(repr(name), result.stderr)

    def test_failure_outside_git_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.check(2, cwd=directory)
        self.assertIn("Cannot check tracked files", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_git_index_error_fails_closed(self):
        (self.root / ".git/index").write_bytes(b"invalid index")
        result = self.check(2)
        self.assertIn("Cannot check tracked files", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_shallow_clone_needs_no_base_branch_or_history(self):
        self.write("cache.tmp", "data")
        self.commit("chore: add file")
        self.write(".gitignore", "*.tmp\n")
        self.commit("chore: ignore file")
        with tempfile.TemporaryDirectory() as directory:
            clone = Path(directory) / "clone"
            subprocess.run(
                [
                    "git",
                    "clone",
                    "--quiet",
                    "--depth",
                    "1",
                    self.root.as_uri(),
                    str(clone),
                ],
                check=True,
                capture_output=True,
            )
            shallow = subprocess.check_output(
                ["git", "rev-parse", "--is-shallow-repository"], cwd=clone, text=True
            )
            self.assertEqual(shallow.strip(), "true")
            result = self.check(1, cwd=clone)
            self.assertIn("cache.tmp", result.stderr)
