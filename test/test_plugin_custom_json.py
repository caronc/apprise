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
import json
from unittest import mock

import requests
from apprise import plugins
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

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
        'instance': plugins.NotifyJSON,
    }),
    ('json://user@localhost?method=invalid', {
        'instance': TypeError,
    }),
    ('json://user:pass@localhost', {
        'instance': plugins.NotifyJSON,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'json://user:****@localhost',
    }),
    ('json://user@localhost', {
        'instance': plugins.NotifyJSON,
    }),

    # Test method variations
    ('json://user@localhost?method=put', {
        'instance': plugins.NotifyJSON,
    }),
    ('json://user@localhost?method=get', {
        'instance': plugins.NotifyJSON,
    }),
    ('json://user@localhost?method=post', {
        'instance': plugins.NotifyJSON,
    }),
    ('json://user@localhost?method=head', {
        'instance': plugins.NotifyJSON,
    }),
    ('json://user@localhost?method=delete', {
        'instance': plugins.NotifyJSON,
    }),

    # Continue testing other cases
    ('json://localhost:8080', {
        'instance': plugins.NotifyJSON,
    }),
    ('json://user:pass@localhost:8080', {
        'instance': plugins.NotifyJSON,
    }),
    ('jsons://localhost', {
        'instance': plugins.NotifyJSON,
    }),
    ('jsons://user:pass@localhost', {
        'instance': plugins.NotifyJSON,
    }),
    ('jsons://localhost:8080/path/', {
        'instance': plugins.NotifyJSON,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'jsons://localhost:8080/path/',
    }),
    ('jsons://user:password@localhost:8080', {
        'instance': plugins.NotifyJSON,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'jsons://user:****@localhost:8080',
    }),
    ('json://localhost:8080/path?+HeaderKey=HeaderValue', {
        'instance': plugins.NotifyJSON,
    }),
    ('json://user:pass@localhost:8081', {
        'instance': plugins.NotifyJSON,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('json://user:pass@localhost:8082', {
        'instance': plugins.NotifyJSON,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('json://user:pass@localhost:8083', {
        'instance': plugins.NotifyJSON,
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
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response
    mock_get.return_value = response

    results = plugins.NotifyJSON.parse_url(
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

    instance = plugins.NotifyJSON(**results)
    assert isinstance(instance, plugins.NotifyJSON)

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
    new_results = plugins.NotifyJSON.parse_url(instance.url(safe=False))
    for k in ('user', 'password', 'port', 'host', 'fullpath', 'path', 'query',
              'schema', 'url', 'method'):
        assert new_results[k] == results[k]
