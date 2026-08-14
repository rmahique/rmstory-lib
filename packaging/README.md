# Packaging

Native packages for Debian/Ubuntu and RHEL/Fedora.
Each build must run **inside a container for the actual target distro**
— package macros, dependency names, and Python versions are
distro-specific, so building on an unrelated host is not representative.
`docker/` has a Dockerfile per distro with every build dependency baked
in (this is what `.github/workflows/build-packages.yml` builds and runs
in CI — same image, same commands, locally or in CI).

| Family | Script | Spec/control files | Dockerfile |
|---|---|---|---|
| Debian, Ubuntu | `build-deb.sh` | `debian/` | `docker/Dockerfile.debian-bookworm` |
| RHEL, CentOS Stream, Fedora | `build-rpm.sh` | `rpm/rmstory.spec` | `docker/Dockerfile.fedora-latest` |
| openSUSE Tumbleweed | `build-rpm.sh` | `rpm/rmstory.spec` (`%if 0%{?suse_version}` branch) | `docker/Dockerfile.opensuse-tumbleweed` |
| openSUSE Leap 16 | `RMSTORY_LEAP_VERSIONED_PYTHON=1 build-rpm.sh` | `rpm/rmstory.spec` (same branch, `leap_versioned_python`-guarded) | `docker/Dockerfile.opensuse-leap-16` |

## openSUSE Leap 15 is not supported (Leap 16 is)

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
version and passes it explicitly via `--define "leap_pyver ..."`,
gated by `--define "leap_versioned_python 1"` (set only by the Leap 16
CI job / `RMSTORY_LEAP_VERSIONED_PYTHON=1`) — see `rpm/rmstory.spec`'s
comment on `leap_versioned_python` for the full mechanism. Computed, not
hardcoded, so a future Leap 16.x point release shipping a newer default
python3 doesn't silently break this.

## multilang-lib isn't baked into the build images

Every built package's `Depends`/`Requires` lists `python3-multilang`.
multilang-lib publishes its own package per distro as a release asset
(https://github.com/rmahique/multilang-lib/releases), but not for
openSUSE Leap 16 yet, and none of it is baked into `docker/`'s build
images. `debian/rules` and `rpm/rmstory.spec`'s `%check` run the test
suite if `multilang` is importable, otherwise skip with a message —
verified both ways: a build with multilang unavailable skips tests and
still produces a working package; the package's own payload runs
correctly once multilang is installed alongside it.

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
podman run --rm -e RMSTORY_LEAP_VERSIONED_PYTHON=1 \
  -v "$(pwd)/..":/workspace -w /workspace/rmstory-lib rmstory-python-leap16 packaging/build-rpm.sh
```

The `RMSTORY_LEAP_VERSIONED_PYTHON=1` env var is required here (only
here, not Tumbleweed) — see "openSUSE Leap 15 is not supported (Leap 16
is)" above for why.

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
