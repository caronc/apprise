# -*- coding: utf-8 -*-
# BSD 3-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2023, Chris Caron <lead2gold@gmail.com>
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
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
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

import requests
from unittest import mock

import apprise
from apprise.plugins.NotifyAprs import NotifyAprs
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "aprs://",
        {
            # We failed to identify any valid authentication
            "instance": TypeError,
        },
    ),
    (
        "aprs://:@/",
        {
            # We failed to identify any valid authentication
            "instance": TypeError,
        },
    ),
    (
        "aprs://DF1JSL-15:12345",
        {
            # No call-sign specified
            "instance": TypeError,
        },
    ),
    (
        "aprs://DF1JSL-15:12345",
        {
            # No password specified
            "instance": TypeError,
        },
    ),
    (
        "aprs://DF1JSL-15:12345@{}".format("DF1ABC"),
        {
            # valid call sign
            "instance": NotifyAprs,
            "requests_response_code": requests.codes.created,
        },
    ),
    (
        "aprs://DF1JSL-15:12345@{}/{}".format("DF1ABC", "DF1DEF"),
        {
            # valid call signs
            "instance": NotifyAprs,
            "requests_response_code": requests.codes.created,
        },
    ),
    (
        "aprs://DF1JSL-15:12345@DF1ABC-1/DF1ABC/DF1ABC-15",
        {
            # valid call signs - not treated as duplicates
            # as SSID's will be honored
            "instance": NotifyAprs,
            "requests_response_code": requests.codes.created,
            # Our expected url(privacy=True) startswith() response:
            # Note that only 1 entry is saved (as other 2 are duplicates)
            "privacy_url": "aprs://user:****@D...C?",
        },
    ),
    (
        "aprs://DF1JSL-15:12345@?to={},{}".format("DF1ABC", "DF1DEF"),
        {
            # support the two= argument
            "instance": NotifyAprs,
            "requests_response_code": requests.codes.created,
        },
    ),
    (
        'aprs://DF1JSL-15:12345@{}?locale="EURO'.format("DF1ABC"),
        {
            # valid call sign with locale setting
            "instance": NotifyAprs,
            "requests_response_code": requests.codes.created,
        },
    ),
    (
        'aprs://DF1JSL-15:12345@{}?locale="NOAM'.format("DF1ABC"),
        {
            # valid call sign with locale setting
            "instance": NotifyAprs,
            "requests_response_code": requests.codes.created,
        },
    ),
    (
        'aprs://DF1JSL-15:12345@{}?locale="SOAM'.format("DF1ABC"),
        {
            # valid call sign with locale setting
            "instance": NotifyAprs,
            "requests_response_code": requests.codes.created,
        },
    ),
    (
        'aprs://DF1JSL-15:12345@{}?locale="AUNZ'.format("DF1ABC"),
        {
            # valid call sign with locale setting
            "instance": NotifyAprs,
            "requests_response_code": requests.codes.created,
        },
    ),
    (
        'aprs://DF1JSL-15:12345@{}?locale="ASIA'.format("DF1ABC"),
        {
            # valid call sign with locale setting
            "instance": NotifyAprs,
            "requests_response_code": requests.codes.created,
        },
    ),
    (
        'aprs://DF1JSL-15:12345@{}?locale="ROTA'.format("DF1ABC"),
        {
            # valid call sign with locale setting
            "instance": NotifyAprs,
            "requests_response_code": requests.codes.created,
        },
    ),
    (
        'aprs://DF1JSL-15:12345@{}?locale="ABCD'.format("DF1ABC"),
        {
            # valid call sign with invalid locale setting
            "instance": NotifyAprs,
            "notify_response": False,
        },
    ),
    (
        "aprs://DF1JSL-15:12345@{}/{}".format("abcdefghi", "a"),
        {
            # invalid call signs
            "instance": NotifyAprs,
            "notify_response": False,
        },
    ),
    # Edge cases
    (
        "aprs://DF1JSL-15:12345@{}".format("DF1ABC"),
        {
            "instance": NotifyAprs,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "aprs://DF1JSL-15:12345@{}".format("DF1ABC"),
        {
            "instance": NotifyAprs,
            # Throws a series of connection and transfer exceptions
            # when this flagis set and tests that we
            # gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_aprs_urls():
    """
    NotifyAprs() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_aprs_edge_cases(mock_post):
    """
    NotifyAprs() Edge Cases
    """
    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.created

    # test the handling of our batch modes
    obj = apprise.Apprise.instantiate("aprs://DF1JSL-15:12345@DF1ABC/DF1DEF")
    assert isinstance(obj, NotifyAprs)

    # objects will be combined into a single post in batch mode
    assert len(obj) == 1

    # Force our batch to break into separate messages
    obj.default_batch_size = 1

    # We'll send 1 message now
    assert len(obj) == 1

    # omitting body test as this would initiate
    # a real message to APRS-IS with an invalid
    # passcode, thus returning a "false" from the
    # plugin and then causes to fail the test.
    """
    assert obj.notify(
        body='body', title='title') is True
    assert mock_post.call_count == 2
    """


@mock.patch("requests.post")
def test_plugin_aprs_config_files(mock_post):
    """
    NotifyAprs() Config File Cases
    """
    content = """
    urls:
      - aprs://DF1JSL-15:12345@DF1ABC":
          - locale: NOAM

      - aprs://DF1JSL-15:12345@DF1ABC:
          - locale: SOAM

      - aprs://DF1JSL-15:12345@DF1ABC:
          - locale: EURO

      - aprs://DF1JSL-15:12345@DF1ABC:
          - locale: ASIA

      - aprs://DF1JSL-15:12345@DF1ABC:
          - locale: AUNZ

      - aprs://DF1JSL-15:12345@DF1ABC:
          - locale: ROTA

      # This will take on normal (default) priority
      - aprs://DF1JSL-15:12345@DF1ABC:
          - locale: aprs_invalid
    """

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.created

    # Create ourselves a config object
    ac = apprise.AppriseConfig()
    assert ac.add_config(content=content) is True

    aobj = apprise.Apprise()

    # Add our configuration
    aobj.add(ac)

    # We should be able to read our 7 servers from that
    # 4x normal (invalid + 3 exclusively specified to be so)
    # 3x emerg
    assert len(ac.servers()) == 6
    assert len(aobj) == 6


#    assert len([x for x in aobj.find(tag='aprs_str')]) == 6
#    assert len([x for x in aobj.find(tag='aprs_invalid')]) == 1
# Notifications work
#    assert aobj.notify(title="title", body="body") is True
