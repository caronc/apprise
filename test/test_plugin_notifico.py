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
import requests
from apprise import plugins
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('notifico://', {
        'instance': TypeError,
    }),
    ('notifico://:@/', {
        'instance': TypeError,
    }),
    ('notifico://1234', {
        # Just a project id provided (no message token)
        'instance': TypeError,
    }),
    ('notifico://abcd/ckhrjW8w672m6HG', {
        # an invalid project id provided
        'instance': TypeError,
    }),
    ('notifico://1234/ckhrjW8w672m6HG', {
        # A project id and message hook provided
        'instance': plugins.NotifyNotifico,
    }),
    ('notifico://1234/ckhrjW8w672m6HG?prefix=no', {
        # Disable our prefix
        'instance': plugins.NotifyNotifico,
    }),
    ('notifico://1234/ckhrjW8w672m6HG?color=yes', {
        'instance': plugins.NotifyNotifico,
        'notify_type': 'info',
    }),
    ('notifico://1234/ckhrjW8w672m6HG?color=yes', {
        'instance': plugins.NotifyNotifico,
        'notify_type': 'success',
    }),
    ('notifico://1234/ckhrjW8w672m6HG?color=yes', {
        'instance': plugins.NotifyNotifico,
        'notify_type': 'warning',
    }),
    ('notifico://1234/ckhrjW8w672m6HG?color=yes', {
        'instance': plugins.NotifyNotifico,
        'notify_type': 'failure',
    }),
    ('notifico://1234/ckhrjW8w672m6HG?color=yes', {
        'instance': plugins.NotifyNotifico,
        'notify_type': 'invalid',
    }),
    ('notifico://1234/ckhrjW8w672m6HG?color=no', {
        # Test our color flag by having it set to off
        'instance': plugins.NotifyNotifico,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'notifico://1...4/c...G',
    }),
    # Support Native URLs
    ('https://n.tkte.ch/h/2144/uJmKaBW9WFk42miB146ci3Kj', {
        'instance': plugins.NotifyNotifico,
    }),
    ('notifico://1234/ckhrjW8w672m6HG', {
        'instance': plugins.NotifyNotifico,
        # don't include an image by default
        'include_image': False,
    }),
    ('notifico://1234/ckhrjW8w672m6HG', {
        'instance': plugins.NotifyNotifico,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('notifico://1234/ckhrjW8w672m6HG', {
        'instance': plugins.NotifyNotifico,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('notifico://1234/ckhrjW8w672m6HG', {
        'instance': plugins.NotifyNotifico,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_notifico_urls():
    """
    NotifyNotifico() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
