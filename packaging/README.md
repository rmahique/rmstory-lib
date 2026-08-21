# Packaging

Native packages for Debian/Ubuntu, RHEL/Fedora, and the SUSE family
(openSUSE Tumbleweed/Leap 16, SLES 15 SP7).
Each build must run **inside a container for the actual target distro**
— package macros, dependency names, and Python versions are
distro-specific, so building on an unrelated host is not representative.
`docker/` has a Dockerfile per distro with every build dependency baked
in (this is what `.github/workflows/build-packages.yml` builds and runs
in CI — same image, same commands, locally or in CI).

Just want a pre-built package, not to build one yourself? See the main
repo's `README.md` `## Details` `### Distro packages` — its "Latest
packages" table always links the current release's actual assets.

| Family | Script | Spec/control files | Dockerfile |
|---|---|---|---|
| Debian, Ubuntu | `build-deb.sh` | `debian/` | `docker/Dockerfile.debian-bookworm` |
| RHEL, CentOS Stream, Fedora | `build-rpm.sh` | `rpm/rmstory.spec` | `docker/Dockerfile.fedora-latest` |
| openSUSE Tumbleweed | `build-rpm.sh` | `rpm/rmstory.spec` (`%if 0%{?suse_version}` branch) | `docker/Dockerfile.opensuse-tumbleweed` |
| openSUSE Leap 16 | `RMSTORY_SUSE_VERSIONED_PYTHON=1 build-rpm.sh` | `rpm/rmstory.spec` (same branch, `suse_versioned_python`-guarded) | `docker/Dockerfile.opensuse-leap-16` |
| SLES 15 SP7 | `RMSTORY_SUSE_PYVER=311 build-rpm.sh` | `rpm/rmstory.spec` (same branch) | `docker/Dockerfile.sles-15-sp7` |

## openSUSE Leap 15 is not supported (Leap 16 and SLES 15 SP7 are)

multilang-lib packages Leap 15 by building against the versioned
`python310` package (Leap 15's *default* python3 is 3.6, too old for
`requires-python >=3.9`) — but that only works because multilang-lib has
**zero** required dependencies. rmstory requires PyYAML at runtime, and
Leap 15's `python310` package family has no `python310-PyYAML` (verified
against the real repo metadata: `python310-devel`/`-setuptools` exist,
`python310-PyYAML` doesn't — the same kind of gap multilang-lib already
documented for `python310-pip`/`-pytest`, just for a package this
project actually needs installed, not an optional build/test tool it can
skip). A package that can't satisfy its own hard runtime dependency on
that target isn't worth shipping, so Leap 15 is dropped rather than
built with a broken `Requires`.

Leap 16 doesn't have this problem the same way — its *default* python3
is already current (3.13, verified), so no alternate-interpreter
workaround is needed there. But it has a *different* quirk: unlike
Tumbleweed's plain `python3-devel`/`-setuptools`/`-pip`/`-pytest`/
`-PyYAML`, Leap 16 only publishes those under the version-specific name
(`python313-*`, verified against the real repo metadata — oddly,
`python3-devel` alone also exists, but the others don't, so all five are
referenced by their versioned name uniformly rather than mixing). RPM's
own `%leap_version` macro returns an unexpanded, unusable value on the
Leap 16 image tested against (`@leap_version@`, literally), so rather
than rely on it, `build-rpm.sh` computes the running python3's actual
version and passes it explicitly via `--define "suse_pyver ..."`,
gated by `--define "suse_versioned_python 1"` (set only by the Leap 16
CI job / `RMSTORY_SUSE_VERSIONED_PYTHON=1`) — see `rpm/rmstory.spec`'s
comment on `suse_versioned_python` for the full mechanism. Computed, not
hardcoded, so a future Leap 16.x point release shipping a newer default
python3 doesn't silently break this.

SLES 15 SP7 is a *third*, different case: its default python3 is 3.6
(same problem as Leap 15) — but unlike Leap 15's `python310`, its own
versioned family, `python311`, genuinely does have `-PyYAML`/`-pytest`/
`-devel`/`-setuptools`/`-pip` (verified against the real repo metadata —
this is exactly the gap that sank Leap 15). So it's supportable, just
not via Leap 16's "derive the version from the container's already-
correct default python3" trick, since SLES 15 SP7 has no correct default
to derive from — its job passes `RMSTORY_SUSE_PYVER=311` explicitly
instead of `RMSTORY_SUSE_VERSIONED_PYTHON=1`. It also needs one more
package Leap 16/Tumbleweed don't: `python311-wheel`, since SLES 15 SP7's
setuptools (67.7.2, verified) predates setuptools bundling `bdist_wheel`
itself (>=70.1) — without it, `pip wheel` fails with "invalid command
'bdist_wheel'" (verified by hitting exactly that failure without it).
And its package-name suffix ("311") and its real interpreter *binary*
name are different strings — `/usr/bin/python3.11` (dotted), not
`/usr/bin/python311` (verified against the real image: no such binary or
package exists, only `python311-base` providing the dotted one) — see
`rpm/rmstory.spec`'s comment on `suse_python` vs. `suse_py_pkg` for how
that's kept straight.

## multilang-lib isn't baked into the build images

Every built package's `Depends`/`Requires` lists `python3-multilang`.
multilang-lib publishes its own package per distro as a release asset
(https://github.com/rmahique/multilang-lib/releases), but not for
openSUSE Leap 16 or SLES 15 SP7 yet, and none of it is baked into
`docker/`'s build images. `debian/rules` and `rpm/rmstory.spec`'s
`%check` run the test suite if `multilang` is importable, otherwise skip
with a message — verified both ways: a build with multilang unavailable
skips tests and still produces a working package; the package's own
payload runs correctly once multilang is installed alongside it. On
SLES 15 SP7 specifically, multilang-lib's own `SQLiteBackend` needs the
stdlib `sqlite3` module, which SLES splits into a separate `python311`
package (distinct from `python311-base`) not otherwise needed by
rmstory itself — install it too if you're testing against a real
multilang-lib on that target (`zypper install python311`).

## Debian / Ubuntu

```bash
podman build -t rmstory-python-deb -f packaging/docker/Dockerfile.debian-bookworm packaging/docker
podman run --rm -v "$(pwd)/..":/workspace -w /workspace/rmstory-lib rmstory-python-deb packaging/build-deb.sh
```

`pybuild-plugin-pyproject` (in the Dockerfile) is required because this
project builds via `pyproject.toml` (PEP 517/setuptools), not a legacy
`setup.py` — without it, `dh_auto_configure` fails with "PEP517 plugin
dependencies are not available."

Resulting `.deb` files land in the parent directory of the repo — so the
directory the repo lives in must be part of what's bind-mounted into the
container, not just the repo itself (a bare `-v "$(pwd)":/workspace/rmstory-lib`
means the build's `../*.deb` output lands in the container's ephemeral
filesystem and is lost when it exits, not on the host).

## RHEL / CentOS Stream / Fedora

```bash
podman build -t rmstory-python-rpm -f packaging/docker/Dockerfile.fedora-latest packaging/docker
podman run --rm -v "$(pwd)/..":/workspace -w /workspace/rmstory-lib rmstory-python-rpm packaging/build-rpm.sh
```

## openSUSE Tumbleweed

```bash
podman build -t rmstory-python-tumbleweed -f packaging/docker/Dockerfile.opensuse-tumbleweed packaging/docker
podman run --rm -v "$(pwd)/..":/workspace -w /workspace/rmstory-lib rmstory-python-tumbleweed packaging/build-rpm.sh
```

Same pip-wheel build mechanism as Fedora's `%pyproject_wheel` would use,
since `pyproject-rpm-macros` isn't reliably available on SUSE either way
— see `rpm/rmstory.spec`'s `%if 0%{?suse_version}` branch.

Resulting RPMs land under `~/rpmbuild/RPMS/noarch/` *inside* the
container, so `build-rpm.sh` alone (without copying them out before the
container exits) isn't enough to get them onto the host — see how
`build-packages.yml`'s `collect:` step chains a `find ... | xargs cp`
into the same `podman run` invocation.

## openSUSE Leap 16

```bash
podman build -t rmstory-python-leap16 -f packaging/docker/Dockerfile.opensuse-leap-16 packaging/docker
podman run --rm -e RMSTORY_SUSE_VERSIONED_PYTHON=1 \
  -v "$(pwd)/..":/workspace -w /workspace/rmstory-lib rmstory-python-leap16 packaging/build-rpm.sh
```

The `RMSTORY_SUSE_VERSIONED_PYTHON=1` env var is required here (only
here, not Tumbleweed) — see "openSUSE Leap 15 is not supported (Leap 16
and SLES 15 SP7 are)" above for why.

## SLES 15 SP7

```bash
podman build -t rmstory-python-sles15sp7 -f packaging/docker/Dockerfile.sles-15-sp7 packaging/docker
podman run --rm -e RMSTORY_SUSE_PYVER=311 \
  -v "$(pwd)/..":/workspace -w /workspace/rmstory-lib rmstory-python-sles15sp7 packaging/build-rpm.sh
```

`RMSTORY_SUSE_PYVER=311` (not `RMSTORY_SUSE_VERSIONED_PYTHON=1`) is
required here — see "openSUSE Leap 15 is not supported (Leap 16 and
SLES 15 SP7 are)" above for why SLES 15 SP7 needs the version pinned
explicitly rather than derived. `registry.suse.com/suse/sle15` pulls
from the public `SLE_BCI` repo, which needs no SUSEConnect
registration/subscription for anything this build uses (verified by
pulling and building anonymously).

## Before a real release

- For a signed/repo-distributed build, use `mock` (RPM) or `sbuild`/`pbuilder`
  (Debian) instead of a bare `podman run`, and go through your normal
  OBS/COPR/PPA signing flow rather than `rpmbuild`/`dpkg-buildpackage`
  directly.
- multilang-lib's packages are release assets, not a live apt/zypper
  repo, so `docker/`'s build images still can't `apt install
  python3-multilang` directly. Once it has a real repo, point these
  images at it and drop the `%check`/`dh_auto_test` skip. Until then,
  fetch the matching release asset into the build image if you want
  tests to actually run — never check out multilang-lib's source.
