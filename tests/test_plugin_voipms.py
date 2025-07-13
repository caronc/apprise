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

# Disable logging for a cleaner testing output
import logging
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise
from apprise.plugins.voipms import NotifyVoipms

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "voipms://",
        {
            # No email/password specified
            "instance": TypeError,
        },
    ),
    (
        "voipms://@:",
        {
            # Invalid url
            "instance": TypeError,
        },
    ),
    (
        "voipms://{}/{}".format("user@example.com", "1" * 11),
        {
            # No password specified
            "instance": TypeError,
        },
    ),
    (
        "voipms://:{}".format("password"),
        {
            # No email specified
            "instance": TypeError,
        },
    ),
    (
        "voipms://{}:{}/{}".format("user@", "pass", "1" * 11),
        {
            # Check valid email
            "instance": TypeError,
        },
    ),
    (
        "voipms://{password}:{email}".format(
            email="user@example.com", password="password"
        ),
        {
            # No from_phone specified
            "instance": TypeError,
        },
    ),
    # Invalid phone number test
    (
        "voipms://{password}:{email}/1613".format(
            email="user@example.com", password="password"
        ),
        {
            # Invalid phone number
            "instance": TypeError,
        },
    ),
    # Invalid country code phone number test
    (
        "voipms://{password}:{email}/01133122446688".format(
            email="user@example.com", password="password"
        ),
        {
            # Non North American phone number
            "instance": TypeError,
        },
    ),
    (
        "voipms://{password}:{email}/{from_phone}/{targets}/".format(
            email="user@example.com",
            password="password",
            from_phone="16134448888",
            targets="/".join(["26134442222"]),
        ),
        {
            # Invalid target phone number
            "instance": NotifyVoipms,
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "voipms://{password}:{email}/{from_phone}".format(
            email="user@example.com",
            password="password",
            from_phone="16138884444",
        ),
        {
            "instance": NotifyVoipms,
            # No targets specified
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "voipms://{password}:{email}/?from={from_phone}".format(
            email="user@example.com",
            password="password",
            from_phone="16138884444",
        ),
        {
            "instance": NotifyVoipms,
            # No targets specified
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "voipms://{password}:{email}/{from_phone}/{targets}/".format(
            email="user@example.com",
            password="password",
            from_phone="16138884444",
            targets="/".join(["16134442222"]),
        ),
        {
            # Valid
            "instance": NotifyVoipms,
            "response": True,
            "privacy_url": "voipms://p...d:user@example.com/16...4",
        },
    ),
    (
        "voipms://{password}:{email}/{from_phone}/{targets}/".format(
            email="user@example.com",
            password="password",
            from_phone="16138884444",
            targets="/".join(["16134442222", "16134443333"]),
        ),
        {
            # Valid multiple targets
            "instance": NotifyVoipms,
            "response": True,
            "privacy_url": "voipms://p...d:user@example.com/16...4",
        },
    ),
    (
        "voipms://{password}:{email}/?from={from_phone}&to={targets}".format(
            email="user@example.com",
            password="password",
            from_phone="16138884444",
            targets="16134448888",
        ),
        {
            # Valid
            "instance": NotifyVoipms,
        },
    ),
    (
        "voipms://{password}:{email}/{from_phone}/{targets}/".format(
            email="user@example.com",
            password="password",
            from_phone="16138884444",
            targets="16134442222",
        ),
        {
            "instance": NotifyVoipms,
            # Throws a series of errors
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_voipms():
    """NotifyVoipms() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.get")
def test_plugin_voipms_edge_cases(mock_get):
    """NotifyVoipms() Edge Cases."""

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_get.return_value = response

    # Initialize some generic (but valid) tokens
    email = "user@example.com"
    password = "password"
    source = "+1 (555) 123-3456"
    targets = "+1 (555) 123-9876"

    # No email specified
    with pytest.raises(TypeError):
        NotifyVoipms(email=None, source=source)

    # a error response is returned
    response.status_code = 400
    response.content = dumps({
        "code": 21211,
        "message": "Unable to process your request.",
    })
    mock_get.return_value = response

    # Initialize our object
    obj = Apprise.instantiate(
        f"voipms://{password}:{email}/{source}/{targets}"
    )

    assert isinstance(obj, NotifyVoipms)

    # We will fail with the above error code
    assert obj.notify("title", "body", "info") is False


@mock.patch("requests.get")
def test_plugin_voipms_non_success_status(mock_get):
    """NotifyVoipms() Non Success Status."""

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_get.return_value = response

    # A 200 response is returned but non-success message
    response.status_code = 200
    response.content = dumps({
        "status": "invalid_credentials",
        "message": "Username or Password is incorrect",
    })

    obj = Apprise.instantiate(
        "voipms://{password}:{email}/{source}/{targets}".format(
            email="user@example.com",
            password="badpassword",
            source="16134448888",
            targets="16134442222",
        )
    )

    assert isinstance(obj, NotifyVoipms)

    # We will fail with the above error code
    assert obj.notify("title", "body", "info") is False

    response.content = "{"
    assert obj.send("title", "body") is False
