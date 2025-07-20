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
from json import dumps, loads

# Disable logging for a cleaner testing output
import logging
import os
from unittest import mock

from helpers import AppriseURLTester
import requests

from apprise import Apprise, AppriseAttachment, NotifyType
from apprise.plugins.mastodon import NotifyMastodon

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# Our Testing URLs
apprise_url_tests = (
    ##################################
    # NotifyMastodon
    ##################################
    (
        "mastodon://",
        {
            # Missing Everything :)
            "instance": None,
        },
    ),
    (
        "mastodon://:@/",
        {
            "instance": None,
        },
    ),
    (
        "mastodon://hostname",
        {
            # Missing Access Token
            "instance": TypeError,
        },
    ),
    (
        "toot://access_token@hostname",
        {
            # We're good; it's a simple notification
            "instance": NotifyMastodon,
        },
    ),
    (
        "toots://access_token@hostname",
        {
            # We're good; it's another simple notification
            "instance": NotifyMastodon,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "mastodons://****@hostname/",
        },
    ),
    (
        "mastodon://access_token@hostname/@user/@user2",
        {
            # We're good; it's another simple notification
            "instance": NotifyMastodon,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "mastodon://****@hostname/@user/@user2",
        },
    ),
    (
        "mastodon://hostname/@user/@user2?token=abcd123",
        {
            # Our access token can be provided as a token= variable
            "instance": NotifyMastodon,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "mastodon://****@hostname/@user/@user2",
        },
    ),
    (
        "mastodon://access_token@hostname?to=@user, @user2",
        {
            # We're good; it's another simple notification
            "instance": NotifyMastodon,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "mastodon://****@hostname/@user/@user2",
        },
    ),
    (
        "mastodon://access_token@hostname/?cache=no",
        {
            # disable cache as a test
            "instance": NotifyMastodon,
        },
    ),
    (
        "mastodon://access_token@hostname/?spoiler=spoiler%20text",
        {
            # a public post
            "instance": NotifyMastodon,
        },
    ),
    (
        "mastodon://access_token@hostname/?language=en",
        {
            # over-ride our language
            "instance": NotifyMastodon,
        },
    ),
    (
        "mastodons://access_token@hostname:8443",
        {
            # A custom port specified
            "instance": NotifyMastodon,
        },
    ),
    (
        "mastodon://access_token@hostname/?key=My%20Idempotency%20Key",
        {
            # Prevent duplicate submissions of the same status. Idempotency
            # keys are stored for up to 1 hour, and can be any arbitrary
            # string. Consider using a hash or UUID generated client-side.
            "instance": NotifyMastodon,
        },
    ),
    (
        "mastodon://access_token@hostname/-/%/",
        {
            # Invalid users specified
            "instance": TypeError,
        },
    ),
    (
        "mastodon://access_token@hostname?visibility=invalid",
        {
            # An invalid visibility
            "instance": TypeError,
        },
    ),
    (
        "mastodon://access_token@hostname?visibility=direct",
        {
            # A direct message
            "instance": NotifyMastodon,
            # Expected notify() response False (because we won't
            # get the response we were expecting from the upstream
            # server
            "notify_response": False,
        },
    ),
    (
        "mastodon://access_token@hostname?visibility=direct",
        {
            # A direct message
            "instance": NotifyMastodon,
            # Provide a response that allows us to look our content up
            "requests_response_text": {
                "id": "12345",
                "username": "test",
            },
        },
    ),
    (
        "toots://access_token@hostname",
        {
            "instance": NotifyMastodon,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_mastodon_urls():
    """NotifyMastodon() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_mastodon_general(mock_post, mock_get):
    """NotifyMastodon() General Tests."""
    token = "access_key"
    host = "nuxref.com"

    response_obj = {
        "username": "caronc",
        "id": 1234,
    }

    # Epoch time:
    epoch = datetime.fromtimestamp(0, timezone.utc)

    request = mock.Mock()
    request.content = dumps(response_obj)
    request.status_code = requests.codes.ok
    request.headers = {
        "X-RateLimit-Limit": (
            (datetime.now(timezone.utc) - epoch).total_seconds()
        ),
        "X-RateLimit-Remaining": 1,
    }

    # Prepare Mock
    mock_get.return_value = request
    mock_post.return_value = request

    # Instantiate our object
    obj = NotifyMastodon(token=token, host=host)

    assert isinstance(obj, NotifyMastodon)
    assert isinstance(obj.url(), str)

    # apprise room was found
    assert obj.send(body="test") is True

    # Change our status code and try again
    request.status_code = 403
    assert obj.send(body="test") is False
    assert obj.ratelimit_remaining == 1

    # Return the status
    request.status_code = requests.codes.ok
    # Force a reset
    request.headers["X-RateLimit-Remaining"] = 0
    # behind the scenes, it should cause us to update our rate limit
    assert obj.send(body="test") is True
    assert obj.ratelimit_remaining == 0

    # This should cause us to block
    request.headers["X-RateLimit-Remaining"] = 10
    assert obj.send(body="test") is True
    assert obj.ratelimit_remaining == 10

    # Handle cases where we simply couldn't get this field
    del request.headers["X-RateLimit-Remaining"]
    assert obj.send(body="test") is True
    # It remains set to the last value
    assert obj.ratelimit_remaining == 10

    # Reset our variable back to 1
    request.headers["X-RateLimit-Remaining"] = 1

    # Handle cases where our epoch time is wrong
    del request.headers["X-RateLimit-Limit"]
    assert obj.send(body="test") is True

    # Return our object, but place it in the future forcing us to block
    request.headers["X-RateLimit-Limit"] = (
        datetime.now(timezone.utc) - epoch
    ).total_seconds() + 1
    request.headers["X-RateLimit-Remaining"] = 0
    obj.ratelimit_remaining = 0
    assert obj.send(body="test") is True

    # Return our object, but place it in the future forcing us to block
    request.headers["X-RateLimit-Limit"] = (
        datetime.now(timezone.utc) - epoch
    ).total_seconds() - 1
    request.headers["X-RateLimit-Remaining"] = 0
    obj.ratelimit_remaining = 0
    assert obj.send(body="test") is True

    # Return our limits to always work
    request.headers["X-RateLimit-Limit"] = (
        datetime.now(timezone.utc) - epoch
    ).total_seconds()
    request.headers["X-RateLimit-Remaining"] = 1
    obj.ratelimit_remaining = 1

    # Alter pending targets
    obj.targets.append("usera")
    request.content = dumps(response_obj)
    response_obj = {
        "username": "usera",
        "id": 4321,
    }

    # Cause content response to be None
    request.content = None
    assert obj.send(body="test") is True

    # Invalid JSON
    request.content = "{"
    assert obj.send(body="test") is True

    # Return it to a parseable string
    request.content = "{}"

    results = NotifyMastodon.parse_url(
        f"mastodon://{token}@{host}/@user?visbility=direct"
    )
    assert isinstance(results, dict)
    assert "@user" in results["targets"]

    # cause a json parsing issue now
    response_obj = None
    assert obj.send(body="test") is True

    response_obj = "{"
    assert obj.send(body="test") is True

    mock_get.reset_mock()
    mock_post.reset_mock()

    #
    # Test our lazy lookups
    #

    # Prepare a good status response
    request = mock.Mock()
    request.content = dumps({"id": "1234", "username": "caronc"})
    request.status_code = requests.codes.ok
    mock_get.return_value = request

    mastodon_url = "mastodons://key@host?visibility=direct"
    obj = Apprise.instantiate(mastodon_url)
    obj._whoami(lazy=True)
    assert mock_get.call_count == 1
    assert (
        mock_get.call_args_list[0][0][0]
        == "https://host/api/v1/accounts/verify_credentials"
    )

    mock_get.reset_mock()
    obj._whoami(lazy=True)
    assert mock_get.call_count == 0

    mock_get.reset_mock()
    obj._whoami(lazy=False)
    assert mock_get.call_count == 1
    assert (
        mock_get.call_args_list[0][0][0]
        == "https://host/api/v1/accounts/verify_credentials"
    )


@mock.patch("requests.post")
@mock.patch("requests.get")
def test_plugin_mastodon_attachments(mock_get, mock_post):
    """NotifyMastodon() Toot Attachment Checks."""
    akey = "access_key"
    host = "nuxref.com"
    username = "caronc"

    # Prepare a good status response
    good_response_obj = {
        "id": "1234",
    }

    good_response = mock.Mock()
    good_response.content = dumps(good_response_obj)
    good_response.status_code = requests.codes.ok

    # Prepare a good whoami response
    good_whoami_response_obj = {
        "username": username,
        "id": "9876",
    }

    good_whoami_response = mock.Mock()
    good_whoami_response.content = dumps(good_whoami_response_obj)
    good_whoami_response.status_code = requests.codes.ok

    # Prepare bad response
    bad_response = mock.Mock()
    bad_response.content = dumps({})
    bad_response.status_code = requests.codes.internal_server_error

    # Prepare a good media response
    good_media_response = mock.Mock()
    good_media_response.content = dumps({
        "id": "710511363345354753",
        "file_mime": "image/jpeg",
    })
    good_media_response.status_code = requests.codes.ok

    #
    #  Start testing using fixtures above
    #
    mock_post.side_effect = [good_media_response, good_response]
    mock_get.return_value = good_whoami_response

    mastodon_url = f"mastodon://{akey}@{host}"

    # attach our content
    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.gif"))

    # instantiate our object
    obj = Apprise.instantiate(mastodon_url)

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

    # Test our call count
    assert mock_get.call_count == 0
    assert mock_post.call_count == 2
    assert (
        mock_post.call_args_list[0][0][0] == "http://nuxref.com/api/v1/media"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == "http://nuxref.com/api/v1/statuses"
    )

    # Test our media payload
    assert "files" in mock_post.call_args_list[0][1]
    assert "file" in mock_post.call_args_list[0][1]["files"]
    assert (
        mock_post.call_args_list[0][1]["files"]["file"][0]
        == "apprise-test.gif"
    )

    # Test our status payload
    payload = loads(mock_post.call_args_list[1][1]["data"])
    assert "status" in payload
    assert payload["status"] == "title\r\nbody"
    assert "sensitive" in payload
    assert payload["sensitive"] is False
    assert "media_ids" in payload
    assert isinstance(payload["media_ids"], list)
    assert len(payload["media_ids"]) == 1
    assert payload["media_ids"][0] == "710511363345354753"

    # Verify we don't set incorrect keys not otherwise specified
    assert "spoiler_text" not in payload

    mock_get.reset_mock()
    mock_post.reset_mock()

    #
    # Handle the query again, but this time perform a direct message
    # requiring us to look up who we are
    #
    mock_post.side_effect = [good_media_response, good_response]
    mock_get.return_value = good_whoami_response

    mastodon_url = f"mastodon://{akey}@{host}?visibility=direct"

    # attach our content
    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.gif"))

    # instantiate our object
    obj = Apprise.instantiate(mastodon_url)

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

    # Test our call count
    assert mock_get.call_count == 1
    assert mock_post.call_count == 2
    assert (
        mock_get.call_args_list[0][0][0]
        == "http://nuxref.com/api/v1/accounts/verify_credentials"
    )
    assert (
        mock_post.call_args_list[0][0][0] == "http://nuxref.com/api/v1/media"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == "http://nuxref.com/api/v1/statuses"
    )

    # Test our status payload
    payload = loads(mock_post.call_args_list[1][1]["data"])
    assert "status" in payload
    # Our ID was added into the payload
    assert payload["status"] == "@caronc title\r\nbody"
    assert "sensitive" in payload
    assert payload["sensitive"] is False
    assert "media_ids" in payload
    assert isinstance(payload["media_ids"], list)
    assert len(payload["media_ids"]) == 1
    assert payload["media_ids"][0] == "710511363345354753"

    mock_get.reset_mock()
    mock_post.reset_mock()

    # Store 3 attachments
    attach = (
        AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.gif")),
        AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.png")),
        AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.jpeg")),
    )

    # Prepare a good media response
    mr1 = mock.Mock()
    mr1.content = dumps({
        "id": "1",
        "file_mime": "image/gif",
    })
    mr1.status_code = requests.codes.ok

    mr2 = mock.Mock()
    mr2.content = dumps({
        "id": "2",
        "file_mime": "image/png",
    })
    mr2.status_code = requests.codes.ok

    mr3 = mock.Mock()
    mr3.content = dumps({
        "id": "3",
        "file_mime": "image/jpeg",
    })
    mr3.status_code = requests.codes.ok

    # Return 3 good uploads and a good status response
    mock_post.side_effect = [mr1, mr2, mr3, good_response, good_response]
    mock_get.return_value = good_whoami_response

    # instantiate our object
    mastodon_url = (
        f"mastodons://{akey}@{host}?visibility=direct&sensitive=yes&key=abcd"
    )
    obj = Apprise.instantiate(mastodon_url)

    # Send ourselves a direct message where our ID was already found
    # in the body.  This smart detection method will prevent us from
    # adding the @caronc to the begining of the same message (since it's a
    # direct message)
    assert (
        obj.notify(
            body="Check this out @caronc",
            title="Apprise",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is True
    )

    # Test our call count
    assert mock_get.call_count == 1
    assert mock_post.call_count == 5
    assert (
        mock_post.call_args_list[0][0][0] == "https://nuxref.com/api/v1/media"
    )
    assert (
        mock_post.call_args_list[1][0][0] == "https://nuxref.com/api/v1/media"
    )
    assert (
        mock_post.call_args_list[2][0][0] == "https://nuxref.com/api/v1/media"
    )
    # Our status's will batch up and send the last 2 images in one
    # and our animated gif in one.
    assert (
        mock_post.call_args_list[3][0][0]
        == "https://nuxref.com/api/v1/statuses"
    )
    assert (
        mock_post.call_args_list[4][0][0]
        == "https://nuxref.com/api/v1/statuses"
    )
    assert (
        mock_get.call_args_list[0][0][0]
        == "https://nuxref.com/api/v1/accounts/verify_credentials"
    )

    # Test our status payload
    payload = loads(mock_post.call_args_list[3][1]["data"])
    assert "status" in payload
    assert payload["status"] == "Apprise\r\nCheck this out @caronc"
    assert "sensitive" in payload
    assert payload["sensitive"] is True
    assert "language" not in payload
    assert "Idempotency-Key" in payload
    assert payload["Idempotency-Key"] == "abcd"
    assert "media_ids" in payload
    assert isinstance(payload["media_ids"], list)
    assert len(payload["media_ids"]) == 1
    assert payload["media_ids"][0] == "1"

    payload = loads(mock_post.call_args_list[4][1]["data"])
    assert "status" in payload
    assert payload["status"] == "02/02"
    assert "sensitive" in payload
    assert payload["sensitive"] is False
    assert "language" not in payload
    assert "Idempotency-Key" in payload
    assert payload["Idempotency-Key"] == "abcd-part01"
    assert "media_ids" in payload
    assert isinstance(payload["media_ids"], list)
    assert len(payload["media_ids"]) == 2
    assert "2" in payload["media_ids"]
    assert "3" in payload["media_ids"]

    # A second call does not cause us to look up our ID as we already know it
    mock_get.reset_mock()
    mock_post.reset_mock()
    mock_post.side_effect = [mr1, mr2, mr3, good_response, good_response]
    mock_get.return_value = good_whoami_response
    assert (
        obj.notify(
            body="Check this out @caronc",
            title="Apprise",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is True
    )

    # Same number of posts
    assert mock_post.call_count == 5
    # But no lookup was made
    assert mock_get.call_count == 0

    mock_get.reset_mock()
    mock_post.reset_mock()

    # Prepare an attach list
    attach = (
        os.path.join(TEST_VAR_DIR, "apprise-test.png"),
        os.path.join(TEST_VAR_DIR, "apprise-test.jpeg"),
    )

    mock_post.side_effect = [mr2, mr3, good_response, good_response]
    mock_get.return_value = good_whoami_response

    # instantiate our object (but turn off the batch mode)
    mastodon_url = f"mastodons://{akey}@{host}?batch=no"
    obj = Apprise.instantiate(mastodon_url)

    assert (
        obj.notify(
            body="Check this out @caronc",
            title="Apprise",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is True
    )

    # 2 attachments + 2 different status messages
    assert mock_post.call_count == 4

    # But no lookup was made
    assert mock_get.call_count == 0

    assert (
        mock_post.call_args_list[0][0][0] == "https://nuxref.com/api/v1/media"
    )
    assert (
        mock_post.call_args_list[1][0][0] == "https://nuxref.com/api/v1/media"
    )
    assert (
        mock_post.call_args_list[2][0][0]
        == "https://nuxref.com/api/v1/statuses"
    )
    assert (
        mock_post.call_args_list[3][0][0]
        == "https://nuxref.com/api/v1/statuses"
    )

    mock_get.reset_mock()
    mock_post.reset_mock()

    # Prepare a bad media response
    bad_response = mock.Mock()
    bad_response.status_code = requests.codes.internal_server_error

    bad_responses = (
        dumps({"error": "authorized scopes"}),
        "",
    )

    #
    # Test our Media failures
    #

    # Try several bad responses so we can capture the block of code where
    # we try to help the end user to remind them what scope they're missing
    for response in bad_responses:
        mock_post.side_effect = [good_media_response, bad_response]
        bad_response.content = response

        # instantiate our object
        mastodon_url = (
            f"mastodons://{akey}@{host}?visibility=public&spoiler=uhoh"
        )
        obj = Apprise.instantiate(mastodon_url)

        # Our notification will fail now since our toot will error out
        # This is the same test as above, except our error response isn't
        # parseable
        assert (
            obj.notify(
                body="body",
                title="title",
                notify_type=NotifyType.INFO,
                attach=attach,
            )
            is False
        )

        # Test our call count
        assert mock_get.call_count == 0
        assert mock_post.call_count == 2
        assert (
            mock_post.call_args_list[0][0][0]
            == "https://nuxref.com/api/v1/media"
        )
        assert (
            mock_post.call_args_list[1][0][0]
            == "https://nuxref.com/api/v1/media"
        )

        mock_get.reset_mock()
        mock_post.reset_mock()

    #
    # Test our Status failures
    #

    # Try several bad responses so we can capture the block of code where
    # we try to help the end user to remind them what scope they're missing
    for response in bad_responses:
        mock_post.side_effect = [bad_response]
        bad_response.content = response

        # instantiate our object
        mastodon_url = f"mastodons://{akey}@{host}"
        obj = Apprise.instantiate(mastodon_url)

        # Our notification will fail now since our toot will error out
        # This is the same test as above, except our error response isn't
        # parseable
        assert (
            obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
            is False
        )

        # Test our call count
        assert mock_get.call_count == 0
        assert mock_post.call_count == 1
        assert (
            mock_post.call_args_list[0][0][0]
            == "https://nuxref.com/api/v1/statuses"
        )

        mock_get.reset_mock()
        mock_post.reset_mock()

    #
    # Test our whoami failures
    #

    # Try several bad responses so we can capture the block of code where
    # we try to help the end user to remind them what scope they're missing
    for response in bad_responses:
        mock_get.side_effect = [bad_response]
        bad_response.content = response

        # instantiate our object
        mastodon_url = f"mastodons://{akey}@{host}?visibility=direct"
        obj = Apprise.instantiate(mastodon_url)

        # Our notification will fail now since our toot will error out
        # This is the same test as above, except our error response isn't
        # parseable
        assert (
            obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
            is False
        )

        # Test our call count
        assert mock_get.call_count == 1
        assert mock_post.call_count == 0
        assert (
            mock_get.call_args_list[0][0][0]
            == "https://nuxref.com/api/v1/accounts/verify_credentials"
        )

        mock_get.reset_mock()
        mock_post.reset_mock()

    mock_post.side_effect = [mr1, mr2, mr3, good_response, good_response]
    mock_get.return_value = None

    # instantiate our object
    mastodon_url = f"mastodons://{akey}@{host}"
    obj = Apprise.instantiate(mastodon_url)

    # An invalid attachment will cause a failure
    path = os.path.join(TEST_VAR_DIR, "/invalid/path/to/an/invalid/file.jpg")
    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=path,
        )
        is False
    )

    # No get requests are made
    assert mock_get.call_count == 0

    # No post request as attachment is no good anyway
    assert mock_post.call_count == 0

    mock_get.reset_mock()
    mock_post.reset_mock()

    # We have an OSError thrown in the middle of our preparation
    mock_post.side_effect = [
        good_media_response,
        OSError(),
        good_media_response,
    ]
    mock_get.return_value = good_response

    # 3 images are produced
    attach = [
        os.path.join(TEST_VAR_DIR, "apprise-test.gif"),
        # This one is not supported, so it's ignored gracefully
        os.path.join(TEST_VAR_DIR, "apprise-archive.zip"),
        # A supported video file
        os.path.join(TEST_VAR_DIR, "apprise-test.mp4"),
    ]

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

    assert mock_get.call_count == 0
    # No get request as cached response is used
    assert mock_post.call_count == 2
    assert (
        mock_post.call_args_list[0][0][0] == "https://nuxref.com/api/v1/media"
    )
    assert (
        mock_post.call_args_list[1][0][0] == "https://nuxref.com/api/v1/media"
    )
