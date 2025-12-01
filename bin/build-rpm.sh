#!/bin/bash
# -*- coding: utf-8 -*-
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
#!/usr/bin/env bash
set -euo pipefail

# Set Apprise root directory
APPRISE_DIR="${APPRISE_DIR:-/apprise}"
DIST_DIR="${DIST_DIR:-$PWD/dist/rpm}"
SOURCES_DIR="$APPRISE_DIR/SOURCES"
SRPM_DIR="$DIST_DIR/"

PYTHON=python3
TOX="tox -c $APPRISE_DIR/tox.ini"

if [ ! -d "$DIST_DIR" ]; then
   echo "==> Cleaning previous builds"
   $TOX -e clean --notest

   echo "==> Linting RPM spec"
       rpmlint "$APPRISE_DIR/packaging/redhat/python-apprise.spec"

   echo "==> Generating man pages"
   ronn --roff --organization="Chris Caron <lead2gold@gmail.com>" \
       "$APPRISE_DIR/packaging/man/apprise.md"

   echo "==> Extracting translations"
   $TOX -e i18n

   echo "==> Compiling translations"
   $TOX -e compile

   echo "==> Building source distribution"
   $TOX -e build-sdist
fi

VERSION=$(rpmspec -q --qf "%{version}\n" "$APPRISE_DIR/packaging/redhat/python-apprise.spec" | head -n1)
TARBALL="$APPRISE_DIR/dist/apprise-${VERSION}.tar.gz"

if [[ ! -f "$TARBALL" ]]; then
  echo "❌ Tarball not found: $TARBALL"
  exit 1
fi

echo "==> Preparing SOURCES directory"
mkdir -p "$SOURCES_DIR"
cp "$TARBALL" "$SOURCES_DIR/"
find $APPRISE_DIR/packaging/redhat/ -iname '*.patch' -exec cp {} "$SOURCES_DIR" \;

echo "==> Building RPM (source and binary)"
mkdir -p "$DIST_DIR"
rpmbuild --define "_topdir $APPRISE_DIR" \
         --define "_sourcedir $SOURCES_DIR" \
         --define "_specdir $APPRISE_DIR/packaging/redhat" \
         --define "_srcrpmdir $DIST_DIR" \
         --define "_rpmdir $DIST_DIR" \
         -ba "$APPRISE_DIR/packaging/redhat/python-apprise.spec"

echo "✅ RPM build completed successfully"
echo "📦 Artifacts:"
find "$DIST_DIR" -type f -name "*.rpm"
