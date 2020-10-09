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
from io import StringIO

# The root identifier needed to monitor 'apprise' logging
LOGGER_NAME = 'apprise'

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

# Create ourselve a generic (singleton) logging reference
logger = logging.getLogger(LOGGER_NAME)


class LogCapture(object):
    """
    A class used to allow one to instantiate loggers that write to
    memory for temporary purposes. e.g.:

       1.  with LogCapture() as captured:
       2.
       3.      # Send our notification(s)
       4.      aobj.notify("hello world")
       5.
       6.      # retrieve our logs produced by the above call via our
       7.      # `captured` StringIO object we have access to within the `with`
       8.      # block here:
       9.      print(captured.getvalue())

    """
    def __init__(self, level=None, name=LOGGER_NAME,
                 fmt='%(asctime)s - %(thread)d - %(levelname)s - %(message)s'):
        """
        Instantiate a temporary log capture object

        You can optionally specify a logging level such as logging.INFO if you
        wish, otherwise by default the script uses whatever logging has been
        set globally.

        Optionally over-ride the fmt as well if you wish.

        """
        # Our memory buffer placeholder
        self.__mem_buffer = StringIO()

        # Our logging level tracking
        self.__level = level
        self.__restore_level = None

        # Acquire a pointer to our logger
        self.__logger = logging.getLogger(name)

        # Prepare our handler
        self.__handler = logging.StreamHandler(self.__mem_buffer)

        # Use the specified level, otherwise take on the already
        # effective level of our logger
        self.__handler.setLevel(
            self.__level if self.__level is not None
            else self.__logger.getEffectiveLevel())

        # Prepare our formatter
        self.__handler.setFormatter(logging.Formatter(fmt))

    def __enter__(self):
        """
        Allows logger manipulation within a 'with' block
        """

        if self.__level is not None:
            # Temporary adjust our log level if required
            self.__restore_level = self.__logger.getEffectiveLevel()
            if self.__restore_level > self.__level:
                # Bump our log level up for the duration of our `with`
                self.__logger.setLevel(self.__level)

            else:
                # No restoration required
                self.__restore_level = None

        else:
            # Do nothing but enforce that we have nothing to restore to
            self.__restore_level = None

        # Add our handler
        self.__logger.addHandler(self.__handler)

        # return our memory pointer
        return self.__mem_buffer

    def __exit__(self, exc_type, exc_value, tb):
        """
        removes the handler gracefully when the with block has completed
        """

        # Flush our content
        self.__handler.flush()
        self.__mem_buffer.flush()

        # Drop our handler
        self.__logger.removeHandler(self.__handler)

        if self.__restore_level is not None:
            # Restore level
            self.__logger.setLevel(self.__restore_level)

        if exc_type is not None:
            # pass exception on if one was generated
            return False

        return True
