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

import re
import sys
import mock
import pytest
from apprise import Apprise
from apprise import URLBase
from apprise.logger import LogCapture

# Disable logging for a cleaner testing output
from apprise.logger import logging
from apprise.logger import logger


def test_apprise_logger():
    """
    API: Apprise() Logger

    """

    # Ensure we're not running in a disabled state
    logging.disable(logging.NOTSET)

    # Set our log level
    URLBase.logger.setLevel(logging.DEPRECATE + 1)

    # Deprication will definitely not trigger
    URLBase.logger.deprecate('test')

    # Verbose Debugging is not on at this point
    URLBase.logger.trace('test')

    # Set both logging entries on
    URLBase.logger.setLevel(logging.TRACE)

    # Deprication will definitely trigger
    URLBase.logger.deprecate('test')

    # Verbose Debugging will activate
    URLBase.logger.trace('test')

    # Disable Logging
    logging.disable(logging.CRITICAL)


@pytest.mark.skipif(sys.version_info.major <= 2, reason="Requires Python 3.x+")
def test_apprise_log_captures_py3():
    """
    API: Apprise() Python v3 Log Captures

    """

    # Ensure we're not running in a disabled state
    logging.disable(logging.NOTSET)

    logger.setLevel(logging.CRITICAL)
    with LogCapture(level=logging.TRACE) as stream:
        logger.trace("trace")
        logger.debug("debug")
        logger.info("info")
        logger.warning("warning")
        logger.error("error")
        logger.deprecate("deprecate")

        logs = re.split(r'\r*\n', stream.getvalue().rstrip())

        # We have a log entry for each of the 6 logs we generated above
        assert 'trace' in stream.getvalue()
        assert 'debug' in stream.getvalue()
        assert 'info' in stream.getvalue()
        assert 'warning' in stream.getvalue()
        assert 'error' in stream.getvalue()
        assert 'deprecate' in stream.getvalue()
        assert len(logs) == 6

    # Verify that we did not lose our effective log level even though
    # the above steps the level up for the duration of the capture
    assert logger.getEffectiveLevel() == logging.CRITICAL

    logger.setLevel(logging.TRACE)
    with LogCapture(level=logging.DEBUG) as stream:
        logger.trace("trace")
        logger.debug("debug")
        logger.info("info")
        logger.warning("warning")
        logger.error("error")
        logger.deprecate("deprecate")

        # We have a log entry for 5 of the log entries we generated above
        # There will be no 'trace' entry
        assert 'trace' not in stream.getvalue()
        assert 'debug' in stream.getvalue()
        assert 'info' in stream.getvalue()
        assert 'warning' in stream.getvalue()
        assert 'error' in stream.getvalue()
        assert 'deprecate' in stream.getvalue()

        logs = re.split(r'\r*\n', stream.getvalue().rstrip())
        assert len(logs) == 5

    # Verify that we did not lose our effective log level even though
    # the above steps the level up for the duration of the capture
    assert logger.getEffectiveLevel() == logging.TRACE

    logger.setLevel(logging.ERROR)
    with LogCapture(level=logging.WARNING) as stream:
        logger.trace("trace")
        logger.debug("debug")
        logger.info("info")
        logger.warning("warning")
        logger.error("error")
        logger.deprecate("deprecate")

        # We have a log entry for 3 of the log entries we generated above
        # There will be no 'trace', 'debug', or 'info' entry
        assert 'trace' not in stream.getvalue()
        assert 'debug' not in stream.getvalue()
        assert 'info' not in stream.getvalue()
        assert 'warning' in stream.getvalue()
        assert 'error' in stream.getvalue()
        assert 'deprecate' in stream.getvalue()

        logs = re.split(r'\r*\n', stream.getvalue().rstrip())
        assert len(logs) == 3

    # Set a global level of ERROR
    logger.setLevel(logging.ERROR)

    # Use the default level of None (by not specifying one); we then
    # use whatever has been defined globally
    with LogCapture() as stream:
        logger.trace("trace")
        logger.debug("debug")
        logger.info("info")
        logger.warning("warning")
        logger.error("error")
        logger.deprecate("deprecate")

        assert 'trace' not in stream.getvalue()
        assert 'debug' not in stream.getvalue()
        assert 'info' not in stream.getvalue()
        assert 'warning' not in stream.getvalue()
        assert 'error' in stream.getvalue()
        assert 'deprecate' in stream.getvalue()

        logs = re.split(r'\r*\n', stream.getvalue().rstrip())
        assert len(logs) == 2

    # Verify that we did not lose our effective log level
    assert logger.getEffectiveLevel() == logging.ERROR

    with LogCapture(level=logging.TRACE) as stream:
        logger.trace("trace")
        logger.debug("debug")
        logger.info("info")
        logger.warning("warning")
        logger.error("error")
        logger.deprecate("deprecate")

        # We have a log entry for each of the 6 logs we generated above
        assert 'trace' in stream.getvalue()
        assert 'debug' in stream.getvalue()
        assert 'info' in stream.getvalue()
        assert 'warning' in stream.getvalue()
        assert 'error' in stream.getvalue()
        assert 'deprecate' in stream.getvalue()

        logs = re.split(r'\r*\n', stream.getvalue().rstrip())
        assert len(logs) == 6

    # Verify that we did not lose our effective log level even though
    # the above steps the level up for the duration of the capture
    assert logger.getEffectiveLevel() == logging.ERROR

    # Test capture where our notification throws an unhandled exception
    obj = Apprise.instantiate('json://user:password@example.com')
    with mock.patch('requests.post', side_effect=NotImplementedError()):
        with pytest.raises(NotImplementedError):
            # Our exception gets caught in side our with() block
            # and although raised, all graceful handling of the log
            # is reverted as it was
            with LogCapture(level=logging.TRACE) as stream:
                obj.send("hello world")

    # Disable Logging
    logging.disable(logging.CRITICAL)


@pytest.mark.skipif(sys.version_info.major >= 3, reason="Requires Python 2.x+")
def test_apprise_log_captures_py2():
    """
    API: Apprise() Python v2 Log Captures

    """

    # Ensure we're not running in a disabled state
    logging.disable(logging.NOTSET)

    logger.setLevel(logging.CRITICAL)
    with LogCapture(level=logging.TRACE) as stream:
        logger.trace(u"trace")
        logger.debug(u"debug")
        logger.info(u"info")
        logger.warning(u"warning")
        logger.error(u"error")
        logger.deprecate(u"deprecate")

        logs = re.split(r'\r*\n', stream.getvalue().rstrip())

        # We have a log entry for each of the 6 logs we generated above
        assert 'trace' in stream.getvalue()
        assert 'debug' in stream.getvalue()
        assert 'info' in stream.getvalue()
        assert 'warning' in stream.getvalue()
        assert 'error' in stream.getvalue()
        assert 'deprecate' in stream.getvalue()
        assert len(logs) == 6

    # Verify that we did not lose our effective log level even though
    # the above steps the level up for the duration of the capture
    assert logger.getEffectiveLevel() == logging.CRITICAL

    logger.setLevel(logging.TRACE)
    with LogCapture(level=logging.DEBUG) as stream:
        logger.trace(u"trace")
        logger.debug(u"debug")
        logger.info(u"info")
        logger.warning(u"warning")
        logger.error(u"error")
        logger.deprecate(u"deprecate")

        # We have a log entry for 5 of the log entries we generated above
        # There will be no 'trace' entry
        assert 'trace' not in stream.getvalue()
        assert 'debug' in stream.getvalue()
        assert 'info' in stream.getvalue()
        assert 'warning' in stream.getvalue()
        assert 'error' in stream.getvalue()
        assert 'deprecate' in stream.getvalue()

        logs = re.split(r'\r*\n', stream.getvalue().rstrip())
        assert len(logs) == 5

    # Verify that we did not lose our effective log level even though
    # the above steps the level up for the duration of the capture
    assert logger.getEffectiveLevel() == logging.TRACE

    logger.setLevel(logging.ERROR)
    with LogCapture(level=logging.WARNING) as stream:
        logger.trace(u"trace")
        logger.debug(u"debug")
        logger.info(u"info")
        logger.warning(u"warning")
        logger.error(u"error")
        logger.deprecate(u"deprecate")

        # We have a log entry for 3 of the log entries we generated above
        # There will be no 'trace', 'debug', or 'info' entry
        assert 'trace' not in stream.getvalue()
        assert 'debug' not in stream.getvalue()
        assert 'info' not in stream.getvalue()
        assert 'warning' in stream.getvalue()
        assert 'error' in stream.getvalue()
        assert 'deprecate' in stream.getvalue()

        logs = re.split(r'\r*\n', stream.getvalue().rstrip())
        assert len(logs) == 3

    # Set a global level of ERROR
    logger.setLevel(logging.ERROR)

    # Use the default level of None (by not specifying one); we then
    # use whatever has been defined globally
    with LogCapture() as stream:
        logger.trace(u"trace")
        logger.debug(u"debug")
        logger.info(u"info")
        logger.warning(u"warning")
        logger.error(u"error")
        logger.deprecate(u"deprecate")

        assert 'trace' not in stream.getvalue()
        assert 'debug' not in stream.getvalue()
        assert 'info' not in stream.getvalue()
        assert 'warning' not in stream.getvalue()
        assert 'error' in stream.getvalue()
        assert 'deprecate' in stream.getvalue()

        logs = re.split(r'\r*\n', stream.getvalue().rstrip())
        assert len(logs) == 2

    # Verify that we did not lose our effective log level
    assert logger.getEffectiveLevel() == logging.ERROR

    with LogCapture(level=logging.TRACE) as stream:
        logger.trace(u"trace")
        logger.debug(u"debug")
        logger.info(u"info")
        logger.warning(u"warning")
        logger.error(u"error")
        logger.deprecate(u"deprecate")

        # We have a log entry for each of the 6 logs we generated above
        assert 'trace' in stream.getvalue()
        assert 'debug' in stream.getvalue()
        assert 'info' in stream.getvalue()
        assert 'warning' in stream.getvalue()
        assert 'error' in stream.getvalue()
        assert 'deprecate' in stream.getvalue()

        logs = re.split(r'\r*\n', stream.getvalue().rstrip())
        assert len(logs) == 6

    # Verify that we did not lose our effective log level even though
    # the above steps the level up for the duration of the capture
    assert logger.getEffectiveLevel() == logging.ERROR

    # Test capture where our notification throws an unhandled exception
    obj = Apprise.instantiate('json://user:password@example.com')
    with mock.patch('requests.post', side_effect=NotImplementedError()):
        with pytest.raises(NotImplementedError):
            # Our exception gets caught in side our with() block
            # and although raised, all graceful handling of the log
            # is reverted as it was
            with LogCapture(level=logging.TRACE) as stream:
                obj.send("hello world")

    # Disable Logging
    logging.disable(logging.CRITICAL)
