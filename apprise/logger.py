# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 Chris Caron <lead2gold@gmail.com>
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

import logging

# Define a verbosity level that is a noisier then debug mode
logging.TRACE = logging.DEBUG - 1

# Define a verbosity level that is always used even when no verbosity is set
# from the command line.  The idea here is to allow for deprecation notices
logging.DEPRECATE = logging.ERROR + 1

# Assign our Levels into our logging object
logging.addLevelName(logging.DEPRECATE, "DEPRECATION WARNING")
logging.addLevelName(logging.TRACE, "TRACE")


def trace(self, message, *args, **kwargs):
    """
    Verbose Debug Logging - Trace
    """
    if self.isEnabledFor(logging.TRACE):
        self._log(logging.TRACE, message, args, **kwargs)


def deprecate(self, message, *args, **kwargs):
    """
    Deprication Warning Logging
    """
    if self.isEnabledFor(logging.DEPRECATE):
        self._log(logging.DEPRECATE, message, args, **kwargs)


# Assign our Loggers for use in Apprise
logging.Logger.trace = trace
logging.Logger.deprecate = deprecate

# Create ourselve a generic logging reference
logger = logging.getLogger('apprise')
