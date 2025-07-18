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

from apprise import NotifyType
from apprise.plugins.xbmc import NotifyXBMC

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "kodi://",
        {
            "instance": None,
        },
    ),
    (
        "kodis://",
        {
            "instance": None,
        },
    ),
    (
        "kodi://localhost",
        {
            "instance": NotifyXBMC,
        },
    ),
    (
        "kodi://192.168.4.1",
        {
            # Support IPv4 Addresses
            "instance": NotifyXBMC,
        },
    ),
    (
        "kodi://[2001:db8:002a:3256:adfe:05c0:0003:0006]",
        {
            # Support IPv6 Addresses
            "instance": NotifyXBMC,
            # Privacy URL
            "privacy_url": "kodi://[2001:db8:002a:3256:adfe:05c0:0003:0006]",
        },
    ),
    (
        "kodi://[2001:db8:002a:3256:adfe:05c0:0003:0006]:8282",
        {
            # Support IPv6 Addresses with port
            "instance": NotifyXBMC,
            # Privacy URL
            "privacy_url": (
                "kodi://[2001:db8:002a:3256:adfe:05c0:0003:0006]:8282"
            ),
        },
    ),
    (
        "kodi://user:pass@localhost",
        {
            "instance": NotifyXBMC,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "kodi://user:****@localhost",
        },
    ),
    (
        "kodi://localhost:8080",
        {
            "instance": NotifyXBMC,
        },
    ),
    (
        "kodi://user:pass@localhost:8080",
        {
            "instance": NotifyXBMC,
        },
    ),
    (
        "kodis://localhost",
        {
            "instance": NotifyXBMC,
        },
    ),
    (
        "kodis://user:pass@localhost",
        {
            "instance": NotifyXBMC,
        },
    ),
    (
        "kodis://localhost:8080/path/",
        {
            "instance": NotifyXBMC,
        },
    ),
    (
        "kodis://user:password@localhost:8080",
        {
            "instance": NotifyXBMC,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "kodis://user:****@localhost:8080",
        },
    ),
    (
        "kodi://localhost",
        {
            "instance": NotifyXBMC,
            # Experement with different notification types
            "notify_type": NotifyType.WARNING,
        },
    ),
    (
        "kodi://localhost",
        {
            "instance": NotifyXBMC,
            # Experement with different notification types
            "notify_type": NotifyType.FAILURE,
        },
    ),
    (
        "kodis://localhost:443",
        {
            "instance": NotifyXBMC,
            # don't include an image by default
            "include_image": False,
        },
    ),
    (
        "kodi://:@/",
        {
            "instance": None,
        },
    ),
    (
        "kodi://user:pass@localhost:8081",
        {
            "instance": NotifyXBMC,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "kodi://user:pass@localhost:8082",
        {
            "instance": NotifyXBMC,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "kodi://user:pass@localhost:8083",
        {
            "instance": NotifyXBMC,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
    #
    # XMBC (Legacy Platform) Shares this same KODI Plugin
    #
    (
        "xbmc://",
        {
            "instance": None,
        },
    ),
    (
        "xbmc://localhost",
        {
            "instance": NotifyXBMC,
        },
    ),
    (
        "xbmc://localhost?duration=14",
        {
            "instance": NotifyXBMC,
        },
    ),
    (
        "xbmc://localhost?duration=invalid",
        {
            "instance": NotifyXBMC,
        },
    ),
    (
        "xbmc://localhost?duration=-1",
        {
            "instance": NotifyXBMC,
        },
    ),
    (
        "xbmc://user:pass@localhost",
        {
            "instance": NotifyXBMC,
        },
    ),
    (
        "xbmc://localhost:8080",
        {
            "instance": NotifyXBMC,
        },
    ),
    (
        "xbmc://user:pass@localhost:8080",
        {
            "instance": NotifyXBMC,
        },
    ),
    (
        "xbmc://user@localhost",
        {
            "instance": NotifyXBMC,
            # don't include an image by default
            "include_image": False,
        },
    ),
    (
        "xbmc://localhost",
        {
            "instance": NotifyXBMC,
            # Experement with different notification types
            "notify_type": NotifyType.WARNING,
        },
    ),
    (
        "xbmc://localhost",
        {
            "instance": NotifyXBMC,
            # Experement with different notification types
            "notify_type": NotifyType.FAILURE,
        },
    ),
    (
        "xbmc://:@/",
        {
            "instance": None,
        },
    ),
    (
        "xbmc://user:pass@localhost:8081",
        {
            "instance": NotifyXBMC,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "xbmc://user:pass@localhost:8082",
        {
            "instance": NotifyXBMC,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "xbmc://user:pass@localhost:8083",
        {
            "instance": NotifyXBMC,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_xbmc_kodi_urls():
    """NotifyXBMC() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
