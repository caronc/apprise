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
#
# Great Resources:
# - Dev/Legacy API:
#    https://firebase.google.com/docs/cloud-messaging/http-server-ref
# - Legacy API (v1) -> OAuth
# - https://firebase.google.com/docs/cloud-messaging/migrate-v1

import json
import os
import sys
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise
from apprise.plugins.fcm import NotifyFCM

try:
    from cryptography.exceptions import UnsupportedAlgorithm

    from apprise.plugins.fcm.color import FCMColorManager
    from apprise.plugins.fcm.common import FCM_MODES
    from apprise.plugins.fcm.oauth import GoogleOAuth
    from apprise.plugins.fcm.priority import FCM_PRIORITIES, FCMPriorityManager

except ImportError:
    # No problem; there is no cryptography support
    pass


# Disable logging for a cleaner testing output
import logging

logging.disable(logging.CRITICAL)

# Test files for KeyFile Directory
PRIVATE_KEYFILE_DIR = os.path.join(os.path.dirname(__file__), "var", "fcm")
FCM_KEYFILE = os.path.join(PRIVATE_KEYFILE_DIR, "service_account.json")


# Our Testing URLs
apprise_url_tests = (
    (
        "fcm://",
        {
            # We failed to identify any valid authentication
            "instance": TypeError,
        },
    ),
    (
        "fcm://:@/",
        {
            # We failed to identify any valid authentication
            "instance": TypeError,
        },
    ),
    (
        "fcm://project@%20%20/",
        {
            # invalid apikey
            "instance": TypeError,
        },
    ),
    (
        "fcm://apikey/",
        {
            # no project id specified so we operate in legacy mode
            "instance": NotifyFCM,
            # but there are no targets specified so we return False
            "notify_response": False,
        },
    ),
    (
        "fcm://apikey/device",
        {
            # Valid device
            "instance": NotifyFCM,
            "privacy_url": "fcm://a...y/device",
        },
    ),
    (
        "fcm://apikey/#topic",
        {
            # Valid topic
            "instance": NotifyFCM,
            "privacy_url": "fcm://a...y/%23topic",
        },
    ),
    (
        "fcm://apikey/device?mode=invalid",
        {
            # Valid device, invalid mode
            "instance": TypeError,
        },
    ),
    (
        "fcm://apikey/#topic1/device/%20/",
        {
            # Valid topic, valid device, and invalid entry
            "instance": NotifyFCM,
        },
    ),
    (
        "fcm://apikey?to=#topic1,device",
        {
            # Test to=
            "instance": NotifyFCM,
        },
    ),
    (
        "fcm://?apikey=abc123&to=device",
        {
            # Test apikey= to=
            "instance": NotifyFCM,
        },
    ),
    (
        "fcm://?apikey=abc123&to=device&image=yes",
        {
            # Test image boolean
            "instance": NotifyFCM,
        },
    ),
    (
        "fcm://?apikey=abc123&to=device&color=no",
        {
            # Disable colors
            "instance": NotifyFCM,
        },
    ),
    (
        "fcm://?apikey=abc123&to=device&color=aabbcc",
        {
            # custom colors
            "instance": NotifyFCM,
        },
    ),
    (
        (
            "fcm://?apikey=abc123&to=device"
            "&image_url=http://example.com/interesting.jpg"
        ),
        {
            # Test image_url
            "instance": NotifyFCM
        },
    ),
    (
        (
            "fcm://?apikey=abc123&to=device"
            "&image_url=http://example.com/interesting.jpg&image=no"
        ),
        {
            # Test image_url but set to no
            "instance": NotifyFCM
        },
    ),
    (
        "fcm://?apikey=abc123&to=device&+key=value&+key2=value2",
        {
            # Test apikey= to= and data arguments
            "instance": NotifyFCM,
        },
    ),
    (
        "fcm://%20?to=device&keyfile=/invalid/path",
        {
            # invalid Project ID
            "instance": TypeError,
        },
    ),
    (
        "fcm://project_id?to=device&keyfile=/invalid/path",
        {
            # Test to= and auto-detection of OAuth mode
            "instance": NotifyFCM,
            # we'll fail to send our notification as a result
            "response": False,
        },
    ),
    (
        "fcm://?to=device&project=project_id&keyfile=/invalid/path",
        {
            # Test project= & to= and auto detection of OAuth mode
            "instance": NotifyFCM,
            # we'll fail to send our notification as a result
            "response": False,
        },
    ),
    (
        "fcm://project_id?to=device&mode=oauth2",
        {
            # no keyfile was specified
            "instance": TypeError,
        },
    ),
    (
        "fcm://project_id?to=device&mode=oauth2&keyfile=/invalid/path",
        {
            # Same test as above except we explicitly set our oauth2 mode
            # Test to= and auto-detection of OAuth mode
            "instance": NotifyFCM,
            # we'll fail to send our notification as a result
            "response": False,
        },
    ),
    (
        "fcm://apikey/#topic1/device/?mode=legacy",
        {
            "instance": NotifyFCM,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "fcm://apikey/#topic1/device/?mode=legacy",
        {
            "instance": NotifyFCM,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
    (
        "fcm://project/#topic1/device/?mode=oauth2&keyfile=file://{}".format(
            os.path.join(
                os.path.dirname(__file__), "var", "fcm", "service_account.json"
            )
        ),
        {
            "instance": NotifyFCM,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "fcm://projectid/#topic1/device/?mode=oauth2&keyfile=file://{}".format(
            os.path.join(
                os.path.dirname(__file__), "var", "fcm", "service_account.json"
            )
        ),
        {
            "instance": NotifyFCM,
            # Throws a series of connection and transfer exceptions when
            # this flag is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


@pytest.fixture
def mock_post(mocker):
    """Prepare a good OAuth mock response."""

    mock_thing = mocker.patch("requests.post")

    response = mock.Mock()
    response.content = json.dumps({
        "access_token": "ya29.c.abcd",
        "expires_in": 3599,
        "token_type": "Bearer",
    })
    response.status_code = requests.codes.ok
    mock_thing.return_value = response

    return mock_thing


@pytest.fixture
def mock_post_legacy(mocker):
    """Prepare a good legacy mock response."""

    mock_thing = mocker.patch("requests.post")

    response = mock.Mock()
    response.status_code = requests.codes.ok
    mock_thing.return_value = response

    return mock_thing


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_fcm_urls():
    """NotifyFCM() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_fcm_legacy_default(mock_post_legacy):
    """NotifyFCM() Legacy/APIKey default checks."""

    # A valid Legacy URL
    obj = Apprise.instantiate(
        "fcm://abc123/device/"
        "?+key=value&+key2=value2"
        "&image_url=https://example.com/interesting.png"
    )

    # Send our notification
    assert obj.notify("test") is True

    # Test our call count
    assert mock_post_legacy.call_count == 1
    assert (
        mock_post_legacy.call_args_list[0][0][0]
        == "https://fcm.googleapis.com/fcm/send"
    )

    payload = mock_post_legacy.mock_calls[0][2]
    data = json.loads(payload["data"])
    assert "data" in data
    assert isinstance(data, dict)
    assert "key" in data["data"]
    assert data["data"]["key"] == "value"
    assert "key2" in data["data"]
    assert data["data"]["key2"] == "value2"

    assert "notification" in data
    assert isinstance(data["notification"], dict)
    assert "notification" in data["notification"]
    assert isinstance(data["notification"]["notification"], dict)
    assert "image" in data["notification"]["notification"]
    assert (
        data["notification"]["notification"]["image"]
        == "https://example.com/interesting.png"
    )


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_fcm_legacy_priorities(mock_post_legacy):
    """NotifyFCM() Legacy/APIKey priorities checks."""

    obj = Apprise.instantiate("fcm://abc123/device/?priority=low")
    assert mock_post_legacy.call_count == 0

    # Send our notification
    assert obj.notify(title="title", body="body") is True

    # Test our call count
    assert mock_post_legacy.call_count == 1
    assert (
        mock_post_legacy.call_args_list[0][0][0]
        == "https://fcm.googleapis.com/fcm/send"
    )

    payload = mock_post_legacy.mock_calls[0][2]
    data = json.loads(payload["data"])
    assert "data" not in data
    assert "notification" in data
    assert isinstance(data["notification"], dict)
    assert "notification" in data["notification"]
    assert isinstance(data["notification"]["notification"], dict)
    assert "image" not in data["notification"]["notification"]
    assert "priority" in data

    # legacy can only switch between high/low
    assert data["priority"] == "normal"


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_fcm_legacy_no_colors(mock_post_legacy):
    """NotifyFCM() Legacy/APIKey `color=no` checks."""

    obj = Apprise.instantiate("fcm://abc123/device/?color=no")
    assert mock_post_legacy.call_count == 0

    # Send our notification
    assert obj.notify(title="title", body="body") is True

    # Test our call count
    assert mock_post_legacy.call_count == 1
    assert (
        mock_post_legacy.call_args_list[0][0][0]
        == "https://fcm.googleapis.com/fcm/send"
    )

    payload = mock_post_legacy.mock_calls[0][2]
    data = json.loads(payload["data"])
    assert "data" not in data
    assert "notification" in data
    assert isinstance(data["notification"], dict)
    assert "notification" in data["notification"]
    assert isinstance(data["notification"]["notification"], dict)
    assert "image" not in data["notification"]["notification"]
    assert "color" not in data["notification"]["notification"]


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_fcm_legacy_colors(mock_post_legacy):
    """NotifyFCM() Legacy/APIKey colors checks."""

    obj = Apprise.instantiate("fcm://abc123/device/?color=AA001b")
    assert mock_post_legacy.call_count == 0

    # Send our notification
    assert obj.notify(title="title", body="body") is True

    # Test our call count
    assert mock_post_legacy.call_count == 1
    assert (
        mock_post_legacy.call_args_list[0][0][0]
        == "https://fcm.googleapis.com/fcm/send"
    )

    payload = mock_post_legacy.mock_calls[0][2]
    data = json.loads(payload["data"])
    assert "data" not in data
    assert "notification" in data
    assert isinstance(data["notification"], dict)
    assert "notification" in data["notification"]
    assert isinstance(data["notification"]["notification"], dict)
    assert "image" not in data["notification"]["notification"]
    assert "color" in data["notification"]["notification"]
    assert data["notification"]["notification"]["color"] == "#aa001b"


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_fcm_oauth_default(mock_post):
    """
    NotifyFCM() general OAuth checks - success.
    Test using a valid Project ID and key file.
    """

    obj = Apprise.instantiate(
        f"fcm://mock-project-id/device/#topic/?keyfile={FCM_KEYFILE}"
    )

    # send our notification
    assert obj.notify("test") is True

    # Test our call count
    assert mock_post.call_count == 3
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://accounts.google.com/o/oauth2/token"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == "https://fcm.googleapis.com/v1/projects/mock-project-id/messages:send"
    )
    assert (
        mock_post.call_args_list[2][0][0]
        == "https://fcm.googleapis.com/v1/projects/mock-project-id/messages:send"
    )


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_fcm_oauth_invalid_project_id(mock_post):
    """NotifyFCM() OAuth checks, with invalid project id."""

    # Test having a valid keyfile, but not a valid project id match.
    obj = Apprise.instantiate(
        f"fcm://invalid_project_id/device/?keyfile={FCM_KEYFILE}"
    )

    # we'll fail as a result
    assert obj.notify("test") is False

    # Test our call count
    assert mock_post.call_count == 0


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_fcm_oauth_keyfile_error(mock_post):
    """NotifyFCM() OAuth checks, while unable to read key file."""

    # Now we test using a valid Project ID but we can't open our file
    obj = Apprise.instantiate(
        f"fcm://mock-project-id/device/?keyfile={FCM_KEYFILE}"
    )

    with mock.patch("builtins.open", side_effect=OSError):
        # we'll fail as a result
        assert obj.notify("test") is False

    # Test our call count
    assert mock_post.call_count == 0


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_fcm_oauth_data_parameters(mock_post):
    """NotifyFCM() OAuth checks, success.

    Test using a valid Project ID and data parameters.
    """

    obj = Apprise.instantiate(
        f"fcm://mock-project-id/device/#topic/?keyfile={FCM_KEYFILE}"
        "&+key=value&+key2=value2"
        "&image_url=https://example.com/interesting.png"
    )
    assert mock_post.call_count == 0

    # send our notification
    assert obj.notify("test") is True

    # Test our call count
    assert mock_post.call_count == 3
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://accounts.google.com/o/oauth2/token"
    )

    assert (
        mock_post.call_args_list[1][0][0]
        == "https://fcm.googleapis.com/v1/projects/mock-project-id/messages:send"
    )
    payload = mock_post.mock_calls[1][2]
    data = json.loads(payload["data"])
    assert "message" in data
    assert isinstance(data["message"], dict)
    assert "data" in data["message"]
    assert isinstance(data["message"]["data"], dict)
    assert "key" in data["message"]["data"]
    assert data["message"]["data"]["key"] == "value"
    assert "key2" in data["message"]["data"]
    assert data["message"]["data"]["key2"] == "value2"

    assert "notification" in data["message"]
    assert isinstance(data["message"]["notification"], dict)
    assert "image" in data["message"]["notification"]
    assert (
        data["message"]["notification"]["image"]
        == "https://example.com/interesting.png"
    )

    assert (
        mock_post.call_args_list[2][0][0]
        == "https://fcm.googleapis.com/v1/projects/mock-project-id/messages:send"
    )

    payload = mock_post.mock_calls[2][2]
    data = json.loads(payload["data"])
    assert "message" in data
    assert isinstance(data["message"], dict)
    assert "data" in data["message"]
    assert isinstance(data["message"]["data"], dict)
    assert "key" in data["message"]["data"]
    assert data["message"]["data"]["key"] == "value"
    assert "key2" in data["message"]["data"]
    assert data["message"]["data"]["key2"] == "value2"

    assert "notification" in data["message"]
    assert isinstance(data["message"]["notification"], dict)
    assert "image" in data["message"]["notification"]
    assert (
        data["message"]["notification"]["image"]
        == "https://example.com/interesting.png"
    )


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_fcm_oauth_priorities(mock_post):
    """Verify priorities work as intended."""

    obj = Apprise.instantiate(
        f"fcm://mock-project-id/device/?keyfile={FCM_KEYFILE}&priority=high"
    )
    assert mock_post.call_count == 0

    # Send our notification
    assert obj.notify(title="title", body="body") is True

    # Test our call count
    assert mock_post.call_count == 2
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://accounts.google.com/o/oauth2/token"
    )

    assert (
        mock_post.call_args_list[1][0][0]
        == "https://fcm.googleapis.com/v1/projects/mock-project-id/messages:send"
    )
    payload = mock_post.mock_calls[1][2]
    data = json.loads(payload["data"])
    assert "message" in data
    assert isinstance(data["message"], dict)
    assert "data" not in data["message"]
    assert "notification" in data["message"]
    assert isinstance(data["message"]["notification"], dict)
    assert "image" not in data["message"]["notification"]
    assert data["message"]["apns"]["headers"]["apns-priority"] == "10"
    assert data["message"]["webpush"]["headers"]["Urgency"] == "high"
    assert data["message"]["android"]["priority"] == "HIGH"


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_fcm_oauth_no_colors(mock_post):
    """Verify `color=no` work as intended."""

    obj = Apprise.instantiate(
        f"fcm://mock-project-id/device/?keyfile={FCM_KEYFILE}&color=no"
    )
    assert mock_post.call_count == 0

    # Send our notification
    assert obj.notify(title="title", body="body") is True

    # Test our call count
    assert mock_post.call_count == 2
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://accounts.google.com/o/oauth2/token"
    )

    assert (
        mock_post.call_args_list[1][0][0]
        == "https://fcm.googleapis.com/v1/projects/mock-project-id/messages:send"
    )
    payload = mock_post.mock_calls[1][2]
    data = json.loads(payload["data"])
    assert "message" in data
    assert isinstance(data["message"], dict)
    assert "data" not in data["message"]
    assert "notification" in data["message"]
    assert isinstance(data["message"]["notification"], dict)
    assert "color" not in data["message"]["notification"]


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_fcm_oauth_colors(mock_post):
    """Verify colors work as intended."""

    obj = Apprise.instantiate(
        f"fcm://mock-project-id/device/?keyfile={FCM_KEYFILE}&color=#12AAbb"
    )
    assert mock_post.call_count == 0

    # Send our notification
    assert obj.notify(title="title", body="body") is True

    # Test our call count
    assert mock_post.call_count == 2
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://accounts.google.com/o/oauth2/token"
    )

    assert (
        mock_post.call_args_list[1][0][0]
        == "https://fcm.googleapis.com/v1/projects/mock-project-id/messages:send"
    )
    payload = mock_post.mock_calls[1][2]
    data = json.loads(payload["data"])
    assert "message" in data
    assert isinstance(data["message"], dict)
    assert "data" not in data["message"]
    assert "notification" in data["message"]
    assert isinstance(data["message"]["notification"], dict)
    assert "color" in data["message"]["android"]["notification"]
    assert data["message"]["android"]["notification"]["color"] == "#12aabb"


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_fcm_keyfile_parse_default(mock_post):
    """NotifyFCM() KeyFile Tests."""

    oauth = GoogleOAuth()
    # We can not get an Access Token without content loaded
    assert oauth.access_token is None

    # Load our content
    assert oauth.load(FCM_KEYFILE) is True
    assert oauth.access_token is not None

    # Test our call count
    assert mock_post.call_count == 1
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://accounts.google.com/o/oauth2/token"
    )

    mock_post.reset_mock()

    # a second call uses cache since our token hasn't expired yet
    assert oauth.access_token is not None
    assert mock_post.call_count == 0


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_fcm_keyfile_parse_no_expiry(mock_post):
    """Test case without `expires_in` entry."""

    mock_post.return_value.content = json.dumps({
        "access_token": "ya29.c.abcd",
        "token_type": "Bearer",
    })

    oauth = GoogleOAuth()
    assert oauth.load(FCM_KEYFILE) is True
    assert oauth.access_token is not None

    # Test our call count
    assert mock_post.call_count == 1
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://accounts.google.com/o/oauth2/token"
    )


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_fcm_keyfile_parse_user_agent(mock_post):
    """Test case with `user-agent` override."""

    oauth = GoogleOAuth(user_agent="test-agent-override")
    assert oauth.load(FCM_KEYFILE) is True
    assert oauth.access_token is not None
    assert mock_post.call_count == 1
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://accounts.google.com/o/oauth2/token"
    )


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_fcm_keyfile_parse_keyfile_failures(mock_post: mock.Mock):
    """Test some errors that can get thrown when trying to handle the
    `service_account.json` file."""

    # Now we test a case where we can't access the file we've been pointed to:
    oauth = GoogleOAuth()
    with mock.patch("builtins.open", side_effect=OSError):
        # We will fail to retrieve our Access Token
        assert oauth.load(FCM_KEYFILE) is False
        assert oauth.access_token is None

    oauth = GoogleOAuth()
    with mock.patch("json.loads", side_effect=([],)):
        # We will fail to retrieve our Access Token since we did not parse
        # a dictionary
        assert oauth.load(FCM_KEYFILE) is False
        assert oauth.access_token is None

    # Case where we can't load the PEM key:
    oauth = GoogleOAuth()
    with mock.patch(
        "cryptography.hazmat.primitives.serialization.load_pem_private_key",
        side_effect=ValueError(""),
    ):
        assert oauth.load(FCM_KEYFILE) is False
        assert oauth.access_token is None

    # Case where we can't load the PEM key:
    oauth = GoogleOAuth()
    with mock.patch(
        "cryptography.hazmat.primitives.serialization.load_pem_private_key",
        side_effect=TypeError(""),
    ):
        assert oauth.load(FCM_KEYFILE) is False
        assert oauth.access_token is None

    # Case where we can't load the PEM key:
    oauth = GoogleOAuth()
    with mock.patch(
        "cryptography.hazmat.primitives.serialization.load_pem_private_key",
        side_effect=UnsupportedAlgorithm(""),
    ):
        # Note: This test should be te
        assert oauth.load(FCM_KEYFILE) is False
        assert oauth.access_token is None

    # Verify that not a single call to the web escaped the test harness.
    assert mock_post.mock_calls == []


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_fcm_keyfile_parse_token_failures(mock_post):
    """Test some web errors that can occur when speaking upstream with Google
    to get our token generated."""

    mock_post.return_value.status_code = requests.codes.internal_server_error

    oauth = GoogleOAuth()
    assert oauth.load(FCM_KEYFILE) is True

    # We'll fail due to an bad web response
    assert oauth.access_token is None

    # Return our status code to how it was
    mock_post.return_value.status_code = requests.codes.ok

    # No access token
    bad_response_1 = mock.Mock()
    bad_response_1.content = json.dumps({
        "expires_in": 3599,
        "token_type": "Bearer",
    })

    # Invalid JSON
    bad_response_2 = mock.Mock()
    bad_response_2.content = "{"

    mock_post.return_value = None
    # Throw an exception on the first call to requests.post()
    for side_effect in (
        requests.RequestException(),
        bad_response_1,
        bad_response_2,
    ):
        mock_post.side_effect = side_effect

        # Test all of our bad side effects
        oauth = GoogleOAuth()
        assert oauth.load(FCM_KEYFILE) is True

        # We'll fail due to an bad web response
        assert oauth.access_token is None


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_fcm_bad_keyfile_parse():
    """NotifyFCM() KeyFile Bad Service Account Type Tests."""

    path = os.path.join(PRIVATE_KEYFILE_DIR, "service_account-bad-type.json")
    oauth = GoogleOAuth()
    assert oauth.load(path) is False


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_fcm_keyfile_missing_entries_parse(tmpdir):
    """NotifyFCM() KeyFile Missing Entries Test."""

    # Prepare a base keyfile reference to use
    path = os.path.join(PRIVATE_KEYFILE_DIR, "service_account.json")
    with open(path, encoding="utf-8") as fp:
        content = json.loads(fp.read())

    path = tmpdir.join("fcm_keyfile.json")

    # Test that we fail to load if the following keys are missing:
    for entry in (
        "client_email",
        "private_key_id",
        "private_key",
        "type",
        "project_id",
    ):

        # Ensure the key actually exists in our file
        assert entry in content

        # Create a copy of our content
        content_copy = content.copy()

        # Remove our entry we expect to validate against
        del content_copy[entry]
        assert entry not in content_copy

        path.write(json.dumps(content_copy))

        oauth = GoogleOAuth()
        assert oauth.load(str(path)) is False

    # Now write ourselves a bad JSON file
    path.write("{")
    oauth = GoogleOAuth()
    assert oauth.load(str(path)) is False


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_fcm_priority_manager():
    """NotifyFCM() FCMPriorityManager() Testing."""

    for mode in FCM_MODES:
        for priority in FCM_PRIORITIES:
            instance = FCMPriorityManager(mode, priority)
            assert isinstance(instance.payload(), dict)
            # Verify it's not empty
            assert bool(instance)
            assert instance.payload()
            assert str(instance) == priority

    # We do not have to set a priority
    instance = FCMPriorityManager(mode)
    assert isinstance(instance.payload(), dict)

    # Dictionary is empty though
    assert not bool(instance)
    assert not instance.payload()
    assert str(instance) == ""

    with pytest.raises(TypeError):
        instance = FCMPriorityManager(mode, "invalid")

    with pytest.raises(TypeError):
        instance = FCMPriorityManager("invald", "high")

    # mode validation is done at the higher NotifyFCM() level so
    # it is not tested here (not required)


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_fcm_color_manager():
    """NotifyFCM() FCMColorManager() Testing."""

    # No colors
    instance = FCMColorManager("no")
    assert bool(instance) is False
    assert instance.get() is None
    # We'll return that we are not defined
    assert str(instance) == "no"

    # Asset colors
    instance = FCMColorManager("yes")
    assert isinstance(instance.get(), str)
    # Output: #rrggbb
    assert len(instance.get()) == 7
    # Starts with has symbol
    assert instance.get()[0] == "#"
    # We'll return that we are defined but using default configuration
    assert str(instance) == "yes"

    # We will be `true` because we can acquire a color based on what was
    # passed in
    assert bool(instance)

    # Custom color
    instance = FCMColorManager("#A2B3A4")
    assert isinstance(instance.get(), str)
    assert instance.get() == "#a2b3a4"
    assert bool(instance)
    # str() response does not include hashtag
    assert str(instance) == "a2b3a4"

    # Custom color (no hashtag)
    instance = FCMColorManager("A2B3A4")
    assert isinstance(instance.get(), str)
    # Hashtag is always part of output
    assert instance.get() == "#a2b3a4"
    assert bool(instance)
    # str() response does not include hashtag
    assert str(instance) == "a2b3a4"

    # Custom color (no hashtag) but only using 3 letter rgb values
    instance = FCMColorManager("AC4")
    assert isinstance(instance.get(), str)
    # Hashtag is always part of output
    assert instance.get() == "#aacc44"
    assert bool(instance)
    # str() response does not include hashtag
    assert str(instance) == "aacc44"


@pytest.mark.skipif(
    "cryptography" in sys.modules,
    reason="Requires that cryptography NOT be installed",
)
def test_plugin_fcm_cryptography_import_error():
    """NotifyFCM Cryptography loading failure."""

    # Prepare a base keyfile reference to use
    path = os.path.join(PRIVATE_KEYFILE_DIR, "service_account.json")

    # Attempt to instantiate our object
    obj = Apprise.instantiate(
        f"fcm://mock-project-id/device/#topic/?keyfile={path!s}"
    )

    # It's not possible because our cryptography depedancy is missing
    assert obj is None


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
@mock.patch("requests.post")
def test_plugin_fcm_edge_cases(mock_post):
    """NotifyFCM() Edge Cases."""

    # Prepare a good response
    response = mock.Mock()
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    # this tests an edge case where verify if the data_kwargs is a dictionary
    # or not.  Below, we don't even define it, so it will be None (causing
    # the check to go).  We'll still correctly instantiate a plugin:
    obj = NotifyFCM("project", "api:123", targets="device")
    assert obj is not None
