# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Chris Caron <lead2gold@gmail.com>
# All rights reserved.
#
# This code is licensed under the MIT License.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files(the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and / or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions :
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
import pytest
import requests
from apprise import plugins
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
        'instance': plugins.NotifyMattermost,
    }),
    ('mmost://user@localhost/3ccdd113474722377935511fc85d3dd4?channel=test', {
        'instance': plugins.NotifyMattermost,
    }),
    ('mmost://user@localhost/3ccdd113474722377935511fc85d3dd4?to=test', {
        'instance': plugins.NotifyMattermost,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'mmost://user@localhost/3...4/',
    }),
    ('mmost://localhost/3ccdd113474722377935511fc85d3dd4'
     '?to=test&image=True', {
         'instance': plugins.NotifyMattermost}),
    ('mmost://localhost/3ccdd113474722377935511fc85d3dd4' \
     '?to=test&image=False', {
         'instance': plugins.NotifyMattermost}),
    ('mmost://localhost/3ccdd113474722377935511fc85d3dd4' \
     '?to=test&image=True', {
         'instance': plugins.NotifyMattermost,
         # don't include an image by default
         'include_image': False}),
    ('mmost://localhost:8080/3ccdd113474722377935511fc85d3dd4', {
        'instance': plugins.NotifyMattermost,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'mmost://localhost:8080/3...4/',
    }),
    ('mmost://localhost:8080/3ccdd113474722377935511fc85d3dd4', {
        'instance': plugins.NotifyMattermost,
    }),
    ('mmost://localhost:invalid-port/3ccdd113474722377935511fc85d3dd4', {
        'instance': None,
    }),
    ('mmosts://localhost/3ccdd113474722377935511fc85d3dd4', {
        'instance': plugins.NotifyMattermost,
    }),
    # Test our paths
    ('mmosts://localhost/a/path/3ccdd113474722377935511fc85d3dd4', {
        'instance': plugins.NotifyMattermost,
    }),
    ('mmosts://localhost/////3ccdd113474722377935511fc85d3dd4///', {
        'instance': plugins.NotifyMattermost,
    }),
    ('mmost://localhost/3ccdd113474722377935511fc85d3dd4', {
        'instance': plugins.NotifyMattermost,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('mmost://localhost/3ccdd113474722377935511fc85d3dd4', {
        'instance': plugins.NotifyMattermost,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('mmost://localhost/3ccdd113474722377935511fc85d3dd4', {
        'instance': plugins.NotifyMattermost,
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
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Invalid Authorization Token
    with pytest.raises(TypeError):
        plugins.NotifyMattermost(None)
    with pytest.raises(TypeError):
        plugins.NotifyMattermost("     ")
