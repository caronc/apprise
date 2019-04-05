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

import six
import mock
import requests
from apprise.common import ConfigFormat
from apprise.config.ConfigHTTP import ConfigHTTP
from apprise.plugins.NotifyBase import NotifyBase
from apprise.plugins import SCHEMA_MAP

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


@mock.patch('requests.get')
@mock.patch('requests.post')
def test_config_http(mock_post, mock_get):
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

        def url(self):
            # Support url() function
            return ''

    # Store our good notification in our schema map
    SCHEMA_MAP['good'] = GoodNotification

    # Prepare Mock
    dummy_request = mock.Mock()
    dummy_request.close.return_value = True
    dummy_request.status_code = requests.codes.ok
    dummy_request.content = """
    taga,tagb=good://server01
    """
    dummy_request.headers = {
        'Content-Length': len(dummy_request.content),
        'Content-Type': 'text/plain',
    }

    mock_post.return_value = dummy_request
    mock_get.return_value = dummy_request

    assert ConfigHTTP.parse_url('garbage://') is None

    results = ConfigHTTP.parse_url('http://user:pass@localhost?+key=value')
    assert isinstance(results, dict)
    ch = ConfigHTTP(**results)
    assert isinstance(ch.url(), six.string_types) is True
    assert isinstance(ch.read(), six.string_types) is True

    # one entry added
    assert len(ch) == 1

    results = ConfigHTTP.parse_url('http://localhost:8080/path/')
    assert isinstance(results, dict)
    ch = ConfigHTTP(**results)
    assert isinstance(ch.url(), six.string_types) is True
    assert isinstance(ch.read(), six.string_types) is True

    # one entry added
    assert len(ch) == 1

    results = ConfigHTTP.parse_url('http://user@localhost?format=text')
    assert isinstance(results, dict)
    ch = ConfigHTTP(**results)
    assert isinstance(ch.url(), six.string_types) is True
    assert isinstance(ch.read(), six.string_types) is True

    # one entry added
    assert len(ch) == 1

    results = ConfigHTTP.parse_url('https://localhost')
    assert isinstance(results, dict)
    ch = ConfigHTTP(**results)
    assert isinstance(ch.url(), six.string_types) is True
    assert isinstance(ch.read(), six.string_types) is True

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
    ch.max_buffer_size = len(dummy_request.content)
    assert isinstance(ch.read(), six.string_types) is True

    # Test YAML detection
    yaml_supported_types = (
        'text/yaml', 'text/x-yaml', 'application/yaml', 'application/x-yaml')

    for st in yaml_supported_types:
        dummy_request.headers['Content-Type'] = st
        ch.default_config_format = None
        assert isinstance(ch.read(), six.string_types) is True
        # Set to YAML
        assert ch.default_config_format == ConfigFormat.YAML

    # Test TEXT detection
    text_supported_types = ('text/plain', 'text/html')

    for st in text_supported_types:
        dummy_request.headers['Content-Type'] = st
        ch.default_config_format = None
        assert isinstance(ch.read(), six.string_types) is True
        # Set to TEXT
        assert ch.default_config_format == ConfigFormat.TEXT

    # The type is never adjusted to mime types we don't understand
    ukwn_supported_types = ('text/css', 'application/zip')

    for st in ukwn_supported_types:
        dummy_request.headers['Content-Type'] = st
        ch.default_config_format = None
        assert isinstance(ch.read(), six.string_types) is True
        # Remains unchanged
        assert ch.default_config_format is None

    # When the entry is missing; we handle this too
    del dummy_request.headers['Content-Type']
    ch.default_config_format = None
    assert isinstance(ch.read(), six.string_types) is True
    # Remains unchanged
    assert ch.default_config_format is None

    # Restore our content type object for lower tests
    dummy_request.headers['Content-Type'] = 'text/plain'

    ch.max_buffer_size = len(dummy_request.content) - 1
    assert ch.read() is None

    # Test an invalid return code
    dummy_request.status_code = 400
    assert ch.read() is None
    ch.max_error_buffer_size = 0
    assert ch.read() is None

    # Exception handling
    for _exception in REQUEST_EXCEPTIONS:
        mock_post.side_effect = _exception
        mock_get.side_effect = _exception
        assert ch.read() is None
