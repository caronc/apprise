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
import requests

from apprise.plugins.NotifyEnigma2 import NotifyEnigma2
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
        'instance': NotifyEnigma2,
        # This will fail because we're also expecting a server acknowledgement
        'notify_response': False,
    }),
    ('enigma2://localhost', {
        'instance': NotifyEnigma2,
        # invalid JSON response
        'requests_response_text': '{',
        'notify_response': False,
    }),
    ('enigma2://localhost', {
        'instance': NotifyEnigma2,
        # False is returned
        'requests_response_text': {
            'result': False
        },
        'notify_response': False,
    }),
    ('enigma2://localhost', {
        'instance': NotifyEnigma2,
        # With the right content, this will succeed
        'requests_response_text': {
            'result': True
        }
    }),
    ('enigma2://user@localhost', {
        'instance': NotifyEnigma2,
        'requests_response_text': {
            'result': True
        }
    }),
    # Set timeout
    ('enigma2://user@localhost?timeout=-1', {
        'instance': NotifyEnigma2,
        'requests_response_text': {
            'result': True
        }
    }),
    # Set timeout
    ('enigma2://user@localhost?timeout=-1000', {
        'instance': NotifyEnigma2,
        'requests_response_text': {
            'result': True
        }
    }),
    # Set invalid timeout (defaults to a set value)
    ('enigma2://user@localhost?timeout=invalid', {
        'instance': NotifyEnigma2,
        'requests_response_text': {
            'result': True
        }
    }),
    ('enigma2://user:pass@localhost', {
        'instance': NotifyEnigma2,
        'requests_response_text': {
            'result': True
        },

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'enigma2://user:****@localhost',
    }),
    ('enigma2://localhost:8080', {
        'instance': NotifyEnigma2,
        'requests_response_text': {
            'result': True
        },
    }),
    ('enigma2://user:pass@localhost:8080', {
        'instance': NotifyEnigma2,
        'requests_response_text': {
            'result': True
        },
    }),
    ('enigma2s://localhost', {
        'instance': NotifyEnigma2,
        'requests_response_text': {
            'result': True
        },
    }),
    ('enigma2s://user:pass@localhost', {
        'instance': NotifyEnigma2,
        'requests_response_text': {
            'result': True
        },

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'enigma2s://user:****@localhost',
    }),
    ('enigma2s://localhost:8080/path/', {
        'instance': NotifyEnigma2,
        'requests_response_text': {
            'result': True
        },
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'enigma2s://localhost:8080/path/',
    }),
    ('enigma2s://user:pass@localhost:8080', {
        'instance': NotifyEnigma2,
        'requests_response_text': {
            'result': True
        },
    }),
    ('enigma2://localhost:8080/path?+HeaderKey=HeaderValue', {
        'instance': NotifyEnigma2,
        'requests_response_text': {
            'result': True
        },
    }),
    ('enigma2://user:pass@localhost:8081', {
        'instance': NotifyEnigma2,
        'requests_response_text': {
            'result': True
        },
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('enigma2://user:pass@localhost:8082', {
        'instance': NotifyEnigma2,
        'requests_response_text': {
            'result': True
        },
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('enigma2://user:pass@localhost:8083', {
        'instance': NotifyEnigma2,
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
