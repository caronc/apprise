# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 Chris Caron <lead2gold@gmail.com>
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

import pytest
import requests
from helpers import AppriseURLTester
from apprise import plugins

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
        'instance': plugins.NotifyGuilded,
        'requests_response_code': requests.codes.no_content,
    }),
    # Provide a temporary username
    ('guilded://l2g@%s/%s' % ('i' * 24, 't' * 64), {
        'instance': plugins.NotifyGuilded,
        'requests_response_code': requests.codes.no_content,
    }),
    # test image= field
    ('guilded://%s/%s?format=markdown&footer=Yes&image=Yes' % (
        'i' * 24, 't' * 64), {
            'instance': plugins.NotifyGuilded,
            'requests_response_code': requests.codes.no_content,
            # don't include an image by default
            'include_image': False,
    }),
    ('guilded://%s/%s?format=markdown&footer=Yes&image=No&fields=no' % (
        'i' * 24, 't' * 64), {
            'instance': plugins.NotifyGuilded,
            'requests_response_code': requests.codes.no_content,
    }),
    ('guilded://%s/%s?format=markdown&footer=Yes&image=Yes' % (
        'i' * 24, 't' * 64), {
            'instance': plugins.NotifyGuilded,
            'requests_response_code': requests.codes.no_content,
    }),
    ('https://media.guilded.gg/webhooks/{}/{}'.format(
        '0' * 10, 'B' * 40), {
            # Native URL Support, support the provided guilded URL from their
            # webpage.
            'instance': plugins.NotifyGuilded,
            'requests_response_code': requests.codes.no_content,
    }),
    ('guilded://%s/%s?format=markdown&avatar=No&footer=No' % (
        'i' * 24, 't' * 64), {
            'instance': plugins.NotifyGuilded,
            'requests_response_code': requests.codes.no_content,
    }),
    # different format support
    ('guilded://%s/%s?format=markdown' % ('i' * 24, 't' * 64), {
        'instance': plugins.NotifyGuilded,
        'requests_response_code': requests.codes.no_content,
    }),
    ('guilded://%s/%s?format=text' % ('i' * 24, 't' * 64), {
        'instance': plugins.NotifyGuilded,
        'requests_response_code': requests.codes.no_content,
    }),
    # Test with avatar URL
    ('guilded://%s/%s?avatar_url=http://localhost/test.jpg' % (
        'i' * 24, 't' * 64), {
            'instance': plugins.NotifyGuilded,
            'requests_response_code': requests.codes.no_content,
    }),
    # Test without image set
    ('guilded://%s/%s' % ('i' * 24, 't' * 64), {
        'instance': plugins.NotifyGuilded,
        'requests_response_code': requests.codes.no_content,
        # don't include an image by default
        'include_image': False,
    }),
    ('guilded://%s/%s/' % ('a' * 24, 'b' * 64), {
        'instance': plugins.NotifyGuilded,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('guilded://%s/%s/' % ('a' * 24, 'b' * 64), {
        'instance': plugins.NotifyGuilded,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('guilded://%s/%s/' % ('a' * 24, 'b' * 64), {
        'instance': plugins.NotifyGuilded,
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
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Initialize some generic (but valid) tokens
    webhook_id = 'A' * 24
    webhook_token = 'B' * 64

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    # Invalid webhook id
    with pytest.raises(TypeError):
        plugins.NotifyGuilded(webhook_id=None, webhook_token=webhook_token)
    # Invalid webhook id (whitespace)
    with pytest.raises(TypeError):
        plugins.NotifyGuilded(webhook_id="  ", webhook_token=webhook_token)

    # Invalid webhook token
    with pytest.raises(TypeError):
        plugins.NotifyGuilded(webhook_id=webhook_id, webhook_token=None)
    # Invalid webhook token (whitespace)
    with pytest.raises(TypeError):
        plugins.NotifyGuilded(webhook_id=webhook_id, webhook_token="   ")

    obj = plugins.NotifyGuilded(
        webhook_id=webhook_id,
        webhook_token=webhook_token,
        footer=True, thumbnail=False)

    # Test that we get a string response
    assert isinstance(obj.url(), str) is True
