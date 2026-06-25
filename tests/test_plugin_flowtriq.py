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
import pytest
import requests

from apprise.plugins.flowtriq import NotifyFlowtriq

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "flowtriq://",
        {
            "instance": None,
        },
    ),
    # No webhook path specified
    (
        "flowtriq://apikey@hostname",
        {
            "instance": TypeError,
        },
    ),
    # No API key specified
    (
        "flowtriq://hostname/hooks/abc123",
        {
            "instance": TypeError,
        },
    ),
    # Provide a hostname, apikey, and webhook path
    (
        "flowtriq://myapikey@hostname/hooks/abc123/",
        {
            "instance": NotifyFlowtriq,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "flowtriq://m...y@hostname/hooks/abc123/",
        },
    ),
    # Provide a hostname with port
    (
        "flowtriq://myapikey@hostname:8443/hooks/abc123/",
        {
            "instance": NotifyFlowtriq,
        },
    ),
    # Multi-segment webhook path
    (
        "flowtriq://myapikey@flowtriq.com/api/v1/webhook/xyz/",
        {
            "instance": NotifyFlowtriq,
        },
    ),
    # An invalid url
    (
        "flowtriq://:@/",
        {
            "instance": None,
        },
    ),
    # Test failure cases
    (
        "flowtriq://myapikey@hostname/hooks/abc123/",
        {
            "instance": NotifyFlowtriq,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "flowtriq://myapikey@hostname/hooks/abc123/",
        {
            "instance": NotifyFlowtriq,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "flowtriq://myapikey@hostname/hooks/abc123/",
        {
            "instance": NotifyFlowtriq,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_flowtriq_urls():
    """NotifyFlowtriq() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_flowtriq_edge_cases():
    """NotifyFlowtriq() Edge Cases."""
    # Initializes the plugin with an invalid API key
    with pytest.raises(TypeError):
        NotifyFlowtriq(apikey=None, webhook_path="hooks/abc123")
    # Whitespace also acts as an invalid API key
    with pytest.raises(TypeError):
        NotifyFlowtriq(apikey="   ", webhook_path="hooks/abc123")

    # Missing webhook path
    with pytest.raises(TypeError):
        NotifyFlowtriq(apikey="validkey", webhook_path=None)
    with pytest.raises(TypeError):
        NotifyFlowtriq(apikey="validkey", webhook_path="   ")
