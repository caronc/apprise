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

# Directory where Apprise Source Code can be found
APPRISE_DIR="/apprise"
PYTHON=python3
PIP=pip3
VENV_CMD="$PYTHON -m venv"

mkenv(){
   # Prepares RPM Environment
   cat << _EOF > $HOME/.rpmmacros
# macros
%_topdir    $APPRISE_DIR
%_sourcedir %{_topdir}/dist
%_specdir   %{_topdir}/dist
%_rpmdir    %{_topdir}/dist/rpm
%_srcrpmdir %{_topdir}/dist/rpm
%_builddir  %{_topdir}/build/rpm
_EOF
   # Prepare our working directories if not already present
   mkdir -p $APPRISE_DIR/{dist/rpm,build/rpm}
   return 0
}

clean(){
   # Tidy .pyc files
   find $APPRISE_DIR -name '*.pyc' -delete &>/dev/null
   find $APPRISE_DIR -type d -name '__pycache__' -exec rm -rf {} \ &>/dev/null;
   # Remove previously build details
   [ -d "$APPRISE_DIR/apprise.egg-info" ] && rm -rf $APPRISE_DIR/apprise.egg-info
   [ -d "$APPRISE_DIR/build" ] && rm -rf $APPRISE_DIR/build
   [ -d "$APPRISE_DIR/BUILDROOT" ] && rm -rf $APPRISE_DIR/BUILDROOT
}

build(){
   # Test spec file for any issues
   rpmlint "$APPRISE_DIR/packaging/redhat/python-apprise.spec"
   [ $? -ne 0 ] && echo "RPMLint Failed!" && return 1

   # Prepare RPM Package
   # Detect our version
   local VER=$(rpmspec -q --qf "%{version}\n" \
      "$APPRISE_DIR/packaging/redhat/python-apprise.spec" 2>/dev/null | head -n1)
   [ -z "$VER" ] && echo "Could not detect Apprise RPM Version" && return 1

   if [ ! -f "$APPRISE_DIR/dist/apprise-$VER.tar.gz" ]; then
      # Build Apprise
      if [ ! -x $HOME/dev/bin/activate ]; then
         $VENV_CMD $HOME/dev
         [ $? -ne 0 ] && echo "Could not create Virtual Python Environment" && return 1
      fi
      . $HOME/dev/bin/activate
      $PIP install coverage babel wheel markdown

      pushd $APPRISE_DIR
      # Build Man Page
      ronn --roff $APPRISE_DIR/packaging/man/apprise.md
      $PYTHON setup.py extract_messages
      $PYTHON setup.py sdist

      # exit from our virtual environment
      deactivate
   fi

   # Prepare our RPM Source and SPEC dependencies
   find "$APPRISE_DIR/packaging/man/" -type f -name '*.1' \
         -exec cp --verbose {} "$APPRISE_DIR/dist" \;
   find "$APPRISE_DIR/packaging/redhat" -type f -name '*.patch' \
         -exec cp --verbose {} "$APPRISE_DIR/dist" \;
   find "$APPRISE_DIR/packaging/redhat" -type f -name '*.spec' \
         -exec cp --verbose {} "$APPRISE_DIR/dist" \;

   # Build and Test our RPM Package
   rpmbuild -ba "$APPRISE_DIR/dist/python-apprise.spec"
   return $?
}

# Prepare our environment
mkenv

# Clean
clean

# Build
build

# Return our build status
exit $?
