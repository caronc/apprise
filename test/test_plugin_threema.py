# -*- coding: utf-8 -*-
# BSD 2-Clause License
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

from unittest import mock

import pytest
import requests

from apprise.plugins.NotifyThreema import NotifyThreema
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('threema://', {
        # No user/secret specified
        'instance': TypeError,
    }),
    ('threema://@:', {
        # Invalid url
        'instance': TypeError,
    }),
    ('threema://user@secret', {
        # username must be 8 characters in len
        'instance': TypeError,
    }),
    ('threema://username@secret/{targets}/'.format(
        targets='/'.join(['2222'])), {

        # Invalid target phone number
        'instance': NotifyThreema,
        'notify_response': False,
        'privacy_url': 'threema://u...e@s...t/2222',
    }),
    ('threema://username@secret/{targets}/'.format(
        targets='/'.join(['16134442222'])), {

        # Valid
        'instance': NotifyThreema,
        'privacy_url': 'threema://u...e@s...t/16134442222',
    }),
    ('threema://username@secret/{targets}/'.format(
        targets='/'.join(['16134442222', '16134443333'])), {

        # Valid multiple targets
        'instance': NotifyThreema,
        'privacy_url': 'threema://u...e@s...t/16134442222/16134443333',
    }),
    ('threema:///?secret=secret&from=username&to={targets}'.format(
        targets=','.join(['16134448888', 'user@gmail.com', 'abcd1234'])), {

        # Valid
        'instance': NotifyThreema,
    }),
    ('threema://username@secret/', {
        'instance': NotifyThreema,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('threema://username@secret/', {
        'instance': NotifyThreema,
        # Throws a series of errors
        'test_requests_exceptions': True,
    }),
)


def test_plugin_threema():
    """
    NotifyThreema() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@ mock.patch('requests.get')
def test_plugin_threema_edge_cases(mock_get):
    """
    NotifyThreema() Edge Cases

    """

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_get.return_value = response

    # Initialize some generic (but valid) tokens
    user = 'username'
    targets = '+1 (555) 123-9876'

    # No email specified
    with pytest.raises(TypeError):
        NotifyThreema(user=user, secret=None, targets=targets)
