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
from apprise.plugins.discord import NotifyDiscord

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# Our Testing URLs
apprise_url_tests = (
    (
        "discord://",
        {
            "instance": TypeError,
        },
    ),
    # An invalid url
    (
        "discord://:@/",
        {
            "instance": TypeError,
        },
    ),
    # No webhook_token specified
    (
        "discord://%s" % ("i" * 24),
        {
            "instance": TypeError,
        },
    ),
    # Provide both an webhook id and a webhook token
    (
        "discord://{}/{}".format("i" * 24, "t" * 64),
        {
            "instance": NotifyDiscord,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    # Provide a temporary username
    (
        "discord://l2g@{}/{}".format("i" * 24, "t" * 64),
        {
            "instance": NotifyDiscord,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    # test image= field
    (
        "discord://{}/{}?format=markdown&footer=Yes&image=Yes&ping=Joe".format(
            "i" * 24, "t" * 64
        ),
        {
            "instance": NotifyDiscord,
            "requests_response_code": requests.codes.no_content,
            # don't include an image by default
            "include_image": False,
        },
    ),
    (
        "discord://{}/{}?format=markdown&footer=Yes&image=No&fields=no".format(
            "i" * 24, "t" * 64
        ),
        {
            "instance": NotifyDiscord,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    (
        "discord://jack@{}/{}?format=markdown&footer=Yes&image=Yes".format(
            "i" * 24, "t" * 64
        ),
        {
            "instance": NotifyDiscord,
            "requests_response_code": requests.codes.no_content,
            "privacy_url": "discord://jack@i...i/t...t/",
        },
    ),
    (
        "https://discord.com/api/webhooks/{}/{}".format("0" * 10, "B" * 40),
        {
            # Native URL Support, support the provided discord URL from their
            # webpage.
            "instance": NotifyDiscord,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    (
        "https://discordapp.com/api/webhooks/{}/{}".format("0" * 10, "B" * 40),
        {
            # Legacy Native URL Support, support the older URL (to be
            # decomissioned on Nov 7th 2020)
            "instance": NotifyDiscord,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    (
        "https://discordapp.com/api/webhooks/{}/{}?footer=yes".format(
            "0" * 10, "B" * 40
        ),
        {
            # Native URL Support with arguments
            "instance": NotifyDiscord,
            "requests_response_code": requests.codes.no_content,
            "privacy_url": "discord://0...0/B...B/",
        },
    ),
    (
        "https://discordapp.com/api/webhooks/{}/{}?footer=yes&botname=joe".format(
            "0" * 10, "B" * 40
        ),
        {
            # Native URL Support with arguments
            "instance": NotifyDiscord,
            "requests_response_code": requests.codes.no_content,
            "privacy_url": "discord://joe@0...0/B...B/",
        },
    ),
    (
        "discord://{}/{}?format=markdown&avatar=No&footer=No".format(
            "i" * 24, "t" * 64
        ),
        {
            "instance": NotifyDiscord,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    (
        "discord://{}/{}?flags=1".format("i" * 24, "t" * 64),
        {
            "instance": NotifyDiscord,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    (
        "discord://{}/{}?flags=-1".format("i" * 24, "t" * 64),
        {
            # invalid flags specified (variation 1)
            "instance": TypeError,
        },
    ),
    (
        "discord://{}/{}?flags=invalid".format("i" * 24, "t" * 64),
        {
            # invalid flags specified (variation 2)
            "instance": TypeError,
        },
    ),
    # different format support
    (
        "discord://{}/{}?format=markdown".format("i" * 24, "t" * 64),
        {
            "instance": NotifyDiscord,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    # Thread ID
    (
        "discord://{}/{}?format=markdown&thread=abc123".format(
            "i" * 24, "t" * 64
        ),
        {
            "instance": NotifyDiscord,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    (
        "discord://{}/{}?format=text".format("i" * 24, "t" * 64),
        {
            "instance": NotifyDiscord,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    # Test with href (title link)
    (
        "discord://{}/{}?hmarkdown=true&ref=http://localhost".format(
            "i" * 24, "t" * 64
        ),
        {
            "instance": NotifyDiscord,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    # Test with url (title link) - Alias of href
    (
        "discord://{}/{}?markdown=true&url=http://localhost".format(
            "i" * 24, "t" * 64
        ),
        {
            "instance": NotifyDiscord,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    # Test with avatar URL
    (
        "discord://{}/{}?avatar_url=http://localhost/test.jpg".format(
            "i" * 24, "t" * 64
        ),
        {
            "instance": NotifyDiscord,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    # Test without image set
    (
        "discord://{}/{}".format("i" * 24, "t" * 64),
        {
            "instance": NotifyDiscord,
            "requests_response_code": requests.codes.no_content,
            # don't include an image by default
            "include_image": False,
        },
    ),
    # Test batch attachment mode enabled (default)
    (
        "discord://{}/{}?batch=yes".format("i" * 24, "t" * 64),
        {
            "instance": NotifyDiscord,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    # Test batch attachment mode disabled (legacy one-per-message)
    (
        "discord://{}/{}?batch=no".format("i" * 24, "t" * 64),
        {
            "instance": NotifyDiscord,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    (
        "discord://{}/{}/".format("a" * 24, "b" * 64),
        {
            "instance": NotifyDiscord,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "discord://{}/{}/".format("a" * 24, "b" * 64),
        {
            "instance": NotifyDiscord,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "discord://{}/{}/".format("a" * 24, "b" * 64),
        {
            "instance": NotifyDiscord,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_discord_urls():
    """NotifyDiscord() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_discord_notifications(mock_post):
    """NotifyDiscord() Notifications/Ping Support."""

    # Initialize some generic (but valid) tokens
    webhook_id = "A" * 24
    webhook_token = "B" * 64

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    # Test our header parsing when not lead with a header
    body = """
    # Heading
    @everyone and @admin, wake and meet our new user <@123>; <@&456>"
    """

    results = NotifyDiscord.parse_url(
        f"discord://{webhook_id}/{webhook_token}/?format=markdown"
    )

    assert isinstance(results, dict)
    assert results["user"] is None
    assert results["webhook_id"] == webhook_id
    assert results["webhook_token"] == webhook_token
    assert results["password"] is None
    assert results["port"] is None
    assert results["host"] == webhook_id
    assert results["fullpath"] == f"/{webhook_token}/"
    assert results["path"] == f"/{webhook_token}/"
    assert results["query"] is None
    assert results["schema"] == "discord"
    assert results["url"] == f"discord://{webhook_id}/{webhook_token}/"

    instance = NotifyDiscord(**results)
    assert isinstance(instance, NotifyDiscord)

    response = instance.send(body=body)
    assert response is True
    assert mock_post.call_count == 1

    details = mock_post.call_args_list[0]
    assert (
        details[0][0]
        == f"https://discord.com/api/webhooks/{webhook_id}/{webhook_token}"
    )

    payload = loads(details[1]["data"])

    assert "allow_mentions" in payload
    assert "users" in payload["allow_mentions"]
    assert len(payload["allow_mentions"]["users"]) == 1
    assert "123" in payload["allow_mentions"]["users"]
    assert "roles" in payload["allow_mentions"]
    assert len(payload["allow_mentions"]["roles"]) == 1
    assert "456" in payload["allow_mentions"]["roles"]
    assert "parse" in payload["allow_mentions"]
    assert len(payload["allow_mentions"]["parse"]) == 2
    assert "everyone" in payload["allow_mentions"]["parse"]
    assert "admin" in payload["allow_mentions"]["parse"]

    # Reset our object
    mock_post.reset_mock()

    results = NotifyDiscord.parse_url(
        f"discord://{webhook_id}/{webhook_token}/?format=text"
    )

    assert isinstance(results, dict)
    assert results["user"] is None
    assert results["webhook_id"] == webhook_id
    assert results["webhook_token"] == webhook_token
    assert results["password"] is None
    assert results["port"] is None
    assert results["host"] == webhook_id
    assert results["fullpath"] == f"/{webhook_token}/"
    assert results["path"] == f"/{webhook_token}/"
    assert results["query"] is None
    assert results["schema"] == "discord"
    assert results["url"] == f"discord://{webhook_id}/{webhook_token}/"

    instance = NotifyDiscord(**results)
    assert isinstance(instance, NotifyDiscord)

    response = instance.send(body=body)
    assert response is True
    assert mock_post.call_count == 1

    details = mock_post.call_args_list[0]
    assert (
        details[0][0]
        == f"https://discord.com/api/webhooks/{webhook_id}/{webhook_token}"
    )

    payload = loads(details[1]["data"])

    # text mode does not ping unless ping is explicitly set to someone
    assert "allow_mentions" not in payload

    # Reset our object
    mock_post.reset_mock()

    # Test our header parsing when not lead with a header
    body = """ """

    results = NotifyDiscord.parse_url(
        # & -> %26 for role otherwise & separates our URL from further parsing
        f"discord://{webhook_id}/{webhook_token}/?ping=@joe,<@321>,<@%26654>"
    )

    assert isinstance(results, dict)
    assert results["user"] is None
    assert results["webhook_id"] == webhook_id
    assert results["webhook_token"] == webhook_token
    assert results["password"] is None
    assert results["port"] is None
    assert results["host"] == webhook_id
    assert results["fullpath"] == f"/{webhook_token}/"
    assert results["path"] == f"/{webhook_token}/"
    assert results["query"] is None
    assert results["schema"] == "discord"
    assert results["url"] == f"discord://{webhook_id}/{webhook_token}/"
    instance = NotifyDiscord(**results)
    assert isinstance(instance, NotifyDiscord)

    response = instance.send(body=body)
    assert response is True
    assert mock_post.call_count == 1

    details = mock_post.call_args_list[0]
    assert (
        details[0][0]
        == f"https://discord.com/api/webhooks/{webhook_id}/{webhook_token}"
    )

    payload = loads(details[1]["data"])

    assert "allow_mentions" in payload
    assert len(payload["allow_mentions"]["users"]) == 1
    assert "321" in payload["allow_mentions"]["users"]
    assert "<@321>" in payload["content"]
    assert len(payload["allow_mentions"]["roles"]) == 1
    assert "654" in payload["allow_mentions"]["roles"]
    assert "<@&654>" in payload["content"]
    assert len(payload["allow_mentions"]["parse"]) == 1
    assert "joe" in payload["allow_mentions"]["parse"]
    assert "@joe" in payload["content"]

    # Reset our object
    mock_post.reset_mock()

    # Test our body in text mode, with ping=set
    body = """
    # Heading
    @everyone and @admin, wake and meet our new user <@123>; <@&456>"
    """

    results = NotifyDiscord.parse_url(
        # & -> %26 for role otherwise & separates our URL from further parsing
        f"discord://{webhook_id}/{webhook_token}/?ping=@joe,<@321>,<@%26654>"
        "&format=text"
    )

    assert isinstance(results, dict)
    assert results["user"] is None
    assert results["webhook_id"] == webhook_id
    assert results["webhook_token"] == webhook_token
    assert results["password"] is None
    assert results["port"] is None
    assert results["host"] == webhook_id
    assert results["fullpath"] == f"/{webhook_token}/"
    assert results["path"] == f"/{webhook_token}/"
    assert results["query"] is None
    assert results["schema"] == "discord"
    assert results["url"] == f"discord://{webhook_id}/{webhook_token}/"

    instance = NotifyDiscord(**results)
    assert isinstance(instance, NotifyDiscord)

    response = instance.send(body=body)
    assert response is True
    assert mock_post.call_count == 1

    details = mock_post.call_args_list[0]
    assert (
        details[0][0]
        == f"https://discord.com/api/webhooks/{webhook_id}/{webhook_token}"
    )

    payload = loads(details[1]["data"])

    # Payload only includes elements on ping= line with text mode
    assert "allow_mentions" in payload
    assert "users" in payload["allow_mentions"]
    assert len(payload["allow_mentions"]["users"]) == 1
    assert "321" in payload["allow_mentions"]["users"]
    assert "roles" in payload["allow_mentions"]
    assert len(payload["allow_mentions"]["roles"]) == 1
    assert "654" in payload["allow_mentions"]["roles"]
    assert "parse" in payload["allow_mentions"]
    assert len(payload["allow_mentions"]["parse"]) == 1
    assert "joe" in payload["allow_mentions"]["parse"]


@mock.patch("requests.post")
@mock.patch("time.sleep")
def test_plugin_discord_general(mock_sleep, mock_post):
    """NotifyDiscord() General Checks."""

    # Prevent throttling
    mock_sleep.return_value = True

    # Turn off clock skew for local testing
    NotifyDiscord.clock_skew = timedelta(seconds=0)

    # Epoch time:
    epoch = datetime.fromtimestamp(0, timezone.utc)

    # Initialize some generic (but valid) tokens
    webhook_id = "A" * 24
    webhook_token = "B" * 64

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = ""
    mock_post.return_value.headers = {
        "X-RateLimit-Reset": (
            (datetime.now(timezone.utc) - epoch).total_seconds()
        ),
        "X-RateLimit-Remaining": 1,
    }

    # Invalid webhook id
    with pytest.raises(TypeError):
        NotifyDiscord(webhook_id=None, webhook_token=webhook_token)
    # Invalid webhook id (whitespace)
    with pytest.raises(TypeError):
        NotifyDiscord(webhook_id="  ", webhook_token=webhook_token)

    # Invalid webhook token
    with pytest.raises(TypeError):
        NotifyDiscord(webhook_id=webhook_id, webhook_token=None)
    # Invalid webhook token (whitespace)
    with pytest.raises(TypeError):
        NotifyDiscord(webhook_id=webhook_id, webhook_token="   ")

    obj = NotifyDiscord(
        webhook_id=webhook_id,
        webhook_token=webhook_token,
        footer=True,
        thumbnail=False,
    )
    assert obj.ratelimit_remaining == 1

    # Test that we get a string response
    assert isinstance(obj.url(), str) is True

    # This call includes an image with it's payload:
    assert (
        bool(
            obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        )
        is True
    )

    # Force a case where there are no more remaining posts allowed
    mock_post.return_value.headers = {
        "X-RateLimit-Reset": (
            (datetime.now(timezone.utc) - epoch).total_seconds()
        ),
        "X-RateLimit-Remaining": 0,
    }

    # This call includes an image with it's payload:
    assert (
        bool(
            obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        )
        is True
    )

    # behind the scenes, it should cause us to update our rate limit
    assert obj.send(body="test") is True
    assert obj.ratelimit_remaining == 0

    # This should cause us to block
    mock_post.return_value.headers = {
        "X-RateLimit-Reset": (
            (datetime.now(timezone.utc) - epoch).total_seconds()
        ),
        "X-RateLimit-Remaining": 10,
    }
    assert obj.send(body="test") is True
    assert obj.ratelimit_remaining == 10

    # Reset our variable back to 1
    mock_post.return_value.headers = {
        "X-RateLimit-Reset": (
            (datetime.now(timezone.utc) - epoch).total_seconds()
        ),
        "X-RateLimit-Remaining": 1,
    }
    # Handle cases where our epoch time is wrong
    del mock_post.return_value.headers["X-RateLimit-Reset"]
    assert obj.send(body="test") is True

    # Return our object, but place it in the future forcing us to block
    mock_post.return_value.headers = {
        "X-RateLimit-Reset": (
            (datetime.now(timezone.utc) - epoch).total_seconds() + 1
        ),
        "X-RateLimit-Remaining": 0,
    }

    obj.ratelimit_remaining = 0
    assert obj.send(body="test") is True

    # Test 429 error response
    mock_post.return_value.status_code = requests.codes.too_many_requests

    # The below will attempt a second transmission and fail (because we didn't
    # set up a second post request to pass) :)
    assert obj.send(body="test") is False

    # Return our object, but place it in the future forcing us to block
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.headers = {
        "X-RateLimit-Reset": (
            (datetime.now(timezone.utc) - epoch).total_seconds() - 1
        ),
        "X-RateLimit-Remaining": 0,
    }
    assert obj.send(body="test") is True

    # Return our limits to always work
    obj.ratelimit_remaining = 1

    # Return our headers to normal
    mock_post.return_value.headers = {
        "X-RateLimit-Reset": (
            (datetime.now(timezone.utc) - epoch).total_seconds()
        ),
        "X-RateLimit-Remaining": 1,
    }

    # This call includes an image with it's payload:
    assert (
        bool(
            obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        )
        is True
    )

    # Simple Markdown Single line of text
    test_markdown = "body"
    desc, results = obj.extract_markdown_sections(test_markdown)
    assert isinstance(results, list) is True
    assert len(results) == 0

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
            f"discord://{webhook_id}/{webhook_token}/"
            "?format=markdown&footer=Yes"
        )
        is True
    )

    # This call includes an image with it's payload:
    NotifyDiscord.discord_max_fields = 1

    assert (
        bool(
            a.notify(
                body=test_markdown,
                title="title",
                notify_type=NotifyType.INFO,
                body_format=NotifyFormat.TEXT,
            )
        )
        is True
    )

    # Throw an exception on the forth call to requests.post()
    # This allows to test our batch field processing
    response = mock.Mock()
    response.content = ""
    response.status_code = requests.codes.ok
    mock_post.return_value = response
    mock_post.side_effect = [
        response,
        response,
        response,
        requests.RequestException(),
    ]

    # Test our markdown
    obj = Apprise.instantiate(
        f"discord://{webhook_id}/{webhook_token}/?format=markdown"
    )
    assert isinstance(obj, NotifyDiscord)
    assert (
        bool(
            obj.notify(
                body=test_markdown, title="title", notify_type=NotifyType.INFO
            )
        )
        is False
    )
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
        bool(
            obj.notify(
                body=test_markdown, title="title", notify_type=NotifyType.INFO
            )
        )
        is True
    )

    # Create an apprise instance
    a = Apprise()

    # Our processing is slightly different when we aren't using markdown
    # as we do not pre-parse content during our notifications
    assert (
        a.add(
            f"discord://{webhook_id}/{webhook_token}/"
            "?format=markdown&footer=Yes"
        )
        is True
    )

    # This call includes an image with it's payload:
    assert (
        bool(
            a.notify(
                body=test_markdown,
                title="title",
                notify_type=NotifyType.INFO,
                body_format=NotifyFormat.TEXT,
            )
        )
        is True
    )

    assert (
        bool(
            a.notify(
                body=test_markdown,
                title="title",
                notify_type=NotifyType.INFO,
                body_format=NotifyFormat.MARKDOWN,
            )
        )
        is True
    )

    # Toggle our logo availability
    a.asset.image_url_logo = None
    assert (
        bool(a.notify(body="body", title="title", notify_type=NotifyType.INFO))
        is True
    )

    # Create an apprise instance
    a = Apprise()

    # Reset our object
    mock_post.reset_mock()

    # Test our threading
    assert (
        a.add(f"discord://{webhook_id}/{webhook_token}/?thread=12345") is True
    )

    # This call includes an image with it's payload:
    assert bool(a.notify(body="test", title="title")) is True

    assert mock_post.call_count == 1
    response = mock_post.call_args_list[0][1]
    assert "params" in response
    assert response["params"].get("thread_id") == "12345"


@mock.patch("requests.post")
def test_plugin_discord_overflow(mock_post):
    """NotifyDiscord() Overflow Checks."""

    # Initialize some generic (but valid) tokens
    webhook_id = "A" * 24
    webhook_token = "B" * 64

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

    results = NotifyDiscord.parse_url(
        f"discord://{webhook_id}/{webhook_token}/?overflow=split"
    )

    assert isinstance(results, dict)
    assert results["user"] is None
    assert results["webhook_id"] == webhook_id
    assert results["webhook_token"] == webhook_token
    assert results["password"] is None
    assert results["port"] is None
    assert results["host"] == webhook_id
    assert results["fullpath"] == f"/{webhook_token}/"
    assert results["path"] == f"/{webhook_token}/"
    assert results["query"] is None
    assert results["schema"] == "discord"
    assert results["url"] == f"discord://{webhook_id}/{webhook_token}/"

    instance = NotifyDiscord(**results)
    assert isinstance(instance, NotifyDiscord)

    results = instance._apply_overflow(
        body, title=title, overflow=OverflowMode.SPLIT
    )

    # Ensure we never exceed 2000 characters
    for entry in results:
        assert len(entry["title"]) <= instance.title_maxlen
        assert len(entry["title"]) + len(entry["body"]) <= instance.body_maxlen


@mock.patch("requests.post")
def test_plugin_discord_markdown_extra(mock_post):
    """NotifyDiscord() Markdown Extra Checks."""

    # Initialize some generic (but valid) tokens
    webhook_id = "A" * 24
    webhook_token = "B" * 64

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    # Reset our apprise object
    a = Apprise()

    # We want to further test our markdown support to accommodate bug rased on
    # 2022.10.25; see https://github.com/caronc/apprise/issues/717
    assert (
        a.add(
            f"discord://{webhook_id}/{webhook_token}/"
            "?format=markdown&footer=Yes"
        )
        is True
    )

    test_markdown = "[green-blue](https://google.com)"

    # This call includes an image with it's payload:
    assert (
        bool(
            a.notify(
                body=test_markdown,
                title="title",
                notify_type=NotifyType.INFO,
                body_format=NotifyFormat.TEXT,
            )
        )
        is True
    )

    assert (
        bool(a.notify(body="body", title="title", notify_type=NotifyType.INFO))
        is True
    )


@mock.patch("requests.post")
def test_plugin_discord_attachments(mock_post):
    """NotifyDiscord() Attachment Checks."""

    # Initialize some generic (but valid) tokens
    webhook_id = "C" * 24
    webhook_token = "D" * 64

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
        f"discord://{webhook_id}/{webhook_token}/?format=markdown"
    )

    # attach our content
    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.gif"))

    assert (
        bool(
            obj.notify(
                body="body",
                title="title",
                notify_type=NotifyType.INFO,
                attach=attach,
            )
        )
        is True
    )

    # Test our call count
    assert mock_post.call_count == 2
    assert (
        mock_post.call_args_list[0][0][0]
        == f"https://discord.com/api/webhooks/{webhook_id}/{webhook_token}"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == f"https://discord.com/api/webhooks/{webhook_id}/{webhook_token}"
    )

    # Reset our object
    mock_post.reset_mock()

    # Test notifications with mentions and attachments in it
    assert (
        bool(
            obj.notify(
                body="Say hello to <@1234>!",
                notify_type=NotifyType.INFO,
                attach=attach,
            )
        )
        is True
    )

    # Test our call count
    assert mock_post.call_count == 2
    assert (
        mock_post.call_args_list[0][0][0]
        == f"https://discord.com/api/webhooks/{webhook_id}/{webhook_token}"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == f"https://discord.com/api/webhooks/{webhook_id}/{webhook_token}"
    )

    # Reset our object
    mock_post.reset_mock()

    # An invalid attachment will cause a failure
    path = os.path.join(TEST_VAR_DIR, "/invalid/path/to/an/invalid/file.jpg")
    attach = AppriseAttachment(path)
    assert (
        bool(
            obj.notify(
                body="body",
                title="title",
                notify_type=NotifyType.INFO,
                attach=path,
            )
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
def test_plugin_discord_markdown_fields_batches_exactly(mock_post):
    webhook_id = "A" * 24
    webhook_token = "B" * 64

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = ""
    response.headers = {}
    mock_post.return_value = response

    # Force tiny batches
    NotifyDiscord.discord_max_fields = 1

    body = "# H1\nv1\n# H2\nv2\n# H3\nv3\n"
    obj = Apprise.instantiate(
        f"discord://{webhook_id}/{webhook_token}/?format=markdown&fields=yes"
    )
    assert isinstance(obj, NotifyDiscord)

    assert obj.send(body=body) is True

    # H1, H2, H3 => 3 fields => 3 posts (since max_fields=1)
    assert mock_post.call_count == 3


@mock.patch("requests.post")
def test_plugin_discord_markdown_ping_is_additive(mock_post):
    webhook_id = "A" * 24
    webhook_token = "B" * 64

    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    body = "Body pings <@111> and <@&222> @everyone"
    results = NotifyDiscord.parse_url(
        f"discord://{webhook_id}/{webhook_token}/"
        "?format=markdown"
        "&ping=<@333>,<@%26444>,@joe"
    )
    obj = NotifyDiscord(**results)

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
def test_plugin_discord_html_ping_is_exclusive(mock_post):
    webhook_id = "A" * 24
    webhook_token = "B" * 64

    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    body = "Body includes <@111> <@&222> @everyone but must be ignored"
    results = NotifyDiscord.parse_url(
        f"discord://{webhook_id}/{webhook_token}/"
        "?format=html"
        "&ping=<@333>,<@%26444>,@joe"
    )
    obj = NotifyDiscord(**results)

    assert obj.send(body=body) is True
    payload = loads(mock_post.call_args_list[0][1]["data"])

    assert set(payload["allow_mentions"]["users"]) == {"333"}
    assert set(payload["allow_mentions"]["roles"]) == {"444"}
    assert set(payload["allow_mentions"]["parse"]) == {"joe"}


@mock.patch("requests.post")
def test_plugin_discord_markdown_no_mentions_has_no_allow_mentions(mock_post):
    webhook_id = "A" * 24
    webhook_token = "B" * 64

    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    results = NotifyDiscord.parse_url(
        f"discord://{webhook_id}/{webhook_token}/?format=markdown"
    )
    obj = NotifyDiscord(**results)

    assert obj.send(body="Hello world") is True
    payload = loads(mock_post.call_args_list[0][1]["data"])

    assert "allow_mentions" not in payload
    assert "content" not in payload


@mock.patch("requests.post")
def test_plugin_discord_markdown_single_field_posts_once(mock_post):
    webhook_id = "A" * 24
    webhook_token = "B" * 64

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = ""
    response.headers = {}
    mock_post.return_value = response

    NotifyDiscord.discord_max_fields = 10

    body = "# H1\nv1\n"
    obj = Apprise.instantiate(
        f"discord://{webhook_id}/{webhook_token}/?format=markdown&fields=yes"
    )
    assert obj.send(body=body) is True
    assert mock_post.call_count == 1


@mock.patch("requests.post")
def test_plugin_discord_attach_memory(mock_post):
    """Regression: AttachMemory must be sendable without OSError."""
    from apprise.attachment.memory import AttachMemory

    webhook_id = "C" * 24
    webhook_token = "D" * 64

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b""
    mock_post.return_value = response

    obj = Apprise.instantiate(f"discord://{webhook_id}/{webhook_token}/")

    mem = AttachMemory(
        content=b"<html><body><h1>Test</h1></body></html>",
        name="report.html",
        mimetype="text/html",
    )

    assert bool(obj.notify(body="Test", attach=mem)) is True
    assert mock_post.call_count >= 1


@mock.patch("requests.post")
def test_plugin_discord_html_to_markdown_format(mock_post):
    """NotifyDiscord(): HTML body is converted to Markdown."""

    webhook_id = "A" * 24
    webhook_token = "B" * 64

    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = ""
    mock_post.return_value.headers = {}

    # Instantiate a Discord plugin in Markdown mode with fields
    # disabled so the body lands in embeds[0]["description"] directly
    obj = Apprise.instantiate(
        f"discord://{webhook_id}/{webhook_token}/?format=markdown&fields=no"
    )

    aobj = Apprise()
    aobj.add(obj)

    # Notify with an HTML body; the framework should convert it
    # to Markdown before dispatching to Discord
    assert (
        bool(
            aobj.notify(
                body="<b>hello</b> <i>world</i>",
                body_format=NotifyFormat.HTML,
            )
        )
        is True
    )
    assert mock_post.call_count == 1

    # The body must arrive in the embed description as Markdown,
    # not as stripped plain text
    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload["embeds"][0]["description"] == "**hello** *world*"


@mock.patch("requests.post")
def test_plugin_discord_template_content(mock_post, tmpdir):
    """NotifyDiscord() template with 'content' field."""

    webhook_id = "A" * 24
    webhook_token = "B" * 64

    # Prepare a good mock response
    mock_post.return_value = mock.Mock(
        status_code=requests.codes.ok,
        content=b"",
        headers={},
    )

    # Write a minimal Discord webhook template to disk
    template = tmpdir.join("discord.json")
    template.write('{"content": "{{app_body}}"}')

    # Instantiate via URL with template path
    obj = Apprise.instantiate(
        "discord://{}/{}/".format(webhook_id, webhook_token)
        + "?template={}".format(str(template))
    )
    assert isinstance(obj, NotifyDiscord)

    # Verify the template was loaded
    assert obj.template

    # Notification must succeed
    assert (
        bool(
            obj.notify(
                body="hello", title="world", notify_type=NotifyType.INFO
            )
        )
        is True
    )
    assert mock_post.called is True

    # Verify the payload sent - content field contains the body
    posted = loads(mock_post.call_args_list[0][1]["data"])
    assert posted["content"] == "hello"


@mock.patch("requests.post")
def test_plugin_discord_template_embeds(mock_post, tmpdir):
    """NotifyDiscord() template with 'embeds' field."""

    webhook_id = "A" * 24
    webhook_token = "B" * 64

    # Prepare a good mock response
    mock_post.return_value = mock.Mock(
        status_code=requests.codes.ok,
        content=b"",
        headers={},
    )

    # Write a template that uses the embeds structure
    template = tmpdir.join("embeds.json")
    template.write(
        '{"embeds": [{"title": "{{app_title}}", '
        '"description": "{{app_body}}"}]}'
    )

    # Instantiate via URL with template path
    obj = Apprise.instantiate(
        "discord://{}/{}/".format(webhook_id, webhook_token)
        + "?template={}".format(str(template))
    )
    assert isinstance(obj, NotifyDiscord)
    assert obj.template

    # Notification must succeed
    assert (
        bool(
            obj.notify(
                body="my body", title="my title", notify_type=NotifyType.INFO
            )
        )
        is True
    )
    assert mock_post.called is True

    # Verify the embed payload
    posted = loads(mock_post.call_args_list[0][1]["data"])
    assert "embeds" in posted
    assert posted["embeds"][0]["title"] == "my title"
    assert posted["embeds"][0]["description"] == "my body"


def test_plugin_discord_template_tokens(tmpdir):
    """NotifyDiscord() template tokens and URL round-trip."""

    webhook_id = "A" * 24
    webhook_token = "B" * 64

    # Write a minimal content template to disk
    template = tmpdir.join("discord.json")
    template.write('{"content": "{{app_body}}"}')

    # Instantiate with explicit tokens dict
    obj = NotifyDiscord(
        webhook_id=webhook_id,
        webhook_token=webhook_token,
        template=str(template),
        tokens={"mykey": "myval", "count": "42"},
    )
    assert obj.template
    assert obj.tokens["mykey"] == "myval"
    assert obj.tokens["count"] == "42"

    # Round-trip through url() and parse_url()
    url = obj.url()
    result = NotifyDiscord.parse_url(url)
    assert result is not None
    assert "mykey" in result["tokens"]
    assert result["tokens"]["mykey"] == "myval"

    obj2 = NotifyDiscord(**result)
    assert obj2.template
    assert obj2.tokens.get("mykey") == "myval"
    assert obj2.url_identifier == obj.url_identifier


def test_plugin_discord_template_token_invalid():
    """NotifyDiscord() non-dict tokens raises TypeError."""

    webhook_id = "A" * 24
    webhook_token = "B" * 64

    with pytest.raises(TypeError):
        NotifyDiscord(
            webhook_id=webhook_id,
            webhook_token=webhook_token,
            tokens="not-a-dict",
        )


def test_plugin_discord_template_add_failure():
    """NotifyDiscord() template add() failure raises TypeError."""

    webhook_id = "A" * 24
    webhook_token = "B" * 64

    # Force add() to report failure so len(self.template) == 0
    with (
        mock.patch(
            "apprise.plugins.discord.AppriseAttachment.add",
            return_value=False,
        ),
        pytest.raises(TypeError),
    ):
        NotifyDiscord(
            webhook_id=webhook_id,
            webhook_token=webhook_token,
            template="file:///some/template.json",
        )


@mock.patch("requests.post")
def test_plugin_discord_template_inaccessible(mock_post, tmpdir):
    """NotifyDiscord() inaccessible template fails gracefully."""

    webhook_id = "A" * 24
    webhook_token = "B" * 64

    # Prepare a mock response (should never be called)
    mock_post.return_value = mock.Mock(
        status_code=requests.codes.ok,
        content=b"",
        headers={},
    )

    # Create the template so that add() succeeds during init
    template = tmpdir.join("discord.json")
    template.write('{"content": "{{app_body}}"}')

    obj = Apprise.instantiate(
        "discord://{}/{}/".format(webhook_id, webhook_token)
        + "?template={}".format(str(template))
    )
    assert isinstance(obj, NotifyDiscord)

    # Remove the file so the template becomes inaccessible
    os.remove(str(template))

    # Notification must fail; no HTTP call should be made
    assert (
        bool(obj.notify(body="test", title="t", notify_type=NotifyType.INFO))
        is False
    )
    assert mock_post.called is False


@mock.patch("requests.post")
def test_plugin_discord_template_oserror(mock_post, tmpdir):
    """NotifyDiscord() OSError during template read fails gracefully."""

    webhook_id = "A" * 24
    webhook_token = "B" * 64

    # Prepare a mock response (should never be called)
    mock_post.return_value = mock.Mock(
        status_code=requests.codes.ok,
        content=b"",
        headers={},
    )

    # Write a file so the attachment resolves but open() will be mocked
    template = tmpdir.join("discord.json")
    template.write('{"content": "hello"}')

    obj = Apprise.instantiate(
        "discord://{}/{}/".format(webhook_id, webhook_token)
        + "?template={}".format(str(template))
    )
    assert isinstance(obj, NotifyDiscord)

    # Patch open() to raise OSError when the template is read
    with mock.patch("builtins.open", side_effect=OSError):
        assert (
            bool(
                obj.notify(body="test", title="t", notify_type=NotifyType.INFO)
            )
            is False
        )
    assert mock_post.called is False


@mock.patch("requests.post")
def test_plugin_discord_template_invalid_json(mock_post, tmpdir):
    """NotifyDiscord() invalid JSON template fails gracefully."""

    webhook_id = "A" * 24
    webhook_token = "B" * 64

    # Prepare a mock response (should never be called)
    mock_post.return_value = mock.Mock(
        status_code=requests.codes.ok,
        content=b"",
        headers={},
    )

    # Write a syntactically invalid JSON file
    template = tmpdir.join("bad.json")
    template.write("{ not valid json }")

    obj = Apprise.instantiate(
        "discord://{}/{}/".format(webhook_id, webhook_token)
        + "?template={}".format(str(template))
    )
    assert isinstance(obj, NotifyDiscord)

    # Notification must fail due to parse error
    assert (
        bool(obj.notify(body="test", title="t", notify_type=NotifyType.INFO))
        is False
    )
    assert mock_post.called is False


@mock.patch("requests.post")
def test_plugin_discord_template_not_dict(mock_post, tmpdir):
    """NotifyDiscord() template root must be a JSON object, not array."""

    webhook_id = "A" * 24
    webhook_token = "B" * 64

    # Prepare a mock response (should never be called)
    mock_post.return_value = mock.Mock(
        status_code=requests.codes.ok,
        content=b"",
        headers={},
    )

    # Write a JSON array instead of an object
    template = tmpdir.join("array.json")
    template.write('[{"content": "hello"}]')

    obj = Apprise.instantiate(
        "discord://{}/{}/".format(webhook_id, webhook_token)
        + "?template={}".format(str(template))
    )
    assert isinstance(obj, NotifyDiscord)

    # Notification must fail because the root is not a dict
    assert (
        bool(obj.notify(body="test", title="t", notify_type=NotifyType.INFO))
        is False
    )
    assert mock_post.called is False


@mock.patch("requests.post")
def test_plugin_discord_template_payload_validation(mock_post, tmpdir):
    """NotifyDiscord() template payload field validation cases."""

    webhook_id = "A" * 24
    webhook_token = "B" * 64

    # Prepare a mock response (should never be called during failures)
    mock_post.return_value = mock.Mock(
        status_code=requests.codes.ok,
        content=b"",
        headers={},
    )

    template = tmpdir.join("t.json")

    # Case 1: no content and no embeds
    template.write('{"username": "bot"}')
    obj = Apprise.instantiate(
        "discord://{}/{}/".format(webhook_id, webhook_token)
        + "?template={}".format(str(template))
    )
    assert isinstance(obj, NotifyDiscord)
    assert (
        bool(obj.notify(body="test", title="t", notify_type=NotifyType.INFO))
        is False
    )
    assert mock_post.called is False

    # Case 2: content is an empty string
    template.write('{"content": ""}')
    obj = Apprise.instantiate(
        "discord://{}/{}/".format(webhook_id, webhook_token)
        + "?template={}".format(str(template))
    )
    assert isinstance(obj, NotifyDiscord)
    assert (
        bool(obj.notify(body="test", title="t", notify_type=NotifyType.INFO))
        is False
    )

    # Case 3: embeds is an empty list
    template.write('{"embeds": []}')
    obj = Apprise.instantiate(
        "discord://{}/{}/".format(webhook_id, webhook_token)
        + "?template={}".format(str(template))
    )
    assert isinstance(obj, NotifyDiscord)
    assert (
        bool(obj.notify(body="test", title="t", notify_type=NotifyType.INFO))
        is False
    )
    assert mock_post.called is False


@mock.patch("requests.post")
def test_plugin_discord_template_bad_embeds(mock_post, tmpdir):
    """NotifyDiscord() template embeds containing non-dict entries fails."""

    webhook_id = "A" * 24
    webhook_token = "B" * 64

    # Prepare a mock response (should never be called)
    mock_post.return_value = mock.Mock(
        status_code=requests.codes.ok,
        content=b"",
        headers={},
    )

    # Write a template where embeds contains a non-dict entry
    template = tmpdir.join("bad_embeds.json")
    template.write('{"embeds": ["not-a-dict"]}')

    obj = Apprise.instantiate(
        "discord://{}/{}/".format(webhook_id, webhook_token)
        + "?template={}".format(str(template))
    )
    assert isinstance(obj, NotifyDiscord)

    # Notification must fail because the embed entry is not a dict
    assert (
        bool(obj.notify(body="test", title="t", notify_type=NotifyType.INFO))
        is False
    )
    assert mock_post.called is False


@mock.patch("requests.post")
def test_plugin_discord_template_send_failure(mock_post, tmpdir):
    """NotifyDiscord() HTTP failure in template mode."""

    webhook_id = "A" * 24
    webhook_token = "B" * 64

    # Write a valid template
    template = tmpdir.join("discord.json")
    template.write('{"content": "hello"}')

    obj = Apprise.instantiate(
        "discord://{}/{}/".format(webhook_id, webhook_token)
        + "?template={}".format(str(template))
    )
    assert isinstance(obj, NotifyDiscord)

    # Simulate an HTTP error response
    mock_post.return_value = mock.Mock(
        status_code=requests.codes.internal_server_error,
        content=b"",
        headers={},
    )
    assert (
        bool(obj.notify(body="test", title="t", notify_type=NotifyType.INFO))
        is False
    )
    assert mock_post.called is True


@mock.patch("requests.post")
def test_plugin_discord_template_with_attachments(mock_post, tmpdir):
    """NotifyDiscord() template mode still sends attachments."""

    webhook_id = "C" * 24
    webhook_token = "D" * 64

    # Write a valid template
    template = tmpdir.join("discord.json")
    template.write('{"content": "{{app_body}}"}')

    obj = Apprise.instantiate(
        "discord://{}/{}/".format(webhook_id, webhook_token)
        + "?template={}".format(str(template))
    )
    assert isinstance(obj, NotifyDiscord)

    # Prepare a good mock response for both the template call and attachment
    mock_post.return_value = mock.Mock(
        status_code=requests.codes.ok,
        content=b"",
        headers={},
    )

    # Attach a test file
    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.gif"))
    assert (
        bool(
            obj.notify(
                body="test",
                title="t",
                notify_type=NotifyType.INFO,
                attach=attach,
            )
        )
        is True
    )

    # Both the template message and the attachment should have been posted
    assert mock_post.call_count == 2


@mock.patch("requests.post")
def test_plugin_discord_attach_multi_batch(mock_post):
    """NotifyDiscord() multi-attachment batching."""

    webhook_id = "C" * 24
    webhook_token = "D" * 64

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b""
    response.headers = {}
    mock_post.return_value = response

    obj = Apprise.instantiate(
        f"discord://{webhook_id}/{webhook_token}/?format=markdown"
    )
    assert isinstance(obj, NotifyDiscord)
    assert obj.batch is True

    # Three test attachments
    gif = os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    png = os.path.join(TEST_VAR_DIR, "apprise-test.png")
    jpg = os.path.join(TEST_VAR_DIR, "apprise-test.jpeg")
    attach = AppriseAttachment([gif, png, jpg])

    # Default batch mode: all 3 files go in one POST (plus 1 for the message)
    assert obj.send(body="test", attach=attach) is True
    assert mock_post.call_count == 2
    mock_post.reset_mock()

    # Reduce max per batch to 1: each file gets its own POST (4 calls total)
    obj.discord_max_attachments = 1
    assert obj.send(body="test", attach=attach) is True
    assert mock_post.call_count == 4
    mock_post.reset_mock()
    obj.discord_max_attachments = 10

    # Size-based split: force a tiny per-batch byte budget
    obj.discord_max_attach_bytes = 1
    assert obj.send(body="test", attach=attach) is True
    assert mock_post.call_count == 4
    mock_post.reset_mock()
    obj.discord_max_attach_bytes = 25 * 1024 * 1024

    # batch=False: reverts to legacy one-per-message regardless of max
    obj_no_batch = Apprise.instantiate(
        f"discord://{webhook_id}/{webhook_token}/?batch=no"
    )
    assert isinstance(obj_no_batch, NotifyDiscord)
    assert obj_no_batch.batch is False
    assert obj_no_batch.send(body="test", attach=attach) is True
    assert mock_post.call_count == 4
    mock_post.reset_mock()

    # URL round-trip preserves batch flag
    url_on = NotifyDiscord(
        webhook_id=webhook_id,
        webhook_token=webhook_token,
        batch=True,
    ).url()
    assert "batch=yes" in url_on
    url_off = NotifyDiscord(
        webhook_id=webhook_id,
        webhook_token=webhook_token,
        batch=False,
    ).url()
    assert "batch=no" in url_off
    parsed = NotifyDiscord.parse_url(url_off)
    assert parsed["batch"] is False

    # Guard 1: inaccessible file causes failure; body POST still goes out
    with mock.patch("os.path.isfile", return_value=False):
        assert obj.send(body="test", attach=attach) is False
    assert mock_post.call_count == 1
    mock_post.reset_mock()

    # Guard 2: OSError on open causes failure; body POST still goes out
    with mock.patch("builtins.open", side_effect=OSError()):
        assert obj.send(body="test", attach=attach) is False
    assert mock_post.call_count == 1
    mock_post.reset_mock()

    # HTTP error on the attachment batch POST; body POST succeeds
    bad_response = mock.Mock()
    bad_response.status_code = requests.codes.internal_server_error
    bad_response.content = b""
    bad_response.headers = {}
    mock_post.side_effect = [response, bad_response]
    assert obj.send(body="test", attach=attach) is False
    mock_post.side_effect = None
    mock_post.reset_mock()

    # RequestException on the attachment batch POST
    mock_post.side_effect = [response, requests.RequestException()]
    assert obj.send(body="test", attach=attach) is False
    mock_post.side_effect = None
    mock_post.reset_mock()

    # OSError raised by requests.post() during attachment send
    mock_post.side_effect = [response, OSError()]
    assert obj.send(body="test", attach=attach) is False
    mock_post.side_effect = None
    mock_post.reset_mock()

    # Partial batch failure: first batch (files 0+1) succeeds, second fails.
    # Set max=2 so 3 files split into [gif, png] and [jpg].
    obj.discord_max_attachments = 2
    mock_post.side_effect = [response, response, bad_response]
    assert obj.send(body="test", attach=attach) is False
    assert mock_post.call_count == 3
    mock_post.side_effect = None
    obj.discord_max_attachments = 10
