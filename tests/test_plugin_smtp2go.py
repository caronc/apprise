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
from apprise.plugins.smtp2go import NotifySMTP2Go

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# Our Testing URLs
apprise_url_tests = (
    (
        "smtp2go://",
        {
            "instance": TypeError,
        },
    ),
    (
        "smtp2go://:@/",
        {
            "instance": TypeError,
        },
    ),
    # No Token specified
    (
        "smtp2go://user@localhost.localdomain",
        {
            "instance": TypeError,
        },
    ),
    # Token is valid, but no user name specified
    (
        "smtp2go://localhost.localdomain/{}-{}-{}".format(
            "a" * 32, "b" * 8, "c" * 8
        ),
        {
            "instance": TypeError,
        },
    ),
    # Invalid from email address
    (
        'smtp2go://"@localhost.localdomain/{}-{}-{}'.format(
            "a" * 32, "b" * 8, "c" * 8
        ),
        {
            "instance": TypeError,
        },
    ),
    # No To email address, but everything else is valid
    (
        "smtp2go://user@localhost.localdomain/{}-{}-{}".format(
            "a" * 32, "b" * 8, "c" * 8
        ),
        {
            "instance": NotifySMTP2Go,
        },
    ),
    (
        "smtp2go://user@localhost.localdomain/{}-{}-{}?format=markdown".format(
            "a" * 32, "b" * 8, "c" * 8
        ),
        {
            "instance": NotifySMTP2Go,
        },
    ),
    (
        "smtp2go://user@localhost.localdomain/{}-{}-{}?format=html".format(
            "a" * 32, "b" * 8, "c" * 8
        ),
        {
            "instance": NotifySMTP2Go,
        },
    ),
    (
        "smtp2go://user@localhost.localdomain/{}-{}-{}?format=text".format(
            "a" * 32, "b" * 8, "c" * 8
        ),
        {
            "instance": NotifySMTP2Go,
        },
    ),
    # headers
    (
        "smtp2go://user@localhost.localdomain/{}-{}-{}"
        "?+X-Customer-Campaign-ID=Apprise".format("a" * 32, "b" * 8, "c" * 8),
        {
            "instance": NotifySMTP2Go,
        },
    ),
    # bcc and cc
    (
        "smtp2go://user@localhost.localdomain/{}-{}-{}"
        "?bcc=user@example.com&cc=user2@example.com".format(
            "a" * 32, "b" * 8, "c" * 8
        ),
        {
            "instance": NotifySMTP2Go,
        },
    ),
    # One To Email address
    (
        "smtp2go://user@localhost.localdomain/{}-{}-{}/test@example.com"
        .format("a" * 32, "b" * 8, "c" * 8),
        {
            "instance": NotifySMTP2Go,
        },
    ),
    (
        "smtp2go://user@localhost.localdomain/"
        "{}-{}-{}?to=test@example.com".format("a" * 32, "b" * 8, "c" * 8),
        {"instance": NotifySMTP2Go},
    ),
    # One To Email address, a from name specified too
    (
        "smtp2go://user@localhost.localdomain/{}-{}-{}/"
        'test@example.com?name="Frodo"'.format("a" * 32, "b" * 8, "c" * 8),
        {"instance": NotifySMTP2Go},
    ),
    # Invalid 'To' Email address
    (
        "smtp2go://user@localhost.localdomain/{}-{}-{}/invalid".format(
            "a" * 32, "b" * 8, "c" * 8
        ),
        {
            "instance": NotifySMTP2Go,
            # Expected notify() response
            "notify_response": False,
        },
    ),
    # Multiple 'To', 'Cc', and 'Bcc' addresses (with invalid ones)
    (
        "smtp2go://user@example.com/{}-{}-{}/{}?bcc={}&cc={}".format(
            "a" * 32,
            "b" * 8,
            "c" * 8,
            "/".join(
                ("user1@example.com", "invalid", "User2:user2@example.com")
            ),
            ",".join(("user3@example.com", "i@v", "User1:user1@example.com")),
            ",".join(("user4@example.com", "g@r@b", "Da:user5@example.com")),
        ),
        {
            "instance": NotifySMTP2Go,
        },
    ),
    (
        "smtp2go://user@localhost.localdomain/{}-{}-{}".format(
            "a" * 32, "b" * 8, "c" * 8
        ),
        {
            "instance": NotifySMTP2Go,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "smtp2go://user@localhost.localdomain/{}-{}-{}".format(
            "a" * 32, "b" * 8, "c" * 8
        ),
        {
            "instance": NotifySMTP2Go,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "smtp2go://user@localhost.localdomain/{}-{}-{}".format(
            "a" * 32, "b" * 8, "c" * 8
        ),
        {
            "instance": NotifySMTP2Go,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_smtp2go_urls():
    """NotifySMTP2Go() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_smtp2go_attachments(mock_post):
    """NotifySMTP2Go() Attachments."""

    okay_response = requests.Request()
    okay_response.status_code = requests.codes.ok
    okay_response.content = ""

    # Assign our mock object our return value
    mock_post.return_value = okay_response

    # API Key
    apikey = "abc123"

    obj = Apprise.instantiate(f"smtp2go://user@localhost.localdomain/{apikey}")
    assert isinstance(obj, NotifySMTP2Go)

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

    mock_post.return_value = None
    mock_post.side_effect = OSError()
    # We can't send the message if we can't read the attachment
    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=attach,
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
        # We can't send the message we can't open the attachment for reading
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
    obj = Apprise.instantiate(
        f"smtp2go://no-reply@example.com/{apikey}/"
        "user1@example.com/user2@example.com?batch=yes"
    )
    assert isinstance(obj, NotifySMTP2Go)

    # objects will be combined into a single post in batch mode
    assert len(obj) == 1

    # Force our batch to break into separate messages
    obj.default_batch_size = 1

    # We'll send 2 messages now
    assert len(obj) == 2

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
    assert mock_post.call_count == 2

    # single batch
    mock_post.reset_mock()
    # We'll send 1 message
    obj.default_batch_size = 2

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
