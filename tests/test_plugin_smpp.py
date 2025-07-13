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

from contextlib import suppress
import logging
import sys
from unittest import mock

from helpers import AppriseURLTester
import pytest

from apprise import Apprise, NotifyType
from apprise.plugins.smpp import NotifySMPP

with suppress(ImportError):
    import smpplib

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "smpp://",
        {
            "instance": TypeError,
        },
    ),
    (
        "smpp:///",
        {
            "instance": TypeError,
        },
    ),
    (
        "smpp://@/",
        {
            "instance": TypeError,
        },
    ),
    (
        "smpp://user@/",
        {
            "instance": TypeError,
        },
    ),
    (
        "smpp://user:pass/",
        {
            "instance": TypeError,
        },
    ),
    (
        "smpp://user:pass@/",
        {
            "instance": TypeError,
        },
    ),
    (
        "smpp://user@hostname",
        {
            "instance": TypeError,
        },
    ),
    (
        "smpp://user:pass@host:/",
        {
            "instance": TypeError,
        },
    ),
    (
        "smpp://user:pass@host:2775/",
        {
            "instance": TypeError,
        },
    ),
    (
        "smpp://user:pass@host:2775/{}/{}".format("1" * 10, "a" * 32),
        {
            # valid everything but target numbers
            "instance": NotifySMPP,
            # We have no one to notify
            "notify_response": False,
        },
    ),
    (
        "smpp://user:pass@host:2775/{}".format("1" * 10),
        {
            # everything valid
            "instance": NotifySMPP,
            # We have no one to notify
            "notify_response": False,
        },
    ),
    (
        "smpp://user:pass@host/{}/{}".format("1" * 10, "1" * 10),
        {
            "instance": NotifySMPP,
        },
    ),
    (
        "smpps://_?&from={}&to={},{}&user=user&password=pw".format(
            "1" * 10, "1" * 10, "1" * 10
        ),
        {
            # use get args to accomplish the same thing
            "instance": NotifySMPP,
        },
    ),
)


@pytest.mark.skipif(
    "smpplib" in sys.modules, reason="Requires that smpplib NOT be installed"
)
def test_plugin_smpplib_import_error():
    """NotifySMPP() smpplib loading failure."""

    # Attempt to instantiate our object
    obj = Apprise.instantiate(
        "smpp://user:pass@host/{}/{}".format("1" * 10, "1" * 10)
    )

    # It's not possible because our cryptography depedancy is missing
    assert obj is None


@pytest.mark.skipif("smpplib" not in sys.modules, reason="Requires smpplib")
def test_plugin_smpp_urls():
    """NotifySMPP() Apprise URLs."""
    # mock nested inside of outside function to avoid failing
    # when smpplib is unavailable
    with mock.patch("smpplib.client.Client") as mock_client_class:
        mock_client_instance = mock.Mock()
        mock_client_class.return_value = mock_client_instance

        # Raise exception on connect
        mock_client_instance.connect.return_value = True
        mock_client_instance.bind_transmitter.return_value = True
        mock_client_instance.send_message.return_value = True

        # Run our general tests
        AppriseURLTester(tests=apprise_url_tests).run_all()


@pytest.mark.skipif("smpplib" not in sys.modules, reason="Requires smpplib")
def test_plugin_smpp_edge_case():
    """NotifySMPP() Apprise Edge Case."""

    # mock nested inside of outside function to avoid failing
    # when smpplib is unavailable
    with mock.patch("smpplib.client.Client") as mock_client_class:
        mock_client_instance = mock.Mock()
        mock_client_class.return_value = mock_client_instance

        # Raise exception on connect
        mock_client_instance.connect.side_effect = (
            smpplib.exceptions.ConnectionError
        )
        mock_client_instance.bind_transmitter.return_value = True
        mock_client_instance.send_message.return_value = True

        # Instantiate our object
        obj = Apprise.instantiate(
            "smpp://user:pass@host/{}/{}".format("1" * 10, "1" * 10)
        )

        # Well fail to establish a connection
        assert (
            obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
            is False
        )

        # Raise exception on connect
        mock_client_instance.connect.side_effect = None
        mock_client_instance.bind_transmitter.return_value = True
        mock_client_instance.send_message.side_effect = (
            smpplib.exceptions.ConnectionError
        )

        # Well fail to deliver our message
        assert (
            obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
            is False
        )
