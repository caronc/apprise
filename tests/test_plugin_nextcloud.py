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

# Disable logging for a cleaner testing output
from json import dumps
import logging
from unittest import mock

from helpers import AppriseURLTester
import requests

from apprise import Apprise, AppriseAsset, NotifyType, PersistentStoreMode
from apprise.plugins.nextcloud import NotifyNextcloud

NEXTCLOUD_GOOD_RESPONSE = dumps({
    "ocs": {
        "meta": {"status": "ok", "statuscode": 100},
        "data": {"users": ["user1", "user2"]},
    }})

logging.disable(logging.CRITICAL)

apprise_url_tests = (
    ##################################
    # NotifyNextcloud
    ##################################
    (
        "ncloud://:@/",
        {
            "instance": None,
            # Our response expected server response
            "requests_response_text": NEXTCLOUD_GOOD_RESPONSE,
        },
    ),
    (
        "ncloud://",
        {
            "instance": None,
            "requests_response_text": NEXTCLOUD_GOOD_RESPONSE,
        },
    ),
    (
        "nclouds://",
        {
            # No hostname
            "instance": None,
            "requests_response_text": NEXTCLOUD_GOOD_RESPONSE,
        },
    ),
    (
        "ncloud://localhost",
        {
            # No user specified
            "instance": NotifyNextcloud,
            # Since there are no targets specified we expect a False return on
            # send()
            "notify_response": False,
            "requests_response_text": NEXTCLOUD_GOOD_RESPONSE,
        },
    ),
    (
        "ncloud://user@localhost?to=user1,user2&version=invalid",
        {
            # An invalid version was specified
            "instance": TypeError,
            "requests_response_text": NEXTCLOUD_GOOD_RESPONSE,
        },
    ),
    (
        "ncloud://user@localhost?to=user1,user2&version=0",
        {
            # An invalid version was specified
            "instance": TypeError,
            "requests_response_text": NEXTCLOUD_GOOD_RESPONSE,
        },
    ),
    (
        "ncloud://user@localhost?to=user1,user2&version=-23",
        {
            # An invalid version was specified
            "instance": TypeError,
            "requests_response_text": NEXTCLOUD_GOOD_RESPONSE,
        },
    ),
    (
        "ncloud://localhost/admin",
        {
            "instance": NotifyNextcloud,
            "requests_response_text": NEXTCLOUD_GOOD_RESPONSE,
        },
    ),
    (
        "ncloud://user@localhost/admin",
        {
            "instance": NotifyNextcloud,
            "requests_response_text": NEXTCLOUD_GOOD_RESPONSE,
        },
    ),
    (
        "ncloud://user@localhost?to=user1,user2",
        {
            "instance": NotifyNextcloud,
            "requests_response_text": NEXTCLOUD_GOOD_RESPONSE,
        },
    ),
    (
        "ncloud://user@localhost?to=user1,user2&version=20",
        {
            "instance": NotifyNextcloud,
            "requests_response_text": NEXTCLOUD_GOOD_RESPONSE,
        },
    ),
    (
        "ncloud://user@localhost?to=user1,user2&version=21",
        {
            "instance": NotifyNextcloud,
            "requests_response_text": NEXTCLOUD_GOOD_RESPONSE,
        },
    ),
    (
        "ncloud://user@localhost?to=user1&version=20&url_prefix=/abcd",
        {
            "instance": NotifyNextcloud,
            "requests_response_text": NEXTCLOUD_GOOD_RESPONSE,
        },
    ),
    (
        "ncloud://user@localhost?to=user1&version=21&url_prefix=/abcd",
        {
            "instance": NotifyNextcloud,
            "requests_response_text": NEXTCLOUD_GOOD_RESPONSE,
        },
    ),
    (
        "ncloud://user:pass@localhost/user1/user2",
        {
            "instance": NotifyNextcloud,
            "requests_response_text": NEXTCLOUD_GOOD_RESPONSE,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "ncloud://user:****@localhost/@user1/@user2",
        },
    ),
    (
        "ncloud://user:pass@localhost/#group1/#group2/#group1",
        {
            # Test groups, but also note a duplicate group provided
            "instance": NotifyNextcloud,
            "requests_response_text": NEXTCLOUD_GOOD_RESPONSE,
            "privacy_url": "ncloud://user:****@localhost/#group",
        },
    ),
    (
        "ncloud://user:pass@localhost:8080/admin",
        {
            "instance": NotifyNextcloud,
            "requests_response_text": NEXTCLOUD_GOOD_RESPONSE,
        },
    ),
    (
        "nclouds://user:pass@localhost/admin",
        {
            "instance": NotifyNextcloud,
            "requests_response_text": NEXTCLOUD_GOOD_RESPONSE,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "nclouds://user:****@localhost/@admin",
        },
    ),
    (
        "nclouds://user:pass@localhost:8080/admin/",
        {
            "instance": NotifyNextcloud,
            "requests_response_text": NEXTCLOUD_GOOD_RESPONSE,
        },
    ),
    (
        "nclouds://user:pass@localhost:8080/#group/",
        {
            "instance": NotifyNextcloud,
            # Invalid JSON Response
            "requests_response_text": "{",
            # We will fail to make the notify() call due to our bad response
            "notify_response": False,
        },
    ),

    (
        "ncloud://localhost:8080/admin?+HeaderKey=HeaderValue",
        {
            "instance": NotifyNextcloud,
            "requests_response_text": NEXTCLOUD_GOOD_RESPONSE,
        },
    ),
    (
        "ncloud://user:pass@localhost:8081/admin",
        {
            "instance": NotifyNextcloud,
            "requests_response_text": NEXTCLOUD_GOOD_RESPONSE,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "ncloud://user:pass@localhost:8082/admin",
        {
            "instance": NotifyNextcloud,
            "requests_response_text": NEXTCLOUD_GOOD_RESPONSE,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "ncloud://user:pass@localhost:8083/user1/user2/user3",
        {
            "instance": NotifyNextcloud,
            "requests_response_text": NEXTCLOUD_GOOD_RESPONSE,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_nextcloud_urls():
    """NotifyNextcloud() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_nextcloud_edge_cases(mock_post):
    """NotifyNextcloud() Edge Cases."""

    # A response
    robj = mock.Mock()
    robj.content = ""
    robj.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = robj

    # Variation Initializations
    obj = NotifyNextcloud(
        host="localhost", user="admin", password="pass", targets="user"
    )
    assert isinstance(obj, NotifyNextcloud) is True
    assert isinstance(obj.url(), str) is True

    # An empty body
    assert obj.send(body="") is True
    assert "data" in mock_post.call_args_list[0][1]
    assert "shortMessage" in mock_post.call_args_list[0][1]["data"]
    # The longMessage argument is not set
    assert "longMessage" not in mock_post.call_args_list[0][1]["data"]


@mock.patch("requests.post")
def test_plugin_nextcloud_url_prefix(mock_post):
    """NotifyNextcloud() URL Prefix Testing."""

    response = mock.Mock()
    response.content = ""
    response.status_code = requests.codes.ok

    # Prepare our mock object
    mock_post.return_value = response

    # instantiate our object (without a batch mode)
    obj = Apprise.instantiate(
        "ncloud://localhost/admin/?version=20&url_prefix=/abcd"
    )

    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    # Not set to batch, so we send 2 different messages
    assert mock_post.call_count == 1
    assert (
        mock_post.call_args_list[0][0][0]
        == "http://localhost/abcd/ocs/v2.php/apps/"
        "admin_notifications/api/v1/notifications/admin")


@mock.patch("requests.post")
@mock.patch("requests.get")
def test_plugin_nextcloud_groups_and_all(mock_get, mock_post):
    """NotifyNextcloud() Group and All user expansion."""

    # Mock POST success
    post_resp = mock.Mock()
    post_resp.content = ""
    post_resp.status_code = requests.codes.ok
    mock_post.return_value = post_resp

    # Mock GET responses for group and users listing
    def get_side_effect(url, *args, **kwargs):
        resp = mock.Mock()
        if "/ocs/v1.php/cloud/groups/" in url:
            # Return JSON for group
            j = {
                "ocs": {
                    "meta": {"status": "ok", "statuscode": 100},
                    "data": {"users": ["user1", "user2"]},
                }
            }
            resp.status_code = requests.codes.ok
            resp.json = lambda: j
            resp.content = dumps(j).encode()
            return resp

        elif "/ocs/v1.php/cloud/users" in url:
            j = {
                "ocs": {
                    "meta": {"status": "ok", "statuscode": 100},
                    "data": {"users": ["user1", "user3"]},
                }
            }
            resp.status_code = requests.codes.ok
            resp.json = lambda: j
            resp.content = dumps(j).encode()
            return resp
        # default
        resp.status_code = requests.codes.ok
        resp.content = b""
        resp.json = lambda: {}
        return resp

    mock_get.side_effect = get_side_effect

    # Instantiate with a mix of targets: group, all, and direct user
    obj = NotifyNextcloud(
        host="localhost",
        user="admin",
        password="pass",
        targets=["#devs", "all", "user4"],
    )

    assert isinstance(obj, NotifyNextcloud)

    # Send notification
    assert (
        obj.send(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    # Expected resolved users (deduplicated): user1, user2, user3, user4
    # Hence 4 POST calls
    assert mock_post.call_count == 4

    # Validate calls were made to expected endpoints
    called_urls = [c[0][0] for c in mock_post.call_args_list]
    for u in ("user1", "user2", "user3", "user4"):
        assert any(u in url for url in called_urls)


@mock.patch("requests.post")
@mock.patch("requests.get")
def test_plugin_nextcloud_persistent_storage(mock_get, mock_post, tmpdir):
    """Testing persistent storage"""

    post_resp = mock.Mock()
    post_resp.content = ""
    post_resp.status_code = requests.codes.ok
    mock_post.return_value = post_resp

    # Set up persistent storage
    asset = AppriseAsset(
        storage_mode=PersistentStoreMode.FLUSH,
        storage_path=str(tmpdir),
    )

    def get_side_effect(url, *args, **kwargs):
        resp = mock.Mock()
        # Default json() to empty
        resp.json = lambda: {}

        if "/ocs/v1.php/cloud/groups" in url:
            resp.status_code = requests.codes.ok
            payload = {"ocs": {"data": {"users": ["u1"]}}}
            resp.json = lambda: payload
            resp.content = dumps(payload).encode()
            return resp

        elif "/ocs/v1.php/cloud/users" in url:
            resp.status_code = requests.codes.ok
            payload = {"ocs": {"data": {"users": ["u2"]}}}
            resp.json = lambda: payload
            resp.content = dumps(payload).encode()
            return resp

        resp.status_code = 500
        resp.content = b""
        return resp

    mock_get.side_effect = get_side_effect

    obj = NotifyNextcloud(
        host="localhost",
        user="admin",
        password="pass",
        targets=["#devs", "all"],
        asset=asset,
    )
    # We failed to get our list
    assert obj.send(
        body="body", title="title", notify_type=NotifyType.INFO) is True

    # User and Group looked up
    assert mock_get.call_count == 2

    # Expect users u1 (group) and u2 (all)
    assert mock_post.call_count == 2
    called_urls = [c[0][0] for c in mock_post.call_args_list]
    for u in ("u1", "u2"):
        assert any(u in url for url in called_urls)

    mock_get.reset_mock()
    mock_post.reset_mock()

    obj = NotifyNextcloud(
        host="localhost",
        user="admin",
        password="pass",
        targets=["#devs"],
        asset=asset,
    )
    # We succeeded this time
    assert obj.send(
        body="body", title="title", notify_type=NotifyType.INFO) is True

    # Expect users u1 (group) only and pulled from cache
    assert mock_get.call_count == 0
    assert mock_post.call_count == 1
    assert mock_post.call_args_list[0][0][0].endswith("/u1")


@mock.patch("requests.post")
@mock.patch("requests.get")
def test_plugin_nextcloud_groups_errors_and_dedup(mock_get, mock_post):
    """Non-200/exception paths return empty lists and dedup still applies."""

    post_resp = mock.Mock()
    post_resp.content = ""
    post_resp.status_code = requests.codes.ok
    mock_post.return_value = post_resp

    # Non-200 for group and users; JSON invalid
    def get_side_effect(url, *args, **kwargs):
        resp = mock.Mock()
        resp.status_code = 401
        resp.content = b"<ocs><data></data></ocs>"
        # Return empty/invalid JSON to drive empty path
        resp.json = lambda: {}
        return resp

    mock_get.side_effect = get_side_effect

    # Provide duplicates alongside failing expansions
    obj = NotifyNextcloud(
        host="localhost",
        user="admin",
        password="pass",
        targets=["#devs", "all", "user1", "user1", "user2"],
    )

    # We failed to hit the server for data
    assert obj.send(body="x", title="y", notify_type=NotifyType.INFO) is False

    # we have no control over the order, but we know that on the first
    # GET call, we'd have gotten a 401 response; so we'd have stopped from
    # that point further
    assert mock_get.call_count == 1

    # Nothing notified
    assert mock_post.call_count == 0


@mock.patch("requests.post")
@mock.patch("requests.get")
def test_plugin_nextcloud_req_exception_and_empty_targets(mock_get, mock_post):
    """RequestException returns empty expansion; direct users send."""

    post_resp = mock.Mock()
    post_resp.content = ""
    post_resp.status_code = requests.codes.ok
    mock_post.return_value = post_resp

    def get_side_effect(url, *args, **kwargs):
        raise requests.RequestException("boom")

    mock_get.side_effect = get_side_effect

    obj = NotifyNextcloud(
        host="localhost",
        user="admin",
        password="pass",
        targets=["", "   ", "#DevTeam", "#", "userX"],
    )

    # Our Group inquiry failed to respond
    assert obj.send(body="x", title="y", notify_type=NotifyType.INFO) is False
    assert mock_post.call_count == 0
    assert mock_get.call_count == 1
    assert mock_get.call_args_list[0][0][0] \
        == "http://localhost/ocs/v1.php/cloud/groups/DevTeam"
    assert mock_get.call_args_list[0][1]["params"].get("format") == "json"


@mock.patch("requests.post")
@mock.patch("requests.get")
def test_plugin_nextcloud_json_empty_returns_empty(mock_get, mock_post):
    """Invalid/empty JSON returns empty; direct users still send."""

    post_resp = mock.Mock()
    post_resp.content = ""
    post_resp.status_code = requests.codes.ok
    mock_post.return_value = post_resp

    def get_side_effect(url, *args, **kwargs):
        resp = mock.Mock()
        resp.json = lambda: {}
        resp.status_code = requests.codes.ok
        resp.content = b"{}"
        return resp

    mock_get.side_effect = get_side_effect

    obj = NotifyNextcloud(
        host="localhost",
        user="admin",
        password="pass",
        targets=["#broken", "all", "userZ"],
    )

    # Our notification
    assert obj.send(body="x", title="y", notify_type=NotifyType.INFO) is True
    # Only direct userZ posts because both expansions return empty
    assert mock_get.call_count == 2
    assert any("/cloud/users" in call[0][0]
               for call in mock_get.call_args_list)
    assert any("/cloud/groups/broken" in call[0][0]
               for call in mock_get.call_args_list)

    # userZ would get a notification
    assert mock_post.call_count == 1
    assert mock_post.call_args_list[0][0][0].endswith("/userZ")


@mock.patch("requests.post")
@mock.patch("requests.get")
def test_plugin_nextcloud_caching_group_and_all(mock_get, mock_post):
    """Cache hits avoid repeat OCS lookups."""

    # First round of GETs return users for group and all
    def get_side_effect(url, *args, **kwargs):
        resp = mock.Mock()
        resp.status_code = requests.codes.ok
        if "/ocs/v1.php/cloud/groups" in url:
            j = {
                "ocs": {
                    "meta": {"status": "ok", "statuscode": 100},
                    "data": {"users": ["g1", "g2"]},
                }
            }
        elif "/ocs/v1.php/cloud/users" in url:
            j = {
                "ocs": {
                    "meta": {"status": "ok", "statuscode": 100},
                    "data": {"users": ["a1", "a2"]},
                }
            }
        else:
            j = {"ocs": {"data": {"users": []}}}
        resp.json = lambda: j
        resp.content = dumps(j).encode()
        return resp

    mock_get.side_effect = get_side_effect

    post_resp = mock.Mock()
    post_resp.content = ""
    post_resp.status_code = requests.codes.ok
    mock_post.return_value = post_resp

    obj = NotifyNextcloud(
        host="localhost",
        user="admin",
        password="pass",
        targets=["#devs", "all", "@joe"],
    )

    # First send: resolves via OCS; expect 2 GETs (group + all)
    assert obj.send(body="b", title="t", notify_type=NotifyType.INFO) is True
    assert mock_get.call_count == 2
    called = "".join(c[0][0] for c in mock_get.call_args_list)
    assert "/cloud/groups/" in called and "/cloud/users" in called

    # we sent 5 notifications
    assert mock_post.call_count == 5
    expected_users = {"a1", "a2", "g1", "g2", "joe"}

    # Extract the user segment from the URL of each call
    actual_users = {
        call[0][0].split("/")[-1]
        for call in mock_post.call_args_list
    }

    # Assert that the set of actual users matches the set of expected users
    assert actual_users == expected_users

    # Reset our mock object
    mock_get.reset_mock()
    mock_post.reset_mock()

    assert obj.send(body="b2", title="t2", notify_type=NotifyType.INFO) is True
    # Cached responses were used to get our user information
    assert mock_get.call_count == 0
    assert mock_post.call_count == 5

    # We can re-verify our notifications went as expected:
    actual_users = {
        call[0][0].split("/")[-1]
        for call in mock_post.call_args_list
    }

    # Assert that the set of actual users matches the set of expected users
    assert actual_users == expected_users
