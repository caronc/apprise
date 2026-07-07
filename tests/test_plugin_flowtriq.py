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

# Disable logging for a cleaner testing output
import json
import logging
from unittest import mock
from urllib.parse import urlparse

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, NotifyType
from apprise.plugins.flowtriq import NotifyFlowtriq

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "flowtriq://",
        {
            "instance": None,
        },
    ),
    # No webhook path specified
    (
        "flowtriq://apikey@hostname",
        {
            "instance": TypeError,
        },
    ),
    # No API key specified
    (
        "flowtriq://hostname/hooks/abc123",
        {
            "instance": TypeError,
        },
    ),
    # Provide a hostname, apikey, and webhook path (insecure)
    (
        "flowtriq://myapikey@hostname/hooks/abc123/",
        {
            "instance": NotifyFlowtriq,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "flowtriq://m...y@hostname/hooks/abc123/",
        },
    ),
    # Secure variant (flowtriqs://)
    (
        "flowtriqs://myapikey@hostname/hooks/abc123/",
        {
            "instance": NotifyFlowtriq,
            "privacy_url": "flowtriqs://m...y@hostname/hooks/abc123/",
        },
    ),
    # Provide a hostname with port (insecure)
    (
        "flowtriq://myapikey@hostname:8080/hooks/abc123/",
        {
            "instance": NotifyFlowtriq,
            "privacy_url": "flowtriq://m...y@hostname:8080/hooks/abc123/",
        },
    ),
    # Secure with non-default port
    (
        "flowtriqs://myapikey@hostname:8443/hooks/abc123/",
        {
            "instance": NotifyFlowtriq,
            "privacy_url": "flowtriqs://m...y@hostname:8443/hooks/abc123/",
        },
    ),
    # Multi-segment webhook path
    (
        "flowtriqs://myapikey@flowtriq.com/api/v1/webhook/xyz/",
        {
            "instance": NotifyFlowtriq,
        },
    ),
    # An invalid url
    (
        "flowtriq://:@/",
        {
            "instance": None,
        },
    ),
    # Test failure cases
    (
        "flowtriq://myapikey@hostname/hooks/abc123/",
        {
            "instance": NotifyFlowtriq,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "flowtriq://myapikey@hostname/hooks/abc123/",
        {
            "instance": NotifyFlowtriq,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "flowtriq://myapikey@hostname/hooks/abc123/",
        {
            "instance": NotifyFlowtriq,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_flowtriq_urls():
    """NotifyFlowtriq() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_flowtriq_edge_cases():
    """NotifyFlowtriq() Edge Cases."""
    # Initializes the plugin with an invalid API key
    with pytest.raises(TypeError):
        NotifyFlowtriq(apikey=None, webhook_path="hooks/abc123")
    # Whitespace also acts as an invalid API key
    with pytest.raises(TypeError):
        NotifyFlowtriq(apikey="   ", webhook_path="hooks/abc123")

    # Missing webhook path
    with pytest.raises(TypeError):
        NotifyFlowtriq(apikey="validkey", webhook_path=None)
    with pytest.raises(TypeError):
        NotifyFlowtriq(apikey="validkey", webhook_path="   ")

    # A webhook path consisting only of slashes strips to empty
    with pytest.raises(TypeError):
        NotifyFlowtriq(apikey="validkey", webhook_path="///")

    # Missing host is caught after super().__init__()
    with pytest.raises(TypeError):
        NotifyFlowtriq(
            apikey="validkey", webhook_path="hooks/abc123", host=None
        )


@mock.patch("requests.post")
def test_plugin_flowtriq_send(mock_post):
    """NotifyFlowtriq() send path coverage."""

    def _mk_resp(code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = b"{}"
        return r

    # ------------------------------------------------------------------
    # Successful send — 200
    # ------------------------------------------------------------------
    mock_post.return_value = _mk_resp(requests.codes.ok)
    obj = NotifyFlowtriq(
        apikey="ft_key_xxxx",
        webhook_path="hooks/abc123",
        host="flowtriq.com",
    )
    assert obj.send(body="Test body", title="Test title") is True
    assert mock_post.call_count == 1

    # Verify the POST landed at the right hostname
    call_url = mock_post.call_args[0][0]
    assert urlparse(call_url).hostname == "flowtriq.com"

    # Verify payload structure and severity mapping for INFO
    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["body"] == "Test body"
    assert payload["title"] == "Test title"
    assert payload["severity"] == "info"
    assert payload["source"] == "apprise"

    # Verify the API key header
    headers = mock_post.call_args[1]["headers"]
    assert headers["X-API-Key"] == "ft_key_xxxx"
    assert headers["Content-Type"] == "application/json"

    mock_post.reset_mock()

    # ------------------------------------------------------------------
    # 201, 202, 204 are also accepted
    # ------------------------------------------------------------------
    for code in (
        requests.codes.created,
        requests.codes.accepted,
        requests.codes.no_content,
    ):
        mock_post.return_value = _mk_resp(code)
        assert obj.send(body="body") is True

    mock_post.reset_mock()

    # ------------------------------------------------------------------
    # Severity mapping for all notify types
    # ------------------------------------------------------------------
    severity_cases = [
        (NotifyType.INFO, "info"),
        (NotifyType.SUCCESS, "success"),
        (NotifyType.WARNING, "warning"),
        (NotifyType.FAILURE, "critical"),
    ]
    mock_post.return_value = _mk_resp()
    for notify_type, expected_severity in severity_cases:
        obj.send(body="body", notify_type=notify_type)
        payload = json.loads(mock_post.call_args[1]["data"])
        assert payload["severity"] == expected_severity

    mock_post.reset_mock()

    # ------------------------------------------------------------------
    # Port is included in the request URL when set
    # ------------------------------------------------------------------
    obj_port = NotifyFlowtriq(
        apikey="key",
        webhook_path="hooks/test",
        host="myhost.example.com",
        port=8443,
    )
    mock_post.return_value = _mk_resp()
    assert obj_port.send(body="body") is True
    call_url = mock_post.call_args[0][0]
    parsed = urlparse(call_url)
    assert parsed.hostname == "myhost.example.com"
    assert parsed.port == 8443

    mock_post.reset_mock()

    # ------------------------------------------------------------------
    # HTTP error response returns False
    # ------------------------------------------------------------------
    mock_post.return_value = _mk_resp(requests.codes.internal_server_error)
    assert obj.send(body="body") is False

    mock_post.reset_mock()

    # ------------------------------------------------------------------
    # Unknown HTTP error code (no entry in lookup table) returns False
    # ------------------------------------------------------------------
    mock_post.return_value = _mk_resp(999)
    assert obj.send(body="body") is False

    mock_post.reset_mock()

    # ------------------------------------------------------------------
    # requests.RequestException returns False
    # ------------------------------------------------------------------
    mock_post.side_effect = requests.RequestException("boom")
    assert obj.send(body="body") is False


@mock.patch("requests.post")
def test_plugin_flowtriq_url_parsing(mock_post):
    """NotifyFlowtriq() URL round-trip and parse_url edge cases."""

    # Round-trip: parse_url(url()) must recover the same object
    obj = NotifyFlowtriq(
        apikey="mykey",
        webhook_path="hooks/abc123",
        host="flowtriq.com",
    )
    result = NotifyFlowtriq.parse_url(obj.url())
    assert result is not None
    obj2 = NotifyFlowtriq(**result)
    assert obj.url_identifier == obj2.url_identifier

    # Round-trip with non-default port
    obj_port = NotifyFlowtriq(
        apikey="mykey",
        webhook_path="api/v1/wh",
        host="myhost",
        port=9000,
    )
    result = NotifyFlowtriq.parse_url(obj_port.url())
    assert result is not None
    obj_port2 = NotifyFlowtriq(**result)
    assert obj_port.url_identifier == obj_port2.url_identifier

    # url_identifier via URL parse: flowtriq:// is insecure → port fallback 80
    obj_insecure = NotifyFlowtriq.parse_url("flowtriq://key@h/hooks/x")
    assert obj_insecure is not None
    uid_ins = NotifyFlowtriq(**obj_insecure).url_identifier
    assert uid_ins[0] == "flowtriq"
    assert uid_ins[1] == "h"
    assert uid_ins[2] == 80

    # flowtriqs:// is secure → port fallback 443
    obj_secure = NotifyFlowtriq.parse_url("flowtriqs://key@h/hooks/x")
    assert obj_secure is not None
    uid_sec = NotifyFlowtriq(**obj_secure).url_identifier
    assert uid_sec[0] == "flowtriqs"
    assert uid_sec[1] == "h"
    assert uid_sec[2] == 443

    # parse_url with no user field → apikey is None
    result = NotifyFlowtriq.parse_url("flowtriq://hostname/hooks/abc123")
    assert result is not None
    assert result["apikey"] is None

    # parse_url with empty path → webhook_path is None
    result = NotifyFlowtriq.parse_url("flowtriq://key@hostname")
    assert result is not None
    assert not result.get("webhook_path")

    # parse_url returns None for an unparseable URL
    result = NotifyFlowtriq.parse_url("flowtriq://:@/")
    assert result is None

    # privacy_url hides the API key
    obj = NotifyFlowtriq(
        apikey="myapikey",
        webhook_path="hooks/abc123",
        host="hostname",
    )
    priv = obj.url(privacy=True)
    assert "myapikey" not in priv
    assert "m...y" in priv


@mock.patch("requests.post")
def test_plugin_flowtriq_apprise_integration(mock_post):
    """NotifyFlowtriq() Apprise integration."""

    mock_post.return_value = mock.Mock()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = b"{}"

    app = Apprise()
    assert app.add("flowtriq://mykey@flowtriq.com/hooks/abc123") is True
    assert bool(app.notify(title="Title", body="Body")) is True
    assert mock_post.call_count == 1
