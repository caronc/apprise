#!/bin/sh
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

# Absolute path to this script, e.g. /home/user/bin/foo.sh
SCRIPT=$(readlink -f "$0")

# Absolute path this script is in, thus /home/user/bin
SCRIPTPATH=$(dirname "$SCRIPT")

PYTHONPATH=""

FOUNDROOT=1
if [ -f "$(dirname $SCRIPTPATH)/setup.cfg" ]; then
   pushd "$(dirname $SCRIPTPATH)" &>/dev/null
   FOUNDROOT=$?
   PYTHONPATH="$(dirname $SCRIPTPATH)"

elif [ -f "$SCRIPTPATH/setup.cfg" ]; then
   pushd "$SCRIPTPATH" &>/dev/null
   FOUNDROOT=$?
   PYTHONPATH="$SCRIPTPATH"
fi

if [ $FOUNDROOT -ne 0 ]; then
   echo "Error: Could not locate apprise setup.cfg file."
   exit 1
fi

# Tidy previous reports (if present)
[ -d .coverage-reports ] && rm -rf .coverage-reports

# This is a useful tool for checking for any lint errors and additionally
# checking the overall coverage.
which flake8 &>/dev/null
[ $? -ne 0 ] && \
   echo "Missing flake8; make sure it is installed:" && \
   echo "  >  pip install flake8" && \
   exit 1

which coverage &>/dev/null
[ $? -ne 0 ] && \
   echo "Missing coverage; make sure it is installed:" &&
   echo "  >  pip install pytest-cov coverage" && \
   exit 1

echo "Performing PEP8 check..."
LANG=C.UTF-8 PYTHONPATH=$PYTHONPATH flake8 . --show-source --statistics
if [ $? -ne 0 ]; then
   echo "PEP8 check failed"
   exit 1
fi
echo "PEP8 check succeeded; no errors found! :)"
echo

# Run our unit test coverage check
echo "Running test coverage check..."
pushd $PYTHONPATH &>/dev/null
if [ ! -z "$@" ]; then
   LANG=C.UTF-8 PYTHONPATH=$PYTHONPATH coverage run -m pytest -vv -k "$@"
   RET=$?

else
   LANG=C.UTF-8 PYTHONPATH=$PYTHONPATH coverage run -m pytest -vv
   RET=$?
fi

if [ $RET -ne 0 ]; then
   echo "Tests failed."
   exit 1
fi

# Build our report
LANG=C.UTF-8 PYTHONPATH=$PYTHONPATH coverage combine

# Prepare XML Reference
LANG=C.UTF-8 PYTHONPATH=$PYTHONPATH coverage xml

# Print our report
LANG=C.UTF-8 PYTHONPATH=$PYTHONPATH coverage report --show-missing
