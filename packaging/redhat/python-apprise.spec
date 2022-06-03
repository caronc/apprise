# Copyright (C) 2022 Chris Caron <lead2gold@gmail.com>
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
%endif

%if 0%{?_module_build}
%bcond_with tests
%else
# When bootstrapping Python, we cannot test this yet
%bcond_without tests
%endif

%if 0%{?rhel} && 0%{?rhel} <= 7
%global with_python3 0
%endif

%global pypi_name apprise

%global common_description %{expand: \
Apprise is a Python package for simplifying access to all of the different
notification services that are out there. Apprise opens the door and makes
it easy to access:

Apprise API, AWS SES, AWS SNS, Bark, Boxcar, ClickSend, DAPNET, DingTalk,
Discord, E-Mail, Emby, Faast, FCM, Flock, Gitter, Google Chat, Gotify, Growl,
Guilded, Home Assistant, IFTTT, Join, Kavenegar, KODI, Kumulos, LaMetric,
Line, MacOSX, Mailgun, Mattermost, Matrix, Microsoft Windows, Microsoft Teams,
MessageBird, MQTT, MSG91, MyAndroid, Nexmo, Nextcloud, NextcloudTalk, Notica,
Notifico, ntfy, Office365, OneSignal, Opsgenie, PagerDuty, ParsePlatform,
PopcornNotify, Prowl, Pushalot, PushBullet, Pushjet, Pushover, PushSafer,
Reddit, Rocket.Chat, SendGrid, ServerChan, Signal, SimplePush, Sinch, Slack,
SMTP2Go, Spontit, SparkPost, Super Toasty, Streamlabs, Stride, Syslog,
Techulus Push, Telegram, Twilio, Twitter, Twist, XBMC, XMPP, Webex Teams}

Name:           python-%{pypi_name}
Version:        0.9.9
Release:        1%{?dist}
Summary:        A simple wrapper to many popular notification services used today
License:        MIT
URL:            https://github.com/caronc/%{pypi_name}
Source0:        %{url}/archive/v%{version}/%{pypi_name}-%{version}.tar.gz
# this patch allows version of requests that ships with RHEL v7 to
# correctly handle test coverage.  It also removes reference to a
# extra check not supported in py.test in EPEL7 builds
Patch0:         %{pypi_name}-rhel7-support.patch
BuildArch:      noarch

%description %{common_description}

%if 0%{?with_python2}
%package -n python2-%{pypi_name}
Summary: A simple wrapper to many popular notification services used today
%{?python_provide:%python_provide python2-%{pypi_name}}

BuildRequires: python2-devel
BuildRequires: python-requests
BuildRequires: python2-requests-oauthlib
BuildRequires: python-six
BuildRequires: python2-click >= 5.0
BuildRequires: python-markdown
%if 0%{?rhel} && 0%{?rhel} <= 7
BuildRequires: python-cryptography
BuildRequires: python-babel
BuildRequires: python-yaml
%else
BuildRequires: python2-cryptography
BuildRequires: python2-babel
BuildRequires: python2-yaml
%endif

Requires: python-requests
Requires: python2-requests-oauthlib
Requires: python-six
Requires: python-markdown
%if 0%{?rhel} && 0%{?rhel} <= 7
Requires: python-cryptography
Requires: python-yaml
%else
Requires: python2-cryptography
Requires: python2-yaml
%endif

%if %{with tests}
BuildRequires: python-mock
BuildRequires: python2-pytest-runner
BuildRequires: python2-pytest

%endif

%description -n python2-%{pypi_name} %{common_description}
%endif

%package -n %{pypi_name}
Summary: Apprise CLI Tool

%if 0%{?with_python3}
Requires: python%{python3_pkgversion}-click >= 5.0
Requires: python%{python3_pkgversion}-%{pypi_name} = %{version}-%{release}
%endif

%if 0%{?with_python2}
Requires: python2-click >= 5.0
Requires: python2-%{pypi_name} = %{version}-%{release}
%endif

%description -n %{pypi_name}
An accompanied CLI tool that can be used as part of Apprise
to issue notifications from the command line to you favorite
services.

%if 0%{?with_python3}
%package -n python%{python3_pkgversion}-%{pypi_name}
Summary: A simple wrapper to many popular notification services used today
%{?python_provide:%python_provide python%{python3_pkgversion}-%{pypi_name}}

BuildRequires: python%{python3_pkgversion}-devel
BuildRequires: python%{python3_pkgversion}-setuptools
BuildRequires: python%{python3_pkgversion}-requests
BuildRequires: python%{python3_pkgversion}-requests-oauthlib
BuildRequires: python%{python3_pkgversion}-six
BuildRequires: python%{python3_pkgversion}-click >= 5.0
BuildRequires: python%{python3_pkgversion}-markdown
BuildRequires: python%{python3_pkgversion}-yaml
BuildRequires: python%{python3_pkgversion}-babel
BuildRequires: python%{python3_pkgversion}-cryptography
Requires: python%{python3_pkgversion}-requests
Requires: python%{python3_pkgversion}-requests-oauthlib
Requires: python%{python3_pkgversion}-six
Requires: python%{python3_pkgversion}-markdown
Requires: python%{python3_pkgversion}-cryptography
Requires: python%{python3_pkgversion}-yaml

%if %{with tests}
BuildRequires: python%{python3_pkgversion}-mock
BuildRequires: python%{python3_pkgversion}-pytest
BuildRequires: python%{python3_pkgversion}-pytest-runner
%endif

%description -n python%{python3_pkgversion}-%{pypi_name} %{common_description}
%endif

%prep
%setup -q -n %{pypi_name}-%{version}
%if 0%{?rhel} && 0%{?rhel} <= 7
# rhel7 older package work-arounds
%patch0 -p1
# rhel7 doesn't like the new asyncio syntax
rm -f apprise/py3compat/asyncio.py
# rhel7 doesn't support slixmpp and formatting in place
# within the dev-requirements.txt file to reference it
sed -i -e '/^slixmpp.*/d' dev-requirements.txt
%endif

%build
%if 0%{?with_python2}
%py2_build
%endif
%if 0%{?with_python3}
%py3_build
%endif

%install
%if 0%{?with_python2}
%py2_install
%endif
%if 0%{?with_python3}
%py3_install
%endif

install -p -D -T -m 0644 packaging/man/%{pypi_name}.1 \
   %{buildroot}%{_mandir}/man1/%{pypi_name}.1

%if %{with tests}
%check
%if 0%{?with_python2}
LANG=C.UTF-8 PYTHONPATH=%{buildroot}%{python2_sitelib} py.test
%endif
%if 0%{?with_python3}
LANG=C.UTF-8 PYTHONPATH=%{buildroot}%{python3_sitelib} py.test-%{python3_version}
%endif
%endif

%if 0%{?with_python2}
%files -n python2-%{pypi_name}
%license LICENSE
%doc README.md
%{python2_sitelib}/%{pypi_name}
%exclude %{python2_sitelib}/%{pypi_name}/cli.*
%{python2_sitelib}/*.egg-info
%endif

%if 0%{?with_python3}
%files -n python%{python3_pkgversion}-%{pypi_name}
%license LICENSE
%doc README.md
%{python3_sitelib}/%{pypi_name}
%exclude %{python3_sitelib}/%{pypi_name}/cli.*
%{python3_sitelib}/*.egg-info
%endif

%files -n %{pypi_name}
%{_bindir}/%{pypi_name}
%{_mandir}/man1/%{pypi_name}.1*

%if 0%{?with_python3}
%{python3_sitelib}/%{pypi_name}/cli.*
%endif

%if 0%{?with_python2}
%{python2_sitelib}/%{pypi_name}/cli.*
%endif

%changelog
* Thu Jun  2 2022 Chris Caron <lead2gold@gmail.com> - 0.9.9-1
- Updated to v0.9.9

* Thu Apr 28 2022 Chris Caron <lead2gold@gmail.com> - 0.9.8.3-1
- Updated to v0.9.8.3

* Sat Apr 23 2022 Chris Caron <lead2gold@gmail.com> - 0.9.8.2-1
- Updated to v0.9.8.2

* Tue Apr 19 2022 Chris Caron <lead2gold@gmail.com> - 0.9.8.1-1
- Updated to v0.9.8.1

* Mon Apr 18 2022 Chris Caron <lead2gold@gmail.com> - 0.9.8-1
- Updated to v0.9.8

* Wed Feb  2 2022 Chris Caron <lead2gold@gmail.com> - 0.9.7-1
- Updated to v0.9.7

* Wed Dec  1 2021 Chris Caron <lead2gold@gmail.com> - 0.9.6-1
- Updated to v0.9.6

* Sat Sep 18 2021 Chris Caron <lead2gold@gmail.com> - 0.9.5.1-2
- Updated to v0.9.5.1

* Sat Sep 18 2021 Chris Caron <lead2gold@gmail.com> - 0.9.5-1
- Updated to v0.9.5

* Wed Aug 11 2021 Chris Caron <lead2gold@gmail.com> - 0.9.4-1
- Updated to v0.9.4

* Fri Jul 23 2021 Fedora Release Engineering <releng@fedoraproject.org> - 0.9.3-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_35_Mass_Rebuild

* Fri Jun 04 2021 Python Maint <python-maint@redhat.com> - 0.9.3-2
- Rebuilt for Python 3.10

* Sun May 16 2021 Chris Caron <lead2gold@gmail.com> - 0.9.3-1
- Updated to v0.9.3

* Sun May  2 2021 Chris Caron <lead2gold@gmail.com> - 0.9.2-1
- Updated to v0.9.2

* Tue Feb 23 2021 Chris Caron <lead2gold@gmail.com> - 0.9.1-2
- Added missing cryptography dependency

* Tue Feb 23 2021 Chris Caron <lead2gold@gmail.com> - 0.9.1-1
- Updated to v0.9.1

-* Wed Jan 27 2021 Fedora Release Engineering <releng@fedoraproject.org> - 0.9.0-3
-- Rebuilt for https://fedoraproject.org/wiki/Fedora_34_Mass_Rebuild

* Thu Jan 14 2021 Chris Caron <lead2gold@gmail.com> - 0.9.0-2
- Fixed unit tests

* Wed Dec 30 2020 Chris Caron <lead2gold@gmail.com> - 0.9.0-1
- Updated to v0.9.0

* Sun Oct  4 2020 Chris Caron <lead2gold@gmail.com> - 0.8.9-1
- Updated to v0.8.9

* Wed Sep  2 2020 Chris Caron <lead2gold@gmail.com> - 0.8.8-1
- Updated to v0.8.8

* Thu Aug 13 2020 Chris Caron <lead2gold@gmail.com> - 0.8.7-1
- Updated to v0.8.7

* Mon Aug 03 2020 Chris Caron <lead2gold@gmail.com> - 0.8.6-4
- Updated SPEC so Fedora 33 Mass Rebuild would pass

* Sat Aug 01 2020 Fedora Release Engineering <releng@fedoraproject.org> - 0.8.6-3
- Second attempt - Rebuilt for
  https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Tue Jul 28 2020 Fedora Release Engineering <releng@fedoraproject.org> - 0.8.6-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Sat Jun 13 2020 Chris Caron <lead2gold@gmail.com> - 0.8.6-1
- Updated to v0.8.6

* Tue May 26 2020 Miro Hrončok <mhroncok@redhat.com> - 0.8.5-2
- Rebuilt for Python 3.9

* Mon Mar 30 2020 Chris Caron <lead2gold@gmail.com> - 0.8.5-1
- Updated to v0.8.5

* Sat Feb  1 2020 Chris Caron <lead2gold@gmail.com> - 0.8.4-1
- Updated to v0.8.4

* Sun Jan 12 2020 Chris Caron <lead2gold@gmail.com> - 0.8.3-1
- Updated to v0.8.3

* Mon Nov 25 2019 Chris Caron <lead2gold@gmail.com> - 0.8.2-1
- Updated to v0.8.2

* Sun Oct 13 2019 Chris Caron <lead2gold@gmail.com> - 0.8.1-1
- Updated to v0.8.1

* Fri Sep 20 2019 Chris Caron <lead2gold@gmail.com> - 0.8.0-1
- Updated to v0.8.0

* Fri Jul 19 2019 Chris Caron <lead2gold@gmail.com> - 0.7.9-1
- Updated to v0.7.9

* Thu Jun  6 2019 Chris Caron <lead2gold@gmail.com> - 0.7.8-1
- Updated to v0.7.8

* Fri May 31 2019 Chris Caron <lead2gold@gmail.com> - 0.7.7-1
- Updated to v0.7.7

* Tue Apr 16 2019 Chris Caron <lead2gold@gmail.com> - 0.7.6-1
- Updated to v0.7.6

* Sun Apr  7 2019 Chris Caron <lead2gold@gmail.com> - 0.7.5-1
- Updated to v0.7.5

* Sun Mar 10 2019 Chris Caron <lead2gold@gmail.com> - 0.7.4-1
- Updated to v0.7.4
- Fedora review process added a man page, spec restructuring and 2 patch files
  to accomodate some valid points brought forth. These have already been pushed
  upstream and will be removed on the next version.

* Fri Feb 22 2019 Chris Caron <lead2gold@gmail.com> - 0.7.3-1
- Updated to v0.7.3
- Added Python 3 build support

* Sun Sep  9 2018 Chris Caron <lead2gold@gmail.com> - 0.5.0-1
- Updated to v0.5.0

* Sun Mar 11 2018 Chris Caron <lead2gold@gmail.com> - 0.0.8-1
- Initial Release
