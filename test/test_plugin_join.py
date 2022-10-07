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
import apprise
from apprise import plugins
from apprise import NotifyType
from helpers import AppriseURLTester
from apprise.plugins.NotifyJoin import JoinPriority

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('join://', {
        'instance': TypeError,
    }),
    # API Key + bad url
    ('join://:@/', {
        'instance': TypeError,
    }),
    # APIkey; no device
    ('join://%s' % ('a' * 32), {
        'instance': plugins.NotifyJoin,
    }),
    # API Key + device (using to=)
    ('join://%s?to=%s' % ('a' * 32, 'd' * 32), {
        'instance': plugins.NotifyJoin,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'join://a...a/',
    }),
    # API Key + priority setting
    ('join://%s?priority=high' % ('a' * 32), {
        'instance': plugins.NotifyJoin,
    }),
    # API Key + invalid priority setting
    ('join://%s?priority=invalid' % ('a' * 32), {
        'instance': plugins.NotifyJoin,
    }),
    # API Key + priority setting (empty)
    ('join://%s?priority=' % ('a' * 32), {
        'instance': plugins.NotifyJoin,
    }),
    # API Key + device
    ('join://%s@%s?image=True' % ('a' * 32, 'd' * 32), {
        'instance': plugins.NotifyJoin,
    }),
    # No image
    ('join://%s@%s?image=False' % ('a' * 32, 'd' * 32), {
        'instance': plugins.NotifyJoin,
    }),
    # API Key + Device Name
    ('join://%s/%s' % ('a' * 32, 'My Device'), {
        'instance': plugins.NotifyJoin,
    }),
    # API Key + device
    ('join://%s/%s' % ('a' * 32, 'd' * 32), {
        'instance': plugins.NotifyJoin,
        # don't include an image by default
        'include_image': False,
    }),
    # API Key + 2 devices
    ('join://%s/%s/%s' % ('a' * 32, 'd' * 32, 'e' * 32), {
        'instance': plugins.NotifyJoin,
        # don't include an image by default
        'include_image': False,
    }),
    # API Key + 1 device and 1 group
    ('join://%s/%s/%s' % ('a' * 32, 'd' * 32, 'group.chrome'), {
        'instance': plugins.NotifyJoin,
    }),
    ('join://%s' % ('a' * 32), {
        'instance': plugins.NotifyJoin,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('join://%s' % ('a' * 32), {
        'instance': plugins.NotifyJoin,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('join://%s' % ('a' * 32), {
        'instance': plugins.NotifyJoin,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_join_urls():
    """
    NotifyJoin() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.get')
@mock.patch('requests.post')
def test_plugin_join_edge_cases(mock_post, mock_get):
    """
    NotifyJoin() Edge Cases

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Generate some generic message types
    device = 'A' * 32
    group = 'group.chrome'
    apikey = 'a' * 32

    # Initializes the plugin with devices set to a string
    plugins.NotifyJoin(apikey=apikey, targets=group)

    # Initializes the plugin with devices set to None
    plugins.NotifyJoin(apikey=apikey, targets=None)

    # Initializes the plugin with an invalid apikey
    with pytest.raises(TypeError):
        plugins.NotifyJoin(apikey=None)

    # Whitespace also acts as an invalid apikey
    with pytest.raises(TypeError):
        plugins.NotifyJoin(apikey="   ")

    # Initializes the plugin with devices set to a set
    p = plugins.NotifyJoin(apikey=apikey, targets=[group, device])

    # Prepare our mock responses
    req = requests.Request()
    req.status_code = requests.codes.created
    req.content = ''
    mock_get.return_value = req
    mock_post.return_value = req

    # Test notifications without a body or a title; nothing to send
    # so we return False
    p.notify(body=None, title=None, notify_type=NotifyType.INFO) is False


@mock.patch('requests.post')
def test_plugin_join_config_files(mock_post):
    """
    NotifyJoin() Config File Cases
    """
    content = """
    urls:
      - join://%s@%s:
          - priority: -2
            tag: join_int low
          - priority: "-2"
            tag: join_str_int low
          - priority: low
            tag: join_str low

          # This will take on normal (default) priority
          - priority: invalid
            tag: join_invalid

      - join://%s@%s:
          - priority: 2
            tag: join_int emerg
          - priority: "2"
            tag: join_str_int emerg
          - priority: emergency
            tag: join_str emerg
    """ % ('a' * 32, 'b' * 32, 'c' * 32, 'd' * 32)

    # Disable Throttling to speed testing
    plugins.NotifyJoin.request_rate_per_sec = 0

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
        assert s.priority == JoinPriority.LOW

    assert len([x for x in aobj.find(tag='emerg')]) == 3
    for s in aobj.find(tag='emerg'):
        assert s.priority == JoinPriority.EMERGENCY

    assert len([x for x in aobj.find(tag='join_str')]) == 2
    assert len([x for x in aobj.find(tag='join_str_int')]) == 2
    assert len([x for x in aobj.find(tag='join_int')]) == 2

    assert len([x for x in aobj.find(tag='join_invalid')]) == 1
    assert next(aobj.find(tag='join_invalid')).priority == \
        JoinPriority.NORMAL

    # Notifications work
    assert aobj.notify(title="title", body="body") is True
