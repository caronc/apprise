# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Chris Caron <lead2gold@gmail.com>
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
import os
import sys
import json
from unittest import mock

import requests
from apprise import Apprise
from apprise import AppriseAttachment
from apprise import NotifyType

from apprise.plugins.NotifyJSON import NotifyJSON
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), 'var')

# Our Testing URLs
apprise_url_tests = (
    ('json://:@/', {
        'instance': None,
    }),
    ('json://', {
        'instance': None,
    }),
    ('jsons://', {
        'instance': None,
    }),
    ('json://localhost', {
        'instance': NotifyJSON,
    }),
    ('json://user@localhost?method=invalid', {
        'instance': TypeError,
    }),
    ('json://user:pass@localhost', {
        'instance': NotifyJSON,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'json://user:****@localhost',
    }),
    ('json://user@localhost', {
        'instance': NotifyJSON,
    }),

    # Test method variations
    ('json://user@localhost?method=put', {
        'instance': NotifyJSON,
    }),
    ('json://user@localhost?method=get', {
        'instance': NotifyJSON,
    }),
    ('json://user@localhost?method=post', {
        'instance': NotifyJSON,
    }),
    ('json://user@localhost?method=head', {
        'instance': NotifyJSON,
    }),
    ('json://user@localhost?method=delete', {
        'instance': NotifyJSON,
    }),

    # Continue testing other cases
    ('json://localhost:8080', {
        'instance': NotifyJSON,
    }),
    ('json://user:pass@localhost:8080', {
        'instance': NotifyJSON,
    }),
    ('jsons://localhost', {
        'instance': NotifyJSON,
    }),
    ('jsons://user:pass@localhost', {
        'instance': NotifyJSON,
    }),
    ('jsons://localhost:8080/path/', {
        'instance': NotifyJSON,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'jsons://localhost:8080/path/',
    }),
    # Test our GET params
    ('json://localhost:8080/path?-ParamA=Value', {
        'instance': NotifyJSON,
    }),
    ('jsons://user:password@localhost:8080', {
        'instance': NotifyJSON,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'jsons://user:****@localhost:8080',
    }),
    # Test our Headers
    ('json://localhost:8080/path?+HeaderKey=HeaderValue', {
        'instance': NotifyJSON,
    }),
    ('json://user:pass@localhost:8081', {
        'instance': NotifyJSON,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('json://user:pass@localhost:8082', {
        'instance': NotifyJSON,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('json://user:pass@localhost:8083', {
        'instance': NotifyJSON,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_custom_json_urls():
    """
    NotifyJSON() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
@mock.patch('requests.get')
def test_plugin_custom_json_edge_cases(mock_get, mock_post):
    """
    NotifyJSON() Edge Cases

    """

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response
    mock_get.return_value = response

    results = NotifyJSON.parse_url(
        'json://localhost:8080/command?:message=test&method=GET')

    assert isinstance(results, dict)
    assert results['user'] is None
    assert results['password'] is None
    assert results['port'] == 8080
    assert results['host'] == 'localhost'
    assert results['fullpath'] == '/command'
    assert results['path'] == '/'
    assert results['query'] == 'command'
    assert results['schema'] == 'json'
    assert results['url'] == 'json://localhost:8080/command'
    assert isinstance(results['qsd:'], dict) is True
    assert results['qsd:']['message'] == 'test'

    instance = NotifyJSON(**results)
    assert isinstance(instance, NotifyJSON)

    response = instance.send(title='title', body='body')
    assert response is True
    assert mock_post.call_count == 0
    assert mock_get.call_count == 1

    details = mock_get.call_args_list[0]
    assert details[0][0] == 'http://localhost:8080/command'
    assert 'title' in details[1]['data']
    dataset = json.loads(details[1]['data'])
    assert dataset['title'] == 'title'
    assert 'message' in dataset
    # message over-ride was provided
    assert dataset['message'] == 'test'

    assert instance.url(privacy=False).startswith(
        'json://localhost:8080/command?')

    # Generate a new URL based on our last and verify key values are the same
    new_results = NotifyJSON.parse_url(instance.url(safe=False))
    for k in ('user', 'password', 'port', 'host', 'fullpath', 'path', 'query',
              'schema', 'url', 'method'):
        assert new_results[k] == results[k]


@mock.patch('requests.post')
def test_notify_json_plugin_attachments(mock_post):
    """
    NotifyJSON() Attachments

    """

    okay_response = requests.Request()
    okay_response.status_code = requests.codes.ok
    okay_response.content = ""

    # Assign our mock object our return value
    mock_post.return_value = okay_response

    obj = Apprise.instantiate('json://localhost.localdomain/')
    assert isinstance(obj, NotifyJSON)

    # Test Valid Attachment
    path = os.path.join(TEST_VAR_DIR, 'apprise-test.gif')
    attach = AppriseAttachment(path)
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is True

    # Test invalid attachment
    path = os.path.join(TEST_VAR_DIR, '/invalid/path/to/an/invalid/file.jpg')
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=path) is False

    # Get a appropriate "builtin" module name for pythons 2/3.
    if sys.version_info.major >= 3:
        builtin_open_function = 'builtins.open'

    else:
        builtin_open_function = '__builtin__.open'

    # Test Valid Attachment (load 3)
    path = (
        os.path.join(TEST_VAR_DIR, 'apprise-test.gif'),
        os.path.join(TEST_VAR_DIR, 'apprise-test.gif'),
        os.path.join(TEST_VAR_DIR, 'apprise-test.gif'),
    )
    attach = AppriseAttachment(path)

    # Return our good configuration
    mock_post.side_effect = None
    mock_post.return_value = okay_response
    with mock.patch(builtin_open_function, side_effect=OSError()):
        # We can't send the message we can't open the attachment for reading
        assert obj.notify(
            body='body', title='title', notify_type=NotifyType.INFO,
            attach=attach) is False

    # test the handling of our batch modes
    obj = Apprise.instantiate('json://no-reply@example.com/')
    assert isinstance(obj, NotifyJSON)

    # Now send an attachment normally without issues
    mock_post.reset_mock()
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is True
    assert mock_post.call_count == 1
