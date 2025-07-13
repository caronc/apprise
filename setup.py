#!/usr/bin/env python
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

#
# 2025.07.10 NOTE:
# setup.py (Temporary shim for RHEL9 Package Building Only)
# Refer to tox for everything else; this will be removed once RHEL9 support
# is dropped.
#
import os
import re

from setuptools import find_packages, setup


def read_version() -> str:
    with open(os.path.join("apprise", "__init__.py"), encoding="utf-8") as f:
        for line in f:
            m = re.match(r'^__version__\s*=\s*[\'"]([^\'"]+)', line)
            if m:
                return m.group(1)
    raise RuntimeError("Version not found")


# tox is not supported well in RHEL9 so this stub file is the only way to
# successfully build the RPM; packaging/redhat/python-apprise.spec has
# been updated accordingly to accomodate reference to this for older
# versions of the distribution only
setup(
    name="apprise",
    version=read_version(),
    packages=find_packages(exclude=["tests*", "packaging*"]),
    entry_points={
        "console_scripts": [
            "apprise = apprise.cli:main",
        ],
    },
    package_data={
        "apprise": [
            "assets/NotifyXML-*.xsd",
            "assets/themes/default/*.png",
            "assets/themes/default/*.ico",
            "i18n/*.py",
            "i18n/*/LC_MESSAGES/*.mo",
            "py.typed",
            "*.pyi",
            "*/*.pyi",
        ],
    },
)
