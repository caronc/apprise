# -*- coding: utf-8 -*-
#
# Apprise - Push Notification Library.
# Copyright (C) 2023  Chris Caron <lead2gold@gmail.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor,
# Boston, MA  02110-1301, USA.

import pytest
from unittest import mock

from apprise.plugins.NotifyBoxcar import NotifyBoxcar
from helpers import AppriseURLTester
from apprise import NotifyType
import requests

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('boxcar://', {
        # invalid secret key
        'instance': TypeError,
    }),
    # A a bad url
    ('boxcar://:@/', {
        'instance': TypeError,
    }),
    # No secret specified
    ('boxcar://%s' % ('a' * 64), {
        'instance': TypeError,
    }),
    # No access specified (whitespace is trimmed)
    ('boxcar://%%20/%s' % ('a' * 64), {
        'instance': TypeError,
    }),
    # No secret specified (whitespace is trimmed)
    ('boxcar://%s/%%20' % ('a' * 64), {
        'instance': TypeError,
    }),
    # Provide both an access and a secret
    ('boxcar://%s/%s' % ('a' * 64, 'b' * 64), {
        'instance': NotifyBoxcar,
        'requests_response_code': requests.codes.created,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'boxcar://a...a/****/',
    }),
    # Test without image set
    ('boxcar://%s/%s?image=True' % ('a' * 64, 'b' * 64), {
        'instance': NotifyBoxcar,
        'requests_response_code': requests.codes.created,
        # don't include an image in Asset by default
        'include_image': False,
    }),
    ('boxcar://%s/%s?image=False' % ('a' * 64, 'b' * 64), {
        'instance': NotifyBoxcar,
        'requests_response_code': requests.codes.created,
    }),
    # our access, secret and device are all 64 characters
    # which is what we're doing here
    ('boxcar://%s/%s/@tag1/tag2///%s/?to=tag3' % (
        'a' * 64, 'b' * 64, 'd' * 64), {
        'instance': NotifyBoxcar,
        'requests_response_code': requests.codes.created,
    }),
    # An invalid tag
    ('boxcar://%s/%s/@%s' % ('a' * 64, 'b' * 64, 't' * 64), {
        'instance': NotifyBoxcar,
        'requests_response_code': requests.codes.created,
    }),
    ('boxcar://%s/%s/' % ('a' * 64, 'b' * 64), {
        'instance': NotifyBoxcar,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('boxcar://%s/%s/' % ('a' * 64, 'b' * 64), {
        'instance': NotifyBoxcar,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('boxcar://%s/%s/' % ('a' * 64, 'b' * 64), {
        'instance': NotifyBoxcar,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_boxcar_urls():
    """
    NotifyBoxcar() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.get')
@mock.patch('requests.post')
def test_plugin_boxcar_edge_cases(mock_post, mock_get):
    """
    NotifyBoxcar() Edge Cases

    """

    # Generate some generic message types
    device = 'A' * 64
    tag = '@B' * 63

    access = '-' * 64
    secret = '_' * 64

    # Initializes the plugin with recipients set to None
    NotifyBoxcar(access=access, secret=secret, targets=None)

    # Initializes the plugin with a valid access, but invalid access key
    with pytest.raises(TypeError):
        NotifyBoxcar(access=None, secret=secret, targets=None)

    # Initializes the plugin with a valid access, but invalid secret
    with pytest.raises(TypeError):
        NotifyBoxcar(access=access, secret=None, targets=None)

    # Initializes the plugin with recipients list
    # the below also tests our the variation of recipient types
    NotifyBoxcar(
        access=access, secret=secret, targets=[device, tag])

    mock_get.return_value = requests.Request()
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.created
    mock_get.return_value.status_code = requests.codes.created

    # Test notifications without a body or a title
    p = NotifyBoxcar(access=access, secret=secret, targets=None)

    assert p.notify(body=None, title=None, notify_type=NotifyType.INFO) is True

    # Test comma, separate values
    device = 'a' * 64

    p = NotifyBoxcar(
        access=access, secret=secret,
        targets=','.join([device, device, device]))
    assert len(p.device_tokens) == 3
