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

import requests

from apprise.plugins.notifico import NotifyNotifico
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
    ('notifico://example.com/1234', {
        # Just a project id provided (no message token)
        'instance': TypeError,
    }),
    ('notifico://example.com/abcd/ckhrjW8w672m6HG', {
        # an invalid project id provided
        'instance': TypeError,
    }),
    ('notifico://example.com/1234/%34^j$', {
        # A project id and invalid message hook provided
        'instance': TypeError,
    }),
    ('notifico://example.com/1234/ckhrjW8w672m6HG', {
        # A project id and message hook provided
        'instance': NotifyNotifico,
    }),
    ('notifico://example.com/1234/ckhrjW8w672m6HG?prefix=no', {
        # Disable our prefix
        'instance': NotifyNotifico,
    }),
    ('notifico://user@example.com:20/1234/ckhrjW8w672m6HG?color=yes', {
        'instance': NotifyNotifico,
        'notify_type': 'info',
    }),
    ('notificos://user:pass@example.com/1234/ckhrjW8w672m6HG?color=yes', {
        'instance': NotifyNotifico,
        'notify_type': 'success',
    }),
    ('notificos://user:pass@example.com/'
     '?project=1234&token=ckhrjW8w672m6HG&color=yes', {
         'instance': NotifyNotifico,
         'notify_type': 'success',

         # Our expected url(privacy=True) startswith() response:
         'privacy_url': 'notificos://user:****@example.com/1...4/c...G'}),

    ('notifico://example.com/1234/ckhrjW8w672m6HG?color=yes', {
        'instance': NotifyNotifico,
        'notify_type': 'warning',
    }),
    ('notificos://example.com/1234/ckhrjW8w672m6HG?color=yes', {
        'instance': NotifyNotifico,
        'notify_type': 'failure',
    }),
    ('notifico://example.com/1234/ckhrjW8w672m6HG?color=yes', {
        'instance': NotifyNotifico,
        'notify_type': 'invalid',
    }),
    ('notifico://example.com/1234/ckhrjW8w672m6HG?color=no', {
        # Test our color flag by having it set to off
        'instance': NotifyNotifico,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'notifico://example.com/1...4/c...G',
    }),
    ('notifico://example.com/1234/ckhrjW8w672m6HG', {
        'instance': NotifyNotifico,
        # don't include an image by default
        'include_image': False,
    }),
    ('notifico://example.com/1234/ckhrjW8w672m6HG', {
        'instance': NotifyNotifico,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('notifico://example.com/1234/ckhrjW8w672m6HG', {
        'instance': NotifyNotifico,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('notifico://example.com/1234/ckhrjW8w672m6HG', {
        'instance': NotifyNotifico,
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
