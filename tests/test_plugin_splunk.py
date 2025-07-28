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
import requests

from apprise.plugins.splunk import NotifySplunk

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "splunk://",
        {
            "instance": TypeError,
        },
    ),
    (
        "splunk://:@/",
        {
            "instance": TypeError,
        },
    ),
    (
        "splunk://routekey@%badapi%",
        {
            "instance": TypeError,
        },
    ),
    (
        "splunk://abc123",
        {
            # No route key provided
            "instance": TypeError,
        },
    ),
    (
        "splunk://%badroute%@apikey",
        {
            "instance": TypeError,
        },
    ),
    (
        "splunk://?apikey=abc123&routing_key=db",
        {
            # We're good
            "instance": NotifySplunk,
        },
    ),
    (
        "splunk://route@abc123/entity_id",
        {
            # We're good
            "instance": NotifySplunk,
        },
    ),
    (
        "splunk://route@abc123/?entity_id=my_entity",
        {
            # We're good
            "instance": NotifySplunk,
        },
    ),
    # Support legacy URL
    (
        (
            "https://alert.victorops.com/integrations/generic/20131114/"
            "alert/apikey/routing_key"
        ),
        {
            # We're good
            "instance": NotifySplunk,
        },
    ),
    # Support legacy URL (with entity id provided)
    (
        (
            "https://alert.victorops.com/integrations/generic/20131114/"
            "alert/apikey/routing_key/entity_id"
        ),
        {
            # We're good
            "instance": NotifySplunk,
        },
    ),
    # support victorops:// too!
    (
        "victorops://?apikey=abc123&route=db",
        {
            # We're good
            "instance": NotifySplunk,
        },
    ),
    (
        "splunk://?apikey=abc123&route=db",
        {
            # We're good
            "instance": NotifySplunk,
        },
    ),
    (
        "splunk://db@apikey?action=recovery",
        {
            # Always Recovery Alias
            "instance": NotifySplunk,
        },
    ),
    (
        "splunk://db@apikey?action=resolve",
        {
            # Always Recovery Alias
            "instance": NotifySplunk,
        },
    ),
    (
        "splunk://db@apikey?action=r",
        {
            # Always Recovery (short form)
            "instance": NotifySplunk,
        },
    ),
    (
        "splunk://db@apikey?action=acknowledgement",
        {
            # Always Acknowledgement
            "instance": NotifySplunk,
        },
    ),
    (
        "splunk://db@apikey?action=ack",
        {
            # Always Acknowledgement (short form)
            "instance": NotifySplunk,
        },
    ),
    (
        "splunk://db@apikey?action=critical",
        {
            # Always Critical
            "instance": NotifySplunk,
        },
    ),
    (
        "splunk://db@apikey?action=crit",
        {
            # Always Critical (short form)
            "instance": NotifySplunk,
        },
    ),
    (
        "splunk://db@apikey?action=warning",
        {
            # Always Warning
            "instance": NotifySplunk,
        },
    ),
    (
        "splunk://db@apikey?action=warn",
        {
            # Always Warning (short form)
            "instance": NotifySplunk,
        },
    ),
    (
        "splunk://db@apikey?action=info",
        {
            # Always INFO
            "instance": NotifySplunk,
        },
    ),
    (
        "splunk://db@apikey?action=i",
        {
            # Always INFO (short form)
            "instance": NotifySplunk,
        },
    ),
    (
        "splunk://db@apikey?action=invalid",
        {
            # Invalid Action
            "instance": TypeError,
        },
    ),
    (
        "splunk://db@apikey?:warning=critical",
        {
            # Map warnings to CRITICAL
            "instance": NotifySplunk,
        },
    ),
    (
        "splunk://db@apikey?:invalid=critical",
        {
            # A bad Apprise Notification Type was provided
            "instance": TypeError,
        },
    ),
    (
        "splunk://db@apikey?:warning=invalid",
        {
            # A bad Splunk Notification Type was provided
            "instance": TypeError,
        },
    ),
    (
        "splunk://db@apikey",
        {
            "instance": NotifySplunk,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "splunk://db@apikey",
        {
            "instance": NotifySplunk,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "splunk://db@token",
        {
            "instance": NotifySplunk,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_splunk_urls():
    """NotifySplunk() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()
