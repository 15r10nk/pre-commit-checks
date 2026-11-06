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
repos:
- repo: https://github.com/15r10nk/pre-commit-checks
  rev: v0.1.0
  hooks:
  - id: check-changelog
```

Run against committed changes:

```sh
pre-commit run check-changelog --hook-stage manual --from-ref origin/main --to-ref HEAD
```

The hook uses the manual stage because it needs the complete PR commit range.
It does not run automatically on individual commits. Both refs must be available
locally. In PR CI, check out full history (`fetch-depth: 0`) and use the PR's
base and head SHAs as `--from-ref` and `--to-ref` respectively. Missing or invalid
refs fail the check.

Create a fragment with `uv run scriv create --add --edit` and commit it before
rerunning the check.

## Development

Requires Python 3.8 or newer and Git. The hook has no runtime dependencies.

```sh
python -m unittest discover -s tests
python -m pip install . pre-commit
pre-commit validate-manifest .pre-commit-hooks.yaml
```
