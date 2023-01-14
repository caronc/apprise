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

import os
from unittest import mock

import pytest
import requests

from apprise.plugins.NotifyGuilded import NotifyGuilded
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), 'var')

# Our Testing URLs
apprise_url_tests = (
    ('guilded://', {
        'instance': TypeError,
    }),
    # An invalid url
    ('guilded://:@/', {
        'instance': TypeError,
    }),
    # No webhook_token specified
    ('guilded://%s' % ('i' * 24), {
        'instance': TypeError,
    }),
    # Provide both an webhook id and a webhook token
    ('guilded://%s/%s' % ('i' * 24, 't' * 64), {
        'instance': NotifyGuilded,
        'requests_response_code': requests.codes.no_content,
    }),
    # Provide a temporary username
    ('guilded://l2g@%s/%s' % ('i' * 24, 't' * 64), {
        'instance': NotifyGuilded,
        'requests_response_code': requests.codes.no_content,
    }),
    # test image= field
    ('guilded://%s/%s?format=markdown&footer=Yes&image=Yes' % (
        'i' * 24, 't' * 64), {
            'instance': NotifyGuilded,
            'requests_response_code': requests.codes.no_content,
            # don't include an image by default
            'include_image': False,
    }),
    ('guilded://%s/%s?format=markdown&footer=Yes&image=No&fields=no' % (
        'i' * 24, 't' * 64), {
            'instance': NotifyGuilded,
            'requests_response_code': requests.codes.no_content,
    }),
    ('guilded://%s/%s?format=markdown&footer=Yes&image=Yes' % (
        'i' * 24, 't' * 64), {
            'instance': NotifyGuilded,
            'requests_response_code': requests.codes.no_content,
    }),
    ('https://media.guilded.gg/webhooks/{}/{}'.format(
        '0' * 10, 'B' * 40), {
            # Native URL Support, support the provided guilded URL from their
            # webpage.
            'instance': NotifyGuilded,
            'requests_response_code': requests.codes.no_content,
    }),
    ('guilded://%s/%s?format=markdown&avatar=No&footer=No' % (
        'i' * 24, 't' * 64), {
            'instance': NotifyGuilded,
            'requests_response_code': requests.codes.no_content,
    }),
    # different format support
    ('guilded://%s/%s?format=markdown' % ('i' * 24, 't' * 64), {
        'instance': NotifyGuilded,
        'requests_response_code': requests.codes.no_content,
    }),
    ('guilded://%s/%s?format=text' % ('i' * 24, 't' * 64), {
        'instance': NotifyGuilded,
        'requests_response_code': requests.codes.no_content,
    }),
    # Test with avatar URL
    ('guilded://%s/%s?avatar_url=http://localhost/test.jpg' % (
        'i' * 24, 't' * 64), {
            'instance': NotifyGuilded,
            'requests_response_code': requests.codes.no_content,
    }),
    # Test without image set
    ('guilded://%s/%s' % ('i' * 24, 't' * 64), {
        'instance': NotifyGuilded,
        'requests_response_code': requests.codes.no_content,
        # don't include an image by default
        'include_image': False,
    }),
    ('guilded://%s/%s/' % ('a' * 24, 'b' * 64), {
        'instance': NotifyGuilded,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('guilded://%s/%s/' % ('a' * 24, 'b' * 64), {
        'instance': NotifyGuilded,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('guilded://%s/%s/' % ('a' * 24, 'b' * 64), {
        'instance': NotifyGuilded,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_guilded_urls():
    """
    NotifyGuilded() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
def test_plugin_guilded_general(mock_post):
    """
    NotifyGuilded() General Checks

    """

    # Initialize some generic (but valid) tokens
    webhook_id = 'A' * 24
    webhook_token = 'B' * 64

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    # Invalid webhook id
    with pytest.raises(TypeError):
        NotifyGuilded(webhook_id=None, webhook_token=webhook_token)
    # Invalid webhook id (whitespace)
    with pytest.raises(TypeError):
        NotifyGuilded(webhook_id="  ", webhook_token=webhook_token)

    # Invalid webhook token
    with pytest.raises(TypeError):
        NotifyGuilded(webhook_id=webhook_id, webhook_token=None)
    # Invalid webhook token (whitespace)
    with pytest.raises(TypeError):
        NotifyGuilded(webhook_id=webhook_id, webhook_token="   ")

    obj = NotifyGuilded(
        webhook_id=webhook_id,
        webhook_token=webhook_token,
        footer=True, thumbnail=False)

    # Test that we get a string response
    assert isinstance(obj.url(), str) is True
