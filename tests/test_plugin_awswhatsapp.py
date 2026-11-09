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


from base64 import b64decode
from datetime import datetime, timezone
from json import dumps, loads

# Disable logging for a cleaner testing output
import logging
from unittest import mock
from urllib.parse import urlparse

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, AppriseAttachment, NotifyType
from apprise.attachment.memory import AttachMemory
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.awswhatsapp import NotifyAWSWhatsApp

logging.disable(logging.CRITICAL)

TEST_ACCESS_KEY_ID = "AHIAJGNT76XIMXDBIJYA"
TEST_ACCESS_KEY_SECRET = "bu1dHSdO22pfaaVy/wmNsdljF4C07D3bndi9PQJ9"
TEST_REGION = "us-east-2"
TEST_FROM = "phone-number-id-0123456789abcdef0123456789abcdef"

# A realistic-looking (but fake) AWS session token
TEST_SESSION_TOKEN = "FwoGZXIvYXdz+SESSION/TOKENABCDEFGHIJKLMNOPQRS="

# Credentials, region and sender shared by the URLs below
BASE = (
    f"awswhatsapp://{TEST_ACCESS_KEY_ID}/{TEST_ACCESS_KEY_SECRET}/"
    f"{TEST_REGION}/{TEST_FROM}"
)

# A successful AWS response
AWS_OK = dumps({"messageId": "msg-1", "mediaId": "media-1"})

# Our Testing URLs
apprise_url_tests = (
    (
        "awswhatsapp://",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "awswhatsapp://:@/",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"awswhatsapp://{TEST_ACCESS_KEY_ID}/{TEST_ACCESS_KEY_SECRET}/",
        {
            # Missing a region (and our From Phone ID)
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"awswhatsapp://{TEST_ACCESS_KEY_ID}/{TEST_ACCESS_KEY_SECRET}/"
        f"{TEST_REGION}",
        {
            # Missing our From Phone ID
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"awswhatsapp://{TEST_ACCESS_KEY_ID}/{TEST_ACCESS_KEY_SECRET}/"
        f"{TEST_REGION}/12345/15551234567",
        {
            # Invalid From Phone ID
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        BASE,
        {
            # No targets; we load but have no one to notify
            "instance": NotifyAWSWhatsApp,
            "notify_response": False,
        },
    ),
    (
        f"{BASE}/15551234567/abcd",
        {
            # One valid target; the invalid one is dropped
            "instance": NotifyAWSWhatsApp,
            "requests_response_text": AWS_OK,
            # No ?bucket= was given, so attachments can not be sent
            "attach_response": False,
            "privacy_url": "awswhatsapp://A...A/****/us-east-2/"
            f"{TEST_FROM}/%2B15551234567/",
        },
    ),
    (
        f"awswhatsapp://{TEST_SESSION_TOKEN.replace('/', '%2F')}@"
        f"{TEST_ACCESS_KEY_ID}/{TEST_ACCESS_KEY_SECRET}/{TEST_REGION}/"
        f"{TEST_FROM}/15551234567",
        {
            # Temporary credentials
            "instance": NotifyAWSWhatsApp,
            "requests_response_text": AWS_OK,
            "attach_response": False,
            "privacy_url": "awswhatsapp://F...=@A...A/****/",
        },
    ),
    (
        f"awswhatsapp://{TEST_ACCESS_KEY_ID}/{TEST_ACCESS_KEY_SECRET}/"
        f"{TEST_REGION}/{TEST_FROM}/?to=15551234567&key=newkey"
        "&secret=newsecret&region=us-west-1&token=abc",
        {
            # Argument overrides
            "instance": NotifyAWSWhatsApp,
            "requests_response_text": AWS_OK,
            "attach_response": False,
            "privacy_url": "awswhatsapp://a...c@n...y/****/us-west-1/",
        },
    ),
    (
        f"{BASE}/15551234567?access=newkey",
        {
            # ?access= works too
            "instance": NotifyAWSWhatsApp,
            "privacy_url": "awswhatsapp://n...y/****/",
            "requests_response_text": AWS_OK,
            "attach_response": False,
        },
    ),
    (
        f"{BASE}/15551234567?template=alerts&lang=fr_FR&:body=1&:type=2",
        {
            # A template
            "instance": NotifyAWSWhatsApp,
            "requests_response_text": AWS_OK,
            "attach_response": False,
        },
    ),
    (
        f"{BASE}/15551234567?template=bad%20name",
        {
            # Invalid template name
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"{BASE}/15551234567?template=alerts&lang=12",
        {
            # Invalid template language
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"{BASE}/15551234567?template=alerts&:invalid-name=1",
        {
            # Invalid template component id
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"{BASE}/15551234567?template=alerts&:body=invalid-name",
        {
            # Invalid template component mapping
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"{BASE}/15551234567?template=alerts&:body=1&:1=text",
        {
            # Template component index assigned twice
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"{BASE}/15551234567?bucket=-bad-",
        {
            # Invalid S3 bucket
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"{BASE}/15551234567",
        {
            "instance": NotifyAWSWhatsApp,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        f"{BASE}/15551234567",
        {
            "instance": NotifyAWSWhatsApp,
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        f"{BASE}/15551234567",
        {
            "instance": NotifyAWSWhatsApp,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def aws_response(code=requests.codes.ok, content=AWS_OK):
    """Return a mocked AWS response."""
    r = mock.Mock()
    r.status_code = code
    r.content = content.encode("utf-8") if content is not None else None
    return r


def sent(mock_post):
    """Return the WhatsApp messages decoded from each send request."""
    return [
        loads(b64decode(loads(c.kwargs["data"])["message"]))
        for c in mock_post.call_args_list
        if c.args[0].endswith("/v1/whatsapp/send")
    ]


def attachment(name="photo.png", mimetype="image/png"):
    """Return an in-memory attachment."""
    return AttachMemory(content=b"data", name=name, mimetype=mimetype)


def test_plugin_awswhatsapp_urls():
    """NotifyAWSWhatsApp() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_awswhatsapp_signature():
    """Requests are signed exactly as the AWS SDK signs them."""

    obj = NotifyAWSWhatsApp(
        access_key_id="AKIAEXAMPLE",
        secret_access_key="wJalr/XUtnFEMI+K7MDENG=bPxRfiCYEXAMPLEKEY",
        region_name="us-east-1",
        from_phone_id=TEST_FROM,
        targets="15551234567",
    )

    # The expected value was produced by botocore's SigV4Auth for the
    # same request at the same moment
    with mock.patch("apprise.plugins.awswhatsapp.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(
            2026, 11, 6, 12, 34, 56, tzinfo=timezone.utc
        )
        headers = obj.aws_prepare_request(
            "POST",
            obj.notify_host,
            "/v1/whatsapp/send",
            "social-messaging",
            # sha256 of an empty payload
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            {"Content-Type": "application/json"},
        )

    assert headers["X-Amz-Date"] == "20261106T123456Z"
    assert headers["Authorization"] == (
        "AWS4-HMAC-SHA256 Credential=AKIAEXAMPLE/20261106/us-east-1/"
        "social-messaging/aws4_request, "
        "SignedHeaders=content-type;host;x-amz-date, "
        "Signature=bc8607ee7208b082401cce2853edc250947036e0a9d2875999c30d"
        "5a555c9363"
    )


@mock.patch("requests.post")
def test_plugin_awswhatsapp_send(mock_post):
    """A message reaches every target."""

    mock_post.return_value = aws_response()

    obj = Apprise.instantiate(
        f"awswhatsapp://{TEST_SESSION_TOKEN.replace('/', '%2F')}@"
        f"{TEST_ACCESS_KEY_ID}/{TEST_ACCESS_KEY_SECRET}/{TEST_REGION}/"
        f"{TEST_FROM}/+1 (555) 123-4567/15557654321"
    )
    assert isinstance(obj, NotifyAWSWhatsApp)
    assert len(obj) == 2

    assert obj.notify(title="Alert", body="Disk is full") is True
    assert mock_post.call_count == 2

    # Our request went to the regional AWS WhatsApp endpoint
    url = mock_post.call_args_list[0].args[0]
    assert urlparse(url).hostname == (
        "social-messaging.us-east-2.amazonaws.com"
    )

    # Our session token is sent and signed
    headers = mock_post.call_args_list[0].kwargs["headers"]
    assert headers["X-Amz-Security-Token"] == TEST_SESSION_TOKEN
    assert "x-amz-security-token" in headers["Authorization"]

    # Our sender and Meta API version
    payload = loads(mock_post.call_args_list[0].kwargs["data"])
    assert payload["originationPhoneNumberId"] == TEST_FROM
    assert payload["metaApiVersion"] == "v23.0"

    # Our WhatsApp message; the title is merged into the body
    messages = sent(mock_post)
    assert messages[0] == {
        "messaging_product": "whatsapp",
        "to": "+15551234567",
        "type": "text",
        "text": {"body": "Alert\r\nDisk is full"},
    }
    assert messages[1]["to"] == "+15557654321"

    # A response that is not a JSON object is still a success
    mock_post.return_value = aws_response(content="[]")
    assert obj.notify(body="test") is True

    mock_post.return_value = aws_response(content="not json")
    assert obj.notify(body="test") is True


def test_plugin_awswhatsapp_invalid_region():
    """An invalid region is rejected."""

    with pytest.raises(AppriseImproperlyConfigured):
        NotifyAWSWhatsApp(
            access_key_id=TEST_ACCESS_KEY_ID,
            secret_access_key=TEST_ACCESS_KEY_SECRET,
            region_name="nowhere",
            from_phone_id=TEST_FROM,
        )


@mock.patch("requests.post")
def test_plugin_awswhatsapp_template(mock_post):
    """Templates are filled in by index."""

    mock_post.return_value = aws_response()

    # Parameters are placed in index order no matter how they are given
    obj = Apprise.instantiate(
        f"{BASE}/15551234567?template=system_alert&lang=pt_BR"
        "&:3=Production&:body=1&:type=2"
    )
    assert obj.notify(body="Backup failed", notify_type=NotifyType.FAILURE)

    message = sent(mock_post)[0]
    assert message["type"] == "template"
    assert message["template"] == {
        "name": "system_alert",
        "language": {"code": "pt_BR"},
        "components": [
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": "Backup failed"},
                    {"type": "text", "text": "failure"},
                    {"type": "text", "text": "Production"},
                ],
            }
        ],
    }

    # A template without parameters is sent as-is
    mock_post.reset_mock()
    obj = Apprise.instantiate(f"{BASE}/15551234567?template=hello_world")
    assert obj.notify(body="ignored")
    assert sent(mock_post)[0]["template"] == {
        "name": "hello_world",
        "language": {"code": "en_US"},
    }


def test_plugin_awswhatsapp_url_parsing():
    """A URL rebuilds the same object when parsed again."""

    obj = Apprise.instantiate(
        f"{BASE}/15551234567/15557654321?token={TEST_SESSION_TOKEN}"
        "&template=alerts&lang=fr_FR&:body=1&:2=Production&bucket=staging"
    )
    clone = Apprise.instantiate(obj.url())

    assert clone.url_identifier == obj.url_identifier
    assert clone.targets == obj.targets
    assert clone.aws_session_token == TEST_SESSION_TOKEN
    assert clone.aws_secret_access_key == TEST_ACCESS_KEY_SECRET
    assert clone.template == "alerts"
    assert clone.language == "fr_FR"
    assert clone.components == obj.components
    assert clone.bucket == "staging"

    # Without a region, there is nothing to find our sender after
    result = NotifyAWSWhatsApp.parse_url(
        f"awswhatsapp://{TEST_ACCESS_KEY_ID}/{TEST_ACCESS_KEY_SECRET}"
    )
    assert result["from_phone_id"] is None
    assert result["targets"] == []


@mock.patch("requests.delete")
@mock.patch("requests.put")
@mock.patch("requests.post")
def test_plugin_awswhatsapp_attachments(mock_post, mock_put, mock_delete):
    """Attachments are staged in S3, imported, sent and cleaned up."""

    mock_post.return_value = aws_response()
    mock_put.return_value = aws_response(content="")
    mock_delete.return_value = aws_response(requests.codes.no_content, "")

    obj = Apprise.instantiate(f"{BASE}/15551234567?bucket=staging")
    attach = AppriseAttachment()
    attach.add(attachment())
    attach.add(attachment("report.pdf", "application/pdf"))

    assert obj.notify(body="Here you go", attach=attach) is True

    # Each file was staged in our bucket
    assert mock_put.call_count == 2
    put_url = urlparse(mock_put.call_args_list[0].args[0])
    assert put_url.hostname == "staging.s3.us-east-2.amazonaws.com"
    assert put_url.path.startswith("/apprise/")
    headers = mock_put.call_args_list[0].kwargs["headers"]
    assert headers["Content-Type"] == "image/png"
    assert headers["X-Amz-Content-Sha256"] == "UNSIGNED-PAYLOAD"

    # ... imported into WhatsApp ...
    imported = loads(mock_post.call_args_list[0].kwargs["data"])
    assert imported["sourceS3File"] == {
        "bucketName": "staging",
        "key": put_url.path[1:],
    }

    # ... and removed again
    assert mock_delete.call_count == 2
    assert (
        mock_delete.call_args_list[0].args[0]
        == (mock_put.call_args_list[0].args[0])
    )

    # Our text is followed by one message per attachment
    messages = sent(mock_post)
    assert [m["type"] for m in messages] == ["text", "image", "document"]
    assert messages[1]["image"] == {"id": "media-1"}
    assert messages[2]["document"] == {
        "id": "media-1",
        "filename": "report.pdf",
    }

    # Attachments can be sent without a body
    mock_post.reset_mock()
    assert obj.notify(body="", attach=attachment()) is True
    assert [m["type"] for m in sent(mock_post)] == ["image"]

    # A failed clean up does not fail the notification
    mock_delete.return_value = aws_response(requests.codes.forbidden, "")
    assert obj.notify(body="test", attach=attachment()) is True


@mock.patch("requests.delete")
@mock.patch("requests.put")
@mock.patch("requests.post")
def test_plugin_awswhatsapp_attachment_failures(
    mock_post, mock_put, mock_delete
):
    """An attachment that can not be uploaded fails the notification."""

    mock_post.return_value = aws_response()
    mock_put.return_value = aws_response(content="")
    mock_delete.return_value = aws_response(requests.codes.no_content, "")

    obj = Apprise.instantiate(f"{BASE}/15551234567?bucket=staging")

    # Inaccessible file
    with mock.patch("os.path.isfile", return_value=False):
        attach = AppriseAttachment("/no/such/file.png")
        assert obj.notify(body="test", attach=attach) is False

    # The file can not be read
    with mock.patch.object(AttachMemory, "open", side_effect=OSError()):
        assert obj.notify(body="test", attach=attachment()) is False

    # Nothing was uploaded or sent
    assert mock_put.call_count == 0
    assert mock_post.call_count == 0

    # S3 refuses our upload; nothing is imported or removed
    mock_put.return_value = aws_response(requests.codes.forbidden, None)
    assert obj.notify(body="test", attach=attachment()) is False
    mock_put.side_effect = requests.RequestException()
    assert obj.notify(body="test", attach=attachment()) is False
    assert mock_post.call_count == 0
    assert mock_delete.call_count == 0

    mock_put.side_effect = None
    mock_put.return_value = aws_response(content="")

    # WhatsApp refuses the import; our staged file is still removed
    mock_post.return_value = aws_response(requests.codes.bad_request, "{}")
    assert obj.notify(body="test", attach=attachment()) is False
    assert mock_delete.call_count == 1

    # The import response has no media ID
    mock_post.return_value = aws_response(content="{}")
    assert obj.notify(body="test", attach=attachment()) is False
    assert mock_delete.call_count == 2

    # Nothing was ever sent to our target
    assert sent(mock_post) == []


def test_plugin_awswhatsapp_retry_skips_delivered():
    """A retry only resends the messages that failed."""

    calls = []

    def post(url, data=None, **kwargs):
        # Refuse every message to our second target
        calls.append((url, data))
        if url.endswith("/v1/whatsapp/send"):
            to = loads(b64decode(loads(data)["message"]))["to"]
            if to == "+15559999999":
                return aws_response(requests.codes.bad_request, "{}")

        return aws_response()

    with (
        mock.patch("requests.post", side_effect=post),
        mock.patch("requests.put", return_value=aws_response(content="")),
        mock.patch(
            "requests.delete",
            return_value=aws_response(requests.codes.no_content, ""),
        ),
        # Keep the run quick; the delays are not what is being tested.
        mock.patch("apprise.plugins.base.time.sleep"),
        mock.patch("apprise.apprise.time.sleep"),
    ):
        aobj = Apprise()
        assert aobj.add(
            f"{BASE}/15551234567/15559999999?bucket=staging&retry=2&wait=0"
        )
        assert not aobj.notify(body="hello", attach=attachment())

    messages = [
        loads(b64decode(loads(data)["message"]))
        for url, data in calls
        if url.endswith("/v1/whatsapp/send")
    ]

    # The healthy target got the text and the image exactly once
    good = [m["type"] for m in messages if m["to"] == "+15551234567"]
    assert good == ["text", "image"]

    # The failing target was tried on every attempt
    bad = [m for m in messages if m["to"] == "+15559999999"]
    assert len(bad) == 3 * 2


@mock.patch("requests.post")
def test_plugin_awswhatsapp_named_template(mock_post):
    """Named parameters survive URL parsing and reach the Meta payload."""
    mock_post.return_value = aws_response()
    obj = Apprise.instantiate(
        f"{BASE}/15551234567?template=opt_in_agendamentos_pge&lang=pt_BR"
        "&:nome=TESTE%20Apprise"
    )
    assert isinstance(obj, NotifyAWSWhatsApp)
    clone = Apprise.instantiate(obj.url())
    assert clone.notify(body="ignored")
    assert sent(mock_post)[0]["template"]["components"][0]["parameters"] == [
        {"type": "text", "text": "TESTE Apprise", "parameter_name": "nome"}
    ]


@mock.patch("requests.post")
def test_plugin_awswhatsapp_dynamic_named_template(mock_post):
    mock_post.return_value = aws_response()
    obj = Apprise.instantiate(
        f"{BASE}/15551234567?template=alerts&:body=mensagem&:type=tipo&:nome=Test"
    )
    assert obj.notify(body="Alert", notify_type=NotifyType.FAILURE)
    params = sent(mock_post)[0]["template"]["components"][0]["parameters"]
    assert {p["parameter_name"]: p["text"] for p in params} == {
        "mensagem": "Alert",
        "tipo": "failure",
        "nome": "Test",
    }


@pytest.mark.parametrize(
    "mapping",
    [
        {"nome": "Test", "1": "Test"},
        {"body": "nome", "nome": "Test"},
        {"nome!": "Test"},
        {"body": "1trailing"},
    ],
)
def test_plugin_awswhatsapp_invalid_named_mapping(mapping):
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyAWSWhatsApp(
            access_key_id=TEST_ACCESS_KEY_ID,
            secret_access_key=TEST_ACCESS_KEY_SECRET,
            region_name=TEST_REGION,
            from_phone_id=TEST_FROM,
            template="alerts",
            template_mapping=mapping,
        )
