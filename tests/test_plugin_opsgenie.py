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

from json import dumps

# Disable logging for a cleaner testing output
import logging
from unittest import mock

from helpers import AppriseURLTester
import requests

import apprise
from apprise.plugins.opsgenie import (
    NotifyOpsgenie,
    NotifyType,
    OpsgeniePriority,
)

logging.disable(logging.CRITICAL)

# a test UUID we can use
UUID4 = "8b799edf-6f98-4d3a-9be7-2862fb4e5752"

OPSGENIE_GOOD_RESPONSE = dumps({
    "result": "Request will be processed",
    "took": 0.204,
    "requestId": "43a29c5c-3dbf-4fa4-9c26-f4f71023e120",
})

# Our Testing URLs
apprise_url_tests = (
    (
        "opsgenie://",
        {
            # We failed to identify any valid authentication
            "instance": TypeError,
        },
    ),
    (
        "opsgenie://:@/",
        {
            # We failed to identify any valid authentication
            "instance": TypeError,
        },
    ),
    (
        "opsgenie://%20%20/",
        {
            # invalid apikey specified
            "instance": TypeError,
        },
    ),
    (
        "opsgenie://apikey/user/?region=xx",
        {
            # invalid region id
            "instance": TypeError,
        },
    ),
    (
        "opsgenie://user@apikey/",
        {
            # No targets specified; this is allowed
            "instance": NotifyOpsgenie,
            "notify_type": NotifyType.WARNING,
            # Bad response returned
            "requests_response_text": "{",
            # We will not be successful sending the notice
            "notify_response": False,
        },
    ),
    (
        "opsgenie://apikey/",
        {
            # No targets specified; this is allowed
            "instance": NotifyOpsgenie,
            "notify_type": NotifyType.FAILURE,
            # Our response expected server response
            "requests_response_text": OPSGENIE_GOOD_RESPONSE,
        },
    ),
    (
        "opsgenie://apikey/user",
        {
            # Valid user
            "instance": NotifyOpsgenie,
            "notify_type": NotifyType.FAILURE,
            # Our response expected server response
            "requests_response_text": OPSGENIE_GOOD_RESPONSE,
            "privacy_url": "opsgenie://a...y/%40user",
        },
    ),
    (
        "opsgenie://apikey/@user?region=eu",
        {
            # European Region
            "instance": NotifyOpsgenie,
            "notify_type": NotifyType.FAILURE,
            # Our response expected server response
            "requests_response_text": OPSGENIE_GOOD_RESPONSE,
        },
    ),
    (
        "opsgenie://apikey/@user?entity=A%20Entity",
        {
            # Assign an entity
            "instance": NotifyOpsgenie,
            "notify_type": NotifyType.FAILURE,
            # Our response expected server response
            "requests_response_text": OPSGENIE_GOOD_RESPONSE,
        },
    ),
    (
        "opsgenie://apikey/@user?alias=An%20Alias",
        {
            # Assign an alias
            "instance": NotifyOpsgenie,
            "notify_type": NotifyType.FAILURE,
            # Our response expected server response
            "requests_response_text": OPSGENIE_GOOD_RESPONSE,
        },
    ),
    # Bad Action
    (
        "opsgenie://apikey/@user?action=invalid",
        {
            # Assign an entity
            "instance": TypeError,
        },
    ),
    (
        "opsgenie://from@apikey/@user?:invalid=note",
        {
            # Assign an entity
            "instance": TypeError,
        },
    ),
    (
        "opsgenie://apikey/@user?:warning=invalid",
        {
            # Assign an entity
            "instance": TypeError,
        },
    ),
    # Creates an index entry
    (
        "opsgenie://apikey/@user?entity=index&action=new",
        {
            # Assign an entity
            "instance": NotifyOpsgenie,
            "notify_type": NotifyType.FAILURE,
            # Our response expected server response
            "requests_response_text": OPSGENIE_GOOD_RESPONSE,
        },
    ),
    # Now action it
    (
        "opsgenie://apikey/@user?entity=index&action=acknowledge",
        {
            # Assign an entity
            "instance": NotifyOpsgenie,
            "notify_type": NotifyType.SUCCESS,
            # Our response expected server response
            "requests_response_text": OPSGENIE_GOOD_RESPONSE,
        },
    ),
    (
        "opsgenie://from@apikey/@user?entity=index&action=note",
        {
            # Assign an entity
            "instance": NotifyOpsgenie,
            "notify_type": NotifyType.SUCCESS,
            # Our response expected server response
            "requests_response_text": OPSGENIE_GOOD_RESPONSE,
        },
    ),
    (
        "opsgenie://from@apikey/@user?entity=index&action=note",
        {
            # Assign an entity
            "instance": NotifyOpsgenie,
            "notify_type": NotifyType.SUCCESS,
            # Our response expected server response
            "requests_response_text": OPSGENIE_GOOD_RESPONSE,
            "response": False,
            "requests_response_code": 500,
        },
    ),
    (
        "opsgenie://apikey/@user?entity=index&action=close",
        {
            # Assign an entity
            "instance": NotifyOpsgenie,
            "notify_type": NotifyType.SUCCESS,
            # Our response expected server response
            "requests_response_text": OPSGENIE_GOOD_RESPONSE,
        },
    ),
    (
        "opsgenie://apikey/@user?entity=index&action=delete",
        {
            # Assign an entity
            "instance": NotifyOpsgenie,
            "notify_type": NotifyType.SUCCESS,
            # Our response expected server response
            "requests_response_text": OPSGENIE_GOOD_RESPONSE,
        },
    ),
    # map info messages to generate a new message
    (
        "opsgenie://apikey/@user?entity=index2&:info=new",
        {
            # Assign an entity
            "instance": NotifyOpsgenie,
            "notify_type": NotifyType.INFO,
            # Our response expected server response
            "requests_response_text": OPSGENIE_GOOD_RESPONSE,
        },
    ),
    (
        "opsgenie://joe@apikey/@user?priority=p3",
        {
            # Assign our priority
            "instance": NotifyOpsgenie,
            "notify_type": NotifyType.FAILURE,
            # Our response expected server response
            "requests_response_text": OPSGENIE_GOOD_RESPONSE,
        },
    ),
    (
        "opsgenie://apikey/?tags=comma,separated",
        {
            # Test our our 'tags' (tag is reserved in Apprise) but not 'tags'
            # Also test the fact we do not need to define a target
            "instance": NotifyOpsgenie,
            "notify_type": NotifyType.FAILURE,
            # Our response expected server response
            "requests_response_text": OPSGENIE_GOOD_RESPONSE,
        },
    ),
    (
        "opsgenie://apikey/@user?priority=invalid",
        {
            # Invalid priority (loads using default)
            "instance": NotifyOpsgenie,
            "notify_type": NotifyType.FAILURE,
            # Our response expected server response
            "requests_response_text": OPSGENIE_GOOD_RESPONSE,
        },
    ),
    (
        "opsgenie://apikey/user@email.com/#team/*sche/^esc/%20/a",
        {
            # Valid user (email), valid schedule, Escalated ID,
            # an invalid entry (%20), and too short of an entry (a)
            "instance": NotifyOpsgenie,
            "notify_type": NotifyType.FAILURE,
            # Our response expected server response
            "requests_response_text": OPSGENIE_GOOD_RESPONSE,
        },
    ),
    (
        f"opsgenie://apikey/@{UUID4}/#{UUID4}/*{UUID4}/^{UUID4}/",
        {
            # similar to the above, except we use the UUID's
            "instance": NotifyOpsgenie,
            "notify_type": NotifyType.FAILURE,
            # Our response expected server response
            "requests_response_text": OPSGENIE_GOOD_RESPONSE,
        },
    ),
    # Same link as before but @ missing at the front causing an ambigious
    # lookup however the entry is treated a though a @ was in front (user)
    (
        f"opsgenie://apikey/{UUID4}/#{UUID4}/*{UUID4}/^{UUID4}/",
        {
            # similar to the above, except we use the UUID's
            "instance": NotifyOpsgenie,
            "notify_type": NotifyType.FAILURE,
            # Our response expected server response
            "requests_response_text": OPSGENIE_GOOD_RESPONSE,
        },
    ),
    (
        "opsgenie://apikey?to=#team,user&+key=value&+type=override",
        {
            # Test to= and details (key/value pair) also override 'type'
            "instance": NotifyOpsgenie,
            "notify_type": NotifyType.FAILURE,
            # Our response expected server response
            "requests_response_text": OPSGENIE_GOOD_RESPONSE,
        },
    ),
    (
        "opsgenie://apikey/#team/@user/?batch=yes",
        {
            # Test batch=
            "instance": NotifyOpsgenie,
            "notify_type": NotifyType.FAILURE,
            # Our response expected server response
            "requests_response_text": OPSGENIE_GOOD_RESPONSE,
        },
    ),
    (
        "opsgenie://apikey/#team/@user/?batch=no",
        {
            # Test batch=
            "instance": NotifyOpsgenie,
            "notify_type": NotifyType.FAILURE,
            # Our response expected server response
            "requests_response_text": OPSGENIE_GOOD_RESPONSE,
        },
    ),
    (
        "opsgenie://?apikey=abc&to=user",
        {
            # Test Kwargs
            "instance": NotifyOpsgenie,
            "notify_type": NotifyType.FAILURE,
            # Our response expected server response
            "requests_response_text": OPSGENIE_GOOD_RESPONSE,
        },
    ),
    (
        "opsgenie://apikey/#team/user/",
        {
            "instance": NotifyOpsgenie,
            # throw a bizzare code forcing us to fail to look it up
            "notify_type": NotifyType.FAILURE,
            # Our response expected server response
            "requests_response_text": OPSGENIE_GOOD_RESPONSE,
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "opsgenie://apikey/#topic1/device/",
        {
            "instance": NotifyOpsgenie,
            "notify_type": NotifyType.FAILURE,
            # Our response expected server response
            "requests_response_text": OPSGENIE_GOOD_RESPONSE,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_opsgenie_urls(tmpdir):
    """NotifyOpsgenie() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all(str(tmpdir))


@mock.patch("requests.post")
def test_plugin_opsgenie_config_files(mock_post):
    """NotifyOpsgenie() Config File Cases."""
    content = """
    urls:
      - opsgenie://apikey/user:
          - priority: 1
            tag: opsgenie_int low
          - priority: "1"
            tag: opsgenie_str_int low
          - priority: "p1"
            tag: opsgenie_pstr_int low
          - priority: low
            tag: opsgenie_str low

          # This will take on moderate (default) priority
          - priority: invalid
            tag: opsgenie_invalid

      - opsgenie://apikey2/user2:
          - priority: 5
            tag: opsgenie_int emerg
          - priority: "5"
            tag: opsgenie_str_int emerg
          - priority: "p5"
            tag: opsgenie_pstr_int emerg
          - priority: emergency
            tag: opsgenie_str emerg
    """

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = OPSGENIE_GOOD_RESPONSE

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
    assert len(list(aobj.find(tag="low"))) == 4
    for s in aobj.find(tag="low"):
        assert s.priority == OpsgeniePriority.LOW

    assert len(list(aobj.find(tag="emerg"))) == 4
    for s in aobj.find(tag="emerg"):
        assert s.priority == OpsgeniePriority.EMERGENCY

    assert len(list(aobj.find(tag="opsgenie_str"))) == 2
    assert len(list(aobj.find(tag="opsgenie_str_int"))) == 2
    assert len(list(aobj.find(tag="opsgenie_pstr_int"))) == 2
    assert len(list(aobj.find(tag="opsgenie_int"))) == 2

    assert len(list(aobj.find(tag="opsgenie_invalid"))) == 1
    assert (
        next(aobj.find(tag="opsgenie_invalid")).priority
        == OpsgeniePriority.NORMAL
    )


@mock.patch("requests.post")
def test_plugin_opsgenie_edge_case(mock_post):
    """NotifyOpsgenie() Edge Cases."""
    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = OPSGENIE_GOOD_RESPONSE

    instance = apprise.Apprise.instantiate("opsgenie://apikey")
    assert isinstance(instance, NotifyOpsgenie)

    assert len(instance.store.keys()) == 0
    assert instance.notify("test", "key", NotifyType.FAILURE) is True
    assert len(instance.store.keys()) == 1

    # Again just causes same index to get over-written
    assert instance.notify("test", "key", NotifyType.FAILURE) is True
    assert len(instance.store.keys()) == 1
    assert "a62f2225bf" in instance.store

    # Assign it garbage
    instance.store["a62f2225bf"] = "garbage"
    # This causes an internal check to fail where the keys are expected to be
    # as a list (this one is now a string)
    # content self corrects and things are fine
    assert instance.notify("test", "key", NotifyType.FAILURE) is True
    assert len(instance.store.keys()) == 1

    # new key is new index
    assert instance.notify("test", "key2", NotifyType.FAILURE) is True
    assert len(instance.store.keys()) == 2
