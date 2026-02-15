# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2026, Chris Caron <lead2gold@gmail.com>
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

from apprise import Apprise
from apprise.plugins import jellyfin

logging.disable(logging.CRITICAL)

# Our Testing URLs
# Note: The majority of tests are already handled by the emby:// adaptation

apprise_url_tests = (
    # Insecure Request; no hostname specified
    (
        "jellyfin://",
        {
            "instance": None,
        },
    ),
    # Secure Request; no hostname specified
    (
        "jellyfins://",
        {
            "instance": None,
        },
    ),
    # No user specified
    (
        "jellyfin://localhost",
        {
            # Missing a username
            "instance": TypeError,
        },
    ),
    (
        "jellyfin://:@/",
        {
            "instance": None,
        },
    ),
    # Valid Authentication (we do not validate credentials here)
    (
        "jellyfin://l2g@localhost",
        {
            "instance": jellyfin.NotifyJellyfin,
            # Authentication can't be validated through these unit tests
            "response": False,
        },
    ),
    (
        "jellyfins://l2g:password@localhost",
        {
            "instance": jellyfin.NotifyJellyfin,
            "response": False,
            "privacy_url": "jellyfins://l2g:****@localhost",
        },
    ),
)


def test_plugin_jellyfin_urls():
    """NotifyJellyfin() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_jellyfin_instantiation():
    """NotifyJellyfin() instantiation tests."""

    obj = Apprise.instantiate("jellyfin://l2g:l2gpass@localhost")
    assert isinstance(obj, jellyfin.NotifyJellyfin)

    obj = Apprise.instantiate("jellyfins://l2g:l2gpass@localhost")
    assert isinstance(obj, jellyfin.NotifyJellyfin)
