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
import requests

import apprise
from apprise import NotifyType
from apprise.plugins.dapnet import DapnetPriority, NotifyDapnet

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "dapnet://",
        {
            # We failed to identify any valid authentication
            "instance": TypeError,
        },
    ),
    (
        "dapnet://:@/",
        {
            # We failed to identify any valid authentication
            "instance": TypeError,
        },
    ),
    (
        "dapnet://user:pass",
        {
            # No call-sign specified
            "instance": TypeError,
        },
    ),
    (
        "dapnet://user@host",
        {
            # No password specified
            "instance": TypeError,
        },
    ),
    (
        "dapnet://user:pass@{}".format("DF1ABC"),
        {
            # valid call sign
            "instance": NotifyDapnet,
            "requests_response_code": requests.codes.created,
        },
    ),
    (
        "dapnet://user:pass@{}/{}".format("DF1ABC", "DF1DEF"),
        {
            # valid call signs
            "instance": NotifyDapnet,
            "requests_response_code": requests.codes.created,
        },
    ),
    (
        "dapnet://user:pass@DF1ABC-1/DF1ABC/DF1ABC-15",
        {
            # valid call signs; but a few are duplicates;
            # at the end there will only be 1 entry
            "instance": NotifyDapnet,
            "requests_response_code": requests.codes.created,
            # Our expected url(privacy=True) startswith() response:
            # Note that only 1 entry is saved (as other 2 are duplicates)
            "privacy_url": "dapnet://user:****@D...C?",
        },
    ),
    (
        "dapnet://user:pass@?to={},{}".format("DF1ABC", "DF1DEF"),
        {
            # support the to= argument
            "instance": NotifyDapnet,
            "requests_response_code": requests.codes.created,
        },
    ),
    (
        "dapnet://user:pass@{}?priority=normal".format("DF1ABC"),
        {
            # valid call sign with priority
            "instance": NotifyDapnet,
            "requests_response_code": requests.codes.created,
        },
    ),
    (
        "dapnet://user:pass@{}?priority=em&batch=false".format(
            "/".join(["DF1ABC", "0A1DEF"])
        ),
        {
            # valid call sign with priority (emergency) + no batch
            # transmissions
            "instance": NotifyDapnet,
            "requests_response_code": requests.codes.created,
        },
    ),
    (
        "dapnet://user:pass@{}?priority=invalid".format("DF1ABC"),
        {
            # invalid priority
            "instance": NotifyDapnet,
            "requests_response_code": requests.codes.created,
        },
    ),
    (
        "dapnet://user:pass@{}?txgroups=dl-all,all".format("DF1ABC"),
        {
            # valid call sign with two transmitter groups
            "instance": NotifyDapnet,
            "requests_response_code": requests.codes.created,
        },
    ),
    (
        "dapnet://user:pass@{}?txgroups=invalid".format("DF1ABC"),
        {
            # valid call sign with invalid transmitter group
            "instance": NotifyDapnet,
            "requests_response_code": requests.codes.created,
        },
    ),
    (
        "dapnet://user:pass@{}/{}".format("abcdefghi", "a"),
        {
            # invalid call signs
            "instance": NotifyDapnet,
            "notify_response": False,
        },
    ),
    # Edge cases
    (
        "dapnet://user:pass@{}".format("DF1ABC"),
        {
            "instance": NotifyDapnet,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "dapnet://user:pass@{}".format("DF1ABC"),
        {
            "instance": NotifyDapnet,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_dapnet_urls():
    """NotifyDapnet() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_dapnet_edge_cases(mock_post):
    """NotifyDapnet() Edge Cases."""
    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.created

    # test the handling of our batch modes
    obj = apprise.Apprise.instantiate(
        "dapnet://user:pass@{}?batch=yes".format(
            "/".join(["DF1ABC", "DF1DEF"])
        )
    )
    assert isinstance(obj, NotifyDapnet)

    # objects will be combined into a single post in batch mode
    assert len(obj) == 1

    # Force our batch to break into separate messages
    obj.default_batch_size = 1

    # We'll send 2 messages now
    assert len(obj) == 2

    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )
    assert mock_post.call_count == 2


@mock.patch("requests.post")
def test_plugin_dapnet_config_files(mock_post):
    """NotifyDapnet() Config File Cases."""
    content = """
    urls:
      - dapnet://user:pass@DF1ABC:
          - priority: 0
            tag: dapnet_int normal
          - priority: "0"
            tag: dapnet_str_int normal
          - priority: normal
            tag: dapnet_str normal

          # This will take on normal (default) priority
          - priority: invalid
            tag: dapnet_invalid

      - dapnet://user1:pass2@DF1ABC:
          - priority: 1
            tag: dapnet_int emerg
          - priority: "1"
            tag: dapnet_str_int emerg
          - priority: emergency
            tag: dapnet_str emerg
    """

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.created

    # Create ourselves a config object
    ac = apprise.AppriseConfig()
    assert ac.add_config(content=content) is True

    aobj = apprise.Apprise()

    # Add our configuration
    aobj.add(ac)

    # We should be able to read our 7 servers from that
    # 4x normal (invalid + 3 exclusivly specified to be so)
    # 3x emerg
    assert len(ac.servers()) == 7
    assert len(aobj) == 7
    assert len(list(aobj.find(tag="normal"))) == 3
    for s in aobj.find(tag="normal"):
        assert s.priority == DapnetPriority.NORMAL

    assert len(list(aobj.find(tag="emerg"))) == 3
    for s in aobj.find(tag="emerg"):
        assert s.priority == DapnetPriority.EMERGENCY

    assert len(list(aobj.find(tag="dapnet_str"))) == 2
    assert len(list(aobj.find(tag="dapnet_str_int"))) == 2
    assert len(list(aobj.find(tag="dapnet_int"))) == 2

    assert len(list(aobj.find(tag="dapnet_invalid"))) == 1
    assert (
        next(aobj.find(tag="dapnet_invalid")).priority == DapnetPriority.NORMAL
    )

    # Notifications work
    assert aobj.notify(title="title", body="body") is True
