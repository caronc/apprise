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
from hashlib import sha1
import json
import logging
from unittest import mock
from urllib.parse import urlparse

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, NotifyType
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.opsimate import NotifyOpsiMate

logging.disable(logging.CRITICAL)

# The token a default OpsiMate installation ships with
TOKEN = "opsimate"

# Our Testing URLs
apprise_url_tests = (
    (
        "opsimate://",
        {
            # No host specified
            "instance": None,
        },
    ),
    (
        "opsimate://localhost",
        {
            # No API token specified
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "opsimate://%20@localhost",
        {
            # A blank API token
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "opsimate://{}@localhost".format(TOKEN),
        {
            # A valid token and host
            "instance": NotifyOpsiMate,
            "privacy_url": "opsimate://o...e@localhost/",
        },
    ),
    (
        "opsimate://{}@localhost:3001".format(TOKEN),
        {
            # A port
            "instance": NotifyOpsiMate,
            "privacy_url": "opsimate://o...e@localhost:3001/",
        },
    ),
    (
        "opsimates://{}@opsimate.example.com".format(TOKEN),
        {
            # A secure connection
            "instance": NotifyOpsiMate,
            "privacy_url": "opsimates://o...e@opsimate.example.com/",
        },
    ),
    (
        "opsimate://localhost?apikey={}".format(TOKEN),
        {
            # The token supplied as an argument
            "instance": NotifyOpsiMate,
        },
    ),
    (
        "opsimate://localhost?token={}".format(TOKEN),
        {
            # The token supplied as an argument using its other name
            "instance": NotifyOpsiMate,
        },
    ),
    (
        "opsimate://{}@localhost:3001?id=disk-full&team=platform"
        "&resolve=yes&+env=prod&+region=eu".format(TOKEN),
        {
            # Every option in use
            "instance": NotifyOpsiMate,
        },
    ),
    (
        "opsimate://{}@localhost".format(TOKEN),
        {
            "instance": NotifyOpsiMate,
            # A validation error has been returned by the server
            "response": False,
            "requests_response_code": requests.codes.bad_request,
        },
    ),
    (
        "opsimate://{}@localhost".format(TOKEN),
        {
            "instance": NotifyOpsiMate,
            # An invalid token has been refused by the server
            "response": False,
            "requests_response_code": requests.codes.unauthorized,
        },
    ),
    (
        "opsimate://{}@localhost".format(TOKEN),
        {
            "instance": NotifyOpsiMate,
            # An unknown response code
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "opsimate://{}@localhost".format(TOKEN),
        {
            "instance": NotifyOpsiMate,
            # Socket errors are handled
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_opsimate_urls():
    """NotifyOpsiMate() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_opsimate_payload(mock_post):
    """NotifyOpsiMate() builds the alert it sends."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b'{"success":true}'
    mock_post.return_value = response

    obj = Apprise.instantiate(
        "opsimates://{}@opsimate.example.com:8443/?team=platform"
        "&+env=prod&+region=eu".format(TOKEN)
    )
    assert isinstance(obj, NotifyOpsiMate)
    assert obj.team == "platform"
    assert obj.resolve is False
    assert obj.alert_id is None

    assert obj.notify(
        title="Disk full on web-01",
        body="Disk usage at 98 percent",
        notify_type=NotifyType.FAILURE,
    )

    # One post to the Custom Alerts API of our host
    assert mock_post.call_count == 1
    url = mock_post.call_args[0][0]
    assert url == "https://opsimate.example.com:8443/api/v1/alerts/custom"
    assert urlparse(url).scheme == "https"

    # The token travels in a header
    headers = mock_post.call_args[1]["headers"]
    assert headers["x-api-token"] == TOKEN
    assert headers["Content-Type"] == "application/json"
    assert "Authorization" not in headers

    # The other request options follow the plugin's settings
    assert mock_post.call_args[1]["verify"] is True
    assert mock_post.call_args[1]["timeout"] == obj.request_timeout

    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload == {
        "id": "apprise-{}".format(
            sha1(b"disk full on web-01").hexdigest()[:16]
        ),
        "alertName": "Disk full on web-01",
        "summary": "Disk usage at 98 percent",
        "severity": "critical",
        "status": "firing",
        "tags": {
            "env": "prod",
            "region": "eu",
            "source": "apprise",
            "team": "platform",
        },
        "team": "platform",
    }

    # A plain http URL on the default port
    mock_post.reset_mock()
    obj = Apprise.instantiate("opsimate://{}@localhost".format(TOKEN))
    assert obj.notify(title="Disk full", body="web-01")
    assert mock_post.call_args[0][0] == (
        "http://localhost/api/v1/alerts/custom"
    )
    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["tags"] == {"source": "apprise"}
    assert "team" not in payload


@mock.patch("requests.post")
def test_plugin_opsimate_severity(mock_post):
    """NotifyOpsiMate() maps each notification type to a severity."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b""
    mock_post.return_value = response

    obj = NotifyOpsiMate(apikey=TOKEN, host="localhost")
    for notify_type, severity in (
        (NotifyType.INFO, "info"),
        (NotifyType.SUCCESS, "info"),
        (NotifyType.WARNING, "warning"),
        (NotifyType.FAILURE, "critical"),
    ):
        assert obj.notify(
            title="Disk full", body="web-01", notify_type=notify_type
        )
        payload = json.loads(mock_post.call_args[1]["data"])
        assert payload["severity"] == severity

        # Without ?resolve=yes every notification fires the alert
        assert payload["status"] == "firing"


@mock.patch("requests.post")
def test_plugin_opsimate_resolve(mock_post):
    """NotifyOpsiMate() resolves on success when asked to."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b""
    mock_post.return_value = response

    def sent():
        return json.loads(mock_post.call_args[1]["data"])

    obj = Apprise.instantiate(
        "opsimate://{}@localhost:3001?resolve=yes".format(TOKEN)
    )
    assert isinstance(obj, NotifyOpsiMate)
    assert obj.resolve is True

    # A failure fires the alert
    assert obj.notify(
        title="Disk full", body="at 98%", notify_type=NotifyType.FAILURE
    )
    fired = sent()
    assert fired["status"] == "firing"
    assert fired["severity"] == "critical"

    # A success with the same title resolves that very alert.  Only the
    # id and the status travel, so OpsiMate keeps the name, severity and
    # summary the alert was fired with.
    assert obj.notify(
        title="Disk full", body="at 40%", notify_type=NotifyType.SUCCESS
    )
    assert sent() == {"id": fired["id"], "status": "resolved"}

    # Without a title the id still comes from the first line of the body
    assert obj.notify(body="Disk full\nat 40%", notify_type=NotifyType.SUCCESS)
    assert sent() == {"id": fired["id"], "status": "resolved"}

    # A fixed id resolves whatever it names
    fixed = NotifyOpsiMate(
        apikey=TOKEN, host="localhost", alert_id="disk-01", resolve=True
    )
    assert fixed.notify(
        title="anything", body="x", notify_type=NotifyType.SUCCESS
    )
    assert sent() == {"id": "disk-01", "status": "resolved"}

    # Other notification types still fire even with resolve set
    for notify_type in (NotifyType.INFO, NotifyType.WARNING):
        assert obj.notify(
            title="Disk full", body="hmm", notify_type=notify_type
        )
        assert sent()["status"] == "firing"


@mock.patch("requests.post")
def test_plugin_opsimate_alert_id(mock_post):
    """NotifyOpsiMate() derives a stable id or uses the one given."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b""
    mock_post.return_value = response

    def sent():
        return json.loads(mock_post.call_args[1]["data"])

    obj = NotifyOpsiMate(apikey=TOKEN, host="localhost")

    # The same title always yields the same id, whatever the case or the
    # surrounding whitespace
    assert obj.notify(title="Disk full", body="a")
    first = sent()["id"]
    assert first == "apprise-{}".format(sha1(b"disk full").hexdigest()[:16])
    assert obj.notify(title="  DISK FULL ", body="b")
    assert sent()["id"] == first

    # A different title is a different alert
    assert obj.notify(title="CPU hot", body="a")
    assert sent()["id"] != first

    # Without a title, the first line of the body names the alert and
    # yields the id
    assert obj.notify(body="Disk full\nat 98% on web-01")
    payload = sent()
    assert payload["alertName"] == "Disk full"
    assert payload["summary"] == "Disk full\nat 98% on web-01"
    assert payload["id"] == first

    # A long first line is cut to a sensible alert name
    assert obj.notify(body="x" * 300)
    assert sent()["alertName"] == "x" * obj.opsimate_alert_name_maxlen

    # An explicit id always wins
    obj = NotifyOpsiMate(apikey=TOKEN, host="localhost", alert_id="disk-01")
    assert obj.notify(title="Disk full", body="a")
    assert sent()["id"] == "disk-01"
    assert obj.notify(title="Something else", body="a")
    assert sent()["id"] == "disk-01"


@mock.patch("requests.post")
def test_plugin_opsimate_tags(mock_post):
    """NotifyOpsiMate() always tags the source and keeps the team."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b""
    mock_post.return_value = response

    def sent():
        return json.loads(mock_post.call_args[1]["data"])

    # No extras: only the source tag
    obj = NotifyOpsiMate(apikey=TOKEN, host="localhost")
    assert obj.notify(title="Disk full", body="a")
    assert sent()["tags"] == {"source": "apprise"}

    # Custom tags ride along; the source tag can not be overwritten
    obj = Apprise.instantiate(
        "opsimate://{}@localhost?+env=prod&+source=cron".format(TOKEN)
    )
    assert obj.tags == {"env": "prod", "source": "cron"}
    assert obj.notify(title="Disk full", body="a")
    assert sent()["tags"] == {"env": "prod", "source": "apprise"}

    # The team is a tag and the owning team of the alert
    obj = NotifyOpsiMate(apikey=TOKEN, host="localhost", team="platform")
    assert obj.notify(title="Disk full", body="a")
    payload = sent()
    assert payload["tags"] == {"source": "apprise", "team": "platform"}
    assert payload["team"] == "platform"


def test_plugin_opsimate_init():
    """NotifyOpsiMate() init and url round trip."""

    obj = NotifyOpsiMate(
        apikey=TOKEN,
        host="localhost",
        port=3001,
        alert_id="  disk-01  ",
        team="  ",
        resolve="yes",
        tags={"env": "prod"},
    )
    assert obj.alert_id == "disk-01"
    assert obj.team is None
    assert obj.resolve is True
    assert obj.tags == {"env": "prod"}
    assert len(obj) == 1

    # The URL survives a round trip
    url = obj.url()
    assert url.startswith("opsimate://{}@localhost:3001/?".format(TOKEN))
    result = NotifyOpsiMate.parse_url(url)
    obj2 = NotifyOpsiMate(**result)
    assert obj.url_identifier == obj2.url_identifier
    assert obj2.alert_id == "disk-01"
    assert obj2.team is None
    assert obj2.resolve is True
    assert obj2.tags == {"env": "prod"}
    assert obj2.port == 3001
    assert obj2.secure is False

    # Privacy mode hides the token
    assert obj.url(privacy=True).startswith("opsimate://o...e@localhost:3001/")
    assert "{}@".format(TOKEN) not in obj.url(privacy=True)
    secret = NotifyOpsiMate(apikey="s3cr3t-t0ken", host="localhost")
    assert "s3cr3t-t0ken" in secret.url()
    assert "s3cr3t-t0ken" not in secret.url(privacy=True)
    assert secret.url(privacy=True).startswith("opsimate://s...n@localhost/")

    # Every other option survives too, over a secure connection
    obj = Apprise.instantiate(
        "opsimates://{}@opsimate.example.com/?team=platform".format(TOKEN)
    )
    assert isinstance(obj, NotifyOpsiMate)
    assert obj.secure is True
    assert obj.apikey == TOKEN
    result = NotifyOpsiMate.parse_url(obj.url())
    obj2 = NotifyOpsiMate(**result)
    assert obj2.secure is True
    assert obj2.team == "platform"
    assert obj2.resolve is False
    assert obj2.alert_id is None
    assert obj2.tags == {}
    assert obj.url_identifier == obj2.url_identifier

    # The default port is left off the URL
    obj = NotifyOpsiMate(apikey=TOKEN, host="localhost", port=80)
    assert obj.url().startswith("opsimate://{}@localhost/?".format(TOKEN))

    # A token supplied as an argument lands in the same place
    obj = Apprise.instantiate("opsimate://localhost?token={}".format(TOKEN))
    assert obj.apikey == TOKEN
    obj = Apprise.instantiate("opsimate://localhost?apikey={}".format(TOKEN))
    assert obj.apikey == TOKEN

    # A missing or blank token is refused
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyOpsiMate(apikey="  ", host="localhost")

    with pytest.raises(AppriseImproperlyConfigured):
        NotifyOpsiMate(apikey=None, host="localhost")

    # A URL without a host can not be loaded
    assert NotifyOpsiMate.parse_url("opsimate://") is None
    assert Apprise.instantiate("opsimate://{}@".format(TOKEN)) is None


@mock.patch("requests.post")
def test_plugin_opsimate_errors(mock_post):
    """NotifyOpsiMate() reports validation and authentication errors."""

    obj = NotifyOpsiMate(apikey=TOKEN, host="localhost")
    obj.logger = mock.Mock()

    # A validation error names the fields OpsiMate rejected
    response = mock.Mock()
    response.status_code = requests.codes.bad_request
    response.content = json.dumps(
        {
            "success": False,
            "error": "Validation error",
            "details": [
                {
                    "expected": "string",
                    "code": "invalid_type",
                    "path": ["alertName"],
                    "message": "Invalid input: expected string",
                },
                "not-a-dict",
            ],
        }
    ).encode("utf-8")
    mock_post.return_value = response

    assert obj.notify(title="Disk full", body="a") is False
    warnings = [str(c) for c in obj.logger.warning.call_args_list]
    assert any("Validation error" in w for w in warnings)
    assert any(
        "alertName: Invalid input: expected string" in w for w in warnings
    )

    # A validation error without details falls back to the error text
    obj.logger.reset_mock()
    response.content = b'{"success": false, "error": "Bad alert"}'
    assert obj.notify(title="Disk full", body="a") is False
    warnings = [str(c) for c in obj.logger.warning.call_args_list]
    assert any("Bad alert" in w for w in warnings)

    # A 400 whose body is not JSON is still reported
    obj.logger.reset_mock()
    response.content = b"<html>nope</html>"
    assert obj.notify(title="Disk full", body="a") is False
    warnings = [str(c) for c in obj.logger.warning.call_args_list]
    assert any("nope" in w for w in warnings)

    # A 400 with an empty body
    obj.logger.reset_mock()
    response.content = None
    assert obj.notify(title="Disk full", body="a") is False
    assert obj.logger.warning.call_count == 2

    # A 400 whose JSON is not an object
    obj.logger.reset_mock()
    response.content = b"[1, 2]"
    assert obj.notify(title="Disk full", body="a") is False
    assert obj.logger.warning.call_count == 2

    # A bad token is an authentication error
    obj.logger.reset_mock()
    response.status_code = requests.codes.unauthorized
    response.content = b'{"success": false, "error": "Invalid API token"}'
    assert obj.notify(title="Disk full", body="a") is False
    warnings = [str(c) for c in obj.logger.warning.call_args_list]
    assert len(warnings) == 1
    assert "Authentication error" in warnings[0]

    # Any other failure is reported without extra detail
    obj.logger.reset_mock()
    response.status_code = requests.codes.internal_server_error
    response.content = b""
    assert obj.notify(title="Disk full", body="a") is False
    assert obj.logger.warning.call_count == 1

    # A connection error is handled
    obj.logger.reset_mock()
    mock_post.side_effect = requests.ConnectionError("boom")
    assert obj.notify(title="Disk full", body="a") is False
    warnings = [str(c) for c in obj.logger.warning.call_args_list]
    assert len(warnings) == 1
    assert "Connection error" in warnings[0]


@mock.patch("requests.post")
def test_plugin_opsimate_accepted_codes(mock_post):
    """NotifyOpsiMate() treats every 2xx the server may return as sent."""

    response = mock.Mock()
    response.content = b""
    mock_post.return_value = response

    obj = NotifyOpsiMate(apikey=TOKEN, host="localhost")
    for code in (
        requests.codes.ok,
        requests.codes.created,
        requests.codes.accepted,
        requests.codes.no_content,
    ):
        response.status_code = code
        assert obj.notify(title="Disk full", body="a") is True
