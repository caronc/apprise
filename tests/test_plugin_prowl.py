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
from apprise.plugins.prowl import NotifyProwl, ProwlPriority

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "prowl://",
        {
            "instance": TypeError,
        },
    ),
    # bad url
    (
        "prowl://:@/",
        {
            "instance": TypeError,
        },
    ),
    # Invalid API Key
    (
        "prowl://%s" % ("a" * 20),
        {
            "instance": TypeError,
        },
    ),
    # Provider Key
    (
        "prowl://{}/{}".format("a" * 40, "b" * 40),
        {
            "instance": NotifyProwl,
        },
    ),
    # Invalid Provider Key
    (
        "prowl://{}/{}".format("a" * 40, "b" * 20),
        {
            "instance": TypeError,
        },
    ),
    # APIkey; no device
    (
        "prowl://%s" % ("a" * 40),
        {
            "instance": NotifyProwl,
        },
    ),
    # API Key
    (
        "prowl://%s" % ("a" * 40),
        {
            "instance": NotifyProwl,
            # don't include an image by default
            "include_image": False,
        },
    ),
    # API Key + priority setting
    (
        "prowl://%s?priority=high" % ("a" * 40),
        {
            "instance": NotifyProwl,
        },
    ),
    # API Key + invalid priority setting
    (
        "prowl://%s?priority=invalid" % ("a" * 40),
        {
            "instance": NotifyProwl,
        },
    ),
    # API Key + priority setting (empty)
    (
        "prowl://%s?priority=" % ("a" * 40),
        {
            "instance": NotifyProwl,
        },
    ),
    # API Key + No Provider Key (empty)
    (
        "prowl://%s///" % ("w" * 40),
        {
            "instance": NotifyProwl,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "prowl://w...w/",
        },
    ),
    # API Key + Provider Key
    (
        "prowl://{}/{}".format("a" * 40, "b" * 40),
        {
            "instance": NotifyProwl,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "prowl://a...a/b...b",
        },
    ),
    # API Key + with image
    (
        "prowl://%s" % ("a" * 40),
        {
            "instance": NotifyProwl,
        },
    ),
    (
        "prowl://%s" % ("a" * 40),
        {
            "instance": NotifyProwl,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "prowl://%s" % ("a" * 40),
        {
            "instance": NotifyProwl,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "prowl://%s" % ("a" * 40),
        {
            "instance": NotifyProwl,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_prowl():
    """NotifyProwl() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_prowl_edge_cases():
    """NotifyProwl() Edge Cases."""
    # Initializes the plugin with an invalid apikey
    with pytest.raises(TypeError):
        NotifyProwl(apikey=None)
    # Whitespace also acts as an invalid apikey value
    with pytest.raises(TypeError):
        NotifyProwl(apikey="  ")

    # Whitespace also acts as an invalid provider key
    with pytest.raises(TypeError):
        NotifyProwl(apikey="abcd", providerkey=object())
    with pytest.raises(TypeError):
        NotifyProwl(apikey="abcd", providerkey="  ")


@mock.patch("requests.post")
def test_plugin_prowl_config_files(mock_post):
    """NotifyProwl() Config File Cases."""
    content = """
    urls:
      - prowl://{}:
          - priority: -2
            tag: prowl_int low
          - priority: "-2"
            tag: prowl_str_int low
          - priority: low
            tag: prowl_str low

          # This will take on moderate (default) priority
          - priority: invalid
            tag: prowl_invalid

      - prowl://{}:
          - priority: 2
            tag: prowl_int emerg
          - priority: "2"
            tag: prowl_str_int emerg
          - priority: emergency
            tag: prowl_str emerg
    """.format("a" * 40, "b" * 40)

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
        assert s.priority == ProwlPriority.LOW

    assert len(list(aobj.find(tag="emerg"))) == 3
    for s in aobj.find(tag="emerg"):
        assert s.priority == ProwlPriority.EMERGENCY

    assert len(list(aobj.find(tag="prowl_str"))) == 2
    assert len(list(aobj.find(tag="prowl_str_int"))) == 2
    assert len(list(aobj.find(tag="prowl_int"))) == 2

    assert len(list(aobj.find(tag="prowl_invalid"))) == 1
    assert (
        next(aobj.find(tag="prowl_invalid")).priority == ProwlPriority.NORMAL
    )
