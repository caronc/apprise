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
import logging
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise
from apprise.plugins.ringcentral import (
    NotifyRingCentral,
    RingCentralAuthMode,
    RingCentralEnvironment,
    RingCentralExtension,
)

logging.disable(logging.CRITICAL)


# Shared valid credential constants used across tests
CLIENT_ID = "client_id"
CLIENT_SECRET = "client-secret"
SOURCE = "+15551233456"
JWT_TOKEN = "a" * 80


# A realistic RingCentral token response (covers both auth and SMS fields)
GOOD_RESPONSE = {
    # OAuth token fields
    "access_token": "abc123",
    "token_type": "bearer",
    "expires_in": 3600,
    "scope": "Faxes SMS TeamMessaging A2PSMS",
    "owner_id": "123",
    "endpoint_id": "akfJbWJYQ7GEUev2CaR37k",
    # SMS response fields
    "uri": (
        "https://platform.ringcentral.com/restapi/v1.0/"
        "account/123/extension/123/message-store/123"
    ),
    "id": 123,
    "to": [{"phoneNumber": "+14223453486", "name": "Chris"}],
    "from": {"phoneNumber": "+14223452386", "name": "Chris"},
    "type": "SMS",
    "messageStatus": "Queued",
}

# Our Testing URLs
apprise_url_tests = (
    (
        "ringc://",
        {
            # No credentials at all
            "instance": TypeError,
        },
    ),
    (
        "ringc://:@/",
        {
            # No credentials at all
            "instance": TypeError,
        },
    ),
    (
        "ringc://password@client_id/18005554321",
        {
            # No client secret
            "instance": TypeError,
        },
    ),
    (
        "ringc://18005554321:jwt{}@client_id".format("a" * 60),
        {
            # JWT provided but no client secret
            "instance": TypeError,
        },
    ),
    (
        "ringc://18005554321:jwt{}@%21%21%21/secret".format("b" * 60),
        {
            # Invalid client_id
            "instance": TypeError,
        },
    ),
    (
        "ringc://18005554321:jwt{}@client_id/%21%21%21/".format("c" * 60),
        {
            # Invalid client secret
            "instance": TypeError,
        },
    ),
    (
        "ringc://18005554321:password@client_id/secret?mode=invalid",
        {
            # Invalid auth mode
            "instance": TypeError,
        },
    ),
    (
        "ringc://18005554321:password@client_id/secret?ext=invalid",
        {
            # Invalid extension
            "instance": TypeError,
        },
    ),
    (
        "ringc://18005554321:password@client_id/secret?env=invalid",
        {
            # Invalid environment
            "instance": TypeError,
        },
    ),
    (
        "ringc://18005554321:jwt=@client_id/secret?mode=jwt",
        {
            # Invalid JWT token (contains disallowed chars)
            "instance": TypeError,
        },
    ),
    # Valid JWT mode with explicit ?mode=jwt
    (
        "ringc://18005554321:jwt{}@client_id/secret/1555123456?mode=jwt".format(
            "c" * 60
        ),
        {
            "instance": NotifyRingCentral,
            "requests_response_text": GOOD_RESPONSE,
            "privacy_url": "ringc://18005554321:j...c@c...d/****/"
            "1555123456/?env=prod&ext=sms&mode=jwt",
        },
    ),
    # Valid JWT mode auto-detected from token length (>60 chars)
    (
        "ringc://18005554321:jwt{}@client_id/secret/1555123456".format(
            "c" * 60
        ),
        {
            "instance": NotifyRingCentral,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    # Invalid phone number in targets (gets dropped, loopback used)
    (
        "ringc://18005554321:jwt{}@client_id/secret/245/?ext=sms&env=sandbox".format(
            "c" * 60
        ),
        {
            "instance": NotifyRingCentral,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    # BASIC auth mode
    (
        "ringc://18005554321:password@client_id/secret",
        {
            "instance": NotifyRingCentral,
            "requests_response_text": GOOD_RESPONSE,
        },
    ),
    # Query param form with ?token= and ?secret=
    (
        "ringc://_?token={}&secret={}&from={}".format(
            "a" * 8, "b" * 16, "5" * 11
        ),
        {
            "requests_response_text": GOOD_RESPONSE,
            "instance": NotifyRingCentral,
        },
    ),
    # Query param form with ?source= instead of ?from=
    (
        "ringc://_?token={}&secret={}&source={}".format(
            "a" * 8, "b" * 16, "5" * 11
        ),
        {
            "requests_response_text": GOOD_RESPONSE,
            "instance": NotifyRingCentral,
        },
    ),
    # Query param form with ?to= target
    (
        "ringc://_?token={}&secret={}&from={}&to={}".format(
            "a" * 8, "b" * 16, "5" * 11, "7" * 13
        ),
        {
            "requests_response_text": GOOD_RESPONSE,
            "instance": NotifyRingCentral,
        },
    ),
    # HTTP 999 (unknown response code)
    (
        "ringc://18005554321:jwt{}@client_id/secret".format("c" * 60),
        {
            "instance": NotifyRingCentral,
            "requests_response_text": GOOD_RESPONSE,
            "response": False,
            "requests_response_code": 999,
        },
    ),
    # RequestException handling
    (
        "ringc://18005554321:jwt{}@client_id/secret".format("c" * 60),
        {
            "instance": NotifyRingCentral,
            "requests_response_text": GOOD_RESPONSE,
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_ringc_urls():
    """NotifyRingCentral() Apprise URLs."""
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_ringc_init(mock_post):
    """NotifyRingCentral() init edge cases."""

    def _mk_resp(d, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = d
        return r

    mock_post.return_value = _mk_resp(b"{}")

    # No client_id
    with pytest.raises(TypeError):
        NotifyRingCentral(
            client_id=None,
            client_secret=CLIENT_SECRET,
            source=SOURCE,
        )

    # Blank client_id
    with pytest.raises(TypeError):
        NotifyRingCentral(
            client_id="  ",
            client_secret=CLIENT_SECRET,
            source=SOURCE,
        )

    # No client_secret
    with pytest.raises(TypeError):
        NotifyRingCentral(
            client_id=CLIENT_ID,
            client_secret=None,
            source=SOURCE,
        )

    # Blank client_secret
    with pytest.raises(TypeError):
        NotifyRingCentral(
            client_id=CLIENT_ID,
            client_secret="  ",
            source=SOURCE,
        )

    # Invalid source phone
    with pytest.raises(TypeError):
        NotifyRingCentral(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            source="notaphone",
        )

    # Invalid auth mode
    with pytest.raises(TypeError):
        NotifyRingCentral(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            source=SOURCE,
            mode="bad_mode",
        )

    # Invalid environment
    with pytest.raises(TypeError):
        NotifyRingCentral(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            source=SOURCE,
            environment="invalid",
        )

    # Invalid extension
    with pytest.raises(TypeError):
        NotifyRingCentral(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            source=SOURCE,
            extension="invalid",
        )

    # Invalid JWT token in JWT mode
    with pytest.raises(TypeError):
        NotifyRingCentral(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            source=SOURCE,
            token="bad token!",
            mode=RingCentralAuthMode.JWT,
        )

    # Valid BASIC mode (token is a plain password -- no regex check)
    obj = NotifyRingCentral(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        source=SOURCE,
        token="some-password",
    )
    assert obj.mode == RingCentralAuthMode.BASIC

    # Valid JWT mode
    obj = NotifyRingCentral(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        source=SOURCE,
        token=JWT_TOKEN,
        mode=RingCentralAuthMode.JWT,
    )
    assert obj.mode == RingCentralAuthMode.JWT


@mock.patch("requests.post")
def test_plugin_ringc_url_and_identifier(mock_post):
    """NotifyRingCentral() url() and url_identifier."""

    def _mk_resp(d, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = d
        return r

    mock_post.return_value = _mk_resp(b"{}")

    # BASIC mode with targets
    obj = NotifyRingCentral(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        source=SOURCE,
        token="secret",
        targets=["15559998888"],
    )
    assert obj.url_identifier == (
        "ringc",
        CLIENT_ID,
        CLIENT_SECRET,
        SOURCE.lstrip("+"),
    )

    full_url = obj.url()
    assert "ringc://" in full_url
    assert "mode=basic" in full_url

    privacy_url = obj.url(privacy=True)
    assert "****" in privacy_url

    # Round-trip
    result = NotifyRingCentral.parse_url(full_url)
    assert result is not None
    obj2 = NotifyRingCentral(**result)
    assert obj.url_identifier == obj2.url_identifier
    assert len(obj.targets) == len(obj2.targets)

    # JWT mode
    obj_jwt = NotifyRingCentral(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        source=SOURCE,
        token=JWT_TOKEN,
        mode=RingCentralAuthMode.JWT,
    )
    full_url_jwt = obj_jwt.url()
    assert "mode=jwt" in full_url_jwt
    privacy_url_jwt = obj_jwt.url(privacy=True)
    assert "mode=jwt" in privacy_url_jwt

    # Round-trip JWT
    result_jwt = NotifyRingCentral.parse_url(full_url_jwt)
    assert result_jwt is not None
    obj_jwt2 = NotifyRingCentral(**result_jwt)
    assert obj_jwt.url_identifier == obj_jwt2.url_identifier

    # __len__
    assert len(obj) == 1  # one target
    obj_no_targets = NotifyRingCentral(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        source=SOURCE,
        token="pw",
    )
    assert len(obj_no_targets) == 1  # no targets -> loopback -> 1


@mock.patch("requests.post")
def test_plugin_ringc_send_success(mock_post):
    """NotifyRingCentral() successful send."""
    from json import dumps as jdumps

    good_auth = mock.Mock()
    good_auth.status_code = requests.codes.ok
    good_auth.content = jdumps(GOOD_RESPONSE).encode()

    good_sms = mock.Mock()
    good_sms.status_code = requests.codes.ok
    good_sms.content = jdumps(GOOD_RESPONSE).encode()

    mock_post.side_effect = [good_auth, good_sms]

    obj = NotifyRingCentral(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        source=SOURCE,
        token="password",
        targets=["15559998888"],
    )
    assert obj.notify(body="Test message") is True
    assert mock_post.call_count == 2

    # Second call reuses cached token (no new auth call)
    good_sms2 = mock.Mock()
    good_sms2.status_code = requests.codes.ok
    good_sms2.content = jdumps(GOOD_RESPONSE).encode()
    mock_post.side_effect = [good_sms2]
    assert obj.notify(body="Second message") is True
    assert mock_post.call_count == 3


@mock.patch("requests.post")
def test_plugin_ringc_send_multi_target(mock_post):
    """NotifyRingCentral() send to multiple targets."""
    from json import dumps as jdumps

    def _ok():
        r = mock.Mock()
        r.status_code = requests.codes.ok
        r.content = jdumps(GOOD_RESPONSE).encode()
        return r

    # auth + 2 targets = 3 calls
    mock_post.side_effect = [_ok(), _ok(), _ok()]

    obj = NotifyRingCentral(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        source=SOURCE,
        token="password",
        targets=["15559998881", "15559998882"],
    )
    assert obj.notify(body="Multi-target") is True
    assert mock_post.call_count == 3


@mock.patch("requests.post")
def test_plugin_ringc_send_loopback(mock_post):
    """NotifyRingCentral() with no targets sends to source (loopback)."""
    from json import dumps as jdumps

    good = mock.Mock()
    good.status_code = requests.codes.ok
    good.content = jdumps(GOOD_RESPONSE).encode()

    # auth + 1 loopback send
    mock_post.side_effect = [good, good]

    obj = NotifyRingCentral(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        source=SOURCE,
        token="password",
    )
    assert obj.notify(body="Loopback") is True
    assert mock_post.call_count == 2


@mock.patch("requests.post")
def test_plugin_ringc_auth_failure(mock_post):
    """NotifyRingCentral() returns False when auth fails."""
    bad = mock.Mock()
    bad.status_code = requests.codes.internal_server_error
    bad.content = b"{}"
    mock_post.return_value = bad

    obj = NotifyRingCentral(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        source=SOURCE,
        token="password",
    )
    assert obj.notify(body="Test") is False


@mock.patch("requests.post")
def test_plugin_ringc_send_http_error(mock_post):
    """NotifyRingCentral() handles HTTP error on send."""
    from json import dumps as jdumps

    good_auth = mock.Mock()
    good_auth.status_code = requests.codes.ok
    good_auth.content = jdumps(GOOD_RESPONSE).encode()

    bad_sms = mock.Mock()
    bad_sms.status_code = requests.codes.internal_server_error
    bad_sms.content = b"{}"

    mock_post.side_effect = [good_auth, bad_sms]

    obj = NotifyRingCentral(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        source=SOURCE,
        token="password",
        targets=["15559998888"],
    )
    assert obj.notify(body="Test") is False


@mock.patch("requests.post")
def test_plugin_ringc_send_unknown_code(mock_post):
    """NotifyRingCentral() handles unknown HTTP response code."""
    from json import dumps as jdumps

    good_auth = mock.Mock()
    good_auth.status_code = requests.codes.ok
    good_auth.content = jdumps(GOOD_RESPONSE).encode()

    bad_sms = mock.Mock()
    bad_sms.status_code = 999
    bad_sms.content = b"{}"

    mock_post.side_effect = [good_auth, bad_sms]

    obj = NotifyRingCentral(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        source=SOURCE,
        token="password",
        targets=["15559998888"],
    )
    assert obj.notify(body="Test") is False


@mock.patch("requests.post")
def test_plugin_ringc_request_exception(mock_post):
    """NotifyRingCentral() handles RequestException."""
    mock_post.side_effect = requests.RequestException("Connection refused")

    obj = NotifyRingCentral(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        source=SOURCE,
        token="password",
        targets=["15559998888"],
    )
    assert obj.notify(body="Test") is False


@mock.patch("requests.post")
def test_plugin_ringc_send_partial_failure(mock_post):
    """NotifyRingCentral() returns False when any target fails."""
    from json import dumps as jdumps

    good_auth = mock.Mock()
    good_auth.status_code = requests.codes.ok
    good_auth.content = jdumps(GOOD_RESPONSE).encode()

    good_sms = mock.Mock()
    good_sms.status_code = requests.codes.ok
    good_sms.content = jdumps(GOOD_RESPONSE).encode()

    bad_sms = mock.Mock()
    bad_sms.status_code = requests.codes.internal_server_error
    bad_sms.content = b"{}"

    # auth + good send + bad send
    mock_post.side_effect = [good_auth, good_sms, bad_sms]

    obj = NotifyRingCentral(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        source=SOURCE,
        token="password",
        targets=["15559998881", "15559998882"],
    )
    assert obj.notify(body="Partial") is False


@mock.patch("requests.post")
def test_plugin_ringc_jwt_mode(mock_post):
    """NotifyRingCentral() JWT auth mode."""
    from json import dumps as jdumps

    good = mock.Mock()
    good.status_code = requests.codes.ok
    good.content = jdumps(GOOD_RESPONSE).encode()

    mock_post.side_effect = [good, good]

    obj = NotifyRingCentral(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        source=SOURCE,
        token=JWT_TOKEN,
        mode=RingCentralAuthMode.JWT,
        targets=["15559998888"],
    )
    assert obj.mode == RingCentralAuthMode.JWT
    assert obj.notify(body="JWT test") is True

    # Verify the auth call used the JWT grant type
    auth_call = mock_post.call_args_list[0]
    assert "jwt-bearer" in str(auth_call)


@mock.patch("requests.post")
def test_plugin_ringc_environment_and_extension(mock_post):
    """NotifyRingCentral() environment and extension handling."""
    from json import dumps as jdumps

    good = mock.Mock()
    good.status_code = requests.codes.ok
    good.content = jdumps(GOOD_RESPONSE).encode()

    mock_post.side_effect = [good, good]

    # Sandbox environment + MMS extension
    obj = NotifyRingCentral(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        source=SOURCE,
        token="password",
        environment=RingCentralEnvironment.SANDBOX,
        extension=RingCentralExtension.MMS,
        targets=["15559998888"],
    )
    assert obj.environment == RingCentralEnvironment.SANDBOX
    assert obj.extension == RingCentralExtension.MMS
    assert obj.notify(body="MMS test") is True

    # Verify .devtest appears in the URL called
    notify_call = mock_post.call_args_list[1]
    assert ".devtest" in notify_call[0][0]
    assert "/mms" in notify_call[0][0]


@mock.patch("requests.post")
def test_plugin_ringc_parse_url(mock_post):
    """NotifyRingCentral() URL parsing edge cases."""

    mock_post.return_value = mock.Mock()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = b"{}"

    # URL with all params in query string
    url = "ringc://_?token={}&secret={}&from={}".format(
        "a" * 8, "b" * 16, "5" * 11
    )
    result = NotifyRingCentral.parse_url(url)
    assert result is not None
    assert result["token"] == "a" * 8
    assert result["client_secret"] == "b" * 16
    obj = NotifyRingCentral(**result)
    assert isinstance(obj, NotifyRingCentral)

    # Reverse URL form: token@client_id/secret/source
    url2 = "ringc://{}@client_id/secret/15551234567".format("c" * 8)
    result2 = NotifyRingCentral.parse_url(url2)
    assert result2 is not None
    assert result2["source"] == "15551234567"

    # ?to= appends targets
    url3 = "ringc://15559990000:password@client_id/secret?to=15551234567"
    result3 = NotifyRingCentral.parse_url(url3)
    assert result3 is not None
    assert "15551234567" in result3["targets"]

    # ?env= and ?ext= overrides
    url4 = "ringc://15559990000:password@client_id/secret?env=sandbox&ext=mms"
    result4 = NotifyRingCentral.parse_url(url4)
    assert result4 is not None
    assert result4["environment"] == "sandbox"
    assert result4["extension"] == "mms"

    # ?source= override (alias for ?from=)
    url5 = "ringc://_?token=abc&secret=xyz&source=15559990000"
    result5 = NotifyRingCentral.parse_url(url5)
    assert result5 is not None
    assert result5["source"] == "15559990000"

    # ?mode= override
    url6 = "ringc://15559990000:password@client_id/secret?mode=basic"
    result6 = NotifyRingCentral.parse_url(url6)
    assert result6 is not None
    assert result6["mode"] == "basic"

    # JWT auto-detection from token length (>60 chars)
    url7 = "ringc://15559990000:{}@client_id/secret".format("x" * 70)
    result7 = NotifyRingCentral.parse_url(url7)
    assert result7 is not None
    assert result7["mode"] == RingCentralAuthMode.JWT

    # Short token -> BASIC mode auto-detection
    url8 = "ringc://15559990000:shortpw@client_id/secret"
    result8 = NotifyRingCentral.parse_url(url8)
    assert result8 is not None
    assert result8["mode"] == RingCentralAuthMode.BASIC

    # Invalid URL returns None
    assert NotifyRingCentral.parse_url(None) is None


@mock.patch("requests.post")
def test_plugin_ringc_logout(mock_post):
    """NotifyRingCentral() logout sends revocation request."""
    from json import dumps as jdumps

    good = mock.Mock()
    good.status_code = requests.codes.ok
    good.content = jdumps(GOOD_RESPONSE).encode()

    bad_revoke = mock.Mock()
    bad_revoke.status_code = requests.codes.internal_server_error
    bad_revoke.content = b"{}"

    # login succeeds, then logout fails gracefully
    mock_post.side_effect = [good, good, bad_revoke]

    obj = NotifyRingCentral(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        source=SOURCE,
        token="password",
        targets=["15559998888"],
    )
    assert obj.notify(body="Test") is True
    assert obj._access_token is not None

    # Explicit logout (token is still valid, sends revoke)
    obj.logout()
    assert obj._access_token is None

    # Logout a second time (nothing to revoke -- no-op)
    obj.logout()
    assert mock_post.call_count == 3


@mock.patch("requests.post")
def test_plugin_ringc_del_exception(mock_post):
    """NotifyRingCentral() __del__ handles OSError from logout."""
    mock_post.return_value = mock.Mock()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = b"{}"

    with mock.patch(
        "apprise.plugins.ringcentral.NotifyRingCentral.logout",
        side_effect=OSError(),
    ):
        obj = NotifyRingCentral(
            client_id=CLIENT_ID,
            client_secret="valid-secret",
            source=SOURCE,
        )
        # __del__ must not propagate the exception
        del obj


@mock.patch("requests.post")
def test_plugin_ringc_invalid_json_response(mock_post):
    """NotifyRingCentral() handles non-JSON response bodies."""
    from json import dumps as jdumps

    good_auth = mock.Mock()
    good_auth.status_code = requests.codes.ok
    good_auth.content = jdumps(GOOD_RESPONSE).encode()

    bad_json = mock.Mock()
    bad_json.status_code = requests.codes.ok
    bad_json.content = b"not-json"

    mock_post.side_effect = [good_auth, bad_json]

    obj = NotifyRingCentral(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        source=SOURCE,
        token="password",
        targets=["15559998888"],
    )
    # Should succeed (status 200 regardless of body parseability)
    assert obj.notify(body="Test") is True


@mock.patch("requests.post")
def test_plugin_ringc_dropped_targets(mock_post):
    """NotifyRingCentral() drops invalid phone numbers silently."""
    mock_post.return_value = mock.Mock()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = b"{}"

    obj = NotifyRingCentral(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        source=SOURCE,
        token="password",
        targets=["abc", "15559998888"],
    )
    # "abc" is invalid and should be dropped
    assert len(obj.targets) == 1
    assert "15559998888" in obj.targets[0]


@mock.patch("requests.post")
def test_plugin_ringc_apprise_integration(mock_post):
    """NotifyRingCentral() works through the Apprise interface."""
    from json import dumps as jdumps

    good = mock.Mock()
    good.status_code = requests.codes.ok
    good.content = jdumps(GOOD_RESPONSE).encode()

    mock_post.return_value = good

    a = Apprise()
    url = "ringc://18005554321:{}@client_id/secret/15559998888".format(
        "c" * 60
    )
    assert a.add(url) is True
    assert a.notify(body="Apprise integration test") is True
