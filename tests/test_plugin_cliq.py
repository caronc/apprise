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

from apprise import Apprise, NotifyFormat, NotifyType
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.cliq import NotifyCliq

logging.disable(logging.CRITICAL)

# A realistic Webhook Token
TOKEN = (
    "1001.2798931fdf4905dc5d37806b47d8253a.2d73063dae2ccf4a04810ddb0a1b2c3d"
)

# Our Testing URLs
apprise_url_tests = (
    (
        "cliq://",
        {
            # No token specified
            "instance": TypeError,
        },
    ),
    (
        "cliq://invalid!token/general",
        {
            # An invalid token
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "cliq://{}".format(TOKEN),
        {
            # No channel or bot to notify
            "instance": NotifyCliq,
            "notify_response": False,
        },
    ),
    (
        "cliq://{}/general".format(TOKEN),
        {
            # A channel without its optional "#"
            "instance": NotifyCliq,
            "requests_response_code": requests.codes.no_content,
            "privacy_url": "cliq://1...d/%23general",
        },
    ),
    (
        "zcliq://Alerts@{}/%23general/@mybot".format(TOKEN),
        {
            # An alias schema, a bot name, a channel and a bot
            "instance": NotifyCliq,
            "privacy_url": "cliq://Alerts@1...d/",
        },
    ),
    (
        "zohocliq://?token={}&to=general,@mybot&botname=Alerts"
        "&region=eu&company=1234&image=no&broadcast=yes".format(TOKEN),
        {
            # Every option supplied as an argument
            "instance": NotifyCliq,
        },
    ),
    (
        "cliq://{}/general?region=mars".format(TOKEN),
        {
            # An invalid region
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "cliq://{}/general?company=bad!id".format(TOKEN),
        {
            # An invalid company
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "https://cliq.zoho.com/api/v2/channelsbyname/general/message"
        "?zapikey={}".format(TOKEN),
        {
            # A native channel webhook URL
            "instance": NotifyCliq,
        },
    ),
    (
        "cliq://{}/general".format(TOKEN),
        {
            "instance": NotifyCliq,
            # A failure has been returned by the server
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "cliq://{}/general".format(TOKEN),
        {
            "instance": NotifyCliq,
            # An unknown response code
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "cliq://{}/general".format(TOKEN),
        {
            "instance": NotifyCliq,
            # Socket errors are handled
            "test_requests_exceptions": True,
        },
    ),
)


def _mk_resp(code=requests.codes.ok):
    """Build a mocked Cliq response."""
    response = mock.Mock()
    response.status_code = code
    response.content = b""
    return response


def test_plugin_cliq_urls():
    """NotifyCliq() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_cliq_init():
    """NotifyCliq() validates its options and sorts its targets."""

    obj = NotifyCliq(
        token=TOKEN,
        targets=["#general", "ops", "@mybot", "bad!channel"],
        botname="  ",
        region=" EU ",
    )
    assert sorted(obj.targets) == ["#general", "#ops", "@mybot"]
    assert obj.invalid_targets == ["bad!channel"]
    assert obj.botname is None
    assert obj.region == "eu"
    assert obj.company is None
    assert len(obj) == 3

    # Invalid targets are kept in the URL so nothing is silently lost
    assert "bad%21channel" in obj.url()

    # Defaults apply when nothing else is given
    obj = NotifyCliq(token=TOKEN)
    assert obj.region == "us"
    assert obj.include_image is True
    assert obj.broadcast is False
    assert len(obj) == 1

    with pytest.raises(AppriseImproperlyConfigured):
        NotifyCliq(token=None)

    with pytest.raises(AppriseImproperlyConfigured):
        NotifyCliq(token=TOKEN, region="xx")

    with pytest.raises(AppriseImproperlyConfigured):
        NotifyCliq(token=TOKEN, company="no way")


def test_plugin_cliq_round_trip():
    """NotifyCliq() URLs survive being rebuilt from url()."""

    obj = Apprise.instantiate(
        "zcliq://My%20Bot@{}/general/@mybot?region=jp&company=99"
        "&image=no&broadcast=yes".format(TOKEN)
    )
    assert isinstance(obj, NotifyCliq)

    # Aliases are always written back using the main schema
    assert obj.url().startswith("cliq://My%20Bot@")

    obj2 = Apprise.instantiate(obj.url())
    assert isinstance(obj2, NotifyCliq)
    assert obj2.url_identifier == obj.url_identifier
    assert sorted(obj2.targets) == sorted(obj.targets)
    assert obj2.botname == "My Bot"
    assert obj2.region == "jp"
    assert obj2.company == "99"
    assert obj2.include_image is False
    assert obj2.broadcast is True

    # A different region is a different account
    obj3 = Apprise.instantiate(
        "cliq://{}/general?region=eu&company=99".format(TOKEN)
    )
    assert obj3.url_identifier != obj.url_identifier


def test_plugin_cliq_native_urls():
    """NotifyCliq() understands the webhook URLs Cliq hands out."""

    # A channel in the Australian data center for a specific company
    result = NotifyCliq.parse_native_url(
        "https://cliq.zoho.com.au/company/777/api/v2/channelsbyname/"
        "devops/message?zapikey={}".format(TOKEN)
    )
    assert result["token"] == TOKEN
    assert result["targets"] == ["#devops"]
    assert result["region"] == "au"
    assert result["company"] == "777"

    # A bot in the Canadian data center, with extra arguments around
    # the token
    result = NotifyCliq.parse_native_url(
        "https://cliq.zohocloud.ca/api/v2/bots/abot/message"
        "?a=b&zapikey={}&c=d".format(TOKEN)
    )
    assert result["token"] == TOKEN
    assert result["targets"] == ["@abot"]
    assert result["region"] == "ca"
    assert "company" not in result

    # A domain Cliq does not use
    assert (
        NotifyCliq.parse_native_url(
            "https://cliq.zoho.xyz/api/v2/channelsbyname/devops/message"
            "?zapikey={}".format(TOKEN)
        )
        is None
    )


@mock.patch("requests.post")
def test_plugin_cliq_payload(mock_post):
    """NotifyCliq() posts the message, card and sender details."""

    mock_post.return_value = _mk_resp(requests.codes.no_content)

    obj = Apprise.instantiate(
        "cliq://Alerts@{}/general/@mybot?region=eu&company=1234"
        "&broadcast=yes".format(TOKEN)
    )
    assert isinstance(obj, NotifyCliq)

    assert obj.notify(
        title="Disk & <db01>",
        body="Usage at **95%**",
        body_format=NotifyFormat.MARKDOWN,
        notify_type=NotifyType.WARNING,
    )

    # One post for each target
    assert mock_post.call_count == 2
    calls = {urlparse(c[0][0]).path: c for c in mock_post.call_args_list}

    # Both go to the European data center for the right company
    for call in calls.values():
        assert urlparse(call[0][0]).hostname == "cliq.zoho.eu"
        assert call[1]["params"] == {"zapikey": TOKEN}

    channel = calls["/company/1234/api/v2/channelsbyname/general/message"]
    bot = calls["/company/1234/api/v2/bots/mybot/message"]

    payload = json.loads(channel[1]["data"])
    assert payload["text"] == "Usage at *95%*"
    assert payload["card"] == {
        "title": "Disk & <db01>",
        "theme": "modern-inline",
    }
    assert payload["bot"]["name"] == "Alerts"
    assert payload["bot"]["image"].startswith("http")
    assert "broadcast" not in payload

    # Only bot messages are broadcast
    payload = json.loads(bot[1]["data"])
    assert payload["broadcast"] is True
    assert payload["text"] == "Usage at *95%*"

    # Without an image or bot name the sender is left alone
    mock_post.reset_mock()
    obj = NotifyCliq(token=TOKEN, targets="general", include_image=False)
    assert obj.notify(body="Hello")
    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload == {"text": "Hello"}
    url = mock_post.call_args[0][0]
    assert urlparse(url).hostname == "cliq.zoho.com"
    assert urlparse(url).path == "/api/v2/channelsbyname/general/message"

    # A bot name on its own still changes the sender
    mock_post.reset_mock()
    obj = NotifyCliq(
        token=TOKEN, targets="general", botname="Ops", include_image=False
    )
    assert obj.send(body="", title="Only a title")
    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload == {"text": "Only a title", "bot": {"name": "Ops"}}

    # The image alone uses the Apprise name
    mock_post.reset_mock()
    obj = NotifyCliq(token=TOKEN, targets="@mybot")
    assert obj.notify(body="Hello")
    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["bot"]["name"] == "Apprise"
    assert "broadcast" not in payload


@mock.patch("requests.post")
def test_plugin_cliq_partial_failure(mock_post):
    """NotifyCliq() keeps going when one target fails."""

    mock_post.side_effect = [
        _mk_resp(requests.codes.not_found),
        _mk_resp(),
    ]

    obj = NotifyCliq(token=TOKEN, targets=["#gone", "#general"])
    assert obj.notify(body="Hello") is False
    assert mock_post.call_count == 2


@mock.patch("requests.post")
def test_plugin_cliq_formats(mock_post):
    """NotifyCliq() turns Markdown into the Cliq formatting style."""

    mock_post.return_value = _mk_resp()
    obj = NotifyCliq(token=TOKEN, targets="general", include_image=False)

    # HTML is converted to Markdown and then into Cliq's style
    assert obj.notify(
        body='<b>bold</b> <i>it</i> <a href="https://x.com/a_b">l_ink</a>',
        body_format=NotifyFormat.HTML,
    )
    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["text"] == "*bold* _it_ [l_ink](https://x.com/a_b)"

    # Plain text reaches Cliq exactly as it was typed
    assert obj.notify(
        body="5 * 3 = a_b <tag> [x](y)",
        body_format=NotifyFormat.TEXT,
    )
    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["text"] == "5 * 3 = a_b <tag> [x](y)"

    # Content with no declared format is not touched
    assert obj.notify(body="**raw** \\*")
    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["text"] == "**raw** \\*"


def test_plugin_cliq_dialect():
    """NotifyCliq() converts each piece of CommonMark it understands."""

    f = NotifyCliq._commonmark_to_cliq

    # Emphasis
    assert f("**bold** and *it*") == "*bold* and _it_"

    # Code is kept, including unmatched backticks
    assert f("`c*d` and ```x**y```") == "`c*d` and ```x**y```"
    assert f("a ` b *c*") == "a ` b _c_"

    # Links keep their label and lose any angle brackets
    assert f("[a](<https://x.com/(b)>)") == "[a](https://x.com/(b%29)"
    assert f("[a](https://x.com/b_*c*)") == "[a](https://x.com/b_*c*)"

    # Autolinks lose their brackets; other "<" is literal
    assert f("see <https://y.com/a*b> now") == "see https://y.com/a*b now"
    assert f("a < b") == "a < b"

    # Broken links are left as text
    assert f("[a](<unterminated") == "[a](<unterminated"
    assert f("[a](has space)") == "[a](has space)"
    assert f("[a] then (b)") == "[a] then (b)"

    # Escapes are removed
    assert f("5 \\* 3 \\_") == "5 * 3 _"

    # Other formats are not converted
    obj = NotifyCliq(token=TOKEN)
    assert obj.dialect_convert("**x**", NotifyFormat.TEXT) == "**x**"
    assert obj.dialect_convert("**x**", NotifyFormat.MARKDOWN) == "*x*"
