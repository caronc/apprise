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
from apprise.plugins.twitter import NotifyTwitter

# Disable logging for a cleaner testing output
logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

TWITTER_SCREEN_NAME = "apprise"


# Our Testing URLs
apprise_url_tests = (
    ##################################
    # NotifyTwitter
    ##################################
    (
        "twitter://",
        {
            # Missing Consumer API Key
            "instance": TypeError,
        },
    ),
    (
        "twitter://:@/",
        {
            "instance": TypeError,
        },
    ),
    (
        "twitter://consumer_key",
        {
            # Missing Keys
            "instance": TypeError,
        },
    ),
    (
        "twitter://consumer_key/consumer_secret/",
        {
            # Missing Keys
            "instance": TypeError,
        },
    ),
    (
        "twitter://consumer_key/consumer_secret/atoken1/",
        {
            # Missing Access Secret
            "instance": TypeError,
        },
    ),
    (
        "twitter://consumer_key/consumer_secret/atoken2/access_secret",
        {
            # No user mean's we message ourselves
            "instance": NotifyTwitter,
            # Expected notify() response False (because we won't be able
            # to detect our user)
            "notify_response": False,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "x://c...y/****/a...2/****",
        },
    ),
    (
        (
            "twitter://consumer_key/consumer_secret/atoken3/access_secret"
            "?cache=no"
        ),
        {
            # No user mean's we message ourselves
            "instance": NotifyTwitter,
            # However we'll be okay if we return a proper response
            "requests_response_text": {
                "id": 12345,
                "screen_name": "test",
                # For attachment handling
                "media_id": 123,
            },
        },
    ),
    (
        "twitter://consumer_key/consumer_secret/atoken4/access_secret",
        {
            # No user mean's we message ourselves
            "instance": NotifyTwitter,
            # However we'll be okay if we return a proper response
            "requests_response_text": {
                "id": 12345,
                "screen_name": "test",
                # For attachment handling
                "media_id": 123,
            },
        },
    ),
    # A duplicate of the entry above, this will cause cache to be referenced
    (
        "twitter://consumer_key/consumer_secret/atoken5/access_secret",
        {
            # No user mean's we message ourselves
            "instance": NotifyTwitter,
            # However we'll be okay if we return a proper response
            "requests_response_text": {
                "id": 12345,
                "screen_name": "test",
                # For attachment handling
                "media_id": 123,
            },
        },
    ),
    # handle cases where the screen_name is missing from the response causing
    # an exception during parsing
    (
        "twitter://consumer_key/consumer_secret2/atoken6/access_secret",
        {
            # No user mean's we message ourselves
            "instance": NotifyTwitter,
            # However we'll be okay if we return a proper response
            "requests_response_text": {
                "id": 12345,
                # For attachment handling
                "media_id": 123,
            },
            # due to a mangled response_text we'll fail
            "notify_response": False,
        },
    ),
    (
        "twitter://user@consumer_key/csecret2/atoken7/access_secret/-/%/",
        {
            # One Invalid User
            "instance": NotifyTwitter,
            # Expected notify() response False (because we won't be able
            # to detect our user)
            "notify_response": False,
        },
    ),
    (
        (
            "twitter://user@consumer_key/csecret/atoken8/access_secret"
            "?cache=No&batch=No"
        ),
        {
            # No Cache & No Batch
            "instance": NotifyTwitter,
            "requests_response_text": [{"id": 12345, "screen_name": "user"}],
        },
    ),
    (
        "twitter://user@consumer_key/csecret/atoken9/access_secret",
        {
            # We're good!
            "instance": NotifyTwitter,
            "requests_response_text": [{"id": 12345, "screen_name": "user"}],
        },
    ),
    (
        "twitter://user@consumer_key/csecret/atoken11/access_secret",
        {
            # We're identifying the same user we already sent to
            "instance": NotifyTwitter,
            "notify_response": False,
        },
    ),
    (
        "tweet://ckey/csecret/atoken12/access_secret",
        {
            # A Public Tweet
            "instance": NotifyTwitter,
        },
    ),
    (
        "twitter://user@ckey/csecret/atoken13/access_secret?mode=invalid",
        {
            # An invalid mode
            "instance": TypeError,
        },
    ),
    (
        (
            "twitter://usera@consumer_key/consumer_secret/atoken14/"
            "access_secret/user/?to=userb"
        ),
        {
            # We're good!
            "instance": NotifyTwitter,
            "requests_response_text": [
                {"id": 12345, "screen_name": "usera"},
                {"id": 12346, "screen_name": "userb"},
                {
                    # A garbage entry we can test exception handling on
                    "id": 123,
                },
            ],
        },
    ),
    (
        "twitter://ckey/csecret/atoken15/access_secret",
        {
            "instance": NotifyTwitter,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "twitter://ckey/csecret/atoken16/access_secret",
        {
            "instance": NotifyTwitter,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
    (
        "twitter://ckey/csecret/atoken17/access_secret?mode=tweet",
        {
            "instance": NotifyTwitter,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def good_response(data):
    """Prepare a good response."""
    response = Mock()
    response.content = json.dumps(data)
    response.status_code = requests.codes.ok
    return response


def bad_response(data):
    """Prepare a bad response."""
    response = Mock()
    response.content = json.dumps(data)
    response.status_code = requests.codes.internal_server_error
    return response


@pytest.fixture
def twitter_url():
    ckey = "ckey"
    csecret = "csecret"
    akey = "akey"
    asecret = "asecret"
    url = f"twitter://{ckey}/{csecret}/{akey}/{asecret}"
    return url


@pytest.fixture
def good_message_response():
    """Prepare a good tweet response."""
    response = good_response({
        "screen_name": TWITTER_SCREEN_NAME,
        "id": 9876,
    })
    return response


@pytest.fixture
def bad_message_response():
    """Prepare a bad message response."""
    response = bad_response(
        {
            "errors": [{
                "code": 999,
                "message": "Something failed",
            }]
        }
    )
    return response


@pytest.fixture
def good_media_response():
    """Prepare a good media response."""
    response = Mock()
    response.content = json.dumps({
        "media_id": 710511363345354753,
        "media_id_string": "710511363345354753",
        "media_key": "3_710511363345354753",
        "size": 11065,
        "expires_after_secs": 86400,
        "image": {"image_type": "image/jpeg", "w": 800, "h": 320},
    })
    response.status_code = requests.codes.ok
    return response


@pytest.fixture
def bad_media_response():
    """Prepare a bad media response."""
    response = bad_response({
        "errors": [{
            "code": 93,
            "message": (
                "This application is not allowed to access or "
                "delete your direct messages."
            ),
        }]
    })
    return response


@pytest.fixture(autouse=True)
def ensure_get_verify_credentials_is_mocked(mocker, good_message_response):
    """
    Make sure requests to https://api.twitter.com/1.1/account/verify_credentials.json
    do not escape the test harness, for all test case functions.
    """
    mock_get = mocker.patch("requests.get")
    mock_get.return_value = good_message_response


def test_plugin_twitter_urls():
    """NotifyTwitter() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_twitter_general(mocker):
    """NotifyTwitter() General Tests."""

    mock_get = mocker.patch("requests.get")
    mock_post = mocker.patch("requests.post")

    ckey = "ckey"
    csecret = "csecret"
    akey = "akey"
    asecret = "asecret"

    response_obj = [{
        "screen_name": TWITTER_SCREEN_NAME,
        "id": 9876,
    }]

    # Epoch time:
    epoch = datetime.fromtimestamp(0, timezone.utc)

    request = Mock()
    request.content = json.dumps(response_obj)
    request.status_code = requests.codes.ok
    request.headers = {
        "x-rate-limit-reset": (
            (datetime.now(timezone.utc) - epoch).total_seconds()
        ),
        "x-rate-limit-remaining": 1,
    }

    # Prepare Mock
    mock_get.return_value = request
    mock_post.return_value = request

    # Variation Initializations
    obj = NotifyTwitter(
        ckey=ckey,
        csecret=csecret,
        akey=akey,
        asecret=asecret,
        targets=TWITTER_SCREEN_NAME,
    )

    assert isinstance(obj, NotifyTwitter) is True
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
    request.headers["x-rate-limit-remaining"] = 0
    # behind the scenes, it should cause us to update our rate limit
    assert obj.send(body="test") is True
    assert obj.ratelimit_remaining == 0

    # This should cause us to block
    request.headers["x-rate-limit-remaining"] = 10
    assert obj.send(body="test") is True
    assert obj.ratelimit_remaining == 10

    # Handle cases where we simply couldn't get this field
    del request.headers["x-rate-limit-remaining"]
    assert obj.send(body="test") is True
    # It remains set to the last value
    assert obj.ratelimit_remaining == 10

    # Reset our variable back to 1
    request.headers["x-rate-limit-remaining"] = 1

    # Handle cases where our epoch time is wrong
    del request.headers["x-rate-limit-reset"]
    assert obj.send(body="test") is True

    # Return our object, but place it in the future forcing us to block
    request.headers["x-rate-limit-reset"] = (
        datetime.now(timezone.utc) - epoch
    ).total_seconds() + 1
    request.headers["x-rate-limit-remaining"] = 0
    obj.ratelimit_remaining = 0
    assert obj.send(body="test") is True

    # Return our object, but place it in the future forcing us to block
    request.headers["x-rate-limit-reset"] = (
        datetime.now(timezone.utc) - epoch
    ).total_seconds() - 1
    request.headers["x-rate-limit-remaining"] = 0
    obj.ratelimit_remaining = 0
    assert obj.send(body="test") is True

    # Return our limits to always work
    request.headers["x-rate-limit-reset"] = (
        datetime.now(timezone.utc) - epoch
    ).total_seconds()
    request.headers["x-rate-limit-remaining"] = 1
    obj.ratelimit_remaining = 1

    # Alter pending targets
    obj.targets.append("usera")
    request.content = json.dumps(response_obj)
    response_obj = [{
        "screen_name": "usera",
        "id": 1234,
    }]

    assert obj.send(body="test") is True

    # Flush our cache forcing it is re-creating
    NotifyTwitter._user_cache = {}
    assert obj.send(body="test") is True

    # Cause content response to be None
    request.content = None
    assert obj.send(body="test") is True

    # Invalid JSON
    request.content = "{"
    assert obj.send(body="test") is True

    # Return it to a parseable string
    request.content = "{}"

    results = NotifyTwitter.parse_url(
        f"twitter://{ckey}/{csecret}/{akey}/{asecret}?to={TWITTER_SCREEN_NAME}"
    )
    assert isinstance(results, dict) is True
    assert TWITTER_SCREEN_NAME in results["targets"]

    # cause a json parsing issue now
    response_obj = None
    assert obj.send(body="test") is True

    response_obj = "{"
    assert obj.send(body="test") is True

    # Set ourselves up to handle whoami calls

    # Flush out our cache
    NotifyTwitter._user_cache = {}

    response_obj = {
        "screen_name": TWITTER_SCREEN_NAME,
        "id": 9876,
    }
    request.content = json.dumps(response_obj)

    obj = NotifyTwitter(ckey=ckey, csecret=csecret, akey=akey, asecret=asecret)

    assert obj.send(body="test") is True

    # Alter the key forcing us to look up a new value of ourselves again
    NotifyTwitter._user_cache = {}
    NotifyTwitter._whoami_cache = None
    obj.ckey = "different.then.it.was"
    assert obj.send(body="test") is True

    NotifyTwitter._whoami_cache = None
    obj.ckey = "different.again"
    assert obj.send(body="test") is True


def test_plugin_twitter_edge_cases():
    """NotifyTwitter() Edge Cases."""

    with pytest.raises(TypeError):
        NotifyTwitter(ckey=None, csecret=None, akey=None, asecret=None)

    with pytest.raises(TypeError):
        NotifyTwitter(ckey="value", csecret=None, akey=None, asecret=None)

    with pytest.raises(TypeError):
        NotifyTwitter(ckey="value", csecret="value", akey=None, asecret=None)

    with pytest.raises(TypeError):
        NotifyTwitter(
            ckey="value", csecret="value", akey="value", asecret=None
        )

    assert isinstance(
        NotifyTwitter(
            ckey="value", csecret="value", akey="value", asecret="value"
        ),
        NotifyTwitter,
    )

    assert isinstance(
        NotifyTwitter(
            ckey="value",
            csecret="value",
            akey="value",
            asecret="value",
            user="l2gnux",
        ),
        NotifyTwitter,
    )

    # Invalid Target User
    obj = NotifyTwitter(
        ckey="value",
        csecret="value",
        akey="value",
        asecret="value",
        targets="%G@rB@g3",
    )

    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is False
    )


def test_plugin_twitter_dm_caching(
    mocker, twitter_url, good_message_response, good_media_response
):
    """Verify that the `NotifyTwitter.{_user_cache,_whoami_cache}` caches work
    as intended."""

    # This is the request to `account/verify_credentials.json`.
    # Explicitly mock it here so the calls to it can be evaluated.
    mock_get = mocker.patch("requests.get")
    mock_get.return_value = good_message_response

    # This test case submits two notifications, so make sure to provide two
    # mocked responses.
    mock_post = mocker.patch("requests.post")
    mock_post.side_effect = [good_message_response, good_message_response]

    # Make sure to start with empty caches.
    if hasattr(NotifyTwitter, "_user_cache"):
        NotifyTwitter._user_cache = {}
    if hasattr(NotifyTwitter, "_whoami_cache"):
        NotifyTwitter._whoami_cache = {}

    # Create application objects.
    obj = Apprise.instantiate(twitter_url)

    # Send the first notification.
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    # Test call counts.
    assert mock_get.call_count == 1
    assert (
        mock_get.call_args_list[0][0][0]
        == "https://api.twitter.com/1.1/account/verify_credentials.json"
    )

    assert mock_post.call_count == 1
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://api.twitter.com/1.1/direct_messages/events/new.json"
    )

    # Reset the mocks to start counting calls from scratch.
    mock_get.reset_mock()
    mock_post.reset_mock()

    # Send another notification.
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    # Calls to `verify_credentials.json` will get cached by `NotifyTwitter`.
    # So, the `GET` request to `verify_credentials.json` should only have been
    # issued once.
    assert mock_get.call_count == 0
    assert mock_post.call_count == 1


def test_plugin_twitter_dm_attachments_basic(
    mocker, twitter_url, good_message_response, good_media_response
):
    """
    NotifyTwitter() DM Attachment Checks - Basic
    """

    mock_get = mocker.patch("requests.get")
    mock_post = mocker.patch("requests.post")

    # Epoch time:
    epoch = datetime.fromtimestamp(0, timezone.utc)
    mock_get.return_value = good_message_response
    mock_post.return_value.headers = {
        "x-rate-limit-reset": (
            (datetime.now(timezone.utc) - epoch).total_seconds()
        ),
        "x-rate-limit-remaining": 1,
    }

    # The first response is for uploading the attachment,
    # the second one for posting the actual message.
    mock_post.side_effect = [good_media_response, good_message_response]

    # Create application objects.
    obj = Apprise.instantiate(twitter_url)
    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.gif"))

    # Send our notification.
    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is True
    )

    # Test call counts.
    assert mock_get.call_count == 1
    assert (
        mock_get.call_args_list[0][0][0]
        == "https://api.twitter.com/1.1/account/verify_credentials.json"
    )

    assert mock_post.call_count == 2
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://upload.twitter.com/1.1/media/upload.json"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == "https://api.twitter.com/1.1/direct_messages/events/new.json"
    )


def test_plugin_twitter_dm_attachments_message_fails(
    mocker, twitter_url, good_media_response, bad_message_response
):
    """Test case with a bad media response."""

    mock_post = mocker.patch("requests.post")
    mock_post.side_effect = [good_media_response, bad_message_response]

    # Create application objects.
    obj = Apprise.instantiate(twitter_url)
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

    assert mock_post.call_count == 2
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://upload.twitter.com/1.1/media/upload.json"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == "https://api.twitter.com/1.1/direct_messages/events/new.json"
    )


def test_plugin_twitter_dm_attachments_upload_fails(
    mocker, twitter_url, good_message_response, bad_media_response
):
    """Test case where upload fails."""

    mock_post = mocker.patch("requests.post")
    mock_post.side_effect = [bad_media_response, good_message_response]

    # Create application objects.
    obj = Apprise.instantiate(twitter_url)
    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.gif"))

    # Send our notification; it will fail because of the media response.
    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is False
    )

    # Test call counts.
    assert mock_post.call_count == 1
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://upload.twitter.com/1.1/media/upload.json"
    )


def test_plugin_twitter_dm_attachments_invalid_attachment(
    mocker, twitter_url, good_message_response
):
    """Test case with an invalid attachment."""

    mock_post: Mock = mocker.patch("requests.post")
    mock_post.side_effect = [good_media_response, good_message_response]

    # Create application objects.
    # An invalid attachment will cause a failure.
    obj = Apprise.instantiate(twitter_url)
    attach = AppriseAttachment(
        os.path.join(TEST_VAR_DIR, "/invalid/path/to/an/invalid/file.jpg")
    )

    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is False
    )

    # Verify no post requests have been issued, because attachment is not good.
    assert mock_post.mock_calls == []


def test_plugin_twitter_dm_attachments_multiple(
    mocker, twitter_url, good_message_response, good_media_response
):

    mock_post = mocker.patch("requests.post")

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

    # 4 images are produced
    attach = [
        os.path.join(TEST_VAR_DIR, "apprise-test.gif"),
        os.path.join(TEST_VAR_DIR, "apprise-test.gif"),
        os.path.join(TEST_VAR_DIR, "apprise-test.jpeg"),
        os.path.join(TEST_VAR_DIR, "apprise-test.png"),
        # This one is not supported, so it's ignored gracefully
        os.path.join(TEST_VAR_DIR, "apprise-test.mp4"),
    ]

    # Create application objects.
    obj = Apprise.instantiate(twitter_url)

    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is True
    )

    assert mock_post.call_count == 8
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://upload.twitter.com/1.1/media/upload.json"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == "https://upload.twitter.com/1.1/media/upload.json"
    )
    assert (
        mock_post.call_args_list[2][0][0]
        == "https://upload.twitter.com/1.1/media/upload.json"
    )
    assert (
        mock_post.call_args_list[3][0][0]
        == "https://upload.twitter.com/1.1/media/upload.json"
    )
    assert (
        mock_post.call_args_list[4][0][0]
        == "https://api.twitter.com/1.1/direct_messages/events/new.json"
    )
    assert (
        mock_post.call_args_list[5][0][0]
        == "https://api.twitter.com/1.1/direct_messages/events/new.json"
    )
    assert (
        mock_post.call_args_list[6][0][0]
        == "https://api.twitter.com/1.1/direct_messages/events/new.json"
    )
    assert (
        mock_post.call_args_list[7][0][0]
        == "https://api.twitter.com/1.1/direct_messages/events/new.json"
    )


def test_plugin_twitter_dm_attachments_multiple_oserror(
    mocker, twitter_url, good_message_response, good_media_response
):

    # Inject an `OSError` into the middle of the operation.
    mock_post = mocker.patch("requests.post")
    mock_post.side_effect = [good_media_response, OSError()]

    # 2 images are produced
    attach = [
        os.path.join(TEST_VAR_DIR, "apprise-test.gif"),
        os.path.join(TEST_VAR_DIR, "apprise-test.png"),
        # This one is not supported, so it's ignored gracefully
        os.path.join(TEST_VAR_DIR, "apprise-test.mp4"),
    ]

    # Create application objects.
    obj = Apprise.instantiate(twitter_url)

    # We'll fail to send this time
    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is False
    )

    assert mock_post.call_count == 2
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://upload.twitter.com/1.1/media/upload.json"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == "https://upload.twitter.com/1.1/media/upload.json"
    )


@patch("requests.post")
def test_plugin_twitter_tweet_attachments_basic(
    mock_post, twitter_url, good_message_response, good_media_response
):
    """
    NotifyTwitter() Tweet Attachment Checks - Basic
    """

    mock_post.side_effect = [good_media_response, good_message_response]

    # Create application objects.
    twitter_url += "?mode=tweet"
    obj = Apprise.instantiate(twitter_url)
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
    assert mock_post.call_count == 2
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://upload.twitter.com/1.1/media/upload.json"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == "https://api.twitter.com/1.1/statuses/update.json"
    )


@patch("requests.post")
def test_plugin_twitter_tweet_attachments_more_logging(
    mock_post, twitter_url, good_media_response
):
    """
    NotifyTwitter() Tweet Attachment Checks - More logging

    TODO: The "more logging" aspect is not verified yet?
    """

    good_tweet_response = good_response({
        "screen_name": TWITTER_SCREEN_NAME,
        "id": 9876,
        # needed for additional logging
        "id_str": "12345",
        "user": {
            "screen_name": TWITTER_SCREEN_NAME,
        },
    })

    mock_post.side_effect = [good_media_response, good_tweet_response]

    # Create application objects.
    twitter_url += "?mode=tweet"
    obj = Apprise.instantiate(twitter_url)
    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.gif"))

    # Send our notification (again); this time there will be more logging
    # TODO: The "more logging" aspect is not verified yet?
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
    assert mock_post.call_count == 2
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://upload.twitter.com/1.1/media/upload.json"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == "https://api.twitter.com/1.1/statuses/update.json"
    )


@patch("requests.post")
def test_plugin_twitter_tweet_attachments_bad_message_response(
    mock_post, twitter_url, good_media_response, bad_message_response
):

    mock_post.side_effect = [good_media_response, bad_message_response]

    # Create application objects.
    twitter_url += "?mode=tweet"
    obj = Apprise.instantiate(twitter_url)
    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.gif"))

    # Our notification will fail now since our tweet will error out.
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
    assert mock_post.call_count == 2
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://upload.twitter.com/1.1/media/upload.json"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == "https://api.twitter.com/1.1/statuses/update.json"
    )


@patch("requests.post")
def test_plugin_twitter_tweet_attachments_bad_message_response_unparseable(
    mock_post, twitter_url, good_media_response
):

    bad_message_response = bad_response("")
    mock_post.side_effect = [good_media_response, bad_message_response]

    # Create application objects.
    twitter_url += "?mode=tweet"
    obj = Apprise.instantiate(twitter_url)
    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.gif"))

    # The notification will fail now since the tweet will error out.
    # This is the same test as above, except that the error response is not
    # parseable.
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
    assert mock_post.call_count == 2
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://upload.twitter.com/1.1/media/upload.json"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == "https://api.twitter.com/1.1/statuses/update.json"
    )


@patch("requests.post")
def test_plugin_twitter_tweet_attachments_upload_fails(
    mock_post, twitter_url, good_media_response
):

    # Prepare a bad tweet response.
    bad_tweet_response = bad_response({})

    # Test case where upload fails.
    mock_post.side_effect = [good_media_response, bad_tweet_response]

    # Create application objects.
    twitter_url += "?mode=tweet"
    obj = Apprise.instantiate(twitter_url)
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
    assert mock_post.call_count == 2
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://upload.twitter.com/1.1/media/upload.json"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == "https://api.twitter.com/1.1/statuses/update.json"
    )


@patch("requests.post")
def test_plugin_twitter_tweet_attachments_invalid_attachment(
    mock_post, twitter_url, good_message_response, good_media_response
):

    mock_post.side_effect = [good_media_response, good_message_response]

    # Create application objects.
    twitter_url += "?mode=tweet"
    obj = Apprise.instantiate(twitter_url)
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

    # No post request as attachment is not good.
    assert mock_post.call_count == 0


@patch("requests.post")
def test_plugin_twitter_tweet_attachments_multiple_batch(
    mock_post, twitter_url, good_message_response, good_media_response
):

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

    # instantiate our object
    obj = Apprise.instantiate(twitter_url + "?mode=tweet")

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

    assert mock_post.call_count == 7
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://upload.twitter.com/1.1/media/upload.json"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == "https://upload.twitter.com/1.1/media/upload.json"
    )
    assert (
        mock_post.call_args_list[2][0][0]
        == "https://upload.twitter.com/1.1/media/upload.json"
    )
    assert (
        mock_post.call_args_list[3][0][0]
        == "https://upload.twitter.com/1.1/media/upload.json"
    )
    assert (
        mock_post.call_args_list[4][0][0]
        == "https://api.twitter.com/1.1/statuses/update.json"
    )
    assert (
        mock_post.call_args_list[5][0][0]
        == "https://api.twitter.com/1.1/statuses/update.json"
    )
    # The 2 images are grouped together (batch mode)
    assert (
        mock_post.call_args_list[6][0][0]
        == "https://api.twitter.com/1.1/statuses/update.json"
    )


@patch("requests.post")
def test_plugin_twitter_tweet_attachments_multiple_nobatch(
    mock_post, twitter_url, good_message_response, good_media_response
):

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

    # instantiate our object (without a batch mode)
    obj = Apprise.instantiate(twitter_url + "?mode=tweet&batch=no")

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

    assert mock_post.call_count == 8
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://upload.twitter.com/1.1/media/upload.json"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == "https://upload.twitter.com/1.1/media/upload.json"
    )
    assert (
        mock_post.call_args_list[2][0][0]
        == "https://upload.twitter.com/1.1/media/upload.json"
    )
    assert (
        mock_post.call_args_list[3][0][0]
        == "https://upload.twitter.com/1.1/media/upload.json"
    )
    assert (
        mock_post.call_args_list[4][0][0]
        == "https://api.twitter.com/1.1/statuses/update.json"
    )
    assert (
        mock_post.call_args_list[5][0][0]
        == "https://api.twitter.com/1.1/statuses/update.json"
    )
    assert (
        mock_post.call_args_list[6][0][0]
        == "https://api.twitter.com/1.1/statuses/update.json"
    )
    assert (
        mock_post.call_args_list[7][0][0]
        == "https://api.twitter.com/1.1/statuses/update.json"
    )


@patch("requests.post")
def test_plugin_twitter_tweet_attachments_multiple_oserror(
    mock_post, twitter_url, good_media_response
):

    # We have an OSError thrown in the middle of our preparation
    mock_post.side_effect = [good_media_response, OSError()]

    # 2 images are produced
    attach = [
        os.path.join(TEST_VAR_DIR, "apprise-test.gif"),
        os.path.join(TEST_VAR_DIR, "apprise-test.png"),
        # This one is not supported, so it's ignored gracefully
        os.path.join(TEST_VAR_DIR, "apprise-test.mp4"),
    ]

    # We'll fail to send this time
    obj = Apprise.instantiate(twitter_url + "?mode=tweet")
    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is False
    )

    assert mock_post.call_count == 2
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://upload.twitter.com/1.1/media/upload.json"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == "https://upload.twitter.com/1.1/media/upload.json"
    )
