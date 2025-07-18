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

from apprise.plugins.notifico import NotifyNotifico

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "notifico://",
        {
            "instance": TypeError,
        },
    ),
    (
        "notifico://:@/",
        {
            "instance": TypeError,
        },
    ),
    (
        "notifico://1234",
        {
            # Just a project id provided (no message token)
            "instance": TypeError,
        },
    ),
    (
        "notifico://abcd/ckhrjW8w672m6HG",
        {
            # an invalid project id provided
            "instance": TypeError,
        },
    ),
    (
        "notifico://1234/ckhrjW8w672m6HG",
        {
            # A project id and message hook provided
            "instance": NotifyNotifico,
        },
    ),
    (
        "notifico://1234/ckhrjW8w672m6HG?prefix=no",
        {
            # Disable our prefix
            "instance": NotifyNotifico,
        },
    ),
    (
        "notifico://1234/ckhrjW8w672m6HG?color=yes",
        {
            "instance": NotifyNotifico,
            "notify_type": "info",
        },
    ),
    (
        "notifico://1234/ckhrjW8w672m6HG?color=yes",
        {
            "instance": NotifyNotifico,
            "notify_type": "success",
        },
    ),
    (
        "notifico://1234/ckhrjW8w672m6HG?color=yes",
        {
            "instance": NotifyNotifico,
            "notify_type": "warning",
        },
    ),
    (
        "notifico://1234/ckhrjW8w672m6HG?color=yes",
        {
            "instance": NotifyNotifico,
            "notify_type": "failure",
        },
    ),
    (
        "notifico://1234/ckhrjW8w672m6HG?color=yes",
        {
            "instance": NotifyNotifico,
            "notify_type": "invalid",
        },
    ),
    (
        "notifico://1234/ckhrjW8w672m6HG?color=no",
        {
            # Test our color flag by having it set to off
            "instance": NotifyNotifico,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "notifico://1...4/c...G",
        },
    ),
    # Support Native URLs
    (
        "https://n.tkte.ch/h/2144/uJmKaBW9WFk42miB146ci3Kj",
        {
            "instance": NotifyNotifico,
        },
    ),
    (
        "notifico://1234/ckhrjW8w672m6HG",
        {
            "instance": NotifyNotifico,
            # don't include an image by default
            "include_image": False,
        },
    ),
    (
        "notifico://1234/ckhrjW8w672m6HG",
        {
            "instance": NotifyNotifico,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "notifico://1234/ckhrjW8w672m6HG",
        {
            "instance": NotifyNotifico,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "notifico://1234/ckhrjW8w672m6HG",
        {
            "instance": NotifyNotifico,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_notifico_urls():
    """NotifyNotifico() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
