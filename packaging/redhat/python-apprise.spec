# Copyright (C) 2019 Chris Caron <lead2gold@gmail.com>
# All rights reserved.
#
# This code is licensed under the MIT License.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files(the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and / or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions :
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
###############################################################################
%global with_python2 1
%global with_python3 1

%if 0%{?fedora} || 0%{?rhel} >= 8
# Python v2 Support dropped
%global with_python2 0
%endif # fedora and/or rhel7

%if 0%{?_module_build}
%bcond_with tests
%else
# When bootstrapping Python, we cannot test this yet
%bcond_without tests
%endif # module_build

%if 0%{?rhel} && 0%{?rhel} <= 7
%global with_python3 0
%endif # using rhel7

Name:           python-apprise
Version:        0.7.5
Release:        1%{?dist}
Summary:        A simple wrapper to many popular notification services used today
License:        MIT
URL:            https://github.com/caronc/apprise
Source0:        %{url}/archive/v%{version}/apprise-%{version}.tar.gz
# A simple man page to help with rpmlint. Future versions of apprise would not
# require this entry as it will be part of the distribution going forward.
# this man page was added as part of the Fedora review process
Source1:        apprise.1
# this patch allows version of requests that ships with RHEL v7 to
# correctly handle test coverage.  It also removes reference to a
# extra check not supported in py.test in EPEL7 builds
Patch0:         apprise-rhel7-support.patch
BuildArch:      noarch

%description
Apprise is a Python package for simplifying access to all of the different
notification services that are out there. Apprise opens the door and makes
it easy to access:

Boxcar, Discord, E-Mail, Emby, Faast, Flock, Gitter, Gotify, Growl, IFTTT,
Join, KODI, MatterMost, Matrix, Microsoft Windows Notifications,
Microsoft Teams, Notify My Android, Prowl, Pushalot, PushBullet, Pushjet,
Pushover, Rocket.Chat, Slack, Super Toasty, Stride, Telegram, Twitter, XBMC,
XMPP, Webex Teams

%if 0%{?with_python2}
%package -n python2-apprise
Summary: A simple wrapper to many popular notification services used today
%{?python_provide:%python_provide python2-apprise}

BuildRequires: python2-devel
BuildRequires: python-decorator
BuildRequires: python-requests
BuildRequires: python2-requests-oauthlib
BuildRequires: python2-oauthlib
BuildRequires: python-six
BuildRequires: python2-click >= 5.0
BuildRequires: python-markdown
%if 0%{?rhel} && 0%{?rhel} <= 7
BuildRequires: python-yaml
%else
BuildRequires: python2-yaml
%endif # using rhel7

Requires: python-decorator
Requires: python-requests
Requires: python2-requests-oauthlib
Requires: python2-oauthlib
Requires: python-six
Requires: python-markdown
%if 0%{?rhel} && 0%{?rhel} <= 7
BuildRequires: python-yaml
%else
Requires: python2-yaml
%endif # using rhel7

%if %{with tests}
BuildRequires: python-mock
BuildRequires: python2-pytest-runner
BuildRequires: python2-pytest

%endif # with_tests

%description -n python2-apprise
Apprise is a Python package for simplifying access to all of the different
notification services that are out there. Apprise opens the door and makes
it easy to access:

Boxcar, Discord, E-Mail, Emby, Faast, Flock, Gitter, Gotify, Growl, IFTTT,
Join, KODI, MatterMost, Matrix, Microsoft Windows Notifications,
Microsoft Teams, Notify My Android, Prowl, Pushalot, PushBullet, Pushjet,
Pushover, Rocket.Chat, Slack, Super Toasty, Stride, Telegram, Twitter, XBMC,
XMPP, Webex Teams
%endif # with_python2

%package -n apprise
Summary: Apprise CLI Tool

%if 0%{?with_python3}
Requires: python%{python3_pkgversion}-click >= 5.0
Requires: python%{python3_pkgversion}-apprise = %{version}-%{release}
%endif # with_python3

%if 0%{?with_python2}
Requires: python2-click >= 5.0
Requires: python2-apprise = %{version}-%{release}
%endif # with_python2

%description -n apprise
An accompanied CLI tool that can be used as part of Apprise
to issue notifications from the command line to you favorite
services.

%if 0%{?with_python3}
%package -n python%{python3_pkgversion}-apprise
Summary: A simple wrapper to many popular notification services used today
%{?python_provide:%python_provide python%{python3_pkgversion}-apprise}

BuildRequires: python%{python3_pkgversion}-devel
BuildRequires: python%{python3_pkgversion}-decorator
BuildRequires: python%{python3_pkgversion}-requests
BuildRequires: python%{python3_pkgversion}-requests-oauthlib
BuildRequires: python%{python3_pkgversion}-oauthlib
BuildRequires: python%{python3_pkgversion}-six
BuildRequires: python%{python3_pkgversion}-click >= 5.0
BuildRequires: python%{python3_pkgversion}-markdown
BuildRequires: python%{python3_pkgversion}-yaml
Requires: python%{python3_pkgversion}-decorator
Requires: python%{python3_pkgversion}-requests
Requires: python%{python3_pkgversion}-requests-oauthlib
Requires: python%{python3_pkgversion}-oauthlib
Requires: python%{python3_pkgversion}-six
Requires: python%{python3_pkgversion}-markdown
Requires: python%{python3_pkgversion}-yaml

%if %{with tests}
BuildRequires: python%{python3_pkgversion}-mock
BuildRequires: python%{python3_pkgversion}-pytest
BuildRequires: python%{python3_pkgversion}-pytest-runner
%endif # with_tests

%description -n python%{python3_pkgversion}-apprise
Apprise is a Python package for simplifying access to all of the different
notification services that are out there. Apprise opens the door and makes
it easy to access:

Boxcar, Discord, E-Mail, Emby, Faast, Growl, IFTTT, Join, KODI, MatterMost,
Matrix, Notify My Android, Prowl, Pushalot, PushBullet, Pushjet, Pushover,
Rocket.Chat, Slack, Super Toasty, Stride, Telegram, Twitter, XBMC
%endif # with_python3

%prep
%setup -q -n apprise-%{version}
%if 0%{?rhel} && 0%{?rhel} <= 7
# rhel7 older package work-arounds
%patch0 -p1
%endif # using rhel7

%build
%if 0%{?with_python2}
%py2_build
%endif # with_python2
%if 0%{?with_python3}
%py3_build
%endif # with_python3

%install
%if 0%{?with_python2}
%py2_install
%endif # with_python2
%if 0%{?with_python3}
%py3_install
%endif # with_python3

# Install man page
# Future versions will look like this:
# install -p -D -T -m 0644 packages/man/apprise.1 \
#   %{buildroot}%{_mandir}/man1/apprise.1
#
# For now:
install -p -D -T -m 0644 %{SOURCE1} \
   %{buildroot}%{_mandir}/man1/apprise.1

%if %{with tests}
%check
%if 0%{?with_python2}
LANG=C.UTF-8 PYTHONPATH=%{buildroot}%{python2_sitelib} py.test
%endif # with_python2
%if 0%{?with_python3}
LANG=C.UTF-8 PYTHONPATH=%{buildroot}%{python3_sitelib} py.test-%{python3_version}
%endif # with_python3
%endif # with_tests

%if 0%{?with_python2}
%files -n python2-apprise
%license LICENSE
%doc README.md
%{python2_sitelib}/apprise
%exclude %{python2_sitelib}/apprise/cli.*
%{python2_sitelib}/*.egg-info
%endif # with_python2

%if 0%{?with_python3}
%files -n python%{python3_pkgversion}-apprise
%license LICENSE
%doc README.md
%{python3_sitelib}/apprise
%exclude %{python3_sitelib}/apprise/cli.*
%{python3_sitelib}/*.egg-info
%endif # with_python3

%files -n apprise
%{_bindir}/apprise
%{_mandir}/man1/apprise.1*

%if 0%{?with_python3}
%{python3_sitelib}/apprise/cli.*
%endif # with_python3

%if 0%{?with_python2}
%{python2_sitelib}/apprise/cli.*
%endif # with_python2

%changelog
* Sun Apr  7 2019 Chris Caron <lead2gold@gmail.com> - 0.7.5-1
- Updated to v0.7.5

* Sun Mar 10 2019 Chris Caron <lead2gold@gmail.com> - 0.7.4-1
- Updated to v0.7.4
- Fedora review process added a man page, spec restructuring and 2 patch files
  to accomodate some valid points brought forth. These have already been pused
  upstream and will be removed on the next version.

* Fri Feb 22 2019 Chris Caron <lead2gold@gmail.com> - 0.7.3-1
- Updated to v0.7.3
- Added Python 3 build support

* Sun Sep  9 2018 Chris Caron <lead2gold@gmail.com> - 0.5.0-1
- Updated to v0.5.0

* Sun Mar 11 2018 Chris Caron <lead2gold@gmail.com> - 0.0.8-1
- Initial Release
