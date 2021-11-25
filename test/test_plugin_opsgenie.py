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
from apprise import plugins
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# a test UUID we can use
UUID4 = '8b799edf-6f98-4d3a-9be7-2862fb4e5752'

# Our Testing URLs
apprise_url_tests = (
    ('opsgenie://', {
        # We failed to identify any valid authentication
        'instance': TypeError,
    }),
    ('opsgenie://:@/', {
        # We failed to identify any valid authentication
        'instance': TypeError,
    }),
    ('opsgenie://%20%20/', {
        # invalid apikey specified
        'instance': TypeError,
    }),
    ('opsgenie://apikey/user/?region=xx', {
        # invalid region id
        'instance': TypeError,
    }),
    ('opsgenie://apikey/', {
        # No targets specified; this is allowed
        'instance': plugins.NotifyOpsgenie,
    }),
    ('opsgenie://apikey/user', {
        # Valid user
        'instance': plugins.NotifyOpsgenie,
        'privacy_url': 'opsgenie://a...y/%40user',
    }),
    ('opsgenie://apikey/@user?region=eu', {
        # European Region
        'instance': plugins.NotifyOpsgenie,
    }),
    ('opsgenie://apikey/@user?entity=A%20Entity', {
        # Assign an entity
        'instance': plugins.NotifyOpsgenie,
    }),
    ('opsgenie://apikey/@user?alias=An%20Alias', {
        # Assign an alias
        'instance': plugins.NotifyOpsgenie,
    }),
    ('opsgenie://apikey/@user?priority=p3', {
        # Assign our priority
        'instance': plugins.NotifyOpsgenie,
    }),
    ('opsgenie://apikey/?tags=comma,separated', {
        # Test our our 'tags' (tag is reserved in Apprise) but not 'tags'
        # Also test the fact we do not need to define a target
        'instance': plugins.NotifyOpsgenie,
    }),
    ('opsgenie://apikey/@user?priority=invalid', {
        # Invalid priority (loads using default)
        'instance': plugins.NotifyOpsgenie,
    }),
    ('opsgenie://apikey/user@email.com/#team/*sche/^esc/%20/a', {
        # Valid user (email), valid schedule, Escalated ID,
        # an invalid entry (%20), and too short of an entry (a)
        'instance': plugins.NotifyOpsgenie,
    }),
    ('opsgenie://apikey/{}/@{}/#{}/*{}/^{}/'.format(
        UUID4, UUID4, UUID4, UUID4, UUID4), {
        # similar to the above, except we use the UUID's
        'instance': plugins.NotifyOpsgenie,
    }),
    ('opsgenie://apikey?to=#team,user&+key=value&+type=override', {
        # Test to= and details (key/value pair) also override 'type'
        'instance': plugins.NotifyOpsgenie,
    }),
    ('opsgenie://apikey/#team/@user/?batch=yes', {
        # Test batch=
        'instance': plugins.NotifyOpsgenie,
    }),
    ('opsgenie://apikey/#team/@user/?batch=no', {
        # Test batch=
        'instance': plugins.NotifyOpsgenie,
    }),
    ('opsgenie://?apikey=abc&to=user', {
        # Test Kwargs
        'instance': plugins.NotifyOpsgenie,
    }),
    ('opsgenie://apikey/#team/user/', {
        'instance': plugins.NotifyOpsgenie,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('opsgenie://apikey/#topic1/device/', {
        'instance': plugins.NotifyOpsgenie,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_opsgenie_urls():
    """
    NotifyOpsgenie() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
