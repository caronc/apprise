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
import os
import pytest
import requests
from unittest import mock

from apprise import Apprise
from apprise import AppriseAsset
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


def test_apprise_log_memory_captures():
    """
    API: Apprise() Log Memory Captures

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


def test_apprise_log_file_captures(tmpdir):
    """
    API: Apprise() Log File Captures

    """

    # Ensure we're not running in a disabled state
    logging.disable(logging.NOTSET)

    log_file = tmpdir.join('capture.log')
    assert not os.path.isfile(str(log_file))

    logger.setLevel(logging.CRITICAL)
    with LogCapture(path=str(log_file), level=logging.TRACE) as fp:
        # The file will exit now
        assert os.path.isfile(str(log_file))

        logger.trace("trace")
        logger.debug("debug")
        logger.info("info")
        logger.warning("warning")
        logger.error("error")
        logger.deprecate("deprecate")

        content = fp.read().rstrip()
        logs = re.split(r'\r*\n', content)

        # We have a log entry for each of the 6 logs we generated above
        assert 'trace' in content
        assert 'debug' in content
        assert 'info' in content
        assert 'warning' in content
        assert 'error' in content
        assert 'deprecate' in content
        assert len(logs) == 6

    # The file is automatically cleaned up afterwards
    assert not os.path.isfile(str(log_file))

    # Verify that we did not lose our effective log level even though
    # the above steps the level up for the duration of the capture
    assert logger.getEffectiveLevel() == logging.CRITICAL

    logger.setLevel(logging.TRACE)
    with LogCapture(path=str(log_file), level=logging.DEBUG) as fp:
        # The file will exit now
        assert os.path.isfile(str(log_file))

        logger.trace("trace")
        logger.debug("debug")
        logger.info("info")
        logger.warning("warning")
        logger.error("error")
        logger.deprecate("deprecate")

        content = fp.read().rstrip()
        logs = re.split(r'\r*\n', content)

        # We have a log entry for 5 of the log entries we generated above
        # There will be no 'trace' entry
        assert 'trace' not in content
        assert 'debug' in content
        assert 'info' in content
        assert 'warning' in content
        assert 'error' in content
        assert 'deprecate' in content

        assert len(logs) == 5

        # Remove our file before we exit the with clause
        # this causes our delete() call to throw gracefully inside
        os.unlink(str(log_file))

        # Verify file is gone
        assert not os.path.isfile(str(log_file))

    # Verify that we did not lose our effective log level even though
    # the above steps the level up for the duration of the capture
    assert logger.getEffectiveLevel() == logging.TRACE

    logger.setLevel(logging.ERROR)
    with LogCapture(path=str(log_file), delete=False,
                    level=logging.WARNING) as fp:

        # Verify exists
        assert os.path.isfile(str(log_file))

        logger.trace("trace")
        logger.debug("debug")
        logger.info("info")
        logger.warning("warning")
        logger.error("error")
        logger.deprecate("deprecate")

        content = fp.read().rstrip()
        logs = re.split(r'\r*\n', content)

        # We have a log entry for 3 of the log entries we generated above
        # There will be no 'trace', 'debug', or 'info' entry
        assert 'trace' not in content
        assert 'debug' not in content
        assert 'info' not in content
        assert 'warning' in content
        assert 'error' in content
        assert 'deprecate' in content

        assert len(logs) == 3

    # Verify the file still exists (because delete was set to False)
    assert os.path.isfile(str(log_file))

    # remove it now
    os.unlink(str(log_file))

    # Enure it's been removed
    assert not os.path.isfile(str(log_file))

    # Set a global level of ERROR
    logger.setLevel(logging.ERROR)

    # Test case where we can't open the file
    with mock.patch('builtins.open', side_effect=OSError()):
        # Use the default level of None (by not specifying one); we then
        # use whatever has been defined globally
        with pytest.raises(OSError):
            with LogCapture(path=str(log_file)) as fp:
                # we'll never get here because we'll fail to open the file
                pass

    # Disable Logging
    logging.disable(logging.CRITICAL)


@mock.patch('requests.post')
def test_apprise_secure_logging(mock_post):
    """
    API: Apprise() secure logging tests
    """

    # Ensure we're not running in a disabled state
    logging.disable(logging.NOTSET)

    logger.setLevel(logging.CRITICAL)

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    # Default Secure Logging is set to enabled
    asset = AppriseAsset()
    assert asset.secure_logging is True

    # Load our asset
    a = Apprise(asset=asset)

    with LogCapture(level=logging.DEBUG) as stream:
        # add a test server
        assert a.add("json://user:pass1$-3!@localhost") is True

        # Our servers should carry this flag
        a[0].asset.secure_logging is True

        logs = re.split(r'\r*\n', stream.getvalue().rstrip())
        assert len(logs) == 1
        entry = re.split(r'\s-\s', logs[0])
        assert len(entry) == 3
        assert entry[1] == 'DEBUG'
        assert entry[2].startswith(
            'Loaded JSON URL: json://user:****@localhost/')

    # Send notification
    assert a.notify("test") is True

    # Test our call count
    assert mock_post.call_count == 1

    # Reset
    mock_post.reset_mock()

    # Now we test the reverse configuration and turn off
    # secure logging.

    # Default Secure Logging is set to disable
    asset = AppriseAsset(secure_logging=False)
    assert asset.secure_logging is False

    # Load our asset
    a = Apprise(asset=asset)

    with LogCapture(level=logging.DEBUG) as stream:
        # add a test server
        assert a.add("json://user:pass1$-3!@localhost") is True

        # Our servers should carry this flag
        a[0].asset.secure_logging is False

        logs = re.split(r'\r*\n', stream.getvalue().rstrip())
        assert len(logs) == 1
        entry = re.split(r'\s-\s', logs[0])
        assert len(entry) == 3
        assert entry[1] == 'DEBUG'

        # Note that our password is no longer escaped (it is however
        # url encoded)
        assert entry[2].startswith(
            'Loaded JSON URL: json://user:pass1%24-3%21@localhost/')

    # Disable Logging
    logging.disable(logging.CRITICAL)
