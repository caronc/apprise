# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2025, Chris Caron <lead2gold@gmail.com>
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

from datetime import datetime, timezone
import json
import logging
import os
from unittest.mock import Mock, patch

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, AppriseAttachment, NotifyType
from apprise.plugins.bluesky import NotifyBlueSky

# Disable logging for a cleaner testing output
logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

TWITTER_SCREEN_NAME = "apprise"


# Our Testing URLs
apprise_url_tests = (
    ##################################
    # NotifyBlueSky
    ##################################
    (
        "bluesky://",
        {
            # Missing user and app_pass
            "instance": TypeError,
        },
    ),
    (
        "bluesky://:@/",
        {
            "instance": TypeError,
        },
    ),
    (
        "bluesky://app-pw",
        {
            # Missing User
            "instance": TypeError,
        },
    ),
    (
        "bluesky://user@app-pw",
        {
            "instance": NotifyBlueSky,
            # Expected notify() response False (because we won't be able
            # to detect our user)
            "notify_response": False,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "bsky://user@****",
        },
    ),
    (
        "bluesky://user@app-pw1?cache=no",
        {
            "instance": NotifyBlueSky,
            # At minimum we need an access token and did; below has no did
            "requests_response_text": {
                "accessJwt": "abcd",
                "refreshJwt": "abcd",
            },
            "notify_response": False,
        },
    ),
    (
        "bluesky://user@app-pw2?cache=no",
        {
            "instance": NotifyBlueSky,
            # valid payload
            "requests_response_text": {
                "accessJwt": "abcd",
                "refreshJwt": "abcd",
                "did": "did:plc:1234",
                # Support plc response
                "service": [{
                    "type": "AtprotoPersonalDataServer",
                    "serviceEndpoint": "https://example.pds.io",
                }],
            },
        },
    ),
    (
        "bluesky://user@app-pw3",
        {
            # no cache; so we store our results
            "instance": NotifyBlueSky,
            # valid payload
            "requests_response_text": {
                "accessJwt": "abcd",
                "refreshJwt": "abcd",
                "did": "did:plc:1234",
                # For handling attachments
                "blob": "content",
                # Support plc response
                "service": [{
                    "type": "AtprotoPersonalDataServer",
                    "serviceEndpoint": "https://example.pds.io",
                }],
            },
        },
    ),
    (
        "bluesky://user.example.ca@app-pw3",
        {
            # no cache; so we store our results
            "instance": NotifyBlueSky,
            # valid payload
            "requests_response_text": {
                "accessJwt": "abcd",
                "refreshJwt": "abcd",
                "did": "did:plc:1234",
                # For handling attachments
                "blob": "content",
                # Support plc response
                "service": [{
                    "type": "AtprotoPersonalDataServer",
                    "serviceEndpoint": "https://example.pds.io",
                }],
            },
        },
    ),
    # A duplicate of the entry above, this will cause cache to be referenced
    (
        "bluesky://user@app-pw3",
        {
            # no cache; so we store our results
            "instance": NotifyBlueSky,
            # valid payload
            "requests_response_text": {
                "accessJwt": "abcd",
                "refreshJwt": "abcd",
                "did": "did:plc:1234",
                # For handling attachments
                "blob": "content",
                # Support plc response
                "service": [{
                    "type": "AtprotoPersonalDataServer",
                    "serviceEndpoint": "https://example.pds.io",
                }],
            },
        },
    ),
    (
        "bluesky://user@app-pw",
        {
            "instance": NotifyBlueSky,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
            "requests_response_text": {
                "accessJwt": "abcd",
                "refreshJwt": "abcd",
                "did": "did:plc:1234",
                # Support plc response
                "service": [{
                    "type": "AtprotoPersonalDataServer",
                    "serviceEndpoint": "https://example.pds.io",
                }],
            },
        },
    ),
    (
        "bluesky://user@app-pw",
        {
            "instance": NotifyBlueSky,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
            "requests_response_text": {
                "accessJwt": "abcd",
                "refreshJwt": "abcd",
                "did": "did:plc:1234",
                # Support plc response
                "service": [{
                    "type": "AtprotoPersonalDataServer",
                    "serviceEndpoint": "https://example.pds.io",
                }],
            },
        },
    ),
)


def good_response(data=None):
    """Prepare a good response."""
    response = Mock()
    response.content = json.dumps(
        {
            "accessJwt": "abcd",
            "refreshJwt": "abcd",
            "did": "did:plc:1234",
            # Support plc response
            "service": [{
                "type": "AtprotoPersonalDataServer",
                "serviceEndpoint": "https://example.pds.io",
            }],
            "ratelimit-reset": str(
                int(datetime.now(timezone.utc).timestamp()) + 3600
            ),
            "ratelimit-remaining": "10",
        }
        if data is None
        else data
    )

    response.status_code = requests.codes.ok

    # Epoch time:
    epoch = datetime.fromtimestamp(0, timezone.utc)

    # Generate a very large rate-limit header window
    response.headers = {
        "ratelimit-reset": (
            (datetime.now(timezone.utc) - epoch).total_seconds() + 86400
        ),
        "ratelimit-remaining": "1000",
    }

    return response


def bad_response(data=None):
    """Prepare a bad response."""
    response = Mock()
    response.content = json.dumps(
        {
            "error": "InvalidRequest",
            "message": "Something failed",
        }
        if data is None
        else data
    )
    response.headers = {}
    response.status_code = requests.codes.internal_server_error
    return response


@pytest.fixture
def bluesky_url():
    url = "bluesky://user@app-key"
    return url


@pytest.fixture
def good_message_response():
    """Prepare a good response."""
    response = good_response()
    return response


@pytest.fixture
def bad_message_response():
    """Prepare a bad message response."""
    response = bad_response()
    return response


@pytest.fixture
def good_media_response():
    """Prepare a good media response."""
    response = Mock()
    response.content = json.dumps({
        "blob": {
            "$type": "blob",
            "mimeType": "image/jpeg",
            "ref": {"$link": "baf124idksduabcjkaa3iey4bfyq"},
            "size": 73667,
        }
    })
    response.headers = {}
    response.status_code = requests.codes.ok
    return response


def test_plugin_bluesky_urls():
    """NotifyBlueSky() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_bluesky_general(mocker):
    """NotifyBlueSky() General Tests."""

    mock_get = mocker.patch("requests.get")
    mock_post = mocker.patch("requests.post")

    # Epoch time:
    epoch = datetime.fromtimestamp(0, timezone.utc)

    request = good_response()
    request.headers = {
        "ratelimit-reset": (
            (datetime.now(timezone.utc) - epoch).total_seconds()
        ),
        "ratelimit-remaining": "1",
    }

    # Prepare Mock
    mock_get.return_value = request
    mock_post.return_value = request

    # Variation Initializations
    obj = NotifyBlueSky(user="handle", password="app-password")

    assert isinstance(obj, NotifyBlueSky) is True
    assert isinstance(obj.url(), str) is True

    # apprise room was found
    assert obj.send(body="test") is True

    # Change our status code and try again
    request.status_code = 403
    assert obj.send(body="test") is False
    assert obj.ratelimit_remaining == 1

    # Return the status
    request.status_code = requests.codes.ok
    # Force a reset
    request.headers["ratelimit-remaining"] = 0
    # behind the scenes, it should cause us to update our rate limit
    assert obj.send(body="test") is True
    assert obj.ratelimit_remaining == 0

    # This should cause us to block
    request.headers["ratelimit-remaining"] = 10
    assert obj.send(body="test") is True
    assert obj.ratelimit_remaining == 10

    # Handle cases where we simply couldn't get this field
    del request.headers["ratelimit-remaining"]
    assert obj.send(body="test") is True
    # It remains set to the last value
    assert obj.ratelimit_remaining == 10

    # Reset our variable back to 1
    request.headers["ratelimit-remaining"] = 1

    # Handle cases where our epoch time is wrong
    del request.headers["ratelimit-reset"]
    assert obj.send(body="test") is True

    # Return our object, but place it in the future forcing us to block
    request.headers["ratelimit-reset"] = (
        datetime.now(timezone.utc) - epoch
    ).total_seconds() + 1
    request.headers["ratelimit-remaining"] = 0
    obj.ratelimit_remaining = 0
    assert obj.send(body="test") is True

    # Return our object, but place it in the future forcing us to block
    request.headers["ratelimit-reset"] = (
        datetime.now(timezone.utc) - epoch
    ).total_seconds() - 1
    request.headers["ratelimit-remaining"] = 0
    obj.ratelimit_remaining = 0
    assert obj.send(body="test") is True

    # Return our limits to always work
    request.headers["ratelimit-reset"] = (
        datetime.now(timezone.utc) - epoch
    ).total_seconds()
    request.headers["ratelimit-remaining"] = 1
    obj.ratelimit_remaining = 1

    assert obj.send(body="test") is True

    # Flush our cache forcing it is re-creating
    NotifyBlueSky._user_cache = {}
    assert obj.send(body="test") is True

    # Cause content response to be None
    request.content = None
    assert obj.send(body="test") is True

    # Invalid JSON
    request.content = "{"
    assert obj.send(body="test") is True

    # Return it to a parseable string
    request.content = "{}"

    results = NotifyBlueSky.parse_url("bluesky://handle@app-pass-word")
    assert isinstance(results, dict) is True

    # cause a json parsing issue now
    response_obj = None
    assert obj.send(body="test") is True

    response_obj = "{"
    assert obj.send(body="test") is True

    # Flush out our cache
    NotifyBlueSky._user_cache = {}

    response_obj = {
        "accessJwt": "abcd",
        "refreshJwt": "abcd",
        "did": "did:plc:1234",
        # Support plc response
        "service": [{
            "type": "AtprotoPersonalDataServer",
            "serviceEndpoint": "https://example.pds.io",
        }],
    }
    request.content = json.dumps(response_obj)

    obj = NotifyBlueSky(user="handle", password="app-pass-word")
    assert obj.send(body="test") is True

    # Alter the key forcing us to look up a new value of ourselves again
    NotifyBlueSky._user_cache = {}
    NotifyBlueSky._whoami_cache = None
    obj.ckey = "different.then.it.was"
    assert obj.send(body="test") is True

    NotifyBlueSky._whoami_cache = None
    obj.ckey = "different.again"
    assert obj.send(body="test") is True


def test_plugin_bluesky_edge_cases():
    """NotifyBlueSky() Edge Cases."""

    with pytest.raises(TypeError):
        NotifyBlueSky()


@patch("requests.post")
@patch("requests.get")
def test_plugin_bluesky_attachments_basic(
    mock_get,
    mock_post,
    bluesky_url,
    good_message_response,
    good_media_response,
):
    """
    NotifyBlueSky() Attachment Checks - Basic
    """

    mock_get.return_value = good_message_response
    mock_post.side_effect = [
        good_message_response,
        good_media_response,
        good_message_response,
    ]

    # Create application objects.
    obj = Apprise.instantiate(bluesky_url)
    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.gif"))

    # Send our notification
    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is True
    )

    # Verify API calls.
    assert mock_get.call_count == 2
    assert (
        mock_get.call_args_list[0][0][0]
        == "https://public.api.bsky.app/xrpc/com.atproto.identity.resolveHandle"
    )
    assert (
        mock_get.call_args_list[1][0][0]
        == "https://plc.directory/did:plc:1234"
    )

    assert mock_post.call_count == 3
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://example.pds.io/xrpc/com.atproto.server.createSession"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == "https://example.pds.io/xrpc/com.atproto.repo.uploadBlob"
    )
    assert (
        mock_post.call_args_list[2][0][0]
        == "https://example.pds.io/xrpc/com.atproto.repo.createRecord"
    )


@patch("requests.post")
@patch("requests.get")
def test_plugin_bluesky_attachments_bad_message_response(
    mock_get,
    mock_post,
    bluesky_url,
    good_media_response,
    good_message_response,
    bad_message_response,
):

    mock_get.return_value = good_message_response
    mock_post.side_effect = [
        good_message_response,
        bad_message_response,
        good_message_response,
    ]

    # Create application objects.
    obj = Apprise.instantiate(bluesky_url)
    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.gif"))

    # Our notification will fail now since our message will error out.
    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is False
    )

    # Verify API calls.
    assert mock_get.call_count == 2
    assert (
        mock_get.call_args_list[0][0][0]
        == "https://public.api.bsky.app/xrpc/com.atproto.identity.resolveHandle"
    )
    assert (
        mock_get.call_args_list[1][0][0]
        == "https://plc.directory/did:plc:1234"
    )

    assert mock_post.call_count == 2
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://example.pds.io/xrpc/com.atproto.server.createSession"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == "https://example.pds.io/xrpc/com.atproto.repo.uploadBlob"
    )


@patch("requests.post")
@patch("requests.get")
def test_plugin_bluesky_attachments_upload_fails(
    mock_get,
    mock_post,
    bluesky_url,
    good_media_response,
    good_message_response,
):

    # Test case where upload fails.
    mock_get.return_value = good_message_response
    mock_post.side_effect = [good_message_response, OSError]

    # Create application objects.
    obj = Apprise.instantiate(bluesky_url)
    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.gif"))

    # Send our notification; it will fail because of the message response.
    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is False
    )

    # Verify API calls.
    assert mock_get.call_count == 2
    assert (
        mock_get.call_args_list[0][0][0]
        == "https://public.api.bsky.app/xrpc/com.atproto.identity.resolveHandle"
    )
    assert (
        mock_get.call_args_list[1][0][0]
        == "https://plc.directory/did:plc:1234"
    )

    assert mock_post.call_count == 2
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://example.pds.io/xrpc/com.atproto.server.createSession"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == "https://example.pds.io/xrpc/com.atproto.repo.uploadBlob"
    )


@patch("requests.post")
@patch("requests.get")
def test_plugin_bluesky_attachments_invalid_attachment(
    mock_get,
    mock_post,
    bluesky_url,
    good_message_response,
    good_media_response,
):

    mock_get.return_value = good_message_response
    mock_post.side_effect = [good_message_response, good_media_response]

    # Create application objects.
    obj = Apprise.instantiate(bluesky_url)
    attach = AppriseAttachment(
        os.path.join(TEST_VAR_DIR, "/invalid/path/to/an/invalid/file.jpg")
    )

    # An invalid attachment will cause a failure.
    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is False
    )

    # Verify API calls.
    assert mock_get.call_count == 2
    assert (
        mock_get.call_args_list[0][0][0]
        == "https://public.api.bsky.app/xrpc/com.atproto.identity.resolveHandle"
    )
    assert (
        mock_get.call_args_list[1][0][0]
        == "https://plc.directory/did:plc:1234"
    )

    # No post request as attachment is not good.
    assert mock_post.call_count == 1
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://example.pds.io/xrpc/com.atproto.server.createSession"
    )


@patch("requests.post")
@patch("requests.get")
def test_plugin_bluesky_attachments_multiple_batch(
    mock_get,
    mock_post,
    bluesky_url,
    good_message_response,
    good_media_response,
):

    mock_get.return_value = good_message_response
    mock_post.side_effect = [
        good_message_response,
        good_media_response,
        good_media_response,
        good_media_response,
        good_media_response,
        good_message_response,
        good_message_response,
        good_message_response,
        good_message_response,
    ]

    # instantiate our object
    obj = Apprise.instantiate(bluesky_url)

    # 4 images are produced
    attach = [
        os.path.join(TEST_VAR_DIR, "apprise-test.gif"),
        os.path.join(TEST_VAR_DIR, "apprise-test.gif"),
        os.path.join(TEST_VAR_DIR, "apprise-test.jpeg"),
        os.path.join(TEST_VAR_DIR, "apprise-test.png"),
        # This one is not supported, so it's ignored gracefully
        os.path.join(TEST_VAR_DIR, "apprise-test.mp4"),
    ]

    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is True
    )

    # Verify API calls.
    assert mock_get.call_count == 2
    assert (
        mock_get.call_args_list[0][0][0]
        == "https://public.api.bsky.app/xrpc/com.atproto.identity.resolveHandle"
    )
    assert (
        mock_get.call_args_list[1][0][0]
        == "https://plc.directory/did:plc:1234"
    )
    assert mock_post.call_count == 9
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://example.pds.io/xrpc/com.atproto.server.createSession"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == "https://example.pds.io/xrpc/com.atproto.repo.uploadBlob"
    )
    assert (
        mock_post.call_args_list[2][0][0]
        == "https://example.pds.io/xrpc/com.atproto.repo.uploadBlob"
    )
    assert (
        mock_post.call_args_list[3][0][0]
        == "https://example.pds.io/xrpc/com.atproto.repo.uploadBlob"
    )
    assert (
        mock_post.call_args_list[4][0][0]
        == "https://example.pds.io/xrpc/com.atproto.repo.uploadBlob"
    )
    assert (
        mock_post.call_args_list[5][0][0]
        == "https://example.pds.io/xrpc/com.atproto.repo.createRecord"
    )
    assert (
        mock_post.call_args_list[6][0][0]
        == "https://example.pds.io/xrpc/com.atproto.repo.createRecord"
    )
    assert (
        mock_post.call_args_list[7][0][0]
        == "https://example.pds.io/xrpc/com.atproto.repo.createRecord"
    )
    assert (
        mock_post.call_args_list[8][0][0]
        == "https://example.pds.io/xrpc/com.atproto.repo.createRecord"
    )

    # If we call the functions again, the only difference is
    # we no longer need to resolve the handle or create a session
    # as the previous one is fine.
    mock_get.reset_mock()
    mock_post.reset_mock()

    mock_get.return_value = good_message_response
    mock_post.side_effect = [
        good_media_response,
        good_media_response,
        good_media_response,
        good_media_response,
        good_message_response,
        good_message_response,
        good_message_response,
        good_message_response,
    ]

    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is True
    )

    # Verify API calls.
    assert mock_get.call_count == 0
    assert mock_post.call_count == 8
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://example.pds.io/xrpc/com.atproto.repo.uploadBlob"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == "https://example.pds.io/xrpc/com.atproto.repo.uploadBlob"
    )
    assert (
        mock_post.call_args_list[2][0][0]
        == "https://example.pds.io/xrpc/com.atproto.repo.uploadBlob"
    )
    assert (
        mock_post.call_args_list[3][0][0]
        == "https://example.pds.io/xrpc/com.atproto.repo.uploadBlob"
    )
    assert (
        mock_post.call_args_list[4][0][0]
        == "https://example.pds.io/xrpc/com.atproto.repo.createRecord"
    )
    assert (
        mock_post.call_args_list[5][0][0]
        == "https://example.pds.io/xrpc/com.atproto.repo.createRecord"
    )
    assert (
        mock_post.call_args_list[6][0][0]
        == "https://example.pds.io/xrpc/com.atproto.repo.createRecord"
    )
    assert (
        mock_post.call_args_list[7][0][0]
        == "https://example.pds.io/xrpc/com.atproto.repo.createRecord"
    )


@patch("requests.post")
@patch("requests.get")
def test_plugin_bluesky_auth_failure(
    mock_get,
    mock_post,
    bluesky_url,
    good_message_response,
    bad_message_response,
):

    mock_get.return_value = good_message_response
    mock_post.return_value = bad_message_response

    # instantiate our object
    obj = Apprise.instantiate(bluesky_url)

    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is False
    )

    # Verify API calls.
    assert mock_get.call_count == 2
    assert (
        mock_get.call_args_list[0][0][0]
        == "https://public.api.bsky.app/xrpc/com.atproto.identity.resolveHandle"
    )
    assert (
        mock_get.call_args_list[1][0][0]
        == "https://plc.directory/did:plc:1234"
    )
    assert mock_post.call_count == 1
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://example.pds.io/xrpc/com.atproto.server.createSession"
    )


@patch("requests.post")
@patch("requests.get")
def test_plugin_bluesky_did_web_and_plc_resolution(
    mock_get, mock_post, bluesky_url, good_message_response
):
    """
    NotifyBlueSky() - Full coverage of did:web and did:plc path
    """

    # Step 1: Identity resolution response (public.api.bsky.app)
    identity_response = good_response({"did": "did:plc:abcdefg1234567"})

    # Step 2: PLC Directory lookup
    plc_response = good_response({
        "service": [{
            "type": "AtprotoPersonalDataServer",
            "serviceEndpoint": "https://example.pds.io",
        }]
    })

    # Step 3: Auth session
    session_response = good_response()

    # Step 4: Create post
    post_response = good_response()

    mock_get.side_effect = [identity_response, plc_response]
    mock_post.side_effect = [session_response, post_response]

    obj = Apprise.instantiate(bluesky_url)
    assert obj.notify(body="Resolved PLC Flow") is True

    # Reset for did:web test
    identity_response = good_response({"did": "did:web:example.com"})

    web_did_response = good_response({
        "service": [{
            "type": "AtprotoPersonalDataServer",
            "serviceEndpoint": "https://example.com",
        }]
    })

    mock_get.side_effect = [identity_response, web_did_response]
    mock_post.side_effect = [session_response, post_response]

    obj = Apprise.instantiate(bluesky_url)
    assert obj.notify(body="Resolved WEB Flow") is True

    # Invalid DID scheme
    bad_did_response = good_response({"did": "did:unsupported:scheme"})

    mock_get.side_effect = [bad_did_response]
    obj = Apprise.instantiate(bluesky_url)
    assert obj.notify(body="fail due to bad scheme") is False


@patch("requests.get")
def test_plugin_bluesky_pds_resolution_failures(mock_get):
    """
    NotifyBlueSky() - Missing service field or invalid service endpoint
    """
    identity_response = good_response({"did": "did:plc:missing-service"})
    plc_no_service = good_response({"foo": "bar"})

    mock_get.side_effect = [identity_response, plc_no_service]
    obj = NotifyBlueSky(user="handle", password="pass")
    did, endpoint = obj.get_identifier()
    assert (did, endpoint) == (False, False)

    identity_response = good_response({"did": "did:web:example.com"})
    web_did_no_service = good_response({"foo": "bar"})

    mock_get.side_effect = [identity_response, web_did_no_service]
    obj = NotifyBlueSky(user="handle", password="pass")
    did, endpoint = obj.get_identifier()
    assert (did, endpoint) == (False, False)


@patch("requests.get")
def test_plugin_bluesky_missing_pds_endpoint(mock_get):
    """
    NotifyBlueSky() - test case where endpoint is missing from DID document
    """
    # Return a valid DID resolution
    identity_response = good_response({"did": "did:plc:abcdefg1234567"})

    # Return DID document with a service list, but no matching PDS type
    incomplete_pds_response = good_response({
        "service": [{
            "type": "SomeOtherService",
            "serviceEndpoint": "https://unrelated.example.com",
        }]
    })

    mock_get.side_effect = [identity_response, incomplete_pds_response]
    obj = NotifyBlueSky(user="handle", password="app-pw")
    assert obj.get_identifier() == (False, False)
