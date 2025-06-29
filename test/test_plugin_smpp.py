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

import logging
import sys

import pytest
from apprise import Apprise
from apprise.plugins.smpp import NotifySMPP
from helpers import AppriseURLTester

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('smpp://', {
        'instance': None,
    }),
    ('smpp:///', {
        'instance': None,
    }),
    ('smpp://@/', {
        'instance': None,
    }),
    ('smpp://user@/', {
        'instance': None,
    }),
    ('smpp://user:pass/', {
        'instance': None,
    }),
    ('smpp://user:pass@/', {
        'instance': None,
    }),
    ('smpp://user:pass@host:/', {
        'instance': None,
    }),
    ('smpp://user:pass@host:port/', {
        'instance': None,
    }),
    ('smpp://user:pass@host:port/{}/{}'.format('1' * 10, 'a' * 32), {
        # valid everything but target numbers
        'instance': NotifySMPP,
        # We have no one to notify
        'notify_response': False,
    }),
    ('smpp://user:pass@host:port/{}'.format('1' * 10), {
        # everything valid
        'instance': NotifySMPP,
        # We have no one to notify
        'notify_response': False,
    }),
    ('smpp://user:pass@host:port/{}/{}'.format('1' * 10, '1' * 10), {
        'instance': NotifySMPP,
    }),
    ('smpp://_?&from={}&to={},{}'.format(
        '1' * 10, '1' * 10, '1' * 10), {
        # use get args to accomplish the same thing
        'instance': NotifySMPP,
    }),
    ('smpp://user:pass@host:port/{}/{}'.format('1' * 10, '1' * 10), {
        'instance': NotifySMPP,
        # throw a bizarre code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('smpp://user:pass@host:port/{}/{}'.format('1' * 10, '1' * 10), {
        'instance': NotifySMPP,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracefully handle them
        'test_requests_exceptions': True,
    }),
)


@pytest.mark.skipif(
    'python-smpp' in sys.modules,
    reason="Requires that python-smpp NOT be installed")
def test_plugin_fcm_cryptography_import_error():
    """
    NotifySimplePush() python-smpp loading failure
    """

    # Attempt to instantiate our object
    obj = Apprise.instantiate(
        'smpp://user:pass@host:port/{}/{}'.format('1' * 10, '1' * 10))

    # It's not possible because our cryptography depedancy is missing
    assert obj is None


@pytest.mark.skipif(
    'python-smpp' not in sys.modules, reason="Requires python-smpp")
def test_plugin_smpp_urls():
    """
    NotifySMPP() Apprise URLs
    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
