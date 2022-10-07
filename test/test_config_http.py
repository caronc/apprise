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

import time
import pytest
from unittest import mock

import requests
from apprise.common import ConfigFormat
from apprise.config.ConfigHTTP import ConfigHTTP
from apprise.plugins.NotifyBase import NotifyBase
from apprise.common import NOTIFY_SCHEMA_MAP

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)


# Some exception handling we'll use
REQUEST_EXCEPTIONS = (
    requests.ConnectionError(
        0, 'requests.ConnectionError() not handled'),
    requests.RequestException(
        0, 'requests.RequestException() not handled'),
    requests.HTTPError(
        0, 'requests.HTTPError() not handled'),
    requests.ReadTimeout(
        0, 'requests.ReadTimeout() not handled'),
    requests.TooManyRedirects(
        0, 'requests.TooManyRedirects() not handled'),
)


@mock.patch('requests.post')
def test_config_http(mock_post):
    """
    API: ConfigHTTP() object

    """

    # Define our good:// url
    class GoodNotification(NotifyBase):
        def __init__(self, *args, **kwargs):
            super(GoodNotification, self).__init__(*args, **kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

        def url(self, **kwargs):
            # Support url() function
            return ''

    # Store our good notification in our schema map
    NOTIFY_SCHEMA_MAP['good'] = GoodNotification

    # Our default content
    default_content = """taga,tagb=good://server01"""

    class DummyResponse:
        """
        A dummy response used to manage our object
        """
        status_code = requests.codes.ok
        headers = {
            'Content-Length': len(default_content),
            'Content-Type': 'text/plain',
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

    assert ConfigHTTP.parse_url('garbage://') is None

    results = ConfigHTTP.parse_url('http://user:pass@localhost?+key=value')
    assert isinstance(results, dict)
    ch = ConfigHTTP(**results)
    assert isinstance(ch.url(), str) is True
    assert isinstance(ch.read(), str) is True

    # one entry added
    assert len(ch) == 1

    results = ConfigHTTP.parse_url('http://localhost:8080/path/')
    assert isinstance(results, dict)
    ch = ConfigHTTP(**results)
    assert isinstance(ch.url(), str) is True
    assert isinstance(ch.read(), str) is True

    # one entry added
    assert len(ch) == 1

    # Clear all our mock counters
    mock_post.reset_mock()

    # Cache Handling; cache each request for 30 seconds
    results = ConfigHTTP.parse_url('http://localhost:8080/path/?cache=30')
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

    with mock.patch('time.time', return_value=time.time() + 10):
        # even with 10 seconds elapsed, no fetch will be made
        assert ch.expired() is False
        assert ch
        assert len(ch.servers()) == 1
        assert len(ch) == 1

    # No remote post has been made
    assert mock_post.call_count == 0

    with mock.patch('time.time', return_value=time.time() + 31):
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
    results = ConfigHTTP.parse_url('http://localhost:8080/path/?cache=False')
    assert isinstance(results, dict)
    assert isinstance(ch.url(), str) is True

    results = ConfigHTTP.parse_url('http://localhost:8080/path/?cache=-10')
    assert isinstance(results, dict)
    with pytest.raises(TypeError):
        ch = ConfigHTTP(**results)

    results = ConfigHTTP.parse_url('http://user@localhost?format=text')
    assert isinstance(results, dict)
    ch = ConfigHTTP(**results)
    assert isinstance(ch.url(), str) is True
    assert isinstance(ch.read(), str) is True

    # one entry added
    assert len(ch) == 1

    results = ConfigHTTP.parse_url('https://localhost')
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
        'text/yaml', 'text/x-yaml', 'application/yaml', 'application/x-yaml')

    for st in yaml_supported_types:
        dummy_response.headers['Content-Type'] = st
        ch.default_config_format = None
        assert isinstance(ch.read(), str) is True
        # Set to YAML
        assert ch.default_config_format == ConfigFormat.YAML

    # Test TEXT detection
    text_supported_types = ('text/plain', 'text/html')

    for st in text_supported_types:
        dummy_response.headers['Content-Type'] = st
        ch.default_config_format = None
        assert isinstance(ch.read(), str) is True
        # Set to TEXT
        assert ch.default_config_format == ConfigFormat.TEXT

    # The type is never adjusted to mime types we don't understand
    ukwn_supported_types = ('text/css', 'application/zip')

    for st in ukwn_supported_types:
        dummy_response.headers['Content-Type'] = st
        ch.default_config_format = None
        assert isinstance(ch.read(), str) is True
        # Remains unchanged
        assert ch.default_config_format is None

    # When the entry is missing; we handle this too
    del dummy_response.headers['Content-Type']
    ch.default_config_format = None
    assert isinstance(ch.read(), str) is True
    # Remains unchanged
    assert ch.default_config_format is None

    # Restore our content type object for lower tests
    dummy_response.headers['Content-Type'] = 'text/plain'

    # Take a snapshot
    max_buffer_size = ch.max_buffer_size

    ch.max_buffer_size = len(dummy_response.text) - 1
    assert ch.read() is None

    # Restore buffer size count
    ch.max_buffer_size = max_buffer_size

    # Test erroneous Content-Length
    # Our content is still within the limits, so we're okay
    dummy_response.headers['Content-Length'] = 'garbage'

    assert isinstance(ch.read(), str) is True

    dummy_response.headers['Content-Length'] = 'None'
    # Our content is still within the limits, so we're okay
    assert isinstance(ch.read(), str) is True

    # Handle cases where the content length is exactly at our limit
    dummy_response.text = 'a' * ch.max_buffer_size
    # This is acceptable
    assert isinstance(ch.read(), str) is True

    # If we are over our limit though..
    dummy_response.text = 'b' * (ch.max_buffer_size + 1)
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
