# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2024, Chris Caron <lead2gold@gmail.com>
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

import pytest
import requests

from apprise.plugins.NotifyMattermost import NotifyMattermost
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('mmost://', {
        'instance': None,
    }),
    ('mmosts://', {
        'instance': None,
    }),
    ('mmost://:@/', {
        'instance': None,
    }),
    ('mmosts://localhost', {
        # Thrown because there was no webhook id specified
        'instance': TypeError,
    }),
    ('mmost://localhost/3ccdd113474722377935511fc85d3dd4', {
        'instance': NotifyMattermost,
    }),
    ('mmost://user@localhost/3ccdd113474722377935511fc85d3dd4?channel=test', {
        'instance': NotifyMattermost,
    }),
    ('mmost://user@localhost/3ccdd113474722377935511fc85d3dd4?to=test', {
        'instance': NotifyMattermost,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'mmost://user@localhost/3...4/',
    }),
    ('mmost://localhost/3ccdd113474722377935511fc85d3dd4'
     '?to=test&image=True', {
         'instance': NotifyMattermost}),
    ('mmost://localhost/3ccdd113474722377935511fc85d3dd4' \
     '?to=test&image=False', {
         'instance': NotifyMattermost}),
    ('mmost://localhost/3ccdd113474722377935511fc85d3dd4' \
     '?to=test&image=True', {
         'instance': NotifyMattermost,
         # don't include an image by default
         'include_image': False}),
    ('mmost://localhost:8080/3ccdd113474722377935511fc85d3dd4', {
        'instance': NotifyMattermost,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'mmost://localhost:8080/3...4/',
    }),
    ('mmost://localhost:8080/3ccdd113474722377935511fc85d3dd4', {
        'instance': NotifyMattermost,
    }),
    ('mmost://localhost:invalid-port/3ccdd113474722377935511fc85d3dd4', {
        'instance': None,
    }),
    ('mmosts://localhost/3ccdd113474722377935511fc85d3dd4', {
        'instance': NotifyMattermost,
    }),
    # Test our paths
    ('mmosts://localhost/a/path/3ccdd113474722377935511fc85d3dd4', {
        'instance': NotifyMattermost,
    }),
    ('mmosts://localhost/////3ccdd113474722377935511fc85d3dd4///', {
        'instance': NotifyMattermost,
    }),
    ('mmost://localhost/3ccdd113474722377935511fc85d3dd4', {
        'instance': NotifyMattermost,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('mmost://localhost/3ccdd113474722377935511fc85d3dd4', {
        'instance': NotifyMattermost,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('mmost://localhost/3ccdd113474722377935511fc85d3dd4', {
        'instance': NotifyMattermost,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_mattermost_urls():
    """
    NotifyMattermost() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_mattermost_edge_cases():
    """
    NotifyMattermost() Edge Cases

    """

    # Invalid Authorization Token
    with pytest.raises(TypeError):
        NotifyMattermost(None)
    with pytest.raises(TypeError):
        NotifyMattermost("     ")
