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
import os
from unittest import mock

from helpers import AppriseURLTester
import requests

from apprise import Apprise, AppriseAttachment, NotifyType
from apprise.plugins.apprise_api import NotifyAppriseAPI

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# Our Testing URLs
apprise_url_tests = (
    (
        "apprise://",
        {
            # invalid url (not complete)
            "instance": None,
        },
    ),
    # A a bad url
    (
        "apprise://:@/",
        {
            "instance": None,
        },
    ),
    # No token specified
    (
        "apprise://localhost",
        {
            "instance": TypeError,
        },
    ),
    # invalid token
    (
        "apprise://localhost/!",
        {
            "instance": TypeError,
        },
    ),
    # No token specified (whitespace is trimmed)
    (
        "apprise://localhost/%%20",
        {
            "instance": TypeError,
        },
    ),
    # A valid URL with Token
    (
        "apprise://localhost/%s" % ("a" * 32),
        {
            "instance": NotifyAppriseAPI,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "apprise://localhost/a...a/",
        },
    ),
    # A valid URL with long Token
    (
        "apprise://localhost/%s" % ("a" * 128),
        {
            "instance": NotifyAppriseAPI,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "apprise://localhost/a...a/",
        },
    ),
    # A valid URL with Token (using port)
    (
        "apprise://localhost:8080/%s" % ("b" * 32),
        {
            "instance": NotifyAppriseAPI,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "apprise://localhost:8080/b...b/",
        },
    ),
    # A secure (https://) reference
    (
        "apprises://localhost/%s" % ("c" * 32),
        {
            "instance": NotifyAppriseAPI,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "apprises://localhost/c...c/",
        },
    ),
    # Native URL suport (https)
    (
        "https://example.com/path/notify/%s" % ("d" * 32),
        {
            "instance": NotifyAppriseAPI,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "apprises://example.com/path/d...d/",
        },
    ),
    # Native URL suport (http)
    (
        "http://example.com/notify/%s" % ("d" * 32),
        {
            "instance": NotifyAppriseAPI,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "apprise://example.com/d...d/",
        },
    ),
    # support to= keyword
    (
        "apprises://localhost/?to=%s" % ("e" * 32),
        {
            "instance": NotifyAppriseAPI,
            "privacy_url": "apprises://localhost/e...e/",
        },
    ),
    # support token= keyword (even when passed with to=, token over-rides)
    (
        "apprise://localhost/?token={}&to={}".format("f" * 32, "abcd"),
        {
            "instance": NotifyAppriseAPI,
            "privacy_url": "apprise://localhost/f...f/",
        },
    ),
    # Test tags
    (
        "apprise://localhost/?token={}&tags=admin,team".format("abcd"),
        {
            "instance": NotifyAppriseAPI,
            "privacy_url": "apprise://localhost/a...d/",
        },
    ),
    # Test Format string
    (
        "apprise://user@localhost/mytoken0/?format=markdown",
        {
            "instance": NotifyAppriseAPI,
            "privacy_url": "apprise://user@localhost/m...0/",
        },
    ),
    (
        "apprise://user@localhost/mytoken1/",
        {
            "instance": NotifyAppriseAPI,
            "privacy_url": "apprise://user@localhost/m...1/",
        },
    ),
    (
        "apprise://localhost:8080/mytoken/",
        {
            "instance": NotifyAppriseAPI,
        },
    ),
    (
        "apprise://user:pass@localhost:8080/mytoken2/",
        {
            "instance": NotifyAppriseAPI,
            "privacy_url": "apprise://user:****@localhost:8080/m...2/",
        },
    ),
    (
        "apprises://localhost/mytoken/",
        {
            "instance": NotifyAppriseAPI,
        },
    ),
    (
        "apprises://user:pass@localhost/mytoken3/",
        {
            "instance": NotifyAppriseAPI,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "apprises://user:****@localhost/m...3/",
        },
    ),
    (
        "apprises://localhost:8080/mytoken4/",
        {
            "instance": NotifyAppriseAPI,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "apprises://localhost:8080/m...4/",
        },
    ),
    (
        "apprises://localhost:8080/abc123/?method=json",
        {
            "instance": NotifyAppriseAPI,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "apprises://localhost:8080/a...3/",
        },
    ),
    (
        "apprises://localhost:8080/abc123/?method=form",
        {
            "instance": NotifyAppriseAPI,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "apprises://localhost:8080/a...3/",
        },
    ),
    # Invalid method specified
    (
        "apprises://localhost:8080/abc123/?method=invalid",
        {
            "instance": TypeError,
        },
    ),
    (
        "apprises://user:password@localhost:8080/mytoken5/",
        {
            "instance": NotifyAppriseAPI,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "apprises://user:****@localhost:8080/m...5/",
        },
    ),
    (
        "apprises://localhost:8080/path?+HeaderKey=HeaderValue",
        {
            "instance": NotifyAppriseAPI,
        },
    ),
    (
        "apprise://localhost/%s" % ("a" * 32),
        {
            "instance": NotifyAppriseAPI,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "apprise://localhost/%s" % ("a" * 32),
        {
            "instance": NotifyAppriseAPI,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "apprise://localhost/%s" % ("a" * 32),
        {
            "instance": NotifyAppriseAPI,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_apprise_urls():
    """NotifyAppriseAPI() General Checks."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_notify_apprise_api_attachments(mock_post):
    """NotifyAppriseAPI() Attachments."""

    okay_response = requests.Request()

    for method in ("json", "form"):
        okay_response.status_code = requests.codes.ok
        okay_response.content = ""

        # Assign our mock object our return value
        mock_post.return_value = okay_response

        obj = Apprise.instantiate(
            f"apprise://user@localhost/mytoken1/?method={method}"
        )
        assert isinstance(obj, NotifyAppriseAPI)

        # Test Valid Attachment
        path = os.path.join(TEST_VAR_DIR, "apprise-test.gif")
        attach = AppriseAttachment(path)
        assert (
            obj.notify(
                body="body",
                title="title",
                notify_type=NotifyType.INFO,
                attach=attach,
            )
            is True
        )

        # Test invalid attachment
        path = os.path.join(
            TEST_VAR_DIR, "/invalid/path/to/an/invalid/file.jpg"
        )
        assert (
            obj.notify(
                body="body",
                title="title",
                notify_type=NotifyType.INFO,
                attach=path,
            )
            is False
        )

        # Test Valid Attachment (load 3)
        path = (
            os.path.join(TEST_VAR_DIR, "apprise-test.gif"),
            os.path.join(TEST_VAR_DIR, "apprise-test.gif"),
            os.path.join(TEST_VAR_DIR, "apprise-test.gif"),
        )
        attach = AppriseAttachment(path)

        # Return our good configuration
        mock_post.side_effect = None
        mock_post.return_value = okay_response
        with mock.patch("builtins.open", side_effect=OSError()):
            # We can't send the message we can't open the attachment for
            # reading
            assert (
                obj.notify(
                    body="body",
                    title="title",
                    notify_type=NotifyType.INFO,
                    attach=attach,
                )
                is False
            )

        with mock.patch("requests.post", side_effect=OSError()):
            # Attachment issue
            assert (
                obj.notify(
                    body="body",
                    title="title",
                    notify_type=NotifyType.INFO,
                    attach=attach,
                )
                is False
            )

        # test the handling of our batch modes
        obj = Apprise.instantiate("apprise://user@localhost/mytoken1/")
        assert isinstance(obj, NotifyAppriseAPI)

        # Now send an attachment normally without issues
        mock_post.reset_mock()

        assert (
            obj.notify(
                body="body",
                title="title",
                notify_type=NotifyType.INFO,
                attach=attach,
            )
            is True
        )
        assert mock_post.call_count == 1

        details = mock_post.call_args_list[0]
        assert details[0][0] == "http://localhost/notify/mytoken1"
        assert obj.url(privacy=False).startswith(
            "apprise://user@localhost/mytoken1/"
        )

        mock_post.reset_mock()
