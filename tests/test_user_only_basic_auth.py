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

"""A URL with a user and no password must not send the password "None"."""

import base64
import io
from unittest import mock

import pytest
import requests

from apprise import Apprise
from apprise.attachment.http import AttachHTTP
from apprise.config.http import ConfigHTTP

# User only URLs, in the forms the plugin templates and README document
USER_ONLY_URLS = (
    "json://tok@localhost",
    "form://tok@localhost",
    "xml://tok@localhost",
    "kodi://tok@localhost",
    "enigma2://tok@localhost",
    "hassio://tok@localhost/accesstoken",
    "signal://tok@localhost/+15551234567/+15557654321",
    "ntfy://tok@localhost/topic",
    "apprise://tok@localhost/apikey",
    "bark://tok@localhost/devicekey",
    "synology://tok@localhost/token",
    "gorush://tok@localhost/device",
    "notica://tok@localhost/token",
)


def _reply(*args, **kwargs):
    """Stand in for the server: a real response, no network."""
    response = requests.Response()
    response.status_code = requests.codes.ok
    response._content = b"{}"
    response.raw = io.BytesIO(b"{}")
    return response


@pytest.mark.parametrize("url", USER_ONLY_URLS)
def test_user_only_auth_header(url):
    """The Authorization header carries 'tok:' and never 'tok:None'."""
    with mock.patch("requests.Session.send", side_effect=_reply) as send:
        obj = Apprise.instantiate(url)
        assert obj is not None
        obj.notify(body="body", title="title")

    assert send.call_count >= 1
    for call in send.call_args_list:
        header = call.args[0].headers["Authorization"]
        assert header == "Basic " + base64.b64encode(b"tok:").decode()


def test_config_http_user_only_auth_header():
    """Configuration over HTTP does the same."""
    with mock.patch("requests.Session.send", side_effect=_reply) as send:
        obj = ConfigHTTP(**ConfigHTTP.parse_url("http://tok@localhost/cfg"))
        obj.read()

    header = send.call_args.args[0].headers["Authorization"]
    assert header == "Basic " + base64.b64encode(b"tok:").decode()


def test_attachment_http_user_only_auth_header():
    """Attachments over HTTP do the same."""
    with mock.patch("requests.Session.send", side_effect=_reply) as send:
        obj = AttachHTTP(**AttachHTTP.parse_url("http://tok@localhost/a.txt"))
        assert obj.download()

    header = send.call_args.args[0].headers["Authorization"]
    assert header == "Basic " + base64.b64encode(b"tok:").decode()
