%global srcname rmstory

# build-rpm.sh passes --define "version ..." (scripts/compute-version.sh's
# output) for every commit build; 0.1.0 here is only a fallback for anyone
# invoking rpmbuild directly against this spec without going through the
# script.
%{!?version: %global version 0.1.0}

Name:           python3-%{srcname}
Version:        %{version}
Release:        1%{?dist}
Summary:        Translate and recombine stories authored as tagged spans

License:        GPL-3.0-or-later
URL:            https://github.com/rmahique/rmstory-lib
Source0:        %{srcname}-%{version}.tar.gz

BuildArch:      noarch

%if 0%{?suse_version}
# openSUSE Tumbleweed, openSUSE Leap 16, and SLES 15 SP7 -- openSUSE Leap
# 15 is deliberately not supported here (unlike multilang-lib, which has
# zero required dependencies and builds fine on every SUSE flavor). This
# project requires PyYAML at runtime, and Leap 15's versioned python310
# package family -- needed since Leap 15's *default* python3 is 3.6, too
# old for requires-python >=3.9 -- has no python310-PyYAML (confirmed
# against the real repo metadata: python310-devel/-setuptools exist,
# python310-PyYAML doesn't, the same gap multilang-lib already documented
# for python310-pip/-pytest). A package that can't satisfy its own hard
# runtime dependency isn't worth shipping, so Leap 15 is skipped rather
# than built with a broken Requires.
#
# Leap 16's *default* python3 is already current (3.13, confirmed), so
# no alternate-interpreter workaround is needed there the way Leap 15
# needed python310 -- but its -devel/-setuptools/-pip/-pytest/-PyYAML
# are only packaged under the version-specific name (python313-*,
# confirmed against the real repo metadata), not the plain python3-*
# names Tumbleweed uses.
#
# SLES 15 SP7 is a different case again: its *default* python3 is 3.6,
# same problem as Leap 15 -- but its own versioned family, python311,
# *does* have -PyYAML/-pytest/-devel/-setuptools/-pip (confirmed against
# the real repo metadata; this is exactly the gap that sank Leap 15's
# python310), so it's supportable, just not via Leap 16's "derive the
# version from whatever the default python3 already is" trick, since
# SLES 15 SP7's default is the wrong (3.6) one.
#
# build-rpm.sh threads this through as %%{suse_pyver} (the bare version
# number, e.g. "313" or "311", used for *package* names) and
# %%{suse_python} (the actual interpreter *binary* to invoke -- NOT just
# "python" + suse_pyver: SUSE's package-name suffix and its real binary
# name are different strings, confirmed against the real image --
# python311-base provides /usr/bin/python3.11, dotted after the major
# version; there's no /usr/bin/python311 at all). Leap 16's job passes
# suse_pyver derived from the container's actual default python3
# (self-updating if a future Leap 16.x point release bumps it) but keeps
# suse_python as plain "python3", since Leap 16's default already *is*
# the right interpreter; SLES 15 SP7's job passes both explicitly
# (RMSTORY_SUSE_PYVER), since there's no correct default to derive
# either from. Tumbleweed sets neither, so both macros default to plain
# "python3" naming/binary. See build-rpm.sh for exactly how each is
# computed.
%{!?suse_pyver: %global suse_pyver 3}
%{!?suse_python: %global suse_python python3}
%if 0%{?suse_versioned_python}
%global suse_py_pkg python%{suse_pyver}
# The real interpreter *package* name (for BuildRequires/Requires) is
# python311-base, not "python3.11" (%%{suse_python}, the *binary* name --
# not a resolvable package/capability on its own) and not "python311"
# either (confirmed against the real image: no such package exists,
# only python311-base, -devel, -setuptools, ...).
%global suse_py_base %{suse_py_pkg}-base
%else
%global suse_py_pkg python3
%global suse_py_base python3
%endif
BuildRequires:  python3
BuildRequires:  %{suse_py_base}
BuildRequires:  %{suse_py_pkg}-devel
BuildRequires:  %{suse_py_pkg}-setuptools
# SLES 15 SP7's setuptools (67.7.2, confirmed) predates setuptools
# bundling `bdist_wheel` itself (>=70.1); without the standalone `wheel`
# package `pip wheel` fails with "invalid command 'bdist_wheel'"
# (confirmed by hitting exactly that failure without it). Harmless on
# Tumbleweed/Leap 16's newer setuptools, which no longer needs it.
BuildRequires:  %{suse_py_pkg}-wheel
BuildRequires:  %{suse_py_pkg}-pip
BuildRequires:  %{suse_py_pkg}-PyYAML
# Still uses the same pip-wheel mechanism as Fedora/RHEL's
# %%pyproject_wheel would, since pyproject-rpm-macros isn't reliably
# available on SUSE either way.
#
# %%python3_sitelib isn't defined without the base python-rpm-macros
# package -- ask the *actual* interpreter we're building with (not
# necessarily bare python3 -- see above) for the exact path it will
# install into instead of guessing lib vs lib64.
%global python3_sitelib %(%{suse_python} -c "import sysconfig; print(sysconfig.get_path('purelib', vars={'base': '/usr', 'platbase': '/usr'}))" 2>/dev/null || echo /usr/lib/python3/site-packages)
%else
# Fedora / RHEL / CentOS Stream: the modern PEP 517 build/install macros
# (%%pyproject_wheel / %%pyproject_install), not the legacy setup.py-based
# %%py3_build / %%py3_install -- this project has no setup.py.
BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
BuildRequires:  python3-pytest
BuildRequires:  python3-PyYAML
BuildRequires:  pyproject-rpm-macros
%endif

%if 0%{?suse_version}
# Bare `python3` alone would be satisfied by SLES 15 SP7's ancient 3.6
# without ever pulling in the versioned interpreter rmstory's own console
# script is actually built against (see the %%{suse_py_base} explanation
# above) -- %%{suse_py_base} covers that; it's plain "python3" on
# Tumbleweed/Leap 16, so this is a no-op change there.
Requires:       %{suse_py_base}
Requires:       %{suse_py_pkg}-PyYAML
%else
Requires:       python3
Requires:       python3-pyyaml
%endif
# multilang-lib publishes its own package per distro as a release asset
# (github.com/rmahique/multilang-lib/releases), not through a live repo
# -- this Requires (python3-multilang) reflects a real deployment's
# need, same reasoning as ../debian/control's Depends. %%check below
# doesn't assume it's actually installed in *this* build environment.
Requires:       python3-multilang

%description
Provides the rmstory CLI (extract/translate/story/validate) and library
API for translating and recombining stories authored as tagged <span>
elements in markdown/HTML files. Translations are stored via
multilang-lib; a story is a lightweight ordered-id index, not a second
content store. Twelve pluggable machine-translation engines are available
(gemini, deepl, google-translate, microsoft-translator, libretranslate,
baidu, claude-code, ollama, deepseek, mistral, qwen, kimi) -- the last
nine work out of the box (plain REST calls or a CLI subprocess, no SDK).
The first three each need their vendor's own SDK, none of which is
packaged for any distro (pip-only) -- install the one(s) you want with
`pip install "rmstory[gemini]"`, `"rmstory[deepl]"`, or
`"rmstory[google-translate]"` (see README.md). claude-code instead shells
out to the `claude` CLI (https://claude.com/claude-code), not pip at
all; ollama, deepseek, mistral, qwen, and kimi are plain REST calls
needing only an API key (ollama needs neither a key nor even a network
call off this machine).

%prep
%autosetup -n %{srcname}-%{version}

%if 0%{?suse_version}
%build
%{suse_python} -m pip wheel . --no-deps --no-build-isolation --wheel-dir dist

%install
%{suse_python} -m pip install dist/*.whl --no-deps --root=%{buildroot} --prefix=/usr
%else
%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files %{srcname}
%endif

%check
# multilang-lib (python3-multilang) is this package's one runtime
# dependency the test suite actually needs importable -- see the Requires
# comment above for why it may not be present in this build environment
# yet. Run the tests if it's importable, skip with a clear message
# otherwise, rather than failing the whole package build over a
# dependency the *installed* package correctly declares but this build
# container doesn't necessarily provide.
%if 0%{?suse_version}
if PYTHONPATH=%{buildroot}%{python3_sitelib} %{suse_python} -c "import pytest, multilang" >/dev/null 2>&1; then
    PYTHONPATH=%{buildroot}%{python3_sitelib} %{suse_python} -m pytest tests/ -v
else
    echo "pytest and/or multilang not available; skipping %%check"
fi
%else
if PYTHONPATH=%{buildroot}%{python3_sitelib} %{__python3} -c "import multilang" >/dev/null 2>&1; then
    PYTHONPATH=%{buildroot}%{python3_sitelib} %{__python3} -m pytest tests/ -v
else
    echo "multilang not available in this build environment; skipping %%check"
fi
%endif

%if 0%{?suse_version}
%files
%license LICENSE
%doc README.md
%{python3_sitelib}/%{srcname}/
# Not %%{srcname}-%%{version}*.dist-info/: pip names the dist-info dir
# after pyproject.toml's own static version (0.1.0), not this RPM
# package's --define "version ..." (0.1.0^20260813 on an untagged
# build) -- those only coincide on an actual tagged release, so this
# glob must not assume they match.
%{python3_sitelib}/%{srcname}-*.dist-info/
%{_bindir}/%{srcname}
%else
# %%pyproject_save_files (above) recorded the exact install manifest, so
# this doesn't need to guess at egg-info vs dist-info layout -- but it
# doesn't capture the console_scripts entry point (rmstory itself,
# [project.scripts] in pyproject.toml), so that's listed explicitly.
%files -f %{pyproject_files}
%license LICENSE
%doc README.md
%{_bindir}/%{srcname}
%endif

%changelog
* Thu Aug 13 2026 Raúl Mahiques <claude.ia@raulmahiques.com> - 0.1.0-1
- Initial release: extract/translate/story/validate CLI, translation
  storage via multilang-lib, per-story ordered-id indexes, and six
  pluggable machine-translation engines.
