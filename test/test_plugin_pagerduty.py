# -*- coding: utf-8 -*-
#
# Copyright (C) 2022 Chris Caron <lead2gold@gmail.com>
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

# Our Testing URLs
apprise_url_tests = (
    ('pagerduty://', {
        # No Access Token or Integration/Routing Key specified
        'instance': TypeError,
    }),
    ('pagerduty://%20@%20/', {
        # invalid Access Token and Integration/Routing Key
        'instance': TypeError,
    }),
    ('pagerduty://%20/', {
        # invalid Access Token; no Integration/Routing Key
        'instance': TypeError,
    }),
    ('pagerduty://%20@abcd/', {
        # Invalid Integration/Routing Key (but valid Access Token)
        'instance': TypeError,
    }),
    ('pagerduty://myroutekey@myapikey/%20', {
        # bad source
        'instance': TypeError,
    }),
    ('pagerduty://myroutekey@myapikey/mysource/%20', {
        # bad component
        'instance': TypeError,
    }),
    ('pagerduty://myroutekey@myapikey?region=invalid', {
        # invalid region
        'instance': TypeError,
    }),
    ('pagerduty://myroutekey@myapikey', {
        # minimum requirements met
        'instance': plugins.NotifyPagerDuty,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'pagerduty://****@****/A...e/N...n?',
    }),
    ('pagerduty://myroutekey@myapikey?image=no', {
        # minimum requirements met and disable images
        'instance': plugins.NotifyPagerDuty,
    }),
    ('pagerduty://myroutekey@myapikey?region=eu', {
        # european region
        'instance': plugins.NotifyPagerDuty,
    }),
    # Custom values
    ('pagerduty://myroutekey@myapikey?+key=value&+key2=value2', {
        # minimum requirements and support custom key/value pairs
        'instance': plugins.NotifyPagerDuty,
    }),
    ('pagerduty://myroutekey@myapikey/mysource/mycomponent', {
        # a valid url
        'instance': plugins.NotifyPagerDuty,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'pagerduty://****@****/m...e/m...t?',
    }),
    ('pagerduty://routekey@apikey/ms/mc?group=mygroup&class=myclass', {
        # class/group testing
        'instance': plugins.NotifyPagerDuty,
    }),
    ('pagerduty://?integrationkey=r&apikey=a&source=s&component=c'
        '&group=g&class=c&image=no&click=http://localhost', {
            # all parameters
            'instance': plugins.NotifyPagerDuty}),
    ('pagerduty://somerkey@someapikey/bizzare/code', {
        'instance': plugins.NotifyPagerDuty,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('pagerduty://myroutekey@myapikey/mysource/mycomponent', {
        'instance': plugins.NotifyPagerDuty,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_pagerduty_urls():
    """
    NotifyPagerDuty() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
