# Disable logging for a cleaner testing output
from json import dumps, loads
import logging
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise
from apprise.common import NotifyType
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.lark import NotifyLark

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "lark://",
        {
            # Teams Token missing
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "lark://:@/",
        {
            # We don't have strict host checking on for lark, so this URL
            # actually becomes parseable and :@ becomes a hostname.
            # The below errors because a second token wasn't found
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "lark://{}".format("abcd-1234"),
        {
            # token provided - we're good
            "instance": NotifyLark,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "lark://****/",
        },
    ),
    (
        "lark://{}".format("abcd-1234"),
        {
            # token provided - we're good
            "instance": NotifyLark,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "lark://****/",
        },
    ),
    (
        "lark://?token={}".format("abcd-1234"),
        {
            # token provided - we're good
            "instance": NotifyLark,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "lark://****/",
        },
    ),
    # Support Native URLs with arguments
    (
        "https://open.larksuite.com/open-apis/bot/v2/hook/{}".format(
            "abcd-1234"
        ),
        {
            # token provided - we're good
            "instance": NotifyLark,
        },
    ),
    (
        "lark://{}".format("abcd-1234"),
        {
            "instance": NotifyLark,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "lark://{}".format("abcd-1234"),
        {
            "instance": NotifyLark,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "lark://{}".format("a" * 80),
        {
            "instance": NotifyLark,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_lark_urls():
    """NotifyLark() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def _lark_response(code=0):
    """Build a Lark webhook response."""
    response = requests.Response()
    response.status_code = requests.codes.ok
    response._content = dumps(
        {"StatusCode": code if code else 0, "code": code, "msg": "ok"}
    ).encode("utf-8")
    return response


@mock.patch("requests.post")
def test_plugin_lark_text_is_default(mock_post):
    """NotifyLark(): plain text stays the default message type."""

    mock_post.return_value = _lark_response()

    aobj = Apprise()
    assert aobj.add("lark://{}".format("a" * 8))
    assert bool(aobj.notify(title="title", body="body")) is True
    assert mock_post.call_count == 1

    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload["msg_type"] == "text"
    assert payload["content"]["text"] == "title\nbody"
    assert "card" not in payload


@mock.patch("requests.post")
def test_plugin_lark_markdown_card(mock_post):
    """NotifyLark(): Markdown is delivered as an interactive card."""

    mock_post.return_value = _lark_response()

    aobj = Apprise()
    assert aobj.add("lark://{}?format=markdown".format("a" * 8))
    assert bool(aobj.notify(title="title", body="**body**")) is True
    assert mock_post.call_count == 1

    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload["msg_type"] == "interactive"
    assert payload["card"]["header"]["title"]["content"] == "title"
    assert payload["card"]["header"]["template"] == "blue"
    assert payload["card"]["elements"][0]["text"]["tag"] == "lark_md"
    assert payload["card"]["elements"][0]["text"]["content"] == "**body**"


@pytest.mark.parametrize(
    "notify_type,colour",
    [
        (NotifyType.INFO, "blue"),
        (NotifyType.SUCCESS, "green"),
        (NotifyType.WARNING, "orange"),
        (NotifyType.FAILURE, "red"),
    ],
)
@mock.patch("requests.post")
def test_plugin_lark_card_colours(mock_post, notify_type, colour):
    """NotifyLark(): the card header colour tracks the notification type."""

    mock_post.return_value = _lark_response()

    obj = Apprise.instantiate("lark://{}?format=markdown".format("a" * 8))
    assert obj.notify(body="body", notify_type=notify_type) is True

    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload["card"]["header"]["template"] == colour


@mock.patch("requests.post")
def test_plugin_lark_card_byte_budget(mock_post):
    """NotifyLark(): a CJK card is trimmed to the 20 KB byte cap."""

    mock_post.return_value = _lark_response()

    obj = Apprise.instantiate("lark://{}?format=markdown".format("a" * 8))
    assert obj.notify(body="\u4e2d" * 20000) is True
    assert mock_post.call_count == 1

    raw = mock_post.call_args_list[0][1]["data"]
    assert len(raw) <= NotifyLark.max_payload_bytes

    content = loads(raw)["card"]["elements"][0]["text"]["content"]
    assert content.endswith("\u2026")


@mock.patch("requests.post")
def test_plugin_lark_rejected_payload(mock_post):
    """NotifyLark(): a non-zero response code fails the notification."""

    mock_post.return_value = _lark_response(code=9499)

    obj = Apprise.instantiate("lark://{}".format("a" * 8))
    assert obj.notify(body="body") is False


def test_plugin_lark_markdown_url():
    """NotifyLark(): format=markdown survives a URL round trip."""

    obj = Apprise.instantiate("lark://{}?format=markdown".format("a" * 8))
    url = obj.url()
    assert "format=markdown" in url
    assert Apprise.instantiate(url) is not None
