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

from apprise.plugins.dot import NotifyDot

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "dot://",
        {
            # No API key or device ID
            "instance": None,
        },
    ),
    (
        "dot://@",
        {
            # No device ID
            "instance": None,
        },
    ),
    (
        "dot://apikey@",
        {
            # No device ID
            "instance": None,
        },
    ),
    (
        "dot://@device_id",
        {
            # No API key
            "instance": NotifyDot,
            # Expected notify() response False (because we won't be able
            # to actually notify anything if no api key was specified
            "notify_response": False,
        },
    ),
    (
        "dot://apikey@device_id/text/",
        {
            # Everything is okay (text mode)
            "instance": NotifyDot,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "dot://****@device_id/text/",
        },
    ),
    (
        "dot://apikey@device_id/text/?refresh=no",
        {
            # Disable refresh now
            "instance": NotifyDot,
        },
    ),
    (
        "dot://apikey@device_id/text/?signature=test_signature",
        {
            # With signature
            "instance": NotifyDot,
        },
    ),
    (
        "dot://apikey@device_id/text/?link=https://example.com",
        {
            # With link
            "instance": NotifyDot,
        },
    ),
    (
        "dot://apikey@device_id/image/?link=https://example.com&border=1&dither_type=ORDERED&dither_kernel=ATKINSON",
        {
            # Image mode configuration (missing image data causes notify failure)
            "instance": NotifyDot,
            "notify_response": False,
        },
    ),
    (
        "dot://apikey@device_id/image/?image=ZmFrZUJhc2U2NA==&link=https://example.com&border=1&dither_type=DIFFUSION&dither_kernel=FLOYD_STEINBERG",
        {
            # Image mode with provided image data
            "instance": NotifyDot,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "dot://****@device_id/image/",
        },
    ),
    (
        "dot://apikey@device_id/text/",
        {
            "instance": NotifyDot,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "dot://apikey@device_id/text/",
        {
            "instance": NotifyDot,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
    (
        "dot://apikey@device_id/unknown/",
        {
            # Unknown mode defaults back to text
            "instance": NotifyDot,
            "privacy_url": "dot://****@device_id/text/",
        },
    ),
)


def test_plugin_dot_urls():
    """NotifyDot() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()

