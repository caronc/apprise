#
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

import logging

from helpers import AppriseURLTester
import requests

from apprise.plugins.spugpush import NotifySpugpush

logging.disable(logging.CRITICAL)

apprise_url_tests = (
    (
        "spugpush://",
        {
            "instance": TypeError,
        },
    ),
    (
        "spugpush://invalid!",
        {
            "instance": TypeError,
        },
    ),
    (
        "spugpush://abc123def456ghi789jkl012mno345pq",
        {
            "instance": NotifySpugpush,
            "privacy_url": "spugpush://****/",
        },
    ),
    (
        "spugpush://?token=abc123def456ghi789jkl012mno345pq",
        {
            "instance": NotifySpugpush,
            "privacy_url": "spugpush://****/",
        },
    ),
    (
        "https://push.spug.dev/send/abc123def456ghi789jkl012mno345pq",
        {
            "instance": NotifySpugpush,
        },
    ),
    (
        "spugpush://abc123def456ghi789jkl012mno345pq",
        {
            "instance": NotifySpugpush,
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "spugpush://abc123def456ghi789jkl012mno345pq",
        {
            "instance": NotifySpugpush,
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "spugpush://ffffffffffffffffffffffffffffffff",
        {
            "instance": NotifySpugpush,
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_spugpush_urls():
    AppriseURLTester(tests=apprise_url_tests).run_all()
