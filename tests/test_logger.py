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
import re
import sys
from unittest import mock

import pytest
import requests

from apprise import Apprise, AppriseAsset, URLBase

# Disable logging for a cleaner testing output
from apprise.logger import LogCapture, logger, logging


def test_apprise_logger():
    """
    API: Apprise() Logger

    """

    # Ensure we're not running in a disabled state
    logging.disable(logging.NOTSET)

    # Set our log level
    URLBase.logger.setLevel(logging.DEPRECATE + 1)

    # Deprication will definitely not trigger
    URLBase.logger.deprecate("test")

    # Verbose Debugging is not on at this point
    URLBase.logger.trace("test")

    # Set both logging entries on
    URLBase.logger.setLevel(logging.TRACE)

    # Deprication will definitely trigger
    URLBase.logger.deprecate("test")

    # Verbose Debugging will activate
    URLBase.logger.trace("test")

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

        logs = re.split(r"\r*\n", stream.getvalue().rstrip())

        # We have a log entry for each of the 6 logs we generated above
        assert "trace" in stream.getvalue()
        assert "debug" in stream.getvalue()
        assert "info" in stream.getvalue()
        assert "warning" in stream.getvalue()
        assert "error" in stream.getvalue()
        assert "deprecate" in stream.getvalue()
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
        assert "trace" not in stream.getvalue()
        assert "debug" in stream.getvalue()
        assert "info" in stream.getvalue()
        assert "warning" in stream.getvalue()
        assert "error" in stream.getvalue()
        assert "deprecate" in stream.getvalue()

        logs = re.split(r"\r*\n", stream.getvalue().rstrip())
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
        assert "trace" not in stream.getvalue()
        assert "debug" not in stream.getvalue()
        assert "info" not in stream.getvalue()
        assert "warning" in stream.getvalue()
        assert "error" in stream.getvalue()
        assert "deprecate" in stream.getvalue()

        logs = re.split(r"\r*\n", stream.getvalue().rstrip())
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

        assert "trace" not in stream.getvalue()
        assert "debug" not in stream.getvalue()
        assert "info" not in stream.getvalue()
        assert "warning" not in stream.getvalue()
        assert "error" in stream.getvalue()
        assert "deprecate" in stream.getvalue()

        logs = re.split(r"\r*\n", stream.getvalue().rstrip())
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
        assert "trace" in stream.getvalue()
        assert "debug" in stream.getvalue()
        assert "info" in stream.getvalue()
        assert "warning" in stream.getvalue()
        assert "error" in stream.getvalue()
        assert "deprecate" in stream.getvalue()

        logs = re.split(r"\r*\n", stream.getvalue().rstrip())
        assert len(logs) == 6

    # Verify that we did not lose our effective log level even though
    # the above steps the level up for the duration of the capture
    assert logger.getEffectiveLevel() == logging.ERROR

    # Test capture where our notification throws an unhandled exception
    obj = Apprise.instantiate("json://user:password@example.com")
    with (
        mock.patch("requests.post", side_effect=NotImplementedError()),
        pytest.raises(NotImplementedError),
        # Our exception gets caught in side our with() block
        # and although raised, all graceful handling of the log
        # is reverted as it was
        LogCapture(level=logging.TRACE) as stream,
    ):
        obj.send("hello world")

    # Disable Logging
    logging.disable(logging.CRITICAL)


def test_apprise_log_file_captures(tmpdir):
    """
    API: Apprise() Log File Captures

    """

    # Ensure we're not running in a disabled state
    logging.disable(logging.NOTSET)

    log_file = tmpdir.join("capture.log")
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
        logs = re.split(r"\r*\n", content)

        # We have a log entry for each of the 6 logs we generated above
        assert "trace" in content
        assert "debug" in content
        assert "info" in content
        assert "warning" in content
        assert "error" in content
        assert "deprecate" in content
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
        logs = re.split(r"\r*\n", content)

        # We have a log entry for 5 of the log entries we generated above
        # There will be no 'trace' entry
        assert "trace" not in content
        assert "debug" in content
        assert "info" in content
        assert "warning" in content
        assert "error" in content
        assert "deprecate" in content

        assert len(logs) == 5

        # Concurrent file access is not possible on Windows.
        # PermissionError: [WinError 32] The process cannot access the file
        # because it is being used by another process.
        if sys.platform != "win32":
            # Remove our file before we exit the with clause
            # this causes our delete() call to throw gracefully inside
            os.unlink(str(log_file))

            # Verify file is gone
            assert not os.path.isfile(str(log_file))

    # Verify that we did not lose our effective log level even though
    # the above steps the level up for the duration of the capture
    assert logger.getEffectiveLevel() == logging.TRACE

    logger.setLevel(logging.ERROR)
    with LogCapture(
        path=str(log_file), delete=False, level=logging.WARNING
    ) as fp:

        # Verify exists
        assert os.path.isfile(str(log_file))

        logger.trace("trace")
        logger.debug("debug")
        logger.info("info")
        logger.warning("warning")
        logger.error("error")
        logger.deprecate("deprecate")

        content = fp.read().rstrip()
        logs = re.split(r"\r*\n", content)

        # We have a log entry for 3 of the log entries we generated above
        # There will be no 'trace', 'debug', or 'info' entry
        assert "trace" not in content
        assert "debug" not in content
        assert "info" not in content
        assert "warning" in content
        assert "error" in content
        assert "deprecate" in content

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
    with (
        mock.patch("builtins.open", side_effect=OSError()),
        # Use the default level of None (by not specifying one); we then
        # use whatever has been defined globally
        pytest.raises(OSError),
        LogCapture(path=str(log_file)) as fp,
    ):

        # we'll never get here because we'll fail to open the file
        pass

    # Disable Logging
    logging.disable(logging.CRITICAL)


@mock.patch("requests.post")
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
        assert a[0].asset.secure_logging is True

        logs = re.split(r"\r*\n", stream.getvalue().rstrip())
        assert len(logs) == 1
        entry = re.split(r"\s-\s", logs[0])
        assert len(entry) == 3
        assert entry[1] == "DEBUG"
        assert entry[2].startswith(
            "Loaded JSON URL: json://user:****@localhost/"
        )

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
        assert a[0].asset.secure_logging is False

        logs = re.split(r"\r*\n", stream.getvalue().rstrip())
        assert len(logs) == 1
        entry = re.split(r"\s-\s", logs[0])
        assert len(entry) == 3
        assert entry[1] == "DEBUG"

        # Note that our password is no longer escaped (it is however
        # url encoded)
        assert entry[2].startswith(
            "Loaded JSON URL: json://user:pass1%24-3%21@localhost/"
        )

    # Disable Logging
    logging.disable(logging.CRITICAL)
