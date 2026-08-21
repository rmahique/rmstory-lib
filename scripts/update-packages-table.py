#!/usr/bin/env python3
"""
Regenerates the "Latest packages" table in README.md (between the
<!-- PACKAGES_TABLE_START --> / <!-- PACKAGES_TABLE_END --> markers) from
one release's uploaded assets. Run by .github/workflows/release.yml right
after the GitHub Release is published, so the table can never drift from
what's actually attached to the release -- there's deliberately no way to
hand-edit those rows and have them stick.

Usage: update-packages-table.py <release-assets-dir> <tag> <repo>

    <release-assets-dir>: the flattened, combo-prefixed directory
        release.yml's own "Prefix each file with its combo name" step
        already builds -- filenames look like
        "debian-bookworm-python3-rmstory_0.1.0-1_all.deb".
    <tag>: the release tag (e.g. "1.0"). Also the version string for
        every package in the release: release.yml only ever runs from an
        exact tag, and compute-version.sh's IS_RELEASE branch (see that
        script) uses the tag verbatim, with no date suffix, for exactly
        that case.
    <repo>: "owner/name", for building each asset's download URL.
"""

import re
import sys
from pathlib import Path

_START = "<!-- PACKAGES_TABLE_START -->"
_END = "<!-- PACKAGES_TABLE_END -->"

# combo name (build-packages.yml's matrix) -> (display name, installable
# asset suffix). Matched by prefix against release-assets' combo-prefixed
# filenames -- deliberately excludes .sha512 checksums and RPM's
# .src.rpm source package, neither of which a user installs directly.
_COMBOS = [
    ("debian-bookworm", "Debian 12 (bookworm)", ".deb"),
    ("fedora-latest", "Fedora (latest)", ".noarch.rpm"),
    ("opensuse-tumbleweed", "openSUSE Tumbleweed", ".noarch.rpm"),
    ("opensuse-leap-16", "openSUSE Leap 16", ".noarch.rpm"),
    ("sles-15-sp7", "SLES 15 SP7", ".noarch.rpm"),
]


def _find_asset(assets, combo, suffix):
    return next(
        (
            a
            for a in assets
            if a.name.startswith(combo + "-") and a.name.endswith(suffix) and ".src.rpm" not in a.name
        ),
        None,
    )


def build_table(assets_dir, tag, repo):
    assets = sorted(Path(assets_dir).iterdir())

    rows = []
    for combo, display, suffix in _COMBOS:
        asset = _find_asset(assets, combo, suffix)
        if asset is None:
            continue
        url = "https://github.com/{}/releases/download/{}/{}".format(repo, tag, asset.name)
        rows.append("| {} | {} | [{}]({}) |".format(display, tag, asset.name, url))

    if not rows:
        raise SystemExit("no installable package assets found in {}".format(assets_dir))

    header = "| Distribution | Version | Package |\n| --- | --- | --- |"
    return "\n".join([header, *rows])


def update_readme(readme_path, table):
    text = readme_path.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(_START) + r".*?" + re.escape(_END), re.DOTALL)
    if not pattern.search(text):
        raise SystemExit("{} is missing the {} / {} markers".format(readme_path, _START, _END))

    replacement = "{}\n{}\n{}".format(_START, table, _END)
    readme_path.write_text(pattern.sub(replacement, text), encoding="utf-8")


def main():
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    assets_dir, tag, repo = sys.argv[1:4]

    table = build_table(assets_dir, tag, repo)
    update_readme(Path("README.md"), table)


if __name__ == "__main__":
    main()
