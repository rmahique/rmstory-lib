#!/usr/bin/env bash
# Build an RPM for RHEL/CentOS/Fedora or openSUSE/SLES.
#
# Must run inside (or targeting) the actual distro you're packaging for —
# a mock chroot, an osc build, or a matching container — not on an
# unrelated host OS, since macro names (python3_sitelib, py3_build) and
# dependency package names differ per distro family.
set -euo pipefail

cd "$(dirname "$0")/.."   # repo root

# Every commit gets a package: compute-version.sh returns the exact tag
# when HEAD is a release, otherwise the latest tag (or pyproject.toml's
# version if no tag exists yet) plus today's date (`^`-separated, since
# RPM's Version field can't contain `+` or `-`).
PYPROJECT_VERSION="$(grep -m1 '^version *= *"' pyproject.toml | sed -E 's/^version *= *"([^"]+)".*/\1/')"
VERSION="$(scripts/compute-version.sh rpm "$PYPROJECT_VERSION")"
if [ -z "$VERSION" ]; then
    echo "error: could not determine version" >&2
    exit 1
fi

# A plain tarball, not `python3 -m build --sdist`: RPM's %prep/%autosetup
# just needs a `rmstory-${VERSION}/` directory inside a .tar.gz, not a
# proper PEP 517 sdist -- and this avoids needing the `build` PyPI module
# (and thus network access, and thus any particular python3 version) at
# all. Every distro family's rpmbuild gets exactly the same tarball this
# way.
mkdir -p dist
STAGING="$(mktemp -d)"
DESTDIR="${STAGING}/rmstory-${VERSION}"
mkdir -p "$DESTDIR"
cp -r rmstory tests pyproject.toml README.md LICENSE "$DESTDIR/"
tar czf "dist/rmstory-${VERSION}.tar.gz" -C "$STAGING" "rmstory-${VERSION}"
rm -rf "$STAGING"

RPMBUILD_ROOT="${HOME}/rpmbuild"
mkdir -p "${RPMBUILD_ROOT}"/{SOURCES,SPECS}
cp "dist/rmstory-${VERSION}.tar.gz" "${RPMBUILD_ROOT}/SOURCES/"
cp packaging/rpm/rmstory.spec "${RPMBUILD_ROOT}/SPECS/"

# --define "_topdir ...": openSUSE/SLES's rpmbuild defaults %_topdir to
# /usr/src/packages instead of ~/rpmbuild (Fedora/RHEL/Debian's default),
# so without this override the build looks for SOURCES/SPECS in the wrong
# place on SUSE. Harmless to set explicitly everywhere else too, since it
# matches what those distros already default to.
#
# --define "version ...": overrides the spec's hardcoded Version: 0.1.0
# so every commit build (not just tagged releases) gets stamped with
# compute-version.sh's output instead of always building 0.1.0-1.
#
# RMSTORY_LEAP_VERSIONED_PYTHON=1 (set by the openSUSE Leap 16 CI job
# only, not by Tumbleweed): Leap 16's default python3 is already current
# (unlike Leap 15's, no alternate-interpreter workaround needed), but its
# -devel/-setuptools/-pip/-pytest/-PyYAML packages are only published
# under a version-specific name (python313-*, not Tumbleweed's plain
# python3-*) -- see rmstory.spec's comment on `leap_versioned_python` for
# the full reasoning. The exact suffix is computed here from whatever
# python3 is actually installed, not hardcoded, so a future Leap 16.x
# point release with a newer default python3 doesn't silently break this.
EXTRA_DEFINES=()
if [ "${RMSTORY_LEAP_VERSIONED_PYTHON:-0}" = "1" ]; then
    LEAP_PYVER="$(python3 -c 'import sys; print(f"{sys.version_info.major}{sys.version_info.minor}")')"
    EXTRA_DEFINES+=(--define "leap_versioned_python 1" --define "leap_pyver ${LEAP_PYVER}")
fi

rpmbuild --define "_topdir ${RPMBUILD_ROOT}" --define "version ${VERSION}" \
    "${EXTRA_DEFINES[@]}" -ba "${RPMBUILD_ROOT}/SPECS/rmstory.spec"

# sha512sum next to each package this run produced, not a combined
# SHA512SUMS -- callers (CI artifact upload, a release page) may only
# want one specific package's checksum, not the whole batch's.
find "${RPMBUILD_ROOT}/RPMS" "${RPMBUILD_ROOT}/SRPMS" -name "*${VERSION}*.rpm" 2>/dev/null | while read -r pkg; do
    sha512sum "$pkg" > "${pkg}.sha512"
done

echo "Build artifacts placed under ${RPMBUILD_ROOT}/RPMS and .../SRPMS (plus matching .sha512 files)."
