import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "pre_commit_checks/check_changelog.py"


class GitRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.git("init", "--initial-branch=main")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.com")
        self.write("changelog.d/existing.md", "Existing fragment\n")
        self.write("changelog.d/.gitignore", "!.gitignore\n")
        self.commit("chore: initial")
        self.base = self.git("rev-parse", "HEAD").strip()

    def git(self, *args):
        return subprocess.check_output(
            ["git", *args], cwd=self.root, stderr=subprocess.PIPE, text=True
        )

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def commit(self, message):
        self.git("add", "--all")
        self.git("commit", "--allow-empty", "-m", message)

    def check(self, expected, base=None):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=self.root,
            env={
                **os.environ,
                "PRE_COMMIT_FROM_REF": self.base if base is None else base,
                "PRE_COMMIT_TO_REF": "HEAD",
            },
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result


class ChangelogTests(GitRepositoryTest):
    def test_feature_and_fix_forms_require_fragment(self):
        for message in (
            "feat: feature",
            "fix: bug",
            "feat(cli): feature",
            "fix(cli)!: breaking fix",
            "feat!: breaking feature",
        ):
            with self.subTest(message=message):
                self.git("reset", "--hard", self.base)
                self.commit(message)
                result = self.check(1)
                self.assertIn("uv run scriv create --add --edit", result.stderr)

    def test_other_commit_types_do_not_require_fragment(self):
        for message in (
            "docs: document feat: commits",
            "refactor: simplify",
            "chore: release v1.0.0",
            "ci: update workflow",
        ):
            self.commit(message)
        self.check(0)

    def test_fragment_in_later_commit_is_accepted(self):
        self.commit("feat: feature")
        self.write("changelog.d/new.md", "### Added\n\nA feature.\n")
        self.commit("docs: describe feature")
        self.check(0)

    def test_modified_existing_fragment_is_insufficient(self):
        self.write("changelog.d/existing.md", "Updated fragment\n")
        self.commit("fix: bug")
        self.check(1)

    def test_empty_or_unrelated_files_are_insufficient(self):
        self.write("changelog.d/empty.md", " \n\t")
        self.write("changelog.d/new.txt", "Some text")
        self.write("changelog.d/.gitignore", "# updated\n")
        self.write("docs/new.md", "Documentation")
        self.commit("fix: bug")
        self.check(1)

    def test_uncommitted_fragment_is_insufficient(self):
        self.commit("fix: bug")
        self.write("changelog.d/new.md", "Bug fix\n")
        self.check(1)

    def test_deleted_fragment_is_insufficient(self):
        self.write("changelog.d/new.md", "Feature\n")
        self.commit("feat: feature")
        (self.root / "changelog.d/new.md").unlink()
        self.commit("chore: remove fragment")
        self.check(1)

    def test_base_branch_commits_are_not_checked(self):
        self.git("checkout", "-b", "feature")
        self.commit("docs: document feature")
        self.git("checkout", "main")
        self.commit("feat: unrelated main feature")
        base = self.git("rev-parse", "HEAD").strip()
        self.git("checkout", "feature")
        self.check(0, base=base)

    def test_fragment_on_diverged_branch_is_accepted(self):
        self.git("checkout", "-b", "feature")
        self.write("changelog.d/new.md", "Feature\n")
        self.commit("feat: feature")
        self.git("checkout", "main")
        self.write("changelog.d/main.md", "Unrelated fix\n")
        self.commit("fix: unrelated main fix")
        base = self.git("rev-parse", "HEAD").strip()
        self.git("checkout", "feature")
        self.check(0, base=base)

    def test_missing_refs_fail_with_instructions(self):
        result = self.check(1, base="")
        self.assertIn("Both PRE_COMMIT_FROM_REF and PRE_COMMIT_TO_REF", result.stderr)

    def test_invalid_ref_fails(self):
        self.check(1, base="missing-ref")


class AutomaticBaseTests(GitRepositoryTest):
    def setUp(self):
        super().setUp()
        self.git("checkout", "-b", "feature")

    def automatic_check(self, expected, args=(), env=None):
        environment = dict(os.environ)
        for name in (
            "PRE_COMMIT_FROM_REF",
            "PRE_COMMIT_TO_REF",
            "PRE_COMMIT_REMOTE_NAME",
        ):
            environment.pop(name, None)
        environment.update(env or {})
        result = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=self.root,
            env=environment,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def test_detects_local_main_without_refs(self):
        self.commit("feat: feature")
        self.automatic_check(1)
        self.write("changelog.d/new.md", "Feature\n")
        self.commit("docs: changelog")
        self.automatic_check(0)

    def test_prefers_remote_default_branch(self):
        self.git("update-ref", "refs/remotes/origin/trunk", self.base)
        self.git(
            "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/trunk"
        )
        self.git("checkout", "main")
        self.commit("feat: unrelated main change")
        self.git("checkout", "feature")
        self.commit("docs: feature documentation")
        self.automatic_check(0)

    def test_detects_origin_main(self):
        self.git("update-ref", "refs/remotes/origin/main", self.base)
        self.git("branch", "-D", "main")
        self.commit("fix: bug")
        self.automatic_check(1)

    def test_detects_local_master(self):
        self.git("branch", "-m", "main", "master")
        self.commit("fix: bug")
        self.automatic_check(1)

    def test_configurable_base_branch(self):
        self.git("branch", "-m", "main", "trunk")
        self.commit("fix: bug")
        self.automatic_check(1, args=("--base-ref", "trunk"))
        result = self.automatic_check(1)
        self.assertIn("Cannot determine the base branch", result.stderr)

    def test_uncommitted_fragment_is_not_accepted_automatically(self):
        self.commit("feat: feature")
        self.write("changelog.d/new.md", "Feature\n")
        self.git("add", "changelog.d/new.md")
        self.automatic_check(1)

    def test_push_range_does_not_hide_earlier_feature_commits(self):
        self.commit("feat: feature")
        previous_push = self.git("rev-parse", "HEAD").strip()
        self.commit("docs: more documentation")
        self.automatic_check(
            1,
            env={
                "PRE_COMMIT_REMOTE_NAME": "origin",
                "PRE_COMMIT_FROM_REF": previous_push,
                "PRE_COMMIT_TO_REF": "HEAD",
            },
        )

    def test_push_checks_the_branch_being_pushed(self):
        self.commit("feat: feature")
        pushed_head = self.git("rev-parse", "HEAD").strip()
        self.git("checkout", "main")
        self.automatic_check(
            1,
            env={
                "PRE_COMMIT_REMOTE_NAME": "origin",
                "PRE_COMMIT_FROM_REF": self.base,
                "PRE_COMMIT_TO_REF": pushed_head,
            },
        )
