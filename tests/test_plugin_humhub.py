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
import logging
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise
from apprise.plugins.humhub import NotifyHumHub

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    # No host
    (
        "humhub://",
        {
            "instance": None,
        },
    ),
    # Host present but no user/token
    (
        "humhub://hostname",
        {
            "instance": TypeError,
        },
    ),
    # Token present but no container ID
    (
        "humhub://token@hostname",
        {
            "instance": TypeError,
        },
    ),
    # Invalid container ID (not numeric)
    (
        "humhubs://token@hostname/invalid",
        {
            "instance": TypeError,
        },
    ),
    # Negative container ID (not a positive integer)
    (
        "humhubs://token@hostname/-1",
        {
            "instance": TypeError,
        },
    ),
    # Zero container ID (not a positive integer)
    (
        "humhubs://token@hostname/0",
        {
            "instance": TypeError,
        },
    ),
    # Valid bearer token + container ID over HTTP (insecure)
    (
        "humhub://mytoken@hostname/1",
        {
            "instance": NotifyHumHub,
            "privacy_url": "humhub://m...n@hostname/1/",
            "requests_response_text": '{"id": 1}',
        },
    ),
    # Valid bearer token + container ID over HTTPS
    (
        "humhubs://mytoken@hostname/1",
        {
            "instance": NotifyHumHub,
            "privacy_url": "humhubs://m...n@hostname/1/",
            "requests_response_text": '{"id": 1}',
        },
    ),
    # Valid basic auth + container ID
    (
        "humhubs://user:pass@hostname/1",
        {
            "instance": NotifyHumHub,
            "privacy_url": "humhubs://u...r:****@hostname/1/",
            "requests_response_text": '{"id": 1}',
        },
    ),
    # Multiple container IDs in the path
    (
        "humhubs://mytoken@hostname/1/2/3",
        {
            "instance": NotifyHumHub,
            "requests_response_text": '{"id": 1}',
        },
    ),
    # Container IDs via ?to= parameter
    (
        "humhubs://mytoken@hostname/?to=1,2,3",
        {
            "instance": NotifyHumHub,
            "requests_response_text": '{"id": 1}',
        },
    ),
    # Custom port
    (
        "humhubs://mytoken@hostname:8443/1",
        {
            "instance": NotifyHumHub,
            "requests_response_text": '{"id": 1}',
        },
    ),
    # HTTP 500 response -- bearer auth
    (
        "humhubs://mytoken@hostname/1",
        {
            "instance": NotifyHumHub,
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    # Unknown error code -- bearer auth
    (
        "humhubs://mytoken@hostname/1",
        {
            "instance": NotifyHumHub,
            "response": False,
            "requests_response_code": 999,
        },
    ),
    # RequestException -- bearer auth
    (
        "humhubs://mytoken@hostname/1",
        {
            "instance": NotifyHumHub,
            "test_requests_exceptions": True,
        },
    ),
    # HTTP 500 response -- basic auth
    (
        "humhubs://user:pass@hostname/1",
        {
            "instance": NotifyHumHub,
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    # Unknown error code -- basic auth
    (
        "humhubs://user:pass@hostname/1",
        {
            "instance": NotifyHumHub,
            "response": False,
            "requests_response_code": 999,
        },
    ),
    # RequestException -- basic auth
    (
        "humhubs://user:pass@hostname/1",
        {
            "instance": NotifyHumHub,
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_humhub_urls():
    """NotifyHumHub() Apprise URLs."""
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_humhub_init():
    """NotifyHumHub() initialization edge cases."""

    # No user/token at all
    with pytest.raises(TypeError):
        NotifyHumHub(user=None, host="hostname", targets=["1"])

    # Empty string user
    with pytest.raises(TypeError):
        NotifyHumHub(user="", host="hostname", targets=["1"])

    # No containers specified
    with pytest.raises(TypeError):
        NotifyHumHub(user="token", host="hostname", targets=[])

    # None targets
    with pytest.raises(TypeError):
        NotifyHumHub(user="token", host="hostname", targets=None)

    # Only invalid targets
    with pytest.raises(TypeError):
        NotifyHumHub(user="token", host="hostname", targets=["bad", "0", "-5"])

    # Mixed valid and invalid -- should succeed, dropping the bad ones
    obj = NotifyHumHub(
        user="token", host="hostname", targets=["1", "bad", "2"]
    )
    assert len(obj.targets) == 2
    assert "1" in obj.targets
    assert "2" in obj.targets
    assert len(obj._invalid_targets) == 1
    assert "bad" in obj._invalid_targets

    # Valid bearer token
    obj = NotifyHumHub(user="bearertoken", host="hostname", targets=["42"])
    assert obj.targets == ["42"]
    assert obj.password is None

    # Valid basic auth
    obj = NotifyHumHub(
        user="admin", password="secret", host="hostname", targets=["5"]
    )
    assert obj.targets == ["5"]
    assert obj.password == "secret"


@mock.patch("requests.post")
def test_plugin_humhub_bearer_send(mock_post):
    """NotifyHumHub() bearer token send."""

    # Successful response
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = b""

    obj = NotifyHumHub(user="mytoken", host="localhost", targets=["1"])
    assert obj.notify(body="Test body") is True

    # Confirm bearer token header was set
    assert mock_post.called
    _, kwargs = mock_post.call_args
    assert "Authorization" in kwargs.get("headers", {})
    assert kwargs["headers"]["Authorization"] == "Bearer mytoken"
    assert kwargs.get("auth") is None


@mock.patch("requests.post")
def test_plugin_humhub_basic_send(mock_post):
    """NotifyHumHub() basic auth send."""

    # Successful response
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = b""

    obj = NotifyHumHub(
        user="admin", password="secret", host="localhost", targets=["1"]
    )
    assert obj.notify(body="Test body") is True

    # Confirm basic auth tuple was passed and no Authorization header
    assert mock_post.called
    _, kwargs = mock_post.call_args
    assert kwargs.get("auth") == ("admin", "secret")
    assert "Authorization" not in kwargs.get("headers", {})


@mock.patch("requests.post")
def test_plugin_humhub_multi_container(mock_post):
    """NotifyHumHub() multiple container send."""

    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = b""

    obj = NotifyHumHub(user="token", host="localhost", targets=["1", "2", "3"])
    assert obj.notify(body="Hello") is True

    # One POST per container
    assert mock_post.call_count == 3


@mock.patch("requests.post")
def test_plugin_humhub_partial_failure(mock_post):
    """NotifyHumHub() partial failure across multiple containers."""

    def side_effect_fn(*args, **kwargs):
        # Fail on the second call (container "2"), succeed on others
        if mock_post.call_count == 2:
            r = requests.Request()
            r.status_code = requests.codes.internal_server_error
            r.content = b"error"
            return r
        r = requests.Request()
        r.status_code = requests.codes.ok
        r.content = b""
        return r

    mock_post.side_effect = side_effect_fn

    obj = NotifyHumHub(user="token", host="localhost", targets=["1", "2", "3"])
    # Partial failure means overall False
    assert obj.notify(body="msg") is False
    assert mock_post.call_count == 3


@mock.patch("requests.post")
def test_plugin_humhub_http_errors(mock_post):
    """NotifyHumHub() HTTP error responses."""

    # HTTP 401 Unauthorized
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = 401
    mock_post.return_value.content = b"Unauthorized"

    obj = NotifyHumHub(user="token", host="localhost", targets=["1"])
    assert obj.notify(body="msg") is False

    # HTTP 500 Internal Server Error
    mock_post.return_value.status_code = requests.codes.internal_server_error
    assert obj.notify(body="msg") is False

    # Unknown / unexpected code
    mock_post.return_value.status_code = 999
    assert obj.notify(body="msg") is False


@mock.patch("requests.post")
def test_plugin_humhub_request_exception(mock_post):
    """NotifyHumHub() RequestException handling."""

    mock_post.side_effect = requests.RequestException("Connection refused")

    obj = NotifyHumHub(user="token", host="localhost", targets=["1", "2"])
    assert obj.notify(body="msg") is False
    # Both containers attempted
    assert mock_post.call_count == 2


def test_plugin_humhub_url_round_trip():
    """NotifyHumHub() URL round-trip invariant."""

    # Bearer token, single container
    obj1 = NotifyHumHub(user="mytoken", host="myhost", targets=["7"])
    result = NotifyHumHub.parse_url(obj1.url())
    obj2 = NotifyHumHub(**result)
    assert obj1.url_identifier == obj2.url_identifier
    assert len(obj1.targets) == len(obj2.targets)

    # Basic auth, multiple containers
    obj1 = NotifyHumHub(
        user="admin",
        password="secret",
        host="myhost",
        targets=["1", "2", "3"],
    )
    result = NotifyHumHub.parse_url(obj1.url())
    obj2 = NotifyHumHub(**result)
    assert obj1.url_identifier == obj2.url_identifier
    assert len(obj1.targets) == len(obj2.targets)

    # Custom port
    obj1 = NotifyHumHub(user="tok", host="myhost", port=9090, targets=["10"])
    result = NotifyHumHub.parse_url(obj1.url())
    obj2 = NotifyHumHub(**result)
    assert obj1.url_identifier == obj2.url_identifier

    # Invalid targets round-trip inline in path alongside valid ones
    obj1 = NotifyHumHub(user="tok", host="myhost", targets=["5", "bad", "0"])
    assert len(obj1.targets) == 1
    assert len(obj1._invalid_targets) == 2
    # url() emits valid + invalid targets together in the path
    generated = obj1.url()
    assert "bad" in generated
    assert "0" in generated
    result = NotifyHumHub.parse_url(generated)
    obj2 = NotifyHumHub(**result)
    # obj2 re-validates: valid target "5" survives, invalid ones re-land in
    # _invalid_targets so the overall target count is the same
    assert len(obj2.targets) == 1


def test_plugin_humhub_url_parsing():
    """NotifyHumHub() parse_url edge cases."""

    # Bearer token from path and ?to= combined
    result = NotifyHumHub.parse_url("humhubs://mytoken@hostname/1/?to=2,3")
    assert result is not None
    assert "1" in result["targets"]
    assert "2" in result["targets"]
    assert "3" in result["targets"]

    # Basic auth
    result = NotifyHumHub.parse_url("humhubs://user:pass@hostname/42")
    assert result is not None
    assert result["user"] == "user"
    assert result["password"] == "pass"
    assert "42" in result["targets"]

    # Empty / invalid URL returns None (no host)
    assert NotifyHumHub.parse_url("humhubs://") is None
    # Only host, no user -- parse_url succeeds; TypeError raised at init
    result = NotifyHumHub.parse_url("humhubs://hostname/1")
    assert result is not None


def test_plugin_humhub_privacy_url():
    """NotifyHumHub() privacy URL masking."""

    obj = NotifyHumHub(user="secrettoken", host="myhost", targets=["1"])
    priv = obj.url(privacy=True)
    assert "secrettoken" not in priv
    assert "myhost" in priv

    obj2 = NotifyHumHub(
        user="admin", password="topsecret", host="myhost", targets=["1"]
    )
    priv2 = obj2.url(privacy=True)
    assert "topsecret" not in priv2
    assert "admin" not in priv2 or "****" in priv2


@mock.patch("requests.post")
def test_plugin_humhub_apprise_integration(mock_post):
    """NotifyHumHub() Apprise integration."""

    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = b""

    aobj = Apprise()
    assert aobj.add("humhubs://mytoken@localhost/1")
    assert aobj.notify(title="Title", body="Body") is True

    aobj2 = Apprise()
    assert aobj2.add("humhubs://user:pass@localhost/1")
    assert aobj2.notify(title="Title", body="Body") is True


@mock.patch("requests.post")
def test_plugin_humhub_attachment_success(mock_post):
    """NotifyHumHub() attachment upload success."""
    from io import BytesIO

    # First response: post creation with a post ID
    create_resp = requests.Request()
    create_resp.status_code = requests.codes.ok
    create_resp.content = b'{"id": 42}'

    # Second response: attachment upload success
    upload_resp = requests.Request()
    upload_resp.status_code = requests.codes.ok
    upload_resp.content = b"{}"

    mock_post.side_effect = [create_resp, upload_resp]

    # Build a mock accessible attachment
    attachment = mock.MagicMock()
    attachment.__bool__ = mock.MagicMock(return_value=True)
    attachment.name = "test.png"
    attachment.open = mock.MagicMock(return_value=BytesIO(b"image data"))

    obj = NotifyHumHub(user="token", host="localhost", targets=["1"])
    assert obj.send(body="Test body", attach=[attachment]) is True
    # Post creation + file upload
    assert mock_post.call_count == 2


@mock.patch("requests.post")
def test_plugin_humhub_attachment_multiple(mock_post):
    """NotifyHumHub() multiple attachments all uploaded."""
    from io import BytesIO

    # Post creation returns a post ID
    create_resp = requests.Request()
    create_resp.status_code = requests.codes.ok
    create_resp.content = b'{"id": 10}'

    # Three attachment upload responses
    upload_resp = requests.Request()
    upload_resp.status_code = requests.codes.ok
    upload_resp.content = b"{}"

    mock_post.side_effect = [
        create_resp,
        upload_resp,
        upload_resp,
        upload_resp,
    ]

    def make_attach(name):
        """Build a mock accessible attachment."""
        a = mock.MagicMock()
        a.__bool__ = mock.MagicMock(return_value=True)
        a.name = name
        a.open = mock.MagicMock(return_value=BytesIO(b"data"))
        return a

    attachments = [
        make_attach("a.png"),
        make_attach("b.png"),
        make_attach("c.png"),
    ]

    obj = NotifyHumHub(user="token", host="localhost", targets=["1"])
    assert obj.send(body="msg", attach=attachments) is True
    # 1 creation + 3 uploads
    assert mock_post.call_count == 4


@mock.patch("requests.post")
def test_plugin_humhub_attachment_inaccessible(mock_post):
    """NotifyHumHub() inaccessible attachment marks failure."""

    # Post creation succeeds with a post ID
    create_resp = requests.Request()
    create_resp.status_code = requests.codes.ok
    create_resp.content = b'{"id": 7}'
    mock_post.return_value = create_resp

    # Build a mock inaccessible attachment (falsy)
    attachment = mock.MagicMock()
    attachment.__bool__ = mock.MagicMock(return_value=False)
    attachment.url = mock.MagicMock(return_value="file:///tmp/missing")

    obj = NotifyHumHub(user="token", host="localhost", targets=["1"])
    assert obj.send(body="msg", attach=[attachment]) is False
    # Only the post creation call was made; upload skipped
    assert mock_post.call_count == 1


@mock.patch("requests.post")
def test_plugin_humhub_attachment_no_post_id(mock_post):
    """NotifyHumHub() handles missing post ID in creation response."""

    # Post creation returns 200 but no "id" field in the response body
    create_resp = requests.Request()
    create_resp.status_code = requests.codes.ok
    create_resp.content = b"{}"
    mock_post.return_value = create_resp

    attachment = mock.MagicMock()
    attachment.__bool__ = mock.MagicMock(return_value=True)

    obj = NotifyHumHub(user="token", host="localhost", targets=["1"])
    assert obj.send(body="msg", attach=[attachment]) is False
    # Only the post creation call was made; no upload attempted
    assert mock_post.call_count == 1


@mock.patch("requests.post")
def test_plugin_humhub_attachment_bad_json_response(mock_post):
    """NotifyHumHub() handles unparseable post creation response."""

    # Post creation returns 200 but a non-JSON body
    create_resp = requests.Request()
    create_resp.status_code = requests.codes.ok
    create_resp.content = b"not json"
    mock_post.return_value = create_resp

    attachment = mock.MagicMock()
    attachment.__bool__ = mock.MagicMock(return_value=True)

    obj = NotifyHumHub(user="token", host="localhost", targets=["1"])
    assert obj.send(body="msg", attach=[attachment]) is False
    assert mock_post.call_count == 1


@mock.patch("requests.post")
def test_plugin_humhub_attachment_upload_failure(mock_post):
    """NotifyHumHub() attachment upload HTTP failure."""
    from io import BytesIO

    # Post creation succeeds
    create_resp = requests.Request()
    create_resp.status_code = requests.codes.ok
    create_resp.content = b'{"id": 3}'

    # Attachment upload returns HTTP 500
    upload_resp = requests.Request()
    upload_resp.status_code = requests.codes.internal_server_error
    upload_resp.content = b"error"

    mock_post.side_effect = [create_resp, upload_resp]

    attachment = mock.MagicMock()
    attachment.__bool__ = mock.MagicMock(return_value=True)
    attachment.name = "report.pdf"
    attachment.open = mock.MagicMock(return_value=BytesIO(b"pdf data"))

    obj = NotifyHumHub(user="token", host="localhost", targets=["1"])
    assert obj.send(body="msg", attach=[attachment]) is False
    assert mock_post.call_count == 2


@mock.patch("requests.post")
def test_plugin_humhub_attachment_request_exception(mock_post):
    """NotifyHumHub() RequestException during attachment upload."""
    from io import BytesIO

    # Post creation succeeds
    create_resp = requests.Request()
    create_resp.status_code = requests.codes.ok
    create_resp.content = b'{"id": 5}'

    # Upload raises RequestException
    mock_post.side_effect = [
        create_resp,
        requests.RequestException("Connection refused"),
    ]

    attachment = mock.MagicMock()
    attachment.__bool__ = mock.MagicMock(return_value=True)
    attachment.name = "file.txt"
    attachment.open = mock.MagicMock(return_value=BytesIO(b"text data"))

    obj = NotifyHumHub(user="token", host="localhost", targets=["1"])
    assert obj.send(body="msg", attach=[attachment]) is False


@mock.patch("requests.post")
def test_plugin_humhub_attachment_oserror(mock_post):
    """NotifyHumHub() OSError when opening attachment file."""

    # Post creation succeeds
    create_resp = requests.Request()
    create_resp.status_code = requests.codes.ok
    create_resp.content = b'{"id": 8}'
    mock_post.return_value = create_resp

    # Attachment open() raises OSError before requests.post is reached
    attachment = mock.MagicMock()
    attachment.__bool__ = mock.MagicMock(return_value=True)
    attachment.name = "secret.key"
    attachment.open = mock.MagicMock(side_effect=OSError("Permission denied"))

    obj = NotifyHumHub(user="token", host="localhost", targets=["1"])
    assert obj.send(body="msg", attach=[attachment]) is False
    # OSError fires inside _send() before requests.post; only creation hit
    assert mock_post.call_count == 1
