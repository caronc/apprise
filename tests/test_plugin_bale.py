# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2026, AryanZeynali
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

from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

import apprise
from apprise.common import NotifyType
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.bale import NotifyBale

BOT_ID = "123456"
TOKEN_SECRET = "s" * 16
CHAT_ID = "987654321"
GROUP_CHAT_ID = "-987654321"
URL = f"bale://{BOT_ID}:{TOKEN_SECRET}@{CHAT_ID}"
ENDPOINT = f"https://tapi.bale.ai/bot{BOT_ID}:{TOKEN_SECRET}/sendMessage"


apprise_url_tests = (
    (
        URL,
        {
            "instance": NotifyBale,
            "notify_response": False,
            "requests_response_code": requests.codes.ok,
            "privacy_url": f"bale://{BOT_ID}:****@{CHAT_ID}",
        },
    ),
    (
        f"bale://{BOT_ID}:{TOKEN_SECRET}@{GROUP_CHAT_ID}",
        {
            "instance": NotifyBale,
            "notify_response": False,
            "requests_response_code": requests.codes.ok,
            "privacy_url": f"bale://{BOT_ID}:****@{GROUP_CHAT_ID}",
        },
    ),
    (
        f"bale://{BOT_ID}@{CHAT_ID}",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"bale://bot-id:secret@{CHAT_ID}",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"bale://:secret@{CHAT_ID}",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"bale://{BOT_ID}:secret@not-a-chat",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
)


def test_plugin_bale_urls():
    """NotifyBale() Apprise URLs."""
    AppriseURLTester(tests=apprise_url_tests).run_all()


@pytest.mark.parametrize(
    ("title", "expected_text"),
    (
        ("Alert", "Alert\nbody"),
        ("", "body"),
    ),
)
@mock.patch("apprise.plugins.bale.requests.post")
def test_plugin_bale_send_message(mock_post, title, expected_text):
    """Send a titled or untitled message to Bale."""
    response = mock.Mock(status_code=requests.codes.ok)
    response.json.return_value = {"ok": True}
    mock_post.return_value = response

    obj = apprise.Apprise.instantiate(URL)
    assert obj is not None
    assert obj.notify(
        body="body",
        title=title,
        notify_type=NotifyType.INFO,
    )
    mock_post.assert_called_once_with(
        ENDPOINT,
        data={"chat_id": CHAT_ID, "text": expected_text},
        verify=True,
        timeout=(15.0, 15.0),
        allow_redirects=False,
    )


@pytest.mark.parametrize(
    ("title", "body_length", "overflow"),
    (
        ("", 4097, "split"),
        ("", 4097, "truncate"),
        ("Alert", 4091, "split"),
        ("Alert", 4091, "truncate"),
    ),
)
@mock.patch("apprise.plugins.bale.requests.post")
def test_plugin_bale_message_limit(mock_post, title, body_length, overflow):
    """Respect Bale's 4096-character text limit for overflow modes."""
    response = mock.Mock(status_code=requests.codes.ok)
    response.json.return_value = {"ok": True}
    mock_post.return_value = response

    body = "x" * body_length
    obj = apprise.Apprise.instantiate(f"{URL}?overflow={overflow}")
    assert obj is not None
    assert obj.notify(body=body, title=title)

    texts = [call.kwargs["data"]["text"] for call in mock_post.call_args_list]
    assert texts
    assert all(len(text) <= 4096 for text in texts)
    if overflow == "truncate":
        assert len(texts) == 1
    else:
        assert len(texts) == 2
        if title:
            chunks = []
            for index, text in enumerate(texts, start=1):
                header, chunk = text.split("\n", 1)
                assert header == f"{title} [{index}/{len(texts)}]"
                chunks.append(chunk)
            assert "".join(chunks) == body
        else:
            assert "".join(texts) == body


@pytest.mark.parametrize(
    ("title_length", "body_length", "overflow"),
    (
        (250, 3846, "split"),
        (250, 3846, "truncate"),
        (249, 3847, "split"),
    ),
)
@mock.patch("apprise.plugins.bale.requests.post")
def test_plugin_bale_long_title_message_limit(
    mock_post, title_length, body_length, overflow
):
    """Keep long titles and split counters within Bale's text limit."""
    response = mock.Mock(status_code=requests.codes.ok)
    response.json.return_value = {"ok": True}
    mock_post.return_value = response

    title = "T" * title_length
    body = "x" * body_length
    obj = apprise.Apprise.instantiate(f"{URL}?overflow={overflow}")
    assert obj is not None
    assert obj.notify(body=body, title=title)

    texts = [call.kwargs["data"]["text"] for call in mock_post.call_args_list]
    assert texts
    assert all(len(text) <= 4096 for text in texts)
    if overflow == "split":
        assert len(texts) == 2
        chunks = []
        for index, text in enumerate(texts, start=1):
            header, chunk = text.split("\n", 1)
            assert header == f"{title[:244]} [{index}/{len(texts)}]"
            chunks.append(chunk)
        assert "".join(chunks) == body
    else:
        assert len(texts) == 1
        assert texts[0] == f"{title}\n{body[:3845]}"


@mock.patch("apprise.plugins.bale.requests.post")
@pytest.mark.parametrize(
    ("status_code", "payload", "json_error"),
    (
        (requests.codes.ok, {"ok": False}, None),
        (requests.codes.internal_server_error, None, None),
        (
            requests.codes.ok,
            None,
            ValueError(f"{TOKEN_SECRET} private response body"),
        ),
    ),
)
def test_plugin_bale_rejects_failed_responses(
    mock_post, status_code, payload, json_error
):
    """Reject HTTP, API, and malformed JSON responses."""
    response = mock.Mock(status_code=status_code)
    if json_error is None:
        response.json.return_value = payload
    else:
        response.json.side_effect = json_error
    mock_post.return_value = response

    obj = apprise.Apprise.instantiate(URL)
    assert obj is not None
    marker = "PRIVATE-BALE-MARKER"
    with mock.patch.multiple(
        obj.logger, warning=mock.DEFAULT, debug=mock.DEFAULT
    ) as logged_calls:
        assert not obj.notify(body=marker)
        logged = repr(logged_calls["warning"].call_args_list) + repr(
            logged_calls["debug"].call_args_list
        )

    assert marker not in logged
    assert TOKEN_SECRET not in logged


@mock.patch("apprise.plugins.bale.requests.post")
def test_plugin_bale_hides_request_exception_details(mock_post):
    """Do not log credentials, message text, or exception details."""
    marker = "PRIVATE-BALE-MARKER"
    mock_post.side_effect = requests.ConnectionError(marker)

    obj = apprise.Apprise.instantiate(URL)
    assert obj is not None
    with mock.patch.multiple(
        obj.logger, warning=mock.DEFAULT, debug=mock.DEFAULT
    ) as logged_calls:
        assert not obj.notify(body=marker)
        logged = repr(logged_calls["warning"].call_args_list) + repr(
            logged_calls["debug"].call_args_list
        )

    assert marker not in logged
    assert TOKEN_SECRET not in logged
