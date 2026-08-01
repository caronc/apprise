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
import base64
import json
import logging
import re
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, NotifyFormat
import apprise.plugins.bark as bark_module
from apprise.plugins.bark import NotifyBark

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "bark://",
        {
            # No no host
            "instance": None,
        },
    ),
    (
        "bark://:@/",
        {
            # just invalid all around
            "instance": None,
        },
    ),
    (
        "bark://localhost",
        {
            # No Device Key specified
            "instance": NotifyBark,
            # Expected notify() response False (because we won't be able
            # to actually notify anything if no device_key was specified
            "notify_response": False,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key",
        {
            # Everything is okay
            "instance": NotifyBark,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "bark://192.168.0.6:8081/",
        },
    ),
    (
        "bark://user@192.168.0.6:8081/device_key",
        {
            # Everything is okay (test with user)
            "instance": NotifyBark,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "bark://user@192.168.0.6:8081/",
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?sound=invalid",
        {
            # bad sound, but we go ahead anyway
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?sound=alarm",
        {
            # alarm.caf sound loaded
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?sound=NOiR.cAf",
        {
            # noir.caf sound loaded
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?badge=100",
        {
            # set badge
            "instance": NotifyBark,
        },
    ),
    (
        "barks://192.168.0.6:8081/device_key/?badge=invalid",
        {
            # set invalid badge
            "instance": NotifyBark,
        },
    ),
    (
        "barks://192.168.0.6:8081/device_key/?badge=-12",
        {
            # set invalid badge
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?category=apprise",
        {
            # set category
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?image=no",
        {
            # do not display image
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?group=apprise",
        {
            # set group
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?level=invalid",
        {
            # bad level, but we go ahead anyway
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/?to=device_key",
        {
            # test use of to= argument
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?click=http://localhost",
        {
            # Our click link
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?level=active",
        {
            # active level
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?level=critical",
        {
            # critical level
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?level=critical&volume=10",
        {
            # critical level with volume 10
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?level=critical&volume=invalid",
        {
            # critical level with invalid volume
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?level=critical&volume=11",
        {
            # volume > 10
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?level=critical&volume=-1",
        {
            # volume < 0
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?level=critical&volume=",
        {
            # volume None
            "instance": NotifyBark,
        },
    ),
    (
        "bark://user:pass@192.168.0.5:8086/device_key/device_key2/",
        {
            # Everything is okay
            "instance": NotifyBark,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "bark://user:****@192.168.0.5:8086/",
        },
    ),
    (
        "barks://192.168.0.7/device_key/",
        {
            "instance": NotifyBark,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "barks://192.168.0.7/****",
        },
    ),
    (
        "bark://192.168.0.7/device_key",
        {
            "instance": NotifyBark,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?icon=https://example.com/icon.png",
        {
            # set custom icon
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?icon=https://example.com/icon.png&image=no",
        {
            # set custom icon and disable default image
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?call=1",
        {
            # set call parameter to repeat ringtone
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?call=1&sound=alarm&level=critical",
        {
            # set call parameter with other parameters
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?format=markdown",
        {
            # enable markdown mode via global format parameter
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?format=text",
        {
            # explicitly set text format (default behavior)
            "instance": NotifyBark,
        },
    ),
)


def test_plugin_bark_urls():
    """NotifyBark() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_bark_html_to_markdown_format(mock_post):
    """NotifyBark(): HTML body is converted to Markdown."""

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    # Load via Apprise URL with markdown format enabled
    aobj = Apprise()
    assert aobj.add("bark://192.168.0.6:8081/device_key/?format=markdown")

    # Notify with an HTML body; the framework converts it to Markdown
    # before dispatching to the Bark plugin
    assert (
        aobj.notify(
            body="<b>hello</b> <i>world</i>",
            body_format=NotifyFormat.HTML,
        )
        is True
    )
    assert mock_post.call_count == 1

    # The body must arrive as Markdown, not stripped plain text
    payload = json.loads(mock_post.call_args_list[0][1]["data"])
    assert payload["markdown"] == "**hello** *world*"


@pytest.mark.parametrize(
    ("key", "expected_ciphertext"),
    (
        (
            "k" * 16,
            "M31imDGJqdEEszZWcWfgiMTooJniyhmvnRIIrUSrWDVi3FxcD9cl1Dyre2wQ8a5I2bhFyBrGPeMEwp1+Uw==",
        ),
        (
            "k" * 24,
            "QyuvztP2Yktq2khUWXw6hYrjLnhuc+kC44lyGOaVYBRJC4vsYaB6RewayvX+4ZKjUUIifRWDtIiVFq/KgA==",
        ),
        (
            "k" * 32,
            "a9CkBbe9d0qkskyAzKyb4pV/WjH6D1J/JLm0EOUTMcoTpJEs10gqANkkLKaOPqVXL0yo0AaxElYjmLmynw==",
        ),
    ),
)
def test_plugin_bark_aesgcm_wire_format(
    key,
    expected_ciphertext,
    monkeypatch,
):
    """NotifyBark() matches Bark's AES-GCM combined wire format."""
    pytest.importorskip("cryptography")
    monkeypatch.setattr(
        bark_module.secrets,
        "token_urlsafe",
        lambda length: "fixed-iv-123",
    )
    instance = NotifyBark(
        host="localhost",
        targets=("device-key",),
        secure=True,
        encryption_key=key,
    )

    ciphertext, iv = instance._encrypt_payload(
        {"body": "Encrypted weather", "level": "active"}
    )

    assert iv == "fixed-iv-123"
    assert ciphertext == expected_ciphertext


@pytest.mark.parametrize(
    "key",
    (
        pytest.param("short", id="too-short"),
        pytest.param("k" * 17, id="unsupported-length"),
        pytest.param("🔒" * 16, id="non-ascii-unicode-probe"),
        pytest.param(b"k" * 16, id="non-string"),
    ),
)
def test_plugin_bark_rejects_invalid_encryption_keys(key):
    """NotifyBark() rejects keys Bark cannot use as raw AES keys."""
    with pytest.raises(TypeError, match="Bark encryption key"):
        NotifyBark(
            host="localhost",
            targets=("device-key",),
            secure=True,
            encryption_key=key,
        )


def test_plugin_bark_encryption_fails_closed_without_cryptography(monkeypatch):
    """NotifyBark() never downgrades requested encryption to plaintext."""
    monkeypatch.setattr(bark_module, "BARK_AESGCM_SUPPORT", False)

    with pytest.raises(TypeError, match="requires the 'cryptography' package"):
        NotifyBark(
            host="localhost",
            targets=("device-key",),
            secure=True,
            encryption_key="k" * 32,
        )

    instance = NotifyBark(
        host="localhost",
        targets=("device-key",),
        secure=True,
    )
    assert instance.encryption_key is None


def test_plugin_bark_encryption_url_roundtrip_and_privacy():
    """NotifyBark() preserves encryption config without exposing secrets."""
    pytest.importorskip("cryptography")
    device_key = "private-device-key"
    encryption_key = "k" * 32
    instance = NotifyBark(
        host="localhost",
        targets=(device_key,),
        secure=True,
        encryption_key=encryption_key,
    )

    generated_url = instance.url(privacy=False)
    assert device_key in generated_url
    assert encryption_key in generated_url

    private_url = instance.url(privacy=True)
    assert device_key not in private_url
    assert encryption_key not in private_url
    assert private_url.startswith("barks://localhost/****?")
    assert "key=" in private_url

    parsed = NotifyBark.parse_url(generated_url)
    rebuilt = NotifyBark(**parsed)
    assert rebuilt.encryption_key == encryption_key
    assert rebuilt.targets == [device_key]
    assert rebuilt.url_identifier == instance.url_identifier

    different_key = NotifyBark(
        host="localhost",
        targets=(device_key,),
        secure=True,
        encryption_key="x" * 32,
    )
    assert different_key.url_identifier != instance.url_identifier


@mock.patch("requests.post")
def test_plugin_bark_encrypts_complete_payload_with_fresh_iv_per_target(
    mock_post,
    monkeypatch,
):
    """NotifyBark() encrypts all parameters and rotates IVs per request."""
    aesgcm = pytest.importorskip(
        "cryptography.hazmat.primitives.ciphers.aead"
    ).AESGCM
    generated_ivs = iter(("abcdefghijkl", "mnopqrstuvwx"))
    token_urlsafe = mock.Mock(side_effect=lambda length: next(generated_ivs))
    monkeypatch.setattr(
        bark_module.secrets,
        "token_urlsafe",
        token_urlsafe,
    )
    response = mock.Mock()
    response.status_code = requests.codes.ok
    mock_post.return_value = response
    key = "k" * 32
    private_body = "Private encrypted body"
    private_title = "Private encrypted title"
    targets = ("private-device-one", "private-device-two")
    instance = NotifyBark(
        host="localhost",
        targets=targets,
        secure=True,
        encryption_key=key,
        include_image=False,
        sound="alarm",
        category="private-category",
        group="private-group",
        level="active",
        click="https://private.example.invalid",
        badge=3,
        volume=4,
        icon="https://private.example.invalid/icon.png",
        call=True,
    )
    instance.logger = mock.Mock()

    assert instance.send(body=private_body, title=private_title) is True
    assert mock_post.call_count == 2

    request_payloads = [
        json.loads(call.kwargs["data"]) for call in mock_post.call_args_list
    ]
    assert {payload["device_key"] for payload in request_payloads} == set(
        targets
    )
    assert [payload["iv"] for payload in request_payloads] == [
        "abcdefghijkl",
        "mnopqrstuvwx",
    ]
    assert token_urlsafe.call_args_list == [
        mock.call(bark_module.BARK_GCM_IV_RANDOM_BYTES),
        mock.call(bark_module.BARK_GCM_IV_RANDOM_BYTES),
    ]
    assert all(
        re.fullmatch(r"[A-Za-z0-9_-]{12}", payload["iv"])
        for payload in request_payloads
    )
    assert all(
        set(payload) == {"device_key", "ciphertext", "iv"}
        for payload in request_payloads
    )

    expected_parameters = {
        "title": private_title,
        "body": private_body,
        "sound": "alarm.caf",
        "url": "https://private.example.invalid",
        "badge": 3,
        "level": "active",
        "category": "private-category",
        "group": "private-group",
        "volume": 4,
        "icon": "https://private.example.invalid/icon.png",
        "call": 1,
    }
    for request_payload in request_payloads:
        plaintext = aesgcm(key.encode("ascii")).decrypt(
            request_payload["iv"].encode("ascii"),
            base64.b64decode(request_payload["ciphertext"]),
            None,
        )
        assert json.loads(plaintext) == expected_parameters

    logged = repr(instance.logger.method_calls)
    for private_value in (
        key,
        private_body,
        private_title,
        *targets,
        "private-category",
        "private-group",
        "private.example.invalid",
    ):
        assert private_value not in logged


@mock.patch("requests.post")
def test_plugin_bark_encrypts_markdown_payload(mock_post, monkeypatch):
    """NotifyBark() encrypts Markdown and does not add a plaintext body."""
    aesgcm = pytest.importorskip(
        "cryptography.hazmat.primitives.ciphers.aead"
    ).AESGCM
    monkeypatch.setattr(
        bark_module.secrets,
        "token_urlsafe",
        lambda length: "fixed-iv-123",
    )
    response = mock.Mock()
    response.status_code = requests.codes.ok
    mock_post.return_value = response
    key = "k" * 32
    instance = NotifyBark(
        host="localhost",
        targets=("device-key",),
        secure=True,
        encryption_key=key,
        include_image=False,
        format=NotifyFormat.MARKDOWN,
    )

    assert instance.send(body="**encrypted**", title="Title") is True

    request_payload = json.loads(mock_post.call_args.kwargs["data"])
    plaintext = aesgcm(key.encode("ascii")).decrypt(
        request_payload["iv"].encode("ascii"),
        base64.b64decode(request_payload["ciphertext"]),
        None,
    )
    assert json.loads(plaintext) == {
        "title": "Title",
        "markdown": "**encrypted**",
    }


@mock.patch("requests.post")
def test_plugin_bark_rotates_iv_across_repeated_sends(
    mock_post,
    monkeypatch,
):
    """NotifyBark() generates a fresh IV for every repeated request."""
    pytest.importorskip("cryptography")
    generated_ivs = iter(("abcdefghijkl", "mnopqrstuvwx"))
    monkeypatch.setattr(
        bark_module.secrets,
        "token_urlsafe",
        lambda length: next(generated_ivs),
    )
    response = mock.Mock()
    response.status_code = requests.codes.ok
    mock_post.return_value = response
    instance = NotifyBark(
        host="localhost",
        targets=("device-key",),
        secure=True,
        encryption_key="k" * 32,
        include_image=False,
    )

    assert instance.send(body="same body", title="same title") is True
    assert instance.send(body="same body", title="same title") is True

    payloads = [
        json.loads(call.kwargs["data"]) for call in mock_post.call_args_list
    ]
    assert [payload["iv"] for payload in payloads] == [
        "abcdefghijkl",
        "mnopqrstuvwx",
    ]
    assert payloads[0]["ciphertext"] != payloads[1]["ciphertext"]


def test_plugin_bark_rejects_incompatible_generated_iv(monkeypatch):
    """NotifyBark() rejects RNG output Bark cannot decrypt."""
    pytest.importorskip("cryptography")
    monkeypatch.setattr(
        bark_module.secrets,
        "token_urlsafe",
        lambda length: "too-short",
    )
    instance = NotifyBark(
        host="localhost",
        targets=("device-key",),
        secure=True,
        encryption_key="k" * 32,
    )

    with pytest.raises(ValueError, match="incompatible AES-GCM IV"):
        instance._encrypt_payload({"body": "private body"})


@mock.patch("requests.post")
def test_plugin_bark_encryption_failure_prevents_network_io(mock_post):
    """NotifyBark() fails closed when payload encryption fails."""
    pytest.importorskip("cryptography")
    instance = NotifyBark(
        host="localhost",
        targets=("private-device",),
        secure=True,
        encryption_key="k" * 32,
        include_image=False,
    )
    instance.logger = mock.Mock()
    instance._encrypt_payload = mock.Mock(
        side_effect=ValueError("private encryption detail")
    )

    assert instance.send(body="private body", title="private title") is False
    mock_post.assert_not_called()
    logged = repr(instance.logger.method_calls)
    assert "private encryption detail" not in logged
    assert "private body" not in logged
    assert "private title" not in logged
    assert "private-device" not in logged


@mock.patch("requests.post")
def test_plugin_bark_encrypted_send_http_error(mock_post, monkeypatch):
    """NotifyBark() suppresses response details when encrypted."""
    pytest.importorskip("cryptography")
    monkeypatch.setattr(
        bark_module.secrets,
        "token_urlsafe",
        lambda length: "fixed-iv-123",
    )
    response = mock.Mock()
    response.status_code = requests.codes.internal_server_error
    response.content = b"private response body"
    mock_post.return_value = response
    instance = NotifyBark(
        host="localhost",
        targets=("private-device",),
        secure=True,
        encryption_key="k" * 32,
        include_image=False,
    )
    instance.logger = mock.Mock()

    assert instance.send(body="private body", title="private title") is False
    # The encrypted request still went out; it's the server's response
    # that failed, not the encryption step
    assert mock_post.call_count == 1

    # A failure warning must still surface, just without the response
    # body attached to it
    instance.logger.warning.assert_called_once()
    logged = repr(instance.logger.method_calls)
    assert "private response body" not in logged
    assert "private body" not in logged
    assert "private title" not in logged
    assert "private-device" not in logged


@mock.patch("requests.post")
def test_plugin_bark_encrypted_send_connection_error(mock_post, monkeypatch):
    """NotifyBark() suppresses socket exception details when encrypted."""
    pytest.importorskip("cryptography")
    monkeypatch.setattr(
        bark_module.secrets,
        "token_urlsafe",
        lambda length: "fixed-iv-123",
    )
    mock_post.side_effect = requests.RequestException("private socket detail")
    instance = NotifyBark(
        host="localhost",
        targets=("private-device",),
        secure=True,
        encryption_key="k" * 32,
        include_image=False,
    )
    instance.logger = mock.Mock()

    assert instance.send(body="private body", title="private title") is False
    assert mock_post.call_count == 1

    # A failure warning must still surface, just without the raw
    # exception text attached to it
    instance.logger.warning.assert_called_once()
    logged = repr(instance.logger.method_calls)
    assert "private socket detail" not in logged
    assert "private body" not in logged
    assert "private title" not in logged
    assert "private-device" not in logged


def test_plugin_bark_runtime_dependencies():
    """NotifyBark() declares its optional cryptography dependency."""
    assert NotifyBark.runtime_deps() == ("cryptography",)
