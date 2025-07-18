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

from apprise.plugins.notica import NotifyNotica

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "notica://",
        {
            "instance": TypeError,
        },
    ),
    (
        "notica://:@/",
        {
            "instance": TypeError,
        },
    ),
    # Native URL
    (
        "https://notica.us/?%s" % ("z" * 6),
        {
            "instance": NotifyNotica,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "notica://z...z/",
        },
    ),
    # Native URL with additional arguments
    (
        "https://notica.us/?%s&overflow=upstream" % ("z" * 6),
        {
            "instance": NotifyNotica,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "notica://z...z/",
        },
    ),
    # Token specified
    (
        "notica://%s" % ("a" * 6),
        {
            "instance": NotifyNotica,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "notica://a...a/",
        },
    ),
    # Self-Hosted configuration
    (
        "notica://localhost/%s" % ("b" * 6),
        {
            "instance": NotifyNotica,
        },
    ),
    (
        "notica://user@localhost/%s" % ("c" * 6),
        {
            "instance": NotifyNotica,
        },
    ),
    (
        "notica://user:pass@localhost/%s/" % ("d" * 6),
        {
            "instance": NotifyNotica,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "notica://user:****@localhost/d...d",
        },
    ),
    (
        "notica://user:pass@localhost/a/path/%s/" % ("r" * 6),
        {
            "instance": NotifyNotica,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "notica://user:****@localhost/a/path/r...r",
        },
    ),
    (
        "notica://localhost:8080/%s" % ("a" * 6),
        {
            "instance": NotifyNotica,
        },
    ),
    (
        "notica://user:pass@localhost:8080/%s" % ("b" * 6),
        {
            "instance": NotifyNotica,
        },
    ),
    (
        "noticas://localhost/%s" % ("j" * 6),
        {
            "instance": NotifyNotica,
            "privacy_url": "noticas://localhost/j...j",
        },
    ),
    (
        "noticas://user:pass@localhost/%s" % ("e" * 6),
        {
            "instance": NotifyNotica,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "noticas://user:****@localhost/e...e",
        },
    ),
    (
        "noticas://localhost:8080/path/%s" % ("5" * 6),
        {
            "instance": NotifyNotica,
            "privacy_url": "noticas://localhost:8080/path/5...5",
        },
    ),
    (
        "noticas://user:pass@localhost:8080/%s" % ("6" * 6),
        {
            "instance": NotifyNotica,
        },
    ),
    (
        "notica://%s" % ("b" * 6),
        {
            "instance": NotifyNotica,
            # don't include an image by default
            "include_image": False,
        },
    ),
    # Test Header overrides
    (
        "notica://localhost:8080//%s/?+HeaderKey=HeaderValue" % ("7" * 6),
        {
            "instance": NotifyNotica,
        },
    ),
    (
        "notica://%s" % ("c" * 6),
        {
            "instance": NotifyNotica,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "notica://%s" % ("d" * 7),
        {
            "instance": NotifyNotica,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "notica://%s" % ("e" * 8),
        {
            "instance": NotifyNotica,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_notica_urls():
    """NotifyNotica() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
