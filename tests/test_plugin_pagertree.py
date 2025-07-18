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
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise.plugins.pagertree import NotifyPagerTree

logging.disable(logging.CRITICAL)

# a test UUID we can use
INTEGRATION_ID = "int_xxxxxxxxxxx"

# Our Testing URLs
apprise_url_tests = (
    (
        "pagertree://",
        {
            # Missing Integration ID
            "instance": TypeError,
        },
    ),
    # Invalid Integration ID
    (
        "pagertree://%s" % ("+" * 24),
        {
            "instance": TypeError,
        },
    ),
    # Minimum requirements met
    (
        f"pagertree://{INTEGRATION_ID}",
        {
            "instance": NotifyPagerTree,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "pagertree://i...x?",
        },
    ),
    # change the integration id
    (
        f"pagertree://{INTEGRATION_ID}?integration=int_yyyyyyyyyy",
        {
            "instance": NotifyPagerTree,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "pagertree://i...y?",
        },
    ),
    # entries specified on the URL will over-ride the host (integration id)
    (
        f"pagertree://{INTEGRATION_ID}?id=int_zzzzzzzzzz",
        {
            "instance": NotifyPagerTree,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "pagertree://i...z?",
        },
    ),
    # Integration ID + bad url
    (
        "pagertree://:@/",
        {
            "instance": TypeError,
        },
    ),
    (
        f"pagertree://{INTEGRATION_ID}",
        {
            "instance": NotifyPagerTree,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        f"pagertree://{INTEGRATION_ID}",
        {
            "instance": NotifyPagerTree,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        f"pagertree://{INTEGRATION_ID}",
        {
            "instance": NotifyPagerTree,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
    (
        f"pagertree://{INTEGRATION_ID}?urgency=low",
        {
            # urgency override
            "instance": NotifyPagerTree,
        },
    ),
    (
        f"pagertree://?id={INTEGRATION_ID}&urgency=low",
        {
            # urgency override and id= (for integration)
            "instance": NotifyPagerTree,
        },
    ),
    (
        f"pagertree://{INTEGRATION_ID}?tags=production,web",
        {
            # tags
            "instance": NotifyPagerTree,
        },
    ),
    (
        f"pagertree://{INTEGRATION_ID}?action=resolve&thirdparty=123",
        {
            # test resolve
            "instance": NotifyPagerTree,
        },
    ),
    # Custom values
    (
        f"pagertree://{INTEGRATION_ID}?+pagertree-token=123&:env=prod&-m=v",
        {
            # minimum requirements and support custom key/value pairs
            "instance": NotifyPagerTree,
        },
    ),
)


def test_plugin_pagertree_urls():
    """NotifyPagerTree() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_pagertree_general(mock_post):
    """NotifyPagerTree() General Checks."""

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    # Invalid thirdparty id
    with pytest.raises(TypeError):
        NotifyPagerTree(integration=INTEGRATION_ID, thirdparty="   ")
