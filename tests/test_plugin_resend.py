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
import pytest
import requests

from apprise import Apprise, AppriseAttachment, NotifyType
from apprise.plugins.resend import NotifyResend

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# a resend api key
UUID4 = "re_FmABCDEF_987654321zqbabc123abc8fw"

# Our Testing URLs
apprise_url_tests = (
    (
        "resend://",
        {
            "instance": None,
        },
    ),
    (
        "resend://:@/",
        {
            "instance": None,
        },
    ),
    (
        "resend://abcd",
        {
            # Just an broken email (no api key or email)
            "instance": None,
        },
    ),
    (
        "resend://abcd@host",
        {
            # Just an Email specified, no API Key
            "instance": None,
        },
    ),
    (
        "resend://invalid-api-key+*-d:user@example.com",
        {
            # An invalid API Key
            "instance": TypeError,
        },
    ),
    (
        "resend://abcd:user@example.com",
        {
            # No To/Target Address(es) specified; so we sub in the same From
            # address
            "instance": NotifyResend,
        },
    ),
    (
        "resend://abcd:user@example.com/newuser@example.com",
        {
            # A good email
            "instance": NotifyResend,
        },
    ),
    (
        (
            "resend://abcd:user@example.com/newuser@example.com"
            "?bcc=l2g@nuxref.com"
        ),
        {
            # A good email with Blind Carbon Copy
            "instance": NotifyResend,
        },
    ),
    (
        "resend://abcd:user@example.com/newuser@example.com?cc=l2g@nuxref.com",
        {
            # A good email with Carbon Copy
            "instance": NotifyResend,
        },
    ),
    (
        "resend://abcd:user@example.com/newuser@example.com?to=l2g@nuxref.com",
        {
            # A good email with Carbon Copy
            "instance": NotifyResend,
        },
    ),
    (
        "resend://abcd:user@example.ca/newuser@example.ca",
        {
            "instance": NotifyResend,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "resend://abcd:user@example.uk/newuser@example.uk",
        {
            "instance": NotifyResend,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "resend://abcd:user@example.au/newuser@example.au",
        {
            "instance": NotifyResend,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_resend_urls():
    """NotifyResend() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_resend_edge_cases(mock_post, mock_get):
    """NotifyResend() Edge Cases."""

    # no apikey
    with pytest.raises(TypeError):
        NotifyResend(apikey=None, from_email="user@example.com")

    # invalid from email
    with pytest.raises(TypeError):
        NotifyResend(apikey="abcd", from_email="!invalid")

    # no email
    with pytest.raises(TypeError):
        NotifyResend(apikey="abcd", from_email=None)

    # Invalid To email address
    NotifyResend(
        apikey="abcd", from_email="user@example.com", targets="!invalid"
    )

    # Test invalid bcc/cc entries mixed with good ones
    assert isinstance(
        NotifyResend(
            apikey="abcd",
            from_email="l2g@example.com",
            bcc=("abc@def.com", "!invalid"),
            cc=("abc@test.org", "!invalid"),
        ),
        NotifyResend,
    )


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_resend_attachments(mock_post, mock_get):
    """NotifyResend() Attachments."""

    request = mock.Mock()
    request.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = request
    mock_get.return_value = request

    path = os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    attach = AppriseAttachment(path)
    obj = Apprise.instantiate("resend://abcd:user@example.com")
    assert isinstance(obj, NotifyResend)
    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is True
    )

    mock_post.reset_mock()
    mock_get.reset_mock()

    # Try again in a use case where we can't access the file
    with mock.patch("os.path.isfile", return_value=False):
        assert (
            obj.notify(
                body="body",
                title="title",
                notify_type=NotifyType.INFO,
                attach=attach,
            )
            is False
        )

    # Try again in a use case where we can't access the file
    with mock.patch("builtins.open", side_effect=OSError):
        assert (
            obj.notify(
                body="body",
                title="title",
                notify_type=NotifyType.INFO,
                attach=attach,
            )
            is False
        )
