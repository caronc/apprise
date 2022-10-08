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
import os
import sys
from json import loads
from unittest import mock

import pytest
import requests
from apprise import plugins
from apprise import Apprise
from helpers import AppriseURLTester
from apprise import AppriseAttachment
from apprise import NotifyType

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), 'var')

# Our Testing URLs
apprise_url_tests = (
    ('signal://', {
        # No host specified
        'instance': TypeError,
    }),
    ('signal://:@/', {
        # invalid host
        'instance': TypeError,
    }),
    ('signal://localhost', {
        # Just a host provided
        'instance': TypeError,
    }),
    ('signal://localhost', {
        # key and secret provided and from but invalid from no
        'instance': TypeError,
    }),
    ('signal://localhost/123', {
        # invalid from phone
        'instance': TypeError,

    }),
    ('signal://localhost/{}/123/'.format('1' * 11), {
        # invalid 'to' phone number
        'instance': plugins.NotifySignalAPI,
        # Notify will fail because it couldn't send to anyone
        'response': False,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'signal://localhost/+{}/123'.format('1' * 11),
    }),
    ('signal://localhost:8080/{}/'.format('1' * 11), {
        # one phone number will notify ourselves
        'instance': plugins.NotifySignalAPI,
    }),

    ('signal://localhost:8082/+{}/@group.abcd/'.format('2' * 11), {
        # a valid group
        'instance': plugins.NotifySignalAPI,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'signal://localhost:8082/+{}/@abcd'.format('2' * 11),
    }),
    ('signal://localhost:8080/+{}/group.abcd/'.format('1' * 11), {
        # another valid group (without @ symbol)
        'instance': plugins.NotifySignalAPI,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'signal://localhost:8080/+{}/@abcd'.format('1' * 11),
    }),
    ('signal://localhost:8080/?from={}&to={},{}'.format(
        '1' * 11, '2' * 11, '3' * 11), {
        # use get args to acomplish the same thing
        'instance': plugins.NotifySignalAPI,
    }),
    ('signal://localhost:8080/?from={}&to={},{},{}'.format(
        '1' * 11, '2' * 11, '3' * 11, '5' * 3), {
        # 2 good targets and one invalid one
        'instance': plugins.NotifySignalAPI,
    }),
    ('signal://localhost:8080/{}/{}/?from={}'.format(
        '1' * 11, '2' * 11, '3' * 11), {
        # If we have from= specified, then all elements take on the to= value
        'instance': plugins.NotifySignalAPI,
    }),
    ('signals://user@localhost/{}/{}'.format('1' * 11, '3' * 11), {
        # use get args to acomplish the same thing (use source instead of from)
        'instance': plugins.NotifySignalAPI,
    }),
    ('signals://user:password@localhost/{}/{}'.format('1' * 11, '3' * 11), {
        # use get args to acomplish the same thing (use source instead of from)
        'instance': plugins.NotifySignalAPI,
    }),
    ('signals://user:password@localhost/{}/{}'.format('1' * 11, '3' * 11), {
        'instance': plugins.NotifySignalAPI,
        # Test that a 201 response code is still accepted
        'requests_response_code': 201,
    }),
    ('signals://localhost/{}/{}/{}?batch=True'.format(
        '1' * 11, '3' * 11, '4' * 11), {
            # test batch mode
            'instance': plugins.NotifySignalAPI,
    }),
    ('signals://localhost/{}/{}/{}?status=True'.format(
        '1' * 11, '3' * 11, '4' * 11), {
            # test status switch
            'instance': plugins.NotifySignalAPI,
    }),
    ('signal://localhost/{}/{}'.format('1' * 11, '4' * 11), {
        'instance': plugins.NotifySignalAPI,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('signal://localhost/{}/{}'.format('1' * 11, '4' * 11), {
        'instance': plugins.NotifySignalAPI,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_signal_urls():
    """
    NotifySignalAPI() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
def test_plugin_signal_edge_cases(mock_post):
    """
    NotifySignalAPI() Edge Cases

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    # Initialize some generic (but valid) tokens
    source = '+1 (555) 123-3456'
    target = '+1 (555) 987-5432'
    body = "test body"
    title = "My Title"

    # No apikey specified
    with pytest.raises(TypeError):
        plugins.NotifySignalAPI(source=None)

    aobj = Apprise()
    assert aobj.add("signals://localhost:231/{}/{}".format(source, target))
    assert aobj.notify(title=title, body=body)

    assert mock_post.call_count == 1

    details = mock_post.call_args_list[0]
    assert details[0][0] == 'https://localhost:231/v2/send'
    payload = loads(details[1]['data'])
    assert payload['message'] == 'My Title\r\ntest body'

    # Reset our mock object
    mock_post.reset_mock()

    aobj = Apprise()
    assert aobj.add(
        "signals://user@localhost:231/{}/{}?status=True".format(
            source, target))
    assert aobj.notify(title=title, body=body)

    assert mock_post.call_count == 1

    details = mock_post.call_args_list[0]
    assert details[0][0] == 'https://localhost:231/v2/send'
    payload = loads(details[1]['data'])
    # Status flag is set
    assert payload['message'] == '[i] My Title\r\ntest body'


@mock.patch('requests.post')
def test_plugin_signal_test_based_on_feedback(mock_post):
    """
    NotifySignalAPI() User Feedback Test

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    body = "test body"
    title = "My Title"

    aobj = Apprise()
    aobj.add(
        'signal://10.0.0.112:8080/+12512222222/+12513333333/'
        '12514444444?batch=yes')

    assert aobj.notify(title=title, body=body)

    # If a batch, there is only 1 post
    assert mock_post.call_count == 1

    details = mock_post.call_args_list[0]
    assert details[0][0] == 'http://10.0.0.112:8080/v2/send'
    payload = loads(details[1]['data'])
    assert payload['message'] == 'My Title\r\ntest body'
    assert payload['number'] == "+12512222222"
    assert len(payload['recipients']) == 2
    assert "+12513333333" in payload['recipients']
    # The + is appended
    assert "+12514444444" in payload['recipients']

    # Reset our test and turn batch mode off
    mock_post.reset_mock()

    aobj = Apprise()
    aobj.add(
        'signal://10.0.0.112:8080/+12512222222/+12513333333/'
        '12514444444?batch=no')

    assert aobj.notify(title=title, body=body)

    # If a batch, there is only 1 post
    assert mock_post.call_count == 2

    details = mock_post.call_args_list[0]
    assert details[0][0] == 'http://10.0.0.112:8080/v2/send'
    payload = loads(details[1]['data'])
    assert payload['message'] == 'My Title\r\ntest body'
    assert payload['number'] == "+12512222222"
    assert len(payload['recipients']) == 1
    assert "+12513333333" in payload['recipients']

    details = mock_post.call_args_list[1]
    assert details[0][0] == 'http://10.0.0.112:8080/v2/send'
    payload = loads(details[1]['data'])
    assert payload['message'] == 'My Title\r\ntest body'
    assert payload['number'] == "+12512222222"
    assert len(payload['recipients']) == 1

    # The + is appended
    assert "+12514444444" in payload['recipients']

    mock_post.reset_mock()

    # Test group names
    aobj = Apprise()
    aobj.add(
        'signal://10.0.0.112:8080/+12513333333/@group1/@group2/'
        '12514444444?batch=yes')

    assert aobj.notify(title=title, body=body)

    # If a batch, there is only 1 post
    assert mock_post.call_count == 1

    details = mock_post.call_args_list[0]
    assert details[0][0] == 'http://10.0.0.112:8080/v2/send'
    payload = loads(details[1]['data'])
    assert payload['message'] == 'My Title\r\ntest body'
    assert payload['number'] == "+12513333333"
    assert len(payload['recipients']) == 3
    assert "+12514444444" in payload['recipients']
    # our groups
    assert "group.group1" in payload['recipients']
    assert "group.group2" in payload['recipients']
    # Groups are stored properly
    assert '/@group1' in aobj[0].url()
    assert '/@group2' in aobj[0].url()
    # Our target phone number is also in the path
    assert '/+12514444444' in aobj[0].url()


@mock.patch('requests.post')
def test_notify_signal_plugin_attachments(mock_post):
    """
    NotifySignalAPI() Attachments

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    okay_response = requests.Request()
    okay_response.status_code = requests.codes.ok
    okay_response.content = ""

    # Assign our mock object our return value
    mock_post.return_value = okay_response

    obj = Apprise.instantiate(
        'signal://10.0.0.112:8080/+12512222222/+12513333333/'
        '12514444444?batch=no')
    assert isinstance(obj, plugins.NotifySignalAPI)

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

    # Get a appropriate "builtin" module name for pythons 2/3.
    if sys.version_info.major >= 3:
        builtin_open_function = 'builtins.open'

    else:
        builtin_open_function = '__builtin__.open'

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
    with mock.patch(builtin_open_function, side_effect=OSError()):
        # We can't send the message we can't open the attachment for reading
        assert obj.notify(
            body='body', title='title', notify_type=NotifyType.INFO,
            attach=attach) is False

    # test the handling of our batch modes
    obj = Apprise.instantiate(
        'signal://10.0.0.112:8080/+12512222222/+12513333333/'
        '12514444444?batch=yes')
    assert isinstance(obj, plugins.NotifySignalAPI)

    # Now send an attachment normally without issues
    mock_post.reset_mock()
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is True
    assert mock_post.call_count == 1
