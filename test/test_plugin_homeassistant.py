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

from unittest import mock

import requests
from apprise import Apprise
from apprise.plugins.home_assistant import NotifyHomeAssistant
from helpers import AppriseURLTester
import json

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('hassio://:@/', {
        'instance': TypeError,
    }),
    ('hassio://', {
        'instance': TypeError,
    }),
    ('hassios://', {
        'instance': TypeError,
    }),
    # No Long Lived Access Token specified
    ('hassio://user@localhost', {
        'instance': TypeError,
    }),
    ('hassio://localhost/long.lived.token', {
        'instance': NotifyHomeAssistant,
    }),
    ('hassio://localhost/prefix/path/long.lived.token', {
        'instance': NotifyHomeAssistant,
    }),
    ('hassio://localhost/long.lived.token?prefix=/ha', {
        'instance': NotifyHomeAssistant,
    }),
    ('hassio://localhost/service/?token=long.lived.token&prefix=/ha', {
        'instance': NotifyHomeAssistant,
    }),
    ('hassio://localhost/?token=long.lived.token&prefix=/ha&to=service', {
        'instance': NotifyHomeAssistant,
    }),
    ('hassio://localhost/service/$%/?token=long.lived.token&prefix=/ha', {
        # Tests an invalid service entry
        'instance': NotifyHomeAssistant,
    }),
    ('hassio://localhost/%only%/%invalid%/?token=lng.lived.token&prefix=/ha', {
        # Tests an invalid service entry
        'instance': NotifyHomeAssistant,
        # we'll have a notify response failure in this case
        'notify_response': False,
    }),
    ('hassio://user:pass@localhost/long.lived.token/', {
        'instance': NotifyHomeAssistant,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'hassio://user:****@localhost/l...n',
    }),
    ('hassio://localhost:80/long.lived.token', {
        'instance': NotifyHomeAssistant,
    }),
    ('hassio://user@localhost:8123/long.lived.token', {
        'instance': NotifyHomeAssistant,
        'privacy_url': 'hassio://user@localhost/l...n',
    }),
    ('hassios://localhost/long.lived.token?nid=!%', {
        # Invalid notification_id
        'instance': TypeError,
    }),
    ('hassios://localhost/long.lived.token?nid=abcd', {
        # Valid notification_id
        'instance': NotifyHomeAssistant,
    }),
    ('hassios://user:pass@localhost/long.lived.token', {
        'instance': NotifyHomeAssistant,
        'privacy_url': 'hassios://user:****@localhost/l...n',
    }),
    ('hassios://localhost:8443/path/long.lived.token/', {
        'instance': NotifyHomeAssistant,
        'privacy_url': 'hassios://localhost:8443/l...n',
    }),
    ('hassio://localhost:8123/a/path?token=long.lived.token', {
        'instance': NotifyHomeAssistant,
        # Default port; so it's stripped off
        # token was specified as kwarg
        'privacy_url': 'hassio://localhost/l...n',
    }),
    ('hassios://user:password@localhost:80/long.lived.token/', {
        'instance': NotifyHomeAssistant,

        'privacy_url': 'hassios://user:****@localhost:80',
    }),
    ('hassio://user:pass@localhost:8123/long.lived.token', {
        'instance': NotifyHomeAssistant,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('hassio://user:pass@localhost/long.lived.token', {
        'instance': NotifyHomeAssistant,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('hassio://user:pass@localhost/long.lived.token', {
        'instance': NotifyHomeAssistant,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_homeassistant_urls():
    """
    NotifyHomeAssistant() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
def test_plugin_homeassistant_general(mock_post):
    """
    NotifyHomeAssistant() General Checks

    """

    response = mock.Mock()
    response.content = ''
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    # Initializations
    obj = Apprise.instantiate('hassio://localhost/long.lived.token')
    assert isinstance(obj, NotifyHomeAssistant) is True
    assert isinstance(obj.url(), str) is True

    # Send Notification
    assert obj.send(body="test") is True

    assert mock_post.call_count == 1
    assert mock_post.call_args_list[0][0][0] == \
        'http://localhost:8123/api/services/persistent_notification/create'

    # Reset our mock object
    mock_post.reset_mock()

    # Now let's notify an object
    obj = Apprise.instantiate(
        'hassio://localhost/long.lived.token/service')
    assert isinstance(obj, NotifyHomeAssistant) is True
    assert isinstance(obj.url(), str) is True

    # Send Notification
    assert obj.send(body="test") is True

    assert mock_post.call_args_list[0][0][0] == \
        'http://localhost:8123/api/services/notify/service'
    posted_json = json.loads(mock_post.call_args_list[0][1]['data'])
    assert 'notification_id' in posted_json
    assert 'targets' not in posted_json
    assert 'message' in posted_json
    assert posted_json['message'] == 'test'
    assert 'title' in posted_json
    assert posted_json['title'] == ''

    # Reset our mock object
    mock_post.reset_mock()

    #
    # No Batch Processing
    #

    # Now let's notify an object
    obj = Apprise.instantiate(
        'hassio://localhost/long.lived.token/serviceA:target1,target2/'
        'service2/domain1.service3?batch=no')
    assert isinstance(obj, NotifyHomeAssistant) is True
    assert isinstance(obj.url(), str) is True

    # Send Notification
    assert obj.send(body="test-body", title="title") is True

    # Entries are split apart
    assert len(obj) == 4
    assert mock_post.call_count == 4

    assert mock_post.call_args_list[0][0][0] == \
        'http://localhost:8123/api/services/domain1/service3'
    posted_json = json.loads(mock_post.call_args_list[0][1]['data'])
    assert 'notification_id' in posted_json
    assert 'targets' not in posted_json
    assert 'message' in posted_json
    assert posted_json['message'] == 'test-body'
    assert 'title' in posted_json
    assert posted_json['title'] == 'title'

    assert mock_post.call_args_list[1][0][0] == \
        'http://localhost:8123/api/services/notify/service2'
    posted_json = json.loads(mock_post.call_args_list[1][1]['data'])
    assert 'notification_id' in posted_json
    assert 'targets' not in posted_json
    assert 'message' in posted_json
    assert posted_json['message'] == 'test-body'
    assert 'title' in posted_json
    assert posted_json['title'] == 'title'

    assert mock_post.call_args_list[2][0][0] == \
        'http://localhost:8123/api/services/notify/serviceA'
    posted_json = json.loads(mock_post.call_args_list[2][1]['data'])
    assert 'notification_id' in posted_json
    assert 'targets' in posted_json
    assert isinstance(posted_json['targets'], list)
    assert len(posted_json['targets']) == 1
    assert 'target1' in posted_json['targets']
    assert 'message' in posted_json
    assert posted_json['message'] == 'test-body'
    assert 'title' in posted_json
    assert posted_json['title'] == 'title'

    assert mock_post.call_args_list[3][0][0] == \
        'http://localhost:8123/api/services/notify/serviceA'
    posted_json = json.loads(mock_post.call_args_list[3][1]['data'])
    assert 'notification_id' in posted_json
    assert 'targets' in posted_json
    assert isinstance(posted_json['targets'], list)
    assert len(posted_json['targets']) == 1
    assert 'target2' in posted_json['targets']
    assert 'message' in posted_json
    assert posted_json['message'] == 'test-body'
    assert 'title' in posted_json
    assert posted_json['title'] == 'title'

    # Reset our mock object
    mock_post.reset_mock()

    #
    # Batch Processing
    #

    # Now let's notify an object
    obj = Apprise.instantiate(
        'hassio://localhost/long.lived.token/serviceA:target1,target2/'
        'service2/domain1.service3?batch=yes')
    assert isinstance(obj, NotifyHomeAssistant) is True
    assert isinstance(obj.url(), str) is True

    # Send Notification
    assert obj.send(body="test-body", title="title") is True

    # Entries targets can be grouped
    assert len(obj) == 3
    assert mock_post.call_count == 3

    assert mock_post.call_args_list[0][0][0] == \
        'http://localhost:8123/api/services/domain1/service3'
    posted_json = json.loads(mock_post.call_args_list[0][1]['data'])
    assert 'notification_id' in posted_json
    assert 'targets' not in posted_json
    assert 'message' in posted_json
    assert posted_json['message'] == 'test-body'
    assert 'title' in posted_json
    assert posted_json['title'] == 'title'

    assert mock_post.call_args_list[1][0][0] == \
        'http://localhost:8123/api/services/notify/service2'
    posted_json = json.loads(mock_post.call_args_list[1][1]['data'])
    assert 'notification_id' in posted_json
    assert 'targets' not in posted_json
    assert 'message' in posted_json
    assert posted_json['message'] == 'test-body'
    assert 'title' in posted_json
    assert posted_json['title'] == 'title'

    assert mock_post.call_args_list[2][0][0] == \
        'http://localhost:8123/api/services/notify/serviceA'
    posted_json = json.loads(mock_post.call_args_list[2][1]['data'])
    assert 'notification_id' in posted_json
    assert 'targets' in posted_json
    assert isinstance(posted_json['targets'], list)
    # Our batch groups our targets
    assert len(posted_json['targets']) == 2
    assert 'target1' in posted_json['targets']
    assert 'target2' in posted_json['targets']
    assert 'message' in posted_json
    assert posted_json['message'] == 'test-body'
    assert 'title' in posted_json
    assert posted_json['title'] == 'title'

    # Reset our mock object
    mock_post.reset_mock()

    #
    # Test error handling on multi-query request
    #

    # Now let's notify an object
    obj = Apprise.instantiate(
        'hassio://localhost/long.lived.token/serviceA:target1,target2/'
        'service2:target3,target4,target5,target6?batch=no')

    assert isinstance(obj, NotifyHomeAssistant) is True
    assert isinstance(obj.url(), str) is True

    bad_response = mock.Mock()
    bad_response.content = ''
    bad_response.status_code = requests.codes.not_found

    mock_post.side_effect = (response, bad_response)

    # We will fail on our second message sent
    assert obj.send(body="test-body", title="title") is False
