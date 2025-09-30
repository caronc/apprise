# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2025, Chris Caron <lead2gold@gmail.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
###################################################################
%if 0%{?_module_build}
%bcond_with tests
%else
# When bootstrapping Python, we cannot test this yet
%bcond_without tests
%endif

# Handling of new python building structure (for backwards compatiblity)
%global legacy_python_build 0
%if 0%{?fedora} && 0%{?fedora} <= 29
%global legacy_python_build 1
%endif
%if 0%{?rhel} && 0%{?rhel} <= 9
%global legacy_python_build 1
%endif

%global pypi_name apprise

# Handle rpmlint false positives
# - Prevent warnings:
#    en_US ntfy -> notify
#    en_US httpSMS -> HTTP
# rpmlint: ignore-spelling httpSMS ntfy

# - RHEL9 does not recognize: BSD-2-Clause which is correct
# rpmlint: ignore invalid-license

%global common_description %{expand: \
Apprise is a Python package that simplifies access to many popular \
notification services. It supports sending alerts to platforms such as: \
\
`AfricasTalking`, `Apprise API`, `APRS`, `AWS SES`, `AWS SNS`, `Bark`, \
`BlueSky`, `Burst SMS`, `BulkSMS`, `BulkVS`, `Chanify`, `Clickatell`, \
`ClickSend`, `DAPNET`, `DingTalk`, `Discord`, `E-Mail`, `Emby`, `FCM`, \
`Feishu`, `Flock`, `Free Mobile`, `Google Chat`, `Gotify`, `Growl`, \
`Guilded`, `Home Assistant`, `httpSMS`, `IFTTT`, `Join`, `Kavenegar`, `KODI`, \
`Kumulos`, `LaMetric`, `Lark`, `Line`, `MacOSX`, `Mailgun`, `Mastodon`, \
`Mattermost`, `Matrix`, `MessageBird`, `Microsoft Windows`, \
`Microsoft Teams`, `Misskey`, `MQTT`, `MSG91`, `MyAndroid`, `Nexmo`, \
`Nextcloud`, `NextcloudTalk`, `Notica`, `Notifiarr`, `Notifico`, `ntfy`, \
`Office365`, `OneSignal`, `Opsgenie`, `PagerDuty`, `PagerTree`, \
`ParsePlatform`, `Plivo`, `PopcornNotify`, `Prowl`, `Pushalot`, \
`PushBullet`, `Pushjet`, `PushMe`, `Pushover`, `Pushplus`, `PushSafer`, \
`Pushy`, `PushDeer`, `QQ Push`, `Revolt`, `Reddit`, `Resend`, `Rocket.Chat`, \
`RSyslog`, `SendGrid`, `SendPulse`, `ServerChan`, `Seven`, `SFR`, `Signal`, \
`SIGNL4`, `SimplePush`, `Sinch`, `Slack`, `SMPP`, `SMSEagle`, `SMS Manager`, \
`SMTP2Go`, `SparkPost`, `Splunk`, `Spike`, `Spug Push`, `Super Toasty`, \
`Streamlabs`, `Stride`, `Synology Chat`, `Syslog`, `Techulus Push`, \
`Telegram`, `Threema Gateway`, `Twilio`, `Twitter`, `Twist`, `Vapid`, \
`VictorOps`, `Voipms`, `Vonage`, `WebPush`, `WeCom Bot`, `WhatsApp`, \
`Webex Teams`, `Workflows`, `WxPusher`, and `XBMC`.}

Name:           python-%{pypi_name}
Version:        1.9.5
Release:        1%{?dist}
Summary:        A simple wrapper to many popular notification services used today
License:        BSD-2-Clause
URL:            https://github.com/caronc/%{pypi_name}
Source0:        %{url}/archive/v%{version}/%{pypi_name}-%{version}.tar.gz
BuildArch:      noarch

Obsoletes: python%{python3_pkgversion}-%{pypi_name} < %{version}-%{release}
Provides: python%{python3_pkgversion}-%{pypi_name} = %{version}-%{release}

%description %{common_description}

%package -n %{pypi_name}
Summary: Notify messaging platforms from the command line

Requires: python%{python3_pkgversion}-click >= 5.0
Requires: python%{python3_pkgversion}-%{pypi_name} = %{version}-%{release}

%description -n %{pypi_name}
An accompanied CLI tool that can be used as part of Apprise
to issue notifications from the command line to you favorite
services.

%package -n python%{python3_pkgversion}-%{pypi_name}
Summary: A simple wrapper to many popular notification services used today
%{?python_provide:%python_provide python%{python3_pkgversion}-%{pypi_name}}

BuildRequires: gettext
BuildRequires: python%{python3_pkgversion}-devel
%if %{legacy_python_build}
# backwards compatible
BuildRequires: python%{python3_pkgversion}-setuptools
%endif
BuildRequires: python%{python3_pkgversion}-wheel
BuildRequires: python%{python3_pkgversion}-requests
BuildRequires: python%{python3_pkgversion}-requests-oauthlib
BuildRequires: python%{python3_pkgversion}-click >= 5.0
BuildRequires: python%{python3_pkgversion}-markdown
BuildRequires: python%{python3_pkgversion}-yaml
BuildRequires: python%{python3_pkgversion}-babel
BuildRequires: python%{python3_pkgversion}-cryptography
BuildRequires: python%{python3_pkgversion}-certifi
BuildRequires: python%{python3_pkgversion}-paho-mqtt
BuildRequires: python%{python3_pkgversion}-tox
Requires: python%{python3_pkgversion}-requests
Requires: python%{python3_pkgversion}-requests-oauthlib
Requires: python%{python3_pkgversion}-markdown
Requires: python%{python3_pkgversion}-cryptography
Requires: python%{python3_pkgversion}-certifi
Requires: python%{python3_pkgversion}-yaml
Recommends: python%{python3_pkgversion}-paho-mqtt

%if %{with tests}
BuildRequires: python%{python3_pkgversion}-pytest
BuildRequires: python%{python3_pkgversion}-pytest-mock
BuildRequires: python%{python3_pkgversion}-pytest-runner
BuildRequires: python%{python3_pkgversion}-pytest-cov
%endif

%if 0%{?legacy_python_build} == 0
# Logic for non-RHEL ≤ 9 systems
%generate_buildrequires
%pyproject_buildrequires
%endif

%description -n python%{python3_pkgversion}-%{pypi_name} %{common_description}

%prep
%autosetup -n %{pypi_name}-%{version}

%build
%if %{legacy_python_build}
# backwards compatible
%py3_build
%else
%pyproject_wheel
%endif

%install
%if %{legacy_python_build}
# backwards compatible
%py3_install
%else
%pyproject_install
%pyproject_save_files apprise
%endif

%{__install} -p -D -T -m 0644 packaging/man/%{pypi_name}.1 \
   %{buildroot}%{_mandir}/man1/%{pypi_name}.1

%if %{with tests}
%check
%if %{legacy_python_build}
# backwards compatible
LANG=C.UTF-8 PYTHONPATH=%{buildroot}%{python3_sitelib}:%{_builddir}/%{name}-%{version} py.test-%{python3_version}
%else
%pytest
%endif
%endif

%files -n python%{python3_pkgversion}-%{pypi_name}
%license LICENSE
%doc README.md ACKNOWLEDGEMENTS.md CONTRIBUTING.md
%{python3_sitelib}/%{pypi_name}/
# Exclude i18n as it is handled below with the lang(spoken) tag below
%exclude %{python3_sitelib}/%{pypi_name}/i18n/
%exclude %{python3_sitelib}/%{pypi_name}/cli.*

# Handle egg-info to dist-info transfer
%if 0%{?fedora} >= 40 || 0%{?rhel} >= 10
%{python3_sitelib}/apprise-*.dist-info/
%else
%{python3_sitelib}/apprise-*.egg-info
%endif

# Localised Files
%lang(en) %{python3_sitelib}/%{pypi_name}/i18n/en/LC_MESSAGES/apprise.mo

%files -n %{pypi_name}
%{_bindir}/%{pypi_name}
%{_mandir}/man1/%{pypi_name}.1*
%{python3_sitelib}/%{pypi_name}/cli.*
%{python3_sitelib}/%{pypi_name}/__pycache__/cli*.py?

%changelog
* Tue Sep 30 2025 Chris Caron <lead2gold@gmail.com> - 1.9.5-1
- Updated to v1.9.5

* Fri Sep 19 2025 Python Maint <python-maint@redhat.com> - 1.9.4-4
- Rebuilt for Python 3.14.0rc3 bytecode

* Sat Aug 16 2025 Chris Caron <lead2gold@gmail.com> - 1.9.4-3
- Spec file modernization BZ2377453
- Translation files patch added to allow v1.9.4 to build corectly

* Fri Aug 15 2025 Python Maint <python-maint@redhat.com> - 1.9.4-2
- Rebuilt for Python 3.14.0rc2 bytecode

* Sat Aug  2 2025 Chris Caron <lead2gold@gmail.com> - 1.9.4
- Updated to v1.9.4

* Sun Mar 30 2025 Chris Caron <lead2gold@gmail.com> - 1.9.3
- Updated to v1.9.3

* Sat Jan 18 2025 Fedora Release Engineering <releng@fedoraproject.org> - 1.9.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Wed Jan  8 2025 Chris Caron <lead2gold@gmail.com> - 1.9.2
- Updated to v1.9.2

* Tue Dec 17 2024 Chris Caron <lead2gold@gmail.com> - 1.9.1
- Updated to v1.9.1

* Mon Sep  2 2024 Chris Caron <lead2gold@gmail.com> - 1.9.0
- Updated to v1.9.0

* Thu Jul 25 2024 Chris Caron <lead2gold@gmail.com> - 1.8.1
- Updated to v1.8.1

* Fri Jul 19 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.8.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Fri Jun 07 2024 Python Maint <python-maint@redhat.com> - 1.8.0-2
- Rebuilt for Python 3.13

* Sat May 11 2024 Chris Caron <lead2gold@gmail.com> - 1.8.0
- Updated to v1.8.0

* Sat Apr 13 2024 Chris Caron <lead2gold@gmail.com> - 1.7.6
- Updated to v1.7.6

* Sat Mar 30 2024 Chris Caron <lead2gold@gmail.com> - 1.7.5
- Updated to v1.7.5

* Sat Mar  9 2024 Chris Caron <lead2gold@gmail.com> - 1.7.4
- Updated to v1.7.4

* Sun Mar  3 2024 Chris Caron <lead2gold@gmail.com> - 1.7.3
- Updated to v1.7.3

* Sat Jan 27 2024 Chris Caron <lead2gold@gmail.com> - 1.7.2
- Updated to v1.7.2

* Fri Jan 26 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.6.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Sun Jan 21 2024 Fedora Release Engineering <releng@fedoraproject.org> - 1.6.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Sun Oct 15 2023 Chris Caron <lead2gold@gmail.com> - 1.6.0
- Updated to v1.6.0

* Sun Aug 27 2023 Chris Caron <lead2gold@gmail.com> - 1.5.0
- Updated to v1.5.0
- apprise-fedora-rpm-testcase-handling.patch added for test handling

* Fri Jul 21 2023 Fedora Release Engineering <releng@fedoraproject.org> - 1.4.5-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Thu Jul  6 2023 Chris Caron <lead2gold@gmail.com> - 1.4.5
- Updated to v1.4.5

* Wed Jun 14 2023 Python Maint <python-maint@redhat.com> - 1.4.0-2
- Rebuilt for Python 3.12

* Mon May 15 2023 Chris Caron <lead2gold@gmail.com> - 1.4.0
- Updated to v1.4.0

* Wed Feb 22 2023 Chris Caron <lead2gold@gmail.com> - 1.3.0
- Updated to v1.3.0

* Fri Jan 20 2023 Fedora Release Engineering <releng@fedoraproject.org> - 1.2.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_38_Mass_Rebuild

* Wed Dec 28 2022 Chris Caron <lead2gold@gmail.com> - 1.2.1-1
- Updated to v1.2.1

* Tue Nov 15 2022 Chris Caron <lead2gold@gmail.com> - 1.2.0-1
- Updated to v1.2.0

* Sat Oct  8 2022 Chris Caron <lead2gold@gmail.com> - 1.1.0-1
- Updated to v1.1.0

* Fri Oct  7 2022 Chris Caron <lead2gold@gmail.com> - 1.0.0-3
- Python 2 Support dropped

* Wed Aug 31 2022 Chris Caron <lead2gold@gmail.com> - 1.0.0-2
- Rebuilt for RHEL9 Support

* Sat Aug  6 2022 Chris Caron <lead2gold@gmail.com> - 1.0.0-1
- Updated to v1.0.0

* Fri Jul 22 2022 Fedora Release Engineering <releng@fedoraproject.org> - 0.9.9-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_37_Mass_Rebuild

* Wed Jun 15 2022 Python Maint <python-maint@redhat.com> - 0.9.9-2
- Rebuilt for Python 3.11

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
