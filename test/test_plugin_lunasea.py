# -*- coding: utf-8 -*-
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
from unittest import mock
from json import loads

import requests
from helpers import AppriseURLTester

from apprise.plugins.lunasea import NotifyLunaSea

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), 'var')

# Our Testing URLs
apprise_url_tests = (
    ('lunasea://', {
        # Initializes okay (as cloud mode) but has no targets to notify
        'instance': NotifyLunaSea,
        # invalid targets specified (nothing to notify)
        # as a result the response type will be false
        'response': False,
    }),
    ('lunaseas://44$$$$%3012/?mode=private', {
        # Private mode initialization with a horrible hostname
        'instance': None
    }),
    ('lunasea://:@/', {
        # Initializes okay (as cloud mode) but has no targets to notify
        'instance': NotifyLunaSea,
        # invalid targets specified (nothing to notify)
        # as a result the response type will be false
        'response': False,
    }),
    # No targets
    ('lunasea://user:pass@localhost?mode=private', {
        'instance': NotifyLunaSea,
        # invalid targets specified (nothing to notify)
        # as a result the response type will be false
        'response': False,
    }),
    # No valid targets
    ('lunasea://user:pass@localhost/#/!/@', {
        'instance': NotifyLunaSea,
        # invalid targets specified (nothing to notify)
        # as a result the response type will be false
        'response': False,
    }),
    # user/pass combos
    ('lunasea://user@localhost/@user/', {
        'instance': NotifyLunaSea,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'lunasea://user@localhost/@user',
    }),
    # LunaSea cloud mode (enforced)
    ('lunasea://lunasea.app/@user/+device/', {
        'instance': NotifyLunaSea,
    }),
    # No user/pass combo
    ('lunasea://localhost/@user/@user2/?image=True', {
        'instance': NotifyLunaSea,
    }),
    # Enforce image but not otherwise find one
    ('lunasea://localhost/+device/?image=True', {
        'instance': NotifyLunaSea,
        'include_image': False,
    }),
    # No images
    ('lunasea://localhost/+device/?image=False', {
        'instance': NotifyLunaSea,
    }),
    ('lunaseas://user:pass@localhost?to=+device', {
        'instance': NotifyLunaSea,
        # The response text is expected to be the following on a success
    }),
    ('https://just/a/random/host/that/means/nothing', {
        # Nothing transpires from this
        'instance': None
    }),
    # Several targets
    ('lunasea://user:pass@+device/user/@user2/?mode=cloud', {
        'instance': NotifyLunaSea,
        # The response text is expected to be the following on a success
    }),
    # Several targets (but do not add lunasea.app)
    ('lunasea://user:pass@lunasea.app/user1/user2/?mode=cloud', {
        'instance': NotifyLunaSea,
        # The response text is expected to be the following on a success
    }),
    ('lunaseas://user:web/token@localhost/user/?mode=invalid', {
        # Invalid mode
        'instance': TypeError,
    }),
    ('lunasea://user:pass@localhost:8089/+device/user1', {
        'instance': NotifyLunaSea,
        # force a failure using basic mode
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('lunasea://user:pass@localhost:8082/+device', {
        'instance': NotifyLunaSea,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('lunasea://user:pass@localhost:8083/user1/user2/', {
        'instance': NotifyLunaSea,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_lunasea_urls():
    """
    NotifyLunaSea() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
def test_plugin_custom_lunasea_edge_cases(mock_post):
    """
    NotifyLunaSea() Edge Cases

    """

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok
    response.content = ''

    # Prepare Mock
    mock_post.return_value = response

    # Prepare a URL with some garbage in it that gets parsed out anyway
    # key take away is we provided userA and device1
    results = NotifyLunaSea.parse_url('lsea://user:pass@@userA,+device1,~~,,')

    assert isinstance(results, dict)
    assert results['user'] == 'user'
    assert results['password'] == 'pass'
    assert results['port'] is None
    assert results['host'] == 'userA,+device1,~~,,'
    assert results['fullpath'] is None
    assert results['path'] is None
    assert results['query'] is None
    assert results['schema'] == 'lsea'
    assert results['url'] == 'lsea://user:pass@userA,+device1,~~,,'
    assert isinstance(results['qsd:'], dict)

    instance = NotifyLunaSea(**results)
    assert isinstance(instance, NotifyLunaSea)
    assert len(instance.targets) == 2
    assert ('@', 'userA') in instance.targets
    assert ('+', 'device1') in instance.targets

    assert instance.notify("test") is True

    # 1 call to user, and second to device
    assert mock_post.call_count == 2

    url = mock_post.call_args_list[0][0][0]
    assert url == 'https://notify.lunasea.app/v1/custom/device/device1'
    payload = loads(mock_post.call_args_list[0][1]['data'])
    assert 'title' in payload
    assert 'body' in payload
    assert 'image' not in payload
    assert payload['body'] == 'test'
    assert payload['title'] == 'Apprise Notifications'

    url = mock_post.call_args_list[1][0][0]
    assert url == 'https://notify.lunasea.app/v1/custom/user/userA'
    payload = loads(mock_post.call_args_list[1][1]['data'])
    assert 'title' in payload
    assert 'body' in payload
    assert 'image' not in payload
    assert payload['body'] == 'test'
    assert payload['title'] == 'Apprise Notifications'

    assert '@userA' in instance.url()
    assert '+device1' in instance.url()

    # Test using a locally hosted instance now:
    mock_post.reset_mock()

    results = NotifyLunaSea.parse_url(
        'lseas://user:pass@myhost:3222/@userA,+device1,~~,,')

    assert isinstance(results, dict)
    assert results['user'] == 'user'
    assert results['password'] == 'pass'
    assert results['port'] == 3222
    assert results['host'] == 'myhost'
    assert (
        results['fullpath'] == '/%40userA%2C%2Bdevice1%2C~~%2C%2C' or
        # Compatible with RHEL8 (Python v3.6.8)
        results['fullpath'] == '/%40userA%2C%2Bdevice1%2C%7E%7E%2C%2C'
    )
    assert results['path'] == '/'
    assert (
        results['query'] == '%40userA%2C%2Bdevice1%2C~~%2C%2C' or
        # Compatible with RHEL8 (Python v3.6.8)
        results['query'] == '%40userA%2C%2Bdevice1%2C%7E%7E%2C%2C'
    )
    assert results['schema'] == 'lseas'
    assert (
        results['url'] ==
        'lseas://user:pass@myhost:3222/%40userA%2C%2Bdevice1%2C~~%2C%2C' or
        # Compatible with RHEL8 (Python v3.6.8)
        results['url'] ==
        'lseas://user:pass@myhost:3222/%40userA%2C%2Bdevice1%2C%7E%7E%2C%2C'
    )
    assert isinstance(results['qsd:'], dict)

    instance = NotifyLunaSea(**results)
    assert isinstance(instance, NotifyLunaSea)
    assert len(instance.targets) == 2
    assert ('@', 'userA') in instance.targets
    assert ('+', 'device1') in instance.targets

    assert instance.notify("test") is True

    # 1 call to user, and second to device
    assert mock_post.call_count == 2

    url = mock_post.call_args_list[0][0][0]
    assert url == 'https://myhost:3222/v1/custom/device/device1'
    payload = loads(mock_post.call_args_list[0][1]['data'])
    assert 'title' in payload
    assert 'body' in payload
    assert 'image' not in payload
    assert payload['body'] == 'test'
    assert payload['title'] == 'Apprise Notifications'

    url = mock_post.call_args_list[1][0][0]
    assert url == 'https://myhost:3222/v1/custom/user/userA'
    payload = loads(mock_post.call_args_list[1][1]['data'])
    assert 'title' in payload
    assert 'body' in payload
    assert 'image' not in payload
    assert payload['body'] == 'test'
    assert payload['title'] == 'Apprise Notifications'

    assert '@userA' in instance.url()
    assert '+device1' in instance.url()
