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

from json import dumps, loads

# Disable logging for a cleaner testing output
import logging
import os
from typing import Union
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import (
    Apprise,
    AppriseAsset,
    AppriseAttachment,
    NotifyType,
    PersistentStoreMode,
)
from apprise.plugins.matrix import MatrixDiscoveryException, NotifyMatrix

logging.disable(logging.CRITICAL)

MATRIX_GOOD_RESPONSE = dumps(
    {
        "room_id": "!abc123:localhost",
        "room_alias": "#abc123:localhost",
        "joined_rooms": ["!abc123:localhost", "!def456:localhost"],
        "access_token": "abcd1234",
        "home_server": "localhost",
        # user_id is returned by /login and /account/whoami; including it
        # here ensures self.user_id is set after login so _whoami() is not
        # called unnecessarily (it only fires when user_id is still absent).
        "user_id": "@apprise:localhost",
        # Simulate .well-known
        "m.homeserver": {"base_url": "https://matrix.example.com"},
        "m.identity_server": {"base_url": "https://vector.im"},
    }
)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# Our Testing URLs
apprise_url_tests = (
    ##################################
    # NotifyMatrix
    ##################################
    (
        "matrix://",
        {
            "instance": None,
        },
    ),
    (
        "matrixs://",
        {
            "instance": None,
        },
    ),
    (
        "matrix://localhost?mode=off",
        {
            # treats it as a anonymous user to register
            "instance": NotifyMatrix,
            # response is false because we have nothing to notify
            "response": False,
        },
    ),
    (
        "matrix://localhost",
        {
            # response is TypeError because we'll try to initialize as
            # a t2bot and fail (localhost is too short of a api key)
            "instance": TypeError
        },
    ),
    (
        "matrix://user:pass@localhost/#room1/#room2/#room3",
        {
            "instance": NotifyMatrix,
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "matrix://user:pass@localhost/#room1/#room2/!room1",
        {
            "instance": NotifyMatrix,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "matrix://user:pass@localhost:1234/#room",
        {
            "instance": NotifyMatrix,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "matrix://user:****@localhost:1234/",
        },
    ),
    # Matrix supports webhooks too; the following tests this now:
    (
        "matrix://user:token@localhost?mode=matrix&format=text",
        {
            # user and token correctly specified with webhook
            "instance": NotifyMatrix,
            "response": False,
        },
    ),
    (
        "matrix://user:token@localhost?mode=matrix&format=html",
        {
            # user and token correctly specified with webhook
            "instance": NotifyMatrix,
        },
    ),
    (
        "matrix://user:token@localhost:123/#general/?version=3",
        {
            # Provide version over-ride (using version=)
            "instance": NotifyMatrix,
            # Our response expected server response
            "requests_response_text": MATRIX_GOOD_RESPONSE,
            "privacy_url": "matrix://user:****@localhost:123",
        },
    ),
    (
        "matrixs://user:token@localhost/#general?v=2",
        {
            # Provide version over-ride (using v=)
            "instance": NotifyMatrix,
            # Our response expected server response
            "requests_response_text": MATRIX_GOOD_RESPONSE,
            "privacy_url": "matrixs://user:****@localhost",
        },
    ),
    (
        "matrix://user:token@localhost:123/#general/?v=invalid",
        {
            # Invalid version specified
            "instance": TypeError
        },
    ),
    (
        "matrix://user:token@localhost?mode=slack&format=text",
        {
            # user and token correctly specified with webhook
            "instance": NotifyMatrix,
        },
    ),
    (
        "matrixs://user:token@localhost?mode=SLACK&format=markdown",
        {
            # user and token specified; slack webhook still detected
            # despite uppercase characters
            "instance": NotifyMatrix,
        },
    ),
    (
        "matrix://user@localhost?mode=SLACK&format=markdown&token=mytoken",
        {
            # user and token specified; slack webhook still detected
            # despite uppercase characters; token also set on URL as arg
            "instance": NotifyMatrix,
        },
    ),
    (
        "matrix://_?mode=t2bot&token={}".format("b" * 64),
        {
            # Testing t2bot initialization and setting the password using the
            # token directive
            "instance": NotifyMatrix,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "matrix://b...b/",
        },
    ),
    (
        (
            "matrixs://hookuser:hooktoken@hookshot.example"
            "?mode=hookshot&path=%2Fpublic-hooks"
        ),
        {
            "instance": NotifyMatrix,
            "privacy_url": (
                "matrixs://hookuser:****@hookshot.example/"
                "?image=no&mode=hookshot"
            ),
        },
    ),
    (
        (
            "matrixs://hookuser:hooktoken@hookshot.example"
            "?mode=hookshot&path=public-hooks"
        ),
        {
            "instance": NotifyMatrix,
        },
    ),
    # Image Reference
    (
        "matrixs://user:token@localhost?mode=slack&format=markdown&image=True",
        {
            # user and token specified; image set to True
            "instance": NotifyMatrix,
        },
    ),
    (
        (
            "matrixs://user:token@localhost?mode=slack"
            "&format=markdown&image=False"
        ),
        {
            # user and token specified; image set to True
            "instance": NotifyMatrix,
        },
    ),
    # A Bunch of bad ports
    (
        "matrixs://user:pass@hostname:port/#room_alias",
        {
            # Invalid Port specified (was a string)
            "instance": TypeError,
        },
    ),
    (
        "matrixs://user:pass@hostname:0/#room_alias",
        {
            # Invalid Port specified (was a string)
            "instance": TypeError,
        },
    ),
    (
        "matrixs://user:pass@hostname:65536/#room_alias",
        {
            # Invalid Port specified (was a string)
            "instance": TypeError,
        },
    ),
    # More general testing...
    (
        "matrixs://user@{}?mode=t2bot&format=markdown&image=True".format(
            "a" * 64
        ),
        {
            # user and token specified; image set to True
            "instance": NotifyMatrix
        },
    ),
    (
        "matrix://user@{}?mode=t2bot&format=html&image=False".format("z" * 64),
        {
            # user and token specified; image set to True
            "instance": NotifyMatrix
        },
    ),
    # This will default to t2bot because no targets were specified and no
    # password
    (
        "matrixs://{}".format("c" * 64),
        {
            "instance": NotifyMatrix,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
    # Test Native URL
    (
        "https://webhooks.t2bot.io/api/v1/matrix/hook/{}/".format("d" * 64),
        {
            # user and token specified; image set to True
            "instance": NotifyMatrix,
        },
    ),
    (
        "matrix://user:token@localhost?mode=On",
        {
            # invalid webhook specified (unexpected boolean)
            "instance": TypeError,
        },
    ),
    (
        "matrix://token@localhost/?mode=Matrix",
        {
            "instance": NotifyMatrix,
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "matrix://user:token@localhost/mode=matrix",
        {
            "instance": NotifyMatrix,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "matrix://token@localhost:8080/?mode=slack",
        {
            "instance": NotifyMatrix,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
    (
        "matrix://{}/?mode=t2bot".format("b" * 64),
        {
            "instance": NotifyMatrix,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_matrix_urls():
    """NotifyMatrix() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_matrix_general(mock_post, mock_get, mock_put):
    """NotifyMatrix() General Tests."""

    response_obj = {
        "room_id": "!abc123:localhost",
        "room_alias": "#abc123:localhost",
        "joined_rooms": ["!abc123:localhost", "!def456:localhost"],
        "access_token": "abcd1234",
        "home_server": "localhost",
    }
    request = mock.Mock()
    request.content = dumps(response_obj)
    request.status_code = requests.codes.ok

    # Prepare Mock
    mock_get.return_value = request
    mock_post.return_value = request
    mock_put.return_value = request

    # Variation Initializations
    obj = NotifyMatrix(host="host", targets="#abcd")
    assert isinstance(obj, NotifyMatrix)
    assert isinstance(obj.url(), str)
    # Registration successful
    assert obj.send(body="test") is True
    del obj

    obj = NotifyMatrix(host="host", user="user", targets="#abcd")
    assert isinstance(obj, NotifyMatrix)
    assert isinstance(obj.url(), str)
    # Registration successful
    assert obj.send(body="test") is True
    del obj

    obj = NotifyMatrix(host="host", password="passwd", targets="#abcd")
    assert isinstance(obj, NotifyMatrix)
    assert isinstance(obj.url(), str)
    # A username gets automatically generated in these cases
    assert obj.send(body="test") is True
    del obj

    obj = NotifyMatrix(
        host="host", user="user", password="passwd", targets="#abcd"
    )
    assert isinstance(obj.url(), str)
    assert isinstance(obj, NotifyMatrix)
    # Registration Successful
    assert obj.send(body="test") is True
    del obj

    # Test sending other format types
    kwargs = NotifyMatrix.parse_url(
        "matrix://user:passwd@hostname/#abcd?format=html"
    )
    obj = NotifyMatrix(**kwargs)
    assert isinstance(obj.url(), str)
    assert isinstance(obj, NotifyMatrix)
    assert obj.send(body="test") is True
    assert obj.send(title="title", body="test") is True
    del obj

    kwargs = NotifyMatrix.parse_url(
        "matrix://user:passwd@hostname/#abcd/#abcd:localhost?format=markdown"
    )
    obj = NotifyMatrix(**kwargs)
    assert isinstance(obj.url(), str)
    assert isinstance(obj, NotifyMatrix)
    assert obj.send(body="test") is True
    assert obj.send(title="title", body="test") is True
    del obj

    kwargs = NotifyMatrix.parse_url(
        "matrix://user:passwd@hostname/#abcd/!abcd:localhost?format=text"
    )
    obj = NotifyMatrix(**kwargs)
    assert isinstance(obj.url(), str)
    assert isinstance(obj, NotifyMatrix) is True
    assert obj.send(body="test") is True
    assert obj.send(title="title", body="test") is True
    del obj

    # Test notice type notifications
    kwargs = NotifyMatrix.parse_url(
        "matrix://user:passwd@hostname/#abcd?msgtype=notice"
    )
    obj = NotifyMatrix(**kwargs)
    assert isinstance(obj.url(), str) is True
    assert isinstance(obj, NotifyMatrix) is True
    assert obj.send(body="test") is True
    assert obj.send(title="title", body="test") is True

    with pytest.raises(TypeError):
        # invalid message type specified
        kwargs = NotifyMatrix.parse_url(
            "matrix://user:passwd@hostname/#abcd?msgtype=invalid"
        )
        NotifyMatrix(**kwargs)

    # Force a failed login
    ro = response_obj.copy()
    del ro["access_token"]
    request.content = dumps(ro)
    request.status_code = 404

    # Fails because we couldn't register because of 404 errors
    assert obj.send(body="test") is False
    del obj

    obj = NotifyMatrix(host="host", user="test", targets="#abcd")
    assert isinstance(obj, NotifyMatrix) is True
    # Fails because we still couldn't register
    assert obj.send(user="test", password="passwd", body="test") is False
    del obj

    obj = NotifyMatrix(
        host="host", user="test", password="passwd", targets="#abcd"
    )
    assert isinstance(obj, NotifyMatrix) is True
    # Fails because we still couldn't register
    assert obj.send(body="test") is False
    del obj

    obj = NotifyMatrix(host="host", password="passwd", targets="#abcd")
    # Fails because we still couldn't register
    assert isinstance(obj, NotifyMatrix) is True
    assert obj.send(body="test") is False

    # Force a empty joined list response
    ro = response_obj.copy()
    ro["joined_rooms"] = []
    request.content = dumps(ro)
    assert obj.send(user="test", password="passwd", body="test") is False

    # Fall back to original template
    request.content = dumps(response_obj)
    request.status_code = requests.codes.ok

    # update our response object so logins now succeed
    response_obj["user_id"] = "@apprise:localhost"

    # Login was successful but not get a room_id
    ro = response_obj.copy()
    del ro["room_id"]
    request.content = dumps(ro)
    assert obj.send(user="test", password="passwd", body="test") is False

    # Fall back to original template
    request.content = dumps(response_obj)
    request.status_code = requests.codes.ok
    del obj

    obj = NotifyMatrix(host="host", targets=None)
    assert isinstance(obj, NotifyMatrix) is True

    # Force a empty joined list response
    ro = response_obj.copy()
    ro["joined_rooms"] = []
    request.content = dumps(ro)
    assert obj.send(user="test", password="passwd", body="test") is False

    # Fall back to original template
    request.content = dumps(response_obj)
    request.status_code = requests.codes.ok

    # our room list is empty so we'll have retrieved the joined_list
    # as our backup
    assert obj.send(user="test", password="passwd", body="test") is True
    del obj


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_matrix_fetch(mock_post, mock_get, mock_put):
    """NotifyMatrix() Server Fetch/API Tests."""

    response_obj = {
        "room_id": "!abc123:localhost",
        "room_alias": "#abc123:localhost",
        "joined_rooms": ["!abc123:localhost", "!def456:localhost"],
        # Login details
        "access_token": "abcd1234",
        "user_id": "@apprise:localhost",
        "home_server": "localhost",
    }

    def fetch_failed(url, *args, **kwargs):

        # Default configuration
        request = mock.Mock()
        request.status_code = requests.codes.ok
        request.content = dumps(response_obj)

        if url.find("/rooms/") > -1:
            # over-ride on room query
            request.status_code = 403
            request.content = dumps(
                {
                    "errcode": "M_UNKNOWN",
                    "error": "Internal server error",
                }
            )

        return request

    mock_put.side_effect = fetch_failed
    mock_get.side_effect = fetch_failed
    mock_post.side_effect = fetch_failed

    obj = NotifyMatrix(
        host="host", user="user", password="passwd", include_image=True
    )
    assert isinstance(obj, NotifyMatrix) is True
    # We would hve failed to send our image notification
    assert obj.send(user="test", password="passwd", body="test") is False
    del obj

    # Do the same query with no images to fetch
    asset = AppriseAsset(image_path_mask=False, image_url_mask=False)
    obj = NotifyMatrix(
        host="host", user="user", password="passwd", asset=asset
    )
    assert isinstance(obj, NotifyMatrix) is True
    # We would hve failed to send our notification
    assert obj.send(user="test", password="passwd", body="test") is False
    del obj

    response_obj = {
        # Registration
        "access_token": "abcd1234",
        "user_id": "@apprise:localhost",
        "home_server": "localhost",
        # For room joining
        "room_id": "!abc123:localhost",
    }

    # Default configuration
    mock_get.side_effect = None
    mock_post.side_effect = None
    mock_put.side_effect = None

    request = mock.Mock()
    request.status_code = requests.codes.ok
    request.content = dumps(response_obj)
    mock_post.return_value = request
    mock_get.return_value = request
    mock_put.return_value = request

    obj = NotifyMatrix(host="host", include_image=True)
    assert isinstance(obj, NotifyMatrix) is True
    assert obj.access_token is None
    assert obj._register() is True
    assert obj.access_token is not None

    # Cause retries
    request.status_code = 429
    request.content = dumps(
        {
            "retry_after_ms": 1,
        }
    )

    postokay, _response, _ = obj._fetch("/retry/apprise/unit/test")
    assert postokay is False

    request.content = dumps(
        {
            "error": {
                "retry_after_ms": 1,
            }
        }
    )
    postokay, _response, _ = obj._fetch("/retry/apprise/unit/test")
    assert postokay is False

    request.content = dumps({"error": {}})
    postokay, _response, _ = obj._fetch("/retry/apprise/unit/test")
    assert postokay is False
    del obj


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_matrix_auth(mock_post, mock_get, mock_put):
    """NotifyMatrix() Server Authentication."""

    response_obj = {
        # Registration
        "access_token": "abcd1234",
        "user_id": "@apprise:localhost",
        "home_server": "localhost",
    }

    # Default configuration
    request = mock.Mock()
    request.status_code = requests.codes.ok
    request.content = dumps(response_obj)
    mock_post.return_value = request
    mock_get.return_value = request
    mock_put.return_value = request

    obj = NotifyMatrix(host="localhost")
    assert isinstance(obj, NotifyMatrix) is True
    assert obj.access_token is None
    # logging out without an access_token is silently a success
    assert obj._logout() is True
    assert obj.access_token is None

    assert obj._register() is True
    assert obj.access_token is not None

    # Logging in is silently treated as a success because we
    # already had success registering
    assert obj._login() is True
    assert obj.access_token is not None

    # However if we log out
    assert obj._logout() is True
    assert obj.access_token is None

    # And set ourselves up for failure
    request.status_code = 403
    assert obj._login() is False
    assert obj.access_token is None

    # Reset our token
    obj.access_token = None

    # Adjust our response to be invalid - missing access_token in response
    request.status_code = requests.codes.ok
    ro = response_obj.copy()
    del ro["access_token"]
    request.content = dumps(ro)
    # Our registration will fail now
    assert obj._register() is False
    assert obj.access_token is None
    del obj

    # So will login
    obj = NotifyMatrix(host="host", user="user", password="password")
    assert isinstance(obj, NotifyMatrix) is True
    assert obj._login() is False
    assert obj.access_token is None

    # Adjust our response to be invalid - invalid json response
    request.content = "{"
    # Our registration will fail now
    assert obj._register() is False
    assert obj.access_token is None

    request.status_code = requests.codes.ok
    request.content = dumps(response_obj)
    assert obj._register() is True
    assert obj.access_token is not None
    # Test logoff when getting a 403 error
    request.status_code = 403
    assert obj._logout() is False
    assert obj.access_token is not None

    request.status_code = requests.codes.ok
    request.content = dumps(response_obj)
    assert obj._register() is True
    assert obj.access_token is not None
    request.status_code = 403
    request.content = dumps(
        {
            "errcode": "M_UNKNOWN_TOKEN",
            "error": "Access Token unknown or expired",
        }
    )
    # Test logoff when getting a 403 error; but if we have the right error
    # code in the response, then we return a True
    assert obj._logout() is True
    assert obj.access_token is None
    del obj

    # Modern Matrix servers omit home_server from login/register responses.
    # Apprise must derive it from user_id so room-alias resolution works.
    modern_resp = {
        "access_token": "tok99",
        "user_id": "@bot:matrix.org",
        "device_id": "DEVXYZ",
        # no "home_server" key -- matches real matrix.org behaviour
    }
    request.status_code = requests.codes.ok
    request.content = dumps(modern_resp)

    # No home_server in response + no prior home_server -> derive from user_id
    obj2 = NotifyMatrix(host="matrix.org", user="bot", password="pass")
    assert obj2._login() is True
    assert obj2.home_server == "matrix.org"

    obj3 = NotifyMatrix(host="matrix.org", user="bot", password="pass")
    assert obj3._register() is True
    assert obj3.home_server == "matrix.org"

    # No home_server in response + home_server already set -> not overwritten
    obj4 = NotifyMatrix(host="matrix.org", user="bot", password="pass")
    obj4.home_server = "already.set"
    assert obj4._login() is True
    assert obj4.home_server == "already.set"

    obj5 = NotifyMatrix(host="matrix.org", user="bot", password="pass")
    obj5.home_server = "already.set"
    assert obj5._register() is True
    assert obj5.home_server == "already.set"

    # No home_server in response + user_id has no colon ->
    # home_server stays None
    no_colon_resp = {
        "access_token": "tok88",
        "user_id": "@nocoilon",
        "device_id": "DEV88",
    }
    request.content = dumps(no_colon_resp)
    obj6 = NotifyMatrix(host="matrix.org", user="bot", password="pass")
    assert obj6._login() is True
    assert obj6.home_server is None

    obj7 = NotifyMatrix(host="matrix.org", user="bot", password="pass")
    assert obj7._register() is True
    assert obj7.home_server is None
    del obj2, obj3, obj4, obj5, obj6, obj7


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_matrix_rooms(mock_post, mock_get, mock_put):
    """NotifyMatrix() Room Testing."""

    response_obj = {
        # Registration
        "access_token": "abcd1234",
        "user_id": "@apprise:localhost",
        "home_server": "localhost",
        # For joined_room response
        "joined_rooms": ["!abc123", "!def456:localhost"],
        # For room joining
        "room_id": "!abc123",
    }

    # Default configuration
    request = mock.Mock()
    request.status_code = requests.codes.ok
    request.content = dumps(response_obj)
    mock_post.return_value = request
    mock_get.return_value = request
    mock_put.return_value = request

    obj = NotifyMatrix(host="host")
    assert isinstance(obj, NotifyMatrix) is True
    assert obj.access_token is None

    # Can't get room listing if we're not connnected
    assert obj._room_join("#abc123") is None

    assert obj._register() is True
    assert obj.access_token is not None

    assert obj._room_join("!abc123") == response_obj["room_id"]
    # Use cache to get same results
    assert obj.store.get("!abc123") is None
    # However this is how the cache entry gets stored
    assert obj.store.get("!abc123:localhost") is not None
    assert obj.store.get("!abc123:localhost")["id"] == response_obj["room_id"]

    # When hsreq=yes, legacy behaviour is restored and a homeserver is
    # automatically appended to room IDs that omit it.
    obj.store.clear()
    obj.hsreq = True
    mock_post.reset_mock()
    assert obj._room_join("!abc123") == response_obj["room_id"]
    assert mock_post.call_count == 1
    assert (
        mock_post.call_args_list[0][0][0]
        == "http://host/_matrix/client/v3/join/%21abc123%3Alocalhost"
    )

    # When hsreq=no, we honour the raw !room identifier exactly as provided
    # and do not suffix it with :homeserver.
    obj.store.clear()
    obj.hsreq = False

    def _join_side_effect(url, *args, **kwargs):
        r = mock.Mock()

        # With hsreq disabled, only the raw form should be attempted:
        if url.endswith("/_matrix/client/v3/join/%21abc123"):
            r.status_code = requests.codes.ok
            r.content = dumps(response_obj).encode("utf-8")
            return r

        # Default ok for any other unexpected call
        r.status_code = requests.codes.ok
        r.content = dumps(response_obj).encode("utf-8")
        return r

    mock_post.reset_mock()
    mock_post.side_effect = _join_side_effect
    assert obj._room_join("!abc123") == response_obj["room_id"]
    assert mock_post.call_count == 1
    assert (
        mock_post.call_args_list[0][0][0]
        == "http://host/_matrix/client/v3/join/%21abc123"
    )

    mock_post.reset_mock()
    assert obj._room_join("!abc123") == response_obj["room_id"]
    # Cache is used
    assert mock_post.call_count == 0

    # Still using cache
    assert obj._room_join("!abc123:localhost") == response_obj["room_id"]
    assert mock_post.call_count == 0

    # Toggle our settings back
    obj.hsreq = True
    mock_post.reset_mock()
    mock_post.side_effect = _join_side_effect
    assert obj._room_join("!abc123") == response_obj["room_id"]
    # We still no longer need to fetch as we know the info already
    assert mock_post.call_count == 0

    # Restore defaults for remaining tests
    mock_post.side_effect = None
    obj.hsreq = True

    # Use cache to get same results (no additional HTTP call)
    mock_post.reset_mock()
    assert obj._room_join("!abc123") == response_obj["room_id"]
    assert mock_post.call_count == 0

    obj.store.clear()
    assert obj._room_join("!abc123:localhost") == response_obj["room_id"]
    assert obj.store.get("!abc123:localhost") is not None
    assert obj.store.get("!abc123:localhost")["id"] == response_obj["room_id"]
    # Use cache to get same results
    assert obj._room_join("!abc123:localhost") == response_obj["room_id"]

    obj.store.clear()
    assert obj._room_join("abc123") == response_obj["room_id"]
    # Use cache to get same results
    assert obj.store.get("#abc123:localhost") is not None
    assert obj.store.get("#abc123:localhost")["id"] == response_obj["room_id"]
    assert obj._room_join("abc123") == response_obj["room_id"]

    # If home_server is missing, recover it from user_id so we never try
    # to join a '#room:None' alias.
    obj.store.clear()
    obj.home_server = None
    obj.user_id = "@apprise:localhost"
    mock_post.reset_mock()
    assert obj._room_join("abc123") == response_obj["room_id"]
    assert mock_post.call_count == 1
    assert (
        mock_post.call_args_list[0][0][0]
        == "http://host/_matrix/client/v3/join/%23abc123%3Alocalhost"
    )

    obj.store.clear()
    assert obj._room_join("abc123:localhost") == response_obj["room_id"]
    # Use cache to get same results
    assert obj.store.get("#abc123:localhost") is not None
    assert obj.store.get("#abc123:localhost")["id"] == response_obj["room_id"]
    assert obj._room_join("abc123:localhost") == response_obj["room_id"]

    obj.store.clear()
    assert obj._room_join("#abc123:localhost") == response_obj["room_id"]
    # Use cache to get same results
    assert obj.store.get("#abc123:localhost") is not None
    assert obj.store.get("#abc123:localhost")["id"] == response_obj["room_id"]
    assert obj._room_join("#abc123:localhost") == response_obj["room_id"]

    obj.store.clear()
    assert obj._room_join("%") is None
    assert obj._room_join(None) is None

    obj.store.clear()
    obj.home_server = None
    obj.user_id = "@apprise"
    mock_post.reset_mock()
    assert obj._room_join("abc123") is None
    assert mock_post.call_count == 0

    # 403 response; this will push for a room creation for alias based rooms
    # and these will fail
    request.status_code = 403
    obj.store.clear()
    assert obj._room_join("!abc123") is None
    obj.store.clear()
    assert obj._room_join("!abc123:localhost") is None
    obj.store.clear()
    assert obj._room_join("abc123") is None
    obj.store.clear()
    assert obj._room_join("abc123:localhost") is None
    obj.store.clear()
    assert obj._room_join("#abc123:localhost") is None
    del obj

    # Room creation
    request.status_code = requests.codes.ok
    obj = NotifyMatrix(host="host")
    assert isinstance(obj, NotifyMatrix) is True
    assert obj.access_token is None

    # Can't get room listing if we're not connnected
    assert obj._room_create("#abc123") is None

    assert obj._register() is True
    assert obj.access_token is not None

    # You can't add room_id's, they must be aliases
    assert obj._room_create("!abc123") is None
    assert obj._room_create("!abc123:localhost") is None
    obj.store.clear()
    assert obj._room_create("abc123") == response_obj["room_id"]
    obj.store.clear()
    assert obj._room_create("abc123:localhost") == response_obj["room_id"]
    obj.store.clear()
    assert obj._room_create("#abc123:localhost") == response_obj["room_id"]
    obj.store.clear()
    assert obj._room_create("%") is None
    assert obj._room_create(None) is None

    # 403 response; this will push for a room creation for alias based rooms
    # and these will fail
    request.status_code = 403
    obj.store.clear()
    assert obj._room_create("abc123") is None
    obj.store.clear()
    assert obj._room_create("abc123:localhost") is None
    obj.store.clear()
    assert obj._room_create("#abc123:localhost") is None

    request.status_code = 403
    request.content = dumps(
        {
            "errcode": "M_ROOM_IN_USE",
            "error": "Room alias already taken",
        }
    )
    obj.store.clear()
    # This causes us to look up a channel ID if we get a ROOM_IN_USE response
    assert obj._room_create("#abc123:localhost") is None
    del obj

    # Room detection
    request.status_code = requests.codes.ok
    request.content = dumps(response_obj)
    obj = NotifyMatrix(host="localhost")
    assert isinstance(obj, NotifyMatrix) is True
    assert obj.access_token is None

    # No rooms if we're not connected
    response = obj._joined_rooms()
    assert isinstance(response, list) is True
    assert len(response) == 0

    # register our account
    assert obj._register() is True
    assert obj.access_token is not None

    response = obj._joined_rooms()
    assert isinstance(response, list) is True
    assert len(response) == len(response_obj["joined_rooms"])
    for r in response:
        assert r in response_obj["joined_rooms"]

    request.status_code = 403
    response = obj._joined_rooms()
    assert isinstance(response, list) is True
    assert len(response) == 0
    del obj

    # Room id lookup
    request.status_code = requests.codes.ok
    obj = NotifyMatrix(host="localhost")
    assert isinstance(obj, NotifyMatrix) is True
    assert obj.access_token is None

    # Can't get room listing if we're not connnected
    assert obj._room_id("#abc123") is None

    assert obj._register() is True
    assert obj.access_token is not None

    # You can't add room_id's, they must be aliases
    assert obj._room_id("!abc123") is None
    assert obj._room_id("!abc123:localhost") is None
    obj.store.clear()
    assert obj._room_id("abc123") == response_obj["room_id"]
    obj.store.clear()
    assert obj._room_id("abc123:localhost") == response_obj["room_id"]
    obj.store.clear()
    assert obj._room_id("#abc123:localhost") == response_obj["room_id"]
    obj.store.clear()
    assert obj._room_id("%") is None
    assert obj._room_id(None) is None

    # If we can't look the code up, we return None
    request.status_code = 403
    obj.store.clear()
    assert obj._room_id("#abc123:localhost") is None

    # Force a object removal (thus a logout call)
    del obj


def test_plugin_matrix_url_parsing():
    """NotifyMatrix() URL Testing."""
    result = NotifyMatrix.parse_url("matrix://user:token@localhost?to=#room")
    assert isinstance(result, dict) is True
    assert len(result["targets"]) == 1
    assert "#room" in result["targets"]

    result = NotifyMatrix.parse_url(
        "matrix://user:token@localhost?to=#room&hsreq=yes"
    )
    assert isinstance(result, dict) is True
    assert result.get("hsreq") is True

    result = NotifyMatrix.parse_url(
        "matrix://user:token@localhost?to=#room1,#room2,#room3"
    )
    assert isinstance(result, dict) is True
    assert len(result["targets"]) == 3
    assert "#room1" in result["targets"]
    assert "#room2" in result["targets"]
    assert "#room3" in result["targets"]

    # Mixed-case alias with underscore should parse
    result = NotifyMatrix.parse_url(
        "matrix://user:token@localhost?to=#Dev_Room:localhost"
    )
    assert isinstance(result, dict) is True
    assert len(result["targets"]) == 1
    assert "#Dev_Room:localhost" in result["targets"]

    # Mixed-case room id with underscore should be accepted by _room_join
    from apprise.plugins.matrix import IS_ROOM_ID  # local alias

    nm = NotifyMatrix(host="localhost")
    nm.access_token = "abc"  # simulate logged-in
    nm.home_server = "localhost"
    # this should NOT be rejected by the regex
    assert IS_ROOM_ID.match("!Jm_LvU1nas_8KJPBmN9n:nginx.eu")


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_matrix_image_errors(mock_post, mock_get, mock_put):
    """NotifyMatrix() Image Error Handling."""

    def mock_function_handing(url, data, **kwargs):
        """Dummy function for handling image posts (as a failure)"""
        response_obj = {
            "room_id": "!abc123:localhost",
            "room_alias": "#abc123:localhost",
            "joined_rooms": ["!abc123:localhost", "!def456:localhost"],
            "access_token": "abcd1234",
            "home_server": "localhost",
        }

        request = mock.Mock()
        request.content = dumps(response_obj)
        request.status_code = requests.codes.ok

        if "m.image" in data:
            # Fail for images
            request.status_code = 400

        return request

    # Prepare Mock
    mock_get.side_effect = mock_function_handing
    mock_post.side_effect = mock_function_handing
    mock_put.side_effect = mock_function_handing

    obj = NotifyMatrix(host="host", include_image=True, version="2")
    assert isinstance(obj, NotifyMatrix) is True
    assert obj.access_token is None

    # Notification was successful, however we could not post image and since
    # we had post errors (of any kind) we still report a failure.
    assert obj.notify("test", "test") is False
    del obj

    obj = NotifyMatrix(host="host", include_image=False, version="2")
    assert isinstance(obj, NotifyMatrix) is True
    assert obj.access_token is None

    # We didn't post an image (which was set to fail) and therefore our
    # post was okay
    assert obj.notify("test", "test") is True

    # Force a object removal (thus a logout call)
    del obj

    def mock_function_handing(url, data, **kwargs):
        """Dummy function for handling image posts (successfully)"""
        response_obj = {
            "room_id": "!abc123:localhost",
            "room_alias": "#abc123:localhost",
            "joined_rooms": ["!abc123:localhost", "!def456:localhost"],
            "access_token": "abcd1234",
            "home_server": "localhost",
        }

        request = mock.Mock()
        request.content = dumps(response_obj)
        request.status_code = requests.codes.ok

        return request

    # Prepare Mock
    mock_get.side_effect = mock_function_handing
    mock_put.side_effect = mock_function_handing
    mock_post.side_effect = mock_function_handing
    obj = NotifyMatrix(host="host", include_image=True)
    assert isinstance(obj, NotifyMatrix) is True
    assert obj.access_token is None

    assert obj.notify("test", "test") is True
    del obj

    obj = NotifyMatrix(host="host", include_image=False)
    assert isinstance(obj, NotifyMatrix) is True
    assert obj.access_token is None

    assert obj.notify("test", "test") is True

    # Force a object removal (thus a logout call)
    del obj


@mock.patch("requests.put")
@mock.patch("requests.post")
def test_plugin_matrix_attachments_api_v3(mock_post, mock_put):
    """NotifyMatrix() Attachment Checks (v3)"""

    # Prepare a good response
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = MATRIX_GOOD_RESPONSE.encode("utf-8")

    # Prepare a bad response
    bad_response = mock.Mock()
    bad_response.status_code = requests.codes.internal_server_error

    # Prepare Mock return object
    mock_post.return_value = response
    mock_put.return_value = response

    # Instantiate our object
    obj = Apprise.instantiate("matrix://user:pass@localhost/#general?v=3")

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

    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.gif"))

    # Test our call count
    assert mock_put.call_count == 2
    assert mock_post.call_count == 3
    assert (
        mock_post.call_args_list[0][0][0]
        == "http://localhost/_matrix/client/v3/login"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == "http://localhost/_matrix/client/v3/join/%23general%3Alocalhost"
    )
    assert (
        mock_post.call_args_list[2][0][0]
        == "http://localhost/_matrix/media/v3/upload"
    )
    assert (
        mock_put.call_args_list[0][0][0]
        == "http://localhost/_matrix/client/v3/rooms/%21abc123%3Alocalhost/"
        "send/m.room.message/0"
    )
    assert (
        mock_put.call_args_list[1][0][0]
        == "http://localhost/_matrix/client/v3/rooms/%21abc123%3Alocalhost/"
        "send/m.room.message/1"
    )

    # Attach a zip file type
    attach = AppriseAttachment(
        os.path.join(TEST_VAR_DIR, "apprise-archive.zip")
    )
    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is True
    )

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

    mock_put.return_value = None
    mock_post.return_value = None

    # Throw an exception on the first call to requests.post()
    for side_effect in (requests.RequestException(), OSError(), bad_response):
        # Reset our value
        mock_put.reset_mock()
        mock_post.reset_mock()

        mock_post.side_effect = [side_effect]

        assert obj.send(body="test", attach=attach) is False

    # Throw an exception on the second call to requests.post()
    for side_effect in (requests.RequestException(), OSError(), bad_response):
        # Reset our value
        mock_put.reset_mock()
        mock_post.reset_mock()

        mock_put.side_effect = [side_effect, response]
        mock_post.side_effect = [response, side_effect, response]

        # We'll fail now because of our error handling
        assert obj.send(body="test", attach=attach) is False

    # handle a bad response
    mock_put.side_effect = [bad_response, response]
    mock_post.side_effect = [response, bad_response, response]

    # We'll fail now because of an internal exception
    assert obj.send(body="test", attach=attach) is False

    # Force a object removal (thus a logout call)
    del obj


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_matrix_discovery_service(mock_post, mock_get, mock_put):
    """NotifyMatrix() Discovery Service."""

    # Prepare a good response
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = MATRIX_GOOD_RESPONSE.encode("utf-8")

    # Prepare a good response
    bad_response = mock.Mock()
    bad_response.status_code = requests.codes.unauthorized
    bad_response.content = MATRIX_GOOD_RESPONSE.encode("utf-8")

    # Prepare Mock return object
    mock_post.return_value = response
    mock_get.return_value = response
    mock_put.return_value = response

    # Instantiate our object
    obj = Apprise.instantiate(
        "matrixs://user:pass@example.com/#general?v=2&discovery=yes"
    )
    assert obj.notify("body") is True

    response = mock.Mock()
    response.status_code = requests.codes.unavailable
    resp = loads(MATRIX_GOOD_RESPONSE)

    mock_get.return_value = response
    mock_post.return_value = response
    obj = Apprise.instantiate(
        "matrixs://user:pass@example.com/#general?v=2&discovery=yes"
    )
    obj.store.clear(
        NotifyMatrix.discovery_base_key, NotifyMatrix.discovery_identity_key
    )

    # Invalid host / fallback is to resolve our own host
    with pytest.raises(MatrixDiscoveryException):
        _ = obj.base_url

    # Verify cache is not saved
    assert NotifyMatrix.discovery_base_key not in obj.store
    assert NotifyMatrix.discovery_identity_key not in obj.store

    response.status_code = requests.codes.ok
    obj.store.clear(
        NotifyMatrix.discovery_base_key, NotifyMatrix.discovery_identity_key
    )

    # bad data
    resp["m.homeserver"] = "!garbage!:303"
    response.content = dumps(resp).encode("utf-8")
    obj.store.clear(
        NotifyMatrix.discovery_base_key, NotifyMatrix.discovery_identity_key
    )

    with pytest.raises(MatrixDiscoveryException):
        _ = obj.base_url

    # Verify cache is not saved
    assert NotifyMatrix.discovery_base_key not in obj.store
    assert NotifyMatrix.discovery_identity_key not in obj.store

    # We fail our discovery and therefore can't send our notification
    assert obj.notify("hello world") is False

    # bad key
    resp["m.homeserver"] = {}
    response.content = dumps(resp).encode("utf-8")
    obj.store.clear(
        NotifyMatrix.discovery_base_key, NotifyMatrix.discovery_identity_key
    )
    with pytest.raises(MatrixDiscoveryException):
        _ = obj.base_url

    # Verify cache is not saved
    assert NotifyMatrix.discovery_base_key not in obj.store
    assert NotifyMatrix.discovery_identity_key not in obj.store

    resp["m.homeserver"] = {"base_url": "https://nuxref.com/base"}
    response.content = dumps(resp).encode("utf-8")
    obj.store.clear(
        NotifyMatrix.discovery_base_key, NotifyMatrix.discovery_identity_key
    )
    assert obj.base_url == "https://nuxref.com/base"
    assert obj.identity_url == "https://vector.im"

    # Verify cache saved
    assert NotifyMatrix.discovery_base_key in obj.store
    assert NotifyMatrix.discovery_identity_key in obj.store

    # Discovery passes so notifications work too
    assert obj.notify("hello world") is True

    # bad data
    resp["m.identity_server"] = "!garbage!:303"
    response.content = dumps(resp).encode("utf-8")
    obj.store.clear(
        NotifyMatrix.discovery_base_key, NotifyMatrix.discovery_identity_key
    )

    with pytest.raises(MatrixDiscoveryException):
        _ = obj.base_url

    # Verify cache is not saved
    assert NotifyMatrix.discovery_base_key not in obj.store
    assert NotifyMatrix.discovery_identity_key not in obj.store

    # no key
    resp["m.identity_server"] = {}
    response.content = dumps(resp).encode("utf-8")
    obj.store.clear(
        NotifyMatrix.discovery_base_key, NotifyMatrix.discovery_identity_key
    )

    with pytest.raises(MatrixDiscoveryException):
        _ = obj.base_url

    # Verify cache is not saved
    assert NotifyMatrix.discovery_base_key not in obj.store
    assert NotifyMatrix.discovery_identity_key not in obj.store

    # remove
    del resp["m.identity_server"]
    response.content = dumps(resp).encode("utf-8")

    obj.store.clear(
        NotifyMatrix.discovery_base_key, NotifyMatrix.discovery_identity_key
    )
    assert obj.base_url == "https://nuxref.com/base"
    assert obj.identity_url == "https://nuxref.com/base"

    # restore
    resp["m.identity_server"] = {"base_url": '"https://vector.im'}
    response.content = dumps(resp).encode("utf-8")

    # Not found is an acceptable response (no exceptions thrown)
    response.status_code = requests.codes.not_found
    obj.store.clear(
        NotifyMatrix.discovery_base_key, NotifyMatrix.discovery_identity_key
    )
    assert obj.base_url == "https://example.com"
    assert obj.identity_url == "https://example.com"

    # Verify cache saved
    assert NotifyMatrix.discovery_base_key in obj.store
    assert NotifyMatrix.discovery_identity_key in obj.store

    # Discovery passes so notifications work too
    response.status_code = requests.codes.ok
    assert obj.notify("hello world") is True

    response.status_code = requests.codes.ok
    mock_get.return_value = None
    mock_get.side_effect = (response, bad_response)
    obj.store.clear(
        NotifyMatrix.discovery_base_key, NotifyMatrix.discovery_identity_key
    )

    with pytest.raises(MatrixDiscoveryException):
        _ = obj.base_url

    # Verify cache is not saved
    assert NotifyMatrix.discovery_base_key not in obj.store
    assert NotifyMatrix.discovery_identity_key not in obj.store

    # Test case where ourIdentity URI fails to do it's check
    mock_get.side_effect = (response, response, bad_response)
    obj.store.clear(
        NotifyMatrix.discovery_base_key, NotifyMatrix.discovery_identity_key
    )

    with pytest.raises(MatrixDiscoveryException):
        _ = obj.base_url

    # Verify cache is not saved
    assert NotifyMatrix.discovery_base_key not in obj.store
    assert NotifyMatrix.discovery_identity_key not in obj.store

    # Test an empty block response
    response.status_code = requests.codes.ok
    response.content = ""
    mock_get.return_value = response
    mock_get.side_effect = None
    mock_post.return_value = response
    mock_post.side_effect = None
    obj.store.clear(
        NotifyMatrix.discovery_base_key, NotifyMatrix.discovery_identity_key
    )

    assert obj.base_url == "https://example.com"
    assert obj.identity_url == "https://example.com"

    # Verify cache saved
    assert NotifyMatrix.discovery_base_key in obj.store
    assert NotifyMatrix.discovery_identity_key in obj.store

    del obj


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_matrix_attachments_api_v2(mock_post, mock_get, mock_put):
    """NotifyMatrix() Attachment Checks (v2)"""

    # Prepare a good response
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = MATRIX_GOOD_RESPONSE.encode("utf-8")

    # Prepare a bad response
    bad_response = mock.Mock()
    bad_response.status_code = requests.codes.internal_server_error

    # Prepare Mock return object
    mock_post.return_value = response
    mock_get.return_value = response
    mock_put.return_value = response

    # Instantiate our object
    obj = Apprise.instantiate("matrix://user:pass@localhost/#general?v=2")

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

    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.gif"))

    # Attach an unsupported file
    mock_post.return_value = response
    mock_get.return_value = response
    mock_post.side_effect = None
    mock_get.side_effect = None

    # Force a object removal (thus a logout call)
    del obj

    # Instantiate our object
    obj = Apprise.instantiate("matrixs://user:pass@localhost/#general?v=2")

    # Reset our object
    mock_post.reset_mock()
    mock_get.reset_mock()
    mock_put.reset_mock()

    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is True
    )

    # Test our call count -- login, join, upload use POST; sends use PUT
    assert mock_post.call_count == 3
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://matrix.example.com/_matrix/client/r0/login"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == "https://matrix.example.com/_matrix/client/r0/"
        "join/%23general%3Alocalhost"
    )
    assert (
        mock_post.call_args_list[2][0][0]
        == "https://matrix.example.com/_matrix/media/r0/upload"
    )
    assert mock_put.call_count == 2
    assert (
        mock_put.call_args_list[0][0][0]
        == "https://matrix.example.com/_matrix/client/r0"
        "/rooms/%21abc123%3Alocalhost/send/m.room.message/0"
    )
    assert (
        mock_put.call_args_list[1][0][0]
        == "https://matrix.example.com/_matrix/client/r0/"
        "rooms/%21abc123%3Alocalhost/send/m.room.message/1"
    )

    # Attach an unsupported file type; these are skipped
    attach = AppriseAttachment(
        os.path.join(TEST_VAR_DIR, "apprise-archive.zip")
    )
    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is True
    )

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
    mock_get.return_value = None

    # Throw an exception on the first call to requests.post()
    for side_effect in (requests.RequestException(), OSError(), bad_response):
        # Reset our value
        mock_post.reset_mock()
        mock_get.reset_mock()

        mock_post.side_effect = [side_effect, response]
        mock_get.side_effect = [side_effect, response]

        assert obj.send(body="test", attach=attach) is False

    # Throw an exception on the attachment send (now uses PUT)
    for side_effect in (requests.RequestException(), OSError(), bad_response):
        # Reset our value
        mock_post.reset_mock()
        mock_get.reset_mock()
        mock_put.reset_mock()

        mock_post.side_effect = [response]  # upload ok
        mock_put.side_effect = [side_effect, side_effect]  # sends fail

        # We'll fail now because of our error handling
        assert obj.send(body="test", attach=attach) is False

    # handle a bad response on the attachment send (now PUT)
    mock_post.side_effect = [response]  # upload ok
    mock_put.side_effect = [bad_response, response]  # attachment fails
    mock_get.side_effect = None

    # We'll fail now because of an internal exception
    assert obj.send(body="test", attach=attach) is False

    # Force a object removal (thus a logout call)
    del obj

    # Instantiate our object (no discovery required)
    obj = Apprise.instantiate(
        "matrixs://user:pass@localhost/#general?v=2&discovery=no&image=y"
    )

    # Reset our object
    mock_post.reset_mock()
    mock_get.reset_mock()
    mock_put.reset_mock()

    # login + join succeed; image inline send (now PUT) fails
    mock_post.side_effect = [response, response]
    mock_get.side_effect = None
    mock_put.side_effect = [bad_response]

    # image attachment didn't succeed
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is False
    )

    # All calls now succeed
    mock_post.return_value = response
    mock_get.return_value = response
    mock_put.return_value = response
    mock_post.side_effect = None
    mock_get.side_effect = None
    mock_put.side_effect = None

    # We'll fail now because of an internal exception
    assert obj.send(body="test", attach=attach) is True

    # Force __del__() call
    del obj


@mock.patch("requests.put")
@mock.patch("requests.post")
def test_plugin_matrix_v2_compliance(mock_post, mock_put):
    """NotifyMatrix() Verify V2 uses PUT and TID for standard messages."""
    # Setup compliant response
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = MATRIX_GOOD_RESPONSE.encode("utf-8")
    mock_post.return_value = response
    mock_put.return_value = response

    # Instantiate as V2
    obj = Apprise.instantiate("matrix://user:pass@localhost/#general?v=2")

    # Send a standard notification
    assert obj.notify(body="test message") is True

    # Confirm the fix:
    # 1. Path contains the transaction ID '0'
    # 2. Method is PUT
    assert mock_put.call_count == 1
    assert "/_matrix/client/r0/rooms/" in mock_put.call_args_list[0][0][0]
    assert "/send/m.room.message/0" in mock_put.call_args_list[0][0][0]


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_matrix_v2_token_mode_no_txn_increment(
    mock_post, mock_get, mock_put
):
    """Token mode (access_token == password) skips transaction ID increment."""
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = MATRIX_GOOD_RESPONSE.encode("utf-8")
    mock_post.return_value = response
    mock_get.return_value = response
    mock_put.return_value = response

    # Token mode: user omitted, password treated as access token
    # (parse_url swaps user->password when no password supplied)
    obj = Apprise.instantiate(
        "matrixs://my_access_token@localhost/#general?v=2&image=y"
    )
    assert obj is not None

    # Send with image inline enabled
    assert obj.notify(body="token mode image test") is True

    # Send with an attachment
    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.gif"))
    assert obj.send(body="token mode attach test", attach=attach) is True


def test_plugin_matrix_parse_native_url_no_match():
    """parse_native_url returns None for non-t2bot URLs."""
    assert (
        NotifyMatrix.parse_native_url("https://not-a-t2bot-url.com/some/path")
        is None
    )


@mock.patch("requests.post")
def test_plugin_matrix_hookshot_webhook(mock_post):
    """matrix-hookshot webhook mode uses hookshot URL/payload conventions."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b"{}"
    mock_post.return_value = response

    obj = Apprise.instantiate(
        "matrixs://apprise:supersecret@hookshot.example"
        "?mode=hookshot&format=html&path=%2Fpublic-hooks"
    )
    assert obj is not None

    assert obj.notify(title="Title", body="<b>Body</b>") is True

    assert mock_post.call_args.args[0] == (
        "https://hookshot.example/public-hooks/supersecret"
    )

    payload = loads(mock_post.call_args.kwargs["data"])
    assert payload["username"] == "apprise"
    assert payload["text"] == "Title\r\n<b>Body</b>"
    assert payload["html"] == "<h1>Title</h1><b>Body</b>"


@mock.patch("requests.post")
def test_plugin_matrix_hookshot_webhook_empty_title(mock_post):
    """Hookshot webhook mode avoids extra separators for empty titles."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b"{}"
    mock_post.return_value = response

    obj = Apprise.instantiate(
        "matrixs://apprise:supersecret@hookshot.example"
        "?mode=hookshot&format=markdown&path=%2Fpublic-hooks"
    )
    assert obj is not None

    assert obj.notify(body="**Body**") is True

    payload = loads(mock_post.call_args.kwargs["data"])
    assert payload["username"] == "apprise"
    assert payload["text"] == "**Body**"
    assert payload["html"] == "<p><strong>Body</strong></p>"


def test_plugin_matrix_hookshot_path_normalization():
    """Hookshot webhook paths normalize missing leading slashes."""

    obj = Apprise.instantiate(
        "matrixs://apprise:supersecret@hookshot.example"
        "?mode=hookshot&path=public-hooks"
    )
    assert obj is not None
    assert obj.webhook_path == "/public-hooks"


@mock.patch("requests.post")
def test_plugin_matrix_hookshot_root_path_text(mock_post):
    """Hookshot root paths and text mode stay literal."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b"{}"
    mock_post.return_value = response

    obj = Apprise.instantiate(
        "matrixs://apprise:supersecret@hookshot.example"
        "?mode=hookshot&format=text&path=%2F"
    )
    assert obj is not None
    assert obj.notify(body="<b>Body</b>") is True

    assert mock_post.call_args.args[0] == (
        "https://hookshot.example/supersecret"
    )
    assert loads(mock_post.call_args.kwargs["data"])["html"] == (
        "&lt;b&gt;Body&lt;/b&gt;"
    )


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_matrix_transaction_ids_api_v3_no_cache(
    mock_post, mock_get, mock_put
):
    """NotifyMatrix() Transaction ID Checks (v3)"""

    # Prepare a good response
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = MATRIX_GOOD_RESPONSE.encode("utf-8")

    # Prepare a bad response
    bad_response = mock.Mock()
    bad_response.status_code = requests.codes.internal_server_error

    # Prepare Mock return object
    mock_post.return_value = response
    mock_get.return_value = response
    mock_put.return_value = response

    # For each element is 1 batch that is ran
    # the number defined is the number of notifications to send
    batch = [10, 1, 5]

    for notifications in batch:
        # Instantiate our object
        obj = Apprise.instantiate("matrix://user:pass@localhost/#general?v=3")

        # Ensure mode is memory
        assert obj.store.mode == PersistentStoreMode.MEMORY

        # Performs a login
        assert (
            obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
            is True
        )
        assert mock_get.call_count == 0
        assert mock_post.call_count == 2
        assert (
            mock_post.call_args_list[0][0][0]
            == "http://localhost/_matrix/client/v3/login"
        )
        assert (
            mock_post.call_args_list[1][0][0]
            == "http://localhost/_matrix/client/v3/join/%23general%3Alocalhost"
        )
        assert mock_put.call_count == 1
        assert (
            mock_put.call_args_list[0][0][0]
            == "http://localhost/_matrix/client/v3/rooms/"
            + "%21abc123%3Alocalhost/send/m.room.message/0"
        )

        for no, _ in enumerate(range(notifications), start=1):
            # Clean our slate
            mock_post.reset_mock()
            mock_get.reset_mock()
            mock_put.reset_mock()

            assert (
                obj.notify(
                    body="body", title="title", notify_type=NotifyType.INFO
                )
                is True
            )

            assert mock_get.call_count == 0
            assert mock_post.call_count == 0
            assert mock_put.call_count == 1
            assert (
                mock_put.call_args_list[0][0][0]
                == "http://localhost/_matrix/client/v3/rooms/"
                + f"%21abc123%3Alocalhost/send/m.room.message/{no}"
            )

        mock_post.reset_mock()
        mock_get.reset_mock()
        mock_put.reset_mock()

        # Force a object removal (thus a logout call)
        del obj

        assert mock_get.call_count == 0
        assert mock_post.call_count == 1
        assert (
            mock_post.call_args_list[0][0][0]
            == "http://localhost/_matrix/client/v3/logout"
        )
        mock_post.reset_mock()
        assert mock_put.call_count == 0


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_matrix_transaction_ids_api_v3_w_cache(
    mock_post, mock_get, mock_put, tmpdir
):
    """NotifyMatrix() Transaction ID Checks (v3)"""

    # Prepare a good response
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = MATRIX_GOOD_RESPONSE.encode("utf-8")

    # Prepare a bad response
    bad_response = mock.Mock()
    bad_response.status_code = requests.codes.internal_server_error

    # Prepare Mock return object
    mock_post.return_value = response
    mock_get.return_value = response
    mock_put.return_value = response

    # For each element is 1 batch that is ran
    # the number defined is the number of notifications to send
    batch = [10, 1, 5]

    mock_post.reset_mock()
    mock_get.reset_mock()
    mock_put.reset_mock()

    asset = AppriseAsset(
        storage_mode=PersistentStoreMode.FLUSH,
        storage_path=str(tmpdir),
    )

    # Message Counter
    transaction_id = 1

    for no, notifications in enumerate(batch):
        # Instantiate our object
        obj = Apprise.instantiate(
            "matrix://user:pass@localhost/#general?v=3", asset=asset
        )

        # Ensure mode is flush
        assert obj.store.mode == PersistentStoreMode.FLUSH

        # Performs a login
        assert (
            obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
            is True
        )
        assert mock_get.call_count == 0
        if no == 0:
            # first entry
            assert mock_post.call_count == 2
            assert (
                mock_post.call_args_list[0][0][0]
                == "http://localhost/_matrix/client/v3/login"
            )
            assert (
                mock_post.call_args_list[1][0][0]
                == "http://localhost/_matrix/client/v3/"
                "join/%23general%3Alocalhost"
            )
            assert mock_put.call_count == 1
            assert (
                mock_put.call_args_list[0][0][0]
                == "http://localhost/_matrix/client/v3/rooms/"
                + "%21abc123%3Alocalhost/send/m.room.message/0"
            )

        for no, _ in enumerate(range(notifications), start=transaction_id):
            # Clean our slate
            mock_post.reset_mock()
            mock_get.reset_mock()
            mock_put.reset_mock()

            assert (
                obj.notify(
                    body="body", title="title", notify_type=NotifyType.INFO
                )
                is True
            )

            # Increment transaction counter
            transaction_id += 1

            assert mock_get.call_count == 0
            assert mock_post.call_count == 0
            assert mock_put.call_count == 1
            assert (
                mock_put.call_args_list[0][0][0]
                == "http://localhost/_matrix/client/v3/rooms/"
                + f"%21abc123%3Alocalhost/send/m.room.message/{no}"
            )

        # Increment transaction counter
        transaction_id += 1

        mock_post.reset_mock()
        mock_get.reset_mock()
        mock_put.reset_mock()

        # Force a object removal
        # Biggest takeaway is that a logout no longer happens
        del obj

        assert mock_get.call_count == 0
        assert mock_post.call_count == 0
        assert mock_put.call_count == 0


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_matrix_v3_url_with_port_assembly(
    mock_post, mock_get, mock_put, tmpdir
):
    """NotifyMatrix() URL with Port Assembly Checks (v3)"""

    # Prepare a good response
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = MATRIX_GOOD_RESPONSE.encode("utf-8")

    # Prepare Mock return object
    mock_post.return_value = response
    mock_get.return_value = response
    mock_put.return_value = response

    asset = AppriseAsset(
        storage_mode=PersistentStoreMode.FLUSH,
        storage_path=str(tmpdir),
    )

    # Instantiate our object
    obj = Apprise.instantiate(
        "matrixs://user1:pass123@example.ca:8080/#general?v=3", asset=asset
    )
    # Performs a login
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    # Secure Connections have a bit of additional overhead to verify
    # the authenticity of the server through discovery
    assert mock_get.call_count == 3
    assert (
        mock_get.call_args_list[0][0][0]
        == "https://example.ca:8080/.well-known/matrix/client"
    )
    assert (
        mock_get.call_args_list[1][0][0]
        == "https://matrix.example.com/_matrix/client/versions"
    )
    assert (
        mock_get.call_args_list[2][0][0]
        == "https://vector.im/_matrix/identity/v2"
    )

    assert mock_post.call_count == 2
    # matrix.example.com comes from our MATRIX_GOOD_RESPONSE
    # response which defines wht our .well-known returned to us
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://matrix.example.com/_matrix/client/v3/login"
    )
    assert (
        mock_post.call_args_list[1][0][0]
        == "https://matrix.example.com/_matrix/client/v3/"
        "join/%23general%3Alocalhost"
    )
    assert mock_put.call_count == 1
    assert (
        mock_put.call_args_list[0][0][0]
        == "https://matrix.example.com/_matrix/client/v3/rooms/"
        + "%21abc123%3Alocalhost/send/m.room.message/0"
    )

    mock_post.reset_mock()
    mock_get.reset_mock()
    mock_put.reset_mock()

    assert obj.base_url == "https://matrix.example.com"

    # Cache is used under the hood; no second discover is performed
    assert mock_put.call_count == 0
    assert mock_get.call_count == 0
    assert mock_post.call_count == 0

    # Cleanup
    del obj


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_matrix_no_room_create_on_non_not_found_join(
    mock_post: mock.Mock,
    mock_get: mock.Mock,
    mock_put: mock.Mock,
) -> None:
    """No room creation when join fails with 400 (or other non-404).

    A join failure can occur for many reasons, such as auth failure or invite
    required. In these cases, attempting to create the room is incorrect and
    produces misleading follow-up errors like M_ROOM_IN_USE.
    """

    def _resp(status_code: int, content: Union[str, bytes]) -> mock.Mock:
        r = mock.Mock()
        r.status_code = status_code
        if isinstance(content, str):
            r.content = content.encode("utf-8")
        else:
            r.content = content
        return r

    login = dumps(
        {
            "access_token": "t",
            "home_server": "hs",
            "user_id": "@u:hs",
        }
    )

    # POST sequence:
    # 1. /login succeeds
    # 2. /join/#backup fails with 400 and an empty body
    # 3. /logout succeeds during object cleanup remembering token
    mock_post.side_effect = [
        _resp(requests.codes.ok, login),
        _resp(requests.codes.bad_request, b""),
        _resp(requests.codes.ok, dumps({})),
    ]

    # No other requests should be needed (no createRoom, no directory lookup)
    mock_get.return_value = _resp(requests.codes.internal_server_error, b"")
    mock_put.return_value = _resp(requests.codes.ok, dumps({}))

    ap = Apprise()
    ap.add("matrixs://user:pass@matrix.vip/#backup?discovery=no")

    assert ap.notify(title="t", body="b") is False

    # Cleanup explicitly to ensure __del__ executes while mocks are active.
    import gc

    del ap
    gc.collect()

    # login + join + logout
    assert mock_post.call_count == 3
    assert mock_get.call_count == 0


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_matrix_room_create_on_not_found_join(
    mock_post: mock.Mock,
    mock_get: mock.Mock,
    mock_put: mock.Mock,
) -> None:
    """Attempt room creation only when join reports 404 / M_NOT_FOUND."""

    def _resp(status_code: int, content: Union[str, bytes]) -> mock.Mock:
        r = mock.Mock()
        r.status_code = status_code
        if isinstance(content, str):
            r.content = content.encode("utf-8")
        else:
            r.content = content
        return r

    login = dumps(
        {
            "access_token": "t",
            "home_server": "hs",
            "user_id": "@u:hs",
        }
    )

    # POST sequence:
    # 1. /login succeeds
    # 2. /join/#backup returns 404 not found
    # 3. /createRoom returns alias in use, triggering alias resolution
    # 4. /logout succeeds during object cleanup
    mock_post.side_effect = [
        _resp(requests.codes.ok, login),
        _resp(
            requests.codes.not_found,
            dumps({"errcode": "M_NOT_FOUND", "error": "Not found"}),
        ),
        _resp(
            requests.codes.bad_request,
            dumps(
                {
                    "errcode": "M_ROOM_IN_USE",
                    "error": "Room alias already taken",
                }
            ),
        ),
        _resp(requests.codes.ok, dumps({})),
    ]

    # Directory lookup returns the room id
    mock_get.return_value = _resp(
        requests.codes.ok,
        dumps({"room_id": "!abc123:matrix.vip"}),
    )

    # Sending the message succeeds (v3 uses PUT)
    mock_put.return_value = _resp(requests.codes.ok, dumps({}))

    ap = Apprise()
    ap.add("matrixs://user:pass@matrix.vip/#backup?discovery=no")

    assert ap.notify(title="t", body="b") is True

    import gc

    del ap
    gc.collect()

    # login + join + createRoom + logout
    assert mock_post.call_count == 4
    assert mock_get.call_count == 1
    assert mock_put.call_count == 1


# ---------------------------------------------------------------------------
# E2EE unit tests (require the cryptography package)
# ---------------------------------------------------------------------------

try:
    import cryptography  # noqa: F401

    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="Requires cryptography")
def test_plugin_matrix_room_create_e2ee_initial_state(
    mock_post, mock_get, mock_put
):
    """_room_create with e2ee=True/secure=True embeds m.room.encryption in
    initial_state and pre-seeds the room encryption cache."""
    response_obj = {
        "access_token": "tok",
        "user_id": "@u:localhost",
        "home_server": "localhost",
        "room_id": "!abc123",
    }
    r = mock.Mock()
    r.status_code = requests.codes.ok
    r.content = dumps(response_obj).encode()
    mock_post.return_value = r
    mock_get.return_value = r
    mock_put.return_value = r

    obj = NotifyMatrix(
        host="localhost",
        user="u",
        password="p",
        e2ee=True,
        secure=True,
        discovery=False,
    )
    obj.access_token = "tok"
    obj.home_server = "localhost"

    captured_payloads = []
    _orig_fetch = obj._fetch

    def _capture_fetch(path, payload=None, **kw):
        if path == "/createRoom":
            captured_payloads.append(payload)
        return _orig_fetch(path, payload=payload, **kw)

    obj._fetch = _capture_fetch
    room_id = obj._room_create("e2ee_room")
    assert room_id == response_obj["room_id"]
    assert len(captured_payloads) == 1
    init_state = captured_payloads[0].get("initial_state", [])
    assert any(s.get("type") == "m.room.encryption" for s in init_state)
    assert obj.store.get("e2ee_room_enc_{}".format(room_id)) is True


def _rand_b64_32():
    """32 bytes of random data encoded as unpadded base64."""
    import base64

    return base64.b64encode(os.urandom(32)).decode()


def _make_signed_otk(account, user_id, device_id, key_b64=None):
    """Return a signed_curve25519 OTK dict signed by *account*.

    Produces {"key": ..., "signatures": {user_id: {"ed25519:DEV": ...}}}
    suitable for inclusion in a /keys/claim mock response.
    """
    from apprise.plugins.matrix.e2ee import _canonical_json

    if key_b64 is None:
        key_b64 = _rand_b64_32()
    payload = {"key": key_b64}
    sig = account.sign(_canonical_json(payload))
    payload["signatures"] = {user_id: {"ed25519:{}".format(device_id): sig}}
    return payload


@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="Requires cryptography")
def test_plugin_matrix_e2ee_helpers():
    """e2ee helper functions."""
    from apprise.plugins.matrix.e2ee import (
        _b64dec,
        _b64enc,
        _canonical_json,
        _hmac_sha256,
        _pb_bytes,
        _pb_varint_field,
        _varint,
    )

    # _b64enc / _b64dec round-trip
    raw = b"\x00\x01\x02\x03"
    assert _b64dec(_b64enc(raw)) == raw

    # _b64dec tolerates missing padding and URL-safe chars
    # "AA==" -> decode "AA" (2 chars, pad=2)
    assert _b64dec("AA") == b"\x00"
    # URL-safe chars are normalised
    assert _b64dec("AA--") == _b64dec("AA++")

    # _hmac_sha256 returns 32 bytes
    mac = _hmac_sha256(b"\x00" * 32, b"data")
    assert isinstance(mac, bytes) and len(mac) == 32

    # _varint: n==0 -> single zero byte
    assert _varint(0) == b"\x00"
    # n>0 is encoded as multi-byte varint
    assert _varint(128) == b"\x80\x01"

    # _pb_bytes / _pb_varint_field produce bytes
    pb = _pb_bytes(1, b"hello")
    assert isinstance(pb, bytes) and len(pb) > 5
    pv = _pb_varint_field(2, 42)
    assert isinstance(pv, bytes)

    # _canonical_json produces sorted-key JSON bytes
    data = {"z": 1, "a": 2}
    out = _canonical_json(data)
    assert out.startswith(b'{"a"')


def test_plugin_matrix_e2ee_no_cryptography():
    """MATRIX_E2EE_SUPPORT is False when cryptography is unavailable."""
    import importlib
    import sys

    # Block 'cryptography' so the ImportError branch is taken on reload
    saved = {
        k: v for k, v in sys.modules.items() if k.startswith("cryptography")
    }
    for key in list(saved):
        sys.modules[key] = None  # type: ignore[assignment]

    try:
        import apprise.plugins.matrix.e2ee as e2ee_mod

        importlib.reload(e2ee_mod)
        assert e2ee_mod.MATRIX_E2EE_SUPPORT is False
    finally:
        # Restore everything so subsequent tests are not broken
        for key in list(saved):
            if saved[key] is None:
                del sys.modules[key]
            else:
                sys.modules[key] = saved[key]
        # Force a clean reload so MATRIX_E2EE_SUPPORT is True again
        importlib.reload(e2ee_mod)


@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="Requires cryptography")
def test_plugin_matrix_e2ee_olm_account():
    """MatrixOlmAccount creation, signing, serialisation."""
    from apprise.plugins.matrix.e2ee import MatrixOlmAccount

    # Fresh account
    acct = MatrixOlmAccount()
    assert isinstance(acct.identity_key, str)
    assert isinstance(acct.signing_key, str)

    # sign() accepts str and bytes
    sig = acct.sign("hello")
    assert isinstance(sig, str)
    sig2 = acct.sign(b"hello")
    assert isinstance(sig2, str)

    # to_dict / from_dict round-trip
    d = acct.to_dict()
    assert "ik" in d and "sk" in d
    restored = MatrixOlmAccount.from_dict(d)
    assert restored.identity_key == acct.identity_key
    assert restored.signing_key == acct.signing_key

    # Explicit key construction from stored keys
    acct2 = MatrixOlmAccount(
        ik_priv_b64=d["ik"],
        sk_priv_b64=d["sk"],
    )
    assert acct2.identity_key == acct.identity_key

    # device_keys_payload produces a signed dict
    payload = acct.device_keys_payload("@u:h", "DEVID")
    assert "signatures" in payload
    assert "algorithms" in payload

    # fallback_keys_payload: first call generates the fallback OTK (487->499
    # branch: _fallback_otk is None so it is created, then the common path
    # at line 499 runs).  Second call reuses the already-generated key
    # (branch where _fallback_otk is already set is also covered).
    fb1 = acct.fallback_keys_payload("@u:h", "DEVID")
    assert len(fb1) == 1
    fb_key_id1 = next(iter(fb1.keys()))
    assert fb_key_id1.startswith("signed_curve25519:")
    fb2 = acct.fallback_keys_payload("@u:h", "DEVID")
    # second call returns the same key id (key not regenerated)
    assert next(iter(fb2.keys())) == fb_key_id1


@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="Requires cryptography")
def test_plugin_matrix_e2ee_olm_session():
    """MatrixOlmSession encrypts and produces correct wire format."""
    from apprise.plugins.matrix.e2ee import MatrixOlmAccount, _b64dec

    acct = MatrixOlmAccount()
    # Create a second account to act as recipient
    recipient = MatrixOlmAccount()

    session = acct.create_outbound_session(
        recipient.identity_key,
        recipient.identity_key,  # reuse IK as a stand-in OTK
    )

    assert session.their_identity_key == recipient.identity_key

    # str plaintext
    result = session.encrypt("test plaintext")
    assert result["type"] == 0
    assert isinstance(result["body"], str)

    # Decode and check the outer pre-key wire format.
    # Outer: version(0x03) | field1(OTK) | field2(EK) | field3(IK) |
    #        field4(inner+mac) | outer_mac(8)
    # Inner (in field 4): version(0x03) | field1(ratchet_key) |
    #        field2(chain_index) | field4(ciphertext,tag=0x22) | inner_mac(8)
    raw = _b64dec(result["body"])
    assert raw[0:1] == b"\x03", "outer version must be 0x03"
    # field 4, wire-type 2 -> tag = (4<<3)|2 = 0x22 -- ciphertext in inner msg
    assert b"\x22" in raw, "ciphertext field tag 0x22 must be present"
    # Outer field 1 (OTK, tag 0x0A), field 2 (EK, tag 0x12) must appear
    assert b"\x0a" in raw, "outer OTK field (tag 0x0A) must be present"
    assert b"\x12" in raw, "outer EK field (tag 0x12) must be present"

    # bytes plaintext also accepted
    result2 = session.encrypt(b"bytes input")
    assert result2["type"] == 0


@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="Requires cryptography")
def test_plugin_matrix_e2ee_olm_roundtrip():
    """Full Olm round-trip: Alice encrypts, Bob manually decrypts.

    This test implements the Bob (inbound) side of the Olm X3DH and
    message-decryption protocol using the same cryptography primitives,
    verifying that our Alice-side implementation produces wire bytes that
    a conformant receiver can decrypt.

    Critical invariant verified: the outer base-key (pre-key field 2)
    equals the inner ratchet-key (normal-message field 1).  They MUST be
    the same ephemeral key E_A or the receiver cannot reconstruct the
    session and decryption fails.
    """
    import hmac as _hmac_stdlib

    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes, hmac as _hmac_mod
    from cryptography.hazmat.primitives.asymmetric.x25519 import (
        X25519PrivateKey,
    )
    from cryptography.hazmat.primitives.ciphers import (
        Cipher,
        algorithms,
        modes,
    )
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives.padding import PKCS7
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        PublicFormat,
    )

    from apprise.plugins.matrix.e2ee import (
        MatrixOlmAccount,
        _b64dec,
        _b64enc,
    )

    # -- helpers (Bob-side) -------------------------------------------

    def _hmac(key, data):
        h = _hmac_mod.HMAC(key, hashes.SHA256(), backend=default_backend())
        h.update(data)
        return h.finalize()

    def _hkdf(ikm, length, salt, info):
        return HKDF(
            algorithm=hashes.SHA256(),
            length=length,
            salt=salt,
            info=info,
            backend=default_backend(),
        ).derive(ikm)

    def _aes_cbc_decrypt(key, iv, ciphertext):
        cipher = Cipher(
            algorithms.AES(key), modes.CBC(iv), backend=default_backend()
        )
        dec = cipher.decryptor()
        padded = dec.update(ciphertext) + dec.finalize()
        unpadder = PKCS7(128).unpadder()
        return unpadder.update(padded) + unpadder.finalize()

    def _read_varint(data, pos):
        val, shift = 0, 0
        while True:
            b = data[pos]
            pos += 1
            val |= (b & 0x7F) << shift
            shift += 7
            if not (b & 0x80):
                return val, pos

    def _parse_pb_fields(data):
        """Parse length-delimited protobuf body; return {field_num: bytes}."""
        fields = {}
        pos = 0
        while pos < len(data):
            tag, pos = _read_varint(data, pos)
            field_num = tag >> 3
            wire_type = tag & 0x07
            if wire_type == 2:
                length, pos = _read_varint(data, pos)
                fields[field_num] = data[pos : pos + length]
                pos += length
            elif wire_type == 0:
                val, pos = _read_varint(data, pos)
                fields[field_num] = val
            else:
                raise ValueError("Unexpected wire type {}".format(wire_type))
        return fields

    # -- test setup ---------------------------------------------------

    # Alice's account (sender)
    alice = MatrixOlmAccount()

    # Bob's account: identity key + a separate one-time key
    bob = MatrixOlmAccount()
    bob_otk_priv = X25519PrivateKey.generate()
    bob_otk_pub = bob_otk_priv.public_key().public_bytes(
        Encoding.Raw, PublicFormat.Raw
    )
    bob_otk_pub_b64 = _b64enc(bob_otk_pub)

    # Bob's identity-key private (for DH computation)
    bob_ik_priv = bob._ik

    # Alice creates an outbound session to Bob using his real OTK
    session = alice.create_outbound_session(
        bob.identity_key,  # Bob's Curve25519 identity key
        bob_otk_pub_b64,  # Bob's one-time key
    )

    plaintext = "hello from Alice"
    result = session.encrypt(plaintext)
    assert result["type"] == 0

    # -- Bob-side decryption ------------------------------------------

    raw = _b64dec(result["body"])

    # Outer pre-key message format (Olm spec Section 5.2):
    #   version(1) | protobuf(field1=OTK, field2=base_key,
    #                          field3=IK, field4=inner_message)
    #
    # There is NO outer MAC on the pre-key message.  Only the inner
    # normal-message (field 4) has its own 8-byte MAC appended.
    # Reference: olm.md Section 5.2; libolm session.cpp
    # encode_one_time_key_message_length() (no MAC bytes allocated);
    # vodozemac src/olm/messages/pre_key.rs decode() (no MAC consumed).
    assert raw[0:1] == b"\x03", "outer version must be 0x03"

    # Parse the full outer protobuf body (all bytes after the version byte)
    outer_fields = _parse_pb_fields(raw[1:])
    otk_pub_in_msg = outer_fields[1]  # field 1: Bob's OTK public bytes
    base_key = outer_fields[2]  # field 2: Alice's ephemeral E_A
    alice_ik_pub = outer_fields[3]  # field 3: Alice's identity key

    # The OTK bytes in the message must equal Bob's OTK public key
    assert otk_pub_in_msg == bob_otk_pub, (
        "OTK in pre-key message must match the OTK that was claimed"
    )

    # Bob computes X3DH (mirroring Alice's DH operations)
    #   DH1 = X25519(OTK_B_priv, IK_A_pub)
    #   DH2 = X25519(IK_B_priv, E_A_pub)
    #   DH3 = X25519(OTK_B_priv, E_A_pub)
    from cryptography.hazmat.primitives.asymmetric.x25519 import (
        X25519PublicKey,
    )

    alice_ik = X25519PublicKey.from_public_bytes(alice_ik_pub)
    e_a = X25519PublicKey.from_public_bytes(base_key)

    dh1 = bob_otk_priv.exchange(alice_ik)
    dh2 = bob_ik_priv.exchange(e_a)
    dh3 = bob_otk_priv.exchange(e_a)

    ikm = dh1 + dh2 + dh3
    keys64 = _hkdf(ikm, 64, salt=None, info=b"OLM_ROOT")
    root_key = keys64[:32]
    chain_key = keys64[32:]
    del root_key  # not needed for first-message decryption

    # Derive message keys from the initial chain key
    msg_key = _hmac(chain_key, b"\x01")
    keys80 = _hkdf(msg_key, 80, salt=b"\x00" * 32, info=b"OLM_KEYS")
    aes_key = keys80[:32]
    mac_key = keys80[32:64]
    iv = keys80[64:80]

    # Field 4 = inner_normal_message || 8-byte MAC.
    # The inner normal message itself starts with version byte 0x03 followed
    # by the protobuf body; the MAC covers the version + protobuf body.
    inner_with_mac = outer_fields[4]
    inner_body = inner_with_mac[:-8]  # version(1) + pb_fields
    inner_mac_received = inner_with_mac[-8:]

    # Verify the inner MAC (HMAC-SHA-256 of inner_body, truncated to 8 bytes)
    inner_mac_expected = _hmac(mac_key, inner_body)[:8]
    assert _hmac_stdlib.compare_digest(
        inner_mac_expected, inner_mac_received
    ), "inner MAC verification failed"

    # Parse inner fields
    # inner_body = version(0x03) | pb_fields
    assert inner_body[0:1] == b"\x03", "inner version must be 0x03"
    inner_fields = _parse_pb_fields(inner_body[1:])

    # CRITICAL invariant:
    # ratchet_key (inner field 1) == base_key (outer field 2)
    ratchet_key = inner_fields[1]
    assert ratchet_key == base_key, (
        "Olm invariant violated: inner ratchet_key must equal outer base_key "
        "(E_A must be used in BOTH positions per Olm spec Section 5.1). "
        "Got ratchet_key={} base_key={}".format(
            _b64enc(ratchet_key), _b64enc(base_key)
        )
    )

    # Decrypt the AES-256-CBC ciphertext (inner field 4)
    ciphertext = inner_fields[4]
    decrypted = _aes_cbc_decrypt(aes_key, iv, ciphertext)

    assert decrypted.decode("utf-8") == plaintext, (
        "round-trip decryption failed: got {!r}".format(decrypted)
    )


@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="Requires cryptography")
def test_plugin_matrix_e2ee_verify_keys():
    """verify_device_keys and verify_signed_otk accept/reject signatures."""
    from apprise.plugins.matrix.e2ee import (
        MatrixOlmAccount,
        _canonical_json,
        verify_device_keys,
        verify_signed_otk,
    )

    acct = MatrixOlmAccount()
    uid = "@alice:h"
    dev = "DEVID"

    # --- verify_device_keys ---

    # Valid self-signed device keys -> True
    dk = acct.device_keys_payload(uid, dev)
    assert verify_device_keys(dk, uid, dev) is True

    # Payload user_id doesn't match -> False (identity binding check)
    mismatched_uid = {**dk, "user_id": "@other:h"}
    assert verify_device_keys(mismatched_uid, uid, dev) is False

    # Payload device_id doesn't match -> False (identity binding check)
    mismatched_dev = {**dk, "device_id": "WRONGDEV"}
    assert verify_device_keys(mismatched_dev, uid, dev) is False

    # Missing user_id in payload -> False
    no_user_id = {k: v for k, v in dk.items() if k != "user_id"}
    assert verify_device_keys(no_user_id, uid, dev) is False

    # Missing signatures field -> False
    no_sig = {k: v for k, v in dk.items() if k != "signatures"}
    assert verify_device_keys(no_sig, uid, dev) is False

    # Wrong user_id in signatures -> False
    wrong_uid = {
        **dk,
        "signatures": {"@wrong:h": dk["signatures"][uid]},
    }
    assert verify_device_keys(wrong_uid, uid, dev) is False

    # Tampered key value -> False
    tampered = {**dk, "keys": {**dk["keys"], f"ed25519:{dev}": "bad"}}
    assert verify_device_keys(tampered, uid, dev) is False

    # Missing ed25519 key entry -> False
    no_keys = {**dk, "keys": {f"curve25519:{dev}": acct.identity_key}}
    assert verify_device_keys(no_keys, uid, dev) is False

    # --- verify_signed_otk ---

    key_b64 = _rand_b64_32()
    otk_obj = {"key": key_b64}
    sig = acct.sign(_canonical_json(otk_obj))
    signed_otk = {
        **otk_obj,
        "signatures": {uid: {f"ed25519:{dev}": sig}},
    }

    # Valid OTK -> True
    assert verify_signed_otk(signed_otk, uid, dev, acct.signing_key) is True

    # Missing signatures -> False
    assert verify_signed_otk(otk_obj, uid, dev, acct.signing_key) is False

    # Wrong signing key -> False
    other = MatrixOlmAccount()
    assert verify_signed_otk(signed_otk, uid, dev, other.signing_key) is False

    # Tampered key value -> False
    tampered_otk = {**signed_otk, "key": _rand_b64_32()}
    assert verify_signed_otk(tampered_otk, uid, dev, acct.signing_key) is False


@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="Requires cryptography")
def test_plugin_matrix_e2ee_megolm_session():
    """MatrixMegOlmSession encrypt, session_key, rotation, serialisation."""
    from apprise.plugins.matrix.e2ee import (
        MATRIX_MEGOLM_STORE_VERSION,
        MEGOLM_ROTATION_MSGS,
        MatrixMegOlmSession,
    )

    s = MatrixMegOlmSession()
    assert isinstance(s.session_id, str)

    # encrypt returns base64 ciphertext
    ct = s.encrypt({"type": "m.room.message", "content": {}})
    assert isinstance(ct, str)

    # Verify MegOLM wire format (libolm message.cpp):
    #   version(0x03) | field1_varint(msg_index,tag=0x08) |
    #   field2_bytes(ciphertext,tag=0x12) | mac(8) | sig(64)
    from apprise.plugins.matrix.e2ee import _b64dec

    raw = _b64dec(ct)
    assert raw[0:1] == b"\x03", "MegOLM version must be 0x03"
    assert raw[1:2] == b"\x08", "MegOLM field 1 tag must be 0x08 (varint)"
    # After tag 0x08: the varint counter value (0 -> single byte 0x00),
    # then the ciphertext tag 0x12.
    assert b"\x12" in raw, "MegOLM ciphertext field tag 0x12 must be present"

    # session_key returns base64 -- verify wire format per libolm
    # outbound_group_session.c: version(1) + counter(4) + ratchet(128)
    # + ed25519_pub(32) + ed25519_sig(64) = 229 bytes raw = 308 base64 chars
    sk = s.session_key()
    assert isinstance(sk, str)
    sk_raw = _b64dec(sk)
    assert len(sk_raw) == 229, "session_key must be 229 bytes (sig included)"
    assert sk_raw[0:1] == b"\x02", "session_key version must be 0x02"

    # to_dict / from_dict round-trip
    d = s.to_dict()
    assert d["version"] == MATRIX_MEGOLM_STORE_VERSION
    s2 = MatrixMegOlmSession.from_dict(d)
    assert s2.session_id == s.session_id
    assert s2._counter == s._counter

    # should_rotate: explicit count threshold
    assert not s.should_rotate(msg_count=MEGOLM_ROTATION_MSGS - 1)
    assert s.should_rotate(msg_count=MEGOLM_ROTATION_MSGS)

    # should_rotate: time threshold (old created_at)
    old = MatrixMegOlmSession(created_at=0.0)
    assert old.should_rotate()

    # _advance branches -- cascade fires when (n+1) % threshold == 0,
    # i.e. when the counter is one less than a threshold multiple.

    # -- normal step (else branch)
    s3 = MatrixMegOlmSession()
    s3._advance()  # counter 0 -> 1  (1 % 256 != 0, else: R[3] only)

    # -- %256 branch: next counter will be 256
    s4 = MatrixMegOlmSession()
    s4._counter = 255
    s4._advance()

    # -- %65536 branch: next counter will be 65536
    s5 = MatrixMegOlmSession()
    s5._counter = 65535
    s5._advance()

    # -- %2^24 branch: next counter will be 2^24
    s6 = MatrixMegOlmSession()
    s6._counter = (1 << 24) - 1
    s6._advance()


# ---------------------------------------------------------------------------
# E2EE integration tests -- URL parsing and send flow
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="Requires cryptography")
def test_plugin_matrix_e2ee_url_roundtrip():
    """e2ee default is True; disabled state survives url() / parse_url()."""
    # Default (no e2ee param) is now True
    obj = NotifyMatrix(
        host="matrix.example.com",
        user="user",
        password="pass",
        targets=["#room"],
    )
    assert obj.e2ee is True
    # Enabled is the default -- not written to URL
    assert "e2ee" not in obj.url()

    # Disabled survives round-trip
    obj2 = NotifyMatrix(
        host="matrix.example.com",
        user="user",
        password="pass",
        targets=["#room"],
        e2ee=False,
    )
    assert obj2.e2ee is False
    u2 = obj2.url()
    assert "e2ee=no" in u2

    result = NotifyMatrix.parse_url(u2)
    assert result is not None
    assert result.get("e2ee") is False or str(result.get("e2ee")).lower() in (
        "false",
        "no",
        "0",
    )


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="Requires cryptography")
def test_plugin_matrix_e2ee_insecure_connection(mock_post, mock_get, mock_put):
    """e2ee=yes over insecure (matrix://) falls back to unencrypted."""
    resp = mock.Mock()
    resp.status_code = requests.codes.ok
    resp.content = dumps(
        {
            "access_token": "tok",
            "user_id": "@u:h",
            "home_server": "h",
            "device_id": "DEV",
            "room_id": "!r:h",
        }
    ).encode()
    mock_post.return_value = resp
    mock_get.return_value = resp
    mock_put.return_value = resp

    # matrix:// (not matrixs://) -- E2EE silently skipped, plain delivery
    obj = NotifyMatrix(
        host="h",
        user="u",
        password="pass",
        targets=["#room"],
        e2ee=True,
        # secure=False is the default for matrix:// URLs
    )
    assert not obj.secure
    assert obj.send(body="test") is True


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="Requires cryptography")
def test_plugin_matrix_e2ee_no_support(mock_post, mock_get, mock_put):
    """e2ee=yes with MATRIX_E2EE_SUPPORT=False sends unencrypted."""
    resp = mock.Mock()
    resp.status_code = requests.codes.ok
    resp.content = dumps(
        {
            "access_token": "tok",
            "user_id": "@u:h",
            "home_server": "h",
            "device_id": "DEV",
            "room_id": "!r:h",
        }
    ).encode()
    mock_post.return_value = resp
    mock_get.return_value = resp
    mock_put.return_value = resp

    with mock.patch(
        "apprise.plugins.matrix.base.MATRIX_E2EE_SUPPORT",
        False,
    ):
        obj = NotifyMatrix(
            host="h",
            user="u",
            password="pass",
            targets=["#room"],
            e2ee=True,
        )
        # Should succeed (falls back to unencrypted)
        assert obj.send(body="test") is True


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="Requires cryptography")
def test_plugin_matrix_e2ee_send(mock_post, mock_get, mock_put):
    """Full E2EE send path via _send_server_notification."""
    from apprise.plugins.matrix.e2ee import MatrixOlmAccount

    # Recipient device (acts as a room member)
    recipient = MatrixOlmAccount()

    login_resp = {
        "access_token": "tok123",
        "user_id": "@sender:localhost",
        "home_server": "localhost",
        "device_id": "SENDERDEV",
    }

    members_resp = {
        "joined": {"@other:localhost": {}},
    }

    # Properly signed device keys (required by verify_device_keys)
    signed_dev = recipient.device_keys_payload("@other:localhost", "OTHERDEV")
    query_resp = {
        "device_keys": {"@other:localhost": {"OTHERDEV": signed_dev}}
    }

    # Properly signed OTK (required by verify_signed_otk)
    signed_otk = _make_signed_otk(recipient, "@other:localhost", "OTHERDEV")
    claim_resp = {
        "one_time_keys": {
            "@other:localhost": {
                "OTHERDEV": {"signed_curve25519:KEYID": signed_otk}
            }
        }
    }

    def _mk_resp(d):
        r = mock.Mock()
        r.status_code = requests.codes.ok
        r.content = dumps(d).encode()
        return r

    # POST sequence:
    # login, keys/upload (with OTK count), join, keys/query, keys/claim,
    # keys/upload (OTK replenishment), logout
    mock_post.side_effect = [
        _mk_resp(login_resp),
        _mk_resp({"one_time_key_counts": {"signed_curve25519": 1}}),
        _mk_resp({"room_id": "!room:localhost"}),  # join
        _mk_resp(query_resp),  # keys/query
        _mk_resp(claim_resp),  # keys/claim
        # Replenishment: remaining = 1 - 1 (built_count) = 0 < threshold
        _mk_resp(
            {
                "one_time_key_counts": {
                    "signed_curve25519": NotifyMatrix.default_e2ee_otk_count,
                }
            }
        ),
        _mk_resp({}),  # logout
    ]
    mock_get.return_value = _mk_resp(members_resp)
    mock_put.return_value = _mk_resp({})

    obj = NotifyMatrix(
        host="localhost",
        user="sender",
        password="pass",
        targets=["#room"],
        e2ee=True,
        secure=True,
        discovery=False,
    )
    assert obj.send(body="hello", title="hi") is True

    # PUT was called: sendToDevice + rooms/send/encrypted
    assert mock_put.call_count >= 2


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="Requires cryptography")
def test_plugin_matrix_e2ee_send_cached_session(mock_post, mock_get, mock_put):
    """E2EE send skips key-share when session key already shared."""
    login_resp = {
        "access_token": "tok",
        "user_id": "@u:h",
        "home_server": "h",
        "device_id": "DEV",
    }

    def _mk_resp(d):
        r = mock.Mock()
        r.status_code = requests.codes.ok
        r.content = dumps(d).encode()
        return r

    # POST: login, keys/upload, join, logout
    mock_post.side_effect = [
        _mk_resp(login_resp),
        _mk_resp({}),  # keys/upload
        _mk_resp({"room_id": "!r:h"}),  # join
        _mk_resp({}),  # logout
    ]
    mock_put.return_value = _mk_resp({})

    from apprise.plugins.matrix.e2ee import MatrixMegOlmSession

    obj = NotifyMatrix(
        host="h",
        user="u",
        password="pass",
        targets=["!r:h"],
        e2ee=True,
        secure=True,
        discovery=False,
    )
    # Pre-seed room encryption state, MegOLM session, and key-shared flag
    # so that no additional GETs or key-exchange PUTs are issued.
    _sess = MatrixMegOlmSession()
    obj.store.set("e2ee_room_enc_!r:h", True)
    obj.store.set("e2ee_megolm_!r:h", _sess.to_dict())
    obj.store.set("e2ee_key_shared_!r:h", _sess.session_id)
    assert obj.send(body="silent") is True
    # Only one PUT for the encrypted message itself
    assert mock_put.call_count == 1


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="Requires cryptography")
def test_plugin_matrix_e2ee_send_legacy_shared_flag_rekeys(
    mock_post, mock_get, mock_put
):
    """Legacy boolean key-share cache forces a fresh room-key share."""
    from apprise.plugins.matrix.e2ee import (
        MatrixMegOlmSession,
        MatrixOlmAccount,
    )

    obj = NotifyMatrix(
        host="h",
        user="u",
        password="pass",
        targets=["#r"],
        e2ee=True,
    )
    obj.access_token = "tok"
    obj.home_server = "h"
    obj.user_id = "@u:h"
    obj.device_id = "DEV"
    obj._e2ee_account = MatrixOlmAccount()
    session = MatrixMegOlmSession()
    obj.store.set("e2ee_megolm_!r:h", session.to_dict())
    obj.store.set("e2ee_key_shared_!r:h", True)

    with (
        mock.patch.object(
            obj, "_e2ee_share_room_key", return_value=True
        ) as share,
        mock.patch.object(obj, "_fetch", return_value=(True, {}, 200)),
    ):
        assert (
            obj._e2ee_send_to_room("!r:h", "body", "", NotifyType.INFO) is True
        )

    assert share.call_count == 1
    assert obj.store.get("e2ee_key_shared_!r:h") == session.session_id


@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="Requires cryptography")
def test_plugin_matrix_e2ee_setup_restored():
    """E2EE account restores from store via _e2ee_setup and __init__."""
    from apprise.plugins.matrix.e2ee import MatrixOlmAccount

    acct = MatrixOlmAccount()

    obj = NotifyMatrix(
        host="h",
        user="u",
        password="pass",
        targets=["#r"],
        e2ee=True,
    )
    # Seed account + mark keys already uploaded
    obj.store.set("e2ee_account", acct.to_dict())
    obj.store.set("e2ee_keys_uploaded", True)
    obj.store.set(
        "e2ee_device_binding",
        "{}|{}|{}|{}".format(
            obj.user_id or "",
            obj.device_id or "",
            acct.identity_key,
            acct.signing_key,
        ),
    )

    # Simulate state where account is not yet loaded in memory
    obj._e2ee_account = None

    # _e2ee_setup should restore the account from the store
    assert obj._e2ee_setup() is True
    assert obj._e2ee_account is not None
    assert obj._e2ee_account.identity_key == acct.identity_key

    # Bad account data in store -> _e2ee_setup creates a fresh account;
    # the try/except in _e2ee_setup is exercised when from_dict raises.
    obj._e2ee_account = None
    obj.store.set("e2ee_account", {"bad": "data"})
    obj.store.clear("e2ee_keys_uploaded")
    with mock.patch.object(obj, "_e2ee_upload_keys", return_value=True):
        result = obj._e2ee_setup()
    assert result is True
    assert obj._e2ee_account is not None

    # Patch the store so __init__ sees a valid pre-existing account,
    # exercising the success path of the contextlib.suppress block.
    valid_data = obj._e2ee_account.to_dict()
    with mock.patch(
        "apprise.persistent_store.PersistentStore.get",
        return_value=valid_data,
    ):
        obj2 = NotifyMatrix(
            host="h",
            user="u",
            password="pass",
            targets=["#r"],
            e2ee=True,
        )
    assert obj2._e2ee_account is not None


@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="Requires cryptography")
def test_plugin_matrix_e2ee_setup_reuploads_on_binding_change():
    """Changed device/account identity forces a fresh key upload."""
    from apprise.plugins.matrix.e2ee import MatrixOlmAccount

    acct = MatrixOlmAccount()
    obj = NotifyMatrix(
        host="h",
        user="u",
        password="pass",
        targets=["#r"],
        e2ee=True,
    )
    obj.user_id = "@u:h"
    obj.device_id = "DEV_NEW"
    obj._e2ee_account = acct
    obj.store.set("e2ee_account", acct.to_dict())
    obj.store.set("e2ee_keys_uploaded", True)
    obj.store.set("e2ee_device_binding", "@u:h|DEV_OLD|oldik|oldsk")

    with mock.patch.object(
        obj, "_e2ee_upload_keys", return_value=True
    ) as upload:
        assert obj._e2ee_setup() is True

    assert upload.call_count == 1


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="Requires cryptography")
def test_plugin_matrix_e2ee_upload_keys_no_ids(mock_post, mock_get, mock_put):
    """_e2ee_upload_keys returns False when user_id/device_id missing."""
    from apprise.plugins.matrix.e2ee import MatrixOlmAccount

    obj = NotifyMatrix(
        host="h",
        user="u",
        password="pass",
        targets=["#r"],
        e2ee=True,
    )
    obj._e2ee_account = MatrixOlmAccount()
    # No user_id / device_id set
    assert obj._e2ee_upload_keys() is False


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="Requires cryptography")
def test_plugin_matrix_e2ee_upload_keys_http_fail(
    mock_post, mock_get, mock_put
):
    """_e2ee_upload_keys returns False on HTTP error."""
    from apprise.plugins.matrix.e2ee import MatrixOlmAccount

    resp = mock.Mock()
    resp.status_code = 500
    resp.content = dumps({}).encode()
    mock_post.return_value = resp

    obj = NotifyMatrix(
        host="h",
        user="u",
        password="pass",
        targets=["#r"],
        e2ee=True,
    )
    obj._e2ee_account = MatrixOlmAccount()
    obj.access_token = "tok"
    obj.user_id = "@u:h"
    obj.device_id = "DEV"
    obj.home_server = "h"
    assert obj._e2ee_upload_keys() is False


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="Requires cryptography")
def test_plugin_matrix_e2ee_upload_keys_success_marks_published(
    mock_post, mock_get, mock_put
):
    """Successful upload clears the current unpublished OTK batch."""
    from apprise.plugins.matrix.e2ee import MatrixOlmAccount

    resp = mock.Mock()
    resp.status_code = requests.codes.ok
    resp.content = dumps(
        {
            "one_time_key_counts": {
                "signed_curve25519": NotifyMatrix.default_e2ee_otk_count,
            }
        }
    ).encode()
    mock_post.return_value = resp

    obj = NotifyMatrix(
        host="h",
        user="u",
        password="pass",
        targets=["#r"],
        e2ee=True,
    )
    obj._e2ee_account = MatrixOlmAccount()
    obj.access_token = "tok"
    obj.user_id = "@u:h"
    obj.device_id = "DEV"
    obj.home_server = "h"

    # Pre-generate one-time keys so we can verify they are marked published.
    obj._e2ee_account.one_time_keys_payload(
        obj.user_id, obj.device_id, count=3
    )
    assert obj._e2ee_account._otks
    assert obj._e2ee_upload_keys() is True
    assert obj._e2ee_account._otks == {}
    # Server OTK count from the response is persisted for threshold checks.
    assert obj.store.get("e2ee_otk_server_count") == (
        NotifyMatrix.default_e2ee_otk_count
    )


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_matrix_whoami(mock_post, mock_get, mock_put):
    """_whoami() resolves user_id and device_id from GET /account/whoami."""

    def _mk_resp(d, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = dumps(d).encode()
        return r

    obj = NotifyMatrix(
        host="h",
        password="rawtoken",
        targets=["#r"],
        e2ee=True,
    )
    obj.access_token = "rawtoken"
    obj.home_server = "h"

    # Success: server returns user_id and device_id; home_server is
    # extracted from user_id so DM targets resolve correctly.
    mock_get.return_value = _mk_resp(
        {"user_id": "@tok:h", "device_id": "TOKDEV"}
    )
    assert obj._whoami() is True
    assert obj.user_id == "@tok:h"
    assert obj.device_id == "TOKDEV"
    assert obj.home_server == "h"
    assert obj.store.get("user_id") == "@tok:h"
    assert obj.store.get("device_id") == "TOKDEV"
    assert obj.store.get("home_server") == "h"

    # user_id without homeserver component (@alice, no colon) -> home_server
    # is not extracted (branch where len(parts) != 2 is not taken).
    obj.user_id = None
    obj.home_server = None
    mock_get.return_value = _mk_resp(
        {"user_id": "@noserver", "device_id": "DEV2"}
    )
    assert obj._whoami() is True
    assert obj.user_id == "@noserver"
    assert obj.home_server is None  # no colon -> not extracted

    # home_server already known -> not overwritten
    obj.home_server = "existing.h"
    mock_get.return_value = _mk_resp(
        {"user_id": "@tok:other.h", "device_id": "DEV3"}
    )
    assert obj._whoami() is True
    assert obj.home_server == "existing.h"

    # Failure: server returns non-200
    obj.user_id = None
    obj.device_id = None
    mock_get.return_value = _mk_resp({}, code=401)
    assert obj._whoami() is False


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_matrix_send_cached_token_recovers_home_server(
    mock_post, mock_get, mock_put
):
    """Cached auth without home_server should be repaired via _whoami()."""

    obj = NotifyMatrix(
        host="matrix.org",
        user="apprise",
        password="pass",
        targets=["#general"],
    )
    obj.access_token = "cached-token"
    obj.user_id = None
    obj.device_id = None
    obj.home_server = None

    whoami_called = {"count": 0}

    def _fake_whoami():
        whoami_called["count"] += 1
        obj.user_id = "@apprise:matrix.org"
        obj.device_id = "DEV42"
        obj.home_server = "matrix.org"
        return True

    with (
        mock.patch.object(obj, "_room_join", return_value="!room:matrix.org"),
        mock.patch.object(obj, "_whoami", side_effect=_fake_whoami),
        mock.patch.object(
            obj, "_fetch", return_value=(True, {"event_id": "$1"}, 200)
        ),
    ):
        assert obj.send("body", title="test") is True

    assert whoami_called["count"] == 1
    assert obj.home_server == "matrix.org"
    assert obj.user_id == "@apprise:matrix.org"


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="Requires cryptography")
def test_plugin_matrix_e2ee_get_megolm_rotation(mock_post, mock_get, mock_put):
    """_e2ee_get_megolm rotates session after threshold."""
    from apprise.plugins.matrix.e2ee import (
        MEGOLM_ROTATION_MSGS,
        MatrixMegOlmSession,
    )

    obj = NotifyMatrix(
        host="h",
        user="u",
        password="pass",
        targets=["#r"],
        e2ee=True,
    )

    # Seed a session that is already past the rotation threshold
    stale = MatrixMegOlmSession()
    stale._counter = MEGOLM_ROTATION_MSGS
    obj.store.set("e2ee_megolm_!r:h", stale.to_dict())
    obj.store.set("e2ee_key_shared_!r:h", True)

    new_session = obj._e2ee_get_megolm("!r:h")
    assert new_session.session_id != stale.session_id

    # The shared flag should be cleared on rotation
    assert obj.store.get("e2ee_key_shared_!r:h") is None

    # Legacy cached sessions without the current version marker are
    # invalidated and replaced with a fresh session.
    legacy = stale.to_dict()
    del legacy["version"]
    obj.store.set("e2ee_megolm_!r:h", legacy)
    obj.store.set("e2ee_key_shared_!r:h", stale.session_id)
    replaced = obj._e2ee_get_megolm("!r:h")
    assert replaced.session_id != stale.session_id
    assert obj.store.get("e2ee_key_shared_!r:h") is None


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="Requires cryptography")
def test_plugin_matrix_e2ee_room_encrypted(mock_post, mock_get, mock_put):
    """_e2ee_room_encrypted: cached, GET success, GET failure paths."""

    def _mk_resp(d, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = dumps(d).encode()
        return r

    obj = NotifyMatrix(
        host="h",
        user="u",
        password="pass",
        targets=["#r"],
        e2ee=True,
    )
    obj.access_token = "tok"
    obj.home_server = "h"

    # Cache hit -- no GET fired
    obj.store.set("e2ee_room_enc_!r:h", True)
    assert obj._e2ee_room_encrypted("!r:h") is True
    assert mock_get.call_count == 0

    # Cache miss, GET returns 200 with content -> True
    obj.store.clear("e2ee_room_enc_!r:h")
    mock_get.return_value = _mk_resp({"algorithm": "m.megolm.v1.aes-sha2"})
    assert obj._e2ee_room_encrypted("!r:h") is True
    assert mock_get.call_count == 1

    # Cache is now populated
    assert obj.store.get("e2ee_room_enc_!r:h") is True

    # Cache miss, GET returns 404 -> False
    obj.store.clear("e2ee_room_enc_!r:h")
    mock_get.return_value = _mk_resp({}, code=404)
    assert obj._e2ee_room_encrypted("!r:h") is False
    assert obj.store.get("e2ee_room_enc_!r:h") is False


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="Requires cryptography")
def test_plugin_matrix_e2ee_room_members(mock_post, mock_get, mock_put):
    """_e2ee_room_members handles HTTP failures and empty rooms."""

    def _mk_resp(d, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = dumps(d).encode()
        return r

    obj = NotifyMatrix(
        host="h",
        user="u",
        password="pass",
        targets=["#r"],
        e2ee=True,
    )
    obj.access_token = "tok"
    obj.home_server = "h"

    # joined_members HTTP failure -> None
    mock_get.return_value = _mk_resp({}, code=500)
    assert obj._e2ee_room_members("!r:h") is None

    # No joined members -> empty dict
    mock_get.return_value = _mk_resp({"joined": {}})
    assert obj._e2ee_room_members("!r:h") == {}

    # keys/query failure -> None
    mock_get.return_value = _mk_resp({"joined": {"@u:h": {}}})
    mock_post.return_value = _mk_resp({}, code=500)
    assert obj._e2ee_room_members("!r:h") is None

    # Unsigned device key -> device is rejected (empty result for that uid)
    from apprise.plugins.matrix.e2ee import MatrixOlmAccount

    unsigned_resp = {
        "device_keys": {
            "@u:h": {
                "DEV": {
                    "keys": {
                        "curve25519:DEV": "IK",
                        "ed25519:DEV": "SK",
                    }
                    # no "signatures" field
                }
            }
        }
    }
    mock_get.return_value = _mk_resp({"joined": {"@u:h": {}}})
    mock_post.return_value = _mk_resp(unsigned_resp)
    result = obj._e2ee_room_members("!r:h")
    assert result["@u:h"] == {}

    # Properly signed device key -> device included
    acct = MatrixOlmAccount()
    signed_dev = acct.device_keys_payload("@u:h", "DEV")
    query_resp = {"device_keys": {"@u:h": {"DEV": signed_dev}}}
    mock_get.return_value = _mk_resp({"joined": {"@u:h": {}}})
    mock_post.return_value = _mk_resp(query_resp)
    result = obj._e2ee_room_members("!r:h")
    assert "@u:h" in result
    assert result["@u:h"]["DEV"]["curve25519"] == acct.identity_key


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="Requires cryptography")
def test_plugin_matrix_e2ee_share_room_key_branches(
    mock_post, mock_get, mock_put
):
    """_e2ee_share_room_key edge cases."""
    from apprise.plugins.matrix.e2ee import (
        MatrixMegOlmSession,
        MatrixOlmAccount,
    )

    def _mk_resp(d, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = dumps(d).encode()
        return r

    obj = NotifyMatrix(
        host="h",
        user="u",
        password="pass",
        targets=["#r"],
        e2ee=True,
    )
    obj.access_token = "tok"
    obj.home_server = "h"
    obj.user_id = "@sender:h"
    obj.device_id = "SDEV"
    obj._e2ee_account = MatrixOlmAccount()
    session = MatrixMegOlmSession()

    # members failure -> False
    with mock.patch.object(obj, "_e2ee_room_members", return_value=None):
        assert obj._e2ee_share_room_key("!r:h", session) is False

    # empty members -> True (nothing to send)
    with mock.patch.object(obj, "_e2ee_room_members", return_value={}):
        assert obj._e2ee_share_room_key("!r:h", session) is True

    # keys/claim failure -> False
    members = {"@other:h": {"DEV": {"curve25519": "IK", "ed25519": "SK"}}}
    mock_post.return_value = _mk_resp({}, code=500)
    with mock.patch.object(obj, "_e2ee_room_members", return_value=members):
        assert obj._e2ee_share_room_key("!r:h", session) is False

    # keys/claim succeeds but server reports failures{} for remote servers
    # (line 2160 branch: failures dict is non-empty -> debug log, still
    # continues normally; no OTKs returned so built_count=0 -> True).
    failures_resp = {
        "one_time_keys": {},
        "failures": {"remote.example": {"errcode": "M_UNREACHABLE"}},
    }
    mock_post.return_value = _mk_resp(failures_resp)
    with mock.patch.object(obj, "_e2ee_room_members", return_value=members):
        assert obj._e2ee_share_room_key("!r:h", session) is True

    # own device is skipped (sender uid + device match)
    own_members = {
        "@sender:h": {"SDEV": {"curve25519": "IK", "ed25519": "SK"}}
    }
    otk_resp = {
        "one_time_keys": {
            "@sender:h": {"SDEV": {"signed_curve25519:KID": _rand_b64_32()}}
        }
    }
    mock_post.return_value = _mk_resp(otk_resp)
    mock_put.return_value = _mk_resp({})
    with mock.patch.object(
        obj, "_e2ee_room_members", return_value=own_members
    ):
        # All devices skipped -> no PUT; still returns True
        assert obj._e2ee_share_room_key("!r:h", session) is True

    # missing curve25519 key -> device skipped
    no_ik = {"@other:h": {"DEV": {"curve25519": "", "ed25519": "SK"}}}
    with mock.patch.object(obj, "_e2ee_room_members", return_value=no_ik):
        mock_post.return_value = _mk_resp(
            {"one_time_keys": {"@other:h": {"DEV": {}}}}
        )
        assert obj._e2ee_share_room_key("!r:h", session) is True

    # dict-valued OTK with valid signature succeeds end-to-end
    recipient = MatrixOlmAccount()
    their_ik = recipient.identity_key
    their_otk_b64 = _rand_b64_32()
    signed_otk_dict = _make_signed_otk(
        recipient, "@other:h", "DEV", their_otk_b64
    )
    dict_members = {
        "@other:h": {
            "DEV": {
                "curve25519": their_ik,
                "ed25519": recipient.signing_key,
            }
        }
    }
    dict_otk = {
        "one_time_keys": {
            "@other:h": {"DEV": {"signed_curve25519:KID": signed_otk_dict}}
        }
    }
    mock_post.return_value = _mk_resp(dict_otk)
    mock_put.return_value = _mk_resp({})
    with mock.patch.object(
        obj, "_e2ee_room_members", return_value=dict_members
    ):
        assert obj._e2ee_share_room_key("!r:h", session) is True
        payload = loads(mock_put.call_args.kwargs["data"])
        dev_payload = payload["messages"]["@other:h"]["DEV"]
        assert dev_payload["sender_key"] == obj._e2ee_account.identity_key
        # recipient_key and org.matrix.msgid are non-standard fields
        # that were removed; verify they are absent
        assert "recipient_key" not in dev_payload
        assert "org.matrix.msgid" not in dev_payload

    # dict-valued OTK with no signatures -> OTK rejected, device skipped
    unsigned_otk_dict = {"key": their_otk_b64}  # no "signatures" field
    unsigned_otk_resp = {
        "one_time_keys": {
            "@other:h": {"DEV": {"signed_curve25519:KID": unsigned_otk_dict}}
        }
    }
    mock_post.return_value = _mk_resp(unsigned_otk_resp)
    with mock.patch.object(
        obj, "_e2ee_room_members", return_value=dict_members
    ):
        # No valid OTK -> no messages built -> True (nothing to send)
        assert obj._e2ee_share_room_key("!r:h", session) is True

    # Plain-string OTK for signed_curve25519 -> rejected (not a KeyObject)
    str_members = {
        "@other:h": {
            "DEV": {
                "curve25519": their_ik,
                "ed25519": recipient.signing_key,
            }
        }
    }
    str_otk = {
        "one_time_keys": {
            "@other:h": {"DEV": {"signed_curve25519:KID": their_otk_b64}}
        }
    }
    mock_post.return_value = _mk_resp(str_otk)
    with mock.patch.object(
        obj, "_e2ee_room_members", return_value=str_members
    ):
        # No valid KeyObject OTK -> no messages built -> True (nothing sent)
        assert obj._e2ee_share_room_key("!r:h", session) is True

    # OTK key not prefixed with "signed_curve25519:" -> skipped, no OTK found
    bad_key_otk = {
        "one_time_keys": {"@other:h": {"DEV": {"ed25519:KID": their_otk_b64}}}
    }
    mock_post.return_value = _mk_resp(bad_key_otk)
    with mock.patch.object(
        obj, "_e2ee_room_members", return_value=str_members
    ):
        assert obj._e2ee_share_room_key("!r:h", session) is True

    # OTK entry is not a dict (unexpected server response format)
    non_dict_otk = {"one_time_keys": {"@other:h": {"DEV": "invalid_format"}}}
    mock_post.return_value = _mk_resp(non_dict_otk)
    with mock.patch.object(
        obj, "_e2ee_room_members", return_value=str_members
    ):
        assert obj._e2ee_share_room_key("!r:h", session) is True

    # OTK value is an integer (unknown format) -> skipped
    non_str_otk = {
        "one_time_keys": {"@other:h": {"DEV": {"signed_curve25519:KID": 42}}}
    }
    mock_post.return_value = _mk_resp(non_str_otk)
    with mock.patch.object(
        obj, "_e2ee_room_members", return_value=str_members
    ):
        assert obj._e2ee_share_room_key("!r:h", session) is True

    # create_outbound_session raises -> device is skipped gracefully
    # Use a properly signed OTK so verification passes and the Olm call
    # is actually reached.
    create_fail_signed = _make_signed_otk(
        recipient, "@other:h", "DEV", their_otk_b64
    )
    create_fail_otk = {
        "one_time_keys": {
            "@other:h": {"DEV": {"signed_curve25519:KID": create_fail_signed}}
        }
    }
    mock_post.return_value = _mk_resp(create_fail_otk)
    with (
        mock.patch.object(
            obj, "_e2ee_room_members", return_value=dict_members
        ),
        mock.patch.object(
            obj._e2ee_account,
            "create_outbound_session",
            side_effect=Exception("olm error"),
        ),
    ):
        assert obj._e2ee_share_room_key("!r:h", session) is True

    # sendToDevice PUT fails -> returns False (key-shared flag not set)
    # Uses a signed OTK so the full Olm path is exercised before the PUT
    full_signed_otk = _make_signed_otk(
        recipient, "@other:h", "DEV", their_otk_b64
    )
    full_otk_resp = {
        "one_time_keys": {
            "@other:h": {"DEV": {"signed_curve25519:KID": full_signed_otk}}
        }
    }
    mock_post.return_value = _mk_resp(full_otk_resp)
    mock_put.return_value = _mk_resp({}, code=500)
    with mock.patch.object(
        obj, "_e2ee_room_members", return_value=dict_members
    ):
        assert obj._e2ee_share_room_key("!r:h", session) is False

    # token-as-password mode: transaction_id is a UUID, not an int.
    # Previously, the unconditional `+= 1` raised TypeError (UUID + int).
    # With the guard in place the UUID is used as-is and the send succeeds.
    import uuid as _uuid_mod

    uuid_obj = NotifyMatrix(
        host="h", password="rawtoken", targets=["#r"], e2ee=True
    )
    uuid_obj.access_token = "rawtoken"
    uuid_obj.password = "rawtoken"
    uuid_obj.transaction_id = _uuid_mod.uuid4()  # UUID, not int
    uuid_obj.home_server = "h"
    uuid_obj.user_id = "@tok:h"
    uuid_obj.device_id = "TOKDEV"
    uuid_obj._e2ee_account = MatrixOlmAccount()

    uuid_session = MatrixMegOlmSession()
    uuid_otk = _make_signed_otk(recipient, "@other:h", "DEV", their_otk_b64)
    uuid_claim = {
        "one_time_keys": {
            "@other:h": {"DEV": {"signed_curve25519:KID": uuid_otk}}
        }
    }
    mock_post.return_value = _mk_resp(uuid_claim)
    mock_put.return_value = _mk_resp({})
    with mock.patch.object(
        uuid_obj, "_e2ee_room_members", return_value=dict_members
    ):
        # Must not raise TypeError; transaction_id stays as UUID
        assert uuid_obj._e2ee_share_room_key("!r:h", uuid_session) is True
        assert isinstance(uuid_obj.transaction_id, _uuid_mod.UUID)


@mock.patch("requests.post")
@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="Requires cryptography")
def test_plugin_matrix_e2ee_replenish_otks(mock_post):
    """_e2ee_replenish_otks: threshold logic, diagnostics, and error paths."""
    from apprise.plugins.matrix.e2ee import MatrixOlmAccount

    otk_count = NotifyMatrix.default_e2ee_otk_count
    otk_threshold = NotifyMatrix.default_e2ee_otk_replenish_threshold

    def _mk_resp(d, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = dumps(d).encode()
        return r

    def _make_obj():
        obj = NotifyMatrix(
            host="h", user="u", password="pass", targets=["#r"], e2ee=True
        )
        obj.user_id = "@u:h"
        obj.device_id = "DEV"
        obj._e2ee_account = MatrixOlmAccount()
        return obj

    # --- missing credentials: no network call, returns False ---
    obj = _make_obj()
    obj.user_id = None
    assert obj._e2ee_replenish_otks() is False
    assert mock_post.call_count == 0

    obj = _make_obj()
    obj.device_id = None
    assert obj._e2ee_replenish_otks() is False
    assert mock_post.call_count == 0

    # --- pool sufficient: skip upload ---
    # Store a count well above threshold; claimed_count=1 -> remaining is
    # above default_e2ee_otk_replenish_threshold so no upload should happen.
    obj = _make_obj()
    obj.store.set("e2ee_otk_server_count", otk_threshold + otk_count)
    result = obj._e2ee_replenish_otks(claimed_count=1, skipped_no_otk=0)
    assert result is True
    assert mock_post.call_count == 0

    # --- pool low: remaining < threshold triggers upload ---
    obj = _make_obj()
    obj.store.set("e2ee_otk_server_count", otk_threshold - 1)
    mock_post.return_value = _mk_resp(
        {"one_time_key_counts": {"signed_curve25519": otk_count}}
    )
    assert obj._e2ee_replenish_otks(claimed_count=0, skipped_no_otk=0) is True
    assert mock_post.call_count == 1
    assert obj.store.get("e2ee_otk_server_count") == otk_count
    assert obj.store.get("e2ee_account") is not None
    mock_post.reset_mock()

    # --- unknown server count (no store entry): replenish as precaution ---
    obj = _make_obj()
    # e2ee_otk_server_count not set -> unknown
    mock_post.return_value = _mk_resp(
        {"one_time_key_counts": {"signed_curve25519": otk_count}}
    )
    assert obj._e2ee_replenish_otks(claimed_count=0, skipped_no_otk=0) is True
    assert mock_post.call_count == 1
    mock_post.reset_mock()

    # --- skipped_no_otk > 0: always replenishes regardless of count ---
    obj = _make_obj()
    obj.store.set("e2ee_otk_server_count", otk_threshold + otk_count)
    mock_post.return_value = _mk_resp(
        {"one_time_key_counts": {"signed_curve25519": otk_count}}
    )
    assert obj._e2ee_replenish_otks(claimed_count=0, skipped_no_otk=2) is True
    assert mock_post.call_count == 1
    mock_post.reset_mock()

    # --- upload failure: returns False, logs warning ---
    obj = _make_obj()
    obj.store.set("e2ee_otk_server_count", 0)
    mock_post.return_value = _mk_resp({}, code=500)
    assert obj._e2ee_replenish_otks(claimed_count=0, skipped_no_otk=0) is False
    mock_post.reset_mock()

    # --- response missing one_time_key_counts: new count defaults to 0 ---
    obj = _make_obj()
    obj.store.set("e2ee_otk_server_count", 0)
    mock_post.return_value = _mk_resp({})  # no one_time_key_counts key
    assert obj._e2ee_replenish_otks(claimed_count=0, skipped_no_otk=0) is True
    assert obj.store.get("e2ee_otk_server_count") == 0
    mock_post.reset_mock()


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="Requires cryptography")
def test_plugin_matrix_e2ee_send_to_room_formats(
    mock_post, mock_get, mock_put
):
    """_e2ee_send_to_room: HTML/Markdown format paths and key-share fail."""
    from apprise.common import NotifyFormat
    from apprise.plugins.matrix.e2ee import (
        MatrixMegOlmSession,
        MatrixOlmAccount,
    )

    def _mk_resp(d):
        r = mock.Mock()
        r.status_code = requests.codes.ok
        r.content = dumps(d).encode()
        return r

    mock_put.return_value = _mk_resp({})

    def _make_obj(fmt):
        obj = NotifyMatrix(
            host="h",
            user="u",
            password="pass",
            targets=["#r"],
            e2ee=True,
        )
        obj.notify_format = fmt
        obj.access_token = "tok"
        obj.home_server = "h"
        obj.user_id = "@u:h"
        obj.device_id = "DEV"
        obj._e2ee_account = MatrixOlmAccount()
        return obj

    # HTML format
    obj = _make_obj(NotifyFormat.HTML)
    session = MatrixMegOlmSession()
    obj.store.set("e2ee_megolm_!r:h", session.to_dict())
    obj.store.set("e2ee_key_shared_!r:h", session.session_id)
    assert (
        obj._e2ee_send_to_room(
            "!r:h", "<b>body</b>", "<h1>title</h1>", NotifyType.INFO
        )
        is True
    )

    # Markdown format
    obj = _make_obj(NotifyFormat.MARKDOWN)
    session = MatrixMegOlmSession()
    obj.store.set("e2ee_megolm_!r:h", session.to_dict())
    obj.store.set("e2ee_key_shared_!r:h", session.session_id)
    assert (
        obj._e2ee_send_to_room("!r:h", "**bold**", "title", NotifyType.INFO)
        is True
    )

    # key-share flags set after successful share (no pre-seeded flag)
    obj = _make_obj(NotifyFormat.TEXT)
    session = MatrixMegOlmSession()
    obj.store.set("e2ee_megolm_!r:h", session.to_dict())
    with mock.patch.object(obj, "_e2ee_share_room_key", return_value=True):
        assert (
            obj._e2ee_send_to_room("!r:h", "body", "", NotifyType.INFO) is True
        )

    # token-as-password mode: access_token == password skips txn increment
    obj = _make_obj(NotifyFormat.TEXT)
    obj.access_token = "same"
    obj.password = "same"
    session2 = MatrixMegOlmSession()
    obj.store.set("e2ee_megolm_!r:h", session2.to_dict())
    obj.store.set("e2ee_key_shared_!r:h", session2.session_id)
    assert obj._e2ee_send_to_room("!r:h", "body", "", NotifyType.INFO) is True

    # key-share failure aborts send
    obj = _make_obj(NotifyFormat.TEXT)
    obj.store.clear("e2ee_key_shared_!r:h")
    with mock.patch.object(obj, "_e2ee_share_room_key", return_value=False):
        assert (
            obj._e2ee_send_to_room("!r:h", "body", "", NotifyType.INFO)
            is False
        )


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="Requires cryptography")
def test_plugin_matrix_e2ee_setup_failure(mock_post, mock_get, mock_put):
    """When E2EE setup fails, send falls back to unencrypted."""
    resp = mock.Mock()
    resp.status_code = requests.codes.ok
    resp.content = dumps(
        {
            "access_token": "tok",
            "user_id": "@u:h",
            "home_server": "h",
            "device_id": "DEV",
            "room_id": "!r:h",
        }
    ).encode()
    # upload keys call fails
    fail_resp = mock.Mock()
    fail_resp.status_code = 500
    fail_resp.content = dumps({}).encode()
    mock_put.return_value = resp

    mock_post.side_effect = [
        resp,  # login
        fail_resp,  # keys/upload -> failure
        resp,  # join
        resp,  # logout
    ]
    mock_get.return_value = resp

    obj = NotifyMatrix(
        host="h",
        user="u",
        password="pass",
        targets=["!r:h"],
        e2ee=True,
        secure=True,
        discovery=False,
    )
    # Falls back to unencrypted -> send succeeds
    assert obj.send(body="fallback") is True


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="Requires cryptography")
def test_plugin_matrix_e2ee_attachment_encrypted(
    mock_post, mock_get, mock_put
):
    """E2EE mode encrypts and delivers attachments."""
    import tempfile

    login_resp = {
        "access_token": "tok",
        "user_id": "@u:h",
        "home_server": "h",
        "device_id": "DEV",
    }
    upload_resp = {"content_uri": "mxc://h/enc123"}

    def _mk_resp(d):
        r = mock.Mock()
        r.status_code = requests.codes.ok
        r.content = dumps(d).encode()
        return r

    mock_post.side_effect = [
        _mk_resp(login_resp),
        _mk_resp({}),  # keys/upload
        _mk_resp({"room_id": "!r:h"}),  # join
        _mk_resp(upload_resp),  # encrypted attachment upload
        _mk_resp({}),  # logout
    ]
    mock_get.return_value = _mk_resp({"joined": {}})
    mock_put.return_value = _mk_resp({})

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"test attachment")
        attach_path = f.name

    try:
        attach = AppriseAttachment()
        attach.add(attach_path)

        obj = NotifyMatrix(
            host="h",
            user="u",
            password="pass",
            targets=["!r:h"],
            e2ee=True,
            secure=True,
            discovery=False,
        )
        from apprise.plugins.matrix.e2ee import MatrixMegOlmSession

        _s = MatrixMegOlmSession()
        obj.store.set("e2ee_room_enc_!r:h", True)
        obj.store.set("e2ee_megolm_!r:h", _s.to_dict())
        obj.store.set("e2ee_key_shared_!r:h", _s.session_id)
        assert obj.send(body="body", attach=attach) is True

        # Two PUTs: encrypted message + encrypted attachment event
        assert mock_put.call_count == 2

    finally:
        os.unlink(attach_path)


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="Requires cryptography")
def test_plugin_matrix_e2ee_send_attachment_errors(
    mock_post, mock_get, mock_put
):
    """_e2ee_send_attachment error branches: OSError, network, HTTP fail."""
    import tempfile

    from apprise.plugins.matrix.e2ee import (
        MatrixMegOlmSession,
        MatrixOlmAccount,
    )

    def _mk_resp(d, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = dumps(d).encode()
        return r

    obj = NotifyMatrix(
        host="h",
        user="u",
        password="pass",
        targets=["!r:h"],
        e2ee=True,
        secure=True,
        discovery=False,
    )
    obj.access_token = "tok"
    obj.home_server = "h"
    obj.user_id = "@u:h"
    obj.device_id = "DEV"
    obj._e2ee_account = MatrixOlmAccount()
    session = MatrixMegOlmSession()

    # OSError reading file -> False
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"data")
        tmp_path = f.name

    try:

        class _BadAttach:
            path = tmp_path
            name = "f.txt"
            mimetype = "text/plain"

            def __len__(self):
                return 0

        with mock.patch("builtins.open", side_effect=OSError("no read")):
            assert (
                obj._e2ee_send_attachment(_BadAttach(), "!r:h", session)
                is False
            )

        # Network error during upload -> False
        with mock.patch(
            "requests.post",
            side_effect=requests.RequestException("boom"),
        ):
            assert (
                obj._e2ee_send_attachment(_BadAttach(), "!r:h", session)
                is False
            )

        # HTTP error from media server -> False
        with mock.patch("requests.post", return_value=_mk_resp({}, code=500)):
            assert (
                obj._e2ee_send_attachment(_BadAttach(), "!r:h", session)
                is False
            )

        # Upload succeeds but response body is not valid JSON -> treated as
        # missing content_uri -> False
        bad_json_resp = mock.Mock()
        bad_json_resp.status_code = requests.codes.ok
        bad_json_resp.content = b"not-json"
        with mock.patch("requests.post", return_value=bad_json_resp):
            assert (
                obj._e2ee_send_attachment(_BadAttach(), "!r:h", session)
                is False
            )

        # base_url raises -> False
        with mock.patch(
            "apprise.plugins.matrix.base.NotifyMatrix.base_url",
            new_callable=mock.PropertyMock,
            side_effect=Exception("discovery fail"),
        ):
            assert (
                obj._e2ee_send_attachment(_BadAttach(), "!r:h", session)
                is False
            )

        # No access_token -> Authorization header omitted, upload still works
        obj_noauth = NotifyMatrix(
            host="h",
            user="u",
            password="pass",
            targets=["!r:h"],
            e2ee=True,
            secure=True,
            discovery=False,
        )
        obj_noauth.access_token = None
        obj_noauth.home_server = "h"
        obj_noauth.user_id = "@u:h"
        obj_noauth.device_id = "DEV"
        obj_noauth._e2ee_account = MatrixOlmAccount()
        sess_noauth = MatrixMegOlmSession()
        with mock.patch(
            "requests.post",
            return_value=_mk_resp({"content_uri": "mxc://h/y"}),
        ):
            mock_put.return_value = _mk_resp({})
            assert (
                obj_noauth._e2ee_send_attachment(
                    _BadAttach(), "!r:h", sess_noauth
                )
                is True
            )

        # access_token == password -> transaction ID not incremented
        obj2 = NotifyMatrix(
            host="h",
            user="u",
            password="tok",
            targets=["!r:h"],
            e2ee=True,
            secure=True,
            discovery=False,
        )
        obj2.access_token = "tok"
        obj2.password = "tok"
        obj2.home_server = "h"
        obj2.user_id = "@u:h"
        obj2.device_id = "DEV"
        obj2._e2ee_account = MatrixOlmAccount()
        sess2 = MatrixMegOlmSession()
        txn_before = obj2.transaction_id
        upload_r = _mk_resp({"content_uri": "mxc://h/x"})
        put_r = _mk_resp({})
        with mock.patch("requests.post", return_value=upload_r):
            mock_put.return_value = put_r
            result = obj2._e2ee_send_attachment(_BadAttach(), "!r:h", sess2)
        assert result is True
        assert obj2.transaction_id == txn_before

        # Image mimetype -> is_image branch (no 'filename' field added)
        class _ImageAttach:
            path = tmp_path
            name = "photo.png"
            mimetype = "image/png"

            def __len__(self):
                return 4

        with mock.patch("requests.post", return_value=upload_r):
            mock_put.return_value = put_r
            result = obj2._e2ee_send_attachment(_ImageAttach(), "!r:h", sess2)
        assert result is True

    finally:
        os.unlink(tmp_path)


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="Requires cryptography")
def test_plugin_matrix_e2ee_send_attachment_invalid(
    mock_post, mock_get, mock_put
):
    """Invalid attachment and _e2ee_send_attachment failure mark has_error."""
    import tempfile

    login_resp = {
        "access_token": "tok",
        "user_id": "@u:h",
        "home_server": "h",
        "device_id": "DEV",
    }

    def _mk_resp(d):
        r = mock.Mock()
        r.status_code = requests.codes.ok
        r.content = dumps(d).encode()
        return r

    mock_post.side_effect = [
        _mk_resp(login_resp),
        _mk_resp({}),  # keys/upload
        _mk_resp({"room_id": "!r:h"}),  # join
        _mk_resp({}),  # logout
    ]
    mock_get.return_value = _mk_resp({})
    mock_put.return_value = _mk_resp({})

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"data")
        attach_path = f.name

    try:
        from apprise.plugins.matrix.e2ee import MatrixMegOlmSession

        obj = NotifyMatrix(
            host="h",
            user="u",
            password="pass",
            targets=["!r:h"],
            e2ee=True,
            secure=True,
            discovery=False,
        )
        _s = MatrixMegOlmSession()
        obj.store.set("e2ee_room_enc_!r:h", True)
        obj.store.set("e2ee_megolm_!r:h", _s.to_dict())
        obj.store.set("e2ee_key_shared_!r:h", _s.session_id)

        attach = AppriseAttachment()
        attach.add(attach_path)

        # _e2ee_send_attachment fails -> send returns False
        with mock.patch.object(
            obj, "_e2ee_send_attachment", return_value=False
        ):
            assert obj.send(body="body", attach=attach) is False

        # Invalid attachment (falsy) in list -> has_error set and loop breaks
        mock_post.reset_mock()
        mock_post.side_effect = [
            _mk_resp(login_resp),
            _mk_resp({}),  # keys/upload
            _mk_resp({"room_id": "!r:h"}),  # join
            _mk_resp({}),  # logout
        ]
        obj2 = NotifyMatrix(
            host="h",
            user="u",
            password="pass",
            targets=["!r:h"],
            e2ee=True,
            secure=True,
            discovery=False,
        )
        _s2 = MatrixMegOlmSession()
        obj2.store.set("e2ee_room_enc_!r:h", True)
        obj2.store.set("e2ee_megolm_!r:h", _s2.to_dict())
        obj2.store.set("e2ee_key_shared_!r:h", _s2.session_id)
        # Add a non-existent file to get a falsy attachment
        bad_attach = AppriseAttachment()
        bad_attach.add("/nonexistent/path/file.txt")
        with mock.patch.object(obj2, "_e2ee_send_to_room", return_value=True):
            assert obj2.send(body="body", attach=bad_attach) is False

    finally:
        os.unlink(attach_path)


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="Requires cryptography")
def test_plugin_matrix_e2ee_send_room_failure(mock_post, mock_get, mock_put):
    """E2EE path returns False when _e2ee_send_to_room fails."""
    login_resp = {
        "access_token": "tok",
        "user_id": "@u:h",
        "home_server": "h",
        "device_id": "DEV",
    }

    def _mk_resp(d):
        r = mock.Mock()
        r.status_code = requests.codes.ok
        r.content = dumps(d).encode()
        return r

    mock_post.side_effect = [
        _mk_resp(login_resp),
        _mk_resp({}),  # keys/upload
        _mk_resp({"room_id": "!r:h"}),  # join
        _mk_resp({}),  # logout
    ]
    mock_get.return_value = _mk_resp({})
    mock_put.return_value = _mk_resp({})

    from apprise.plugins.matrix.e2ee import MatrixMegOlmSession

    obj = NotifyMatrix(
        host="h",
        user="u",
        password="pass",
        targets=["!r:h"],
        e2ee=True,
        secure=True,
        discovery=False,
    )
    obj.store.set("e2ee_room_enc_!r:h", True)
    _s = MatrixMegOlmSession()
    obj.store.set("e2ee_megolm_!r:h", _s.to_dict())
    obj.store.set("e2ee_key_shared_!r:h", _s.session_id)

    with mock.patch.object(obj, "_e2ee_send_to_room", return_value=False):
        assert obj.send(body="fail") is False


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_matrix_register_with_device_id(mock_post, mock_get, mock_put):
    """Registration response that includes device_id persists it."""
    r = mock.Mock()
    r.status_code = requests.codes.ok
    r.content = dumps(
        {
            "access_token": "tok",
            "user_id": "@u:h",
            "home_server": "h",
            "device_id": "REG_DEV",
        }
    ).encode()
    mock_post.return_value = r

    obj = NotifyMatrix(host="h", discovery=False)
    assert obj._register() is True
    assert obj.device_id == "REG_DEV"
    assert obj.store.get("device_id") == "REG_DEV"


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_matrix_login_reuses_device_id(mock_post, mock_get, mock_put):
    """Login payload reuses the stored device ID when present."""
    r = mock.Mock()
    r.status_code = requests.codes.ok
    r.content = dumps(
        {
            "access_token": "tok",
            "user_id": "@u:h",
            "home_server": "h",
            "device_id": "DEV_REUSED",
        }
    ).encode()
    mock_post.return_value = r

    obj = NotifyMatrix(host="h", user="u", password="pass", discovery=False)
    obj.device_id = "DEV_REUSED"
    assert obj._login() is True

    payload = mock_post.call_args.kwargs["data"]
    assert '"device_id": "DEV_REUSED"' in payload


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_matrix_register_reuses_device_id(
    mock_post, mock_get, mock_put
):
    """Register payload reuses the stored device ID when present."""
    r = mock.Mock()
    r.status_code = requests.codes.ok
    r.content = dumps(
        {
            "access_token": "tok",
            "user_id": "@u:h",
            "home_server": "h",
            "device_id": "DEV_REUSED",
        }
    ).encode()
    mock_post.return_value = r

    obj = NotifyMatrix(host="h", user="u", password="pass", discovery=False)
    obj.device_id = "DEV_REUSED"
    assert obj._register() is True

    payload = mock_post.call_args.kwargs["data"]
    assert '"device_id": "DEV_REUSED"' in payload


@pytest.mark.skipif(not CRYPTOGRAPHY_AVAILABLE, reason="Requires cryptography")
def test_plugin_matrix_e2ee_account_bad_store_data():
    """Corrupt e2ee_account in store is silently ignored."""
    obj = NotifyMatrix(
        host="h",
        user="u",
        password="pass",
        targets=["#r"],
        e2ee=True,
    )
    obj.store.set("e2ee_account", {"ik": "NOTVALID", "sk": "NOTVALID"})

    # Re-instantiate with the same store to trigger the restore path
    obj2 = NotifyMatrix(
        host="h",
        user="u",
        password="pass",
        targets=["#r"],
        e2ee=True,
        store=obj.store,
    )
    # Bad data is suppressed; account is None until setup is called
    assert obj2._e2ee_account is None


def test_plugin_matrix_del_suppresses_logout_exceptions():
    """__del__ should never raise if logout fails during GC cleanup."""
    obj = NotifyMatrix(host="h", user="u", password="pass", targets=["#r"])
    obj.access_token = "tok"

    with mock.patch.object(obj, "_logout", side_effect=RuntimeError("boom")):
        obj.__del__()


# ---------------------------------------------------------------------------
# DM / direct-message tests
# ---------------------------------------------------------------------------


def test_plugin_matrix_dm_target_separation():
    """@user targets are separated from room targets at init time."""
    obj = NotifyMatrix(
        host="h",
        user="u",
        password="pass",
        targets=["#general", "@alice", "@bob:other.com", "!room:h"],
        discovery=False,
    )
    assert "#general" in obj.rooms
    assert "!room:h" in obj.rooms
    assert "@alice" in obj.users
    assert "@bob:other.com" in obj.users
    assert len(obj.rooms) == 2
    assert len(obj.users) == 2

    # __len__ accounts for both rooms and users
    assert len(obj) == 4


def test_plugin_matrix_dm_url_roundtrip():
    """@user targets survive a url() -> parse_url() -> NotifyMatrix cycle."""
    obj = NotifyMatrix(
        host="h",
        user="u",
        password="pass",
        targets=["#room", "@alice"],
        discovery=False,
        secure=True,
    )
    url = obj.url()
    # @ is URL-encoded to %40 inside the path segment
    assert "%40alice" in url

    result = NotifyMatrix.parse_url(url)
    assert result is not None
    obj2 = NotifyMatrix(**result)
    assert "@alice" in obj2.users
    assert any("room" in r for r in obj2.rooms)


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_matrix_dm_room_find_cached(mock_post, mock_get, mock_put):
    """_dm_room_find_or_create returns cached room ID without HTTP calls."""

    def _mk_resp(d, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = dumps(d).encode()
        return r

    mock_post.return_value = _mk_resp({})
    mock_get.return_value = _mk_resp({})
    mock_put.return_value = _mk_resp({})

    obj = NotifyMatrix(
        host="h",
        user="u",
        password="pass",
        targets=["@alice"],
        discovery=False,
    )
    obj.access_token = "tok"
    obj.user_id = "@u:h"
    obj.home_server = "h"

    # Seed the cache
    obj.store.set("dm_room_@alice:h", "!dm123:h")

    room_id = obj._dm_room_find_or_create("@alice")
    assert room_id == "!dm123:h"
    # No HTTP calls should have been made
    assert mock_get.call_count == 0
    assert mock_post.call_count == 0


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_matrix_dm_room_find_via_mdirect(mock_post, mock_get, mock_put):
    """_dm_room_find_or_create finds existing room from m.direct data."""

    def _mk_resp(d, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = dumps(d).encode()
        return r

    mdirect = {"@alice:h": ["!existing_dm:h"]}
    mock_get.return_value = _mk_resp(mdirect)
    mock_post.return_value = _mk_resp({})
    mock_put.return_value = _mk_resp({})

    obj = NotifyMatrix(
        host="h",
        user="u",
        password="pass",
        targets=["@alice"],
        discovery=False,
    )
    obj.access_token = "tok"
    obj.user_id = "@u:h"
    obj.home_server = "h"

    room_id = obj._dm_room_find_or_create("@alice")
    assert room_id == "!existing_dm:h"

    # Result is now cached
    assert obj.store.get("dm_room_@alice:h") == "!existing_dm:h"

    # No createRoom POST should have been made
    assert mock_post.call_count == 0


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_matrix_dm_room_create_new(mock_post, mock_get, mock_put):
    """_dm_room_find_or_create creates a new room when none exists."""

    def _mk_resp(d, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = dumps(d).encode()
        return r

    # GET m.direct returns empty (no existing DM for alice)
    mock_get.return_value = _mk_resp({})
    # First POST = createRoom, second = (not called)
    mock_post.return_value = _mk_resp({"room_id": "!new_dm:h"})
    mock_put.return_value = _mk_resp({})

    obj = NotifyMatrix(
        host="h",
        user="u",
        password="pass",
        targets=["@alice"],
        discovery=False,
    )
    obj.access_token = "tok"
    obj.user_id = "@u:h"
    obj.home_server = "h"

    room_id = obj._dm_room_find_or_create("@alice")
    assert room_id == "!new_dm:h"

    # Should be cached
    assert obj.store.get("dm_room_@alice:h") == "!new_dm:h"

    # m.direct PUT should have been called to update the mapping
    assert mock_put.call_count >= 1


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_matrix_dm_room_create_failure(mock_post, mock_get, mock_put):
    """_dm_room_find_or_create returns None when createRoom fails."""

    def _mk_resp(d, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = dumps(d).encode()
        return r

    mock_get.return_value = _mk_resp({})
    mock_post.return_value = _mk_resp(
        {"errcode": "M_FORBIDDEN"}, code=requests.codes.forbidden
    )
    mock_put.return_value = _mk_resp({})

    obj = NotifyMatrix(
        host="h",
        user="u",
        password="pass",
        targets=["@alice"],
        discovery=False,
    )
    obj.access_token = "tok"
    obj.user_id = "@u:h"
    obj.home_server = "h"

    assert obj._dm_room_find_or_create("@alice") is None


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_matrix_dm_room_create_no_room_id(
    mock_post, mock_get, mock_put
):
    """_dm_room_find_or_create returns None when createRoom omits room_id."""

    def _mk_resp(d, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = dumps(d).encode()
        return r

    mock_get.return_value = _mk_resp({})
    # createRoom returns 200 but no room_id key
    mock_post.return_value = _mk_resp({})
    mock_put.return_value = _mk_resp({})

    obj = NotifyMatrix(
        host="h",
        user="u",
        password="pass",
        targets=["@alice"],
        discovery=False,
    )
    obj.access_token = "tok"
    obj.user_id = "@u:h"
    obj.home_server = "h"

    assert obj._dm_room_find_or_create("@alice") is None


def test_plugin_matrix_dm_invalid_user():
    """_dm_room_find_or_create returns None for a malformed user target."""
    obj = NotifyMatrix(
        host="h",
        user="u",
        password="pass",
        targets=["#r"],
        discovery=False,
    )
    obj.access_token = "tok"
    obj.user_id = "@u:h"
    obj.home_server = "h"

    # No @ prefix -- not a valid user target
    assert obj._dm_room_find_or_create("notauser") is None


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_matrix_dm_send_notification(mock_post, mock_get, mock_put):
    """Sending to @user target resolves DM room and delivers message."""

    def _mk_resp(d, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = dumps(d).encode()
        return r

    mock_get.return_value = _mk_resp({})
    mock_put.return_value = _mk_resp({})
    mock_post.side_effect = [
        _mk_resp(
            {"access_token": "tok", "user_id": "@u:h", "home_server": "h"}
        ),  # login
        _mk_resp({"room_id": "!new_dm:h"}),  # createRoom
        _mk_resp({}),  # logout
    ]

    obj = NotifyMatrix(
        host="h",
        user="u",
        password="pass",
        targets=["@alice"],
        discovery=False,
        e2ee=False,
    )

    # Pre-seed DM room so _room_join succeeds
    def _join_side(*a, **kw):
        return "!new_dm:h"

    with (
        mock.patch.object(obj, "_room_join", side_effect=_join_side),
        mock.patch.object(
            obj, "_dm_room_find_or_create", return_value="!new_dm:h"
        ),
    ):
        assert obj.send(body="hello DM") is True


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_matrix_dm_only_users_no_rooms_skips_joined(
    mock_post, mock_get, mock_put
):
    """When only @user targets are present, _joined_rooms is not queried."""

    def _mk_resp(d, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = dumps(d).encode()
        return r

    mock_get.return_value = _mk_resp({})
    mock_put.return_value = _mk_resp({})
    mock_post.side_effect = [
        _mk_resp(
            {"access_token": "tok", "user_id": "@u:h", "home_server": "h"}
        ),  # login
        _mk_resp({}),  # logout
    ]

    obj = NotifyMatrix(
        host="h",
        user="u",
        password="pass",
        targets=["@alice"],
        discovery=False,
        e2ee=False,
    )

    with (
        mock.patch.object(obj, "_joined_rooms", return_value=[]) as mock_jr,
        mock.patch.object(obj, "_dm_room_find_or_create", return_value=None),
    ):
        obj.send(body="hi")
        # _joined_rooms must NOT have been called
        assert mock_jr.call_count == 0


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_matrix_dm_room_create_mdirect_get_fails(
    mock_post, mock_get, mock_put
):
    """_dm_room_find_or_create still creates room if m.direct GET fails."""

    def _mk_resp(d, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = dumps(d).encode()
        return r

    # GET fails (404)
    mock_get.return_value = _mk_resp({}, code=404)
    mock_post.return_value = _mk_resp({"room_id": "!fallback:h"})
    mock_put.return_value = _mk_resp({})

    obj = NotifyMatrix(
        host="h",
        user="u",
        password="pass",
        targets=["@alice"],
        discovery=False,
    )
    obj.access_token = "tok"
    obj.user_id = "@u:h"
    obj.home_server = "h"

    room_id = obj._dm_room_find_or_create("@alice")
    assert room_id == "!fallback:h"


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_matrix_dm_room_create_no_user_id(
    mock_post, mock_get, mock_put
):
    """_dm_room_find_or_create creates room when user_id is None (skips
    the m.direct GET and PUT)."""

    def _mk_resp(d, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = dumps(d).encode()
        return r

    mock_get.return_value = _mk_resp({})
    mock_post.return_value = _mk_resp({"room_id": "!nodm:h"})
    mock_put.return_value = _mk_resp({})

    obj = NotifyMatrix(
        host="h",
        user="u",
        password="pass",
        targets=["@alice"],
        discovery=False,
    )
    obj.access_token = "tok"
    # user_id intentionally left as None so the m.direct branch is skipped
    obj.home_server = "h"

    room_id = obj._dm_room_find_or_create("@alice")
    assert room_id == "!nodm:h"
    # No GET and no PUT for m.direct since user_id is None
    assert mock_get.call_count == 0


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_matrix_dm_room_create_e2ee(mock_post, mock_get, mock_put):
    """_dm_room_find_or_create with e2ee=True/secure=True embeds
    initial_state and pre-seeds the room encryption cache."""
    from apprise.plugins.matrix.base import MATRIX_E2EE_SUPPORT

    if not MATRIX_E2EE_SUPPORT:
        pytest.skip("cryptography package not installed")

    def _mk_resp(d, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = dumps(d).encode()
        return r

    mock_get.return_value = _mk_resp({})
    mock_post.return_value = _mk_resp({"room_id": "!dm_e2ee:h"})
    mock_put.return_value = _mk_resp({})

    obj = NotifyMatrix(
        host="h",
        user="u",
        password="pass",
        targets=["@alice"],
        e2ee=True,
        secure=True,
        discovery=False,
    )
    obj.access_token = "tok"
    obj.user_id = "@u:h"
    obj.home_server = "h"

    captured_payloads = []
    _orig_fetch = obj._fetch

    def _capture_fetch(path, payload=None, **kw):
        if path == "/createRoom":
            captured_payloads.append(payload or {})
        return _orig_fetch(path, payload=payload, **kw)

    obj._fetch = _capture_fetch

    room_id = obj._dm_room_find_or_create("@alice")
    assert room_id == "!dm_e2ee:h"

    # Verify initial_state was sent with m.room.encryption
    assert len(captured_payloads) == 1
    init_state = captured_payloads[0].get("initial_state", [])
    assert any(s.get("type") == "m.room.encryption" for s in init_state)

    # Room encryption cache must be pre-seeded
    assert obj.store.get("e2ee_room_enc_!dm_e2ee:h") is True


# ---------------------------------------------------------------------------
# home_server recovery-from-user_id coverage tests
# ---------------------------------------------------------------------------


def test_plugin_matrix_init_recovers_home_server_from_user_id(tmpdir):
    """__init__ extracts home_server from a cached user_id when home_server
    was not stored (older cache entries that predate the home_server field)."""
    # A disk-backed asset ensures two separate NotifyMatrix instances that
    # share the same url_id() also share the same persistent store file.
    asset = AppriseAsset(
        storage_mode=PersistentStoreMode.FLUSH,
        storage_path=str(tmpdir),
    )

    # First instance: simulate a login that wrote user_id/access_token but
    # did NOT write home_server (older Apprise behaviour).
    obj = NotifyMatrix(
        host="h", user="u", password="pass", targets=["#r"], asset=asset
    )
    obj.store.set("user_id", "@u:recovered.com")
    obj.store.set("access_token", "tok")
    # Flush to disk before the second instance reads it.
    obj.store.flush()

    # Second instance with the same credentials (same url_id) reads the store.
    # The recovery branch (lines 506-509) should derive home_server from
    # the stored user_id.
    obj2 = NotifyMatrix(
        host="h", user="u", password="pass", targets=["#r"], asset=asset
    )
    assert obj2.home_server == "recovered.com"


def test_plugin_matrix_init_no_home_server_recovery_without_colon(tmpdir):
    """__init__ leaves home_server as None when the cached user_id has no
    colon -- the recovery split yields a single part and the assignment is
    skipped (covers the False branch of line 508)."""
    asset = AppriseAsset(
        storage_mode=PersistentStoreMode.FLUSH,
        storage_path=str(tmpdir),
    )

    obj = NotifyMatrix(
        host="h", user="u", password="pass", targets=["#r"], asset=asset
    )
    # user_id with no colon -- split(":", 1) produces only one element.
    obj.store.set("user_id", "nocolon")
    obj.store.set("access_token", "tok")
    obj.store.flush()

    obj2 = NotifyMatrix(
        host="h", user="u", password="pass", targets=["#r"], asset=asset
    )
    # No colon in user_id means home_server cannot be extracted.
    assert obj2.home_server is None


@mock.patch("requests.put")
@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_matrix_whoami_recovers_home_server_from_user_id(
    mock_post, mock_get, mock_put
):
    """_whoami() extracts home_server from user_id when the server does not
    return a home_server field and self.home_server is unset."""
    r = mock.Mock()
    r.status_code = requests.codes.ok
    r.content = dumps(
        {"user_id": "@u:whoami.example.com", "device_id": "DEVX"}
    ).encode()
    mock_get.return_value = r

    obj = NotifyMatrix(host="h", user="u", password="pass", discovery=False)
    obj.access_token = "tok"
    obj.home_server = None

    assert obj._whoami() is True
    assert obj.home_server == "whoami.example.com"


def test_plugin_matrix_room_create_recovers_home_server_from_user_id():
    """_room_create() falls back to extracting home_server from user_id when
    both the room alias and self.home_server carry no homeserver part."""
    obj = NotifyMatrix(host="h", user="u", password="pass", targets=["#r"])
    obj.access_token = "tok"
    obj.home_server = None
    obj.user_id = "@u:create.example.com"

    # Capture the /createRoom POST so we can verify the room name used.
    captured = {}

    def _fake_fetch(path, payload=None, **kw):
        if path == "/createRoom":
            captured["payload"] = payload
            return True, {"room_id": "!newroom:create.example.com"}, 200
        return False, {}, 404

    with mock.patch.object(obj, "_fetch", side_effect=_fake_fetch):
        room_id = obj._room_create("#bare_alias")

    assert room_id == "!newroom:create.example.com"
    # The room name in the request must use the homeserver from user_id.
    assert captured["payload"]["room_alias_name"] == "bare_alias"


def test_plugin_matrix_room_create_returns_none_without_home_server():
    """_room_create() returns None when neither the alias, self.home_server,
    nor self.user_id can supply a homeserver component."""
    obj = NotifyMatrix(host="h", user="u", password="pass", targets=["#r"])
    obj.access_token = "tok"
    obj.home_server = None
    # user_id with no colon -> extraction yields nothing.
    obj.user_id = "nocolon"

    result = obj._room_create("#bare_alias")
    assert result is None


def test_plugin_matrix_room_id_recovers_home_server_from_user_id():
    """_room_id() falls back to extracting home_server from user_id when both
    the alias and self.home_server carry no homeserver part."""
    obj = NotifyMatrix(host="h", user="u", password="pass", targets=["#r"])
    obj.access_token = "tok"
    obj.home_server = None
    obj.user_id = "@u:lookup.example.com"

    def _fake_fetch(path, payload=None, **kw):
        return True, {"room_id": "!found:lookup.example.com"}, 200

    with mock.patch.object(obj, "_fetch", side_effect=_fake_fetch):
        room_id = obj._room_id("#bare_alias")

    assert room_id == "!found:lookup.example.com"


def test_plugin_matrix_room_id_returns_none_without_home_server():
    """_room_id() returns None when neither the alias, self.home_server,
    nor self.user_id can supply a homeserver component."""
    obj = NotifyMatrix(host="h", user="u", password="pass", targets=["#r"])
    obj.access_token = "tok"
    obj.home_server = None
    obj.user_id = "nocolon"

    result = obj._room_id("#bare_alias")
    assert result is None
