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
# openSUSE Tumbleweed and Leap 16 -- Leap 15 is deliberately not
# supported here (unlike multilang-lib, which has zero required
# dependencies and builds fine on every SUSE flavor). This project
# requires PyYAML at runtime, and Leap 15's versioned python310 package
# family -- needed since Leap 15's *default* python3 is 3.6, too old for
# requires-python >=3.9 -- has no python310-PyYAML (confirmed against the
# real repo metadata: python310-devel/-setuptools exist,
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
# names Tumbleweed uses. build-rpm.sh passes
# --define "leap_versioned_python 1" --define "leap_pyver <NN>" for that
# job only (computed from the actual python3 installed, not hardcoded,
# so a future Leap 16.x point release with a newer default python3
# doesn't silently break this); Tumbleweed doesn't set either, so
# %%{leap_pyver} defaults to plain "3" there, matching its own python3-*
# naming.
%{!?leap_pyver: %global leap_pyver 3}
%if 0%{?leap_versioned_python}
%global suse_py_pkg python%{leap_pyver}
%else
%global suse_py_pkg python3
%endif
BuildRequires:  python3
BuildRequires:  %{suse_py_pkg}-devel
BuildRequires:  %{suse_py_pkg}-setuptools
BuildRequires:  %{suse_py_pkg}-PyYAML
# Still uses the same pip-wheel mechanism as Fedora/RHEL's
# %%pyproject_wheel would, since pyproject-rpm-macros isn't reliably
# available on SUSE either way.
#
# %%python3_sitelib isn't defined without the base python-rpm-macros
# package -- ask python's own sysconfig for the exact path it will
# actually install into instead of guessing lib vs lib64.
%global python3_sitelib %(python3 -c "import sysconfig; print(sysconfig.get_path('purelib', vars={'base': '/usr', 'platbase': '/usr'}))" 2>/dev/null || echo /usr/lib/python3/site-packages)
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
Requires:       python3
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
content store. Six pluggable machine-translation engines are available
(gemini, deepl, google-translate, microsoft-translator, libretranslate,
baidu) -- the last three need no extra package, the first three need
their SDK installed separately via pip (see README.md).

%prep
%autosetup -n %{srcname}-%{version}

%if 0%{?suse_version}
%build
python3 -m pip wheel . --no-deps --no-build-isolation --wheel-dir dist

%install
python3 -m pip install dist/*.whl --no-deps --root=%{buildroot} --prefix=/usr
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
if PYTHONPATH=%{buildroot}%{python3_sitelib} python3 -c "import pytest, multilang" >/dev/null 2>&1; then
    PYTHONPATH=%{buildroot}%{python3_sitelib} python3 -m pytest tests/ -v
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
