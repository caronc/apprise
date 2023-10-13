#!/bin/bash
# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2023, Chris Caron <lead2gold@gmail.com>
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
