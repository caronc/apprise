# -*- coding: utf-8 -*-
#
# Apprise - Push Notification Library.
# Copyright (C) 2023  Chris Caron <lead2gold@gmail.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor,
# Boston, MA  02110-1301, USA.
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
