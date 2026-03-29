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
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from json import loads

# Disable logging for a cleaner testing output
import logging
import os
from random import choice
from string import ascii_uppercase as str_alpha, digits as str_num
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, AppriseAttachment, NotifyFormat, NotifyType
from apprise.common import OverflowMode
from apprise.plugins.fluxer import NotifyFluxer

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")


def _tokens() -> tuple[str, str]:
    """Return tokens that satisfy Fluxer validation."""

    # webhook_id: digits, >= 10
    # webhook_token: [A-Za-z0-9_-], >= 16
    return ("0" * 10, "B" * 40)


# Our Testing URLs
apprise_url_tests = (
    (
        "fluxer://",
        {
            "instance": TypeError,
        },
    ),
    # An invalid url
    (
        "fluxer://:@/",
        {
            "instance": TypeError,
        },
    ),
    # No webhook_token specified
    (
        "fluxer://%s" % ("0" * 10),
        {
            "instance": TypeError,
        },
    ),
    # Provide both a webhook id and a webhook token
    (
        "fluxer://{}/{}".format(*_tokens()),
        {
            "instance": NotifyFluxer,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    # Provide a temporary username
    (
        "fluxer://l2g@{}/{}".format(*_tokens()),
        {
            "instance": NotifyFluxer,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    # Mode set to private, but no hostname was fluxers; we toggle to cloud mode
    (
        "fluxer://api.fluxer.app/{}/{}?mode=private".format(*_tokens()),
        {
            "instance": NotifyFluxer,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    # test image= field
    (
        "fluxer://{}/{}?format=markdown&footer=Yes&image=Yes&ping=Joe".format(
            *_tokens()
        ),
        {
            "instance": NotifyFluxer,
            "requests_response_code": requests.codes.no_content,
            # don't include an image by default
            "include_image": False,
        },
    ),
    (
        "fluxer://{}/{}?format=markdown&footer=Yes&image=No&fields=no".format(
            *_tokens()
        ),
        {
            "instance": NotifyFluxer,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    (
        "fluxer://jack@{}/{}?format=markdown&footer=Yes&image=Yes".format(
            *_tokens()
        ),
        {
            "instance": NotifyFluxer,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    (
        "fluxer://jack@{}/{}?mode=private&host=example.ca".format(*_tokens()),
        {
            "instance": NotifyFluxer,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    (
        "fluxer://{}/{}?mode=private&host=example.ca&name=jack".format(
            *_tokens()
        ),
        {
            "instance": NotifyFluxer,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    (
        "fluxer://example.ca:123/{}/{}".format(*_tokens()),
        {
            "instance": NotifyFluxer,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    (
        # Invalid Mode
        "fluxer://jack@{}/{}?mode=invalid".format(*_tokens()),
        {
            "instance": TypeError,
        },
    ),
    (
        "https://api.fluxer.app/webhooks/{}/{}".format(*_tokens()),
        {
            # Native URL Support
            "instance": NotifyFluxer,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    (
        "https://api.fluxer.app/v1/webhooks/{}/{}?footer=yes".format(
            *_tokens()
        ),
        {
            # Native URL Support with arguments
            "instance": NotifyFluxer,
            "requests_response_code": requests.codes.no_content,
            "privacy_url": "fluxer://0...0/B...B/",
        },
    ),
    (
        "https://api.fluxer.app/v1/webhooks/{}/{}?footer=yes&botname=joe".format(
            *_tokens()
        ),
        {
            # Native URL Support with arguments
            "instance": NotifyFluxer,
            "requests_response_code": requests.codes.no_content,
            "privacy_url": "fluxer://joe@0...0/B...B/",
        },
    ),
    (
        "fluxer://{}/{}?format=markdown&avatar=No&footer=No".format(
            *_tokens()
        ),
        {
            "instance": NotifyFluxer,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    (
        "fluxer://{}/{}?flags=1".format(*_tokens()),
        {
            "instance": NotifyFluxer,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    (
        "fluxer://{}/{}?flags=-1".format(*_tokens()),
        {
            # invalid flags specified (variation 1)
            "instance": TypeError,
        },
    ),
    (
        "fluxer://{}/{}?flags=invalid".format(*_tokens()),
        {
            # invalid flags specified (variation 2)
            "instance": TypeError,
        },
    ),
    # different format support
    (
        "fluxer://{}/{}?format=markdown".format(*_tokens()),
        {
            "instance": NotifyFluxer,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    # Thread ID (forces markdown mode)
    (
        "fluxer://{}/{}?format=markdown&thread=abc123".format(*_tokens()),
        {
            "instance": NotifyFluxer,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    (
        "fluxer://{}/{}?format=text".format(*_tokens()),
        {
            "instance": NotifyFluxer,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    # Test with href (title link)
    (
        "fluxer://{}/{}?hmarkdown=true&ref=http://localhost".format(
            *_tokens()
        ),
        {
            "instance": NotifyFluxer,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    # Test with url (title link) - Alias of href
    (
        "fluxer://{}/{}?markdown=true&url=http://localhost".format(*_tokens()),
        {
            "instance": NotifyFluxer,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    # Test with avatar URL
    (
        "fluxer://{}/{}?avatar_url=http://localhost/test.jpg".format(
            *_tokens()
        ),
        {
            "instance": NotifyFluxer,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    # Test without image set
    (
        "fluxer://{}/{}".format(*_tokens()),
        {
            "instance": NotifyFluxer,
            "requests_response_code": requests.codes.no_content,
            # don't include an image by default
            "include_image": False,
        },
    ),
    (
        "fluxer://{}/{}".format(*_tokens()),
        {
            "instance": NotifyFluxer,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "fluxer://{}/{}".format(*_tokens()),
        {
            "instance": NotifyFluxer,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "fluxer://{}/{}".format(*_tokens()),
        {
            "instance": NotifyFluxer,
            # Throws a series of i/o exceptions with this flag set and tests
            # that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_fluxer_urls() -> None:
    """NotifyFluxer() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_fluxer_notifications(mock_post: mock.MagicMock) -> None:
    """NotifyFluxer() Notifications/Ping Support."""

    webhook_id, webhook_token = _tokens()

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = b""
    mock_post.return_value.headers = {}

    # Test our header parsing when not lead with a header
    body = """
    # Heading
    @everyone and @admin, wake and meet our new user <@123>; <@&456>"
    """

    results = NotifyFluxer.parse_url(
        f"fluxer://{webhook_id}/{webhook_token}/?format=markdown"
    )

    assert isinstance(results, dict)
    assert results["user"] is None
    assert results["webhook_id"] == webhook_id
    assert results["webhook_token"] == webhook_token
    assert results["schema"] == "fluxer"

    instance = NotifyFluxer(**results)
    assert isinstance(instance, NotifyFluxer)

    assert instance.send(body=body) is True
    assert mock_post.call_count == 1

    details = mock_post.call_args_list[0]
    assert (
        details[0][0]
        == f"https://api.fluxer.app/webhooks/{webhook_id}/{webhook_token}"
    )

    payload = loads(details[1]["data"])
    assert isinstance(payload, dict)

    assert "allow_mentions" in payload
    assert set(payload["allow_mentions"]["users"]) == {"123"}
    assert set(payload["allow_mentions"]["roles"]) == {"456"}
    assert set(payload["allow_mentions"]["parse"]) == {"everyone", "admin"}
    assert payload["content"].startswith("👉 ")

    # Reset our object
    mock_post.reset_mock()

    results = NotifyFluxer.parse_url(
        f"fluxer://{webhook_id}/{webhook_token}/?format=text"
    )

    instance = NotifyFluxer(**results)
    assert isinstance(instance, NotifyFluxer)

    assert instance.send(body=body) is True
    payload = loads(mock_post.call_args_list[0][1]["data"])

    # text mode does not parse mentions from body
    assert "allow_mentions" not in payload

    # Reset our object
    mock_post.reset_mock()

    body = " "
    results = NotifyFluxer.parse_url(
        # & -> %26 for role otherwise & separates our URL from further parsing
        f"fluxer://{webhook_id}/{webhook_token}/?ping=@joe,<@321>,<@%26654>"
    )
    instance = NotifyFluxer(**results)
    assert isinstance(instance, NotifyFluxer)

    assert instance.send(body=body) is True
    payload = loads(mock_post.call_args_list[0][1]["data"])

    assert "allow_mentions" in payload
    assert set(payload["allow_mentions"]["users"]) == {"321"}
    assert set(payload["allow_mentions"]["roles"]) == {"654"}
    assert set(payload["allow_mentions"]["parse"]) == {"joe"}
    assert "<@321>" in payload["content"]
    assert "<@&654>" in payload["content"]
    assert "@joe" in payload["content"]

    # Reset our object
    mock_post.reset_mock()

    # Test our body in text mode, with ping=set
    body = """
    # Heading
    @everyone and @admin, wake and meet our new user <@123>; <@&456>"
    """

    results = NotifyFluxer.parse_url(
        # & -> %26 for role otherwise & separates our URL from further parsing
        f"fluxer://{webhook_id}/{webhook_token}/?ping=@joe,<@321>,<@%26654>"
        "&format=text"
    )

    instance = NotifyFluxer(**results)
    assert isinstance(instance, NotifyFluxer)

    assert instance.send(body=body) is True
    payload = loads(mock_post.call_args_list[0][1]["data"])

    # Payload only includes elements on ping= line with text mode
    assert "allow_mentions" in payload
    assert set(payload["allow_mentions"]["users"]) == {"321"}
    assert set(payload["allow_mentions"]["roles"]) == {"654"}
    assert set(payload["allow_mentions"]["parse"]) == {"joe"}


@mock.patch("requests.post")
@mock.patch("time.sleep")
def test_plugin_fluxer_429(
    mock_sleep: mock.MagicMock,
    mock_post: mock.MagicMock,
) -> None:
    """
    NotifyFluxer() 429 handling

    Focus: Fluxer-specific HTTP 429 + Retry-After handling (recursive retry),
    including header parsing edge cases and retry exhaustion.
    """

    # Prevent throttling side effects
    mock_sleep.return_value = True

    webhook_id, webhook_token = _tokens()

    # Basic construction checks (keep these, they match plugin validation)
    with pytest.raises(TypeError):
        NotifyFluxer(webhook_id=None, webhook_token=webhook_token)
    with pytest.raises(TypeError):
        NotifyFluxer(webhook_id="  ", webhook_token=webhook_token)

    with pytest.raises(TypeError):
        NotifyFluxer(webhook_id=webhook_id, webhook_token=None)
    with pytest.raises(TypeError):
        NotifyFluxer(webhook_id=webhook_id, webhook_token="   ")

    obj = NotifyFluxer(
        webhook_id=webhook_id,
        webhook_token=webhook_token,
        footer=True,
        include_image=True,
    )

    # url() must always return a string
    assert isinstance(obj.url(), str)

    # Helper to build responses
    def _resp(code: int, headers: dict[str, str] | None = None) -> mock.Mock:
        r = mock.Mock()
        r.status_code = code
        r.content = b""
        r.headers = headers or {}
        return r

    # Retry-After header missing -> defaults to default_delay_sec (1.0)
    mock_post.reset_mock()
    mock_sleep.reset_mock()
    mock_post.side_effect = [
        _resp(requests.codes.too_many_requests, {}),
        _resp(requests.codes.no_content, {}),
    ]

    assert obj.send(body="test") is True
    assert mock_post.call_count == 2
    assert mock_sleep.call_count == 1
    assert mock_sleep.call_args_list[-1][0][0] == pytest.approx(
        1.0, rel=0, abs=0.05
    )

    # Retry-After invalid -> falls back to 1.0
    mock_post.reset_mock()
    mock_sleep.reset_mock()
    mock_post.side_effect = [
        _resp(requests.codes.too_many_requests, {"Retry-After": "garbage"}),
        _resp(requests.codes.no_content, {}),
    ]

    assert obj.send(body="test") is True
    assert mock_post.call_count == 2
    assert mock_sleep.call_count >= 1
    assert mock_sleep.call_args_list[-1][0][0] == pytest.approx(
        1.0, rel=0, abs=0.05
    )

    # Retry-After < 1.0 -> max(1.0, value) enforces 1.0
    mock_post.reset_mock()
    mock_sleep.reset_mock()
    mock_post.side_effect = [
        _resp(requests.codes.too_many_requests, {"Retry-After": "0.25"}),
        _resp(requests.codes.no_content, {}),
    ]

    assert obj.send(body="test") is True
    assert mock_post.call_count == 2
    assert mock_sleep.call_count >= 1
    assert mock_sleep.call_args_list[-1][0][0] == pytest.approx(
        1.0, rel=0, abs=0.05
    )

    # Retry-After valid integer -> sleeps that many seconds
    mock_post.reset_mock()
    mock_sleep.reset_mock()
    mock_post.side_effect = [
        _resp(requests.codes.too_many_requests, {"Retry-After": "2"}),
        _resp(requests.codes.no_content, {}),
    ]

    assert obj.send(body="test") is True
    assert mock_post.call_count == 2
    assert mock_sleep.call_count >= 1
    assert mock_sleep.call_args_list[-1][0][0] == pytest.approx(
        2.0, rel=0, abs=0.05
    )

    # Retry exhaustion: default send() retries once.
    # If we get 429 twice, second one is not retried and send fails.
    mock_post.reset_mock()
    mock_sleep.reset_mock()
    mock_post.side_effect = [
        _resp(requests.codes.too_many_requests, {"Retry-After": "1"}),
        _resp(requests.codes.too_many_requests, {"Retry-After": "1"}),
    ]

    assert obj.send(body="test") is False
    assert mock_post.call_count == 2
    assert mock_sleep.call_count >= 1

    mock_sleep.reset_mock()
    mock_post.reset_mock()

    response = mock.Mock()
    response.status_code = requests.codes.no_content
    response.content = b""
    response.headers = {}
    mock_post.return_value = response
    mock_post.side_effect = None

    # Force the 'now <= ratelimit_reset' path to compute a wait.
    obj = NotifyFluxer(webhook_id=webhook_id, webhook_token=webhook_token)

    # Force the rate-limit gate to run
    obj.ratelimit_remaining = 0.0

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    obj.ratelimit_reset = now - timedelta(seconds=2)

    with mock.patch.object(obj, "throttle") as m_throttle:
        assert obj.send(body="test") is True

    # We expect throttle(wait=~2.0) to be called.
    assert m_throttle.call_count >= 1
    wait = m_throttle.call_args_list[-1][1].get("wait")

    assert wait is None

    # Call count
    assert mock_post.call_count == 1

    # Reset our object
    mock_post.reset_mock()

    # Force the 'now < ratelimit_reset' path to compute a wait.
    obj = NotifyFluxer(webhook_id=webhook_id, webhook_token=webhook_token)

    # Force the rate-limit gate to run
    obj.ratelimit_remaining = 0.0

    # Bracket the call with timestamps so the assertion is
    # architecture-independent (slow ppc64le build machines can add
    # hundreds of ms of overhead between captures of datetime.now()).
    t_before = datetime.now(timezone.utc).replace(tzinfo=None)
    obj.ratelimit_reset = t_before + timedelta(seconds=2)

    with mock.patch.object(obj, "throttle") as m_throttle:
        assert obj.send(body="test") is True

    t_after = datetime.now(timezone.utc).replace(tzinfo=None)

    # We expect throttle(wait=~2.0) to be called.
    assert m_throttle.call_count >= 1
    wait = m_throttle.call_args_list[-1][1].get("wait")

    assert wait is not None
    # wait = ratelimit_reset - now_inside_plugin
    # The plugin's 'now' is somewhere in [t_before, t_after], so:
    #   lower bound: ratelimit_reset - t_after = 2.0 - elapsed
    #   upper bound: ratelimit_reset - t_before = 2.0
    elapsed = (t_after - t_before).total_seconds()
    assert (2.0 - elapsed) <= wait <= 2.0

    # Call count
    assert mock_post.call_count == 1


@mock.patch("requests.post")
def test_plugin_fluxer_general(
    mock_post: mock.MagicMock,
) -> None:
    """NotifyFluxer() General Checks."""

    webhook_id, webhook_token = _tokens()

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = ""

    # Invalid webhook id
    with pytest.raises(TypeError):
        NotifyFluxer(webhook_id=None, webhook_token=webhook_token)
    # Invalid webhook id (whitespace)
    with pytest.raises(TypeError):
        NotifyFluxer(webhook_id="  ", webhook_token=webhook_token)

    # Invalid webhook token
    with pytest.raises(TypeError):
        NotifyFluxer(webhook_id=webhook_id, webhook_token=None)

    # Private mode but no hostname provided
    with pytest.raises(TypeError):
        NotifyFluxer(
            webhook_id=webhook_id,
            webhook_token=webhook_token,
            mode="private",
        )

    obj = NotifyFluxer(
        webhook_id=webhook_id,
        webhook_token=webhook_token,
        footer=True,
        include_image=True,
    )

    # Simple Markdown Single line of text
    test_markdown = "body"
    desc, results = obj.extract_markdown_sections(test_markdown)
    assert isinstance(results, list) is True
    assert len(results) == 0
    assert desc == "body"

    # Test our header parsing when not lead with a header
    test_markdown = """
    A section of text that has no header at the top.
    It also has a hash tag # <- in the middle of a
    string.

    ## Heading 1
    body

    # Heading 2

    more content
    on multi-lines
    """

    desc, results = obj.extract_markdown_sections(test_markdown)
    # we have a description
    assert isinstance(desc, str) is True
    assert desc.startswith("A section of text that has no header at the top.")
    assert desc.endswith("string.")

    assert isinstance(results, list) is True
    assert len(results) == 2
    assert results[0]["name"] == "Heading 1"
    assert results[0]["value"] == "```md\nbody\n```"
    assert results[1]["name"] == "Heading 2"
    assert (
        results[1]["value"] == "```md\nmore content\n    on multi-lines\n```"
    )

    # Test our header parsing
    test_markdown = (
        "## Heading one\nbody body\n\n"
        + "# Heading 2 ##\n\nTest\n\n"
        + "more content\n"
        + "even more content  \t\r\n\n\n"
        + "# Heading 3 ##\n\n\n"
        + "normal content\n"
        + "# heading 4\n"
        + "#### Heading 5"
    )

    desc, results = obj.extract_markdown_sections(test_markdown)
    assert isinstance(results, list) is True
    # No desc details filled out
    assert isinstance(desc, str) is True
    assert not desc

    # We should have 5 sections (since there are 5 headers identified above)
    assert len(results) == 5
    assert results[0]["name"] == "Heading one"
    assert results[0]["value"] == "```md\nbody body\n```"
    assert results[1]["name"] == "Heading 2"
    assert (
        results[1]["value"]
        == "```md\nTest\n\nmore content\neven more content\n```"
    )
    assert results[2]["name"] == "Heading 3"
    assert results[2]["value"] == "```md\nnormal content\n```"
    assert results[3]["name"] == "heading 4"
    assert results[3]["value"] == "```\n```"
    assert results[4]["name"] == "Heading 5"
    assert results[4]["value"] == "```\n```"

    # Create an apprise instance
    a = Apprise()

    # Our processing is slightly different when we aren't using markdown
    # as we do not pre-parse content during our notifications
    assert (
        a.add(
            f"fluxer://{webhook_id}/{webhook_token}/"
            "?format=markdown&footer=Yes"
        )
        is True
    )

    # This call includes an image with its payload:
    orig_fluxer_max_fields = NotifyFluxer.fluxer_max_fields
    try:
        NotifyFluxer.fluxer_max_fields = 1
        assert (
            a.notify(
                body=test_markdown,
                title="title",
                notify_type=NotifyType.INFO,
                body_format=NotifyFormat.TEXT,
            )
            is True
        )
    finally:
        # Restore the original value to avoid impacting other tests
        NotifyFluxer.fluxer_max_fields = orig_fluxer_max_fields

    # Throw an exception on the forth call to requests.post()
    # This allows to test our batch field processing
    response = mock.Mock()
    response.content = b""
    response.status_code = requests.codes.ok
    response.headers = {}
    mock_post.return_value = response
    mock_post.side_effect = [
        response,
        response,
        response,
        requests.RequestException(),
    ]

    # Test our markdown
    obj = Apprise.instantiate(
        f"fluxer://{webhook_id}/{webhook_token}/?format=markdown"
    )
    assert isinstance(obj, NotifyFluxer)

    # Force batching so we actually hit the 4th post() call
    orig_fluxer_max_fields = NotifyFluxer.fluxer_max_fields
    try:
        NotifyFluxer.fluxer_max_fields = 1

        assert (
            obj.notify(
                body=test_markdown, title="title", notify_type=NotifyType.INFO
            )
            is False
        )
    finally:
        NotifyFluxer.fluxer_max_fields = orig_fluxer_max_fields
        mock_post.side_effect = None

    # Empty String
    desc, results = obj.extract_markdown_sections("")
    assert isinstance(results, list) is True
    assert len(results) == 0

    # No desc details filled out
    assert isinstance(desc, str) is True
    assert not desc

    # String without Heading
    test_markdown = (
        "Just a string without any header entries.\n" + "A second line"
    )
    desc, results = obj.extract_markdown_sections(test_markdown)
    assert isinstance(results, list) is True
    assert len(results) == 0

    # No desc details filled out
    assert isinstance(desc, str) is True
    assert (
        desc == "Just a string without any header entries.\n" + "A second line"
    )

    # Use our test markdown string during a notification
    assert (
        obj.notify(
            body=test_markdown, title="title", notify_type=NotifyType.INFO
        )
        is True
    )

    # Create an apprise instance
    a = Apprise()

    # Our processing is slightly different when we aren't using markdown
    # as we do not pre-parse content during our notifications
    assert (
        a.add(
            f"fluxer://{webhook_id}/{webhook_token}/"
            "?format=markdown&footer=Yes"
        )
        is True
    )

    # This call includes an image with it's payload:
    assert (
        a.notify(
            body=test_markdown,
            title="title",
            notify_type=NotifyType.INFO,
            body_format=NotifyFormat.TEXT,
        )
        is True
    )

    assert (
        a.notify(
            body=test_markdown,
            title="title",
            notify_type=NotifyType.INFO,
            body_format=NotifyFormat.MARKDOWN,
        )
        is True
    )

    # Toggle our logo availability
    a.asset.image_url_logo = None
    assert (
        a.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    # Create an apprise instance
    a = Apprise()

    # Reset our object
    mock_post.reset_mock()

    # Test our threading
    assert (
        a.add(f"fluxer://{webhook_id}/{webhook_token}/?thread=12345") is True
    )

    # This call includes an image with it's payload:
    assert a.notify(body="test", title="title") is True

    assert mock_post.call_count == 1
    response = mock_post.call_args_list[0][1]
    assert "params" in response
    assert response["params"].get("thread_id") == "12345"


@mock.patch("requests.post")
def test_plugin_fluxer_overflow(mock_post):
    """NotifyFluxer() Overflow Checks."""

    webhook_id, webhook_token = _tokens()

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    # Some variables we use to control the data we work with
    body_len = 8000
    title_len = 1024

    # Number of characters per line
    row = 24

    # Create a large body and title with random data
    body = "".join(choice(str_alpha + str_num + " ") for _ in range(body_len))
    body = "\r\n".join([body[i : i + row] for i in range(0, len(body), row)])

    # Create our title using random data
    title = "".join(choice(str_alpha + str_num) for _ in range(title_len))

    results = NotifyFluxer.parse_url(
        f"fluxer://{webhook_id}/{webhook_token}/?overflow=split"
    )

    instance = NotifyFluxer(**results)
    assert isinstance(instance, NotifyFluxer)

    results = instance._apply_overflow(
        body, title=title, overflow=OverflowMode.SPLIT
    )

    # Ensure we never exceed 2000 characters
    for entry in results:
        assert len(entry["title"]) <= instance.title_maxlen
        assert len(entry["title"]) + len(entry["body"]) <= instance.body_maxlen


@mock.patch("requests.post")
def test_plugin_fluxer_markdown_extra(mock_post):
    """NotifyFluxer() Markdown Extra Checks."""

    webhook_id, webhook_token = _tokens()

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = b""
    mock_post.return_value.headers = {}

    # Reset our apprise object
    a = Apprise()

    assert (
        a.add(
            f"fluxer://{webhook_id}/{webhook_token}/"
            "?format=markdown&footer=Yes"
        )
        is True
    )

    test_markdown = "[green-blue](https://google.com)"

    # This call includes an image with it's payload:
    assert (
        a.notify(
            body=test_markdown,
            title="title",
            notify_type=NotifyType.INFO,
            body_format=NotifyFormat.TEXT,
        )
        is True
    )

    assert (
        a.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )


@mock.patch("requests.post")
def test_plugin_fluxer_markdown_attachments(
    mock_post: mock.MagicMock,
) -> None:
    # Prepare our tokens
    webhook_id, webhook_token = _tokens()

    # Prepare a good response
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b""

    # Prepare a bad response
    bad_response = mock.Mock()
    bad_response.status_code = requests.codes.internal_server_error
    bad_response.content = b""

    # Prepare Mock return object
    mock_post.return_value = response

    # Test our markdown
    obj = Apprise.instantiate(
        f"fluxer://{webhook_id}/{webhook_token}/?format=markdown"
    )

    # attach our content
    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.gif"))

    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is True
    )

    # Test our call count
    assert mock_post.call_count == 2
    assert (
        mock_post.call_args_list[0][0][0]
        == f"https://api.fluxer.app/webhooks/{webhook_id}/{webhook_token}"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == f"https://api.fluxer.app/webhooks/{webhook_id}/{webhook_token}"
    )

    # Reset our object
    mock_post.reset_mock()

    # Test notifications with mentions and attachments in it
    assert (
        obj.notify(
            body="Say hello to <@1234>!",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is True
    )

    # Test our call count
    assert mock_post.call_count == 2
    assert (
        mock_post.call_args_list[0][0][0]
        == f"https://api.fluxer.app/webhooks/{webhook_id}/{webhook_token}"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == f"https://api.fluxer.app/webhooks/{webhook_id}/{webhook_token}"
    )

    # Reset our object
    mock_post.reset_mock()

    # An invalid attachment will cause a failure
    path = os.path.join(TEST_VAR_DIR, "/invalid/path/to/an/invalid/file.jpg")
    attach = AppriseAttachment(path)
    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=path,
        )
        is False
    )

    # update our attachment to be valid
    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.gif"))

    mock_post.return_value = None
    # Throw an exception on the first call to requests.post()
    for side_effect in (requests.RequestException(), OSError(), bad_response):
        mock_post.side_effect = [side_effect]

        # We'll fail now because of our error handling
        assert obj.send(body="test", attach=attach) is False

    # Throw an exception on the second call to requests.post()
    for side_effect in (requests.RequestException(), OSError(), bad_response):
        mock_post.side_effect = [response, side_effect]

        # We'll fail now because of our error handling
        assert obj.send(body="test", attach=attach) is False

    # handle a bad response
    bad_response = mock.Mock()
    bad_response.content = b""
    bad_response.headers = {}
    bad_response.status_code = requests.codes.internal_server_error
    mock_post.side_effect = [response, bad_response]

    # We'll fail now because of an internal exception
    assert obj.send(body="test", attach=attach) is False


@mock.patch("requests.post")
def test_plugin_fluxer_markdown_fields_batches_exactly(mock_post):
    webhook_id, webhook_token = _tokens()
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = ""
    response.headers = {}
    mock_post.return_value = response

    # Force tiny batches
    NotifyFluxer.fluxer_max_fields = 1

    body = "# H1\nv1\n# H2\nv2\n# H3\nv3\n"
    obj = Apprise.instantiate(
        f"fluxer://{webhook_id}/{webhook_token}/?format=markdown&fields=yes"
    )
    assert isinstance(obj, NotifyFluxer)

    assert obj.send(body=body) is True

    # H1, H2, H3 => 3 fields => 3 posts (since max_fields=1)
    assert mock_post.call_count == 3

    NotifyFluxer.fluxer_max_fields = 10


@mock.patch("requests.post")
def test_plugin_fluxer_markdown_ping_is_additive(
    mock_post: mock.MagicMock,
) -> None:
    webhook_id, webhook_token = _tokens()

    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = b""
    mock_post.return_value.headers = {}

    body = "Body pings <@111> and <@&222> @everyone"
    results = NotifyFluxer.parse_url(
        f"fluxer://{webhook_id}/{webhook_token}/"
        "?format=markdown"
        "&ping=<@333>,<@%26444>,@joe"
    )
    obj = NotifyFluxer(**results)

    assert obj.send(body=body) is True
    assert mock_post.call_count == 1

    payload = loads(mock_post.call_args_list[0][1]["data"])

    assert "allow_mentions" in payload
    # union
    assert set(payload["allow_mentions"]["users"]) == {"111", "333"}
    assert set(payload["allow_mentions"]["roles"]) == {"222", "444"}
    assert set(payload["allow_mentions"]["parse"]) == {"everyone", "joe"}
    assert payload["content"].startswith("👉 ")


@mock.patch("requests.post")
def test_plugin_fluxer_html_ping_is_exclusive(
    mock_post: mock.MagicMock,
) -> None:
    webhook_id, webhook_token = _tokens()

    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    body = "Body includes <@111> <@&222> @everyone but must be ignored"
    results = NotifyFluxer.parse_url(
        f"fluxer://{webhook_id}/{webhook_token}/"
        "?format=html"
        "&ping=<@333>,<@%26444>,@joe"
    )
    obj = NotifyFluxer(**results)

    assert obj.send(body=body) is True
    payload = loads(mock_post.call_args_list[0][1]["data"])

    assert set(payload["allow_mentions"]["users"]) == {"333"}
    assert set(payload["allow_mentions"]["roles"]) == {"444"}
    assert set(payload["allow_mentions"]["parse"]) == {"joe"}


@mock.patch("requests.post")
def test_plugin_fluxer_markdown_no_mentions_has_no_allow_mentions(
    mock_post: mock.MagicMock,
) -> None:
    webhook_id, webhook_token = _tokens()

    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = b""
    mock_post.return_value.headers = {}

    results = NotifyFluxer.parse_url(
        f"fluxer://{webhook_id}/{webhook_token}/?format=markdown"
    )
    obj = NotifyFluxer(**results)

    assert obj.send(body="Hello world") is True
    payload = loads(mock_post.call_args_list[0][1]["data"])

    assert "allow_mentions" not in payload
    assert "content" not in payload


@mock.patch("requests.post")
def test_plugin_fluxer_markdown_single_field_posts_once(
    mock_post: mock.MagicMock,
) -> None:
    webhook_id, webhook_token = _tokens()

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b""
    response.headers = {}
    mock_post.return_value = response

    NotifyFluxer.fluxer_max_fields = 10

    body = "# H1\nv1\n"
    obj = Apprise.instantiate(
        f"fluxer://{webhook_id}/{webhook_token}/?format=markdown&fields=yes"
    )
    assert isinstance(obj, NotifyFluxer)

    assert obj.send(body=body) is True
    assert mock_post.call_count == 1


@mock.patch("requests.post")
def test_plugin_fluxer_threading(mock_post: mock.MagicMock) -> None:
    """Threading passes thread_id parameter."""

    webhook_id, webhook_token = _tokens()

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b""
    response.headers = {}
    mock_post.return_value = response

    a = Apprise()
    assert (
        a.add(
            f"fluxer://{webhook_id}/{webhook_token}/"
            "?thread=12345&thread_name=abc"
        )
        is True
    )

    assert a.notify(body="test", title="title") is True

    kwargs = mock_post.call_args_list[0][1]
    assert "params" in kwargs
    assert kwargs["params"].get("thread_id") == "12345"

    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload.get("thread_name") == "abc"

    assert "thread_name=abc" in a[0].url()
    assert "thread=12345" in a[0].url()


@mock.patch("requests.post")
@mock.patch("time.sleep")
@mock.patch("builtins.open")
def test_plugin_fluxer_429_attachment_closes_edge_cases(
    mock_open: mock.MagicMock,
    mock_sleep: mock.MagicMock,
    mock_post: mock.MagicMock,
) -> None:
    """
    Cover 429 error during attachment upload triggers the pre-recursion close
    loop, and close() exceptions are suppressed.
    """

    mock_sleep.return_value = True

    webhook_id, webhook_token = _tokens()
    obj = NotifyFluxer(webhook_id=webhook_id, webhook_token=webhook_token)

    attach_path = os.path.join(TEST_VAR_DIR, "apprise-test.png")
    attach = AppriseAttachment(attach_path)

    class _BadCloseIO:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True
            raise OSError("boom")

    bad = _BadCloseIO()
    mock_open.return_value = bad

    def _resp(code: int, headers: dict[str, str] | None = None) -> mock.Mock:
        r = mock.Mock()
        r.status_code = code
        r.content = b""
        r.headers = headers or {}
        return r

    # 3 posts:
    #  (1) initial message post succeeds
    #  (2) attachment post 429 triggers file close-before-recursion
    #  (3) recursive retry succeeds (note: retry is non-attachment in baseline)
    mock_post.side_effect = [
        _resp(requests.codes.no_content, {}),
        _resp(requests.codes.too_many_requests, {"Retry-After": "1"}),
        _resp(requests.codes.no_content, {}),
    ]

    assert obj.send(body="test", attach=attach) is True
    assert bad.closed is True

    mock_post.reset_mock()
    mock_open.reset_mock()

    mock_sleep.reset_mock()
    mock_sleep.return_value = True

    webhook_id, webhook_token = _tokens()
    obj = NotifyFluxer(webhook_id=webhook_id, webhook_token=webhook_token)

    attach_path = os.path.join(TEST_VAR_DIR, "apprise-test.png")
    attach = AppriseAttachment(attach_path)

    class _GoodCloseIO:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    good = _GoodCloseIO()
    mock_open.return_value = good

    def _resp(code: int, headers: dict[str, str] | None = None) -> mock.Mock:
        r = mock.Mock()
        r.status_code = code
        r.content = b""
        r.headers = headers or {}
        return r

    mock_post.side_effect = [
        _resp(requests.codes.no_content, {}),
        _resp(requests.codes.too_many_requests, {"Retry-After": "1"}),
        _resp(requests.codes.no_content, {}),
    ]

    assert obj.send(body="test", attach=attach) is True
    assert good.closed is True


@mock.patch("requests.post")
def test_plugin_fluxer_attach_memory(mock_post: mock.MagicMock) -> None:
    """Regression: AttachMemory must be sendable without OSError."""
    from apprise.attachment.memory import AttachMemory

    webhook_id, webhook_token = _tokens()

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b""
    mock_post.return_value = response

    obj = Apprise.instantiate(f"fluxer://{webhook_id}/{webhook_token}/")

    mem = AttachMemory(
        content=b"<html><body><h1>Test</h1></body></html>",
        name="report.html",
        mimetype="text/html",
    )

    assert obj.notify(body="Test", attach=mem) is True
    assert mock_post.call_count >= 1
