# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2026, Chris Caron <lead2gold@gmail.com>
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

import logging
import os
from unittest import mock

from helpers import AppriseURLTester
import requests

import apprise
from apprise.plugins.signalgrid import NotifySignalgrid

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")


apprise_url_tests = (
    (
        "signalgrid://",
        {
            "instance": TypeError,
        },
    ),
    (
        "signalgrid://CLIENTKEY/CHANNEL",
        {
            "instance": NotifySignalgrid,
            "privacy_url": "signalgrid://C...Y/CHANNEL/",
        },
    ),
    (
        "signalgrid://CLIENTKEY/CHANNEL1/CHANNEL2",
        {
            "instance": NotifySignalgrid,
        },
    ),
    (
        "signalgrid://CLIENTKEY/CHANNEL?critical=yes",
        {
            "instance": NotifySignalgrid,
        },
    ),
    (
        "signalgrid://CLIENTKEY/CHANNEL?to=CHANNEL2,CHANNEL3",
        {
            "instance": NotifySignalgrid,
        },
    ),
    (
        # No channels specified at all; the plugin still loads, but has
        # nothing to notify
        "signalgrid://CLIENTKEY",
        {
            "instance": NotifySignalgrid,
            "notify_response": False,
        },
    ),
    (
        "signalgrid://CLIENTKEY/CHANNEL",
        {
            "instance": NotifySignalgrid,
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "signalgrid://CLIENTKEY/CHANNEL",
        {
            "instance": NotifySignalgrid,
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_signalgrid_urls():
    """NotifySignalgrid() Apprise URLs."""
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_signalgrid_payload(mock_post):
    """Test Signalgrid request payload."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b"OK"
    mock_post.return_value = response

    obj = NotifySignalgrid(
        client_key="CLIENTKEY",
        targets=["CHANNEL"],
        critical=True,
    )

    assert (
        obj.notify(
            title="Server Down",
            body="api01 is unreachable",
            notify_type=apprise.NotifyType.FAILURE,
        )
        is True
    )

    assert mock_post.call_count == 1

    args, kwargs = mock_post.call_args

    assert args[0] == "https://api.signalgrid.co/v1/push"
    assert kwargs["data"]["client_key"] == "CLIENTKEY"
    assert kwargs["data"]["channel"] == "CHANNEL"
    assert kwargs["data"]["title"] == "Server Down"
    assert kwargs["data"]["body"] == "api01 is unreachable"
    assert kwargs["data"]["type"] == "CRIT"
    assert kwargs["data"]["critical"] == "true"


@mock.patch("requests.post")
def test_plugin_signalgrid_type_mapping(mock_post):
    """Test Apprise to Signalgrid type mapping."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    obj = NotifySignalgrid(
        client_key="CLIENTKEY",
        targets=["CHANNEL"],
    )

    mappings = (
        (apprise.NotifyType.INFO, "INFO"),
        (apprise.NotifyType.SUCCESS, "SUCCESS"),
        (apprise.NotifyType.WARNING, "WARN"),
        (apprise.NotifyType.FAILURE, "CRIT"),
    )

    for notify_type, expected in mappings:
        mock_post.reset_mock()

        assert (
            obj.notify(
                title="Test",
                body="Test",
                notify_type=notify_type,
            )
            is True
        )

        assert mock_post.call_args.kwargs["data"]["type"] == expected
        assert mock_post.call_args.kwargs["data"]["critical"] == "false"


@mock.patch("requests.post")
def test_plugin_signalgrid_multi_channel(mock_post):
    """Test Signalgrid sends one request per channel."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    obj = NotifySignalgrid(
        client_key="CLIENTKEY",
        targets=["CHANNEL1", "CHANNEL2"],
    )

    assert len(obj) == 2

    assert obj.notify(title="Test", body="Test") is True
    assert mock_post.call_count == 2

    sent_channels = {
        call.kwargs["data"]["channel"] for call in mock_post.call_args_list
    }
    assert sent_channels == {"CHANNEL1", "CHANNEL2"}


@mock.patch("requests.post")
def test_plugin_signalgrid_multi_channel_partial_failure(mock_post):
    """Test one failed channel still notifies the rest and reports False."""

    ok_response = mock.Mock()
    ok_response.status_code = requests.codes.ok

    error_response = mock.Mock()
    error_response.status_code = requests.codes.internal_server_error
    error_response.content = b"error"

    mock_post.side_effect = [error_response, ok_response]

    obj = NotifySignalgrid(
        client_key="CLIENTKEY",
        targets=["CHANNEL1", "CHANNEL2"],
    )

    assert obj.notify(title="Test", body="Test") is False
    assert mock_post.call_count == 2


def test_plugin_signalgrid_no_targets():
    """Test that a Signalgrid object with no channels loads but has
    nothing to notify."""

    obj = NotifySignalgrid(client_key="CLIENTKEY")

    assert len(obj) == 1
    assert obj.notify(title="Test", body="Test") is False


def test_plugin_signalgrid_url_roundtrip():
    """Test Signalgrid URL parsing and reconstruction."""

    obj = NotifySignalgrid(
        client_key="CLIENTKEY",
        targets=["CHANNEL1", "CHANNEL2"],
        critical=True,
    )

    generated = obj.url()
    parsed = NotifySignalgrid.parse_url(generated)

    assert parsed is not None
    assert parsed["client_key"] == "CLIENTKEY"
    assert parsed["targets"] == ["CHANNEL1", "CHANNEL2"]
    assert parsed["critical"] is True

    obj2 = NotifySignalgrid(**parsed)

    assert obj2.client_key == "CLIENTKEY"
    assert obj2.targets == ["CHANNEL1", "CHANNEL2"]
    assert obj2.critical is True

    # Two connections that share a client key differ only in the channels
    # they notify, so they still identify as the same connection.
    assert obj.url_identifier == obj2.url_identifier


def test_plugin_signalgrid_client_key_override():
    """Test that ?client_key= overrides the hostname-derived value."""

    parsed = NotifySignalgrid.parse_url(
        "signalgrid://IGNOREME/CHANNEL?client_key=REALKEY"
    )

    assert parsed is not None
    assert parsed["client_key"] == "REALKEY"


@mock.patch("requests.post")
def test_plugin_signalgrid_attach_warning(mock_post):
    """Test that attachments are ignored with a warning."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    obj = NotifySignalgrid(client_key="CLIENTKEY", targets=["CHANNEL"])

    attach = apprise.AppriseAttachment(
        os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    )

    with mock.patch.object(obj, "logger") as mock_logger:
        assert obj.notify(title="Test", body="Test", attach=attach) is True
        assert mock_logger.warning.called
