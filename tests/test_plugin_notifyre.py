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
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
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
import os
from unittest import mock
from urllib.parse import urlparse

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, AppriseAttachment, NotifyType
from apprise.plugins.notifyre import NotifyNotifyre, NotifyreMode

logging.disable(logging.CRITICAL)

# Attachment directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# A valid API key used across test cases
API_KEY = "abcdef1234567890"

# Successful API response
GOOD_RESPONSE = {
    "success": True,
    "statusCode": 200,
    "payload": {"smsMessageID": "msg-001", "friendlyID": "ABC-001"},
    "message": "OK",
    "errors": [],
}

# Failure API response (HTTP 200 but success=false)
FAIL_RESPONSE = {
    "success": False,
    "statusCode": 400,
    "payload": None,
    "message": "Invalid recipient",
    "errors": ["recipient format error"],
}

# Our Testing URLs
apprise_url_tests = (
    (
        "notifyre://",
        {
            # No API key
            "instance": TypeError,
        },
    ),
    (
        "notifyre://:@/",
        {
            # Empty credentials
            "instance": TypeError,
        },
    ),
    (
        "notifyre://{}".format(API_KEY),
        {
            # No targets -- loads but notify returns False
            "instance": NotifyNotifyre,
            "notify_response": False,
        },
    ),
    (
        "notifyre://{}/+15551234567".format(API_KEY),
        {
            # Valid SMS notification
            "instance": NotifyNotifyre,
            "privacy_url": "notifyre://a...0/+15551234567/?mode=sms",
        },
    ),
    (
        "notifyre://{}/+15551234567/+15559876543".format(API_KEY),
        {
            # Multiple targets
            "instance": NotifyNotifyre,
            "privacy_url": (
                "notifyre://a...0/+15551234567/+15559876543/?mode=sms"
            ),
        },
    ),
    (
        "notifyre://{}/+15551234567?mode=sms".format(API_KEY),
        {
            # Explicit SMS mode
            "instance": NotifyNotifyre,
        },
    ),
    (
        "notifyre://{}/+15551234567?mode=fax".format(API_KEY),
        {
            # Fax mode
            "instance": NotifyNotifyre,
            "privacy_url": "notifyre://a...0/+15551234567/?mode=fax",
        },
    ),
    (
        "notifyre://{}/+15551234567?mode=fax&from=+15559876543".format(
            API_KEY
        ),
        {
            # Fax mode with source number
            "instance": NotifyNotifyre,
        },
    ),
    (
        "notifyre://{}/+15551234567?mode=invalid".format(API_KEY),
        {
            # Invalid mode
            "instance": TypeError,
        },
    ),
    (
        "notifyre://{}/+15551234567".format(API_KEY),
        {
            # HTTP 500 failure
            "instance": NotifyNotifyre,
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "notifyre://{}/+15551234567".format(API_KEY),
        {
            # Non-standard HTTP error code
            "instance": NotifyNotifyre,
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "notifyre://{}/+15551234567".format(API_KEY),
        {
            # RequestException
            "instance": NotifyNotifyre,
            "test_requests_exceptions": True,
        },
    ),
    (
        "notifyre://{}/+15551234567?mode=fax".format(API_KEY),
        {
            # Fax -- HTTP 500 failure
            "instance": NotifyNotifyre,
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "notifyre://{}/+15551234567?mode=fax".format(API_KEY),
        {
            # Fax -- non-standard HTTP error code
            "instance": NotifyNotifyre,
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "notifyre://{}/+15551234567?mode=fax".format(API_KEY),
        {
            # Fax -- RequestException
            "instance": NotifyNotifyre,
            "test_requests_exceptions": True,
        },
    ),
    (
        "notifyre://{}/+15551234567?campaign=MyCampaign".format(API_KEY),
        {
            # SMS with custom campaign name
            "instance": NotifyNotifyre,
        },
    ),
    (
        "notifyre://{}/+15551234567?mode=fax&template=MyTpl".format(API_KEY),
        {
            # Fax with template name
            "instance": NotifyNotifyre,
        },
    ),
    (
        (
            "notifyre://{}/+15551234567?mode=fax&hq=no&ref=CR123&header=CONF"
        ).format(API_KEY),
        {
            # Fax with hq=no, client ref, and header
            "instance": NotifyNotifyre,
        },
    ),
)


def test_plugin_notifyre_urls(mock_post):
    """AppriseURLTester coverage for all URL entries."""
    AppriseURLTester(tests=apprise_url_tests).run_all()


test_plugin_notifyre_urls = mock.patch("requests.post")(
    test_plugin_notifyre_urls
)


def test_plugin_notifyre_init():
    """Initialization and validation coverage."""

    # Missing API key
    with pytest.raises(TypeError):
        NotifyNotifyre(apikey=None, targets=["+15551234567"])

    # Empty API key
    with pytest.raises(TypeError):
        NotifyNotifyre(apikey="", targets=["+15551234567"])

    # Invalid mode
    with pytest.raises(TypeError):
        NotifyNotifyre(
            apikey=API_KEY, targets=["+15551234567"], mode="invalid"
        )

    # Invalid source phone number
    with pytest.raises(TypeError):
        NotifyNotifyre(
            apikey=API_KEY, targets=["+15551234567"], source="not-a-phone"
        )

    # Valid initialization -- SMS (default)
    obj = NotifyNotifyre(apikey=API_KEY, targets=["+15551234567"])
    assert obj.mode == NotifyreMode.SMS
    assert obj.source is None
    assert len(obj.targets) == 1
    assert obj.body_maxlen == 160

    # New parameter defaults
    assert obj.campaign == obj.app_id
    assert obj.template == ""
    assert obj.ref == ""
    assert obj.hq is True
    assert obj.header == ""

    # Custom campaign name
    obj = NotifyNotifyre(
        apikey=API_KEY, targets=["+15551234567"], campaign="MyCampaign"
    )
    assert obj.campaign == "MyCampaign"

    # Empty/whitespace campaign falls back to app_id
    obj = NotifyNotifyre(
        apikey=API_KEY, targets=["+15551234567"], campaign="   "
    )
    assert obj.campaign == obj.app_id

    # Fax-specific parameters
    obj = NotifyNotifyre(
        apikey=API_KEY,
        targets=["+15551234567"],
        mode="fax",
        template="MyTemplate",
        ref="CR-001",
        hq=False,
        header="CONFIDENTIAL",
    )
    assert obj.template == "MyTemplate"
    assert obj.ref == "CR-001"
    assert obj.hq is False
    assert obj.header == "CONFIDENTIAL"

    # hq parsed from string "no"
    obj = NotifyNotifyre(
        apikey=API_KEY, targets=["+15551234567"], mode="fax", hq="no"
    )
    assert obj.hq is False

    # hq parsed from string "yes"
    obj = NotifyNotifyre(
        apikey=API_KEY, targets=["+15551234567"], mode="fax", hq="yes"
    )
    assert obj.hq is True

    # Valid initialization -- explicit SMS mode
    obj = NotifyNotifyre(apikey=API_KEY, targets=["+15551234567"], mode="sms")
    assert obj.mode == NotifyreMode.SMS
    assert obj.body_maxlen == 160

    # Valid initialization -- fax mode
    obj = NotifyNotifyre(apikey=API_KEY, targets=["+15551234567"], mode="fax")
    assert obj.mode == NotifyreMode.FAX
    assert obj.body_maxlen == 32768

    # Valid initialization -- fax with source
    obj = NotifyNotifyre(
        apikey=API_KEY,
        targets=["+15551234567"],
        mode="fax",
        source="+15559876543",
    )
    assert obj.source == "+15559876543"

    # Invalid phone targets are silently dropped
    obj = NotifyNotifyre(apikey=API_KEY, targets=["not-valid", "+15551234567"])
    assert len(obj.targets) == 1

    # No valid targets -- plugin loads but send() will fail
    obj = NotifyNotifyre(apikey=API_KEY, targets=["not-valid"])
    assert len(obj.targets) == 0


@mock.patch("requests.post")
def test_plugin_notifyre_sms_send(mock_post):
    """SMS send success and failure paths."""

    def _mk_resp(d, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = json.dumps(d).encode()
        return r

    # Successful send
    mock_post.return_value = _mk_resp(GOOD_RESPONSE)
    obj = NotifyNotifyre(apikey=API_KEY, targets=["+15551234567"])
    assert obj.notify(body="Hello", notify_type=NotifyType.INFO) is True
    assert mock_post.call_count == 1

    # Verify the correct endpoint was used
    call_url = mock_post.call_args[0][0]
    assert urlparse(call_url).hostname == "api.notifyre.com"

    # HTTP error response
    mock_post.reset_mock()
    mock_post.return_value = _mk_resp({}, code=requests.codes.bad_request)
    assert obj.notify(body="Hello", notify_type=NotifyType.INFO) is False

    # Unknown HTTP error
    mock_post.reset_mock()
    mock_post.return_value = _mk_resp({}, code=999)
    assert obj.notify(body="Hello", notify_type=NotifyType.INFO) is False

    # API-level failure (success=false on HTTP 200)
    mock_post.reset_mock()
    mock_post.return_value = _mk_resp(FAIL_RESPONSE)
    assert obj.notify(body="Hello", notify_type=NotifyType.INFO) is False

    # Unparseable response body on HTTP 200 is treated as success
    mock_post.reset_mock()
    r = mock.Mock()
    r.status_code = requests.codes.ok
    r.content = b"not-json"
    mock_post.return_value = r
    assert obj.notify(body="Hello", notify_type=NotifyType.INFO) is True

    # RequestException
    mock_post.reset_mock()
    mock_post.side_effect = requests.RequestException("connection refused")
    assert obj.notify(body="Hello", notify_type=NotifyType.INFO) is False


@mock.patch("requests.post")
def test_plugin_notifyre_sms_no_targets(mock_post):
    """SMS send with no valid targets returns False without HTTP call."""
    obj = NotifyNotifyre(apikey=API_KEY, targets=["not-valid"])
    assert obj.notify(body="Hello", notify_type=NotifyType.INFO) is False
    assert mock_post.call_count == 0


@mock.patch("requests.post")
def test_plugin_notifyre_sms_with_source(mock_post):
    """SMS send includes the source (from) number in the payload."""

    def _mk_resp(d, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = json.dumps(d).encode()
        return r

    mock_post.return_value = _mk_resp(GOOD_RESPONSE)
    obj = NotifyNotifyre(
        apikey=API_KEY,
        targets=["+15551234567"],
        source="+15559876543",
    )
    assert obj.notify(body="Hello", notify_type=NotifyType.INFO) is True

    # Verify 'from' was included in the posted payload
    posted = json.loads(mock_post.call_args[1]["data"])
    assert posted["from"] == "+15559876543"


@mock.patch("requests.post")
def test_plugin_notifyre_sms_attachment_warning(mock_post):
    """SMS mode warns when attachments are provided but still sends."""

    def _mk_resp(d, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = json.dumps(d).encode()
        return r

    mock_post.return_value = _mk_resp(GOOD_RESPONSE)

    obj = NotifyNotifyre(apikey=API_KEY, targets=["+15551234567"])
    attach = AppriseAttachment()
    attach.add(os.path.join(TEST_VAR_DIR, "apprise-test.png"))

    # Should warn but still succeed (attachments are ignored in SMS mode)
    assert (
        obj.notify(
            body="Hello",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is True
    )
    assert mock_post.call_count == 1


@mock.patch("requests.post")
def test_plugin_notifyre_fax_send(mock_post):
    """Fax send success and failure paths."""

    def _mk_resp(d, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = json.dumps(d).encode()
        return r

    # Successful send (body text as only document)
    mock_post.return_value = _mk_resp(GOOD_RESPONSE)
    obj = NotifyNotifyre(apikey=API_KEY, targets=["+15551234567"], mode="fax")
    assert obj.notify(body="Hello", notify_type=NotifyType.INFO) is True
    assert mock_post.call_count == 1

    call_url = mock_post.call_args[0][0]
    assert urlparse(call_url).hostname == "api.notifyre.com"

    # HTTP error
    mock_post.reset_mock()
    mock_post.return_value = _mk_resp({}, code=requests.codes.bad_request)
    assert obj.notify(body="Hello", notify_type=NotifyType.INFO) is False

    # Unknown HTTP error
    mock_post.reset_mock()
    mock_post.return_value = _mk_resp({}, code=999)
    assert obj.notify(body="Hello", notify_type=NotifyType.INFO) is False

    # API-level failure (success=false on HTTP 200)
    mock_post.reset_mock()
    mock_post.return_value = _mk_resp(FAIL_RESPONSE)
    assert obj.notify(body="Hello", notify_type=NotifyType.INFO) is False

    # Unparseable JSON on HTTP 200 -- treated as success
    mock_post.reset_mock()
    r = mock.Mock()
    r.status_code = requests.codes.ok
    r.content = b"not-json"
    mock_post.return_value = r
    assert obj.notify(body="Hello", notify_type=NotifyType.INFO) is True

    # RequestException
    mock_post.reset_mock()
    mock_post.side_effect = requests.RequestException("timeout")
    assert obj.notify(body="Hello", notify_type=NotifyType.INFO) is False


@mock.patch("requests.post")
def test_plugin_notifyre_fax_attachments(mock_post):
    """Fax attachment handling -- all guard branches."""

    def _mk_resp(d, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = json.dumps(d).encode()
        return r

    obj = NotifyNotifyre(apikey=API_KEY, targets=["+15551234567"], mode="fax")

    # Successful send with a valid attachment
    mock_post.return_value = _mk_resp(GOOD_RESPONSE)
    attach = AppriseAttachment()
    attach.add(os.path.join(TEST_VAR_DIR, "apprise-test.png"))
    assert (
        obj.notify(
            body="Fax body",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is True
    )
    assert mock_post.call_count == 1

    # Inaccessible file -- Guard 1
    mock_post.reset_mock()
    attach = AppriseAttachment()
    attach.add(os.path.join(TEST_VAR_DIR, "apprise-test.png"))
    with mock.patch("os.path.isfile", return_value=False):
        assert (
            obj.notify(
                body="Fax body",
                notify_type=NotifyType.INFO,
                attach=attach,
            )
            is False
        )
    assert mock_post.call_count == 0

    # OSError on open -- Guard 2
    mock_post.reset_mock()
    attach = AppriseAttachment()
    attach.add(os.path.join(TEST_VAR_DIR, "apprise-test.png"))
    with mock.patch("builtins.open", side_effect=OSError("perm denied")):
        assert (
            obj.notify(
                body="Fax body",
                notify_type=NotifyType.INFO,
                attach=attach,
            )
            is False
        )
    assert mock_post.call_count == 0

    # OSError on read -- handle opened but read fails
    mock_post.reset_mock()
    attach = AppriseAttachment()
    attach.add(os.path.join(TEST_VAR_DIR, "apprise-test.png"))
    mock_fh = mock.MagicMock()
    mock_fh.__enter__ = mock.Mock(return_value=mock_fh)
    mock_fh.__exit__ = mock.Mock(return_value=False)
    mock_fh.read.side_effect = OSError("read error")
    with mock.patch("builtins.open", return_value=mock_fh):
        assert (
            obj.notify(
                body="Fax body",
                notify_type=NotifyType.INFO,
                attach=attach,
            )
            is False
        )
    assert mock_post.call_count == 0

    # HTTP error on the attachment POST
    mock_post.reset_mock()
    mock_post.side_effect = None
    mock_post.return_value = _mk_resp({}, code=requests.codes.bad_request)
    attach = AppriseAttachment()
    attach.add(os.path.join(TEST_VAR_DIR, "apprise-test.png"))
    assert (
        obj.notify(
            body="Fax body",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is False
    )

    # RequestException on the attachment POST
    mock_post.reset_mock()
    mock_post.side_effect = requests.RequestException("timeout")
    attach = AppriseAttachment()
    attach.add(os.path.join(TEST_VAR_DIR, "apprise-test.png"))
    assert (
        obj.notify(
            body="Fax body",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is False
    )

    # Multiple attachments -- partial failure closes opened handles
    mock_post.reset_mock()
    mock_post.side_effect = None
    mock_post.return_value = _mk_resp(GOOD_RESPONSE)
    attach = AppriseAttachment()
    attach.add(os.path.join(TEST_VAR_DIR, "apprise-test.png"))
    attach.add(os.path.join(TEST_VAR_DIR, "apprise-test.gif"))
    attach.add(os.path.join(TEST_VAR_DIR, "apprise-test.jpeg"))
    assert (
        obj.notify(
            body="Multi-page fax",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is True
    )


@mock.patch("requests.post")
def test_plugin_notifyre_fax_no_content(mock_post):
    """Fax with empty body and no attachments returns False."""
    obj = NotifyNotifyre(apikey=API_KEY, targets=["+15551234567"], mode="fax")
    # Simulate empty body (post title-merge the framework would send "")
    result = obj._send_fax("")
    assert result is False
    assert mock_post.call_count == 0


def test_plugin_notifyre_body_maxlen():
    """body_maxlen property returns the correct limit per mode."""
    obj_sms = NotifyNotifyre(apikey=API_KEY, targets=["+15551234567"])
    assert obj_sms.body_maxlen == 160

    obj_fax = NotifyNotifyre(
        apikey=API_KEY, targets=["+15551234567"], mode="fax"
    )
    assert obj_fax.body_maxlen == 32768


def test_plugin_notifyre_url_round_trip():
    """url() -> parse_url() -> re-instantiate produces an equivalent object."""

    # SMS mode
    obj1 = NotifyNotifyre(apikey=API_KEY, targets=["+15551234567"])
    result = NotifyNotifyre.parse_url(obj1.url())
    obj2 = NotifyNotifyre(**result)
    assert obj1.url_identifier == obj2.url_identifier
    assert len(obj1.targets) == len(obj2.targets)

    # Fax mode with source
    obj1 = NotifyNotifyre(
        apikey=API_KEY,
        targets=["+15551234567", "+15559876543"],
        mode="fax",
        source="+15550000001",
    )
    result = NotifyNotifyre.parse_url(obj1.url())
    obj2 = NotifyNotifyre(**result)
    assert obj1.url_identifier == obj2.url_identifier
    assert len(obj1.targets) == len(obj2.targets)

    # Fax mode with all optional parameters
    obj1 = NotifyNotifyre(
        apikey=API_KEY,
        targets=["+15551234567"],
        mode="fax",
        campaign="MyCampaign",
        template="MyTemplate",
        ref="CR-001",
        hq=False,
        header="CONFIDENTIAL",
    )
    result = NotifyNotifyre.parse_url(obj1.url())
    obj2 = NotifyNotifyre(**result)
    assert obj2.campaign == "MyCampaign"
    assert obj2.template == "MyTemplate"
    assert obj2.ref == "CR-001"
    assert obj2.hq is False
    assert obj2.header == "CONFIDENTIAL"

    # SMS mode with custom campaign -- campaign appears in URL
    obj1 = NotifyNotifyre(
        apikey=API_KEY,
        targets=["+15551234567"],
        campaign="SmsCampaign",
    )
    url = obj1.url()
    assert "campaign=SmsCampaign" in url
    result = NotifyNotifyre.parse_url(url)
    obj2 = NotifyNotifyre(**result)
    assert obj2.campaign == "SmsCampaign"

    # Default campaign (== app_id) is NOT included in the URL
    obj1 = NotifyNotifyre(apikey=API_KEY, targets=["+15551234567"])
    assert "campaign" not in obj1.url()


def test_plugin_notifyre_url_parsing():
    """parse_url() handles all supported query-parameter forms."""

    # Basic SMS URL
    result = NotifyNotifyre.parse_url(
        "notifyre://{}/+15551234567".format(API_KEY)
    )
    assert result["apikey"] == API_KEY
    assert "+15551234567" in result["targets"]

    # ?to= parameter appends additional targets
    result = NotifyNotifyre.parse_url(
        "notifyre://{}/?to=+15551234567".format(API_KEY)
    )
    assert "+15551234567" in result["targets"]

    # ?mode=fax
    result = NotifyNotifyre.parse_url(
        "notifyre://{}/+15551234567?mode=fax".format(API_KEY)
    )
    assert result["mode"] == "fax"

    # ?from= source number
    result = NotifyNotifyre.parse_url(
        "notifyre://{}/+15551234567?from=%2B15559876543".format(API_KEY)
    )
    assert result["source"] == "+15559876543"

    # ?campaign= custom campaign name
    result = NotifyNotifyre.parse_url(
        "notifyre://{}/+15551234567?campaign=MyCampaign".format(API_KEY)
    )
    assert result["campaign"] == "MyCampaign"

    # ?template= fax template name
    result = NotifyNotifyre.parse_url(
        "notifyre://{}/+15551234567?template=MyTpl".format(API_KEY)
    )
    assert result["template"] == "MyTpl"

    # ?ref= client reference
    result = NotifyNotifyre.parse_url(
        "notifyre://{}/+15551234567?ref=CR-001".format(API_KEY)
    )
    assert result["ref"] == "CR-001"

    # ?hq=no -> False
    result = NotifyNotifyre.parse_url(
        "notifyre://{}/+15551234567?hq=no".format(API_KEY)
    )
    assert result["hq"] is False

    # ?hq=yes -> True
    result = NotifyNotifyre.parse_url(
        "notifyre://{}/+15551234567?hq=yes".format(API_KEY)
    )
    assert result["hq"] is True

    # ?header= fax cover page header
    result = NotifyNotifyre.parse_url(
        "notifyre://{}/+15551234567?header=CONF".format(API_KEY)
    )
    assert result["header"] == "CONF"

    # A URL with a different schema is not matched by parse_native_url
    assert NotifyNotifyre.parse_native_url("https://notifyre.com/") is None


def test_plugin_notifyre_privacy_url():
    """Privacy URL masks the API key."""
    obj = NotifyNotifyre(apikey=API_KEY, targets=["+15551234567"])
    priv = obj.url(privacy=True)
    # API key should be masked
    assert API_KEY not in priv
    # Targets should remain visible
    assert "+15551234567" in priv


@mock.patch("requests.post")
def test_plugin_notifyre_sms_campaign(mock_post):
    """campaign parameter appears in the SMS API payload."""

    def _mk_resp(d, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = json.dumps(d).encode()
        return r

    mock_post.return_value = _mk_resp(GOOD_RESPONSE)

    # Custom campaign name
    obj = NotifyNotifyre(
        apikey=API_KEY,
        targets=["+15551234567"],
        campaign="MyCampaign",
    )
    assert obj.notify(body="Hello", notify_type=NotifyType.INFO) is True
    posted = json.loads(mock_post.call_args[1]["data"])
    assert posted["campaignName"] == "MyCampaign"

    # Default campaign = app_id
    mock_post.reset_mock()
    mock_post.return_value = _mk_resp(GOOD_RESPONSE)
    obj = NotifyNotifyre(apikey=API_KEY, targets=["+15551234567"])
    assert obj.notify(body="Hello", notify_type=NotifyType.INFO) is True
    posted = json.loads(mock_post.call_args[1]["data"])
    assert posted["campaignName"] == obj.app_id


@mock.patch("requests.post")
def test_plugin_notifyre_fax_params(mock_post):
    """template, ref, hq, header, and campaign appear in the fax payload."""

    def _mk_resp(d, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = json.dumps(d).encode()
        return r

    mock_post.return_value = _mk_resp(GOOD_RESPONSE)

    obj = NotifyNotifyre(
        apikey=API_KEY,
        targets=["+15551234567"],
        mode="fax",
        campaign="FaxCampaign",
        template="CoverTpl",
        ref="CR-999",
        hq=False,
        header="CONFIDENTIAL",
    )
    assert obj.notify(body="Fax body", notify_type=NotifyType.INFO) is True
    posted = json.loads(mock_post.call_args[1]["data"])
    assert posted["campaignName"] == "FaxCampaign"
    assert posted["templateName"] == "CoverTpl"
    assert posted["clientReference"] == "CR-999"
    assert posted["isHighQuality"] is False
    assert posted["header"] == "CONFIDENTIAL"

    # subject is the full body without truncation
    assert posted["subject"] == "Fax body"

    # Defaults: hq=True, empty strings for template/ref/header
    mock_post.reset_mock()
    mock_post.return_value = _mk_resp(GOOD_RESPONSE)
    obj = NotifyNotifyre(apikey=API_KEY, targets=["+15551234567"], mode="fax")
    assert obj.notify(body="Test", notify_type=NotifyType.INFO) is True
    posted = json.loads(mock_post.call_args[1]["data"])
    assert posted["isHighQuality"] is True
    assert posted["templateName"] == ""
    assert posted["clientReference"] == ""
    assert posted["header"] == ""
    assert posted["campaignName"] == obj.app_id


@mock.patch("requests.post")
def test_plugin_notifyre_apprise_integration(mock_post):
    """Apprise.add() + Apprise.notify() integration for both modes."""

    def _mk_resp(d, code=requests.codes.ok):
        r = mock.Mock()
        r.status_code = code
        r.content = json.dumps(d).encode()
        return r

    mock_post.return_value = _mk_resp(GOOD_RESPONSE)

    # SMS via string URL
    app = Apprise()
    assert app.add("notifyre://{}/+15551234567".format(API_KEY))
    assert app.notify(title="Title", body="Body") is True

    # Fax via string URL
    app = Apprise()
    assert app.add("notifyre://{}/+15551234567?mode=fax".format(API_KEY))
    assert app.notify(title="Title", body="Body") is True
