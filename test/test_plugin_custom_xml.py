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
import mock
import requests
from apprise import plugins
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('xml://:@/', {
        'instance': None,
    }),
    ('xml://', {
        'instance': None,
    }),
    ('xmls://', {
        'instance': None,
    }),
    ('xml://localhost', {
        'instance': plugins.NotifyXML,
    }),
    ('xml://user@localhost', {
        'instance': plugins.NotifyXML,
    }),
    ('xml://user@localhost?method=invalid', {
        'instance': TypeError,
    }),
    ('xml://user:pass@localhost', {
        'instance': plugins.NotifyXML,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'xml://user:****@localhost',
    }),

    # Test method variations
    ('xml://user@localhost?method=put', {
        'instance': plugins.NotifyXML,
    }),
    ('xml://user@localhost?method=get', {
        'instance': plugins.NotifyXML,
    }),
    ('xml://user@localhost?method=post', {
        'instance': plugins.NotifyXML,
    }),
    ('xml://user@localhost?method=head', {
        'instance': plugins.NotifyXML,
    }),
    ('xml://user@localhost?method=delete', {
        'instance': plugins.NotifyXML,
    }),

    # Continue testing other cases
    ('xml://localhost:8080', {
        'instance': plugins.NotifyXML,
    }),
    ('xml://user:pass@localhost:8080', {
        'instance': plugins.NotifyXML,
    }),
    ('xmls://localhost', {
        'instance': plugins.NotifyXML,
    }),
    ('xmls://user:pass@localhost', {
        'instance': plugins.NotifyXML,
    }),
    # Continue testing other cases
    ('xml://localhost:8080', {
        'instance': plugins.NotifyXML,
    }),
    ('xml://user:pass@localhost:8080', {
        'instance': plugins.NotifyXML,
    }),
    ('xml://localhost', {
        'instance': plugins.NotifyXML,
    }),
    ('xmls://user:pass@localhost', {
        'instance': plugins.NotifyXML,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'xmls://user:****@localhost',
    }),
    ('xml://user@localhost:8080/path/', {
        'instance': plugins.NotifyXML,
        'privacy_url': 'xml://user@localhost:8080/path',
    }),
    ('xmls://localhost:8080/path/', {
        'instance': plugins.NotifyXML,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'xmls://localhost:8080/path/',
    }),
    ('xmls://user:pass@localhost:8080', {
        'instance': plugins.NotifyXML,
    }),
    ('xml://localhost:8080/path?-HeaderKey=HeaderValue', {
        'instance': plugins.NotifyXML,
    }),
    ('xml://user:pass@localhost:8081', {
        'instance': plugins.NotifyXML,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('xml://user:pass@localhost:8082', {
        'instance': plugins.NotifyXML,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('xml://user:pass@localhost:8083', {
        'instance': plugins.NotifyXML,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_custom_xml_urls():
    """
    NotifyXML() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
@mock.patch('requests.get')
def test_plugin_custom_xml_edge_cases(mock_get, mock_post):
    """
    NotifyXML() Edge Cases

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response
    mock_get.return_value = response

    results = plugins.NotifyXML.parse_url(
        'xml://localhost:8080/command?:message=test&method=GET')

    assert isinstance(results, dict)
    assert results['user'] is None
    assert results['password'] is None
    assert results['port'] == 8080
    assert results['host'] == 'localhost'
    assert results['fullpath'] == '/command'
    assert results['path'] == '/'
    assert results['query'] == 'command'
    assert results['schema'] == 'xml'
    assert results['url'] == 'xml://localhost:8080/command'
    assert isinstance(results['qsd:'], dict) is True
    assert results['qsd:']['message'] == 'test'

    instance = plugins.NotifyXML(**results)
    assert isinstance(instance, plugins.NotifyXML)

    response = instance.send(title='title', body='body')
    assert response is True
    assert mock_post.call_count == 0
    assert mock_get.call_count == 1

    details = mock_get.call_args_list[0]
    assert details[0][0] == 'http://localhost:8080/command'
    assert instance.url(privacy=False).startswith(
        'xml://localhost:8080/command?')

    # Generate a new URL based on our last and verify key values are the same
    new_results = plugins.NotifyXML.parse_url(instance.url(safe=False))
    for k in ('user', 'password', 'port', 'host', 'fullpath', 'path', 'query',
              'schema', 'url', 'method'):
        assert new_results[k] == results[k]
