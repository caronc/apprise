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
#
PYTEST=$(which py.test)

# This script can basically be used to test individual tests that have
# been created. Just run the to run all tests:
#    ./devel/test.sh

# to key in on a specific test type:
#     ./devel/test.sh <keyword>

# Absolute path to this script, e.g. /home/user/bin/foo.sh
SCRIPT=$(readlink -f "$0")

# Absolute path this script is in, thus /home/user/bin
SCRIPTPATH=$(dirname "$SCRIPT")

PYTHONPATH=""

if [ -f "$(dirname $SCRIPTPATH)/setup.cfg" ]; then
   PYTHONPATH="$(dirname $SCRIPTPATH)"

elif [ -f "$SCRIPTPATH/setup.cfg" ]; then
   PYTHONPATH="$SCRIPTPATH"

else
   echo "Error: Could not locate apprise setup.cfg file."
   exit 1
fi

if [ ! -x $PYTEST ]; then
   echo "Error: $PYTEST was not found; make sure it is installed: 'pip3 install pytest'"
   exit 1
fi

pushd $PYTHONPATH &>/dev/null
if [ ! -z "$@" ]; then
   LANG=C.UTF-8 PYTHONPATH=$PYTHONPATH $PYTEST -k "$@"
   exit $?

else
   LANG=C.UTF-8 PYTHONPATH=$PYTHONPATH $PYTEST
   exit $?
fi
