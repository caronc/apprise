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

"""Structured templates, explicit administration and event-processing tests."""

from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import shutil
import subprocess
from unittest import mock
import wave

import pytest

from apprise.attachment.memory import AttachMemory
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.awswhatsapp import NotifyAWSWhatsApp
from apprise.utils.awswhatsapp import (
    decode_events,
    main,
    receive_events,
    template_schema,
    transcode_attachments,
)

SENDER = "phone-number-id-01234567890123456789012345678901"


def plugin(**kwargs):
    return NotifyAWSWhatsApp(
        region_name="us-east-1",
        from_phone_id=SENDER,
        targets="15555550123",
        **kwargs,
    )


@pytest.fixture
def sdk():
    pytest.importorskip("boto3")
    with mock.patch("apprise.plugins.awswhatsapp.boto3.Session") as session:
        client = session.return_value.client.return_value
        client.send_whatsapp_message.return_value = {"messageId": "test-id"}
        yield session, client


def text_header(text="$body"):
    return {"type": "header", "parameters": [{"type": "text", "text": text}]}


@pytest.mark.parametrize(
    "subtype,parameter",
    [
        ("url", {"type": "text", "text": "$body"}),
        ("quick_reply", {"type": "payload", "payload": "accept"}),
        ("copy_code", {"type": "coupon_code", "coupon_code": "SAVE"}),
        (
            "flow",
            {"type": "action", "action": {"flow_token": "secret-flow-token"}},
        ),
    ],
)
def test_structured_headers_buttons_and_body(sdk, subtype, parameter):
    components = [
        text_header("Reference"),
        {
            "type": "button",
            "sub_type": subtype,
            "index": 0,
            "parameters": [parameter],
        },
    ]
    original = deepcopy(components)
    obj = plugin(
        template="alert",
        template_mapping={"body": "message"},
        template_components=components,
    )
    components[0]["parameters"][0]["text"] = "Changed after construction"
    restored = NotifyAWSWhatsApp(**NotifyAWSWhatsApp.parse_url(obj.url()))
    assert restored.send('Body with "quotes" and \\slashes')
    payload = json.loads(
        sdk[1].send_whatsapp_message.call_args.kwargs["message"]
    )
    result = payload["template"]["components"]
    assert result[0] == original[0]
    assert result[1]["index"] == "0"
    assert (
        result[2]["parameters"][0]["text"]
        == 'Body with "quotes" and \\slashes'
    )
    assert "secret-flow-token" not in obj.url(privacy=True)
    assert "Reference" not in obj.url(privacy=True)


def test_location_header(sdk):
    location = {
        "latitude": "-5.09",
        "longitude": -42.8,
        "name": "Office",
        "address": "Example street",
    }
    obj = plugin(
        template="location",
        template_components=[
            {
                "type": "header",
                "parameters": [{"type": "location", "location": location}],
            }
        ],
    )
    assert obj.send("body")
    payload = json.loads(
        sdk[1].send_whatsapp_message.call_args.kwargs["message"]
    )
    assert (
        payload["template"]["components"][0]["parameters"][0]["location"]
        == location
    )


@pytest.mark.parametrize(
    "reference", [{"id": "123"}, {"link": "https://example.com/image.png"}]
)
def test_explicit_media_header_without_s3(sdk, reference):
    assert plugin(
        template="image",
        template_components=[
            {
                "type": "header",
                "parameters": [{"type": "image", "image": reference}],
            }
        ],
    ).send("body")
    sdk[0].return_value.client.assert_called_once()


def test_dynamic_component_escape_and_body_collision(sdk):
    obj = plugin(
        template="alert",
        template_components=[
            text_header("$$body"),
            {
                "type": "body",
                "parameters": [{"type": "text", "text": "$type"}],
            },
        ],
    )
    assert obj.send("body")
    payload = json.loads(
        sdk[1].send_whatsapp_message.call_args.kwargs["message"]
    )
    assert (
        payload["template"]["components"][0]["parameters"][0]["text"]
        == "$body"
    )
    assert (
        payload["template"]["components"][1]["parameters"][0]["text"] == "info"
    )
    with pytest.raises(AppriseImproperlyConfigured):
        plugin(
            template="alert",
            template_mapping={"body": "1"},
            template_components=[
                {"type": "body", "parameters": [{"type": "text", "text": "x"}]}
            ],
        )


def test_attachment_header_conflict(sdk):
    obj = plugin(
        template="alert",
        bucket="example-staging",
        template_components=[text_header()],
    )
    file = AttachMemory(content=b"test", name="a.txt", mimetype="text/plain")
    assert not obj.send("body", attach=[file])
    sdk[0].assert_not_called()


@pytest.mark.parametrize(
    "components",
    [
        "invalid-json",
        {},
        [False],
        [{"type": "footer"}],
        [{"type": "header", "parameters": []}],
        [text_header(), text_header()],
        [{"type": "header", "parameters": [False]}],
        [{"type": "header", "parameters": [{"type": "text", "text": ""}]}],
        [
            {
                "type": "header",
                "parameters": [{"type": "payload", "payload": "x"}],
            }
        ],
        [
            {
                "type": "body",
                "parameters": [{"type": "payload", "payload": "x"}],
            }
        ],
        [{"type": "header", "parameters": [{"type": "image", "image": {}}]}],
        [
            {
                "type": "header",
                "parameters": [
                    {"type": "image", "image": {"link": "http://example.com"}}
                ],
            }
        ],
        [
            {
                "type": "header",
                "parameters": [
                    {
                        "type": "location",
                        "location": {"latitude": 91, "longitude": 0},
                    }
                ],
            }
        ],
        [
            {
                "type": "button",
                "sub_type": "url",
                "index": 10,
                "parameters": [{"type": "text", "text": "x"}],
            }
        ],
        [
            {
                "type": "button",
                "sub_type": "unknown",
                "index": 0,
                "parameters": [{"type": "text", "text": "x"}],
            }
        ],
        [
            {
                "type": "button",
                "sub_type": "url",
                "index": 0,
                "parameters": [{"type": "payload", "payload": "x"}],
            }
        ],
        [text_header("x" * 65537)],
    ],
)
def test_invalid_components_rejected_without_aws(components, sdk):
    with pytest.raises(AppriseImproperlyConfigured):
        plugin(template="alert", template_components=components)
    sdk[0].assert_not_called()


def test_components_require_template():
    with pytest.raises(AppriseImproperlyConfigured):
        plugin(template_components=[text_header()])


def test_group_payload_and_roundtrip(sdk):
    obj = NotifyAWSWhatsApp(
        region_name="us-east-1",
        from_phone_id=SENDER,
        targets=["#123456789012345678", "123456789012345678@g.us"],
    )
    assert obj.targets == ["#123456789012345678"]
    restored = NotifyAWSWhatsApp(**NotifyAWSWhatsApp.parse_url(obj.url()))
    assert restored.send("group test")
    payload = json.loads(
        sdk[1].send_whatsapp_message.call_args.kwargs["message"]
    )
    assert payload["to"] == "123456789012345678@g.us"
    assert payload["recipient_type"] == "group"


def message_event():
    return {
        "changes": [
            {
                "value": {
                    "messages": [
                        {
                            "id": "wamid.in",
                            "from": "15555550123",
                            "type": "text",
                            "text": {"body": "hello"},
                        }
                    ],
                    "statuses": [
                        {
                            "id": "wamid.out",
                            "status": "delivered",
                            "recipient_id": "15555550123",
                        }
                    ],
                }
            }
        ]
    }


@pytest.mark.parametrize(
    "wrapper", ["raw", "aws", "sns", "sqs", "lambda", "meta"]
)
def test_inbound_and_delivery_events(wrapper):
    payload = message_event()
    if wrapper != "raw":
        payload = {
            "messageId": "aws-request",
            "whatsAppWebhookEntry": json.dumps(payload),
        }
    if wrapper in ("sns", "sqs", "lambda"):
        payload = {"Type": "Notification", "Message": json.dumps(payload)}
    if wrapper == "sqs":
        payload = {"Records": [{"body": json.dumps(payload)}]}
    elif wrapper == "lambda":
        payload = {"Records": [{"Sns": {"Message": json.dumps(payload)}}]}
    elif wrapper == "meta":
        payload = {"entry": [payload]}
    records = decode_events(json.dumps(payload))
    assert [record["kind"] for record in records] == ["message", "status"]
    assert records[0]["data"]["text"]["body"] == "hello"
    assert records[1]["status"] == "delivered"
    if wrapper != "raw":
        assert records[1]["aws_message_id"] == "aws-request"


def test_eventbridge_delivery():
    result = decode_events(
        {
            "source": "aws.social-messaging",
            "detail-type": "WhatsApp Message Delivered",
            "detail": {"messageId": "aws-id", "status": "delivered"},
        }
    )
    assert result[0]["message_id"] == "aws-id"
    assert result[0]["status"] == "delivered"


@pytest.mark.parametrize(
    "event",
    [
        [],
        {},
        "bad-json",
        {"Type": "SubscriptionConfirmation", "Message": "{}"},
        "x" * (4 * 1024**2 + 1),
    ],
)
def test_invalid_events(event):
    with pytest.raises((ValueError, TypeError)):
        decode_events(event)


def test_queue_ack_after_handler_only():
    client = mock.Mock()
    client.receive_message.return_value = {
        "Messages": [
            {"Body": json.dumps(message_event()), "ReceiptHandle": "receipt"}
        ]
    }
    handler = mock.Mock()
    assert receive_events(client, "queue", handler) == 2
    client.delete_message.assert_not_called()
    assert receive_events(client, "queue", handler, delete=True) == 2
    client.delete_message.assert_called_once_with(
        QueueUrl="queue", ReceiptHandle="receipt"
    )
    client.reset_mock()
    handler.side_effect = RuntimeError("storage unavailable")
    with pytest.raises(RuntimeError):
        receive_events(client, "queue", handler, delete=True)
    client.delete_message.assert_not_called()


def test_template_discovery_schema():
    result = template_schema(
        json.dumps(
            {
                "name": "reminder",
                "language": "pt_BR",
                "status": "APPROVED",
                "components": [
                    {
                        "type": "BODY",
                        "text": "Hello {{nome}} {{nome}} {{recurso}}",
                    },
                    {"type": "HEADER", "format": "LOCATION"},
                    {
                        "type": "BUTTONS",
                        "buttons": [
                            {"type": "URL", "url": "https://example.com/{{1}}"}
                        ],
                    },
                ],
            }
        )
    )
    assert result["parameters"]["body"] == ["nome", "recurso"]
    assert result["header_format"] == "LOCATION"
    assert result["buttons"][0]["type"] == "URL"


def test_decode_cli(tmp_path, capsys):
    file = tmp_path / "events.json"
    file.write_text(json.dumps(message_event()))
    assert main(["decode-events", "--file", str(file)]) == 0
    assert len(capsys.readouterr().out.splitlines()) == 2


@pytest.mark.parametrize(
    "command,method",
    [
        (
            [
                "describe-template",
                "--waba",
                "waba",
                "--name",
                "hello",
                "--language",
                "en_US",
            ],
            "get_whatsapp_message_template",
        ),
        (
            [
                "configure-events",
                "--waba",
                "waba",
                "--topic-arn",
                "arn:example",
            ],
            "put_whatsapp_business_account_event_destinations",
        ),
    ],
)
def test_explicit_management_commands(command, method, capsys):
    boto3 = pytest.importorskip("boto3")
    with mock.patch.object(boto3, "Session") as session:
        client = session.return_value.client.return_value
        getattr(client, method).return_value = (
            {"template": json.dumps({"name": "hello"})}
            if method.startswith("get_")
            else {}
        )
        assert main(["--region", "us-east-1", *command]) == 0
        getattr(client, method).assert_called_once()
        client.send_whatsapp_message.assert_not_called()
        client.close.assert_called_once()


def test_create_template_explicit_only(tmp_path, capsys):
    boto3 = pytest.importorskip("boto3")
    definition = {"name": "hello", "language": "en_US", "components": []}
    file = tmp_path / "template.json"
    file.write_text(json.dumps(definition))
    with mock.patch.object(boto3, "Session") as session:
        client = session.return_value.client.return_value
        client.create_whatsapp_message_template.return_value = {}
        assert (
            main(
                [
                    "create-template",
                    "--waba",
                    "waba",
                    "--definition",
                    str(file),
                ]
            )
            == 0
        )
        request = client.create_whatsapp_message_template.call_args.kwargs
        assert json.loads(request["templateDefinition"]) == definition
        assert request["id"] == "waba"


def test_ffmpeg_failures_and_cleanup():
    file = AttachMemory(content=b"audio", name="a.wav", mimetype="audio/wav")
    with pytest.raises(ValueError), transcode_attachments([file], "unknown"):
        pass
    with (
        mock.patch("shutil.which", return_value=None),
        pytest.raises(ValueError),
        transcode_attachments([file], "audio"),
    ):
        pass
    with (
        mock.patch("shutil.which", return_value="ffmpeg"),
        mock.patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired("ffmpeg", 120),
        ),
        pytest.raises(ValueError),
        transcode_attachments([file], "audio"),
    ):
        pass


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg not installed")
def test_real_audio_transcoding_offline():
    data = BytesIO()
    with wave.open(data, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(8000)
        output.writeframes(b"\x00\x00" * 800)
    file = AttachMemory(
        content=data.getvalue(), name="test.wav", mimetype="audio/wav"
    )
    with transcode_attachments([file], "audio") as converted:
        result = converted[0]
        assert result.mimetype == "audio/mpeg"
        assert result.name == "test.mp3"
        path = Path(result.path)
        assert path.is_file()
    assert not path.exists()


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg not installed")
@pytest.mark.parametrize(
    "profile,mimetype", [("image", "image/jpeg"), ("sticker", "image/webp")]
)
def test_real_image_conversion(profile, mimetype):
    file = AttachMemory(
        content=(
            Path(__file__).parent / "var" / "apprise-test.png"
        ).read_bytes(),
        name="test.png",
        mimetype="image/png",
    )
    with transcode_attachments([file], profile) as converted:
        assert converted[0].mimetype == mimetype
        assert len(converted[0]) > 0


def test_plugin_conversion_failure_and_invalid_profile(sdk):
    with pytest.raises(AppriseImproperlyConfigured):
        plugin(transcode="invalid")
    obj = plugin(transcode="audio", bucket="example-staging")
    restored = NotifyAWSWhatsApp(**NotifyAWSWhatsApp.parse_url(obj.url()))
    assert restored.transcode == "audio"
    file = AttachMemory(content=b"bad", name="bad.wav", mimetype="audio/wav")
    with mock.patch("shutil.which", return_value=None):
        assert not restored.send("body", attach=[file])
    sdk[0].assert_not_called()


@pytest.mark.parametrize("command", ["senders", "templates"])
def test_management_paginated_read_commands(command, capsys):
    boto3 = pytest.importorskip("boto3")
    with mock.patch.object(boto3, "Session") as session:
        client = session.return_value.client.return_value
        page = (
            {"linkedAccounts": [{"id": "waba"}]}
            if command == "senders"
            else {"templates": [{"templateName": "hello"}]}
        )
        client.get_paginator.return_value.paginate.return_value = [page]
        client.get_linked_whatsapp_business_account.return_value = {
            "account": {"id": "waba"}
        }
        assert (
            main(
                [
                    command,
                    *(["--waba", "waba"] if command == "templates" else []),
                ]
            )
            == 0
        )
        assert capsys.readouterr().out


def test_receive_events_cli_does_not_ack_implicitly(capsys):
    boto3 = pytest.importorskip("boto3")
    with mock.patch.object(boto3, "Session") as session:
        client = session.return_value.client.return_value
        client.receive_message.return_value = {
            "Messages": [
                {
                    "Body": json.dumps(message_event()),
                    "ReceiptHandle": "receipt",
                }
            ]
        }
        assert main(["receive-events", "--queue-url", "queue"]) == 0
        client.delete_message.assert_not_called()
        assert main(["receive-events", "--queue-url", "queue", "--ack"]) == 0
        client.delete_message.assert_called_once()


def test_component_body_header_validation_edges(sdk):
    bad = [
        {"type": "header", "parameters": [{"type": "text", "text": "x"}] * 2},
        {
            "type": "header",
            "parameters": [{"type": "image", "image": {"id": ""}}],
        },
        {
            "type": "header",
            "parameters": [
                {
                    "type": "location",
                    "location": {"latitude": 1, "longitude": 2},
                }
            ],
        },
        {
            "type": "button",
            "index": 0,
            "sub_type": "flow",
            "parameters": [{"type": "action", "action": "bad"}],
        },
        {"type": "header", "parameters": [{"type": "unknown"}]},
    ]
    for component in bad:
        with pytest.raises(AppriseImproperlyConfigured):
            plugin(template="alert", template_components=[component])
    sdk[0].assert_not_called()


def test_event_nesting_guard():
    payload = message_event()
    for _ in range(10):
        payload = {"entry": [payload]}
    with pytest.raises(ValueError):
        decode_events(payload)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg not installed")
def test_real_video_conversion(tmp_path):
    executable = shutil.which("ffmpeg")
    source = tmp_path / "sample.mkv"
    subprocess.run(
        [
            executable,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=32x32:r=1",
            "-t",
            "1",
            "-c:v",
            "ffv1",
            str(source),
        ],
        check=True,
        timeout=30,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    file = AttachMemory(
        content=source.read_bytes(),
        name="sample.mkv",
        mimetype="application/octet-stream",
    )
    with transcode_attachments([file], "video") as converted:
        assert converted[0].mimetype == "video/mp4"
        with converted[0].open() as stream:
            assert stream.read(8)[4:] == b"ftyp"


def test_template_creation_real_sdk_contract(tmp_path, capsys):
    boto3 = pytest.importorskip("boto3")
    from botocore.stub import Stubber

    session = boto3.Session(
        aws_access_key_id="AKIDEXAMPLE",
        aws_secret_access_key="secret",
        region_name="us-east-1",
    )
    client = session.client("socialmessaging")
    if not hasattr(client, "create_whatsapp_message_template"):
        pytest.skip("Template administration requires a newer AWS SDK")
    definition = {
        "name": "hello",
        "language": "en_US",
        "category": "UTILITY",
        "components": [{"type": "BODY", "text": "Hello"}],
    }
    file = tmp_path / "template.json"
    file.write_text(json.dumps(definition))
    with (
        mock.patch.object(boto3, "Session", return_value=session),
        mock.patch.object(session, "client", return_value=client),
        Stubber(client) as stub,
    ):
        stub.add_response(
            "create_whatsapp_message_template",
            {},
            {
                "id": "waba-example",
                "templateDefinition": json.dumps(definition).encode("utf-8"),
            },
        )
        assert (
            main(
                [
                    "create-template",
                    "--waba",
                    "waba-example",
                    "--definition",
                    str(file),
                ]
            )
            == 0
        )
        stub.assert_no_pending_responses()


def configure_media_transport(sdk):
    session, client = sdk
    s3 = mock.Mock()
    session.return_value.client.side_effect = lambda service, **kwargs: (
        s3 if service == "s3" else client
    )
    client.post_whatsapp_message_media.return_value = {"mediaId": "media123"}
    s3.generate_presigned_url.return_value = "https://example.invalid/signed"
    return client, s3


def test_template_button_composes_with_uploaded_header(sdk):
    client, _ = configure_media_transport(sdk)
    button = {
        "type": "button",
        "sub_type": "quick_reply",
        "index": "0",
        "parameters": [{"type": "payload", "payload": "accept"}],
    }
    obj = plugin(
        template="alert",
        bucket="example-staging",
        template_components=[button],
        template_mapping={"body": "1"},
    )
    file = AttachMemory(
        content=b"file", name="example.txt", mimetype="text/plain"
    )
    assert obj.send("Notice", attach=[file])
    payload = json.loads(
        client.send_whatsapp_message.call_args.kwargs["message"]
    )
    assert [part["type"] for part in payload["template"]["components"]] == [
        "button",
        "body",
        "header",
    ]


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg not installed")
def test_plugin_uploads_converted_audio_and_removes_temporary_file(sdk):
    client, s3 = configure_media_transport(sdk)
    data = BytesIO()
    with wave.open(data, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(8000)
        output.writeframes(b"\x00\x00" * 800)
    file = AttachMemory(
        content=data.getvalue(), name="test.wav", mimetype="audio/wav"
    )
    assert plugin(bucket="example-staging", transcode="audio").send(
        "", attach=[file]
    )
    upload = s3.upload_fileobj.call_args
    assert upload.kwargs["ExtraArgs"]["ContentType"] == "audio/mpeg"
    assert not Path(upload.args[0].name).exists()
    payload = json.loads(
        client.send_whatsapp_message.call_args.kwargs["message"]
    )
    assert payload["type"] == "audio"
    assert payload["audio"]["id"] == "media123"
