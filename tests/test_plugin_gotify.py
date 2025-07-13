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
from apprise.plugins.gotify import GotifyPriority, NotifyGotify

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "gotify://",
        {
            "instance": None,
        },
    ),
    # No token specified
    (
        "gotify://hostname",
        {
            "instance": TypeError,
        },
    ),
    # Provide a hostname and token
    (
        "gotify://hostname/%s" % ("t" * 16),
        {
            "instance": NotifyGotify,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "gotify://hostname/t...t",
        },
    ),
    # Provide a hostname, path, and token
    (
        "gotify://hostname/a/path/ending/in/a/slash/%s" % ("u" * 16),
        {
            "instance": NotifyGotify,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "gotify://hostname/a/path/ending/in/a/slash/u...u/",
        },
    ),
    # Markdown test
    (
        "gotify://hostname/%s?format=markdown" % ("t" * 16),
        {
            "instance": NotifyGotify,
        },
    ),
    # Provide a hostname, path, and token
    (
        "gotify://hostname/a/path/not/ending/in/a/slash/%s" % ("v" * 16),
        {
            "instance": NotifyGotify,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": (
                "gotify://hostname/a/path/not/ending/in/a/slash/v...v/"
            ),
        },
    ),
    # Provide a priority
    (
        "gotify://hostname/%s?priority=high" % ("i" * 16),
        {
            "instance": NotifyGotify,
        },
    ),
    # Provide an invalid priority
    (
        "gotify://hostname:8008/%s?priority=invalid" % ("i" * 16),
        {
            "instance": NotifyGotify,
        },
    ),
    # An invalid url
    (
        "gotify://:@/",
        {
            "instance": None,
        },
    ),
    (
        "gotify://hostname/%s/" % ("t" * 16),
        {
            "instance": NotifyGotify,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "gotifys://localhost/%s/" % ("t" * 16),
        {
            "instance": NotifyGotify,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "gotify://localhost/%s/" % ("t" * 16),
        {
            "instance": NotifyGotify,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_gotify_urls():
    """NotifyGotify() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_gotify_edge_cases():
    """NotifyGotify() Edge Cases."""
    # Initializes the plugin with an invalid token
    with pytest.raises(TypeError):
        NotifyGotify(token=None)
    # Whitespace also acts as an invalid token value
    with pytest.raises(TypeError):
        NotifyGotify(token="   ")


@mock.patch("requests.post")
def test_plugin_gotify_config_files(mock_post):
    """NotifyGotify() Config File Cases."""
    content = """
    urls:
      - gotify://hostname/{}:
          - priority: 0
            tag: gotify_int low
          - priority: "0"
            tag: gotify_str_int low
          # We want to make sure our '1' does not match the '10' entry
          - priority: "1"
            tag: gotify_str_int low
          - priority: low
            tag: gotify_str low

          # This will take on moderate (default) priority
          - priority: invalid
            tag: gotify_invalid

      - gotify://hostname/{}:
          - priority: 10
            tag: gotify_int emerg
          - priority: "10"
            tag: gotify_str_int emerg
          - priority: emergency
            tag: gotify_str emerg
    """.format("a" * 16, "b" * 16)

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    # Create ourselves a config object
    ac = apprise.AppriseConfig()
    assert ac.add_config(content=content) is True

    aobj = apprise.Apprise()

    # Add our configuration
    aobj.add(ac)

    # We should be able to read our 8 servers from that
    # 4x low
    # 3x emerg
    # 1x invalid (so takes on normal priority)
    assert len(ac.servers()) == 8
    assert len(aobj) == 8
    assert len(list(aobj.find(tag="low"))) == 4
    for s in aobj.find(tag="low"):
        assert s.priority == GotifyPriority.LOW

    assert len(list(aobj.find(tag="emerg"))) == 3
    for s in aobj.find(tag="emerg"):
        assert s.priority == GotifyPriority.EMERGENCY

    assert len(list(aobj.find(tag="gotify_str"))) == 2
    assert len(list(aobj.find(tag="gotify_str_int"))) == 3
    assert len(list(aobj.find(tag="gotify_int"))) == 2

    assert len(list(aobj.find(tag="gotify_invalid"))) == 1
    assert (
        next(aobj.find(tag="gotify_invalid")).priority == GotifyPriority.NORMAL
    )
