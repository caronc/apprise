# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2024, Chris Caron <lead2gold@gmail.com>
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
    ('boxcar://?access=%s&secret=%s&to=tag5' % ('d' * 64, 'b' * 64), {
        # Test access and secret kwargs
        'privacy_url': 'boxcar://d...d/****/',
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

    # Neither a title or body was specified
    assert p.notify(
        body=None, title=None, notify_type=NotifyType.INFO) is False

    # Acceptable when data is provided:
    assert p.notify(
        body="Test", title=None, notify_type=NotifyType.INFO) is True

    # Test comma, separate values
    device = 'a' * 64
    p = NotifyBoxcar(
        access=access, secret=secret,
        targets=','.join([device, device, device]))
    # unique entries are colapsed into 1
    assert len(p.device_tokens) == 1

    p = NotifyBoxcar(
        access=access, secret=secret,
        targets=','.join(['a' * 64, 'b' * 64, 'c' * 64]))
    # not unique, so we get the same data here
    assert len(p.device_tokens) == 3
