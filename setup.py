# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2024, Chris Caron <lead2gold@gmail.com>
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
    version='1.7.2',
    description='Push Notifications that work with just about every platform!',
    license='BSD',
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
    classifiers=[
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
        'License :: OSI Approved :: BSD License',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
    ],
    entry_points={'console_scripts': console_scripts},
    python_requires='>=3.6',
    setup_requires=['babel', ],
)
