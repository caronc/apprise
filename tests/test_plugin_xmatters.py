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
from json import loads
import logging
from unittest import mock
from urllib.parse import urlparse

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, NotifyType
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.xmatters import NotifyXMatters

logging.disable(logging.CRITICAL)

# An integration ID and API key we can use
IID = "ba601cb1-3513-4320-b48a-05cb501bb5af"
APIKEY = "ffcd4dec-8a49-4a67-9e59-ed9fabcb002d"

# Our Testing URLs
apprise_url_tests = (
    (
        "xmatters://",
        {
            # No hostname
            "instance": None,
        },
    ),
    (
        f"xmatters://{APIKEY}@acmeco",
        {
            # No integration ID
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"xmatters://{APIKEY}@acmeco/%20invalid%3F",
        {
            # Invalid integration ID
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"xmatters://acmeco/{IID}",
        {
            # No credentials at all
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"xmatters://{APIKEY}@acmeco/{IID}",
        {
            # No recipients; the workflow decides who is notified
            "instance": NotifyXMatters,
            "privacy_url": f"xmatters://f...d@acmeco/{IID}/",
        },
    ),
    (
        f"xmatters://{APIKEY}@acmeco/{IID}/jdoe/First%20Aid",
        {
            # Recipients in the path
            "instance": NotifyXMatters,
            "privacy_url": (
                f"xmatters://f...d@acmeco/{IID}/First%20Aid/jdoe/"
            ),
        },
    ),
    (
        f"xmatters://user:pass@acmeco.na5.xmatters.com/{IID}/?to=jdoe",
        {
            # Basic authentication and a full host
            "instance": NotifyXMatters,
            "privacy_url": (
                f"xmatters://user:****@acmeco.na5.xmatters.com/{IID}/jdoe/"
            ),
        },
    ),
    (
        f"xmatters://acmeco/{IID}/?apikey={APIKEY}&recipients=jdoe",
        {
            # ?apikey= and ?recipients=
            "instance": NotifyXMatters,
        },
    ),
    (
        f"https://acmeco.xmatters.com/api/integration/1/functions/{IID}"
        f"/triggers?apiKey={APIKEY}&recipients=jdoe,ops",
        {
            # The trigger URL copied from xMatters
            "instance": NotifyXMatters,
        },
    ),
    (
        f"https://acmeco.xmatters.com/api/integration/1/functions/{IID}"
        "/triggers",
        {
            # A native URL without its API key
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"xmatters://{APIKEY}@acmeco/{IID}/jdoe",
        {
            "instance": NotifyXMatters,
            # xMatters normally answers with a 202
            "requests_response_code": requests.codes.accepted,
        },
    ),
    (
        f"xmatters://{APIKEY}@acmeco/{IID}/jdoe",
        {
            "instance": NotifyXMatters,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        f"xmatters://{APIKEY}@acmeco/{IID}/jdoe",
        {
            "instance": NotifyXMatters,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        f"xmatters://{APIKEY}@acmeco/{IID}/jdoe",
        {
            "instance": NotifyXMatters,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_xmatters_urls():
    """NotifyXMatters() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_xmatters_apikey_payload(mock_post):
    """NotifyXMatters() sends the API key as a URL parameter."""

    response = mock.Mock()
    response.status_code = requests.codes.accepted
    response.content = b'{"requestId": "abc"}'
    mock_post.return_value = response

    obj = Apprise.instantiate(
        f"xmatters://{APIKEY}@acmeco/{IID}/jdoe/First%20Aid/?to=jane|Work"
    )
    assert isinstance(obj, NotifyXMatters)

    assert obj.notify(
        title="Disk <full> & failing",
        body='Some _plain_ text\n\\ "quoted"',
        notify_type=NotifyType.FAILURE,
    )
    assert mock_post.call_count == 1

    # A company name becomes a full xMatters host
    url = mock_post.call_args[0][0]
    assert urlparse(url).hostname == "acmeco.xmatters.com"
    assert url == (
        "https://acmeco.xmatters.com/api/integration/1/functions/"
        f"{IID}/triggers"
    )

    # URL authentication uses the apiKey parameter
    assert mock_post.call_args[1]["params"] == {"apiKey": APIKEY}
    assert mock_post.call_args[1]["auth"] is None

    # The title and body are sent untouched
    payload = loads(mock_post.call_args[1]["data"])
    assert payload == {
        "summary": "Disk <full> & failing",
        "message": 'Some _plain_ text\n\\ "quoted"',
        "recipients": "First Aid,jane|Work,jdoe",
    }


@mock.patch("requests.post")
def test_plugin_xmatters_basic_auth(mock_post):
    """NotifyXMatters() uses basic authentication with a password."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b""
    mock_post.return_value = response

    # A full host and port are kept as given, and any API key is unused
    obj = Apprise.instantiate(
        f"xmatters://user:pass@acmeco.na5.xmatters.com:8443/{IID}"
        f"?apikey={APIKEY}"
    )
    assert isinstance(obj, NotifyXMatters)
    assert obj.apikey is None

    # Without a title, the start of the body is our summary
    assert obj.notify(body="A" * 300)
    assert mock_post.call_count == 1

    url = mock_post.call_args[0][0]
    assert urlparse(url).hostname == "acmeco.na5.xmatters.com"
    assert urlparse(url).port == 8443
    assert mock_post.call_args[1]["params"] is None
    assert mock_post.call_args[1]["auth"] == ("user", "pass")

    # No recipients are sent when none were given
    payload = loads(mock_post.call_args[1]["data"])
    assert payload == {
        "summary": "A" * obj.title_maxlen,
        "message": "A" * 300,
    }

    # Our URL survives a round trip
    obj2 = Apprise.instantiate(obj.url())
    assert obj2.url_identifier == obj.url_identifier
    assert obj2.url() == obj.url()


def test_plugin_xmatters_init():
    """NotifyXMatters() requires a host, ID and credentials."""

    # No host
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyXMatters(integration_id=IID, apikey=APIKEY)

    # A username without a password is not enough
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyXMatters(host="acmeco", integration_id=IID, user="user")

    # Recipients given as a string keep their spaces
    obj = NotifyXMatters(
        host="acmeco",
        integration_id=IID,
        apikey=APIKEY,
        targets="First Aid, jdoe",
    )
    assert obj.targets == ["First Aid", "jdoe"]


def test_plugin_xmatters_url_identifier():
    """NotifyXMatters() identifies the connection, not the recipients."""

    obj1 = Apprise.instantiate(f"xmatters://{APIKEY}@acmeco/{IID}/jdoe")
    obj2 = Apprise.instantiate(f"xmatters://{APIKEY}@acmeco/{IID}/ops")
    obj3 = Apprise.instantiate(f"xmatters://other@acmeco/{IID}/jdoe")
    obj4 = Apprise.instantiate(f"xmatters://{APIKEY}@acmeco/abcd1234/jdoe")

    assert obj1.url_identifier == obj2.url_identifier
    assert obj1.url_identifier != obj3.url_identifier
    assert obj1.url_identifier != obj4.url_identifier

    # The native URL is the same connection as its xmatters:// form
    native = Apprise.instantiate(
        f"https://acmeco.xmatters.com/api/integration/1/functions/{IID}"
        f"/triggers?apiKey={APIKEY}&recipients=jdoe"
    )
    obj5 = Apprise.instantiate(native.url())
    assert native.url_identifier == obj5.url_identifier
    assert obj5.targets == ["jdoe"]
