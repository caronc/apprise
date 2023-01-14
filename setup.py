# -*- coding: utf-8 -*-
#
# Apprise - Push Notification Library.
# Copyright (C) 2023  Chris Caron <lead2gold@gmail.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor,
# Boston, MA  02110-1301, USA.

import re
import os
import platform
import sys

from setuptools import find_packages, setup

cmdclass = {}
try:
    from babel.messages import frontend as babel
    cmdclass = {
        'compile_catalog': babel.compile_catalog,
        'extract_messages': babel.extract_messages,
        'init_catalog': babel.init_catalog,
        'update_catalog': babel.update_catalog,
    }
except ImportError:
    pass

install_options = os.environ.get("APPRISE_INSTALL", "").split(",")
install_requires = open('requirements.txt').readlines()
if platform.system().lower().startswith('win') \
        and not hasattr(sys, "pypy_version_info"):
    # Windows Notification Support
    install_requires += open('win-requirements.txt').readlines()

libonly_flags = set(["lib-only", "libonly", "no-cli", "without-cli"])
if libonly_flags.intersection(install_options):
    console_scripts = []

else:
    # Load our CLI
    console_scripts = ['apprise = apprise.cli:main']

setup(
    name='apprise',
    version='1.2.1',
    description='Push Notifications that work with just about every platform!',
    license='GPLv2',
    long_description=open('README.md', encoding="utf-8").read(),
    long_description_content_type='text/markdown',
    cmdclass=cmdclass,
    url='https://github.com/caronc/apprise',
    keywords=' '.join(re.split(r'\s+', open('KEYWORDS').read())),
    author='Chris Caron',
    author_email='lead2gold@gmail.com',
    packages=find_packages(),
    package_data={
        'apprise': [
            'assets/NotifyXML-*.xsd',
            'assets/themes/default/*.png',
            'assets/themes/default/*.ico',
            'i18n/*.py',
            'i18n/*/LC_MESSAGES/*.mo',
            'py.typed',
            '*.pyi',
            '*/*.pyi'
        ],
    },
    install_requires=install_requires,
    classifiers=(
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Operating System :: OS Independent',
        'Natural Language :: English',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'License :: OSI Approved :: '
        'GNU General Public License v2 or later (GPLv2+)',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
    ),
    entry_points={'console_scripts': console_scripts},
    python_requires='>=3.6',
    setup_requires=['babel', ],
)
