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

from apprise.plugins.guilded import NotifyGuilded

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# Our Testing URLs
apprise_url_tests = (
    (
        "guilded://",
        {
            "instance": TypeError,
        },
    ),
    # An invalid url
    (
        "guilded://:@/",
        {
            "instance": TypeError,
        },
    ),
    # No webhook_token specified
    (
        "guilded://%s" % ("i" * 24),
        {
            "instance": TypeError,
        },
    ),
    # Provide both an webhook id and a webhook token
    (
        "guilded://{}/{}".format("i" * 24, "t" * 64),
        {
            "instance": NotifyGuilded,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    # Provide a temporary username
    (
        "guilded://l2g@{}/{}".format("i" * 24, "t" * 64),
        {
            "instance": NotifyGuilded,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    # test image= field
    (
        "guilded://{}/{}?format=markdown&footer=Yes&image=Yes".format(
            "i" * 24, "t" * 64
        ),
        {
            "instance": NotifyGuilded,
            "requests_response_code": requests.codes.no_content,
            # don't include an image by default
            "include_image": False,
        },
    ),
    (
        "guilded://{}/{}?format=markdown&footer=Yes&image=No&fields=no".format(
            "i" * 24, "t" * 64
        ),
        {
            "instance": NotifyGuilded,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    (
        "guilded://{}/{}?format=markdown&footer=Yes&image=Yes".format(
            "i" * 24, "t" * 64
        ),
        {
            "instance": NotifyGuilded,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    (
        "https://media.guilded.gg/webhooks/{}/{}".format("0" * 10, "B" * 40),
        {
            # Native URL Support, support the provided guilded URL from their
            # webpage.
            "instance": NotifyGuilded,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    (
        "guilded://{}/{}?format=markdown&avatar=No&footer=No".format(
            "i" * 24, "t" * 64
        ),
        {
            "instance": NotifyGuilded,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    # different format support
    (
        "guilded://{}/{}?format=markdown".format("i" * 24, "t" * 64),
        {
            "instance": NotifyGuilded,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    (
        "guilded://{}/{}?format=text".format("i" * 24, "t" * 64),
        {
            "instance": NotifyGuilded,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    # Test with avatar URL
    (
        "guilded://{}/{}?avatar_url=http://localhost/test.jpg".format(
            "i" * 24, "t" * 64
        ),
        {
            "instance": NotifyGuilded,
            "requests_response_code": requests.codes.no_content,
        },
    ),
    # Test without image set
    (
        "guilded://{}/{}".format("i" * 24, "t" * 64),
        {
            "instance": NotifyGuilded,
            "requests_response_code": requests.codes.no_content,
            # don't include an image by default
            "include_image": False,
        },
    ),
    (
        "guilded://{}/{}/".format("a" * 24, "b" * 64),
        {
            "instance": NotifyGuilded,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "guilded://{}/{}/".format("a" * 24, "b" * 64),
        {
            "instance": NotifyGuilded,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "guilded://{}/{}/".format("a" * 24, "b" * 64),
        {
            "instance": NotifyGuilded,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_guilded_urls():
    """NotifyGuilded() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_guilded_general(mock_post):
    """NotifyGuilded() General Checks."""

    # Initialize some generic (but valid) tokens
    webhook_id = "A" * 24
    webhook_token = "B" * 64

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    # Invalid webhook id
    with pytest.raises(TypeError):
        NotifyGuilded(webhook_id=None, webhook_token=webhook_token)
    # Invalid webhook id (whitespace)
    with pytest.raises(TypeError):
        NotifyGuilded(webhook_id="  ", webhook_token=webhook_token)

    # Invalid webhook token
    with pytest.raises(TypeError):
        NotifyGuilded(webhook_id=webhook_id, webhook_token=None)
    # Invalid webhook token (whitespace)
    with pytest.raises(TypeError):
        NotifyGuilded(webhook_id=webhook_id, webhook_token="   ")

    obj = NotifyGuilded(
        webhook_id=webhook_id,
        webhook_token=webhook_token,
        footer=True,
        thumbnail=False,
    )

    # Test that we get a string response
    assert isinstance(obj.url(), str)
