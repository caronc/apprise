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

# Absolute path to this script, e.g. /home/user/bin/foo.sh
SCRIPT=$(readlink -f "$0")

# Absolute path this script is in, thus /home/user/bin
SCRIPTPATH=$(dirname "$SCRIPT")

FOUNDROOT=1
if [ -f "$(dirname $SCRIPTPATH)/setup.cfg" ]; then
   pushd "$(dirname $SCRIPTPATH)" &>/dev/null
   FOUNDROOT=$?

elif [ -f "$SCRIPTPATH/setup.cfg" ]; then
   pushd "$SCRIPTPATH" &>/dev/null
   FOUNDROOT=$?

fi

if [ $FOUNDROOT -ne 0 ]; then
   echo "Error: Could not locate apprise setup.cfg file."
   exit 1
fi

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
flake8 . --show-source --statistics
if [ $? -ne 0 ]; then
   echo "PEP8 check failed"
   exit 1
fi
echo "PEP8 check succeeded; no errors found! :)"
echo

# Run our unit test coverage check
echo "Running test coverage check..."
coverage run -m pytest -vv
if [ $? -ne 0 ]; then
   echo "Tests failed."
   exit 1
fi

# Print our report
coverage report --show-missing
