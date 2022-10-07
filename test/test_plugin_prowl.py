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
from unittest import mock

import pytest
import requests
from apprise.plugins.NotifyProwl import ProwlPriority
from apprise import plugins
import apprise
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('prowl://', {
        'instance': TypeError,
    }),
    # bad url
    ('prowl://:@/', {
        'instance': TypeError,
    }),
    # Invalid API Key
    ('prowl://%s' % ('a' * 20), {
        'instance': TypeError,
    }),
    # Provider Key
    ('prowl://%s/%s' % ('a' * 40, 'b' * 40), {
        'instance': plugins.NotifyProwl,
    }),
    # Invalid Provider Key
    ('prowl://%s/%s' % ('a' * 40, 'b' * 20), {
        'instance': TypeError,
    }),
    # APIkey; no device
    ('prowl://%s' % ('a' * 40), {
        'instance': plugins.NotifyProwl,
    }),
    # API Key
    ('prowl://%s' % ('a' * 40), {
        'instance': plugins.NotifyProwl,
        # don't include an image by default
        'include_image': False,
    }),
    # API Key + priority setting
    ('prowl://%s?priority=high' % ('a' * 40), {
        'instance': plugins.NotifyProwl,
    }),
    # API Key + invalid priority setting
    ('prowl://%s?priority=invalid' % ('a' * 40), {
        'instance': plugins.NotifyProwl,
    }),
    # API Key + priority setting (empty)
    ('prowl://%s?priority=' % ('a' * 40), {
        'instance': plugins.NotifyProwl,
    }),
    # API Key + No Provider Key (empty)
    ('prowl://%s///' % ('w' * 40), {
        'instance': plugins.NotifyProwl,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'prowl://w...w/',
    }),
    # API Key + Provider Key
    ('prowl://%s/%s' % ('a' * 40, 'b' * 40), {
        'instance': plugins.NotifyProwl,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'prowl://a...a/b...b',
    }),
    # API Key + with image
    ('prowl://%s' % ('a' * 40), {
        'instance': plugins.NotifyProwl,
    }),
    ('prowl://%s' % ('a' * 40), {
        'instance': plugins.NotifyProwl,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('prowl://%s' % ('a' * 40), {
        'instance': plugins.NotifyProwl,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('prowl://%s' % ('a' * 40), {
        'instance': plugins.NotifyProwl,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_prowl():
    """
    NotifyProwl() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_prowl_edge_cases():
    """
    NotifyProwl() Edge Cases

    """
    # Initializes the plugin with an invalid apikey
    with pytest.raises(TypeError):
        plugins.NotifyProwl(apikey=None)
    # Whitespace also acts as an invalid apikey value
    with pytest.raises(TypeError):
        plugins.NotifyProwl(apikey='  ')

    # Whitespace also acts as an invalid provider key
    with pytest.raises(TypeError):
        plugins.NotifyProwl(apikey='abcd', providerkey=object())
    with pytest.raises(TypeError):
        plugins.NotifyProwl(apikey='abcd', providerkey='  ')


@mock.patch('requests.post')
def test_plugin_prowl_config_files(mock_post):
    """
    NotifyProwl() Config File Cases
    """
    content = """
    urls:
      - prowl://%s:
          - priority: -2
            tag: prowl_int low
          - priority: "-2"
            tag: prowl_str_int low
          - priority: low
            tag: prowl_str low

          # This will take on moderate (default) priority
          - priority: invalid
            tag: prowl_invalid

      - prowl://%s:
          - priority: 2
            tag: prowl_int emerg
          - priority: "2"
            tag: prowl_str_int emerg
          - priority: emergency
            tag: prowl_str emerg
    """ % ('a' * 40, 'b' * 40)

    # Disable Throttling to speed testing
    plugins.NotifyProwl.request_rate_per_sec = 0

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    # Create ourselves a config object
    ac = apprise.AppriseConfig()
    assert ac.add_config(content=content) is True

    aobj = apprise.Apprise()

    # Add our configuration
    aobj.add(ac)

    # We should be able to read our 7 servers from that
    # 3x low
    # 3x emerg
    # 1x invalid (so takes on normal priority)
    assert len(ac.servers()) == 7
    assert len(aobj) == 7
    assert len([x for x in aobj.find(tag='low')]) == 3
    for s in aobj.find(tag='low'):
        assert s.priority == ProwlPriority.LOW

    assert len([x for x in aobj.find(tag='emerg')]) == 3
    for s in aobj.find(tag='emerg'):
        assert s.priority == ProwlPriority.EMERGENCY

    assert len([x for x in aobj.find(tag='prowl_str')]) == 2
    assert len([x for x in aobj.find(tag='prowl_str_int')]) == 2
    assert len([x for x in aobj.find(tag='prowl_int')]) == 2

    assert len([x for x in aobj.find(tag='prowl_invalid')]) == 1
    assert next(aobj.find(tag='prowl_invalid')).priority == \
        ProwlPriority.NORMAL
