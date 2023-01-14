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

import os
from unittest import mock

import requests

from apprise.plugins.NotifyMailgun import NotifyMailgun
from helpers import AppriseURLTester
from apprise import Apprise
from apprise import AppriseAttachment
from apprise import NotifyType

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), 'var')

# Our Testing URLs
apprise_url_tests = (
    ('mailgun://', {
        'instance': TypeError,
    }),
    ('mailgun://:@/', {
        'instance': TypeError,
    }),
    # No Token specified
    ('mailgun://user@localhost.localdomain', {
        'instance': TypeError,
    }),
    # Token is valid, but no user name specified
    ('mailgun://localhost.localdomain/{}-{}-{}'.format(
        'a' * 32, 'b' * 8, 'c' * 8), {
        'instance': TypeError,
    }),
    # Invalid from email address
    ('mailgun://"@localhost.localdomain/{}-{}-{}'.format(
        'a' * 32, 'b' * 8, 'c' * 8), {
        'instance': TypeError,
    }),
    # No To email address, but everything else is valid
    ('mailgun://user@localhost.localdomain/{}-{}-{}'.format(
        'a' * 32, 'b' * 8, 'c' * 8), {
        'instance': NotifyMailgun,
    }),
    ('mailgun://user@localhost.localdomain/{}-{}-{}?format=markdown'.format(
        'a' * 32, 'b' * 8, 'c' * 8), {
        'instance': NotifyMailgun,
    }),
    ('mailgun://user@localhost.localdomain/{}-{}-{}?format=html'.format(
        'a' * 32, 'b' * 8, 'c' * 8), {
        'instance': NotifyMailgun,
    }),
    ('mailgun://user@localhost.localdomain/{}-{}-{}?format=text'.format(
        'a' * 32, 'b' * 8, 'c' * 8), {
        'instance': NotifyMailgun,
    }),
    # valid url with region specified (case insensitve)
    ('mailgun://user@localhost.localdomain/{}-{}-{}?region=uS'.format(
        'a' * 32, 'b' * 8, 'c' * 8), {
            'instance': NotifyMailgun,
    }),
    # valid url with region specified (case insensitve)
    ('mailgun://user@localhost.localdomain/{}-{}-{}?region=EU'.format(
        'a' * 32, 'b' * 8, 'c' * 8), {
            'instance': NotifyMailgun,
    }),
    # invalid url with region specified (case insensitve)
    ('mailgun://user@localhost.localdomain/{}-{}-{}?region=invalid'.format(
        'a' * 32, 'b' * 8, 'c' * 8), {
            'instance': TypeError,
    }),
    # Use of both 'name' and 'from' together; these are synonymous
    ('mailgun://user@localhost.localdomain/{}-{}-{}?'
     'from=jack@gmail.com&name=Jason<jason@gmail.com>'.format(
         'a' * 32, 'b' * 8, 'c' * 8), {
             'instance': NotifyMailgun}),

    # headers
    ('mailgun://user@localhost.localdomain/{}-{}-{}'
        '?+X-Customer-Campaign-ID=Apprise'.format(
            'a' * 32, 'b' * 8, 'c' * 8), {
                'instance': NotifyMailgun,
        }),
    # template tokens
    ('mailgun://user@localhost.localdomain/{}-{}-{}'
        '?:name=Chris&:status=admin'.format(
            'a' * 32, 'b' * 8, 'c' * 8), {
                'instance': NotifyMailgun,
        }),
    # We can use the `from=` directive as well:
    ('mailgun://user@localhost.localdomain/{}-{}-{}'
        '?:from=Chris&:status=admin'.format(
            'a' * 32, 'b' * 8, 'c' * 8), {
                'instance': NotifyMailgun,
        }),
    # bcc and cc
    ('mailgun://user@localhost.localdomain/{}-{}-{}'
        '?bcc=user@example.com&cc=user2@example.com'.format(
            'a' * 32, 'b' * 8, 'c' * 8), {
                'instance': NotifyMailgun,
        }),
    # One To Email address
    ('mailgun://user@localhost.localdomain/{}-{}-{}/test@example.com'.format(
        'a' * 32, 'b' * 8, 'c' * 8), {
            'instance': NotifyMailgun,
    }),
    ('mailgun://user@localhost.localdomain/'
        '{}-{}-{}?to=test@example.com'.format(
            'a' * 32, 'b' * 8, 'c' * 8), {
                'instance': NotifyMailgun}),
    # One To Email address, a from name specified too
    ('mailgun://user@localhost.localdomain/{}-{}-{}/'
        'test@example.com?name="Frodo"'.format(
            'a' * 32, 'b' * 8, 'c' * 8), {
                'instance': NotifyMailgun}),
    # Invalid 'To' Email address
    ('mailgun://user@localhost.localdomain/{}-{}-{}/invalid'.format(
        'a' * 32, 'b' * 8, 'c' * 8), {
            'instance': NotifyMailgun,
            # Expected notify() response
            'notify_response': False,
    }),
    # Multiple 'To', 'Cc', and 'Bcc' addresses (with invalid ones)
    ('mailgun://user@example.com/{}-{}-{}/{}?bcc={}&cc={}'.format(
        'a' * 32, 'b' * 8, 'c' * 8,
        '/'.join(('user1@example.com', 'invalid', 'User2:user2@example.com')),
        ','.join(('user3@example.com', 'i@v', 'User1:user1@example.com')),
        ','.join(('user4@example.com', 'g@r@b', 'Da:user5@example.com'))), {
            'instance': NotifyMailgun,
    }),
    ('mailgun://user@localhost.localdomain/{}-{}-{}'.format(
        'a' * 32, 'b' * 8, 'c' * 8), {
        'instance': NotifyMailgun,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('mailgun://user@localhost.localdomain/{}-{}-{}'.format(
        'a' * 32, 'b' * 8, 'c' * 8), {
        'instance': NotifyMailgun,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('mailgun://user@localhost.localdomain/{}-{}-{}'.format(
        'a' * 32, 'b' * 8, 'c' * 8), {
        'instance': NotifyMailgun,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_mailgun_urls():
    """
    NotifyMailgun() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
def test_plugin_mailgun_attachments(mock_post):
    """
    NotifyMailgun() Attachments

    """

    okay_response = requests.Request()
    okay_response.status_code = requests.codes.ok
    okay_response.content = ""

    # Assign our mock object our return value
    mock_post.return_value = okay_response

    # API Key
    apikey = 'abc123'

    obj = Apprise.instantiate(
        'mailgun://user@localhost.localdomain/{}'.format(apikey))
    assert isinstance(obj, NotifyMailgun)

    # Test Valid Attachment
    path = os.path.join(TEST_VAR_DIR, 'apprise-test.gif')
    attach = AppriseAttachment(path)
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is True

    # Test invalid attachment
    path = os.path.join(TEST_VAR_DIR, '/invalid/path/to/an/invalid/file.jpg')
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=path) is False

    mock_post.return_value = None
    mock_post.side_effect = OSError()
    # We can't send the message if we can't read the attachment
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is False

    # Test Valid Attachment (load 3)
    path = (
        os.path.join(TEST_VAR_DIR, 'apprise-test.gif'),
        os.path.join(TEST_VAR_DIR, 'apprise-test.gif'),
        os.path.join(TEST_VAR_DIR, 'apprise-test.gif'),
    )
    attach = AppriseAttachment(path)

    # Return our good configuration
    mock_post.side_effect = None
    mock_post.return_value = okay_response
    with mock.patch('builtins.open', side_effect=OSError()):
        # We can't send the message we can't open the attachment for reading
        assert obj.notify(
            body='body', title='title', notify_type=NotifyType.INFO,
            attach=attach) is False

    # Do it again, but fail on the third file
    with mock.patch(
            'builtins.open',
            side_effect=(mock.Mock(), mock.Mock(), OSError())):

        assert obj.notify(
            body='body', title='title', notify_type=NotifyType.INFO,
            attach=attach) is False

    with mock.patch('builtins.open') as mock_open:
        mock_fp = mock.Mock()
        mock_fp.seek.side_effect = OSError()
        mock_open.return_value = mock_fp

        # We can't send the message we can't seek through it
        assert obj.notify(
            body='body', title='title', notify_type=NotifyType.INFO,
            attach=attach) is False

        mock_post.reset_mock()
        # Fail on the third file; this tests the for-loop inside the seek()
        # section of the code that calls close() on previously opened files
        mock_fp.seek.side_effect = (None, None, OSError())
        mock_open.return_value = mock_fp
        # We can't send the message we can't seek through it
        assert obj.notify(
            body='body', title='title', notify_type=NotifyType.INFO,
            attach=attach) is False

    # test the handling of our batch modes
    obj = Apprise.instantiate(
        'mailgun://no-reply@example.com/{}/'
        'user1@example.com/user2@example.com?batch=yes'.format(apikey))
    assert isinstance(obj, NotifyMailgun)

    # Force our batch to break into separate messages
    obj.default_batch_size = 1
    # We'll send 2 messages
    mock_post.reset_mock()

    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is True
    assert mock_post.call_count == 2

    # single batch
    mock_post.reset_mock()
    # We'll send 1 message
    obj.default_batch_size = 2

    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is True
    assert mock_post.call_count == 1


@mock.patch('requests.post')
def test_plugin_mailgun_header_check(mock_post):
    """
    NotifyMailgun() Test Header Prep

    """

    okay_response = requests.Request()
    okay_response.status_code = requests.codes.ok
    okay_response.content = ""

    # Assign our mock object our return value
    mock_post.return_value = okay_response

    # API Key
    apikey = 'abc123'

    obj = Apprise.instantiate(
        'mailgun://user@localhost.localdomain/{}'.format(apikey))
    assert isinstance(obj, NotifyMailgun)
    assert isinstance(obj.url(), str) is True

    # No calls made yet
    assert mock_post.call_count == 0

    # Send our notification
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is True

    # 2 calls were made, one to perform an email lookup, the second
    # was the notification itself
    assert mock_post.call_count == 1
    assert mock_post.call_args_list[0][0][0] == \
        'https://api.mailgun.net/v3/localhost.localdomain/messages'

    payload = mock_post.call_args_list[0][1]['data']
    assert 'from' in payload
    assert 'Apprise <user@localhost.localdomain>' == payload['from']
    assert 'user@localhost.localdomain' == payload['to']

    # Reset our mock object
    mock_post.reset_mock()

    obj = Apprise.instantiate(
        'mailgun://user@localhost.localdomain/'
        '{}?from=Luke%20Skywalker'.format(apikey))
    assert isinstance(obj, NotifyMailgun)
    assert isinstance(obj.url(), str) is True

    # No calls made yet
    assert mock_post.call_count == 0

    # Send our notification
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is True

    assert mock_post.call_count == 1
    payload = mock_post.call_args_list[0][1]['data']
    assert 'from' in payload
    assert 'to' in payload
    assert 'Luke Skywalker <user@localhost.localdomain>' == payload['from']
    assert 'user@localhost.localdomain' == payload['to']

    # Reset our mock object
    mock_post.reset_mock()

    obj = Apprise.instantiate(
        'mailgun://user@localhost.localdomain/{}'
        '?from=Luke%20Skywalker<luke@rebels.com>'.format(apikey))
    assert isinstance(obj, NotifyMailgun)
    assert isinstance(obj.url(), str) is True

    # No calls made yet
    assert mock_post.call_count == 0

    # Send our notification
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is True

    assert mock_post.call_count == 1
    payload = mock_post.call_args_list[0][1]['data']
    assert 'from' in payload
    assert 'to' in payload
    assert 'Luke Skywalker <luke@rebels.com>' == payload['from']
    assert 'luke@rebels.com' == payload['to']

    # Reset our mock object
    mock_post.reset_mock()

    obj = Apprise.instantiate(
        'mailgun://user@localhost.localdomain/{}'
        '?from=luke@rebels.com'.format(apikey))
    assert isinstance(obj, NotifyMailgun)
    assert isinstance(obj.url(), str) is True

    # No calls made yet
    assert mock_post.call_count == 0

    # Send our notification
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO) is True

    assert mock_post.call_count == 1
    payload = mock_post.call_args_list[0][1]['data']
    assert 'from' in payload
    assert 'to' in payload
    assert 'luke@rebels.com' == payload['from']
    assert 'luke@rebels.com' == payload['to']
