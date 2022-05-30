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
from apprise import plugins
import requests
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('enigma2://:@/', {
        'instance': None,
    }),
    ('enigma2://', {
        'instance': None,
    }),
    ('enigma2s://', {
        'instance': None,
    }),
    ('enigma2://localhost', {
        'instance': plugins.NotifyEnigma2,
        # This will fail because we're also expecting a server acknowledgement
        'notify_response': False,
    }),
    ('enigma2://localhost', {
        'instance': plugins.NotifyEnigma2,
        # invalid JSON response
        'requests_response_text': '{',
        'notify_response': False,
    }),
    ('enigma2://localhost', {
        'instance': plugins.NotifyEnigma2,
        # False is returned
        'requests_response_text': {
            'result': False
        },
        'notify_response': False,
    }),
    ('enigma2://localhost', {
        'instance': plugins.NotifyEnigma2,
        # With the right content, this will succeed
        'requests_response_text': {
            'result': True
        }
    }),
    ('enigma2://user@localhost', {
        'instance': plugins.NotifyEnigma2,
        'requests_response_text': {
            'result': True
        }
    }),
    # Set timeout
    ('enigma2://user@localhost?timeout=-1', {
        'instance': plugins.NotifyEnigma2,
        'requests_response_text': {
            'result': True
        }
    }),
    # Set timeout
    ('enigma2://user@localhost?timeout=-1000', {
        'instance': plugins.NotifyEnigma2,
        'requests_response_text': {
            'result': True
        }
    }),
    # Set invalid timeout (defaults to a set value)
    ('enigma2://user@localhost?timeout=invalid', {
        'instance': plugins.NotifyEnigma2,
        'requests_response_text': {
            'result': True
        }
    }),
    ('enigma2://user:pass@localhost', {
        'instance': plugins.NotifyEnigma2,
        'requests_response_text': {
            'result': True
        },

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'enigma2://user:****@localhost',
    }),
    ('enigma2://localhost:8080', {
        'instance': plugins.NotifyEnigma2,
        'requests_response_text': {
            'result': True
        },
    }),
    ('enigma2://user:pass@localhost:8080', {
        'instance': plugins.NotifyEnigma2,
        'requests_response_text': {
            'result': True
        },
    }),
    ('enigma2s://localhost', {
        'instance': plugins.NotifyEnigma2,
        'requests_response_text': {
            'result': True
        },
    }),
    ('enigma2s://user:pass@localhost', {
        'instance': plugins.NotifyEnigma2,
        'requests_response_text': {
            'result': True
        },

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'enigma2s://user:****@localhost',
    }),
    ('enigma2s://localhost:8080/path/', {
        'instance': plugins.NotifyEnigma2,
        'requests_response_text': {
            'result': True
        },
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'enigma2s://localhost:8080/path/',
    }),
    ('enigma2s://user:pass@localhost:8080', {
        'instance': plugins.NotifyEnigma2,
        'requests_response_text': {
            'result': True
        },
    }),
    ('enigma2://localhost:8080/path?+HeaderKey=HeaderValue', {
        'instance': plugins.NotifyEnigma2,
        'requests_response_text': {
            'result': True
        },
    }),
    ('enigma2://user:pass@localhost:8081', {
        'instance': plugins.NotifyEnigma2,
        'requests_response_text': {
            'result': True
        },
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('enigma2://user:pass@localhost:8082', {
        'instance': plugins.NotifyEnigma2,
        'requests_response_text': {
            'result': True
        },
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('enigma2://user:pass@localhost:8083', {
        'instance': plugins.NotifyEnigma2,
        'requests_response_text': {
            'result': True
        },
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_enigma2_urls():
    """
    NotifyEnigma2() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
