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

"""Basic auth follows RFC 7617 for every user and password combination."""

import base64
import io
from typing import Optional
from unittest import mock

import pytest
import requests

from apprise import Apprise
from apprise.attachment.http import AttachHTTP
from apprise.config.http import ConfigHTTP

# Plugin URLs that support Basic auth, with {auth} where credentials go
PLUGIN_URLS = (
    "json://{auth}localhost",
    "form://{auth}localhost",
    "xml://{auth}localhost",
    "kodi://{auth}localhost",
    "enigma2://{auth}localhost",
    "hassio://{auth}localhost/accesstoken",
    "signal://{auth}localhost/+15551234567/+15557654321",
    "ntfy://{auth}localhost/topic",
    "apprise://{auth}localhost/apikey",
    "bark://{auth}localhost/devicekey",
    "synology://{auth}localhost/token",
    "gorush://{auth}localhost/device",
    "notica://{auth}localhost/token",
)

# Credentials as written in a URL, and what Basic auth must carry
AUTH_FORMS = (
    ("tok:secret@", b"tok:secret"),
    ("tok@", b"tok:"),
    ("tok:@", b"tok:"),
    (":secret@", b":secret"),
    ("", None),
)


def _reply(*args, **kwargs):
    """Stand in for the server: a real response, no network."""
    response = requests.Response()
    response.status_code = requests.codes.ok
    response._content = b"{}"
    response.raw = io.BytesIO(b"{}")
    return response


def _basic(credentials: Optional[bytes]) -> Optional[str]:
    """Return the Basic header for ``credentials``, or None without any."""
    if credentials is None:
        return None
    return "Basic " + base64.b64encode(credentials).decode()


def _sent(call, *args):
    """Run ``call`` and return every Authorization header it sent."""
    with mock.patch("requests.Session.send", side_effect=_reply) as send:
        call(*args)

    assert send.call_count >= 1
    return {
        c.args[0].headers.get("Authorization") for c in send.call_args_list
    }


@pytest.mark.parametrize("template", PLUGIN_URLS)
@pytest.mark.parametrize(("auth", "credentials"), AUTH_FORMS)
def test_basic_auth_plugins(template, auth, credentials):
    """Each credential form sends the right header, before and after url()."""
    expected = _basic(credentials)
    if template.startswith("hassio://") and auth[:1] in ("", ":"):
        # Without a user, Home Assistant keeps its access token
        expected = "Bearer accesstoken"

    obj = Apprise.instantiate(template.format(auth=auth))
    assert obj is not None
    assert _sent(obj.notify, "body") == {expected}

    # The URL Apprise writes back sends the same header
    obj = Apprise.instantiate(obj.url())
    assert obj is not None
    assert _sent(obj.notify, "body") == {expected}


@pytest.mark.parametrize(("auth", "credentials"), AUTH_FORMS)
def test_basic_auth_config_http(auth, credentials):
    """Configuration over HTTP sends the same headers."""
    obj = ConfigHTTP(**ConfigHTTP.parse_url(f"http://{auth}localhost/cfg"))
    assert _sent(obj.read) == {_basic(credentials)}

    # The URL Apprise writes back sends the same header
    obj = ConfigHTTP(**ConfigHTTP.parse_url(obj.url()))
    assert _sent(obj.read) == {_basic(credentials)}


@pytest.mark.parametrize(("auth", "credentials"), AUTH_FORMS)
def test_basic_auth_attach_http(auth, credentials):
    """Attachments over HTTP send the same headers."""
    obj = AttachHTTP(**AttachHTTP.parse_url(f"http://{auth}localhost/a.txt"))
    assert _sent(obj.download) == {_basic(credentials)}

    # The URL Apprise writes back keeps the same credentials, where an
    # empty password is simply left out
    prefix = "http://" + auth.replace(":@", "@") + "localhost/"
    assert obj.url().startswith(prefix)
