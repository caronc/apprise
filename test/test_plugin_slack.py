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
from unittest import mock

import pytest
import requests
from apprise import plugins
from apprise import NotifyType
from apprise import AppriseAttachment
from helpers import AppriseURLTester

from json import dumps

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), 'var')

# Our Testing URLs
apprise_url_tests = (
    ('slack://', {
        'instance': TypeError,
    }),
    ('slack://:@/', {
        'instance': TypeError,
    }),
    ('slack://T1JJ3T3L2', {
        # Just Token 1 provided
        'instance': TypeError,
    }),
    ('slack://T1JJ3T3L2/A1BRTD4JD/', {
        # Just 2 tokens provided
        'instance': TypeError,
    }),
    ('slack://T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/#hmm/#-invalid-', {
        # No username specified; this is still okay as we sub in
        # default; The one invalid channel is skipped when sending a message
        'instance': plugins.NotifySlack,
        # There is an invalid channel that we will fail to deliver to
        # as a result the response type will be false
        'response': False,
        'requests_response_text': {
            'ok': False,
            'message': 'Bad Channel',
        },
    }),
    ('slack://T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/#channel', {
        # No username specified; this is still okay as we sub in
        # default; The one invalid channel is skipped when sending a message
        'instance': plugins.NotifySlack,
        # don't include an image by default
        'include_image': False,
        'requests_response_text': 'ok'
    }),
    ('slack://T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/+id/@id/', {
        # + encoded id,
        # @ userid
        'instance': plugins.NotifySlack,
        'requests_response_text': 'ok',
    }),
    ('slack://username@T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/'
        '?to=#nuxref', {
            'instance': plugins.NotifySlack,

            # Our expected url(privacy=True) startswith() response:
            'privacy_url': 'slack://username@T...2/A...D/T...Q/',
            'requests_response_text': 'ok',
        }),
    ('slack://username@T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/#nuxref', {
        'instance': plugins.NotifySlack,
        'requests_response_text': 'ok',
    }),
    # You can't send to email using webhook
    ('slack://T1JJ3T3L2/A1BRTD4JD/TIiajkdnl/user@gmail.com', {
        'instance': plugins.NotifySlack,
        'requests_response_text': 'ok',
        # we'll have a notify response failure in this case
        'notify_response': False,
    }),
    # Specify Token on argument string (with username)
    ('slack://bot@_/#nuxref?token=T1JJ3T3L2/A1BRTD4JD/TIiajkdnadfdajkjkfl/', {
        'instance': plugins.NotifySlack,
        'requests_response_text': 'ok',
    }),
    # Specify Token and channels on argument string (no username)
    ('slack://?token=T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/&to=#chan', {
        'instance': plugins.NotifySlack,
        'requests_response_text': 'ok',
    }),
    # Test webhook that doesn't have a proper response
    ('slack://username@T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/#nuxref', {
        'instance': plugins.NotifySlack,
        'requests_response_text': 'fail',
        # we'll have a notify response failure in this case
        'notify_response': False,
    }),
    # Test using a bot-token (also test footer set to no flag)
    ('slack://username@xoxb-1234-1234-abc124/#nuxref?footer=no', {
        'instance': plugins.NotifySlack,
        'requests_response_text': {
            'ok': True,
            'message': '',
            # support attachments
            'file': {
                'url_private': 'http://localhost/',
            },
        },
    }),
    # Test blocks mode
    ('slack://?token=T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/'
     '&to=#chan&blocks=yes&footer=yes',
        {
            'instance': plugins.NotifySlack,
            'requests_response_text': 'ok'}),
    ('slack://?token=T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/'
     '&to=#chan&blocks=yes&footer=no',
        {
            'instance': plugins.NotifySlack,
            'requests_response_text': 'ok'}),
    ('slack://?token=T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/'
     '&to=#chan&blocks=yes&footer=yes&image=no',
        {
            'instance': plugins.NotifySlack,
            'requests_response_text': 'ok'}),
    ('slack://?token=T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/'
     '&to=#chan&blocks=yes&format=text',
        {
            'instance': plugins.NotifySlack,
            'requests_response_text': 'ok'}),
    ('slack://?token=T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/'
     '&to=#chan&blocks=no&format=text',
        {
            'instance': plugins.NotifySlack,
            'requests_response_text': 'ok'}),

    # Test using a bot-token as argument
    ('slack://?token=xoxb-1234-1234-abc124&to=#nuxref&footer=no&user=test', {
        'instance': plugins.NotifySlack,
        'requests_response_text': {
            'ok': True,
            'message': '',
            # support attachments
            'file': {
                'url_private': 'http://localhost/',
            },
        },
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'slack://test@x...4/nuxref/',
    }),
    # We contain 1 or more invalid channels, so we'll fail on our notify call
    ('slack://?token=xoxb-1234-1234-abc124&to=#nuxref,#$,#-&footer=no', {
        'instance': plugins.NotifySlack,
        'requests_response_text': {
            'ok': True,
            'message': '',
            # support attachments
            'file': {
                'url_private': 'http://localhost/',
            },
        },
        # We fail because of the empty channel #$ and #-
        'notify_response': False,
    }),
    ('slack://username@xoxb-1234-1234-abc124/#nuxref', {
        'instance': plugins.NotifySlack,
        'requests_response_text': {
            'ok': True,
            'message': '',
        },
        # we'll fail to send attachments because we had no 'file' response in
        # our object
        'response': False,
    }),

    ('slack://username@T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ', {
        # Missing a channel, falls back to webhook channel bindings
        'instance': plugins.NotifySlack,
        'requests_response_text': 'ok',
    }),
    # Native URL Support, take the slack URL and still build from it
    ('https://hooks.slack.com/services/{}/{}/{}'.format(
        'A' * 9, 'B' * 9, 'c' * 24), {
        'instance': plugins.NotifySlack,
        'requests_response_text': 'ok',
    }),
    # Native URL Support with arguments
    ('https://hooks.slack.com/services/{}/{}/{}?format=text'.format(
        'A' * 9, 'B' * 9, 'c' * 24), {
        'instance': plugins.NotifySlack,
        'requests_response_text': 'ok',
    }),
    ('slack://username@-INVALID-/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/#cool', {
        # invalid 1st Token
        'instance': TypeError,
    }),
    ('slack://username@T1JJ3T3L2/-INVALID-/TIiajkdnlazkcOXrIdevi7FQ/#great', {
        # invalid 2rd Token
        'instance': TypeError,
    }),
    ('slack://username@T1JJ3T3L2/A1BRTD4JD/-INVALID-/#channel', {
        # invalid 3rd Token
        'instance': TypeError,
    }),
    ('slack://l2g@T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/#usenet', {
        'instance': plugins.NotifySlack,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
        'requests_response_text': 'ok',
    }),
    ('slack://respect@T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/#a', {
        'instance': plugins.NotifySlack,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
        'requests_response_text': 'ok',
    }),
    ('slack://notify@T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/#b', {
        'instance': plugins.NotifySlack,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
        'requests_response_text': 'ok',
    }),
)


def test_plugin_slack_urls():
    """
    NotifySlack() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
def test_plugin_slack_oauth_access_token(mock_post):
    """
    NotifySlack() OAuth Access Token Tests

    """
    # Disable Throttling to speed testing
    plugins.NotifySlack.request_rate_per_sec = 0

    # Generate an invalid bot token
    token = 'xo-invalid'

    request = mock.Mock()
    request.content = dumps({
        'ok': True,
        'message': '',

        # Attachment support
        'file': {
            'url_private': 'http://localhost',
        }
    })
    request.status_code = requests.codes.ok

    # We'll fail to validate the access_token
    with pytest.raises(TypeError):
        plugins.NotifySlack(access_token=token)

    # Generate a (valid) bot token
    token = 'xoxb-1234-1234-abc124'

    # Prepare Mock
    mock_post.return_value = request

    # Variation Initializations
    obj = plugins.NotifySlack(access_token=token, targets='#apprise')
    assert isinstance(obj, plugins.NotifySlack) is True
    assert isinstance(obj.url(), str) is True

    # apprise room was found
    assert obj.send(body="test") is True

    # Test Valid Attachment
    mock_post.reset_mock()

    path = os.path.join(TEST_VAR_DIR, 'apprise-test.gif')
    attach = AppriseAttachment(path)
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is True

    assert mock_post.call_count == 2
    assert mock_post.call_args_list[0][0][0] == \
        'https://slack.com/api/chat.postMessage'
    assert mock_post.call_args_list[1][0][0] == \
        'https://slack.com/api/files.upload'

    # Test a valid attachment that throws an Connection Error
    mock_post.return_value = None
    mock_post.side_effect = (request, requests.ConnectionError(
        0, 'requests.ConnectionError() not handled'))
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is False

    # Test a valid attachment that throws an OSError
    mock_post.return_value = None
    mock_post.side_effect = (request, OSError(0, 'OSError'))
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is False

    # Reset our mock object back to how it was
    mock_post.return_value = request
    mock_post.side_effect = None

    # Test invalid attachment
    path = os.path.join(TEST_VAR_DIR, '/invalid/path/to/an/invalid/file.jpg')
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=path) is False

    # Test case where expected return attachment payload is invalid
    request.content = dumps({
        'ok': True,
        'message': '',

        # Attachment support
        'file': None
    })
    path = os.path.join(TEST_VAR_DIR, 'apprise-test.gif')
    attach = AppriseAttachment(path)
    # We'll fail because of the bad 'file' response
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is False

    # Slack requests pay close attention to the response to determine
    # if things go well... this is not a good JSON response:
    request.content = '{'

    # As a result, we'll fail to send our notification
    assert obj.send(body="test", attach=attach) is False

    request.content = dumps({
        'ok': False,
        'message': 'We failed',
    })

    # A response from Slack (even with a 200 response) still
    # results in a failure:
    assert obj.send(body="test", attach=attach) is False

    # Handle exceptions reading our attachment from disk (should it happen)
    mock_post.side_effect = OSError("Attachment Error")
    mock_post.return_value = None

    # We'll fail now because of an internal exception
    assert obj.send(body="test") is False

    # Test Email Lookup


@mock.patch('requests.post')
def test_plugin_slack_webhook_mode(mock_post):
    """
    NotifySlack() Webhook Mode Tests

    """
    # Disable Throttling to speed testing
    plugins.NotifySlack.request_rate_per_sec = 0

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = 'ok'
    mock_post.return_value.text = 'ok'

    # Initialize some generic (but valid) tokens
    token_a = 'A' * 9
    token_b = 'B' * 9
    token_c = 'c' * 24

    # Support strings
    channels = 'chan1,#chan2,+BAK4K23G5,@user,,,'

    obj = plugins.NotifySlack(
        token_a=token_a, token_b=token_b, token_c=token_c, targets=channels)
    assert len(obj.channels) == 4

    # This call includes an image with it's payload:
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is True

    # Missing first Token
    with pytest.raises(TypeError):
        plugins.NotifySlack(
            token_a=None, token_b=token_b, token_c=token_c,
            targets=channels)

    # Test include_image
    obj = plugins.NotifySlack(
        token_a=token_a, token_b=token_b, token_c=token_c, targets=channels,
        include_image=True)

    # This call includes an image with it's payload:
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is True


@mock.patch('requests.post')
@mock.patch('requests.get')
def test_plugin_slack_send_by_email(mock_get, mock_post):
    """
    NotifySlack() Send by Email Tests

    """
    # Disable Throttling to speed testing
    plugins.NotifySlack.request_rate_per_sec = 0

    # Generate a (valid) bot token
    token = 'xoxb-1234-1234-abc124'

    request = mock.Mock()
    request.content = dumps({
        'ok': True,
        'message': '',
        'user': {
            'id': 'ABCD1234'
        }
    })
    request.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = request
    mock_get.return_value = request

    # Variation Initializations
    obj = plugins.NotifySlack(access_token=token, targets='user@gmail.com')
    assert isinstance(obj, plugins.NotifySlack) is True
    assert isinstance(obj.url(), str) is True

    # No calls made yet
    assert mock_post.call_count == 0
    assert mock_get.call_count == 0

    # Send our notification
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is True

    # 2 calls were made, one to perform an email lookup, the second
    # was the notification itself
    assert mock_get.call_count == 1
    assert mock_post.call_count == 1
    assert mock_get.call_args_list[0][0][0] == \
        'https://slack.com/api/users.lookupByEmail'
    assert mock_post.call_args_list[0][0][0] == \
        'https://slack.com/api/chat.postMessage'

    # Reset our mock object
    mock_post.reset_mock()
    mock_get.reset_mock()

    # Prepare Mock
    mock_post.return_value = request
    mock_get.return_value = request

    # Send our notification again (cached copy of user id associated with
    # email is used)
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is True

    assert mock_get.call_count == 0
    assert mock_post.call_count == 1
    assert mock_post.call_args_list[0][0][0] == \
        'https://slack.com/api/chat.postMessage'

    #
    # Now test a case where we can't look up the valid email
    #
    request.content = dumps({
        'ok': False,
        'message': '',
    })

    # Reset our mock object
    mock_post.reset_mock()
    mock_get.reset_mock()

    # Prepare Mock
    mock_post.return_value = request
    mock_get.return_value = request

    # Variation Initializations
    obj = plugins.NotifySlack(access_token=token, targets='user@gmail.com')
    assert isinstance(obj, plugins.NotifySlack) is True
    assert isinstance(obj.url(), str) is True

    # No calls made yet
    assert mock_post.call_count == 0
    assert mock_get.call_count == 0

    # Send our notification; it will fail because we failed to look up
    # the user id
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is False

    # We would have failed to look up the email, therefore we wouldn't have
    # even bothered to attempt to send the notification
    assert mock_get.call_count == 1
    assert mock_post.call_count == 0
    assert mock_get.call_args_list[0][0][0] == \
        'https://slack.com/api/users.lookupByEmail'

    #
    # Now test a case where we have a poorly formatted JSON response
    #
    request.content = '}'

    # Reset our mock object
    mock_post.reset_mock()
    mock_get.reset_mock()

    # Prepare Mock
    mock_post.return_value = request
    mock_get.return_value = request

    # Variation Initializations
    obj = plugins.NotifySlack(access_token=token, targets='user@gmail.com')
    assert isinstance(obj, plugins.NotifySlack) is True
    assert isinstance(obj.url(), str) is True

    # No calls made yet
    assert mock_post.call_count == 0
    assert mock_get.call_count == 0

    # Send our notification; it will fail because we failed to look up
    # the user id
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is False

    # We would have failed to look up the email, therefore we wouldn't have
    # even bothered to attempt to send the notification
    assert mock_get.call_count == 1
    assert mock_post.call_count == 0
    assert mock_get.call_args_list[0][0][0] == \
        'https://slack.com/api/users.lookupByEmail'

    #
    # Now test a case where we have a poorly formatted JSON response
    #
    request.content = '}'

    # Reset our mock object
    mock_post.reset_mock()
    mock_get.reset_mock()

    # Prepare Mock
    mock_post.return_value = request
    mock_get.return_value = request

    # Variation Initializations
    obj = plugins.NotifySlack(access_token=token, targets='user@gmail.com')
    assert isinstance(obj, plugins.NotifySlack) is True
    assert isinstance(obj.url(), str) is True

    # No calls made yet
    assert mock_post.call_count == 0
    assert mock_get.call_count == 0

    # Send our notification; it will fail because we failed to look up
    # the user id
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is False

    # We would have failed to look up the email, therefore we wouldn't have
    # even bothered to attempt to send the notification
    assert mock_get.call_count == 1
    assert mock_post.call_count == 0
    assert mock_get.call_args_list[0][0][0] == \
        'https://slack.com/api/users.lookupByEmail'

    #
    # Now test a case where we throw an exception trying to perform the lookup
    #

    request.content = dumps({
        'ok': True,
        'message': '',
        'user': {
            'id': 'ABCD1234'
        }
    })
    # Create an unauthorized response
    request.status_code = requests.codes.ok

    # Reset our mock object
    mock_post.reset_mock()
    mock_get.reset_mock()

    # Prepare Mock
    mock_post.return_value = request
    mock_get.side_effect = requests.ConnectionError(
        0, 'requests.ConnectionError() not handled')

    # Variation Initializations
    obj = plugins.NotifySlack(access_token=token, targets='user@gmail.com')
    assert isinstance(obj, plugins.NotifySlack) is True
    assert isinstance(obj.url(), str) is True

    # No calls made yet
    assert mock_post.call_count == 0
    assert mock_get.call_count == 0

    # Send our notification; it will fail because we failed to look up
    # the user id
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is False

    # We would have failed to look up the email, therefore we wouldn't have
    # even bothered to attempt to send the notification
    assert mock_get.call_count == 1
    assert mock_post.call_count == 0
    assert mock_get.call_args_list[0][0][0] == \
        'https://slack.com/api/users.lookupByEmail'
