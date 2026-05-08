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

from json import dumps, loads

# Disable logging for a cleaner testing output
import logging
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, NotifyType
from apprise.plugins.whatsapp import IS_GROUP_ID, NotifyWhatsApp

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "whatsapp://",
        {
            # Not enough details
            "instance": TypeError,
        },
    ),
    (
        "whatsapp://:@/",
        {
            # invalid Access Token
            "instance": TypeError,
        },
    ),
    (
        "whatsapp://{}@_".format("a" * 32),
        {
            # token provided but invalid from
            "instance": TypeError,
        },
    ),
    (
        "whatsapp://%20:{}@12345/{}".format("e" * 32, "4" * 11),
        {
            # Invalid template
            "instance": TypeError,
        },
    ),
    (
        "whatsapp://{}@{}".format("b" * 32, 10**9),
        {
            # token provided and from but no target no
            "instance": NotifyWhatsApp,
            # Response will fail due to no targets defined
            "notify_response": False,
        },
    ),
    (
        "whatsapp://{}:{}@{}/123/{}/abcd/".format(
            "a" * 32, "b" * 32, "3" * 11, "9" * 15
        ),
        {
            # valid everything but target numbers
            "instance": NotifyWhatsApp,
            # Response will fail due to target not being loaded
            "notify_response": False,
        },
    ),
    (
        "whatsapp://{}@12345/{}".format("e" * 32, "4" * 11),
        {
            # simple message
            "instance": NotifyWhatsApp,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "whatsapp://e...e@1...5/%2B44444444444/",
        },
    ),
    (
        "whatsapp://template:{}@12345/{}".format("e" * 32, "4" * 11),
        {
            # template
            "instance": NotifyWhatsApp,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "whatsapp://template:e...e@1...5/%2B44444444444/",
        },
    ),
    (
        "whatsapp://template:{}@12345/{}?lang=fr_CA".format(
            "e" * 32, "4" * 11
        ),
        {
            # template with language over-ride
            "instance": NotifyWhatsApp,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "whatsapp://template:e...e@1...5/%2B44444444444/",
        },
    ),
    (
        "whatsapp://{}@12345/{}?template=template&lang=fr_CA".format(
            "e" * 32, "4" * 11
        ),
        {
            # template specified as kwarg with language over-ride
            "instance": NotifyWhatsApp,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "whatsapp://template:e...e@1...5/%2B44444444444/",
        },
    ),
    (
        "whatsapp://template:{}@12345/{}?lang=1234".format("e" * 32, "4" * 11),
        {
            # template with invalid language over-ride
            "instance": TypeError,
        },
    ),
    (
        "whatsapp://template:{}@12345/{}?:1=test&:body=3&:type=2".format(
            "e" * 32, "4" * 11
        ),
        {
            # template with kwarg assignments
            # {{1}} assigned test
            # {{2}} assigned Apprise Message type (special keyword)
            # {{3}} assigned Apprise Message body (special keyword)
            "instance": NotifyWhatsApp,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "whatsapp://template:e...e@1...5/%2B44444444444/",
        },
    ),
    (
        "whatsapp://template:{}@12345/{}?:invalid=23".format(
            "e" * 32, "4" * 11
        ),
        {
            # template with kwarg assignments
            # Invalid keyword specified; cna only be a digit OR `body'
            # or 'type'
            "instance": TypeError,
        },
    ),
    (
        "whatsapp://template:{}@12345/{}?:body=".format("e" * 32, "4" * 11),
        {
            # template with kwarg assignments
            # No Body Assigment
            "instance": TypeError,
        },
    ),
    (
        "whatsapp://template:{}@12345/{}?:1=Test&:body=1".format(
            "e" * 32, "4" * 11
        ),
        {
            # template with kwarg assignments
            # Ambiguious assignment {{1}} assigned twice
            "instance": TypeError,
        },
    ),
    (
        "whatsapp://{}:{}@123456/{}".format("a" * 32, "b" * 32, "4" * 11),
        {
            # using short-code (6 characters)
            "instance": NotifyWhatsApp,
        },
    ),
    (
        "whatsapp://_?token={}&from={}&to={}".format(
            "d" * 32, "5" * 11, "6" * 11
        ),
        {
            # use get args to acomplish the same thing
            "instance": NotifyWhatsApp,
        },
    ),
    (
        "whatsapp://_?token={}&source={}&to={}".format(
            "d" * 32, "5" * 11, "6" * 11
        ),
        {
            # use get args to acomplish the same thing (use source instead
            # of from)
            "instance": NotifyWhatsApp,
        },
    ),
    (
        "whatsapp://{}@12345/{}".format("e" * 32, "4" * 11),
        {
            "instance": NotifyWhatsApp,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "whatsapp://{}@12345/{}".format("e" * 32, "4" * 11),
        {
            "instance": NotifyWhatsApp,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
    # Group target tests
    (
        # Group ID via '#' prefix
        "whatsapp://{}@12345/%23120363043968066561".format("e" * 32),
        {
            "instance": NotifyWhatsApp,
            "privacy_url": "whatsapp://e...e@1...5/%23120363043968066561/",
        },
    ),
    (
        # Mix of phone number and group ID
        "whatsapp://{}@12345/{}/%23120363043968066561".format(
            "e" * 32, "4" * 11
        ),
        {
            "instance": NotifyWhatsApp,
        },
    ),
    (
        # Group target with HTTP 500
        "whatsapp://{}@12345/%23120363043968066561".format("e" * 32),
        {
            "instance": NotifyWhatsApp,
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        # Group target with request exception
        "whatsapp://{}@12345/%23120363043968066561".format("e" * 32),
        {
            "instance": NotifyWhatsApp,
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_whatsapp_urls():
    """NotifyWhatsApp() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_whatsapp_auth(mock_post):
    """NotifyWhatsApp() Auth.

    - account-wide auth token
    - API key and its own auth token
    """

    response = mock.Mock()
    response.content = ""
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    # Initialize some generic (but valid) tokens
    token = "{}".format("b" * 32)
    from_phone_id = "123456787654321"
    target = "+1 (555) 987-6543"
    message_contents = "test"

    # Variation of initialization without API key
    obj = Apprise.instantiate(f"whatsapp://{token}@{from_phone_id}/{target}")
    assert isinstance(obj, NotifyWhatsApp) is True
    assert isinstance(obj.url(), str) is True

    # Send Notification
    assert obj.send(body=message_contents) is True

    # Validate expected call parameters
    assert mock_post.call_count == 1
    first_call = mock_post.call_args_list[0]

    # URL and message parameters are the same for both calls
    assert first_call[0][0] == (
        "https://graph.facebook.com/"
        f"{NotifyWhatsApp.fb_graph_version}/{from_phone_id}/messages"
    )
    response = loads(first_call[1]["data"])
    assert response["text"]["body"] == message_contents
    assert response["to"] == "+15559876543"
    assert response["recipient_type"] == "individual"


@mock.patch("requests.post")
def test_plugin_whatsapp_edge_cases(mock_post):
    """NotifyWhatsApp() Edge Cases."""

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    # Initialize some generic (but valid) tokens
    token = "b" * 32
    from_phone_id = "123456787654321"
    targets = ("+1 (555) 123-3456",)

    # No token specified
    with pytest.raises(TypeError):
        NotifyWhatsApp(
            token=None, from_phone_id=from_phone_id, targets=targets
        )

    # No from_phone_id specified
    with pytest.raises(TypeError):
        NotifyWhatsApp(token=token, from_phone_id=None, targets=targets)

    # a error response
    response.status_code = 400
    response.content = dumps(
        {
            "error": {
                "code": 21211,
                "message": (
                    "The 'To' number +1234567 is not a valid phone number."
                ),
            },
        }
    )
    mock_post.return_value = response

    # Initialize our object
    obj = NotifyWhatsApp(
        token=token, from_phone_id=from_phone_id, targets=targets
    )

    # We will fail with the above error code
    assert obj.notify("title", "body", "info") is False


@mock.patch("requests.post")
def test_plugin_whatsapp_template_notify_type_value(mock_post):
    response = mock.Mock()
    response.content = ""
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    token = "b" * 32
    from_phone_id = "12345"
    target = "+1 (555) 987-6543"

    # Map notify_type -> {{2}}, body -> {{3}}
    obj = Apprise.instantiate(
        f"whatsapp://template:{token}@{from_phone_id}/{target}?:type=2&:body=3"
    )
    assert isinstance(obj, NotifyWhatsApp)

    assert (
        obj.send(body="test", title="t", notify_type=NotifyType.INFO) is True
    )

    call = mock_post.call_args_list[0]
    assert "NotifyType." not in call[1]["data"]

    payload = loads(call[1]["data"])
    params = payload["template"]["components"][0]["parameters"]

    # Ensure values are injected, not literal strings
    assert params[0]["text"] == NotifyType.INFO.value
    assert params[1]["text"] == "test"


@mock.patch("requests.post")
def test_plugin_whatsapp_groups(mock_post):
    """NotifyWhatsApp() group target support."""

    def _mk_resp(code=requests.codes.ok):
        r = mock.Mock()
        r.content = ""
        r.status_code = code
        return r

    mock_post.return_value = _mk_resp()

    token = "e" * 32
    from_phone_id = "123456787654321"
    # A realistic-looking numeric group ID
    group_id = "120363043968066561"

    # IS_GROUP_ID only matches the numeric portion (no prefix/suffix)
    assert IS_GROUP_ID.match(group_id)
    assert not IS_GROUP_ID.match(f"#{group_id}")
    assert not IS_GROUP_ID.match(f"{group_id}@g.us")
    assert not IS_GROUP_ID.match("abc123")

    # __init__ target classification

    # '#' prefix → group
    obj = NotifyWhatsApp(
        token=token,
        from_phone_id=from_phone_id,
        targets=[f"#{group_id}"],
    )
    assert obj.targets == [f"#{group_id}"]

    # '@g.us' suffix (native API format) → normalised to '#' prefix
    obj = NotifyWhatsApp(
        token=token,
        from_phone_id=from_phone_id,
        targets=[f"{group_id}@g.us"],
    )
    assert obj.targets == [f"#{group_id}"]

    # '#' prefix + '@g.us' suffix (both present) → normalised
    obj = NotifyWhatsApp(
        token=token,
        from_phone_id=from_phone_id,
        targets=[f"#{group_id}@g.us"],
    )
    assert obj.targets == [f"#{group_id}"]

    # Invalid group ID (non-numeric) is dropped with a warning
    obj = NotifyWhatsApp(
        token=token,
        from_phone_id=from_phone_id,
        targets=["#badgroupid", f"#{group_id}"],
    )
    assert obj.targets == [f"#{group_id}"]

    # Mixed: phone number + group ID
    obj = NotifyWhatsApp(
        token=token,
        from_phone_id=from_phone_id,
        targets=["+14155552671", f"#{group_id}"],
    )
    assert len(obj.targets) == 2
    assert "+14155552671" in obj.targets
    assert f"#{group_id}" in obj.targets

    # send() payload verification

    mock_post.reset_mock()
    obj = NotifyWhatsApp(
        token=token,
        from_phone_id=from_phone_id,
        targets=[f"#{group_id}"],
    )
    assert obj.send(body="hello group") is True
    assert mock_post.call_count == 1

    # Group payload must carry recipient_type='group' and 'to'=id@g.us
    sent = loads(mock_post.call_args_list[0][1]["data"])
    assert sent["recipient_type"] == "group"
    assert sent["to"] == f"{group_id}@g.us"

    # send() for individual phone preserves recipient_type='individual'
    mock_post.reset_mock()
    obj = NotifyWhatsApp(
        token=token,
        from_phone_id=from_phone_id,
        targets=["+14155552671"],
    )
    assert obj.send(body="hello individual") is True
    sent = loads(mock_post.call_args_list[0][1]["data"])
    assert sent["recipient_type"] == "individual"
    assert sent["to"] == "+14155552671"

    # mixed send: one phone + one group makes two POST calls
    mock_post.reset_mock()
    obj = NotifyWhatsApp(
        token=token,
        from_phone_id=from_phone_id,
        targets=["+14155552671", f"#{group_id}"],
    )
    assert obj.send(body="mixed") is True
    assert mock_post.call_count == 2
    payloads = [loads(c[1]["data"]) for c in mock_post.call_args_list]
    types = {p["recipient_type"] for p in payloads}
    assert types == {"individual", "group"}

    # HTTP error on group target returns False
    mock_post.return_value = _mk_resp(requests.codes.internal_server_error)
    obj = NotifyWhatsApp(
        token=token,
        from_phone_id=from_phone_id,
        targets=[f"#{group_id}"],
    )
    assert obj.send(body="should fail") is False

    # partial failure: phone succeeds, group errors → overall False
    mock_post.side_effect = [
        _mk_resp(requests.codes.ok),
        _mk_resp(requests.codes.internal_server_error),
    ]
    obj = NotifyWhatsApp(
        token=token,
        from_phone_id=from_phone_id,
        targets=["+14155552671", f"#{group_id}"],
    )
    assert obj.send(body="partial") is False

    # URL round-trip: group ID survives url() -> parse_url()
    mock_post.side_effect = None
    mock_post.return_value = _mk_resp()

    obj = NotifyWhatsApp(
        token=token,
        from_phone_id=from_phone_id,
        targets=[f"#{group_id}"],
    )
    rebuilt = NotifyWhatsApp(**NotifyWhatsApp.parse_url(obj.url()))
    assert rebuilt.targets == obj.targets
    assert rebuilt.url_identifier == obj.url_identifier

    # Round-trip with mixed targets
    obj = NotifyWhatsApp(
        token=token,
        from_phone_id=from_phone_id,
        targets=["+14155552671", f"#{group_id}"],
    )
    rebuilt = NotifyWhatsApp(**NotifyWhatsApp.parse_url(obj.url()))
    assert sorted(rebuilt.targets) == sorted(obj.targets)

    # targets as a plain string (comma-separated, not a list)
    obj = NotifyWhatsApp(
        token=token,
        from_phone_id=from_phone_id,
        targets=f"#{group_id}",
    )
    assert obj.targets == [f"#{group_id}"]

    # whitespace-only list entry is silently skipped
    obj = NotifyWhatsApp(
        token=token,
        from_phone_id=from_phone_id,
        targets=["   ", f"#{group_id}"],
    )
    assert obj.targets == [f"#{group_id}"]

    # ?to= query parameter accepts group IDs
    url = f"whatsapp://_?token={token}&from={from_phone_id}&to=%23{group_id}"
    obj = Apprise.instantiate(url)
    assert isinstance(obj, NotifyWhatsApp)
    assert f"#{group_id}" in obj.targets

    # privacy_url masks group targets correctly
    obj = NotifyWhatsApp(
        token=token,
        from_phone_id=from_phone_id,
        targets=[f"#{group_id}"],
    )
    priv = obj.url(privacy=True)
    # The token should be masked; the group ID should still be present
    assert token not in priv
    assert group_id in priv
