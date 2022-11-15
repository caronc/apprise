#!/bin/bash
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
   # Remove previous `dist` and egg-info directory if it exists
   [ -d $APPRISE_DIR/dist ] && rm -rf $APPRISE_DIR/dist
   [ -d $APPRISE_DIR/apprise.egg-info ] && rm -rf $APPRISE_DIR/apprise.egg-info
   [ -d $APPRISE_DIR/build ] && rm -rf $APPRISE_DIR/build
}

build(){
   # Build Apprise
   if [ ! -x $HOME/dev/bin/activate ]; then
      $VENV_CMD $HOME/dev
      [ $? -ne 0 ] && return 1
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

   # Prepare RPM Package
   find "$APPRISE_DIR/packaging/man/" -type f -name '*.1' \
         -exec cp --verbose {} "$APPRISE_DIR/dist" \;
   find "$APPRISE_DIR/packaging/redhat" -type f -name '*.patch' \
         -exec cp --verbose {} "$APPRISE_DIR/dist" \;
   find "$APPRISE_DIR/packaging/redhat" -type f -name '*.spec' \
         -exec cp --verbose {} "$APPRISE_DIR/dist" \;

   rpmbuild -ba "$APPRISE_DIR/dist/python-apprise.spec"

   return 0
}

# Prepare our environment
mkenv

# Clean
clean

# Build
build
