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

import json

# Disable logging for a cleaner testing output
import logging
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise.plugins.sfr import NotifySFR

logging.disable(logging.CRITICAL)

SFR_GOOD_RESPONSE = json.dumps({
    "success": True,
    "reponse": 8888888,
})

SFR_BAD_RESPONSE = json.dumps({
    "success": False,
    "errorCode": "THIS_IS_AN_ERROR",
    "errorDetail": "Appel api en erreur",
    "fatal": True,
    "invalidParams": True,
})

# Our Testing URLs
apprise_url_tests = (
    (
        "sfr://",
        {
            # No host specified
            "instance": TypeError,
        },
    ),
    (
        "sfr://:@/",
        {
            # Invalid host
            "instance": TypeError,
        },
    ),
    (
        "sfr://:service_password",
        {
            # No user specified
            "instance": TypeError,
        },
    ),
    (
        "sfr://testing:serv@ice_password",
        {
            # Invalid Password
            "instance": TypeError,
        },
    ),
    (
        "sfr://testing:service_password@/5555555555",
        {
            # No spaceId provided
            "instance": TypeError,
        },
    ),
    (
        "sfr://testing:service_password@12345/",
        {
            # No target provided
            "instance": TypeError,
        },
    ),
    (
        f"sfr://:service_password@12345/{3 * 13}",
        {
            # No host but everything else provided
            "instance": TypeError,
        },
    ),
    (
        "sfr://:service_password@space_id/targets?media=TEST",
        {
            "instance": TypeError,
        },
    ),
    (
        "sfr://service_id:",
        {
            "instance": TypeError,
        },
    ),
    (
        "sfr://service_id:@",
        {
            "instance": TypeError,
        },
    ),
    (
        "sfr://service_id:@{}".format("0" * 3),
        {
            "instance": TypeError,
        },
    ),
    (
        "sfr://service_id:@{}/".format("0" * 3),
        {
            "instance": TypeError,
        },
    ),
    (
        "sfr://service_id:@{}/targets".format("0" * 3),
        {
            "instance": TypeError,
        },
    ),
    (
        "sfr://service_id:@{}/targets?media=TEST".format("0" * 3),
        {
            "instance": TypeError,
        },
    ),
    (
        "sfr://service_id:service_password@{}/{}?from=MyApp&timeout=30".format(
            "0" * 3, "0" * 10
        ),
        {
            # a valid group
            "instance": NotifySFR,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": (
                "sfr://service_id:****@0...0/0000000000?"
                "from=MyApp&timeout=30&voice=claire08s&"
                "lang=fr_FR&media=SMSUnicode"
            ),
            # Our response expected server response
            "requests_response_text": SFR_GOOD_RESPONSE,
        },
    ),
    (
        "sfr://service_id:service_password@{}/{}?voice=laura8k&lang=en_US"
        .format("0" * 3, "0" * 10),
        {
            # a valid group
            "instance": NotifySFR,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": (
                "sfr://service_id:****@0...0/0000000000?"
                "from=&timeout=2880&voice=laura8k&"
                "lang=en_US&media=SMSUnicode"
            ),
            # Our response expected server response
            "requests_response_text": SFR_GOOD_RESPONSE,
        },
    ),
    (
        "sfr://service_id:service_password@{}/{}?media=SMS".format(
            "0" * 3, "0" * 10
        ),
        {
            # a valid group
            "instance": NotifySFR,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": (
                "sfr://service_id:****@0...0/0000000000?"
                "from=&timeout=2880&voice=claire08s&"
                "lang=fr_FR&media=SMS"
            ),
            # Our response expected server response
            "requests_response_text": SFR_GOOD_RESPONSE,
        },
    ),
    (
        "sfr://service_id:service_password@{}/{}".format("0" * 3, "0" * 10),
        {
            # Test case where we get a bad response
            "instance": NotifySFR,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": (
                "sfr://service_id:****@0...0/0000000000?"
                "from=&timeout=2880&voice=claire08s&"
                "lang=fr_FR&media=SMSUnicode"
            ),
            # Our failed notification expected server response
            "requests_response_text": SFR_BAD_RESPONSE,
            "requests_response_code": requests.codes.ok,
            # as a result, we expect a failed notification
            "response": False,
        },
    ),
)


def test_plugin_sfr_urls():
    """NotifySFR() Apprise URLs."""
    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_sfr_notification_ok(mock_post):
    """NotifySFR() Notifications Ok response."""
    # Prepare Mock
    # Create a mock response object
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = SFR_GOOD_RESPONSE
    mock_post.return_value = response

    # Test our URL parsing
    results = NotifySFR.parse_url(
        "sfr://srv:pwd@{}/{}?media=SMSLong".format("1" * 8, "0" * 10)
    )

    assert isinstance(results, dict)
    assert results["user"] == "srv"
    assert results["password"] == "pwd"
    assert results["space_id"] == "11111111"
    assert results["targets"] == ["0000000000"]
    assert results["media"] == "SMSLong"
    assert results["timeout"] == ""
    assert results["voice"] == ""
    assert results["lang"] == ""
    assert results["sender"] == ""

    instance = NotifySFR(**results)
    assert isinstance(instance, NotifySFR)
    assert len(instance) == 1
    assert instance.lang == "fr_FR"
    assert instance.lang == "fr_FR"
    assert instance.sender == ""
    assert isinstance(instance.targets, list)
    assert isinstance(instance.timeout, int)
    assert isinstance(instance.voice, str)
    assert isinstance(instance.space_id, str)

    response = instance.send(body="test")
    assert response is True
    assert mock_post.call_count == 1


@mock.patch("requests.post")
def test_plugin_sfr_notification_multiple_targets_ok(mock_post):
    """NotifySFR() Notifications ko response."""
    # Reset our object
    mock_post.reset_mock()
    # Prepare Mock
    # Create a mock response object
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = SFR_GOOD_RESPONSE
    mock_post.return_value = response

    # Test "real" parameters
    results = NotifySFR.parse_url(
        "sfr://{}:other_fjv&8password@{}/?to={},{}&from=MyCustomUser".format(
            "4" * 6, "1" * 8, "6" * 10, "8" * 10
        )
    )

    assert isinstance(results, dict)
    assert results["user"] == "444444"
    assert results["password"] == "other_fjv&8password"
    assert results["space_id"] == "11111111"
    assert results["targets"] == ["6666666666", "8888888888"]
    assert results["media"] == ""
    assert results["timeout"] == ""
    assert results["voice"] == ""
    assert results["lang"] == ""
    assert results["sender"] == "MyCustomUser"

    instance = NotifySFR(**results)
    assert isinstance(instance, NotifySFR)
    assert len(instance) == 2
    assert instance.lang == "fr_FR"
    assert instance.sender == "MyCustomUser"
    assert instance.media == "SMSUnicode"
    assert isinstance(instance.targets, list)
    assert instance.timeout == 2880
    assert instance.voice == "claire08s"
    assert isinstance(instance.space_id, str)

    response = instance.send(body="test")
    assert response is True
    assert mock_post.call_count == 2


@mock.patch("requests.post")
def test_plugin_sfr_notification_ko(mock_post):
    """NotifySFR() Notifications ko response."""
    # Reset our object
    mock_post.reset_mock()
    # Prepare Mock
    # Create a mock response object
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = SFR_BAD_RESPONSE
    mock_post.return_value = response

    # Test "real" parameters
    results = NotifySFR.parse_url(
        "sfr://{}:other_fjv&8password@{}/{}?timeout=30&media=SMS".format(
            "4" * 6, "1" * 8, "2" * 10
        )
    )

    assert isinstance(results, dict)
    assert results["user"] == "444444"
    assert results["password"] == "other_fjv&8password"
    assert results["space_id"] == "11111111"
    assert results["media"] == "SMS"
    assert results["targets"] == ["2222222222"]
    assert results["timeout"] == "30"
    assert results["voice"] == ""
    assert results["lang"] == ""
    assert results["sender"] == ""

    instance = NotifySFR(**results)
    assert isinstance(instance, NotifySFR)
    assert len(instance) == 1
    assert instance.lang == "fr_FR"
    assert instance.sender == ""
    assert instance.media == "SMS"
    assert isinstance(instance.targets, list)
    assert instance.timeout == 30
    assert instance.voice == "claire08s"
    assert isinstance(instance.space_id, str)

    response = instance.send(body="test")
    assert response is False
    assert mock_post.call_count == 1


@mock.patch("requests.post")
def test_plugin_sfr_notification_multiple_targets_all_ko(mock_post):
    """NotifySFR() Notifications ko response."""
    # Reset our object
    mock_post.reset_mock()
    # Prepare Mock
    # Create a mock response object
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = SFR_BAD_RESPONSE
    mock_post.return_value = response

    # Test "real" parameters
    results = NotifySFR.parse_url(
        "sfr://{}:other_fjv&8password@{}/?to={},{}&voice=laura8k".format(
            "4" * 6, "1" * 8, "6" * 4, "8" * 4
        )
    )

    assert isinstance(results, dict)
    assert results["user"] == "444444"
    assert results["password"] == "other_fjv&8password"
    assert results["space_id"] == "11111111"
    assert results["targets"] == ["6666", "8888"]
    assert results["voice"] == "laura8k"
    assert results["media"] == ""
    assert results["timeout"] == ""
    assert results["lang"] == ""
    assert results["sender"] == ""

    # No valid phone number provided
    with pytest.raises(TypeError):
        NotifySFR(**results)


@mock.patch("requests.post")
def test_plugin_sfr_notification_multiple_targets_one_ko(mock_post):
    """NotifySFR() Notifications ko response."""
    # Reset our object
    mock_post.reset_mock()
    # Prepare Mock
    # Create a mock response object
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = SFR_BAD_RESPONSE
    mock_post.return_value = response

    # Test "real" parameters
    results = NotifySFR.parse_url(
        "sfr://{}:&pass@{}/?to={},{}&media=SMSUnicodeLong&lang=en_US".format(
            "4" * 6, "1" * 8, "6" * 10, "8" * 4
        )
    )

    assert isinstance(results, dict)
    assert results["user"] == "444444"
    assert results["password"] == "&pass"
    assert results["space_id"] == "11111111"
    assert results["targets"] == ["6666666666", "8888"]
    assert results["voice"] == ""
    assert results["media"] == "SMSUnicodeLong"
    assert results["timeout"] == ""
    assert results["lang"] == "en_US"
    assert results["sender"] == ""

    instance = NotifySFR(**results)
    assert isinstance(instance, NotifySFR)
    assert len(instance) == 1
    assert instance.lang == "en_US"
    assert instance.sender == ""
    assert instance.media == "SMSUnicodeLong"
    assert isinstance(instance.targets, list)
    assert instance.timeout == 2880
    assert instance.voice == "claire08s"
    assert isinstance(instance.space_id, str)

    # One phone number failed to be parsed, therefore notify fails
    response = instance.send(body="test")
    assert response is False
    assert mock_post.call_count == 1


@mock.patch("requests.post")
def test_plugin_sfr_notification_exceptions(mock_post):
    """NotifySFR() Notifications exceptions."""
    mock_post.reset_mock()
    # Prepare Mock
    # Create a mock response object
    response = mock.Mock()
    response.status_code = requests.codes.internal_server_error
    response.content = SFR_GOOD_RESPONSE
    mock_post.return_value = response

    # Test "real" parameters
    results = NotifySFR.parse_url(
        "sfr://{}:str0*fn_ppw0rd@{}/{}".format(
            "404ghwo89144", "9993384", "0959290404"
        )
    )

    assert isinstance(results, dict)
    assert results["user"] == "404ghwo89144"
    assert results["password"] == "str0*fn_ppw0rd"
    assert results["space_id"] == "9993384"
    assert results["targets"] == ["0959290404"]
    assert results["media"] == ""
    assert results["timeout"] == ""
    assert results["lang"] == ""
    assert results["sender"] == ""

    instance = NotifySFR(**results)
    assert isinstance(instance, NotifySFR)
    assert len(instance) == 1
    assert instance.lang == "fr_FR"
    assert instance.sender == ""
    assert instance.media == "SMSUnicode"
    assert isinstance(instance.targets, list)
    assert instance.timeout == 2880
    assert instance.voice == "claire08s"
    assert isinstance(instance.space_id, str)

    response = instance.send(body="test")
    # Must return False
    assert response is False
    assert mock_post.call_count == 1

    # Test invalid content returned by requests
    mock_post.reset_mock()
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b"Invalid JSON Content"
    mock_post.return_value = response

    # Test "real" parameters
    results = NotifySFR.parse_url(
        "sfr://{}:str0*fn_ppw0rd@{}/{}".format(
            "404ghwo89144", "9993384", "0959290404"
        )
    )

    assert isinstance(results, dict)
    assert results["user"] == "404ghwo89144"
    assert results["password"] == "str0*fn_ppw0rd"
    assert results["space_id"] == "9993384"
    assert results["targets"] == ["0959290404"]
    assert results["media"] == ""
    assert results["timeout"] == ""
    assert results["lang"] == ""
    assert results["sender"] == ""

    instance = NotifySFR(**results)
    assert isinstance(instance, NotifySFR)
    assert len(instance) == 1
    assert instance.lang == "fr_FR"
    assert instance.sender == ""
    assert instance.media == "SMSUnicode"
    assert isinstance(instance.targets, list)
    assert instance.timeout == 2880
    assert instance.voice == "claire08s"
    assert isinstance(instance.space_id, str)

    response = instance.send(body="test")
    # Must return False
    assert response is False
    assert mock_post.call_count == 1


@mock.patch(
    "requests.post",
    side_effect=requests.RequestException("Connection error"),
)
def test_plugin_sfr_notification_exceptions_requests(mock_post):
    """NotifySFR() Notifications requests exceptions."""
    # Test requests socket error return
    mock_post.reset_mock()
    # Prepare Mock
    # Create a mock response object
    response = mock.Mock()
    response.status_code = requests.codes.internal_server_error
    response.content = b"Invalid content"
    mock_post.return_value = response

    # Test "real" parameters
    results = NotifySFR.parse_url(
        "sfr://{}:str0*fn_ppw0rd@{}/{}".format(
            "404ghwo89144", "9993384", "0959290404"
        )
    )

    assert isinstance(results, dict)
    assert results["user"] == "404ghwo89144"
    assert results["password"] == "str0*fn_ppw0rd"
    assert results["space_id"] == "9993384"
    assert results["targets"] == ["0959290404"]
    assert results["media"] == ""
    assert results["timeout"] == ""
    assert results["lang"] == ""
    assert results["sender"] == ""

    instance = NotifySFR(**results)
    assert isinstance(instance, NotifySFR)
    assert len(instance) == 1
    assert instance.lang == "fr_FR"
    assert instance.sender == ""
    assert instance.media == "SMSUnicode"
    assert isinstance(instance.targets, list)
    assert instance.timeout == 2880
    assert instance.voice == "claire08s"
    assert isinstance(instance.space_id, str)

    response = instance.send(body="test")
    # Must return False do to requests error
    assert response is False
    assert mock_post.call_count == 1


@mock.patch("requests.post")
def test_plugin_sfr_failure(mock_post):
    """NotifySFR() Failure Cases."""
    mock_post.reset_mock()
    # Prepare Mock
    # Create a mock response object
    response = mock.Mock()
    response.status_code = requests.codes.no_content
    mock_post.return_value = response

    # Invalid service_id
    with pytest.raises(TypeError):
        NotifySFR(
            user=None,
            password="service_password",
            space_id=int("8" * 10),
            targets=int("8" * 10),
        )

    # Invalid service_password
    with pytest.raises(TypeError):
        NotifySFR(
            user="service_id",
            password=None,
            space_id=int("8" * 10),
            targets=int("8" * 10),
        )

    # Invalid space_id
    with pytest.raises(TypeError):
        NotifySFR(
            user="service_id",
            password="service_password",
            space_id=None,
            targets=int("8" * 10),
        )

    # Invalid targets
    with pytest.raises(TypeError):
        NotifySFR(
            user="service_id",
            password="service_password",
            space_id=int("8" * 10),
            targets=None,
        )
