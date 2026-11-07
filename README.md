# pre-commit-checks

Shared [pre-commit](https://pre-commit.com/) hooks for Python projects.

## check-changelog

Require at least one new, non-empty `changelog.d/*.md` Scriv fragment when a
pull request contains `feat:` or `fix:` commits. Scopes and breaking-change
markers are supported, for example `feat(cli):` and `fix!:`.

The check inspects all commits unique to the pull request and compares its head
with the merge base of the supplied refs. A fragment can be added in a separate
commit. Existing, modified, deleted, empty, or uncommitted fragments do not
satisfy the check. Other commit types do not require a fragment.

Add this to `.pre-commit-config.yaml`:

```yaml
default_install_hook_types: [pre-commit, pre-push]

repos:
- repo: https://github.com/15r10nk/pre-commit-checks
  rev: v0.1.0
  hooks:
  - id: check-changelog
```

Install the hooks once with `pre-commit install`. The changelog check then runs
automatically before `git push`, allowing the fragment to be added in a separate
commit before pushing. It checks the whole branch, including commits from
previous pushes, and only accepts committed fragments.

Run manually without specifying refs:

```sh
pre-commit run check-changelog --hook-stage manual
```

The base branch is detected from `origin/HEAD`, then `origin/main`,
`origin/master`, `main`, or `master`. Keep remote references up to date with
`git fetch`; the hook does not access the network. To override the default,
configure `args: [--base-ref, YOUR_BASE_BRANCH]` on the hook.

In PR CI, check out full history (`fetch-depth: 0`) and pass the PR's exact
base and head SHAs as `--from-ref` and `--to-ref`. Explicit refs take precedence
in manual mode; both must be provided. During a push, the hook uses the pushed
head and the detected base branch, because the push range alone would miss
feature commits from earlier pushes. Missing base branches or invalid refs fail
with an actionable message.

Create a fragment with `uv run scriv create --add --edit` and commit it before
rerunning the check.

## check-tracked-ignored

Reject files that are still in the Git index but match the repository's
`.gitignore` rules. This catches files that were tracked before an ignore rule
was added, including unchanged files outside the current commit's file list.

```yaml
repos:
- repo: https://github.com/15r10nk/pre-commit-checks
  rev: v0.1.0
  hooks:
  - id: check-tracked-ignored
```

The hook runs on commits, pushes, and manual runs. It checks the entire index,
including newly staged files, and works without commit history. Rules in nested
`.gitignore` files and negated patterns are handled by Git itself. Global ignore
files and `.git/info/exclude` are intentionally excluded so results are the same
locally and in CI. There are no hard-coded filename exemptions.

The check only reports problems; it never deletes files or modifies the index.
To stop tracking a file while keeping the local copy, run
`git rm --cached -- <path>` and commit the removal. Alternatively, update the
repository ignore rules to allow deliberately tracked files.

Run it with `prek run check-tracked-ignored --all-files` or
`pre-commit run check-tracked-ignored --all-files`. During an ordinary commit,
the runner stashes unstaged changes so the checked `.gitignore` files match
what is being committed. An explicit `--all-files` run uses the ignore files
currently in the working tree. Old commits and historical file contents are
not inspected or changed.

## Development

Requires Python 3.8 or newer and Git. The hooks have no runtime dependencies.

```sh
python -m unittest discover -s tests
python -m pip install . pre-commit
pre-commit validate-manifest .pre-commit-hooks.yaml
```

## Releases

Install hooks with `uvx prek install`. Run `uvx prek run --all-files` and
`python -m unittest discover -s tests` locally.
Add fragments with `uvx scriv create --add --edit`.

From a clean working tree, `./publish.sh` derives the next semantic version from
Conventional Commits, collects Scriv fragments into CHANGELOG.md, updates the
package version, validates formatting, commits and tags the release, and pushes
the commit and tag atomically to origin. For 0.x versions, features bump the
minor version and fixes bump the patch version.
If preparation fails, inspect the local changes before retrying. A failed push
keeps the local release commit and tag; retry the atomic push after fixing it.
