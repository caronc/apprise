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

from helpers import AppriseURLTester
import pytest
import requests

from apprise.plugins.ryver import NotifyRyver

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "ryver://",
        {
            "instance": TypeError,
        },
    ),
    (
        "ryver://:@/",
        {
            "instance": TypeError,
        },
    ),
    (
        "ryver://apprise",
        {
            # Just org provided (no token)
            "instance": TypeError,
        },
    ),
    (
        "ryver://apprise/ckhrjW8w672m6HG?mode=invalid",
        {
            # invalid mode provided
            "instance": TypeError,
        },
    ),
    (
        "ryver://x/ckhrjW8w672m6HG?mode=slack",
        {
            # Invalid org
            "instance": TypeError,
        },
    ),
    (
        "ryver://apprise/ckhrjW8w672m6HG?mode=slack",
        {
            # No username specified; this is still okay as we use whatever
            # the user told the webhook to use; set our slack mode
            "instance": NotifyRyver,
        },
    ),
    (
        "ryver://apprise/ckhrjW8w672m6HG?mode=ryver",
        {
            # No username specified; this is still okay as we use whatever
            # the user told the webhook to use; set our ryver mode
            "instance": NotifyRyver,
        },
    ),
    # Legacy webhook mode setting:
    # Legacy webhook mode setting:
    (
        "ryver://apprise/ckhrjW8w672m6HG?webhook=slack",
        {
            # No username specified; this is still okay as we use whatever
            # the user told the webhook to use; set our slack mode
            "instance": NotifyRyver,
        },
    ),
    (
        "ryver://apprise/ckhrjW8w672m6HG?webhook=ryver",
        {
            # No username specified; this is still okay as we use whatever
            # the user told the webhook to use; set our ryver mode
            "instance": NotifyRyver,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "ryver://apprise/c...G",
        },
    ),
    # Support Native URLs
    (
        "https://apprise.ryver.com/application/webhook/ckhrjW8w672m6HG",
        {
            "instance": NotifyRyver,
        },
    ),
    # Support Native URLs with arguments
    (
        (
            "https://apprise.ryver.com/application/webhook/ckhrjW8w672m6HG"
            "?webhook=ryver"
        ),
        {
            "instance": NotifyRyver,
        },
    ),
    (
        "ryver://caronc@apprise/ckhrjW8w672m6HG",
        {
            "instance": NotifyRyver,
            # don't include an image by default
            "include_image": False,
        },
    ),
    (
        "ryver://apprise/ckhrjW8w672m6HG",
        {
            "instance": NotifyRyver,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "ryver://apprise/ckhrjW8w672m6HG",
        {
            "instance": NotifyRyver,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "ryver://apprise/ckhrjW8w672m6HG",
        {
            "instance": NotifyRyver,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_ryver_urls():
    """NotifyRyver() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_ryver_edge_cases():
    """NotifyRyver() Edge Cases."""

    # No token
    with pytest.raises(TypeError):
        NotifyRyver(organization="abc", token=None)

    with pytest.raises(TypeError):
        NotifyRyver(organization="abc", token="  ")

    # No organization
    with pytest.raises(TypeError):
        NotifyRyver(organization=None, token="abc")

    with pytest.raises(TypeError):
        NotifyRyver(organization="  ", token="abc")
