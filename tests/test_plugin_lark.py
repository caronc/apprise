# Disable logging for a cleaner testing output
from json import dumps, loads
import logging
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise
from apprise.common import NotifyFormat, NotifyType
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
    response._content = dumps({"code": code, "msg": "ok"}).encode("utf-8")
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
def test_plugin_lark_markdown_input(mock_post):
    """NotifyLark(): Markdown input is sent as a titled card."""

    mock_post.return_value = _lark_response()

    aobj = Apprise()
    assert aobj.add("lark://{}".format("a" * 8))
    assert aobj.notify(
        title="title", body="**body**", body_format=NotifyFormat.MARKDOWN
    )

    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload["msg_type"] == "interactive"
    assert payload["card"]["header"]["title"]["content"] == "title"
    assert payload["card"]["elements"][0]["text"]["content"] == "**body**"

    # Text input on the same URL stays a plain text message
    mock_post.reset_mock()
    assert aobj.notify(
        title="title", body="body", body_format=NotifyFormat.TEXT
    )
    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload["msg_type"] == "text"
    assert "card" not in payload


@mock.patch("requests.post")
def test_plugin_lark_markdown_card(mock_post):
    """NotifyLark(): ?format=markdown is delivered as an interactive card."""

    mock_post.return_value = _lark_response()

    title = "A & <B>"
    body = "**bold** _ . ! * # <"

    aobj = Apprise()
    assert aobj.add("lark://{}?format=markdown".format("a" * 8))
    assert aobj.notify(
        title=title, body=body, body_format=NotifyFormat.MARKDOWN
    )
    assert mock_post.call_count == 1

    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload["msg_type"] == "interactive"
    assert "content" not in payload

    # The title is plain text in the header and is never converted
    header = payload["card"]["header"]
    assert header["title"]["tag"] == "plain_text"
    assert header["title"]["content"] == title
    assert header["template"] == "blue"

    # Declared Markdown reaches the card untouched
    text = payload["card"]["elements"][0]["text"]
    assert text["tag"] == "lark_md"
    assert text["content"] == body

    # A card with no title falls back to the application description
    mock_post.reset_mock()
    obj = Apprise.instantiate("lark://{}?format=markdown".format("a" * 8))
    assert obj.notify(body=body) is True
    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload["card"]["header"]["title"]["content"] == obj.app_desc
    assert payload["card"]["elements"][0]["text"]["content"] == body


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
def test_plugin_lark_utf8_payload(mock_post):
    """NotifyLark(): CJK text is sent as raw UTF-8, not escaped."""

    mock_post.return_value = _lark_response()

    obj = Apprise.instantiate("lark://{}".format("a" * 8))
    assert obj.notify(body="\u4e2d" * 10) is True

    raw = mock_post.call_args_list[0][1]["data"]
    assert ("\u4e2d" * 10).encode("utf-8") in raw
    assert b"\\u4e2d" not in raw


@mock.patch("requests.post")
def test_plugin_lark_throttle_once(mock_post):
    """NotifyLark(): each notification waits on the throttle only once."""

    mock_post.return_value = _lark_response()

    obj = Apprise.instantiate("lark://{}".format("a" * 8))
    with mock.patch.object(obj, "throttle") as mock_throttle:
        assert obj.notify(body="body") is True

    assert mock_throttle.call_count == 1


@pytest.mark.parametrize(
    "content,expected",
    [
        (dumps({"code": 9499, "msg": "Bad Request"}).encode("utf-8"), False),
        (dumps({"code": 0, "msg": "success"}).encode("utf-8"), True),
        (dumps({"StatusCode": 0}).encode("utf-8"), True),
        (b"[]", True),
        (b"not json", True),
        (None, True),
    ],
)
@mock.patch("requests.post")
def test_plugin_lark_response_code(mock_post, content, expected):
    """NotifyLark(): a non-zero code in an HTTP 200 reply is a failure."""

    response = requests.Response()
    response.status_code = requests.codes.ok
    response._content = content
    mock_post.return_value = response

    obj = Apprise.instantiate("lark://{}".format("a" * 8))
    assert obj.notify(body="body") is expected


@mock.patch("requests.post")
def test_plugin_lark_markdown_url(mock_post):
    """NotifyLark(): format=markdown survives a URL round trip."""

    mock_post.return_value = _lark_response()

    obj = Apprise.instantiate("lark://{}?format=markdown".format("a" * 8))
    url = obj.url()
    assert "format=markdown" in url

    # The rebuilt URL still sends plain text input as a card
    again = Apprise.instantiate(url)
    assert again is not None
    assert again.notify(body="body", body_format=NotifyFormat.TEXT) is True

    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload["msg_type"] == "interactive"

    # A plain URL does not pin a format, so it keeps following the input
    assert (
        "format=" not in Apprise.instantiate("lark://{}".format("a" * 8)).url()
    )
