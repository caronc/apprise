# -*- coding: utf-8 -*-
# BSD 3-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2023, Chris Caron <lead2gold@gmail.com>
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
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
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

from apprise.plugins.NotifySynology import NotifySynology
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('synology://:@/', {
        'instance': None,
    }),
    ('synology://', {
        'instance': None,
    }),
    ('synologys://', {
        'instance': None,
    }),
    ('synology://localhost/token', {
        'instance': NotifySynology,
    }),
    ('synology://localhost/token?file_url=http://reddit.com/test.jpg', {
        'instance': NotifySynology,
    }),
    ('synology://user:pass@localhost/token', {
        'instance': NotifySynology,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'synology://user:****@localhost/t...n',
    }),
    # No token was specified
    ('synology://user@localhost', {
        'instance': TypeError,
    }),

    ('synology://user@localhost/token', {
        'instance': NotifySynology,
    }),

    # Continue testing other cases
    ('synology://localhost:8080/token', {
        'instance': NotifySynology,
    }),
    ('synology://user:pass@localhost:8080/token', {
        'instance': NotifySynology,
    }),
    ('synologys://localhost/token', {
        'instance': NotifySynology,
    }),
    ('synologys://localhost/?token=mytoken', {
        'instance': NotifySynology,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'synologys://localhost/m...n',
    }),
    ('synologys://user:pass@localhost/token', {
        'instance': NotifySynology,
    }),
    ('synologys://localhost:8080/token/path/', {
        'instance': NotifySynology,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'synologys://localhost:8080/t...n/path/',
    }),
    ('synologys://user:password@localhost:8080/token', {
        'instance': NotifySynology,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'synologys://user:****@localhost:8080/t...n',
    }),
    # Test our Headers
    ('synology://localhost:8080/path?+HeaderKey=HeaderValue', {
        'instance': NotifySynology,
    }),
    ('synology://user:pass@localhost:8081/token', {
        'instance': NotifySynology,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('synology://user:pass@localhost:8082/token', {
        'instance': NotifySynology,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('synology://user:pass@localhost:8083/token', {
        'instance': NotifySynology,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_custom_synology_urls():
    """
    NotifySynology() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
