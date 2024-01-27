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

import requests

from apprise.plugins.NotifyNotifiarr import NotifyNotifiarr
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('notifiarr://:@/', {
        'instance': TypeError,
    }),
    ('notifiarr://', {
        'instance': TypeError,
    }),
    ('notifiarr://apikey', {
        'instance': NotifyNotifiarr,

        # Response will fail due to no targets defined
        'notify_response': False,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'notifiarr://a...y',
    }),
    ('notifiarr://apikey/1234/?discord_user=invalid', {
        'instance': TypeError,
    }),
    ('notifiarr://apikey/1234/?discord_role=invalid', {
        'instance': TypeError,
    }),
    ('notifiarr://apikey/1234/?event=invalid', {
        'instance': TypeError,
    }),
    ('notifiarr://apikey/%%invalid%%', {
        'instance': NotifyNotifiarr,

        # Response will fail due to no targets defined
        'notify_response': False,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'notifiarr://a...y',
    }),
    ('notifiarr://apikey/#123', {
        'instance': NotifyNotifiarr,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'notifiarr://a...y/#123'
    }),
    ('notifiarr://apikey/123?image=No', {
        'instance': NotifyNotifiarr,
    }),
    ('notifiarr://apikey/123?image=yes', {
        'instance': NotifyNotifiarr,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'notifiarr://a...y/#123',
    }),
    ('notifiarr://apikey/?to=123,432', {
        'instance': NotifyNotifiarr,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'notifiarr://a...y/#123/#432',
    }),
    ('notifiarr://123/?apikey=myapikey', {
        'instance': NotifyNotifiarr,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'notifiarr://m...y/#123',
    }),
    ('notifiarr://123/?apikey=myapikey&image=yes', {
        'instance': NotifyNotifiarr,
    }),
    ('notifiarr://123/?apikey=myapikey&image=no', {
        'instance': NotifyNotifiarr,
    }),
    ('notifiarr://123/?apikey=myapikey&source=My%20System', {
        'instance': NotifyNotifiarr,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'notifiarr://m...y/#123',
    }),
    ('notifiarr://123/?apikey=myapikey&from=My%20System', {
        'instance': NotifyNotifiarr,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'notifiarr://m...y/#123',
    }),
    ('notifiarr://?apikey=myapikey', {
        # No Channel or host
        'instance': NotifyNotifiarr,
        # Response will fail due to no targets defined
        'notify_response': False,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'notifiarr://m...y/',
    }),
    ('notifiarr://invalid?apikey=myapikey', {
        # No Channel or host
        'instance': NotifyNotifiarr,
        # invalid channel
        'notify_response': False,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'notifiarr://m...y/',
    }),
    ('notifiarr://123/325/?apikey=myapikey', {
        'instance': NotifyNotifiarr,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'notifiarr://m...y/#123/#325',
    }),
    ('notifiarr://12/?key=myapikey&discord_user=23'
     '&discord_role=12&event=123', {
         'instance': NotifyNotifiarr,
         # Our expected url(privacy=True) startswith() response:
         'privacy_url': 'notifiarr://m...y/#12'}),
    ('notifiarr://apikey/123/', {
        'instance': NotifyNotifiarr,
    }),
    ('notifiarr://apikey/123', {
        'instance': NotifyNotifiarr,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('notifiarr://apikey/123', {
        'instance': NotifyNotifiarr,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('notifiarr://apikey/123', {
        'instance': NotifyNotifiarr,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_custom_notifiarr_urls():
    """
    NotifyNotifiarr() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
