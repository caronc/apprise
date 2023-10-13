# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2023, Chris Caron <lead2gold@gmail.com>
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

import os
from json import loads, dumps
from unittest import mock

import requests
from apprise import Apprise
from apprise.plugins.NotifySMSEagle import NotifySMSEagle
from helpers import AppriseURLTester
from apprise import AppriseAttachment
from apprise import NotifyType

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

SMSEAGLE_GOOD_RESPONSE = dumps({
    "result": {
        "message_id": "748",
        "status": "ok"
    }})

SMSEAGLE_BAD_RESPONSE = dumps({
    "result": {
        "error_text": "Wrong parameters",
        "status": "error",
    }})


# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), 'var')

# Our Testing URLs
apprise_url_tests = (
    ('smseagle://', {
        # No host specified
        'instance': TypeError,
    }),
    ('smseagle://:@/', {
        # invalid host
        'instance': TypeError,
    }),
    ('smseagle://localhost', {
        # Just a host provided (no access token)
        'instance': TypeError,
    }),
    ('smseagle://%20@localhost', {
        # invalid token
        'instance': TypeError,
    }),
    ('smseagle://token@localhost/123/', {
        # invalid 'to' phone number
        'instance': NotifySMSEagle,
        # Notify will fail because it couldn't send to anyone
        'response': False,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'smseagle://****@localhost/@123',
        # Our response expected server response
        'requests_response_text': SMSEAGLE_GOOD_RESPONSE,
    }),
    ('smseagle://token@localhost/%20/%20/', {
        # invalid 'to' phone number
        'instance': NotifySMSEagle,
        # Notify will fail because it couldn't send to anyone
        'response': False,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'smseagle://****@localhost/',
        # Our response expected server response
        'requests_response_text': SMSEAGLE_GOOD_RESPONSE,
    }),
    ('smseagle://token@localhost:8080/{}/'.format('1' * 11), {
        # one phone number will notify ourselves
        'instance': NotifySMSEagle,
        # Our response expected server response
        'requests_response_text': SMSEAGLE_GOOD_RESPONSE,
    }),
    ('smseagle://localhost:8080/{}/?token=abc1234'.format('1' * 11), {
        # pass our token in as an argument
        'instance': NotifySMSEagle,
        # Our response expected server response
        'requests_response_text': SMSEAGLE_GOOD_RESPONSE,
    }),
    # Set priority
    ('smseagle://token@localhost/@user/?priority=high', {
        'instance': NotifySMSEagle,
        # Our response expected server response
        'requests_response_text': SMSEAGLE_GOOD_RESPONSE,
    }),
    # Support integer value too
    ('smseagle://token@localhost/@user/?priority=1', {
        'instance': NotifySMSEagle,
        'requests_response_text': SMSEAGLE_GOOD_RESPONSE,
    }),
    # Invalid priority
    ('smseagle://token@localhost/@user/?priority=invalid', {
        # Invalid Priority
        'instance': TypeError,
    }),
    # Invalid priority
    ('smseagle://token@localhost/@user/?priority=25', {
        # Invalid Priority
        'instance': TypeError,
    }),
    ('smseagle://token@localhost:8082/#abcd/', {
        # a valid group
        'instance': NotifySMSEagle,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'smseagle://****@localhost:8082/#abcd',
        # Our response expected server response
        'requests_response_text': SMSEAGLE_GOOD_RESPONSE,
    }),
    ('smseagle://token@localhost:8082/@abcd/', {
        # a valid contact
        'instance': NotifySMSEagle,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'smseagle://****@localhost:8082/@abcd',
        # Our response expected server response
        'requests_response_text': SMSEAGLE_GOOD_RESPONSE,
    }),
    ('smseagles://token@localhost:8081/contact/', {
        # another valid group (without @ symbol)
        'instance': NotifySMSEagle,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'smseagles://****@localhost:8081/@contact',
        # Our response expected server response
        'requests_response_text': SMSEAGLE_GOOD_RESPONSE,
    }),
    ('smseagle://token@localhost:8082/@/#/,/', {
        # Test case where we provide bad data
        'instance': NotifySMSEagle,
        # Our failed response
        'requests_response_text': SMSEAGLE_GOOD_RESPONSE,
        # as a result, we expect a failed notification
        'response': False,
    }),
    ('smseagle://token@localhost:8083/@user/', {
        # Test case where we get a bad response
        'instance': NotifySMSEagle,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'smseagle://****@localhost:8083/@user',
        # Our failed response
        'requests_response_text': SMSEAGLE_BAD_RESPONSE,
        # as a result, we expect a failed notification
        'response': False,
    }),
    ('smseagle://token@localhost:8084/@user/', {
        # Test case where we get a bad response
        'instance': NotifySMSEagle,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'smseagle://****@localhost:8084/@user',
        # Our failed response
        'requests_response_text': None,
        # as a result, we expect a failed notification
        'response': False,
    }),
    ('smseagle://token@localhost:8085/@user/', {
        # Test case where we get a bad response
        'instance': NotifySMSEagle,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'smseagle://****@localhost:8085/@user',
        # Our failed response (bad json)
        'requests_response_text': '{',
        # as a result, we expect a failed notification
        'response': False,
    }),
    ('smseagle://token@localhost:8086/?to={},{}'.format(
        '2' * 11, '3' * 11), {
        # use get args to acomplish the same thing
        'instance': NotifySMSEagle,
        # Our response expected server response
        'requests_response_text': SMSEAGLE_GOOD_RESPONSE,
    }),
    ('smseagle://token@localhost:8087/?to={},{},{}'.format(
        '2' * 11, '3' * 11, '5' * 3), {
        # 2 good targets and one invalid one
        'instance': NotifySMSEagle,
        # Our response expected server response
        'requests_response_text': SMSEAGLE_GOOD_RESPONSE,
    }),
    ('smseagle://token@localhost:8088/{}/{}/'.format(
        '2' * 11, '3' * 11), {
        # If we have from= specified, then all elements take on the to= value
        'instance': NotifySMSEagle,
        # Our response expected server response
        'requests_response_text': SMSEAGLE_GOOD_RESPONSE,
    }),
    ('smseagles://token@localhost/{}'.format('3' * 11), {
        # use get args to acomplish the same thing (use source instead of from)
        'instance': NotifySMSEagle,
        # Our response expected server response
        'requests_response_text': SMSEAGLE_GOOD_RESPONSE,
    }),
    ('smseagles://token@localhost/{}/{}?batch=True'.format(
        '3' * 11, '4' * 11), {
            # test batch mode
            'instance': NotifySMSEagle,
            # Our response expected server response
            'requests_response_text': SMSEAGLE_GOOD_RESPONSE,
    }),
    ('smseagles://token@localhost/{}/?flash=yes'.format(
        '3' * 11), {
            # test flash mode
            'instance': NotifySMSEagle,
            # Our response expected server response
            'requests_response_text': SMSEAGLE_GOOD_RESPONSE,
    }),
    ('smseagles://token@localhost/{}/?test=yes'.format(
        '3' * 11), {
            # test mode
            'instance': NotifySMSEagle,
            # Our response expected server response
            'requests_response_text': SMSEAGLE_GOOD_RESPONSE,
    }),
    ('smseagles://token@localhost/{}/{}?status=True'.format(
        '3' * 11, '4' * 11), {
            # test status switch
            'instance': NotifySMSEagle,
            # Our response expected server response
            'requests_response_text': SMSEAGLE_GOOD_RESPONSE,
    }),
    ('smseagle://token@localhost/{}'.format('4' * 11), {
        'instance': NotifySMSEagle,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
        # Our response expected server response
        'requests_response_text': SMSEAGLE_GOOD_RESPONSE,
    }),
    ('smseagle://token@localhost/{}'.format('4' * 11), {
        'instance': NotifySMSEagle,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_smseagle_urls():
    """
    NotifySMSEagle() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
def test_plugin_smseagle_edge_cases(mock_post):
    """
    NotifySMSEagle() Edge Cases

    """

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok
    response.content = SMSEAGLE_GOOD_RESPONSE

    # Prepare Mock
    mock_post.return_value = response

    # Initialize some generic (but valid) tokens
    target = '+1 (555) 987-5432'
    body = "test body"
    title = "My Title"

    aobj = Apprise()
    assert aobj.add(
        "smseagles://token@localhost:231/{}".format(target))
    assert len(aobj) == 1
    assert aobj.notify(title=title, body=body)
    assert mock_post.call_count == 1

    details = mock_post.call_args_list[0]
    assert details[0][0] == 'https://localhost:231/jsonrpc/sms'
    payload = loads(details[1]['data'])
    assert payload['params']['message'] == 'My Title\r\ntest body'

    # Reset our mock object
    mock_post.reset_mock()

    aobj = Apprise()
    assert aobj.add(
        "smseagles://token@localhost:231/{}?status=Yes".format(
            target))
    assert len(aobj) == 1
    assert aobj.notify(title=title, body=body)
    assert mock_post.call_count == 1

    details = mock_post.call_args_list[0]
    assert details[0][0] == 'https://localhost:231/jsonrpc/sms'
    payload = loads(details[1]['data'])
    # Status flag is set
    assert payload['params']['message'] == '[i] My Title\r\ntest body'


@mock.patch('requests.post')
def test_plugin_smseagle_result_set(mock_post):
    """
    NotifySMSEagle() Result Sets

    """

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok
    response.content = SMSEAGLE_GOOD_RESPONSE

    # Prepare Mock
    mock_post.return_value = response

    body = "test body"
    title = "My Title"

    aobj = Apprise()
    aobj.add(
        'smseagle://token@10.0.0.112:8080/+12512222222/+12513333333/'
        '12514444444?batch=yes')
    # In a batch mode we can shove them all into 1 call
    assert len(aobj[0]) == 1

    assert aobj.notify(title=title, body=body)

    # If a batch, there is only 1 post
    assert mock_post.call_count == 1

    details = mock_post.call_args_list[0]
    assert details[0][0] == 'http://10.0.0.112:8080/jsonrpc/sms'
    payload = loads(details[1]['data'])
    assert 'method' in payload
    assert payload['method'] == 'sms.send_sms'

    assert 'params' in payload
    assert isinstance(payload['params'], dict)
    params = payload['params']
    assert 'to' in params
    assert len(params['to'].split(',')) == 3

    assert "+12512222222" in params['to'].split(',')
    assert "+12513333333" in params['to'].split(',')
    # The + is not appended
    assert "12514444444" in params['to'].split(',')
    assert params.get('message_type') == 'sms'
    assert params.get('responsetype') == 'extended'
    assert params.get('access_token') == 'token'
    assert params.get('highpriority') == 0
    assert params.get('flash') == 0
    assert params.get('test') == 0
    assert params.get('unicode') == 1
    assert params.get('message') == 'My Title\r\ntest body'

    # Reset our test and turn batch mode off
    mock_post.reset_mock()

    aobj = Apprise()
    aobj.add(
        'smseagle://token@10.0.0.112:8080/#group/Contact/'
        '123456789?batch=no')
    assert len(aobj[0]) == 3

    assert aobj.notify(title=title, body=body)

    # If batch is off then there is a post per entry
    assert mock_post.call_count == 3

    details = mock_post.call_args_list[0]
    assert details[0][0] == 'http://10.0.0.112:8080/jsonrpc/sms'
    payload = loads(details[1]['data'])
    assert payload['method'] == 'sms.send_sms'

    assert 'params' in payload
    assert isinstance(payload['params'], dict)
    params = payload['params']
    assert 'to' in params
    assert len(params['to'].split(',')) == 1
    assert "123456789" in params['to'].split(',')

    assert params.get('message_type') == 'sms'
    assert params.get('responsetype') == 'extended'
    assert params.get('access_token') == 'token'
    assert params.get('highpriority') == 0
    assert params.get('flash') == 0
    assert params.get('test') == 0
    assert params.get('unicode') == 1
    assert params.get('message') == 'My Title\r\ntest body'

    details = mock_post.call_args_list[1]
    assert details[0][0] == 'http://10.0.0.112:8080/jsonrpc/sms'
    payload = loads(details[1]['data'])
    assert payload['method'] == 'sms.send_togroup'

    assert 'params' in payload
    assert isinstance(payload['params'], dict)
    params = payload['params']
    assert 'groupname' in params
    assert len(params['groupname'].split(',')) == 1
    assert "group" in params['groupname'].split(',')

    assert params.get('message_type') == 'sms'
    assert params.get('responsetype') == 'extended'
    assert params.get('access_token') == 'token'
    assert params.get('highpriority') == 0
    assert params.get('flash') == 0
    assert params.get('test') == 0
    assert params.get('unicode') == 1
    assert params.get('message') == 'My Title\r\ntest body'

    details = mock_post.call_args_list[2]
    assert details[0][0] == 'http://10.0.0.112:8080/jsonrpc/sms'
    payload = loads(details[1]['data'])
    assert payload['method'] == 'sms.send_tocontact'

    assert 'params' in payload
    assert isinstance(payload['params'], dict)
    params = payload['params']
    assert 'contactname' in params
    assert len(params['contactname'].split(',')) == 1
    assert "Contact" in params['contactname'].split(',')

    assert params.get('message_type') == 'sms'
    assert params.get('responsetype') == 'extended'
    assert params.get('access_token') == 'token'
    assert params.get('highpriority') == 0
    assert params.get('flash') == 0
    assert params.get('test') == 0
    assert params.get('unicode') == 1
    assert params.get('message') == 'My Title\r\ntest body'

    mock_post.reset_mock()

    # Test groups and contact names
    aobj = Apprise()
    aobj.add(
        'smseagle://token@10.0.0.112:8080/513333333/#group1/@contact1/'
        'contact2/12514444444?batch=yes')

    # contacts and numbers can be combined and is calculated in batch response
    assert len(aobj[0]) == 3
    assert aobj.notify(title=title, body=body)

    # There is a unique post to each (group, contact x2, and phone x2)
    # The key is the contacts were grouped here in 1 post each
    assert mock_post.call_count == 3

    details = mock_post.call_args_list[0]
    assert details[0][0] == 'http://10.0.0.112:8080/jsonrpc/sms'
    payload = loads(details[1]['data'])
    assert payload['method'] == 'sms.send_sms'

    assert 'params' in payload
    assert isinstance(payload['params'], dict)
    params = payload['params']
    assert 'to' in params
    assert len(params['to'].split(',')) == 2
    assert "513333333" in params['to'].split(',')
    assert "12514444444" in params['to'].split(',')

    assert params.get('message_type') == 'sms'
    assert params.get('responsetype') == 'extended'
    assert params.get('access_token') == 'token'
    assert params.get('highpriority') == 0
    assert params.get('flash') == 0
    assert params.get('test') == 0
    assert params.get('unicode') == 1
    assert params.get('message') == 'My Title\r\ntest body'

    details = mock_post.call_args_list[1]
    assert details[0][0] == 'http://10.0.0.112:8080/jsonrpc/sms'
    payload = loads(details[1]['data'])
    assert payload['method'] == 'sms.send_togroup'

    assert 'params' in payload
    assert isinstance(payload['params'], dict)
    params = payload['params']
    assert 'groupname' in params
    assert len(params['groupname'].split(',')) == 1
    assert "group1" in params['groupname'].split(',')

    assert params.get('message_type') == 'sms'
    assert params.get('responsetype') == 'extended'
    assert params.get('access_token') == 'token'
    assert params.get('highpriority') == 0
    assert params.get('flash') == 0
    assert params.get('test') == 0
    assert params.get('unicode') == 1
    assert params.get('message') == 'My Title\r\ntest body'

    details = mock_post.call_args_list[2]
    assert details[0][0] == 'http://10.0.0.112:8080/jsonrpc/sms'
    payload = loads(details[1]['data'])
    assert payload['method'] == 'sms.send_tocontact'

    assert 'params' in payload
    assert isinstance(payload['params'], dict)
    params = payload['params']
    assert 'contactname' in params
    assert len(params['contactname'].split(',')) == 2
    assert "contact1" in params['contactname'].split(',')
    assert "contact2" in params['contactname'].split(',')

    assert params.get('message_type') == 'sms'
    assert params.get('responsetype') == 'extended'
    assert params.get('access_token') == 'token'
    assert params.get('highpriority') == 0
    assert params.get('flash') == 0
    assert params.get('test') == 0
    assert params.get('unicode') == 1
    assert params.get('message') == 'My Title\r\ntest body'

    # Validate our information is also placed back into the assembled URL
    assert '/@contact1' in aobj[0].url()
    assert '/@contact2' in aobj[0].url()
    assert '/#group1' in aobj[0].url()
    assert '/513333333' in aobj[0].url()
    assert '/12514444444' in aobj[0].url()


@mock.patch('requests.post')
def test_notify_smseagle_plugin_result_list(mock_post):
    """
    NotifySMSEagle() Result List Response

    """

    okay_response = requests.Request()
    okay_response.status_code = requests.codes.ok
    # We want to test the case where the `result` set returned is a list
    okay_response.content = dumps({
        "result": [{
            "message_id": "748",
            "status": "ok"
        }]})

    # Assign our mock object our return value
    mock_post.return_value = okay_response

    obj = Apprise.instantiate('smseagle://token@127.0.0.1/12222222/')
    assert isinstance(obj, NotifySMSEagle)

    # We should successfully handle the list
    assert obj.notify("test") is True

    # However if one of the elements in the list is bad
    okay_response.content = dumps({
        "result": [{
            "message_id": "748",
            "status": "ok"
        }, {
            "message_id": "749",
            "status": "error"
        }]})

    # Assign our mock object our return value
    mock_post.return_value = okay_response

    # We should now fail
    assert obj.notify("test") is False


@mock.patch('requests.post')
def test_notify_smseagle_plugin_attachments(mock_post):
    """
    NotifySMSEagle() Attachments

    """

    okay_response = requests.Request()
    okay_response.status_code = requests.codes.ok
    okay_response.content = SMSEAGLE_GOOD_RESPONSE

    # Assign our mock object our return value
    mock_post.return_value = okay_response

    obj = Apprise.instantiate(
        'smseagle://token@10.0.0.112:8080/+12512222222/+12513333333/'
        '12514444444?batch=no')
    assert isinstance(obj, NotifySMSEagle)

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
        'smseagle://token@10.0.0.112:8080/+12512222222/+12513333333/'
        '12514444444?batch=yes')
    assert isinstance(obj, NotifySMSEagle)

    # Now send an attachment normally without issues
    mock_post.reset_mock()
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is True

    # Verify we posted upstream
    assert mock_post.call_count == 1

    details = mock_post.call_args_list[0]
    assert details[0][0] == 'http://10.0.0.112:8080/jsonrpc/sms'
    payload = loads(details[1]['data'])
    assert payload['method'] == 'sms.send_sms'

    assert 'params' in payload
    assert isinstance(payload['params'], dict)
    params = payload['params']
    assert 'to' in params
    assert len(params['to'].split(',')) == 3
    assert "+12512222222" in params['to'].split(',')
    assert "+12513333333" in params['to'].split(',')
    assert "12514444444" in params['to'].split(',')

    assert params.get('message_type') == 'mms'
    assert params.get('responsetype') == 'extended'
    assert params.get('access_token') == 'token'
    assert params.get('highpriority') == 0
    assert params.get('flash') == 0
    assert params.get('test') == 0
    assert params.get('unicode') == 1
    assert params.get('message') == 'title\r\nbody'

    # Verify our attachments are in place
    assert 'attachments' in params
    assert isinstance(params['attachments'], list)
    assert len(params['attachments']) == 3
    for entry in params['attachments']:
        assert 'content' in entry
        assert 'content_type' in entry
        assert entry.get('content_type').startswith('image/')

    # Reset our mock object
    mock_post.reset_mock()

    # test the handling of our batch modes
    obj = Apprise.instantiate(
        'smseagle://token@10.0.0.112:8080/513333333/')
    assert isinstance(obj, NotifySMSEagle)

    # Unsupported (non image types are not sent)
    attach = os.path.join(TEST_VAR_DIR, 'apprise-test.mp4')
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is True

    # Verify we still posted upstream
    assert mock_post.call_count == 1

    details = mock_post.call_args_list[0]
    assert details[0][0] == 'http://10.0.0.112:8080/jsonrpc/sms'
    payload = loads(details[1]['data'])
    assert payload['method'] == 'sms.send_sms'

    assert 'params' in payload
    assert isinstance(payload['params'], dict)
    params = payload['params']
    assert 'to' in params
    assert len(params['to'].split(',')) == 1
    assert "513333333" in params['to'].split(',')

    assert params.get('message_type') == 'sms'
    assert params.get('responsetype') == 'extended'
    assert params.get('access_token') == 'token'
    assert params.get('highpriority') == 0
    assert params.get('flash') == 0
    assert params.get('test') == 0
    assert params.get('unicode') == 1
    assert params.get('message') == 'title\r\nbody'

    # No attachments were added
    assert 'attachments' not in params
