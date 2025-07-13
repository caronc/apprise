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

# Disable logging for a cleaner testing output
import logging
import time
from typing import ClassVar
from unittest import mock

import pytest
import requests

from apprise import NotificationManager
from apprise.common import ConfigFormat
from apprise.config.http import ConfigHTTP
from apprise.plugins import NotifyBase

logging.disable(logging.CRITICAL)

# Grant access to our Notification Manager Singleton
N_MGR = NotificationManager()

# Some exception handling we'll use
REQUEST_EXCEPTIONS = (
    requests.ConnectionError(0, "requests.ConnectionError() not handled"),
    requests.RequestException(0, "requests.RequestException() not handled"),
    requests.HTTPError(0, "requests.HTTPError() not handled"),
    requests.ReadTimeout(0, "requests.ReadTimeout() not handled"),
    requests.TooManyRedirects(0, "requests.TooManyRedirects() not handled"),
)


@mock.patch("requests.post")
def test_config_http(mock_post):
    """
    API: ConfigHTTP() object

    """

    # Define our good:// url
    class GoodNotification(NotifyBase):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

        def url(self, **kwargs):
            # Support url() function
            return ""

    # Store our good notification in our schema map
    N_MGR["good"] = GoodNotification

    # Our default content
    default_content = """taga,tagb=good://server01"""

    class DummyResponse:
        """A dummy response used to manage our object."""

        status_code = requests.codes.ok
        headers: ClassVar[dict[str, str]] = {
            "Content-Length": str(len(default_content)),
            "Content-Type": "text/plain",
        }

        text = default_content

        # Pointer to file
        ptr = None

        def close(self):
            return

        def raise_for_status(self):
            return

        def __enter__(self):
            return self

        def __exit__(self, *args, **kwargs):
            return

    # Prepare Mock
    dummy_response = DummyResponse()
    mock_post.return_value = dummy_response

    assert ConfigHTTP.parse_url("garbage://") is None

    results = ConfigHTTP.parse_url("http://user:pass@localhost?+key=value")
    assert isinstance(results, dict)
    ch = ConfigHTTP(**results)
    assert isinstance(ch.url(), str) is True
    assert isinstance(ch.read(), str) is True

    # one entry added
    assert len(ch) == 1

    results = ConfigHTTP.parse_url("http://localhost:8080/path/")
    assert isinstance(results, dict)
    ch = ConfigHTTP(**results)
    assert isinstance(ch.url(), str) is True
    assert isinstance(ch.read(), str) is True

    # one entry added
    assert len(ch) == 1

    # Clear all our mock counters
    mock_post.reset_mock()

    # Cache Handling; cache each request for 30 seconds
    results = ConfigHTTP.parse_url("http://localhost:8080/path/?cache=30")
    assert mock_post.call_count == 0
    assert isinstance(ch.url(), str) is True

    assert isinstance(results, dict)
    ch = ConfigHTTP(**results)
    assert mock_post.call_count == 0

    assert isinstance(ch.url(), str) is True
    assert mock_post.call_count == 0

    assert isinstance(ch.read(), str) is True
    assert mock_post.call_count == 1

    # Clear all our mock counters
    mock_post.reset_mock()

    # Behind the scenes we haven't actually made a fetch yet. We can consider
    # our content expired at this point
    assert ch.expired() is True

    # Test using boolean check; this will force a remote fetch
    assert ch

    # Now a call was made
    assert mock_post.call_count == 1
    mock_post.reset_mock()

    # Our content hasn't expired yet (it's good for 30 seconds)
    assert ch.expired() is False
    assert len(ch) == 1
    assert mock_post.call_count == 0

    # Test using boolean check; we will re-use our cache and not
    # make another remote request
    mock_post.reset_mock()
    assert ch
    assert len(ch.servers()) == 1
    assert len(ch) == 1

    # No remote post has been made
    assert mock_post.call_count == 0

    with mock.patch("time.time", return_value=time.time() + 10):
        # even with 10 seconds elapsed, no fetch will be made
        assert ch.expired() is False
        assert ch
        assert len(ch.servers()) == 1
        assert len(ch) == 1

    # No remote post has been made
    assert mock_post.call_count == 0

    with mock.patch("time.time", return_value=time.time() + 31):
        # but 30+ seconds from now is considered expired
        assert ch.expired() is True
        assert ch
        assert len(ch.servers()) == 1
        assert len(ch) == 1

    # Our content would have been renewed with a single new fetch
    assert mock_post.call_count == 1

    # one entry added
    assert len(ch) == 1

    # Invalid cache
    results = ConfigHTTP.parse_url("http://localhost:8080/path/?cache=False")
    assert isinstance(results, dict)
    assert isinstance(ch.url(), str) is True

    results = ConfigHTTP.parse_url("http://localhost:8080/path/?cache=-10")
    assert isinstance(results, dict)
    with pytest.raises(TypeError):
        ch = ConfigHTTP(**results)

    results = ConfigHTTP.parse_url("http://user@localhost?format=text")
    assert isinstance(results, dict)
    ch = ConfigHTTP(**results)
    assert isinstance(ch.url(), str) is True
    assert isinstance(ch.read(), str) is True

    # one entry added
    assert len(ch) == 1

    results = ConfigHTTP.parse_url("https://localhost")
    assert isinstance(results, dict)
    ch = ConfigHTTP(**results)
    assert isinstance(ch.url(), str) is True
    assert isinstance(ch.read(), str) is True

    # one entry added
    assert len(ch) == 1

    # Testing of pop
    ch = ConfigHTTP(**results)

    ref = ch[0]
    assert isinstance(ref, NotifyBase) is True

    ref_popped = ch.pop(0)
    assert isinstance(ref_popped, NotifyBase) is True

    assert ref == ref_popped

    assert len(ch) == 0

    # reference to calls on initial reference
    ch = ConfigHTTP(**results)
    assert isinstance(ch.pop(0), NotifyBase) is True

    ch = ConfigHTTP(**results)
    assert isinstance(ch[0], NotifyBase) is True
    # Second reference actually uses cache
    assert isinstance(ch[0], NotifyBase) is True

    ch = ConfigHTTP(**results)
    # Itereator creation (nothing needed to assert here)
    iter(ch)
    # Second reference actually uses cache
    iter(ch)

    # Test a buffer size limit reach
    ch.max_buffer_size = len(dummy_response.text)
    assert isinstance(ch.read(), str) is True

    # Test YAML detection
    yaml_supported_types = (
        "text/yaml",
        "text/x-yaml",
        "application/yaml",
        "application/x-yaml",
    )

    for st in yaml_supported_types:
        dummy_response.headers["Content-Type"] = st
        ch.default_config_format = None
        assert isinstance(ch.read(), str) is True
        # Set to YAML
        assert ch.default_config_format == ConfigFormat.YAML

    # Test TEXT detection
    text_supported_types = ("text/plain", "text/html")

    for st in text_supported_types:
        dummy_response.headers["Content-Type"] = st
        ch.default_config_format = None
        assert isinstance(ch.read(), str) is True
        # Set to TEXT
        assert ch.default_config_format == ConfigFormat.TEXT

    # The type is never adjusted to mime types we don't understand
    ukwn_supported_types = ("text/css", "application/zip")

    for st in ukwn_supported_types:
        dummy_response.headers["Content-Type"] = st
        ch.default_config_format = None
        assert isinstance(ch.read(), str) is True
        # Remains unchanged
        assert ch.default_config_format is None

    # When the entry is missing; we handle this too
    del dummy_response.headers["Content-Type"]
    ch.default_config_format = None
    assert isinstance(ch.read(), str) is True
    # Remains unchanged
    assert ch.default_config_format is None

    # Restore our content type object for lower tests
    dummy_response.headers["Content-Type"] = "text/plain"

    # Take a snapshot
    max_buffer_size = ch.max_buffer_size

    ch.max_buffer_size = len(dummy_response.text) - 1
    assert ch.read() is None

    # Restore buffer size count
    ch.max_buffer_size = max_buffer_size

    # Test erroneous Content-Length
    # Our content is still within the limits, so we're okay
    dummy_response.headers["Content-Length"] = "garbage"

    assert isinstance(ch.read(), str) is True

    dummy_response.headers["Content-Length"] = "None"
    # Our content is still within the limits, so we're okay
    assert isinstance(ch.read(), str) is True

    # Handle cases where the content length is exactly at our limit
    dummy_response.text = "a" * ch.max_buffer_size
    # This is acceptable
    assert isinstance(ch.read(), str) is True

    # If we are over our limit though..
    dummy_response.text = "b" * (ch.max_buffer_size + 1)
    assert ch.read() is None

    # Test an invalid return code
    dummy_response.status_code = 400
    assert ch.read() is None
    ch.max_error_buffer_size = 0
    assert ch.read() is None

    # Exception handling
    for _exception in REQUEST_EXCEPTIONS:
        mock_post.side_effect = _exception
        assert ch.read() is None

    # Restore buffer size count
    ch.max_buffer_size = max_buffer_size
