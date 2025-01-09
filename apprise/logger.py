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

import os
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


class LogCapture:
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
    def __init__(self, path=None, level=None, name=LOGGER_NAME, delete=True,
                 fmt='%(asctime)s - %(levelname)s - %(message)s'):
        """
        Instantiate a temporary log capture object

        If a path is specified, then log content is sent to that file instead
        of a StringIO object.

        You can optionally specify a logging level such as logging.INFO if you
        wish, otherwise by default the script uses whatever logging has been
        set globally. If you set delete to `False` then when using log files,
        they are not automatically cleaned up afterwards.

        Optionally over-ride the fmt as well if you wish.

        """
        # Our memory buffer placeholder
        self.__buffer_ptr = StringIO()

        # Store our file path as it will determine whether or not we write to
        # memory and a file
        self.__path = path
        self.__delete = delete

        # Our logging level tracking
        self.__level = level
        self.__restore_level = None

        # Acquire a pointer to our logger
        self.__logger = logging.getLogger(name)

        # Prepare our handler
        self.__handler = logging.StreamHandler(self.__buffer_ptr) \
            if not self.__path else logging.FileHandler(
                self.__path, mode='a', encoding='utf-8')

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

        if self.__path:
            # If a path has been identified, ensure we can write to the path
            # and that the file exists
            with open(self.__path, 'a'):
                os.utime(self.__path, None)

            # Update our buffer pointer
            self.__buffer_ptr = open(self.__path, 'r')

        # Add our handler
        self.__logger.addHandler(self.__handler)

        # return our memory pointer
        return self.__buffer_ptr

    def __exit__(self, exc_type, exc_value, tb):
        """
        removes the handler gracefully when the with block has completed
        """

        # Flush our content
        self.__handler.flush()
        self.__buffer_ptr.flush()

        # Drop our handler
        self.__logger.removeHandler(self.__handler)

        if self.__restore_level is not None:
            # Restore level
            self.__logger.setLevel(self.__restore_level)

        if self.__path:
            # Close our file pointer
            self.__buffer_ptr.close()
            self.__handler.close()
            if self.__delete:
                try:
                    # Always remove file afterwards
                    os.unlink(self.__path)

                except OSError:
                    # It's okay if the file does not exist
                    pass

        if exc_type is not None:
            # pass exception on if one was generated
            return False

        return True
