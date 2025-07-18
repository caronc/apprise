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
import logging
from unittest import mock

from helpers import AppriseURLTester
import requests

from apprise import Apprise, NotifyType
from apprise.plugins.nextcloudtalk import NotifyNextcloudTalk

logging.disable(logging.CRITICAL)

apprise_url_tests = (
    ##################################
    # NotifyNextcloudTalk
    ##################################
    (
        "nctalk://:@/",
        {
            "instance": None,
        },
    ),
    (
        "nctalk://",
        {
            "instance": None,
        },
    ),
    (
        "nctalks://",
        {
            # No hostname
            "instance": None,
        },
    ),
    (
        "nctalk://localhost",
        {
            # No user and password and roomid specified
            "instance": TypeError,
        },
    ),
    (
        "nctalk://localhost/roomid",
        {
            # No user and password specified
            "instance": TypeError,
        },
    ),
    (
        "nctalk://user@localhost/roomid",
        {
            # No password specified
            "instance": TypeError,
        },
    ),
    (
        "nctalk://user:pass@localhost",
        {
            # No roomid specified
            "instance": NotifyNextcloudTalk,
            # Since there are no targets specified we expect a False return on
            # send()
            "notify_response": False,
        },
    ),
    (
        "nctalk://user:pass@localhost/roomid1/roomid2",
        {
            "instance": NotifyNextcloudTalk,
            "requests_response_code": requests.codes.created,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "nctalk://user:****@localhost/roomid1/roomid2",
        },
    ),
    (
        "nctalk://user:pass@localhost:8080/roomid",
        {
            "instance": NotifyNextcloudTalk,
            "requests_response_code": requests.codes.created,
        },
    ),
    (
        "nctalk://user:pass@localhost:8080/roomid?url_prefix=/prefix",
        {
            "instance": NotifyNextcloudTalk,
            "requests_response_code": requests.codes.created,
        },
    ),
    (
        "nctalks://user:pass@localhost/roomid",
        {
            "instance": NotifyNextcloudTalk,
            "requests_response_code": requests.codes.created,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "nctalks://user:****@localhost/roomid",
        },
    ),
    (
        "nctalks://user:pass@localhost:8080/roomid/",
        {
            "instance": NotifyNextcloudTalk,
            "requests_response_code": requests.codes.created,
        },
    ),
    (
        "nctalk://user:pass@localhost:8080/roomid?+HeaderKey=HeaderValue",
        {
            "instance": NotifyNextcloudTalk,
            "requests_response_code": requests.codes.created,
        },
    ),
    (
        "nctalk://user:pass@localhost:8081/roomid",
        {
            "instance": NotifyNextcloudTalk,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "nctalk://user:pass@localhost:8082/roomid",
        {
            "instance": NotifyNextcloudTalk,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "nctalk://user:pass@localhost:8083/roomid1/roomid2/roomid3",
        {
            "instance": NotifyNextcloudTalk,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_nextcloudtalk_urls():
    """NotifyNextcloudTalk() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_nextcloudtalk_edge_cases(mock_post):
    """NotifyNextcloudTalk() Edge Cases."""

    # A response
    robj = mock.Mock()
    robj.content = ""
    robj.status_code = requests.codes.created

    # Prepare Mock
    mock_post.return_value = robj

    # Variation Initializations
    obj = NotifyNextcloudTalk(
        host="localhost", user="admin", password="pass", targets="roomid"
    )
    assert isinstance(obj, NotifyNextcloudTalk) is True
    assert isinstance(obj.url(), str) is True

    # An empty body
    assert obj.send(body="") is True
    assert "data" in mock_post.call_args_list[0][1]
    assert "message" in mock_post.call_args_list[0][1]["data"]


@mock.patch("requests.post")
def test_plugin_nextcloud_talk_url_prefix(mock_post):
    """NotifyNextcloudTalk() URL Prefix Testing."""

    response = mock.Mock()
    response.content = ""
    response.status_code = requests.codes.created

    # Prepare our mock object
    mock_post.return_value = response

    # instantiate our object (without a batch mode)
    obj = Apprise.instantiate(
        "nctalk://user:pass@localhost/admin/?url_prefix=/abcd"
    )

    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    # Not set to batch, so we send 2 different messages
    assert mock_post.call_count == 1
    assert (
        mock_post.call_args_list[0][0][0]
        == "http://localhost/abcd/ocs/v2.php/apps/spreed/api/v1/chat/admin"
    )

    mock_post.reset_mock()

    # instantiate our object (without a batch mode)
    obj = Apprise.instantiate(
        "nctalk://user:pass@localhost/admin/?url_prefix=a/longer/path/abcd/"
    )

    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    # Not set to batch, so we send 2 different messages
    assert mock_post.call_count == 1
    assert (
        mock_post.call_args_list[0][0][0]
        == "http://localhost/a/longer/path/abcd/"
        "ocs/v2.php/apps/spreed/api/v1/chat/admin"
    )
