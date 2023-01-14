#!/bin/bash
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
