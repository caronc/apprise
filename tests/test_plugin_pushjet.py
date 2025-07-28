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

from apprise.plugins.pushjet import NotifyPushjet

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "pjet://",
        {
            "instance": None,
        },
    ),
    (
        "pjets://",
        {
            "instance": None,
        },
    ),
    (
        "pjet://:@/",
        {
            "instance": None,
        },
    ),
    #  You must specify a secret key
    (
        "pjet://%s" % ("a" * 32),
        {
            "instance": TypeError,
        },
    ),
    # The proper way to log in
    (
        "pjet://user:pass@localhost/%s" % ("a" * 32),
        {
            "instance": NotifyPushjet,
        },
    ),
    # The proper way to log in
    (
        "pjets://localhost/%s" % ("a" * 32),
        {
            "instance": NotifyPushjet,
        },
    ),
    # Specify your own server with login (secret= MUST be provided)
    (
        "pjet://user:pass@localhost?secret=%s" % ("a" * 32),
        {
            "instance": NotifyPushjet,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "pjet://user:****@localhost",
        },
    ),
    # Specify your own server with port
    (
        "pjets://localhost:8080/%s" % ("a" * 32),
        {
            "instance": NotifyPushjet,
        },
    ),
    (
        "pjets://localhost:8080/%s" % ("a" * 32),
        {
            "instance": NotifyPushjet,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "pjets://localhost:4343/%s" % ("a" * 32),
        {
            "instance": NotifyPushjet,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "pjet://localhost:8081/%s" % ("a" * 32),
        {
            "instance": NotifyPushjet,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_pushjet_urls():
    """NotifyPushjet() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_pushjet_edge_cases():
    """NotifyPushjet() Edge Cases."""

    # No application Key specified
    with pytest.raises(TypeError):
        NotifyPushjet(secret_key=None)

    with pytest.raises(TypeError):
        NotifyPushjet(secret_key="  ")
