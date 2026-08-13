#!/usr/bin/env bash
# Version-computation logic for packaging/build-{deb,rpm}.sh, copied from
# multilang-lib's own scripts/compute-version.sh (same author, same
# convention) since this repo is a single Python package rather than a
# multi-language monorepo.
#
# Every commit gets a buildable package, not just tagged releases:
#   - HEAD is an exact git tag  -> that tag is a "release"; use it verbatim.
#   - otherwise                 -> <latest reachable tag, or the caller's
#                                   fallback version if no tag exists yet>
#                                   plus today's UTC date, so untagged
#                                   builds are still uniquely identifiable
#                                   and sort after the base version.
#
# Usage: compute-version.sh <deb|rpm> <fallback-version>
#
# <fallback-version> is whatever pyproject.toml's own version says.
#
# The date separator differs by package format: Debian's Version field
# allows `+`; RPM's does not -- `^` is what modern rpm (>=4.15) treats as
# "newer than the release it's attached to", which is exactly the
# semantics an unreleased dated build needs.
set -euo pipefail

FORMAT="${1:?usage: compute-version.sh <deb|rpm> <fallback-version>}"
FALLBACK_VERSION="${2:?usage: compute-version.sh <deb|rpm> <fallback-version>}"
TODAY="$(date -u +%Y%m%d)"

BASE_VERSION=""
IS_RELEASE=0

if git rev-parse --git-dir >/dev/null 2>&1; then
    if TAG="$(git describe --tags --exact-match 2>/dev/null)"; then
        BASE_VERSION="${TAG#v}"
        IS_RELEASE=1
    elif TAG="$(git describe --tags --abbrev=0 2>/dev/null)"; then
        BASE_VERSION="${TAG#v}"
    fi
fi

if [ -z "$BASE_VERSION" ]; then
    BASE_VERSION="$FALLBACK_VERSION"
fi

if [ "$IS_RELEASE" -eq 1 ]; then
    echo "$BASE_VERSION"
    exit 0
fi

case "$FORMAT" in
    deb) echo "${BASE_VERSION}+${TODAY}" ;;
    rpm) echo "${BASE_VERSION}^${TODAY}" ;;
    *)
        echo "error: unknown format '$FORMAT' (expected 'deb' or 'rpm')" >&2
        exit 1
        ;;
esac
