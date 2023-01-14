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
import requests

from apprise.plugins.NotifyPushjet import NotifyPushjet
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('pjet://', {
        'instance': None,
    }),
    ('pjets://', {
        'instance': None,
    }),
    ('pjet://:@/', {
        'instance': None,
    }),
    #  You must specify a secret key
    ('pjet://%s' % ('a' * 32), {
        'instance': TypeError,
    }),
    # The proper way to log in
    ('pjet://user:pass@localhost/%s' % ('a' * 32), {
        'instance': NotifyPushjet,
    }),
    # The proper way to log in
    ('pjets://localhost/%s' % ('a' * 32), {
        'instance': NotifyPushjet,
    }),
    # Specify your own server with login (secret= MUST be provided)
    ('pjet://user:pass@localhost?secret=%s' % ('a' * 32), {
        'instance': NotifyPushjet,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'pjet://user:****@localhost',
    }),
    # Specify your own server with port
    ('pjets://localhost:8080/%s' % ('a' * 32), {
        'instance': NotifyPushjet,
    }),
    ('pjets://localhost:8080/%s' % ('a' * 32), {
        'instance': NotifyPushjet,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('pjets://localhost:4343/%s' % ('a' * 32), {
        'instance': NotifyPushjet,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('pjet://localhost:8081/%s' % ('a' * 32), {
        'instance': NotifyPushjet,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_pushjet_urls():
    """
    NotifyPushjet() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_pushjet_edge_cases():
    """
    NotifyPushjet() Edge Cases

    """

    # No application Key specified
    with pytest.raises(TypeError):
        NotifyPushjet(secret_key=None)

    with pytest.raises(TypeError):
        NotifyPushjet(secret_key="  ")
