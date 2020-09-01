#!/bin/sh
# Copyright (C) 2020 Chris Caron <lead2gold@gmail.com>
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
