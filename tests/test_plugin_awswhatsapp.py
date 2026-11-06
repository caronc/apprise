"""AWS WhatsApp URL, credential, delivery and SDK contract tests."""

import base64
import builtins
import importlib.util
from io import BytesIO
import json
from unittest import mock

import pytest

from apprise import Apprise, AppriseAttachment, NotifyType
from apprise.attachment.memory import AttachMemory
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.awswhatsapp import MEDIA_TYPES, NotifyAWSWhatsApp

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
    assert payload["to"] == NUMBER
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


def test_named_template_parameters(sdk):
    mapping = {
        "nome": "Joao Silva",
        "recurso": "Sala A",
        "data": "05/11/2026",
        "horario": "09:00",
        "protocolo": "TESTE",
    }
    obj = plugin(
        template="lembrete_agendamento",
        language="pt_BR",
        template_mapping=mapping,
    )
    restored = NotifyAWSWhatsApp(**NotifyAWSWhatsApp.parse_url(obj.url()))
    assert restored.send("unused")
    payload = json.loads(
        sdk[1].send_whatsapp_message.call_args.kwargs["message"]
    )
    assert payload["template"]["components"][0]["parameters"] == [
        {"type": "text", "parameter_name": key, "text": value}
        for key, value in sorted(mapping.items())
    ]


def test_named_dynamic_body_and_type(sdk):
    assert plugin(
        template="alert",
        template_mapping={
            "body": "mensagem",
            "type": "tipo",
        },
    ).send("Details", notify_type=NotifyType.WARNING)
    payload = json.loads(
        sdk[1].send_whatsapp_message.call_args.kwargs["message"]
    )
    assert payload["template"]["components"][0]["parameters"] == [
        {"type": "text", "parameter_name": "mensagem", "text": "Details"},
        {"type": "text", "parameter_name": "tipo", "text": "warning"},
    ]


@pytest.mark.parametrize(
    "mapping",
    [
        {"1": "positional", "nome": "named"},
        {"body": "nome", "nome": "duplicate"},
        {"body": "bad-name"},
    ],
)
def test_invalid_named_mappings(mapping, sdk):
    with pytest.raises(AppriseImproperlyConfigured):
        plugin(template="alert", template_mapping=mapping)
    sdk[0].assert_not_called()


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
        {"template": "alert", "template_mapping": {"bad-name": "value"}},
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
    assert targets == ["+15555550123", "+15555550124", "+15555550124"]


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


@pytest.fixture
def media_sdk(sdk):
    """Give S3 and Social separate mocks with no live credential access."""
    session, client = sdk
    s3 = mock.Mock()
    session.return_value.client.side_effect = lambda service, **kwargs: (
        s3 if service == "s3" else client
    )
    client.post_whatsapp_message_media.return_value = {"mediaId": "media123"}
    s3.generate_presigned_url.return_value = "https://example.invalid/signed"
    return session, client, s3


def attachment(mimetype="image/png", name="example.png"):
    """Use Apprise's real attachment abstraction for small test files."""
    file = AttachMemory(
        content=b"example", name=name, mimetype="application/octet-stream"
    )
    # Provider MIME metadata must not depend on the host's MIME registry.
    file._mimetype = mimetype
    return file


@pytest.mark.parametrize("mimetype", list(MEDIA_TYPES))
def test_media_types_and_private_staging(media_sdk, mimetype):
    """Every supported type uploads once, sends by ID, then cleans staging."""
    session, client, s3 = media_sdk
    file = attachment(mimetype, "report.pdf")
    obj = plugin(bucket="example-staging")
    restored = NotifyAWSWhatsApp(**NotifyAWSWhatsApp.parse_url(obj.url()))
    assert restored.bucket == "example-staging"
    assert restored.send("", attach=[file])
    s3.upload_fileobj.assert_called_once()
    upload = s3.upload_fileobj.call_args
    assert upload.args[1] == "example-staging"
    key = upload.args[2]
    assert key.startswith("apprise/")
    assert upload.kwargs == {"ExtraArgs": {"ContentType": mimetype}}
    assert upload.args[0].closed
    s3.generate_presigned_url.assert_called_once_with(
        "get_object",
        Params={"Bucket": "example-staging", "Key": key},
        ExpiresIn=300,
    )
    client.post_whatsapp_message_media.assert_called_once_with(
        originationPhoneNumberId=SENDER,
        sourceS3PresignedUrl={
            "url": "https://example.invalid/signed",
            "headers": {"Content-Type": mimetype},
        },
    )
    s3.delete_object.assert_called_once_with(Bucket="example-staging", Key=key)
    payload = json.loads(
        client.send_whatsapp_message.call_args.kwargs["message"]
    )
    kind = MEDIA_TYPES[mimetype][0]
    assert payload["type"] == kind
    assert payload["to"] == NUMBER
    assert payload[kind]["id"] == "media123"
    if kind == "document":
        assert payload[kind]["filename"] == "report.pdf"
    else:
        assert "filename" not in payload[kind]
    s3.close.assert_called_once()
    options = session.return_value.client.call_args.kwargs
    assert options["region_name"] == "us-east-1"
    assert options["verify"] is True


@pytest.mark.parametrize("mimetype", list(MEDIA_TYPES))
@pytest.mark.parametrize("oversized", [False, True])
def test_media_size_boundaries(media_sdk, mimetype, oversized):
    """Check byte limits without allocating large files."""
    file = mock.MagicMock()
    file.mimetype = mimetype
    file.name = "example"
    file.__len__.return_value = MEDIA_TYPES[mimetype][1] + int(oversized)
    outcome = plugin(bucket="example-staging").send("", attach=[file])
    assert outcome is not oversized
    if oversized:
        media_sdk[0].assert_not_called()


@pytest.mark.parametrize(
    "kind,mimetype",
    [
        ("image", "image/png"),
        ("video", "video/mp4"),
        ("document", "application/pdf"),
    ],
)
def test_media_template_headers(media_sdk, kind, mimetype):
    obj = plugin(
        bucket="example-staging",
        template="media_alert",
        template_mapping={"body": "1"},
    )
    assert obj.send("Alert", attach=[attachment(mimetype)])
    payload = json.loads(
        media_sdk[1].send_whatsapp_message.call_args.kwargs["message"]
    )
    assert payload["type"] == "template"
    assert payload["template"]["components"] == [
        {"type": "body", "parameters": [{"type": "text", "text": "Alert"}]},
        {
            "type": "header",
            "parameters": [
                {"type": kind, kind: {"id": "media123"}},
            ],
        },
    ]


@pytest.mark.parametrize(
    "files",
    [
        [attachment("audio/mpeg")],
        [attachment("image/webp")],
        [attachment(), attachment()],
    ],
)
def test_invalid_media_template(media_sdk, files):
    assert not plugin(bucket="example-staging", template="alert").send(
        "body",
        attach=files,
    )
    media_sdk[0].assert_not_called()


def test_invalid_media_and_missing_bucket(media_sdk):
    assert not plugin().send("body", attach=[attachment()])
    assert not plugin(bucket="example-staging").send("body", attach=[False])
    assert not plugin(bucket="example-staging").send(
        "body",
        attach=[attachment("application/zip")],
    )
    assert not plugin(bucket="example-staging").send(
        "body",
        attach=[AttachMemory(content=b"", mimetype="image/png")],
    )
    assert not plugin(template="alert").send("body", total=2)
    assert not plugin().send("")
    with pytest.raises(AppriseImproperlyConfigured):
        plugin(bucket="INVALID/BUCKET")
    media_sdk[0].assert_not_called()


def test_upload_once_for_multiple_recipients(media_sdk):
    obj = NotifyAWSWhatsApp(
        region_name="us-east-1",
        from_phone_id=SENDER,
        targets=[NUMBER, "+15555550124"],
        bucket="example-staging",
    )
    assert obj.send("body", attach=[attachment()])
    assert media_sdk[1].send_whatsapp_message.call_count == 4
    media_sdk[2].upload_fileobj.assert_called_once()


def test_custom_staging_prefix(media_sdk):
    obj = plugin(bucket="example-staging", prefix="/media/tests/")
    restored = NotifyAWSWhatsApp(**NotifyAWSWhatsApp.parse_url(obj.url()))
    assert restored.prefix == "media/tests/"
    assert restored.send("", attach=[attachment()])
    key = media_sdk[2].upload_fileobj.call_args.args[2]
    assert key.startswith("media/tests/")
    assert media_sdk[2].delete_object.call_args.kwargs["Key"] == key


@pytest.mark.parametrize("prefix", ["", "/", "bad\nkey", "a" * 992, None])
def test_invalid_staging_prefix(prefix):
    with pytest.raises(AppriseImproperlyConfigured):
        plugin(prefix=prefix)


@pytest.mark.parametrize(
    "failure_at", ["upload", "presign", "import", "no-id", "read"]
)
def test_media_failures_cleanup_and_close(media_sdk, failure_at):
    _, client, s3 = media_sdk
    file = attachment()
    failure = NoCredentialsError()
    if failure_at == "upload":
        s3.upload_fileobj.side_effect = failure
    elif failure_at == "presign":
        s3.generate_presigned_url.side_effect = failure
    elif failure_at == "import":
        client.post_whatsapp_message_media.side_effect = failure
    elif failure_at == "read":
        file.open = mock.Mock(side_effect=OSError())
    else:
        client.post_whatsapp_message_media.return_value = {}
    assert not plugin(bucket="example-staging").send("body", attach=[file])
    s3.delete_object.assert_called_once()
    client.send_whatsapp_message.assert_not_called()
    client.close.assert_called_once()
    s3.close.assert_called_once()


def test_cleanup_failure_does_not_resend_accepted_media(media_sdk):
    """Cleanup failure is logged but does not trigger duplicate delivery."""
    media_sdk[2].delete_object.side_effect = NoCredentialsError()
    assert plugin(bucket="example-staging").send("", attach=[attachment()])
    media_sdk[1].send_whatsapp_message.assert_called_once()


def test_s3_client_initialization_failure(media_sdk):
    session, client, _ = media_sdk
    session.return_value.client.side_effect = [client, NoCredentialsError()]
    assert not plugin(bucket="example-staging").send(
        "body", attach=[attachment()]
    )
    client.close.assert_called_once()


def test_media_partial_retry_does_not_repeat_body_or_uploaded_files(media_sdk):
    _, client, s3 = media_sdk
    app = Apprise()
    assert app.add(URL + "?bucket=example-staging&retry=1&wait=0")
    client.post_whatsapp_message_media.side_effect = [
        {"mediaId": "image1"},
        {"mediaId": "image2"},
    ]
    client.send_whatsapp_message.side_effect = [
        {"messageId": "body"},
        {"messageId": "first"},
        NoCredentialsError(),
        {"messageId": "second"},
    ]
    assert app.notify(
        body="body",
        attach=AppriseAttachment(
            [
                attachment(name="one.png"),
                attachment(name="two.png"),
            ]
        ),
    )
    payloads = [
        json.loads(call.kwargs["message"])
        for call in client.send_whatsapp_message.call_args_list
    ]
    assert [p["type"] for p in payloads] == ["text", "image", "image", "image"]
    assert [p["image"]["id"] for p in payloads[1:]] == [
        "image1",
        "image2",
        "image2",
    ]
    assert s3.upload_fileobj.call_count == 2


def test_media_only_notification_and_split_body(media_sdk):
    app = Apprise()
    assert app.add(
        URL + "?bucket=example-staging&overflow=split&retry=1&wait=0"
    )
    assert app.notify(body="x" * 2048, attach=attachment())
    payloads = [
        json.loads(call.kwargs["message"])
        for call in media_sdk[1].send_whatsapp_message.call_args_list
    ]
    assert sum(p["type"] == "image" for p in payloads) == 1
    media_sdk[2].upload_fileobj.assert_called_once()
    media_sdk[1].reset_mock()
    assert app.notify(body="", attach=attachment())
    assert (
        json.loads(
            media_sdk[1].send_whatsapp_message.call_args.kwargs["message"]
        )["type"]
        == "image"
    )


def test_real_sdk_media_contract_and_s3_transfer():
    """Use real managed S3 upload, presigning and Social API models offline."""
    session = boto3.Session(
        aws_access_key_id="AKIDEXAMPLE",
        aws_secret_access_key="secret",
        aws_session_token="temporary-token",
        region_name="us-east-1",
    )
    social = session.client("socialmessaging")
    s3 = session.client("s3")
    with (
        mock.patch(
            "apprise.plugins.awswhatsapp.boto3.Session", return_value=session
        ),
        mock.patch.object(session, "client", side_effect=[social, s3]),
        mock.patch("apprise.plugins.awswhatsapp.uuid4") as uuid,
        Stubber(s3) as s3_stub,
        Stubber(social) as social_stub,
    ):
        uuid.return_value.hex = "test-object"
        s3_stub.add_response("put_object", {"ETag": '"example"'})
        s3_stub.add_response(
            "delete_object",
            {},
            {
                "Bucket": "example-staging",
                "Key": "apprise/test-object",
            },
        )
        social_stub.add_response(
            "post_whatsapp_message_media", {"mediaId": "media123"}
        )
        social_stub.add_response(
            "send_whatsapp_message", {"messageId": "message123"}
        )
        assert plugin(bucket="example-staging").send("", attach=[attachment()])
        s3_stub.assert_no_pending_responses()
        social_stub.assert_no_pending_responses()


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
            "to": "+15555550123",
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
