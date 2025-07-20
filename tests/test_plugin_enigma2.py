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
import requests

from apprise.plugins.enigma2 import NotifyEnigma2

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "enigma2://:@/",
        {
            "instance": None,
        },
    ),
    (
        "enigma2://",
        {
            "instance": None,
        },
    ),
    (
        "enigma2s://",
        {
            "instance": None,
        },
    ),
    (
        "enigma2://localhost",
        {
            "instance": NotifyEnigma2,
            # This will fail because we're also expecting a server
            # acknowledgement
            "notify_response": False,
        },
    ),
    (
        "enigma2://localhost",
        {
            "instance": NotifyEnigma2,
            # invalid JSON response
            "requests_response_text": "{",
            "notify_response": False,
        },
    ),
    (
        "enigma2://localhost",
        {
            "instance": NotifyEnigma2,
            # False is returned
            "requests_response_text": {"result": False},
            "notify_response": False,
        },
    ),
    (
        "enigma2://localhost",
        {
            "instance": NotifyEnigma2,
            # With the right content, this will succeed
            "requests_response_text": {"result": True},
        },
    ),
    (
        "enigma2://user@localhost",
        {
            "instance": NotifyEnigma2,
            "requests_response_text": {"result": True},
        },
    ),
    # Set timeout
    (
        "enigma2://user@localhost?timeout=-1",
        {
            "instance": NotifyEnigma2,
            "requests_response_text": {"result": True},
        },
    ),
    # Set timeout
    (
        "enigma2://user@localhost?timeout=-1000",
        {
            "instance": NotifyEnigma2,
            "requests_response_text": {"result": True},
        },
    ),
    # Set invalid timeout (defaults to a set value)
    (
        "enigma2://user@localhost?timeout=invalid",
        {
            "instance": NotifyEnigma2,
            "requests_response_text": {"result": True},
        },
    ),
    (
        "enigma2://user:pass@localhost",
        {
            "instance": NotifyEnigma2,
            "requests_response_text": {"result": True},
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "enigma2://user:****@localhost",
        },
    ),
    (
        "enigma2://localhost:8080",
        {
            "instance": NotifyEnigma2,
            "requests_response_text": {"result": True},
        },
    ),
    (
        "enigma2://user:pass@localhost:8080",
        {
            "instance": NotifyEnigma2,
            "requests_response_text": {"result": True},
        },
    ),
    (
        "enigma2s://localhost",
        {
            "instance": NotifyEnigma2,
            "requests_response_text": {"result": True},
        },
    ),
    (
        "enigma2s://user:pass@localhost",
        {
            "instance": NotifyEnigma2,
            "requests_response_text": {"result": True},
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "enigma2s://user:****@localhost",
        },
    ),
    (
        "enigma2s://localhost:8080/path/",
        {
            "instance": NotifyEnigma2,
            "requests_response_text": {"result": True},
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "enigma2s://localhost:8080/path/",
        },
    ),
    (
        "enigma2s://user:pass@localhost:8080",
        {
            "instance": NotifyEnigma2,
            "requests_response_text": {"result": True},
        },
    ),
    (
        "enigma2://localhost:8080/path?+HeaderKey=HeaderValue",
        {
            "instance": NotifyEnigma2,
            "requests_response_text": {"result": True},
        },
    ),
    (
        "enigma2://user:pass@localhost:8081",
        {
            "instance": NotifyEnigma2,
            "requests_response_text": {"result": True},
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "enigma2://user:pass@localhost:8082",
        {
            "instance": NotifyEnigma2,
            "requests_response_text": {"result": True},
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "enigma2://user:pass@localhost:8083",
        {
            "instance": NotifyEnigma2,
            "requests_response_text": {"result": True},
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_enigma2_urls():
    """NotifyEnigma2() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
