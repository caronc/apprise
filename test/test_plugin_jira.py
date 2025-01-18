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
from json import dumps
import requests
import apprise
from apprise.plugins.jira import (
    NotifyType, NotifyJira, JiraPriority)
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# a test UUID we can use
UUID4 = '8b799edf-6f98-4d3a-9be7-2862fb4e5752'

JIRA_GOOD_RESPONSE = dumps({
    "result": "Request will be processed",
    "took": 0.204,
    "requestId": "43a29c5c-3dbf-4fa4-9c26-f4f71023e120"
})

# Our Testing URLs
apprise_url_tests = (
    ('jira://', {
        # We failed to identify any valid authentication
        'instance': TypeError,
    }),
    ('jira://:@/', {
        # We failed to identify any valid authentication
        'instance': TypeError,
    }),
    ('jira://%20%20/', {
        # invalid apikey specified
        'instance': TypeError,
    }),
    ('jira://apikey/user/?region=xx', {
        # invalid region id
        'instance': TypeError,
    }),
    ('jira://user@apikey/', {
        # No targets specified; this is allowed
        'instance': NotifyJira,
        'notify_type': NotifyType.WARNING,
        # Bad response returned
        'requests_response_text': '{',
        # We will not be successful sending the notice
        'notify_response': False,
    }),
    ('jira://apikey/', {
        # No targets specified; this is allowed
        'instance': NotifyJira,
        'notify_type': NotifyType.FAILURE,
        # Our response expected server response
        'requests_response_text': JIRA_GOOD_RESPONSE,
    }),
    ('jira://apikey/user', {
        # Valid user
        'instance': NotifyJira,
        'notify_type': NotifyType.FAILURE,
        # Our response expected server response
        'requests_response_text': JIRA_GOOD_RESPONSE,
        'privacy_url': 'jira://a...y/%40user',
    }),
    ('jira://apikey/@user?region=eu', {
        # European Region
        'instance': NotifyJira,
        'notify_type': NotifyType.FAILURE,
        # Our response expected server response
        'requests_response_text': JIRA_GOOD_RESPONSE,
    }),
    ('jira://apikey/@user?entity=A%20Entity', {
        # Assign an entity
        'instance': NotifyJira,
        'notify_type': NotifyType.FAILURE,
        # Our response expected server response
        'requests_response_text': JIRA_GOOD_RESPONSE,
    }),
    ('jira://apikey/@user?alias=An%20Alias', {
        # Assign an alias
        'instance': NotifyJira,
        'notify_type': NotifyType.FAILURE,
        # Our response expected server response
        'requests_response_text': JIRA_GOOD_RESPONSE,
    }),
    # Bad Action
    ('jira://apikey/@user?action=invalid', {
        # Assign an entity
        'instance': TypeError,
    }),
    ('jira://from@apikey/@user?:invalid=note', {
        # Assign an entity
        'instance': TypeError,
    }),
    ('jira://apikey/@user?:warning=invalid', {
        # Assign an entity
        'instance': TypeError,
    }),
    # Creates an index entry
    ('jira://apikey/@user?entity=index&action=new', {
        # Assign an entity
        'instance': NotifyJira,
        'notify_type': NotifyType.FAILURE,
        # Our response expected server response
        'requests_response_text': JIRA_GOOD_RESPONSE,
    }),
    # Now action it
    ('jira://apikey/@user?entity=index&action=acknowledge', {
        # Assign an entity
        'instance': NotifyJira,
        'notify_type': NotifyType.SUCCESS,
        # Our response expected server response
        'requests_response_text': JIRA_GOOD_RESPONSE,
    }),
    ('jira://from@apikey/@user?entity=index&action=note', {
        # Assign an entity
        'instance': NotifyJira,
        'notify_type': NotifyType.SUCCESS,
        # Our response expected server response
        'requests_response_text': JIRA_GOOD_RESPONSE,
    }),
    ('jira://from@apikey/@user?entity=index&action=note', {
        # Assign an entity
        'instance': NotifyJira,
        'notify_type': NotifyType.SUCCESS,
        # Our response expected server response
        'requests_response_text': JIRA_GOOD_RESPONSE,
        'response': False,
        'requests_response_code': 500,
    }),
    ('jira://apikey/@user?entity=index&action=close', {
        # Assign an entity
        'instance': NotifyJira,
        'notify_type': NotifyType.SUCCESS,
        # Our response expected server response
        'requests_response_text': JIRA_GOOD_RESPONSE,
    }),
    ('jira://apikey/@user?entity=index&action=delete', {
        # Assign an entity
        'instance': NotifyJira,
        'notify_type': NotifyType.SUCCESS,
        # Our response expected server response
        'requests_response_text': JIRA_GOOD_RESPONSE,
    }),
    # map info messages to generate a new message
    ('jira://apikey/@user?entity=index2&:info=new', {
        # Assign an entity
        'instance': NotifyJira,
        'notify_type': NotifyType.INFO,
        # Our response expected server response
        'requests_response_text': JIRA_GOOD_RESPONSE,
    }),
    ('jira://joe@apikey/@user?priority=p3', {
        # Assign our priority
        'instance': NotifyJira,
        'notify_type': NotifyType.FAILURE,
        # Our response expected server response
        'requests_response_text': JIRA_GOOD_RESPONSE,
    }),
    ('jira://apikey/?tags=comma,separated', {
        # Test our our 'tags' (tag is reserved in Apprise) but not 'tags'
        # Also test the fact we do not need to define a target
        'instance': NotifyJira,
        'notify_type': NotifyType.FAILURE,
        # Our response expected server response
        'requests_response_text': JIRA_GOOD_RESPONSE,
    }),
    ('jira://apikey/@user?priority=invalid', {
        # Invalid priority (loads using default)
        'instance': NotifyJira,
        'notify_type': NotifyType.FAILURE,
        # Our response expected server response
        'requests_response_text': JIRA_GOOD_RESPONSE,
    }),
    ('jira://apikey/user@email.com/#team/*sche/^esc/%20/a', {
        # Valid user (email), valid schedule, Escalated ID,
        # an invalid entry (%20), and too short of an entry (a)
        'instance': NotifyJira,
        'notify_type': NotifyType.FAILURE,
        # Our response expected server response
        'requests_response_text': JIRA_GOOD_RESPONSE,
    }),
    ('jira://apikey/@{}/#{}/*{}/^{}/'.format(
        UUID4, UUID4, UUID4, UUID4), {
        # similar to the above, except we use the UUID's
        'instance': NotifyJira,
        'notify_type': NotifyType.FAILURE,
        # Our response expected server response
        'requests_response_text': JIRA_GOOD_RESPONSE,
    }),
    # Same link as before but @ missing at the front causing an ambigious
    # lookup however the entry is treated a though a @ was in front (user)
    ('jira://apikey/{}/#{}/*{}/^{}/'.format(
        UUID4, UUID4, UUID4, UUID4), {
        # similar to the above, except we use the UUID's
        'instance': NotifyJira,
        'notify_type': NotifyType.FAILURE,
        # Our response expected server response
        'requests_response_text': JIRA_GOOD_RESPONSE,
    }),
    ('jira://apikey?to=#team,user&+key=value&+type=override', {
        # Test to= and details (key/value pair) also override 'type'
        'instance': NotifyJira,
        'notify_type': NotifyType.FAILURE,
        # Our response expected server response
        'requests_response_text': JIRA_GOOD_RESPONSE,
    }),
    ('jira://apikey/#team/@user/?batch=yes', {
        # Test batch=
        'instance': NotifyJira,
        'notify_type': NotifyType.FAILURE,
        # Our response expected server response
        'requests_response_text': JIRA_GOOD_RESPONSE,
    }),
    ('jira://apikey/#team/@user/?batch=no', {
        # Test batch=
        'instance': NotifyJira,
        'notify_type': NotifyType.FAILURE,
        # Our response expected server response
        'requests_response_text': JIRA_GOOD_RESPONSE,
    }),
    ('jira://?apikey=abc&to=user', {
        # Test Kwargs
        'instance': NotifyJira,
        'notify_type': NotifyType.FAILURE,
        # Our response expected server response
        'requests_response_text': JIRA_GOOD_RESPONSE,
    }),
    ('jira://apikey/#team/user/', {
        'instance': NotifyJira,
        # throw a bizzare code forcing us to fail to look it up
        'notify_type': NotifyType.FAILURE,
        # Our response expected server response
        'requests_response_text': JIRA_GOOD_RESPONSE,
        'response': False,
        'requests_response_code': 999,
    }),
    ('jira://apikey/#topic1/device/', {
        'instance': NotifyJira,
        'notify_type': NotifyType.FAILURE,
        # Our response expected server response
        'requests_response_text': JIRA_GOOD_RESPONSE,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_jira_urls(tmpdir):
    """
    NotifyJira() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all(str(tmpdir))


@mock.patch('requests.post')
def test_plugin_jira_config_files(mock_post):
    """
    NotifyJira() Config File Cases
    """
    content = """
    urls:
      - jira://apikey/user:
          - priority: 1
            tag: jira_int low
          - priority: "1"
            tag: jira_str_int low
          - priority: "p1"
            tag: jira_pstr_int low
          - priority: low
            tag: jira_str low

          # This will take on moderate (default) priority
          - priority: invalid
            tag: jira_invalid

      - jira://apikey2/user2:
          - priority: 5
            tag: jira_int emerg
          - priority: "5"
            tag: jira_str_int emerg
          - priority: "p5"
            tag: jira_pstr_int emerg
          - priority: emergency
            tag: jira_str emerg
    """

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = JIRA_GOOD_RESPONSE

    # Create ourselves a config object
    ac = apprise.AppriseConfig()
    assert ac.add_config(content=content) is True

    aobj = apprise.Apprise()

    # Add our configuration
    aobj.add(ac)

    # We should be able to read our 9 servers from that
    # 4x low
    # 4x emerg
    # 1x invalid (so takes on normal priority)
    assert len(ac.servers()) == 9
    assert len(aobj) == 9
    assert len([x for x in aobj.find(tag='low')]) == 4
    for s in aobj.find(tag='low'):
        assert s.priority == JiraPriority.LOW

    assert len([x for x in aobj.find(tag='emerg')]) == 4
    for s in aobj.find(tag='emerg'):
        assert s.priority == JiraPriority.EMERGENCY

    assert len([x for x in aobj.find(tag='jira_str')]) == 2
    assert len([x for x in aobj.find(tag='jira_str_int')]) == 2
    assert len([x for x in aobj.find(tag='jira_pstr_int')]) == 2
    assert len([x for x in aobj.find(tag='jira_int')]) == 2

    assert len([x for x in aobj.find(tag='jira_invalid')]) == 1
    assert next(aobj.find(tag='jira_invalid')).priority == \
        JiraPriority.NORMAL


@mock.patch('requests.post')
def test_plugin_jira_edge_case(mock_post):
    """
    NotifyJira() Edge Cases
    """
    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = JIRA_GOOD_RESPONSE

    instance = apprise.Apprise.instantiate('jira://apikey')
    assert isinstance(instance, NotifyJira)

    assert len(instance.store.keys()) == 0
    assert instance.notify('test', 'key', NotifyType.FAILURE) is True
    assert len(instance.store.keys()) == 1

    # Again just causes same index to get over-written
    assert instance.notify('test', 'key', NotifyType.FAILURE) is True
    assert len(instance.store.keys()) == 1
    assert 'a62f2225bf' in instance.store

    # Assign it garbage
    instance.store['a62f2225bf'] = 'garbage'
    # This causes an internal check to fail where the keys are expected to be
    # as a list (this one is now a string)
    # content self corrects and things are fine
    assert instance.notify('test', 'key', NotifyType.FAILURE) is True
    assert len(instance.store.keys()) == 1

    # new key is new index
    assert instance.notify('test', 'key2', NotifyType.FAILURE) is True
    assert len(instance.store.keys()) == 2
