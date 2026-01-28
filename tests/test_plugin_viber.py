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

from json import dumps
import logging

from helpers import AppriseURLTester
import requests

from apprise import Apprise
from apprise.plugins.viber import NotifyViber

logging.disable(logging.CRITICAL)

VIBER_GOOD_RESPONSE = dumps({"status":0,"status_message":"ok"})
VIBER_BAD_RESPONSE = dumps(
    {"status": 12, "status_message": "Too many requests"})

# Our Testing URLs
apprise_url_tests = (
    ("viber://", False),
    ("viber:///", False),
    ("viber://tokena", {
        "instance": NotifyViber,
        "notify_response": False}),
    ("viber://?token=tokenb", {
        "instance": NotifyViber,
        "notify_response": False}),
    ("viber://token/targetx", {
        "instance": NotifyViber,
        # Our response expected server response
        "requests_response_text": VIBER_GOOD_RESPONSE}),
    ("viber://token/t1/t2?from=Viber%20Bot", {
        "instance": NotifyViber,
        "requests_response_text": VIBER_GOOD_RESPONSE}),
    ("viber://t1/t2?token=token", {
        "instance": NotifyViber,
        "requests_response_text": VIBER_GOOD_RESPONSE}),
    ("viber://?token=token&to=t5", {
        "instance": NotifyViber,
        "requests_response_text": VIBER_GOOD_RESPONSE}),
    ("viber://token/t3?avatar=value", {
        "instance": NotifyViber,
        "requests_response_text": VIBER_GOOD_RESPONSE}),
    ("viber://token/?to=abc,def", {
        "instance": NotifyViber,
        "requests_response_text": VIBER_GOOD_RESPONSE}),
    ("viber://token/m12/?from={}".format(
        "a" * (NotifyViber.viber_sender_name_limit + 1)), {
            "instance": NotifyViber,
            "requests_response_text": VIBER_GOOD_RESPONSE}),
    ("viber://token/m12/?from={}".format(
        "b" * (NotifyViber.viber_sender_name_limit)), {
            "instance": NotifyViber,
            "requests_response_text": VIBER_GOOD_RESPONSE}),
    ("viber://?token=token&to=hij,klm", {
        "instance": NotifyViber,
        "requests_response_text": VIBER_GOOD_RESPONSE}),
    ("viber://?token=token&to=nop,qrs", {
        "instance": NotifyViber,
        "requests_response_text": VIBER_BAD_RESPONSE,
        "notify_response": False}),
    ("viber://?token=token&to=tuv,wxy", {
        "instance": NotifyViber,
        # Bad JSON
        "requests_response_text": "{",
        "notify_response": False}),

    # Privacy redaction of token
    ("viber://token/t10", {
        "instance": NotifyViber,
        "requests_response_text": VIBER_GOOD_RESPONSE,
        "privacy_url": "viber://****/t10"}),
    (
        "viber://token/targetZ",
        {
            "instance": NotifyViber,
            # throw a bizarre code forcing us to fail to look it up
            "requests_response_text": VIBER_GOOD_RESPONSE,
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "viber://token/targetZ",
        {
            "instance": NotifyViber,
            # force a failure
            "response": False,
            "requests_response_text": VIBER_BAD_RESPONSE,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "viber://token/targetY",
        {
            "instance": NotifyViber,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "requests_response_text": VIBER_GOOD_RESPONSE,
            "test_requests_exceptions": True,
        },
    )
)

def test_plugin_viber_urls():
    """Verify URL parsing, privacy, and basic validation."""
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_viber_http_error_and_exception(mocker):
    """Verify HTTP error and requests exception paths."""
    post = mocker.patch("requests.post")

    post.return_value.status_code = 400
    a = Apprise()
    assert a.add("viber://token/target2") is True
    assert a.notify("test") is False

    post.side_effect = requests.RequestException("boom")
    a = Apprise()
    assert a.add("viber://token/target2") is True
    assert a.notify("test") is False
