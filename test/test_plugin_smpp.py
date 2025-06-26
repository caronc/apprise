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

from apprise.plugins.smpp import NotifySmpp
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
        'instance': NotifySmpp,
        # We have no one to notify
        'notify_response': False,
    }),
    ('smpp://user:pass@host:port/{}'.format('1' * 10), {
        # everything valid
        'instance': NotifySmpp,
        # We have no one to notify
        'notify_response': False,
    }),
    ('smpp://user:pass@host:port/{}/{}'.format('1' * 10, '1' * 10), {
        'instance': NotifySmpp,
    }),
    ('smpp://_?&from={}&to={},{}'.format(
        '1' * 10, '1' * 10, '1' * 10), {
         # use get args to accomplish the same thing
         'instance': NotifySmpp,
     }),
    ('smpp://user:pass@host:port/{}/{}'.format('1' * 10, '1' * 10), {
        'instance': NotifySmpp,
        # throw a bizarre code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('smpp://user:pass@host:port/{}/{}'.format('1' * 10, '1' * 10), {
        'instance': NotifySmpp,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracefully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_smpp_urls():
    """
    NotifySmpp() Apprise URLs
    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
def test_plugin_smpp_edge_cases(mock_post):
    """
    NotifySmpp() Edge Cases
    """

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    # Initialize some generic (but valid) apikeys
    apikey = 'b' * 32
    source = '+1 (555) 123-3456'

    # No apikey specified
    with pytest.raises(TypeError):
        NotifySmpp(source=source)

    # a error response
    response.status_code = 400
    response.content = dumps({
        'code': 21211,
        'message': "The 'To' number +1234567 is not a valid phone number.",
    })
    mock_post.return_value = response

    # Initialize our object
    obj = NotifySmpp(source=source)

    # We will fail with the above error code
    assert obj.notify('title', 'body', 'info') is False
