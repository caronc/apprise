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

from json import dumps

# Disable logging for a cleaner testing output
import logging
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.twilio import NotifyTwilio, TwilioNotificationMethod

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "twilio://",
        {
            # No Account SID specified
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "twilio://:@/",
        {
            # invalid Auth token
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "twilio://AC{}@12345678".format("a" * 32),
        {
            # Just sid provided
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "twilio://AC{}:{}@_".format("a" * 32, "b" * 32),
        {
            # sid and token provided but invalid from
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "twilio://AC{}:{}@{}".format("a" * 32, "b" * 32, "3" * 5),
        {
            # using short-code (5 characters) without a target
            # We can still instantiate ourselves with a valid short code
            "instance": NotifyTwilio,
            # Since there are no targets specified we expect a False return on
            # send()
            "notify_response": False,
        },
    ),
    (
        "twilio://AC{}:{}@{}".format("a" * 32, "b" * 32, "3" * 9),
        {
            # sid and token provided and from but invalid from no
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "twilio://AC{}:{}@{}/123/{}/abcd/w:{}".format(
            "a" * 32, "b" * 32, "3" * 11, "9" * 15, 8 * 11
        ),
        {
            # valid everything but target numbers
            "instance": NotifyTwilio,
        },
    ),
    (
        "twilio://AC{}:{}@12345/{}".format("a" * 32, "b" * 32, "4" * 11),
        {
            # using short-code (5 characters)
            "instance": NotifyTwilio,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "twilio://...aaaa:b...b@12345",
        },
    ),
    (
        "twilio://AC{}:{}@98765/{}/w:{}/".format(
            "a" * 32, "b" * 32, "4" * 11, "5" * 11
        ),
        {
            # using short-code (5 characters) and 1 twillio address ignored
            # because source phone number can not be a short code
            "instance": NotifyTwilio,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "twilio://...aaaa:b...b@98765",
        },
    ),
    (
        "twilio://AC{}:{}@w:12345/{}/{}".format(
            "a" * 32, "b" * 32, "4" * 11, "5" * 11
        ),
        {
            # Invalid short-code
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "twilio://AC{}:{}@123456/{}".format("a" * 32, "b" * 32, "4" * 11),
        {
            # using short-code (6 characters)
            "instance": NotifyTwilio,
        },
    ),
    (
        "twilio://AC{}:{}@{}".format("a" * 32, "b" * 32, "5" * 11),
        {
            # using phone no with no target - we text ourselves in
            # this case
            "instance": NotifyTwilio,
        },
    ),
    (
        "twilio://AC{}:{}@{}?method=sms".format("a" * 32, "b" * 32, "5" * 11),
        {
            # Specify explicitly notification method sms
            "instance": NotifyTwilio,
        },
    ),
    (
        "twilio://AC{}:{}@{}?method=mms".format("a" * 32, "b" * 32, "5" * 11),
        {
            # Invalid notification method
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "twilio://AC{}:{}@{}?method=call".format(
            "a" * 32, "b" * 32, "w:" + "5" * 11
        ),
        {
            # Incompatibility between Whatsapp mode and CALL method
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "twilio://_?sid=AC{}&token={}&from={}".format(
            "a" * 32, "b" * 32, "5" * 11
        ),
        {
            # use get args to acomplish the same thing
            "instance": NotifyTwilio,
        },
    ),
    (
        "twilio://_?sid=AC{}&token={}&from={}&to=w:{}".format(
            "a" * 32, "b" * 32, "5" * 11, "6" * 11
        ),
        {
            # Support whatsapp (w: before number)
            "instance": NotifyTwilio,
        },
    ),
    (
        "twilio://_?sid=AC{}&token={}&source={}".format(
            "a" * 32, "b" * 32, "5" * 11
        ),
        {
            # use get args to acomplish the same thing (use source instead of
            # from)
            "instance": NotifyTwilio,
        },
    ),
    (
        "twilio://_?sid=AC{}&token={}&from={}&to={}".format(
            "a" * 32, "b" * 32, "5" * 11, "7" * 13
        ),
        {
            # use to=
            "instance": NotifyTwilio,
        },
    ),
    (
        "twilio://_?sid=AC{}&token={}&from={}&to={}method=call".format(
            "a" * 32, "b" * 32, "5" * 11, "7" * 13
        ),
        {
            # Specify notification method call
            "instance": NotifyTwilio,
        },
    ),
    (
        "twilio://AC{}:{}@{}".format("a" * 32, "b" * 32, "6" * 11),
        {
            "instance": NotifyTwilio,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "twilio://AC{}:{}@{}".format("a" * 32, "b" * 32, "6" * 11),
        {
            "instance": NotifyTwilio,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_twilio_urls():
    """NotifyTwilio() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_twilio_auth(mock_post):
    """NotifyTwilio() Auth.

    - account-wide auth token
    - API key and its own auth token
    """

    response = mock.Mock()
    response.content = ""
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    # Initialize some generic (but valid) tokens
    account_sid = "AC{}".format("b" * 32)
    apikey = "SK{}".format("b" * 32)
    auth_token = "{}".format("b" * 32)
    source = "+1 (555) 123-3456"
    dest = "+1 (555) 987-6543"
    message_contents = "test"

    # Variation of initialization without API key
    obj = Apprise.instantiate(
        f"twilio://{account_sid}:{auth_token}@{source}/{dest}"
    )
    assert isinstance(obj, NotifyTwilio)
    assert isinstance(obj.url(), str)

    # Send Notification
    assert obj.send(body=message_contents) is True

    # Variation of initialization with API key
    obj = Apprise.instantiate(
        f"twilio://{account_sid}:{auth_token}@{source}/{dest}?apikey={apikey}"
    )
    assert isinstance(obj, NotifyTwilio)
    assert isinstance(obj.url(), str)

    # Send Notification
    assert obj.send(body=message_contents) is True

    # Variation of initialization with method call
    obj = Apprise.instantiate(
        f"twilio://{account_sid}:{auth_token}@{source}/{dest}?method=call"
    )
    assert isinstance(obj, NotifyTwilio)
    assert isinstance(obj.url(), str)

    # Send Notification
    assert obj.send(body=message_contents) is True

    # Validate expected call parameters
    assert mock_post.call_count == 3
    first_call = mock_post.call_args_list[0]
    second_call = mock_post.call_args_list[1]
    third_call = mock_post.call_args_list[2]

    # URL and message parameters are the same for both calls
    assert (
        first_call[0][0]
        == second_call[0][0]
        == (
            "https://api.twilio.com/2010-04-01/Accounts"
            f"/{account_sid}/Messages.json"
        )
    )
    assert (
        first_call[1]["data"]["Body"]
        == second_call[1]["data"]["Body"]
        == message_contents
    )
    assert third_call[0][0] == (
        f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Calls.json"
    )
    # Plain text is wrapped in TwiML so the call can speak it
    assert (
        third_call[1]["data"]["Twiml"]
        == f"<Response><Say>{message_contents}</Say></Response>"
    )
    assert (
        first_call[1]["data"]["From"]
        == second_call[1]["data"]["From"]
        == third_call[1]["data"]["From"]
        == "+15551233456"
    )
    assert (
        first_call[1]["data"]["To"]
        == second_call[1]["data"]["To"]
        == third_call[1]["data"]["To"]
        == "+15559876543"
    )

    # Auth differs depending on if API Key is used
    assert first_call[1]["auth"] == (account_sid, auth_token)
    assert second_call[1]["auth"] == (apikey, auth_token)
    assert third_call[1]["auth"] == (account_sid, auth_token)


@mock.patch("requests.post")
def test_plugin_twilio_edge_cases(mock_post):
    """NotifyTwilio() Edge Cases."""

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    # Initialize some generic (but valid) tokens
    account_sid = "AC{}".format("b" * 32)
    auth_token = "{}".format("b" * 32)
    source = "+1 (555) 123-3456"
    whatsapp_source = "w:" + "+1 (555) 123-3456"

    # No account_sid specified
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyTwilio(account_sid=None, auth_token=auth_token, source=source)

    # No auth_token specified
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyTwilio(account_sid=account_sid, auth_token=None, source=source)

    # Source is bad
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyTwilio(account_sid=account_sid, auth_token=auth_token, source="")

    # Incompatibility between mode and method
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyTwilio(
            account_sid=account_sid,
            auth_token=auth_token,
            source=whatsapp_source,
            method=TwilioNotificationMethod.CALL,
        )

    # a error response
    response.status_code = 400
    response.content = dumps(
        {
            "code": 21211,
            "message": "The 'To' number +1234567 is not a valid phone number.",
        }
    )
    mock_post.return_value = response

    # Initialize our object
    obj = NotifyTwilio(
        account_sid=account_sid, auth_token=auth_token, source=source
    )

    # We will fail with the above error code
    assert bool(obj.notify("title", "body", "info")) is False


@mock.patch("requests.post")
def test_plugin_twilio_call_twiml_body_kept_intact(mock_post):
    """A TwiML call body is sent untouched even when a title is given."""

    response = mock.Mock()
    response.content = b"{}"
    response.status_code = requests.codes.created
    mock_post.return_value = response

    twiml = "<Response><Say>Disk full</Say></Response>"
    aobj = Apprise()
    assert aobj.add(
        "twilio://AC{}:{}@15551233456/15559876543?method=call".format(
            "a" * 32, "b" * 32
        )
    )
    assert aobj.notify(body=twiml, title="Alert")

    # The title is not placed in front of the TwiML document
    assert mock_post.call_args[1]["data"]["Twiml"] == twiml

    # Without a title the TwiML document is sent as it was given
    assert aobj.notify(body=twiml)
    assert mock_post.call_args[1]["data"]["Twiml"] == twiml


@mock.patch("requests.post")
def test_plugin_twilio_call_text_is_spoken(mock_post):
    """A plain text call body and its title become escaped TwiML."""

    response = mock.Mock()
    response.content = b"{}"
    response.status_code = requests.codes.created
    mock_post.return_value = response

    aobj = Apprise()
    assert aobj.add(
        "twilio://AC{}:{}@15551233456/15559876543?method=call".format(
            "a" * 32, "b" * 32
        )
    )
    assert aobj.notify(body="Disk < 5% & falling", title="Alert")

    assert mock_post.call_args[1]["data"]["Twiml"] == (
        "<Response><Say>Alert</Say>"
        "<Say>Disk &lt; 5% &amp; falling</Say></Response>"
    )


@pytest.mark.parametrize(
    "body, twiml",
    [
        # Plain text is spoken
        ("all good <3", "<Response><Say>all good &lt;3</Say></Response>"),
        # Anything starting with "<" is relayed for Twilio to validate,
        # including a document that opens with a comment or declaration
        (
            "<!-- generated -->\n<Response><Say>Hi</Say></Response>",
            "<!-- generated -->\n<Response><Say>Hi</Say></Response>",
        ),
        (
            '<?xml version="1.0"?>\n<Response><Say>Hi</Say></Response>',
            '<?xml version="1.0"?>\n<Response><Say>Hi</Say></Response>',
        ),
        ("  <Response/>", "  <Response/>"),
        ("<3 all good", "<3 all good"),
    ],
)
@mock.patch("requests.post")
def test_plugin_twilio_call_twiml_detection(mock_post, body, twiml):
    """A body starting with "<" is relayed as TwiML; text is spoken."""

    response = mock.Mock()
    response.content = b"{}"
    response.status_code = requests.codes.created
    mock_post.return_value = response

    aobj = Apprise()
    assert aobj.add(
        "twilio://AC{}:{}@15551233456/15559876543?method=call".format(
            "a" * 32, "b" * 32
        )
    )
    assert aobj.notify(body=body)
    assert mock_post.call_args[1]["data"]["Twiml"] == twiml


@mock.patch("requests.post")
def test_plugin_twilio_sms_title_joins_body(mock_post):
    """An SMS still carries the title at the top of its body."""

    response = mock.Mock()
    response.content = b"{}"
    response.status_code = requests.codes.created
    mock_post.return_value = response

    aobj = Apprise()
    assert aobj.add(
        "twilio://AC{}:{}@15551233456/15559876543".format("a" * 32, "b" * 32)
    )
    assert aobj.notify(body="body", title="title")
    assert mock_post.call_args[1]["data"]["Body"] == "title\r\nbody"


@mock.patch("requests.post")
def test_plugin_twilio_call_say_injection(mock_post):
    """Text cannot close the Say element early."""

    response = mock.Mock()
    response.content = b"{}"
    response.status_code = requests.codes.created
    mock_post.return_value = response

    aobj = Apprise()
    assert aobj.add(
        "twilio://AC{}:{}@15551233456/15559876543?method=call".format(
            "a" * 32, "b" * 32
        )
    )
    expected = (
        "<Response><Say>t&lt;/Say&gt;&lt;Hangup/&gt;</Say>"
        "<Say>b&lt;/Say&gt;&lt;Play&gt;x&lt;/Play&gt;</Say></Response>"
    )

    # Both a declared text body and undeclared content are escaped
    for body_format in ("text", None):
        assert aobj.notify(
            body="b</Say><Play>x</Play>",
            title="t</Say><Hangup/>",
            body_format=body_format,
        )
        assert mock_post.call_args[1]["data"]["Twiml"] == expected


@pytest.mark.parametrize("overflow", ["split", "truncate"])
@mock.patch("requests.post")
def test_plugin_twilio_call_twiml_not_split(mock_post, overflow):
    """Valid TwiML within Twilio's limit is sent whole as one call."""

    response = mock.Mock()
    response.content = b"{}"
    response.status_code = requests.codes.created
    mock_post.return_value = response

    aobj = Apprise()
    assert aobj.add(
        "twilio://AC{}:{}@15551233456/15559876543?method=call"
        "&overflow={}".format("a" * 32, "b" * 32, overflow)
    )

    # A 3900 character TwiML document, with a long title that is ignored
    twiml = "<Response><Say>{}</Say></Response>".format("x" * 3868)
    assert len(twiml) == 3900
    assert aobj.notify(body=twiml, title="t" * 250, body_format="text")
    assert mock_post.call_count == 1
    assert mock_post.call_args[1]["data"]["Twiml"] == twiml
