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
from json import dumps, loads
import logging
from unittest import mock
from urllib.parse import urlparse

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, NotifyFormat, NotifyType
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.github import GitHubKind, NotifyGitHub

logging.disable(logging.CRITICAL)

# A fake access token
TOKEN = "github_pat_11ABCDEFG0123456789_abcdef"

# Reusable successful GraphQL response
GRAPHQL_OK = dumps(
    {
        "data": {
            "repository": {
                "id": "R_1",
                "discussion": {"id": "D_1"},
                "discussionCategories": {
                    "nodes": [
                        {"id": "C_1", "name": "General", "slug": "general"},
                        {"id": "C_2", "name": "Ideas", "slug": "ideas"},
                    ]
                },
            }
        }
    }
)

# Our Testing URLs
apprise_url_tests = (
    # No owner
    (
        "github://",
        {
            "instance": None,
        },
    ),
    # No token
    (
        "github://caronc/apprise",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    # Invalid token characters
    (
        "github://bad%20token@caronc/apprise",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    # No repository
    (
        f"github://{TOKEN}@caronc",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    # Invalid owner
    (
        f"github://{TOKEN}@caronc_bad/apprise",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    # Invalid repository
    (
        f"github://{TOKEN}@caronc/bad%20repo",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    # Unsupported path
    (
        f"github://{TOKEN}@caronc/apprise/commit/abc123",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    # Pull request without a number
    (
        f"github://{TOKEN}@caronc/apprise/pull",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    # Issue that is not a number
    (
        f"github://{TOKEN}@caronc/apprise/issues/abc",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    # Two numbers would reach two places
    (
        f"github://{TOKEN}@caronc/apprise/issues/12/23",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    # A number after /new is refused too
    (
        f"github://{TOKEN}@caronc/apprise/issues/new/5",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    # Open a new issue
    (
        f"github://{TOKEN}@caronc/apprise",
        {
            "instance": NotifyGitHub,
            "requests_response_code": requests.codes.created,
            "privacy_url": "github://g...f@caronc/apprise/",
        },
    ),
    # Open a new issue with labels and assignees
    (
        f"github://{TOKEN}@caronc/apprise/issues/new"
        "?labels=bug,nightly&assignees=caronc",
        {
            "instance": NotifyGitHub,
            "privacy_url": "github://g...f@caronc/apprise/",
        },
    ),
    # Token supplied with ?token=
    (
        f"github://caronc/apprise/issues/42?token={TOKEN}",
        {
            "instance": NotifyGitHub,
            "privacy_url": "github://g...f@caronc/apprise/issues/42/",
        },
    ),
    # Comment on a pull request pasted from the browser
    (
        f"github://{TOKEN}@caronc/apprise/pull/1807/files",
        {
            "instance": NotifyGitHub,
            "privacy_url": "github://g...f@caronc/apprise/pull/1807/",
        },
    ),
    # Comment on a discussion
    (
        f"github://{TOKEN}@caronc/apprise/discussions/7",
        {
            "instance": NotifyGitHub,
            "requests_response_text": GRAPHQL_OK,
            "privacy_url": "github://g...f@caronc/apprise/discussions/7/",
        },
    ),
    # Start a new discussion in another category
    (
        f"github://{TOKEN}@caronc/apprise/discussions/new?category=ideas",
        {
            "instance": NotifyGitHub,
            "requests_response_text": GRAPHQL_OK,
            "privacy_url": (
                "github://g...f@caronc/apprise/discussions/?category=ideas"
            ),
        },
    ),
    # A discussion with a response GitHub would never send
    (
        f"github://{TOKEN}@caronc/apprise/discussions",
        {
            "instance": NotifyGitHub,
            "requests_response_text": "[]",
            "notify_response": False,
        },
    ),
    # An unreadable reply does not hide a successful status
    (
        f"github://{TOKEN}@caronc/apprise",
        {
            "instance": NotifyGitHub,
            "requests_response_text": b"<html>",
        },
    ),
    # HTTP 500
    (
        f"github://{TOKEN}@caronc/apprise",
        {
            "instance": NotifyGitHub,
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    # Unknown HTTP code
    (
        f"github://{TOKEN}@caronc/apprise/issues/42",
        {
            "instance": NotifyGitHub,
            "response": False,
            "requests_response_code": 999,
        },
    ),
    # RequestException
    (
        f"github://{TOKEN}@caronc/apprise/pull/1807",
        {
            "instance": NotifyGitHub,
            "test_requests_exceptions": True,
        },
    ),
)


def _mk_resp(data, code=requests.codes.ok):
    """Build a mock GitHub response containing JSON data."""
    r = mock.Mock()
    r.status_code = code
    r.content = dumps(data).encode("utf-8")
    return r


def test_plugin_github_urls():
    """Test GitHub notification URLs."""
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_github_init():
    """Test target type and number validation."""
    # An unknown type is refused
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyGitHub(token=TOKEN, owner="caronc", repo="apprise", kind="wiki")

    # A leading # on the number is accepted
    obj = NotifyGitHub(
        token=TOKEN, owner="caronc", repo="apprise", kind="pull", number="#7"
    )
    assert obj.number == 7
    assert obj.kind == GitHubKind.PULL
    assert len(obj) == 1

    # A blank category falls back to the default
    obj = NotifyGitHub(
        token=TOKEN,
        owner="caronc",
        repo="apprise",
        kind="discussion",
        category="  ",
    )
    assert obj.kind == GitHubKind.DISCUSSION
    assert obj.category == "General"


@mock.patch("requests.post")
def test_plugin_github_new_issue(mock_post):
    """Test opening an issue with a title, labels, and assignees."""
    mock_post.return_value = _mk_resp({"number": 1}, requests.codes.created)

    obj = Apprise.instantiate(
        f"github://{TOKEN}@caronc/apprise?labels=bug,nightly&assignees=caronc"
    )
    assert isinstance(obj, NotifyGitHub)
    assert obj.title_maxlen == 256

    assert obj.notify(
        title="Load <failed> & stopped",
        body="**step** _load_ failed!",
        notify_type=NotifyType.FAILURE,
    )

    # Confirm the request went to the issues endpoint
    url = mock_post.call_args[0][0]
    assert urlparse(url).hostname == "api.github.com"
    assert urlparse(url).path == "/repos/caronc/apprise/issues"

    # The title and body reach GitHub untouched
    payload = loads(mock_post.call_args[1]["data"])
    assert payload == {
        "title": "Load <failed> & stopped",
        "body": "**step** _load_ failed!",
        "labels": ["bug", "nightly"],
        "assignees": ["caronc"],
    }

    # Confirm our headers
    headers = mock_post.call_args[1]["headers"]
    assert headers["Authorization"] == f"Bearer {TOKEN}"
    assert headers["Accept"] == "application/vnd.github+json"

    # A missing title falls back to the Apprise description
    mock_post.reset_mock()
    assert obj.notify(body="body only")
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["title"] == obj.app_desc

    # The URL round trips
    obj2 = Apprise.instantiate(obj.url())
    assert obj2.url_identifier == obj.url_identifier
    assert obj2.labels == obj.labels
    assert obj2.assignees == obj.assignees


@mock.patch("requests.post")
def test_plugin_github_comment(mock_post):
    """Test issue and pull request comments."""
    mock_post.return_value = _mk_resp({"id": 1}, requests.codes.created)

    for kind, number in (("issues", 42), ("pull", 1807)):
        mock_post.reset_mock()
        obj = Apprise.instantiate(
            f"github://{TOKEN}@caronc/apprise/{kind}/{number}"
        )
        assert isinstance(obj, NotifyGitHub)
        assert obj.title_maxlen == 0

        assert obj.notify(
            title="Nightly",
            body="**load** failed",
            body_format=NotifyFormat.MARKDOWN,
        )

        # Issues and pull requests share the same comment endpoint
        url = mock_post.call_args[0][0]
        assert urlparse(url).path == (
            f"/repos/caronc/apprise/issues/{number}/comments"
        )

        # The title was merged in as a heading
        payload = loads(mock_post.call_args[1]["data"])
        assert list(payload.keys()) == ["body"]
        assert payload["body"].startswith("# Nightly")
        assert payload["body"].endswith("**load** failed")

        # The URL keeps the path word it was given
        assert f"/{kind}/{number}/" in obj.url()
        obj2 = Apprise.instantiate(obj.url())
        assert obj2.number == obj.number
        assert obj2.kind == obj.kind


@mock.patch("requests.post")
def test_plugin_github_discussion_comment(mock_post):
    """Test looking up and commenting on a discussion."""
    mock_post.side_effect = [
        _mk_resp({"data": {"repository": {"discussion": {"id": "D_1"}}}}),
        _mk_resp({"data": {"addDiscussionComment": {"comment": {}}}}),
    ]

    obj = Apprise.instantiate(f"github://{TOKEN}@caronc/apprise/discussions/7")
    assert obj.title_maxlen == 0
    assert obj.notify(title="Nightly", body="**load** failed")

    # Both calls went to the GraphQL endpoint
    assert mock_post.call_count == 2
    for call in mock_post.call_args_list:
        assert urlparse(call[0][0]).path == "/graphql"

    # The lookup asks for discussion 7 of our repository
    lookup = loads(mock_post.call_args_list[0][1]["data"])
    assert lookup["variables"] == {
        "owner": "caronc",
        "repo": "apprise",
        "number": 7,
    }

    # The comment goes to the ID the lookup returned
    comment = loads(mock_post.call_args_list[1][1]["data"])
    assert comment["variables"]["id"] == "D_1"
    assert comment["variables"]["body"].endswith("**load** failed")

    # A discussion that does not exist fails without commenting
    mock_post.reset_mock()
    mock_post.side_effect = [
        _mk_resp({"data": {"repository": {"discussion": None}}}),
    ]
    assert obj.notify(body="test") is False
    assert mock_post.call_count == 1

    # A failed lookup fails without commenting
    mock_post.reset_mock()
    mock_post.side_effect = [_mk_resp({}, requests.codes.unauthorized)]
    assert obj.notify(body="test") is False
    assert mock_post.call_count == 1


@mock.patch("requests.post")
def test_plugin_github_new_discussion(mock_post):
    """Test starting a discussion in the selected category."""
    categories = _mk_resp(
        {
            "data": {
                "repository": {
                    "id": "R_1",
                    "discussionCategories": {
                        "nodes": [
                            {
                                "id": "C_1",
                                "name": "General",
                                "slug": "general",
                            },
                            {
                                "id": "C_2",
                                "name": "Show and tell",
                                "slug": "show-and-tell",
                            },
                        ]
                    },
                }
            }
        }
    )
    created = _mk_resp({"data": {"createDiscussion": {"discussion": {}}}})

    # The default category is General
    mock_post.side_effect = [categories, created]
    obj = Apprise.instantiate(f"github://{TOKEN}@caronc/apprise/discussions")
    assert obj.title_maxlen == 256
    assert obj.notify(title="Release <2.0> & more", body="**Out** now")

    payload = loads(mock_post.call_args_list[1][1]["data"])
    assert payload["variables"] == {
        "repo": "R_1",
        "category": "C_1",
        "title": "Release <2.0> & more",
        "body": "**Out** now",
    }

    # A category matches by its web slug as well as its name
    mock_post.reset_mock()
    mock_post.side_effect = [categories, created]
    obj = Apprise.instantiate(
        f"github://{TOKEN}@caronc/apprise/discussions?category=show-and-tell"
    )
    assert obj.notify(body="demo")
    payload = loads(mock_post.call_args_list[1][1]["data"])
    assert payload["variables"]["category"] == "C_2"
    assert payload["variables"]["title"] == obj.app_desc

    # The category survives a round trip
    obj2 = Apprise.instantiate(obj.url())
    assert obj2.category == "show-and-tell"
    assert obj2.kind == GitHubKind.DISCUSSION
    assert obj2.number is None

    # An unknown category fails without creating anything
    mock_post.reset_mock()
    mock_post.side_effect = [categories]
    obj = Apprise.instantiate(
        f"github://{TOKEN}@caronc/apprise/discussions?category=Polls"
    )
    assert obj.notify(body="test") is False
    assert mock_post.call_count == 1

    # A failed category lookup fails without creating anything
    mock_post.reset_mock()
    mock_post.side_effect = [_mk_resp({}, requests.codes.not_found)]
    assert obj.notify(body="test") is False
    assert mock_post.call_count == 1


@mock.patch("requests.post")
def test_plugin_github_graphql_errors(mock_post):
    """Test errors returned in a successful GraphQL response."""
    mock_post.return_value = _mk_resp(
        {
            "errors": [
                {"message": "Resource not accessible by integration"},
                "unexpected",
            ]
        }
    )

    obj = Apprise.instantiate(f"github://{TOKEN}@caronc/apprise/discussions/7")
    assert obj.notify(body="test") is False
    assert mock_post.call_count == 1


@mock.patch("requests.post")
def test_plugin_github_http_errors(mock_post):
    """Test known GitHub HTTP errors."""
    obj = Apprise.instantiate(f"github://{TOKEN}@caronc/apprise")
    for code in (401, 403, 404, 410, 422):
        mock_post.return_value = _mk_resp({"message": "Not Found"}, code)
        assert obj.notify(body="test") is False


@mock.patch("requests.post")
def test_plugin_github_malformed_replies(mock_post):
    """NotifyGitHub() fails cleanly on GraphQL replies of the wrong shape."""
    # Replies GitHub would never send to a category lookup
    for reply in (
        {"data": "bad"},
        {"data": {"repository": {"id": "R_1"}}},
        {"data": {"repository": {"id": "R_1", "discussionCategories": {}}}},
        {
            "data": {
                "repository": {
                    "id": "R_1",
                    "discussionCategories": {"nodes": "bad"},
                }
            }
        },
        {
            "data": {
                "repository": {
                    "id": "R_1",
                    "discussionCategories": {
                        "nodes": [{"id": "C_1", "name": 5, "slug": "x"}]
                    },
                }
            }
        },
    ):
        mock_post.reset_mock()
        mock_post.side_effect = [_mk_resp(reply)]
        obj = Apprise.instantiate(
            f"github://{TOKEN}@caronc/apprise/discussions"
        )
        assert obj.notify(body="test") is False
        assert mock_post.call_count == 1

    # Replies GitHub would never send to a discussion lookup
    for reply in (
        {"data": {"repository": {"discussion": "bad"}}},
        {"data": {"repository": None}},
    ):
        mock_post.reset_mock()
        mock_post.side_effect = [_mk_resp(reply)]
        obj = Apprise.instantiate(
            f"github://{TOKEN}@caronc/apprise/discussions/7"
        )
        assert obj.notify(body="test") is False
        assert mock_post.call_count == 1

    # An errors value that is not a list still counts as a failure
    mock_post.reset_mock()
    mock_post.side_effect = [_mk_resp({"errors": True})]
    obj = Apprise.instantiate(f"github://{TOKEN}@caronc/apprise")
    assert obj.notify(body="test") is False


def test_plugin_github_number_length():
    """NotifyGitHub() refuses numbers too large for GitHub to hold."""
    # The largest number GitHub can store is accepted
    obj = NotifyGitHub(
        token=TOKEN, owner="caronc", repo="apprise", number="2147483647"
    )
    assert obj.number == 2147483647

    # Longer numbers are refused instead of raising a conversion error
    for number in ("12345678901", "9" * 5000):
        with pytest.raises(AppriseImproperlyConfigured):
            NotifyGitHub(
                token=TOKEN, owner="caronc", repo="apprise", number=number
            )
