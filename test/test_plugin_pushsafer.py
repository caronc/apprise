# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 Chris Caron <lead2gold@gmail.com>
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

import os
import pytest
from unittest import mock

import requests
from json import dumps
from apprise import AppriseAttachment
from apprise import NotifyType
from apprise import plugins
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), 'var')

# Our Testing URLs
apprise_url_tests = (
    ('psafer://:@/', {
        'instance': TypeError,
    }),
    ('psafer://', {
        'instance': TypeError,
    }),
    ('psafers://', {
        'instance': TypeError,
    }),
    ('psafer://{}'.format('a' * 20), {
        'instance': plugins.NotifyPushSafer,
        # This will fail because we're also expecting a server acknowledgement
        'notify_response': False,
    }),
    ('psafer://{}'.format('b' * 20), {
        'instance': plugins.NotifyPushSafer,
        # invalid JSON response
        'requests_response_text': '{',
        'notify_response': False,
    }),
    ('psafer://{}'.format('c' * 20), {
        'instance': plugins.NotifyPushSafer,
        # A failure has status set to zero
        # We also expect an 'error' flag to be set
        'requests_response_text': {
            'status': 0,
            'error': 'we failed'
        },
        'notify_response': False,
    }),
    ('psafers://{}'.format('d' * 20), {
        'instance': plugins.NotifyPushSafer,
        # A failure has status set to zero
        # Test without an 'error' flag
        'requests_response_text': {
            'status': 0,
        },
        'notify_response': False,
    }),
    # This will notify all users ('a')
    ('psafer://{}'.format('e' * 20), {
        'instance': plugins.NotifyPushSafer,
        # A status of 1 is a success
        'requests_response_text': {
            'status': 1,
        }
    }),
    # This will notify a selected set of devices
    ('psafer://{}/12/24/53'.format('e' * 20), {
        'instance': plugins.NotifyPushSafer,
        # A status of 1 is a success
        'requests_response_text': {
            'status': 1,
        }
    }),
    # Same as above, but exercises the to= argument
    ('psafer://{}?to=12,24,53'.format('e' * 20), {
        'instance': plugins.NotifyPushSafer,
        # A status of 1 is a success
        'requests_response_text': {
            'status': 1,
        }
    }),
    # Set priority
    ('psafer://{}?priority=emergency'.format('f' * 20), {
        'instance': plugins.NotifyPushSafer,
        'requests_response_text': {
            'status': 1,
        }
    }),
    # Support integer value too
    ('psafer://{}?priority=-1'.format('f' * 20), {
        'instance': plugins.NotifyPushSafer,
        'requests_response_text': {
            'status': 1,
        }
    }),
    # Invalid priority
    ('psafer://{}?priority=invalid'.format('f' * 20), {
        # Invalid Priority
        'instance': TypeError,
    }),
    # Invalid priority
    ('psafer://{}?priority=25'.format('f' * 20), {
        # Invalid Priority
        'instance': TypeError,
    }),
    # Set sound
    ('psafer://{}?sound=ok'.format('g' * 20), {
        'instance': plugins.NotifyPushSafer,
        'requests_response_text': {
            'status': 1,
        }
    }),
    # Support integer value too
    ('psafers://{}?sound=14'.format('g' * 20), {
        'instance': plugins.NotifyPushSafer,
        'requests_response_text': {
            'status': 1,
        },
        'privacy_url': 'psafers://g...g',
    }),
    # Invalid sound
    ('psafer://{}?sound=invalid'.format('h' * 20), {
        # Invalid Sound
        'instance': TypeError,
    }),
    ('psafer://{}?sound=94000'.format('h' * 20), {
        # Invalid Sound
        'instance': TypeError,
    }),
    # Set vibration (integer only)
    ('psafers://{}?vibration=1'.format('h' * 20), {
        'instance': plugins.NotifyPushSafer,
        'requests_response_text': {
            'status': 1,
        },
        'privacy_url': 'psafers://h...h',
    }),
    # Invalid sound
    ('psafer://{}?vibration=invalid'.format('h' * 20), {
        # Invalid Vibration
        'instance': TypeError,
    }),
    # Invalid vibration
    ('psafer://{}?vibration=25000'.format('h' * 20), {
        # Invalid Vibration
        'instance': TypeError,
    }),
    ('psafers://{}'.format('d' * 20), {
        'instance': plugins.NotifyPushSafer,
        # A failure has status set to zero
        # Test without an 'error' flag
        'requests_response_text': {
            'status': 0,
        },

        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('psafer://{}'.format('d' * 20), {
        'instance': plugins.NotifyPushSafer,
        # A failure has status set to zero
        # Test without an 'error' flag
        'requests_response_text': {
            'status': 0,
        },

        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('psafers://{}'.format('d' * 20), {
        'instance': plugins.NotifyPushSafer,
        # A failure has status set to zero
        # Test without an 'error' flag
        'requests_response_text': {
            'status': 0,
        },
        # Throws a series of connection and transfer exceptions when this
        # flag is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_pushsafer_urls():
    """
    NotifyPushSafer() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
def test_plugin_pushsafer_general(mock_post):
    """
    NotifyPushSafer() General Tests

    """
    # Disable Throttling to speed testing
    plugins.NotifyPushSafer.request_rate_per_sec = 0

    # Private Key
    privatekey = 'abc123'

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = dumps({
        'status': 1,
        'success': "okay",
    })

    # Exception should be thrown about the fact no private key was specified
    with pytest.raises(TypeError):
        plugins.NotifyPushSafer(privatekey=None)

    # Multiple Attachment Support
    path = os.path.join(TEST_VAR_DIR, 'apprise-test.gif')
    attach = AppriseAttachment()
    for _ in range(0, 4):
        attach.add(path)

    obj = plugins.NotifyPushSafer(privatekey=privatekey)
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is True

    # Test error reading attachment from disk
    with mock.patch('builtins.open', side_effect=OSError):
        obj.notify(
            body='body', title='title', notify_type=NotifyType.INFO,
            attach=attach)

    # Test unsupported mime type
    attach = AppriseAttachment(path)

    attach[0]._mimetype = 'application/octet-stream'

    # We gracefully just don't send the attachment in these cases;
    # The notify itself will still be successful
    mock_post.reset_mock()
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is True

    # the 'p', 'p2', and 'p3' are the data variables used when including an
    # image.
    assert 'data' in mock_post.call_args[1]
    assert 'p' not in mock_post.call_args[1]['data']
    assert 'p2' not in mock_post.call_args[1]['data']
    assert 'p3' not in mock_post.call_args[1]['data']

    # Invalid file path
    path = os.path.join(TEST_VAR_DIR, '/invalid/path/to/an/invalid/file.jpg')
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=path) is False
