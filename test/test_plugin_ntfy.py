# -*- coding: utf-8 -*-
#
# Copyright (C) 2022 Chris Caron <lead2gold@gmail.com>
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

# For testing our return response
GOOD_RESPONSE_TEXT = {
    'code': '0',
    'error': 'success',
}

# Our Testing URLs
apprise_url_tests = (
    ('ntfy://', {
        # Initializes okay (as cloud mode) but has no topics to notify
        'instance': plugins.NotifyNtfy,
        # invalid topics specified (nothing to notify)
        # as a result the response type will be false
        'response': False,
    }),
    ('ntfys://', {
        # Initializes okay (as cloud mode) but has no topics to notify
        'instance': plugins.NotifyNtfy,
        # invalid topics specified (nothing to notify)
        # as a result the response type will be false
        'response': False,
    }),
    ('ntfy://:@/', {
        # Initializes okay (as cloud mode) but has no topics to notify
        'instance': plugins.NotifyNtfy,
        # invalid topics specified (nothing to notify)
        # as a result the response type will be false
        'response': False,
    }),
    # No topics
    ('ntfy://user:pass@localhost', {
        'instance': plugins.NotifyNtfy,
        # invalid topics specified (nothing to notify)
        # as a result the response type will be false
        'response': False,
    }),
    # No valid topics
    ('ntfy://user:pass@localhost/#/!/@', {
        'instance': plugins.NotifyNtfy,
        # invalid topics specified (nothing to notify)
        # as a result the response type will be false
        'response': False,
    }),
    # user/pass combos
    ('ntfy://user@localhost/topic/', {
        'instance': plugins.NotifyNtfy,
        'requests_response_text': GOOD_RESPONSE_TEXT,
    }),
    # No user/pass combo
    ('ntfy://localhost/topic1/topic2/', {
        'instance': plugins.NotifyNtfy,
        'requests_response_text': GOOD_RESPONSE_TEXT,
    }),
    # A topic and port identifier
    ('ntfy://user:pass@localhost:8080/topic/', {
        'instance': plugins.NotifyNtfy,
        # The response text is expected to be the following on a success
        'requests_response_text': GOOD_RESPONSE_TEXT,
    }),
    # A topic (using the to=)
    ('ntfys://user:pass@localhost?to=topic', {
        'instance': plugins.NotifyNtfy,
        # The response text is expected to be the following on a success
        'requests_response_text': GOOD_RESPONSE_TEXT,
    }),
    # Several topics
    ('ntfy://user:pass@localhost/topic/topic/?avatar=Yes', {
        'instance': plugins.NotifyNtfy,
        # The response text is expected to be the following on a success
        'requests_response_text': {
            'status': 'success',
            'data': {
                'authToken': 'abcd',
                'userId': 'user',
            },
        },
    }),
    ('ntfys://user:web/token@localhost/topic/?mode=invalid', {
        # Invalid mode
        'instance': TypeError,
    }),
    ('ntfy://user:pass@localhost:8081/topic/topic2', {
        'instance': plugins.NotifyNtfy,
        # force a failure using basic mode
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('ntfy://user:pass@localhost:8082/topic', {
        'instance': plugins.NotifyNtfy,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('ntfy://user:pass@localhost:8083/topic1/topic2/', {
        'instance': plugins.NotifyNtfy,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_ntfy_chat_urls():
    """
    NotifyNtfy() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
