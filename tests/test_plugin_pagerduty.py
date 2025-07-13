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

from apprise.plugins.pagerduty import NotifyPagerDuty

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "pagerduty://",
        {
            # No Access Token or Integration/Routing Key specified
            "instance": TypeError,
        },
    ),
    (
        "pagerduty://%20@%20/",
        {
            # invalid Access Token and Integration/Routing Key
            "instance": TypeError,
        },
    ),
    (
        "pagerduty://%20/",
        {
            # invalid Access Token; no Integration/Routing Key
            "instance": TypeError,
        },
    ),
    (
        "pagerduty://%20@abcd/",
        {
            # Invalid Integration/Routing Key (but valid Access Token)
            "instance": TypeError,
        },
    ),
    (
        "pagerduty://myroutekey@myapikey/%20",
        {
            # bad source
            "instance": TypeError,
        },
    ),
    (
        "pagerduty://myroutekey@myapikey/mysource/%20",
        {
            # bad component
            "instance": TypeError,
        },
    ),
    (
        "pagerduty://myroutekey@myapikey?region=invalid",
        {
            # invalid region
            "instance": TypeError,
        },
    ),
    (
        "pagerduty://myroutekey@myapikey?severity=invalid",
        {
            # invalid severity
            "instance": TypeError,
        },
    ),
    (
        "pagerduty://myroutekey@myapikey",
        {
            # minimum requirements met
            "instance": NotifyPagerDuty,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "pagerduty://****@****/A...e/N...n?",
        },
    ),
    (
        "pagerduty://myroutekey@myapikey?image=no",
        {
            # minimum requirements met and disable images
            "instance": NotifyPagerDuty,
        },
    ),
    (
        "pagerduty://myroutekey@myapikey?region=eu",
        {
            # european region
            "instance": NotifyPagerDuty,
        },
    ),
    (
        "pagerduty://myroutekey@myapikey?severity=critical",
        {
            # Severity over-ride
            "instance": NotifyPagerDuty,
        },
    ),
    (
        "pagerduty://myroutekey@myapikey?severity=err",
        {
            # Severity over-ride (short-form)
            "instance": NotifyPagerDuty,
        },
    ),
    # Custom values
    (
        "pagerduty://myroutekey@myapikey?+key=value&+key2=value2",
        {
            # minimum requirements and support custom key/value pairs
            "instance": NotifyPagerDuty,
        },
    ),
    (
        "pagerduty://myroutekey@myapikey/mysource/mycomponent",
        {
            # a valid url
            "instance": NotifyPagerDuty,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "pagerduty://****@****/m...e/m...t?",
        },
    ),
    (
        "pagerduty://routekey@apikey/ms/mc?group=mygroup&class=myclass",
        {
            # class/group testing
            "instance": NotifyPagerDuty,
        },
    ),
    (
        (
            "pagerduty://?integrationkey=r&apikey=a&source=s&component=c"
            "&group=g&class=c&image=no&click=http://localhost"
        ),
        {
            # all parameters
            "instance": NotifyPagerDuty
        },
    ),
    (
        "pagerduty://somerkey@someapikey/bizzare/code",
        {
            "instance": NotifyPagerDuty,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "pagerduty://myroutekey@myapikey/mysource/mycomponent",
        {
            "instance": NotifyPagerDuty,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_pagerduty_urls():
    """NotifyPagerDuty() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
