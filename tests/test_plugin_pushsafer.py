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

from json import dumps

# Disable logging for a cleaner testing output
import logging
import os
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import AppriseAttachment, NotifyType
from apprise.plugins.pushsafer import NotifyPushSafer

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# Our Testing URLs
apprise_url_tests = (
    (
        "psafer://:@/",
        {
            "instance": TypeError,
        },
    ),
    (
        "psafer://",
        {
            "instance": TypeError,
        },
    ),
    (
        "psafers://",
        {
            "instance": TypeError,
        },
    ),
    (
        "psafer://{}".format("a" * 20),
        {
            "instance": NotifyPushSafer,
            # This will fail because we're also expecting a server
            # acknowledgement
            "notify_response": False,
        },
    ),
    (
        "psafer://{}".format("b" * 20),
        {
            "instance": NotifyPushSafer,
            # invalid JSON response
            "requests_response_text": "{",
            "notify_response": False,
        },
    ),
    (
        "psafer://{}".format("c" * 20),
        {
            "instance": NotifyPushSafer,
            # A failure has status set to zero
            # We also expect an 'error' flag to be set
            "requests_response_text": {"status": 0, "error": "we failed"},
            "notify_response": False,
        },
    ),
    (
        "psafers://{}".format("d" * 20),
        {
            "instance": NotifyPushSafer,
            # A failure has status set to zero
            # Test without an 'error' flag
            "requests_response_text": {
                "status": 0,
            },
            "notify_response": False,
        },
    ),
    # This will notify all users ('a')
    (
        "psafer://{}".format("e" * 20),
        {
            "instance": NotifyPushSafer,
            # A status of 1 is a success
            "requests_response_text": {
                "status": 1,
            },
        },
    ),
    # This will notify a selected set of devices
    (
        "psafer://{}/12/24/53".format("e" * 20),
        {
            "instance": NotifyPushSafer,
            # A status of 1 is a success
            "requests_response_text": {
                "status": 1,
            },
        },
    ),
    # Same as above, but exercises the to= argument
    (
        "psafer://{}?to=12,24,53".format("e" * 20),
        {
            "instance": NotifyPushSafer,
            # A status of 1 is a success
            "requests_response_text": {
                "status": 1,
            },
        },
    ),
    # Set priority
    (
        "psafer://{}?priority=emergency".format("f" * 20),
        {
            "instance": NotifyPushSafer,
            "requests_response_text": {
                "status": 1,
            },
        },
    ),
    # Support integer value too
    (
        "psafer://{}?priority=-1".format("f" * 20),
        {
            "instance": NotifyPushSafer,
            "requests_response_text": {
                "status": 1,
            },
        },
    ),
    # Invalid priority
    (
        "psafer://{}?priority=invalid".format("f" * 20),
        {
            # Invalid Priority
            "instance": TypeError,
        },
    ),
    # Invalid priority
    (
        "psafer://{}?priority=25".format("f" * 20),
        {
            # Invalid Priority
            "instance": TypeError,
        },
    ),
    # Set sound
    (
        "psafer://{}?sound=ok".format("g" * 20),
        {
            "instance": NotifyPushSafer,
            "requests_response_text": {
                "status": 1,
            },
        },
    ),
    # Support integer value too
    (
        "psafers://{}?sound=14".format("g" * 20),
        {
            "instance": NotifyPushSafer,
            "requests_response_text": {
                "status": 1,
            },
            "privacy_url": "psafers://g...g",
        },
    ),
    # Invalid sound
    (
        "psafer://{}?sound=invalid".format("h" * 20),
        {
            # Invalid Sound
            "instance": TypeError,
        },
    ),
    (
        "psafer://{}?sound=94000".format("h" * 20),
        {
            # Invalid Sound
            "instance": TypeError,
        },
    ),
    # Set vibration (integer only)
    (
        "psafers://{}?vibration=1".format("h" * 20),
        {
            "instance": NotifyPushSafer,
            "requests_response_text": {
                "status": 1,
            },
            "privacy_url": "psafers://h...h",
        },
    ),
    # Invalid sound
    (
        "psafer://{}?vibration=invalid".format("h" * 20),
        {
            # Invalid Vibration
            "instance": TypeError,
        },
    ),
    # Invalid vibration
    (
        "psafer://{}?vibration=25000".format("h" * 20),
        {
            # Invalid Vibration
            "instance": TypeError,
        },
    ),
    (
        "psafers://{}".format("d" * 20),
        {
            "instance": NotifyPushSafer,
            # A failure has status set to zero
            # Test without an 'error' flag
            "requests_response_text": {
                "status": 0,
            },
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "psafer://{}".format("d" * 20),
        {
            "instance": NotifyPushSafer,
            # A failure has status set to zero
            # Test without an 'error' flag
            "requests_response_text": {
                "status": 0,
            },
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "psafers://{}".format("d" * 20),
        {
            "instance": NotifyPushSafer,
            # A failure has status set to zero
            # Test without an 'error' flag
            "requests_response_text": {
                "status": 0,
            },
            # Throws a series of connection and transfer exceptions when this
            # flag is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_pushsafer_urls():
    """NotifyPushSafer() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_pushsafer_general(mock_post):
    """NotifyPushSafer() General Tests."""

    # Private Key
    privatekey = "abc123"

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = dumps({
        "status": 1,
        "success": "okay",
    })

    # Exception should be thrown about the fact no private key was specified
    with pytest.raises(TypeError):
        NotifyPushSafer(privatekey=None)

    # Multiple Attachment Support
    path = os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    attach = AppriseAttachment()
    for _ in range(0, 4):
        attach.add(path)

    obj = NotifyPushSafer(privatekey=privatekey)
    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is True
    )

    # Test error reading attachment from disk
    with mock.patch("builtins.open", side_effect=OSError):
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=attach,
        )

    # Test unsupported mime type
    attach = AppriseAttachment(path)

    attach[0]._mimetype = "application/octet-stream"

    # We gracefully just don't send the attachment in these cases;
    # The notify itself will still be successful
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

    # the 'p', 'p2', and 'p3' are the data variables used when including an
    # image.
    assert "data" in mock_post.call_args[1]
    assert "p" not in mock_post.call_args[1]["data"]
    assert "p2" not in mock_post.call_args[1]["data"]
    assert "p3" not in mock_post.call_args[1]["data"]

    # Invalid file path
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
