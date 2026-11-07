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

## Development

Requires Python 3.8 or newer and Git. The hook has no runtime dependencies.

```sh
python -m unittest discover -s tests
python -m pip install . pre-commit
pre-commit validate-manifest .pre-commit-hooks.yaml
```
