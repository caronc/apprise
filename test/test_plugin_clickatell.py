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
from json import dumps
from unittest import mock

import pytest
import requests

from apprise.plugins.clickatell import NotifyClickatell
from helpers import AppriseURLTester

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('clickatell://', {
        # only schema provided
        'instance': TypeError,
    }),
    ('clickatell:///', {
        # invalid api_token
        'instance': TypeError,
    }),
    ('clickatell://@/', {
        # invalid api_token
        'instance': TypeError,
    }),
    ('clickatell://{}/'.format('a' * 32), {
        # no targets provided
        'instance': TypeError,
    }),
    ('clickatell://{}@/'.format('a' * 32), {
        # no targets provided
        'instance': TypeError,
    }),
    ('clickatell://{}@{}/'.format('a' * 32, '1' * 9), {
        # no targets provided
        'instance': TypeError,
    }),
    ('clickatell://{}@{}'.format('a' * 32, 'b' * 32, '3' * 9), {
        # no targets provided
        'instance': TypeError,
    }),
    ('clickatell://{}@{}/123/{}/abcd'.format(
        'a' * 32, '1' * 6, '3' * 11), {
         # valid everything but target numbers
         'instance': NotifyClickatell,
     }),
    ('clickatell://{}/{}'.format('a' * 32, '1' * 9), {
        # everything valid
        'instance': NotifyClickatell,
    }),
    ('clickatell://{}@{}/{}'.format('a' * 32, '1' * 9, '1' * 9), {
        # everything valid
        'instance': NotifyClickatell,
    }),
    ('clickatell://_?token={}&from={}&to={},{}'.format(
        'a' * 32, '1' * 9, '1' * 9, '1' * 9), {
         # use get args to accomplish the same thing
         'instance': NotifyClickatell,
     }),
    ('clickatell://_?token={}'.format('a' * 32), {
        # use get args
        'instance': NotifyClickatell,
        'notify_response': False,
    }),
    ('clickatell://_?token={}&from={}'.format('a' * 32, '1' * 9), {
        # use get args
        'instance': NotifyClickatell,
        'notify_response': False,
    }),
    ('clickatell://{}/{}'.format('a' * 32, '1' * 9), {
        'instance': NotifyClickatell,
        # throw a bizarre code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('clickatell://{}@{}/{}'.format('a' * 32, '1' * 9, '1' * 9), {
        'instance': NotifyClickatell,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracefully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_clickatell_urls():
    """
    NotifyClickatell() Apprise URLs
    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
def test_plugin_clickatell_edge_cases(mock_post):
    """
    NotifyClickatell() Edge Cases
    """

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    # Initialize some generic (but valid) tokens
    api_token = 'b' * 32
    from_phone = '+1 (555) 123-3456'

    # No api_token specified
    with pytest.raises(TypeError):
        NotifyClickatell(api_token=None, from_phone=from_phone)

    # a error response
    response.status_code = 400
    response.content = dumps({
        'code': 21211,
        'message': "The 'To' number +1234567 is not a valid phone number.",
    })
    mock_post.return_value = response

    # Initialize our object
    obj = NotifyClickatell(api_token=api_token, from_phone=from_phone)

    # We will fail with the above error code
    assert obj.notify('title', 'body', 'info') is False
