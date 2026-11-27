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
import json
import logging
from unittest import mock

from helpers import AppriseURLTester
import requests

from apprise import Apprise
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.parseplatform import NotifyParsePlatform

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "parsep://",
        {
            "instance": None,
        },
    ),
    # API Key + bad url
    (
        "parsep://:@/",
        {
            "instance": None,
        },
    ),
    # APIkey; no app_id or master_key
    (
        "parsep://%s" % ("a" * 32),
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    # APIkey; no master_key
    (
        "parsep://app_id@%s" % ("a" * 32),
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    # APIkey; no app_id
    (
        "parseps://:master_key@%s" % ("a" * 32),
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    # app_id + master_key (using arguments=)
    (
        "parseps://localhost?app_id={}&master_key={}".format(
            "a" * 32, "d" * 32
        ),
        {
            "instance": NotifyParsePlatform,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "parseps://a...a:d...d@localhost",
        },
    ),
    # Set a device id + custom port
    (
        "parsep://app_id:master_key@localhost:8080?device=ios",
        {
            "instance": NotifyParsePlatform,
        },
    ),
    # invalid device id
    (
        "parsep://app_id:master_key@localhost?device=invalid",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    # Normal Query
    (
        "parseps://app_id:master_key@localhost",
        {
            "instance": NotifyParsePlatform,
        },
    ),
    (
        "parseps://app_id:master_key@localhost",
        {
            "instance": NotifyParsePlatform,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "parseps://app_id:master_key@localhost",
        {
            "instance": NotifyParsePlatform,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "parseps://app_id:master_key@localhost",
        {
            "instance": NotifyParsePlatform,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_parse_platform_urls():
    """NotifyParsePlatform() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_parse_platform_device_case(mock_post):
    """NotifyParsePlatform() accepts device= in any case."""

    mock_post.return_value = mock.Mock()
    mock_post.return_value.status_code = requests.codes.ok

    obj = Apprise.instantiate(
        "parseps://app_id:master_key@localhost?device=IOS"
    )
    assert isinstance(obj, NotifyParsePlatform)
    assert obj.device == "ios"

    # The normalized device is what gets sent
    assert obj.notify(body="body") is True
    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["where"]["deviceType"]["$in"] == ["ios"]

    # Surrounding whitespace is accepted too
    obj = NotifyParsePlatform(
        app_id="app_id",
        master_key="master_key",
        host="localhost",
        device=" Android ",
    )
    assert obj.devices == ["android"]

    # The normalized value is written back by url()
    obj2 = Apprise.instantiate(obj.url())
    assert isinstance(obj2, NotifyParsePlatform)
    assert obj2.device == "android"

    # All devices
    obj = Apprise.instantiate(
        "parseps://app_id:master_key@localhost?device=All"
    )
    assert isinstance(obj, NotifyParsePlatform)
    assert obj.devices == ["ios", "android"]
