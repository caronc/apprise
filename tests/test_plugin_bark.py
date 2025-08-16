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

from apprise.plugins.bark import NotifyBark

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "bark://",
        {
            # No no host
            "instance": None,
        },
    ),
    (
        "bark://:@/",
        {
            # just invalid all around
            "instance": None,
        },
    ),
    (
        "bark://localhost",
        {
            # No Device Key specified
            "instance": NotifyBark,
            # Expected notify() response False (because we won't be able
            # to actually notify anything if no device_key was specified
            "notify_response": False,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key",
        {
            # Everything is okay
            "instance": NotifyBark,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "bark://192.168.0.6:8081/",
        },
    ),
    (
        "bark://user@192.168.0.6:8081/device_key",
        {
            # Everything is okay (test with user)
            "instance": NotifyBark,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "bark://user@192.168.0.6:8081/",
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?sound=invalid",
        {
            # bad sound, but we go ahead anyway
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?sound=alarm",
        {
            # alarm.caf sound loaded
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?sound=NOiR.cAf",
        {
            # noir.caf sound loaded
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?badge=100",
        {
            # set badge
            "instance": NotifyBark,
        },
    ),
    (
        "barks://192.168.0.6:8081/device_key/?badge=invalid",
        {
            # set invalid badge
            "instance": NotifyBark,
        },
    ),
    (
        "barks://192.168.0.6:8081/device_key/?badge=-12",
        {
            # set invalid badge
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?category=apprise",
        {
            # set category
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?image=no",
        {
            # do not display image
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?group=apprise",
        {
            # set group
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?level=invalid",
        {
            # bad level, but we go ahead anyway
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/?to=device_key",
        {
            # test use of to= argument
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?click=http://localhost",
        {
            # Our click link
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?level=active",
        {
            # active level
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?level=critical",
        {
            # critical level
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?level=critical&volume=10",
        {
            # critical level with volume 10
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?level=critical&volume=invalid",
        {
            # critical level with invalid volume
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?level=critical&volume=11",
        {
            # volume > 10
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?level=critical&volume=-1",
        {
            # volume < 0
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?level=critical&volume=",
        {
            # volume None
            "instance": NotifyBark,
        },
    ),
    (
        "bark://user:pass@192.168.0.5:8086/device_key/device_key2/",
        {
            # Everything is okay
            "instance": NotifyBark,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "bark://user:****@192.168.0.5:8086/",
        },
    ),
    (
        "barks://192.168.0.7/device_key/",
        {
            "instance": NotifyBark,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "barks://192.168.0.7/device_key",
        },
    ),
    (
        "bark://192.168.0.7/device_key",
        {
            "instance": NotifyBark,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?icon=https://example.com/icon.png",
        {
            # set custom icon
            "instance": NotifyBark,
        },
    ),
    (
        "bark://192.168.0.6:8081/device_key/?icon=https://example.com/icon.png&image=no",
        {
            # set custom icon and disable default image
            "instance": NotifyBark,
        },
    ),
)


def test_plugin_bark_urls():
    """NotifyBark() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
