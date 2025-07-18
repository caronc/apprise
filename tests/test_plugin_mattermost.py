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

import json

# Disable logging for a cleaner testing output
import logging

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise
from apprise.plugins.mattermost import NotifyMattermost

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "mmost://",
        {
            "instance": None,
        },
    ),
    (
        "mmosts://",
        {
            "instance": None,
        },
    ),
    (
        "mmost://:@/",
        {
            "instance": None,
        },
    ),
    (
        "mmosts://localhost",
        {
            # Thrown because there was no webhook id specified
            "instance": TypeError,
        },
    ),
    (
        "mmost://localhost/3ccdd113474722377935511fc85d3dd4",
        {
            "instance": NotifyMattermost,
        },
    ),
    (
        "mmost://user@localhost/3ccdd113474722377935511fc85d3dd4?channel=test",
        {
            "instance": NotifyMattermost,
        },
    ),
    (
        "mmost://user@localhost/3ccdd113474722377935511fc85d3dd4?channels=test",
        {
            "instance": NotifyMattermost,
        },
    ),
    (
        "mmost://user@localhost/3ccdd113474722377935511fc85d3dd4?to=test",
        {
            "instance": NotifyMattermost,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "mmost://user@localhost/3...4/",
        },
    ),
    (
        (
            "mmost://localhost/3ccdd113474722377935511fc85d3dd4"
            "?to=test&image=True"
        ),
        {"instance": NotifyMattermost},
    ),
    (
        (
            "mmost://localhost/3ccdd113474722377935511fc85d3dd4"
            "?to=test&image=False"
        ),
        {"instance": NotifyMattermost},
    ),
    (
        (
            "mmost://localhost/3ccdd113474722377935511fc85d3dd4"
            "?to=test&image=True"
        ),
        {
            "instance": NotifyMattermost,
            # don't include an image by default
            "include_image": False,
        },
    ),
    (
        "mmost://localhost:8080/3ccdd113474722377935511fc85d3dd4",
        {
            "instance": NotifyMattermost,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "mmost://localhost:8080/3...4/",
        },
    ),
    (
        "mmost://localhost:8080/3ccdd113474722377935511fc85d3dd4",
        {
            "instance": NotifyMattermost,
        },
    ),
    (
        "mmost://localhost:invalid-port/3ccdd113474722377935511fc85d3dd4",
        {
            "instance": None,
        },
    ),
    (
        "mmosts://localhost/3ccdd113474722377935511fc85d3dd4",
        {
            "instance": NotifyMattermost,
        },
    ),
    (
        "https://mattermost.example.com/hooks/3ccdd113474722377935511fc85d3dd4",
        {
            "instance": NotifyMattermost,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "mmosts://mattermost.example.com/3...4/",
        },
    ),
    # Test our paths
    (
        "mmosts://localhost/a/path/3ccdd113474722377935511fc85d3dd4",
        {
            "instance": NotifyMattermost,
        },
    ),
    (
        "mmosts://localhost/////3ccdd113474722377935511fc85d3dd4///",
        {
            "instance": NotifyMattermost,
        },
    ),
    (
        "mmost://localhost/3ccdd113474722377935511fc85d3dd4",
        {
            "instance": NotifyMattermost,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "mmost://localhost/3ccdd113474722377935511fc85d3dd4",
        {
            "instance": NotifyMattermost,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "mmost://localhost/3ccdd113474722377935511fc85d3dd4",
        {
            "instance": NotifyMattermost,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


@pytest.fixture
def request_mock(mocker):
    """Prepare requests mock."""
    mock_post = mocker.patch("requests.post")
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    return mock_post


def test_plugin_mattermost_urls():
    """NotifyMattermost() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_mattermost_edge_cases():
    """NotifyMattermost() Edge Cases."""

    # Invalid Authorization Token
    with pytest.raises(TypeError):
        NotifyMattermost(None)
    with pytest.raises(TypeError):
        NotifyMattermost("     ")


def test_plugin_mattermost_channels(request_mock):
    """NotifyMattermost() Channel Testing."""

    # Test channels with/without hashtag (#)
    user = "user1"
    token = "token"
    channels = ["#one", "two"]

    # Instantiate our URL
    obj = Apprise.instantiate(
        "mmost://{user}@localhost:8065/{token}?channels={channels}".format(
            user=user, token=token, channels=",".join(channels)
        )
    )

    assert isinstance(obj, NotifyMattermost)
    assert obj.notify(body="body", title="title") is True

    assert request_mock.called is True
    assert request_mock.call_count == 2
    assert request_mock.call_args_list[0][0][0].startswith(
        "http://localhost:8065/hooks/token"
    )

    # Our Posted JSON Object
    posted_json = json.loads(request_mock.call_args_list[0][1]["data"])
    assert "username" in posted_json
    assert "channel" in posted_json
    assert "text" in posted_json
    assert posted_json["username"] == "user1"
    assert posted_json["channel"] == "one"
    assert posted_json["text"] == "title\r\nbody"

    # Our second Posted JSON Object
    posted_json = json.loads(request_mock.call_args_list[1][1]["data"])
    assert posted_json["username"] == "user1"
    assert posted_json["channel"] == "two"
    assert posted_json["text"] == "title\r\nbody"


def test_mattermost_post_default_port(request_mock):
    # Test token
    token = "token"

    # Instantiate our URL
    obj = Apprise.instantiate(f"mmosts://mattermost.example.com/{token}")

    assert isinstance(obj, NotifyMattermost)
    assert obj.notify(body="body", title="title") is True

    # Make sure we don't use port if not provided
    assert request_mock.called is True
    assert request_mock.call_count == 1
    assert request_mock.call_args_list[0][0][0].startswith(
        "https://mattermost.example.com/hooks/token"
    )

    # Our Posted JSON Object
    posted_json = json.loads(request_mock.call_args_list[0][1]["data"])
    assert "text" in posted_json
    assert posted_json["text"] == "title\r\nbody"
