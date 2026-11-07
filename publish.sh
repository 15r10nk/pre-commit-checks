#!/bin/sh
set -eu

cd "$(dirname "$0")"

if test -n "$(git status --porcelain)"; then
    echo "Working tree is not clean" >&2
    exit 1
fi

python -m unittest discover -s tests
uvx prek run --all-files
uvx prek run check-changelog --stage manual

next_version="$(uvx --from commitizen cz bump --get-next --yes)"
tag="v$next_version"
remote_tag="$(git ls-remote --tags origin "refs/tags/$tag")"
if test -n "$(git tag --list "$tag")" || test -n "$remote_tag"; then
    echo "Release tag already exists: $tag" >&2
    exit 1
fi

uvx --from scriv scriv collect --version "$next_version" --no-edit
uvx --from commitizen cz bump "$next_version" --yes --version-files-only
uvx prek run --all-files || uvx prek run --all-files

git add -- pyproject.toml CHANGELOG.md changelog.d
git commit -m "chore: release $tag"
git tag --annotate "$tag" --message "Release $tag"
# Fragments were validated before being collected into CHANGELOG.md.
SKIP="${SKIP:+$SKIP,}check-changelog" git push --atomic origin HEAD "$tag"
