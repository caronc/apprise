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
from unittest import mock

import requests
from apprise import plugins
from helpers import AppriseURLTester
from apprise import Apprise
from apprise import NotifyType
from apprise import AppriseAttachment

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), 'var')

# Our Testing URLs
apprise_url_tests = (
    ('form://:@/', {
        'instance': None,
    }),
    ('form://', {
        'instance': None,
    }),
    ('forms://', {
        'instance': None,
    }),
    ('form://localhost', {
        'instance': plugins.NotifyForm,
    }),
    ('form://user@localhost?method=invalid', {
        'instance': TypeError,
    }),
    ('form://user:pass@localhost', {
        'instance': plugins.NotifyForm,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'form://user:****@localhost',
    }),
    ('form://user@localhost', {
        'instance': plugins.NotifyForm,
    }),

    # Test method variations
    ('form://user@localhost?method=put', {
        'instance': plugins.NotifyForm,
    }),
    ('form://user@localhost?method=get', {
        'instance': plugins.NotifyForm,
    }),
    ('form://user@localhost?method=post', {
        'instance': plugins.NotifyForm,
    }),
    ('form://user@localhost?method=head', {
        'instance': plugins.NotifyForm,
    }),
    ('form://user@localhost?method=delete', {
        'instance': plugins.NotifyForm,
    }),

    # Custom payload options
    ('form://localhost:8080?:key=value&:key2=value2', {
        'instance': plugins.NotifyForm,
    }),

    # Continue testing other cases
    ('form://localhost:8080', {
        'instance': plugins.NotifyForm,
    }),
    ('form://user:pass@localhost:8080', {
        'instance': plugins.NotifyForm,
    }),
    ('forms://localhost', {
        'instance': plugins.NotifyForm,
    }),
    ('forms://user:pass@localhost', {
        'instance': plugins.NotifyForm,
    }),
    ('forms://localhost:8080/path/', {
        'instance': plugins.NotifyForm,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'forms://localhost:8080/path/',
    }),
    ('forms://user:password@localhost:8080', {
        'instance': plugins.NotifyForm,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'forms://user:****@localhost:8080',
    }),
    ('form://localhost:8080/path?+HeaderKey=HeaderValue', {
        'instance': plugins.NotifyForm,
    }),
    ('form://user:pass@localhost:8081', {
        'instance': plugins.NotifyForm,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('form://user:pass@localhost:8082', {
        'instance': plugins.NotifyForm,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('form://user:pass@localhost:8083', {
        'instance': plugins.NotifyForm,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_custom_form_urls():
    """
    NotifyForm() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
def test_plugin_custom_form_attachments(mock_post):
    """
    NotifyForm() Attachments

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    okay_response = requests.Request()
    okay_response.status_code = requests.codes.ok
    okay_response.content = ""

    # Assign our mock object our return value
    mock_post.return_value = okay_response

    obj = Apprise.instantiate(
        'form://user@localhost.localdomain/?method=post')
    assert isinstance(obj, plugins.NotifyForm)

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

    mock_post.return_value = None
    mock_post.side_effect = OSError()
    # We can't send the message if we can't read the attachment
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is False

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
    with mock.patch('builtins.open', side_effect=OSError()):
        # We can't send the message we can't open the attachment for reading
        assert obj.notify(
            body='body', title='title', notify_type=NotifyType.INFO,
            attach=attach) is False

    # Fail on the 2nd attempt (but not the first)
    with mock.patch('builtins.open',
                    side_effect=[None, OSError(), None]):
        # We can't send the message we can't open the attachment for reading
        assert obj.notify(
            body='body', title='title', notify_type=NotifyType.INFO,
            attach=attach) is False

    # Test file exception handling when performing post
    mock_post.return_value = None
    mock_post.side_effect = OSError()
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is False


@mock.patch('requests.post')
@mock.patch('requests.get')
def test_plugin_custom_form_edge_cases(mock_get, mock_post):
    """
    NotifyForm() Edge Cases

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response
    mock_get.return_value = response

    results = plugins.NotifyForm.parse_url(
        'form://localhost:8080/command?:abcd=test&method=POST')

    assert isinstance(results, dict)
    assert results['user'] is None
    assert results['password'] is None
    assert results['port'] == 8080
    assert results['host'] == 'localhost'
    assert results['fullpath'] == '/command'
    assert results['path'] == '/'
    assert results['query'] == 'command'
    assert results['schema'] == 'form'
    assert results['url'] == 'form://localhost:8080/command'
    assert isinstance(results['qsd:'], dict) is True
    assert results['qsd:']['abcd'] == 'test'

    instance = plugins.NotifyForm(**results)
    assert isinstance(instance, plugins.NotifyForm)

    response = instance.send(title='title', body='body')
    assert response is True
    assert mock_post.call_count == 1
    assert mock_get.call_count == 0

    details = mock_post.call_args_list[0]
    assert details[0][0] == 'http://localhost:8080/command'
    assert 'abcd' in details[1]['data']
    assert details[1]['data']['abcd'] == 'test'
    assert 'title' in details[1]['data']
    assert details[1]['data']['title'] == 'title'
    assert 'message' in details[1]['data']
    assert details[1]['data']['message'] == 'body'

    assert instance.url(privacy=False).startswith(
        'form://localhost:8080/command?')

    # Generate a new URL based on our last and verify key values are the same
    new_results = plugins.NotifyForm.parse_url(instance.url(safe=False))
    for k in ('user', 'password', 'port', 'host', 'fullpath', 'path', 'query',
              'schema', 'url', 'payload', 'method'):
        assert new_results[k] == results[k]

    # Reset our mock configuration
    mock_post.reset_mock()
    mock_get.reset_mock()

    results = plugins.NotifyForm.parse_url(
        'form://localhost:8080/command?:message=test&method=POST')

    assert isinstance(results, dict)
    assert results['user'] is None
    assert results['password'] is None
    assert results['port'] == 8080
    assert results['host'] == 'localhost'
    assert results['fullpath'] == '/command'
    assert results['path'] == '/'
    assert results['query'] == 'command'
    assert results['schema'] == 'form'
    assert results['url'] == 'form://localhost:8080/command'
    assert isinstance(results['qsd:'], dict) is True
    assert results['qsd:']['message'] == 'test'

    instance = plugins.NotifyForm(**results)
    assert isinstance(instance, plugins.NotifyForm)

    response = instance.send(title='title', body='body')
    assert response is True
    assert mock_post.call_count == 1
    assert mock_get.call_count == 0

    details = mock_post.call_args_list[0]
    assert details[0][0] == 'http://localhost:8080/command'
    assert 'title' in details[1]['data']
    assert details[1]['data']['title'] == 'title'
    # 'body' is over-ridden by 'test' passed inline with the URL
    assert 'message' in details[1]['data']
    assert details[1]['data']['message'] == 'test'

    assert instance.url(privacy=False).startswith(
        'form://localhost:8080/command?')

    # Generate a new URL based on our last and verify key values are the same
    new_results = plugins.NotifyForm.parse_url(instance.url(safe=False))
    for k in ('user', 'password', 'port', 'host', 'fullpath', 'path', 'query',
              'schema', 'url', 'payload', 'method'):
        assert new_results[k] == results[k]

    # Reset our mock configuration
    mock_post.reset_mock()
    mock_get.reset_mock()

    results = plugins.NotifyForm.parse_url(
        'form://localhost:8080/command?:message=test&method=GET')

    assert isinstance(results, dict)
    assert results['user'] is None
    assert results['password'] is None
    assert results['port'] == 8080
    assert results['host'] == 'localhost'
    assert results['fullpath'] == '/command'
    assert results['path'] == '/'
    assert results['query'] == 'command'
    assert results['schema'] == 'form'
    assert results['url'] == 'form://localhost:8080/command'
    assert isinstance(results['qsd:'], dict) is True
    assert results['qsd:']['message'] == 'test'

    instance = plugins.NotifyForm(**results)
    assert isinstance(instance, plugins.NotifyForm)

    response = instance.send(title='title', body='body')
    assert response is True
    assert mock_post.call_count == 0
    assert mock_get.call_count == 1

    details = mock_get.call_args_list[0]
    assert details[0][0] == 'http://localhost:8080/command'

    assert 'title' in details[1]['params']
    assert details[1]['params']['title'] == 'title'
    # 'body' is over-ridden by 'test' passed inline with the URL
    assert 'message' in details[1]['params']
    assert details[1]['params']['message'] == 'test'

    assert instance.url(privacy=False).startswith(
        'form://localhost:8080/command?')

    # Generate a new URL based on our last and verify key values are the same
    new_results = plugins.NotifyForm.parse_url(instance.url(safe=False))
    for k in ('user', 'password', 'port', 'host', 'fullpath', 'path', 'query',
              'schema', 'url', 'payload', 'method'):
        assert new_results[k] == results[k]
