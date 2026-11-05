"""AWS WhatsApp URL, credential, delivery and SDK contract tests."""

import base64
import builtins
import importlib.util
from io import BytesIO
import json
from unittest import mock

import pytest

from apprise import Apprise, NotifyType
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.awswhatsapp import NotifyAWSWhatsApp

try:
    import boto3
    from botocore.awsrequest import AWSResponse
    from botocore.exceptions import (
        ClientError,
        EndpointConnectionError,
        NoCredentialsError,
    )
    from botocore.stub import Stubber
except ImportError:
    pytest.skip("boto3 is not installed", allow_module_level=True)

SENDER = "phone-number-id-01234567890123456789012345678901"
NUMBER = "+15555550123"
URL = f"awswhatsapp://us-east-1/{SENDER}/{NUMBER}"


@pytest.fixture
def sdk():
    """Intercept SDK sessions so tests never discover real AWS credentials."""
    with mock.patch("apprise.plugins.awswhatsapp.boto3.Session") as session:
        client = session.return_value.client.return_value
        client.send_whatsapp_message.return_value = {"messageId": "example-id"}
        yield session, client


def plugin(**kwargs):
    """Create a sender using only test configuration."""
    return NotifyAWSWhatsApp(
        region_name="us-east-1",
        from_phone_id=SENDER,
        targets=NUMBER,
        **kwargs,
    )


def test_text_and_default_credentials(sdk):
    """Apprise discovers the plugin and the SDK receives UTF-8 JSON bytes."""
    session, client = sdk
    app = Apprise()
    assert app.add(URL)
    session.assert_not_called()
    assert app.notify(body="Olá", title="Alert")
    session.assert_called_once_with()
    args, options = session.return_value.client.call_args
    assert args == ("socialmessaging",)
    assert options["region_name"] == "us-east-1"
    assert options["verify"] is True
    assert options["config"].retries["total_max_attempts"] == 1
    request = client.send_whatsapp_message.call_args.kwargs
    assert request["originationPhoneNumberId"] == SENDER
    assert request["metaApiVersion"] == "v23.0"
    assert isinstance(request["message"], bytes)
    payload = json.loads(request["message"])
    assert payload["to"] == NUMBER.lstrip("+")
    assert payload["type"] == "text"
    assert "Alert" in payload["text"]["body"]
    assert "Olá" in payload["text"]["body"]
    client.close.assert_called_once()


def test_url_roundtrip_and_credentials(sdk):
    """Secrets with reserved URL characters survive exactly one decoding."""
    original = plugin(
        access_key_id="AKIDEXAMPLE",
        secret_access_key="secret/+%2F=",
        session_token="session/+%2B=",
        template="system_alert",
        template_mapping={"body": "1", "2": "Literal + %2F"},
        language="pt_BR",
        meta_api_version="v24.0",
        verify=False,
        cto=7,
        rto=11,
    )
    restored = NotifyAWSWhatsApp(**NotifyAWSWhatsApp.parse_url(original.url()))
    assert restored.url() == original.url()
    assert restored.secret_access_key == "secret/+%2F="
    assert restored.session_token == "session/+%2B="
    assert restored.template_mapping == original.template_mapping
    assert restored.send("body")
    session, _ = sdk
    session.assert_called_once_with(
        aws_access_key_id="AKIDEXAMPLE",
        aws_secret_access_key="secret/+%2F=",
        aws_session_token="session/+%2B=",
    )
    options = session.return_value.client.call_args.kwargs
    assert options["verify"] is False
    assert options["config"].connect_timeout == 7
    assert options["config"].read_timeout == 11
    assert "secret" not in restored.url(privacy=True)
    assert "session" not in restored.url(privacy=True)


def test_template_mapping_and_numeric_order(sdk):
    """Position 10 follows 9, and literals are distinct from mapped values."""
    mapping = {str(i): str(i) for i in range(2, 11)}
    mapping.update(body="1", type="11")
    obj = plugin(template="system_alert", template_mapping=mapping)
    assert obj.send("Notification", notify_type=NotifyType.WARNING)
    payload = json.loads(
        sdk[1].send_whatsapp_message.call_args.kwargs["message"]
    )
    assert payload["template"] == {
        "name": "system_alert",
        "language": {"code": "en_US"},
        "components": [
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": value}
                    for value in [
                        "Notification",
                        *map(str, range(2, 11)),
                        "warning",
                    ]
                ],
            }
        ],
    }


def test_template_without_parameters(sdk):
    """Static approved templates do not gain unintended body parameters."""
    assert plugin(template="hello_world").send("ignored")
    payload = json.loads(
        sdk[1].send_whatsapp_message.call_args.kwargs["message"]
    )
    assert payload["template"] == {
        "name": "hello_world",
        "language": {"code": "en_US"},
    }


@pytest.mark.parametrize(
    "settings",
    [
        {"region_name": "invalid"},
        {"from_phone_id": "12345"},
        {"language": "123"},
        {"meta_api_version": "invalid"},
        {"access_key_id": "access"},
        {"secret_access_key": "secret"},
        {"session_token": "token"},
        {"template": ""},
        {"template": "INVALID NAME"},
        {"targets": "invalid"},
        {"template_mapping": {"body": "1"}},
        {"template": "alert", "template_mapping": {"body": "0"}},
        {"template": "alert", "template_mapping": {"3": "gap"}},
        {"template": "alert", "template_mapping": {"bad": "value"}},
        {"template": "alert", "template_mapping": {"body": "1", "1": "dup"}},
    ],
)
def test_invalid_configuration(settings, sdk):
    """Reject malformed configuration before any credential discovery."""
    options = {
        "region_name": "us-east-1",
        "from_phone_id": SENDER,
        "targets": NUMBER,
    }
    options.update(settings)
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyAWSWhatsApp(**options)
    sdk[0].assert_not_called()


def test_empty_targets_and_disabled(sdk):
    obj = NotifyAWSWhatsApp(region_name="us-east-1", from_phone_id=SENDER)
    assert len(obj) == 1
    assert not obj.send("body")
    obj = plugin()
    obj.enabled = False
    assert not obj.send("body")
    sdk[0].assert_not_called()


def test_parse_targets_and_identifier(sdk):
    results = NotifyAWSWhatsApp.parse_url(URL + "/?to=15555550124")
    obj = NotifyAWSWhatsApp(**results)
    assert obj.targets == [NUMBER, "+15555550124"]
    assert len(obj) == 2
    assert obj.url_identifier == ("awswhatsapp", "us-east-1", SENDER, None)
    assert NotifyAWSWhatsApp.parse_url("awswhatsapp://[") is None
    assert plugin().runtime_deps() == (
        "boto3",
        "botocore",
        "s3transfer",
        "jmespath",
    )


@pytest.mark.parametrize(
    "failure",
    [
        ClientError(
            {"Error": {"Code": "ThrottledRequestException"}},
            "SendWhatsAppMessage",
        ),
        EndpointConnectionError(endpoint_url="https://example.invalid"),
        NoCredentialsError(),
        {},
    ],
)
def test_failed_recipient_is_retried_without_resending_success(sdk, failure):
    """Apprise retries only failed recipients after partial success."""
    app = Apprise()
    assert app.add(URL + "/15555550124?retry=1&wait=0")
    sdk[1].send_whatsapp_message.side_effect = [
        {"messageId": "first"},
        failure,
        {"messageId": "second"},
    ]
    assert app.notify(body="body")
    targets = [
        json.loads(call.kwargs["message"])["to"]
        for call in sdk[1].send_whatsapp_message.call_args_list
    ]
    assert targets == ["15555550123", "15555550124", "15555550124"]


def test_client_initialization_failure(sdk):
    sdk[0].return_value.client.side_effect = NoCredentialsError()
    assert not plugin().send("body")


def test_missing_optional_sdk(monkeypatch):
    """Apprise can load the module without the optional AWS SDK installed."""
    import apprise.plugins.awswhatsapp as module

    original_import = builtins.__import__

    def without_sdk(name, *args, **kwargs):
        if name == "boto3":
            raise ImportError("AWS SDK not installed")
        return original_import(name, *args, **kwargs)

    spec = importlib.util.spec_from_file_location(
        "apprise.plugins._awswhatsapp_without_sdk", module.__file__
    )
    isolated = importlib.util.module_from_spec(spec)
    monkeypatch.setattr(builtins, "__import__", without_sdk)
    spec.loader.exec_module(isolated)
    assert not isolated.NotifyAWSWhatsApp.enabled
    assert not isolated.NotifyAWSWhatsApp(
        region_name="us-east-1",
        from_phone_id=SENDER,
        targets=NUMBER,
    ).send("body")


def test_duplicate_recipients(sdk):
    """Equivalent phone numbers receive only one request."""
    obj = NotifyAWSWhatsApp(
        region_name="us-east-1",
        from_phone_id=SENDER,
        targets=[NUMBER, NUMBER.lstrip("+")],
    )
    assert len(obj) == 1
    assert obj.send("body")
    sdk[1].send_whatsapp_message.assert_called_once()


def test_botocore_contract_and_wire_serialization():
    """Exercise real AWS models, base64 serialization and SigV4 offline."""
    client = boto3.client(
        "socialmessaging",
        region_name="us-east-1",
        aws_access_key_id="AKIDEXAMPLE",
        aws_secret_access_key="secret",
        aws_session_token="temporary-token",
    )
    obj = plugin()
    expected_message = json.dumps(
        {
            "messaging_product": "whatsapp",
            "to": "15555550123",
            "type": "text",
            "text": {"body": "Olá"},
        },
        ensure_ascii=False,
    ).encode("utf-8")
    with mock.patch("apprise.plugins.awswhatsapp.boto3.Session") as session:
        session.return_value.client.return_value = client
        with Stubber(client) as stub:
            stub.add_response(
                "send_whatsapp_message",
                {"messageId": "example"},
                {
                    "originationPhoneNumberId": SENDER,
                    "metaApiVersion": "v23.0",
                    "message": expected_message,
                },
            )
            assert obj.send("Olá")
            stub.assert_no_pending_responses()

        class RawResponse(BytesIO):
            def stream(self, amt=None, decode_content=False):
                yield self.read()

        response = AWSResponse(
            "https://social-messaging.us-east-1.amazonaws.com/v1/whatsapp/send",
            200,
            {"content-type": "application/json"},
            RawResponse(b'{"messageId":"example"}'),
        )
        with mock.patch.object(
            client._endpoint.http_session, "send", return_value=response
        ) as send:
            assert obj.send("Olá")
        request = send.call_args.args[0]
        assert request.url.endswith("/v1/whatsapp/send")
        wire = json.loads(request.body)
        assert base64.b64decode(wire["message"]) == expected_message
        assert b"AWS4-HMAC-SHA256" in request.headers["Authorization"]
        assert request.headers["X-Amz-Security-Token"] == b"temporary-token"
