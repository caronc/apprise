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
from apprise import Apprise
from apprise import AppriseAttachment
from apprise import NotifyType
from apprise.plugins.NotifySMTP2Go import NotifySMTP2Go
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), 'var')

# Our Testing URLs
apprise_url_tests = (
    ('smtp2go://', {
        'instance': TypeError,
    }),
    ('smtp2go://:@/', {
        'instance': TypeError,
    }),
    # No Token specified
    ('smtp2go://user@localhost.localdomain', {
        'instance': TypeError,
    }),
    # Token is valid, but no user name specified
    ('smtp2go://localhost.localdomain/{}-{}-{}'.format(
        'a' * 32, 'b' * 8, 'c' * 8), {
        'instance': TypeError,
    }),
    # Invalid from email address
    ('smtp2go://"@localhost.localdomain/{}-{}-{}'.format(
        'a' * 32, 'b' * 8, 'c' * 8), {
        'instance': TypeError,
    }),
    # No To email address, but everything else is valid
    ('smtp2go://user@localhost.localdomain/{}-{}-{}'.format(
        'a' * 32, 'b' * 8, 'c' * 8), {
        'instance': NotifySMTP2Go,
    }),
    ('smtp2go://user@localhost.localdomain/{}-{}-{}?format=markdown'.format(
        'a' * 32, 'b' * 8, 'c' * 8), {
        'instance': NotifySMTP2Go,
    }),
    ('smtp2go://user@localhost.localdomain/{}-{}-{}?format=html'.format(
        'a' * 32, 'b' * 8, 'c' * 8), {
        'instance': NotifySMTP2Go,
    }),
    ('smtp2go://user@localhost.localdomain/{}-{}-{}?format=text'.format(
        'a' * 32, 'b' * 8, 'c' * 8), {
        'instance': NotifySMTP2Go,
    }),
    # headers
    ('smtp2go://user@localhost.localdomain/{}-{}-{}'
        '?+X-Customer-Campaign-ID=Apprise'.format(
            'a' * 32, 'b' * 8, 'c' * 8), {
                'instance': NotifySMTP2Go,
        }),
    # bcc and cc
    ('smtp2go://user@localhost.localdomain/{}-{}-{}'
        '?bcc=user@example.com&cc=user2@example.com'.format(
            'a' * 32, 'b' * 8, 'c' * 8), {
                'instance': NotifySMTP2Go,
        }),
    # One To Email address
    ('smtp2go://user@localhost.localdomain/{}-{}-{}/test@example.com'.format(
        'a' * 32, 'b' * 8, 'c' * 8), {
            'instance': NotifySMTP2Go,
    }),
    ('smtp2go://user@localhost.localdomain/'
        '{}-{}-{}?to=test@example.com'.format(
            'a' * 32, 'b' * 8, 'c' * 8), {
                'instance': NotifySMTP2Go}),
    # One To Email address, a from name specified too
    ('smtp2go://user@localhost.localdomain/{}-{}-{}/'
        'test@example.com?name="Frodo"'.format(
            'a' * 32, 'b' * 8, 'c' * 8), {
                'instance': NotifySMTP2Go}),
    # Invalid 'To' Email address
    ('smtp2go://user@localhost.localdomain/{}-{}-{}/invalid'.format(
        'a' * 32, 'b' * 8, 'c' * 8), {
            'instance': NotifySMTP2Go,
            # Expected notify() response
            'notify_response': False,
    }),
    # Multiple 'To', 'Cc', and 'Bcc' addresses (with invalid ones)
    ('smtp2go://user@example.com/{}-{}-{}/{}?bcc={}&cc={}'.format(
        'a' * 32, 'b' * 8, 'c' * 8,
        '/'.join(('user1@example.com', 'invalid', 'User2:user2@example.com')),
        ','.join(('user3@example.com', 'i@v', 'User1:user1@example.com')),
        ','.join(('user4@example.com', 'g@r@b', 'Da:user5@example.com'))), {
            'instance': NotifySMTP2Go,
    }),
    ('smtp2go://user@localhost.localdomain/{}-{}-{}'.format(
        'a' * 32, 'b' * 8, 'c' * 8), {
        'instance': NotifySMTP2Go,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('smtp2go://user@localhost.localdomain/{}-{}-{}'.format(
        'a' * 32, 'b' * 8, 'c' * 8), {
        'instance': NotifySMTP2Go,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('smtp2go://user@localhost.localdomain/{}-{}-{}'.format(
        'a' * 32, 'b' * 8, 'c' * 8), {
        'instance': NotifySMTP2Go,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_smtp2go_urls():
    """
    NotifySMTP2Go() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
def test_plugin_smtp2go_attachments(mock_post):
    """
    NotifySMTP2Go() Attachments

    """

    okay_response = requests.Request()
    okay_response.status_code = requests.codes.ok
    okay_response.content = ""

    # Assign our mock object our return value
    mock_post.return_value = okay_response

    # API Key
    apikey = 'abc123'

    obj = Apprise.instantiate(
        'smtp2go://user@localhost.localdomain/{}'.format(apikey))
    assert isinstance(obj, NotifySMTP2Go)

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

    # test the handling of our batch modes
    obj = Apprise.instantiate(
        'smtp2go://no-reply@example.com/{}/'
        'user1@example.com/user2@example.com?batch=yes'.format(apikey))
    assert isinstance(obj, NotifySMTP2Go)

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
