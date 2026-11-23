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
import logging
from unittest import mock

import pytest
import requests

from apprise import Apprise
from apprise.attachment.http import AttachHTTP
from apprise.config.http import ConfigHTTP

logging.disable(logging.CRITICAL)

# User with no password, an explicit password, and an explicit empty one.
# A missing password must not be sent as the text "None".
_AUTH_URLS = (
    ("json://tok@host/path", ("tok", "")),
    ("json://tok:s3cret@host/path", ("tok", "s3cret")),
    ("json://tok:@host/path", ("tok", "")),
    ("jsons://tok@host/path", ("tok", "")),
    ("form://tok@host", ("tok", "")),
    ("form://tok:s3cret@host", ("tok", "s3cret")),
    ("xml://tok@host", ("tok", "")),
    ("xml://tok:s3cret@host", ("tok", "s3cret")),
    ("kodi://tok@host", ("tok", "")),
    ("kodi://tok:s3cret@host", ("tok", "s3cret")),
    ("enigma2://tok@host", ("tok", "")),
    ("enigma2://tok:s3cret@host", ("tok", "s3cret")),
    ("hassio://tok@host/accesstoken", ("tok", "")),
    ("hassio://tok:s3cret@host/accesstoken", ("tok", "s3cret")),
    ("signal://tok@host/11111111111/", ("tok", "")),
    ("signal://tok:s3cret@host/11111111111/", ("tok", "s3cret")),
    ("ntfy://tok@host/topic", ("tok", "")),
    ("ntfy://tok:s3cret@host/topic", ("tok", "s3cret")),
    ("apprise://tok@host/mytoken", ("tok", "")),
    ("apprise://tok:s3cret@host/mytoken", ("tok", "s3cret")),
    ("apprise://:s3cret@host/mytoken", ("", "s3cret")),
    ("bark://tok@host/device", ("tok", "")),
    ("bark://tok:s3cret@host/device", ("tok", "s3cret")),
    ("synology://tok@host/token", ("tok", "")),
    ("synology://tok:s3cret@host/token", ("tok", "s3cret")),
    ("gorush://tok@host/devtoken", ("tok", "")),
    ("gorush://tok:s3cret@host/devtoken", ("tok", "s3cret")),
    ("notica://tok@host/token", ("tok", "")),
    ("notica://tok:s3cret@host/token", ("tok", "s3cret")),
)


def _basic_credentials(auth):
    """Return the user:password bytes requests would put in Basic auth."""
    prepared = requests.Request("GET", "http://host/", auth=auth).prepare()
    token = prepared.headers["Authorization"].split(" ", 1)[1]
    return base64.b64decode(token)


def _ok_response():
    """A successful requests response the plugins will accept."""
    response = mock.Mock()
    response.status_code = requests.codes.ok
    # Enigma2 treats a reply without result=true as a failed send.
    response.content = b'{"result": true}'
    response.text = '{"result": true}'
    return response


def _sent_auth(*mocked):
    """Return the auth tuple from the first HTTP call that was made."""
    calls = [
        call
        for item in mocked
        if item.call_args_list
        for call in item.call_args_list
    ]
    assert calls, "no HTTP request was made"
    return calls[0][1]["auth"]


def _assert_basic_auth(sent, expected):
    """The tuple and the header requests would build must both match."""
    user, password = expected
    assert sent == expected
    assert _basic_credentials(sent) == f"{user}:{password}".encode()


@pytest.mark.parametrize(("url", "auth"), _AUTH_URLS)
@mock.patch("requests.request")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_user_only_basic_auth(mock_post, mock_get, mock_request, url, auth):
    """A user with no password is sent as an empty password, not 'None'."""
    for mocked in (mock_post, mock_get, mock_request):
        mocked.return_value = _ok_response()

    obj = Apprise.instantiate(url)
    assert obj is not None
    assert obj.notify(body="hi") is True

    _assert_basic_auth(_sent_auth(mock_post, mock_get, mock_request), auth)


class _Stream:
    """A small streamed body for HTTP config and attachment fetches."""

    status_code = requests.codes.ok
    headers = {
        "Content-Length": "4",
        "Content-Type": "text/plain",
    }
    encoding = "utf-8"
    text = "body"

    def iter_content(self, chunk_size=1, **kwargs):
        yield b"body"

    def raise_for_status(self):
        return None

    def close(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


@pytest.mark.parametrize(
    ("url", "auth"),
    [
        ("http://tok@host/file.txt", ("tok", "")),
        ("http://tok:s3cret@host/file.txt", ("tok", "s3cret")),
        ("http://tok:@host/file.txt", ("tok", "")),
    ],
)
@mock.patch("requests.Session.get")
def test_http_attachment_user_only_basic_auth(mock_get, url, auth):
    """HTTP attachments send an empty password when none was given."""
    mock_get.return_value = _Stream()

    parsed = AttachHTTP.parse_url(url)
    assert isinstance(parsed, dict)
    attachment = AttachHTTP(**parsed)
    assert attachment.download() is True

    _assert_basic_auth(mock_get.call_args[1]["auth"], auth)


@pytest.mark.parametrize(
    ("url", "auth"),
    [
        ("http://tok@host/apprise.yml", ("tok", "")),
        ("http://tok:s3cret@host/apprise.yml", ("tok", "s3cret")),
        ("http://tok:@host/apprise.yml", ("tok", "")),
        ("http://:s3cret@host/apprise.yml", ("", "s3cret")),
    ],
)
@mock.patch("requests.post")
def test_http_config_user_only_basic_auth(mock_post, url, auth):
    """HTTP configuration sends an empty password when none was given."""
    mock_post.return_value = _Stream()

    parsed = ConfigHTTP.parse_url(url)
    assert isinstance(parsed, dict)
    config = ConfigHTTP(**parsed)
    assert config.read() is not None

    _assert_basic_auth(mock_post.call_args[1]["auth"], auth)
