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

# Disable logging for a cleaner testing output
import logging
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

import apprise
from apprise import NotifyType
from apprise.plugins.join import JoinPriority, NotifyJoin

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "join://",
        {
            "instance": TypeError,
        },
    ),
    # API Key + bad url
    (
        "join://:@/",
        {
            "instance": TypeError,
        },
    ),
    # APIkey; no device
    (
        "join://%s" % ("a" * 32),
        {
            "instance": NotifyJoin,
        },
    ),
    # API Key + device (using to=)
    (
        "join://{}?to={}".format("a" * 32, "d" * 32),
        {
            "instance": NotifyJoin,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "join://a...a/",
        },
    ),
    # API Key + priority setting
    (
        "join://%s?priority=high" % ("a" * 32),
        {
            "instance": NotifyJoin,
        },
    ),
    # API Key + invalid priority setting
    (
        "join://%s?priority=invalid" % ("a" * 32),
        {
            "instance": NotifyJoin,
        },
    ),
    # API Key + priority setting (empty)
    (
        "join://%s?priority=" % ("a" * 32),
        {
            "instance": NotifyJoin,
        },
    ),
    # API Key + device
    (
        "join://{}@{}?image=True".format("a" * 32, "d" * 32),
        {
            "instance": NotifyJoin,
        },
    ),
    # No image
    (
        "join://{}@{}?image=False".format("a" * 32, "d" * 32),
        {
            "instance": NotifyJoin,
        },
    ),
    # API Key + Device Name
    (
        "join://{}/{}".format("a" * 32, "My Device"),
        {
            "instance": NotifyJoin,
        },
    ),
    # API Key + device
    (
        "join://{}/{}".format("a" * 32, "d" * 32),
        {
            "instance": NotifyJoin,
            # don't include an image by default
            "include_image": False,
        },
    ),
    # API Key + 2 devices
    (
        "join://{}/{}/{}".format("a" * 32, "d" * 32, "e" * 32),
        {
            "instance": NotifyJoin,
            # don't include an image by default
            "include_image": False,
        },
    ),
    # API Key + 1 device and 1 group
    (
        "join://{}/{}/{}".format("a" * 32, "d" * 32, "group.chrome"),
        {
            "instance": NotifyJoin,
        },
    ),
    (
        "join://%s" % ("a" * 32),
        {
            "instance": NotifyJoin,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "join://%s" % ("a" * 32),
        {
            "instance": NotifyJoin,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "join://%s" % ("a" * 32),
        {
            "instance": NotifyJoin,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_join_urls():
    """NotifyJoin() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_join_edge_cases(mock_post, mock_get):
    """NotifyJoin() Edge Cases."""

    # Generate some generic message types
    device = "A" * 32
    group = "group.chrome"
    apikey = "a" * 32

    # Initializes the plugin with devices set to a string
    NotifyJoin(apikey=apikey, targets=group)

    # Initializes the plugin with devices set to None
    NotifyJoin(apikey=apikey, targets=None)

    # Initializes the plugin with an invalid apikey
    with pytest.raises(TypeError):
        NotifyJoin(apikey=None)

    # Whitespace also acts as an invalid apikey
    with pytest.raises(TypeError):
        NotifyJoin(apikey="   ")

    # Initializes the plugin with devices set to a set
    p = NotifyJoin(apikey=apikey, targets=[group, device])

    # Prepare our mock responses
    req = requests.Request()
    req.status_code = requests.codes.created
    req.content = ""
    mock_get.return_value = req
    mock_post.return_value = req

    # Test notifications without a body or a title; nothing to send
    # so we return False
    assert (
        p.notify(body=None, title=None, notify_type=NotifyType.INFO) is False
    )


@mock.patch("requests.post")
def test_plugin_join_config_files(mock_post):
    """NotifyJoin() Config File Cases."""
    content = """
    urls:
      - join://{}@{}:
          - priority: -2
            tag: join_int low
          - priority: "-2"
            tag: join_str_int low
          - priority: low
            tag: join_str low

          # This will take on normal (default) priority
          - priority: invalid
            tag: join_invalid

      - join://{}@{}:
          - priority: 2
            tag: join_int emerg
          - priority: "2"
            tag: join_str_int emerg
          - priority: emergency
            tag: join_str emerg
    """.format("a" * 32, "b" * 32, "c" * 32, "d" * 32)

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    # Create ourselves a config object
    ac = apprise.AppriseConfig()
    assert ac.add_config(content=content) is True

    aobj = apprise.Apprise()

    # Add our configuration
    aobj.add(ac)

    # We should be able to read our 7 servers from that
    # 3x low
    # 3x emerg
    # 1x invalid (so takes on normal priority)
    assert len(ac.servers()) == 7
    assert len(aobj) == 7
    assert len(list(aobj.find(tag="low"))) == 3
    for s in aobj.find(tag="low"):
        assert s.priority == JoinPriority.LOW

    assert len(list(aobj.find(tag="emerg"))) == 3
    for s in aobj.find(tag="emerg"):
        assert s.priority == JoinPriority.EMERGENCY

    assert len(list(aobj.find(tag="join_str"))) == 2
    assert len(list(aobj.find(tag="join_str_int"))) == 2
    assert len(list(aobj.find(tag="join_int"))) == 2

    assert len(list(aobj.find(tag="join_invalid"))) == 1
    assert next(aobj.find(tag="join_invalid")).priority == JoinPriority.NORMAL

    # Notifications work
    assert aobj.notify(title="title", body="body") is True
