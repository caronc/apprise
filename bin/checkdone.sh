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
