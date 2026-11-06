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

"""Optional AWS WhatsApp management, event and media utilities.

These explicit operations do not run as a side effect of sending notifications.
"""

import argparse
from contextlib import closing, contextmanager, nullcontext
from copy import deepcopy
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from ..attachment.file import AttachFile


@contextmanager
def transcode_attachments(attachments, profile):
    """Convert media with FFmpeg and remove temporary files after sending."""
    profiles = {
        "image": (".jpg", "image/jpeg", ["-frames:v", "1", "-c:v", "mjpeg"]),
        "audio": (
            ".mp3",
            "audio/mpeg",
            ["-vn", "-c:a", "libmp3lame", "-b:a", "128k", "-ac", "2"],
        ),
        "video": (
            ".mp4",
            "video/mp4",
            [
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
            ],
        ),
        "sticker": (
            ".webp",
            "image/webp",
            [
                "-frames:v",
                "1",
                "-c:v",
                "libwebp",
                "-vf",
                "scale=512:512:force_original_aspect_ratio=decrease,pad=512:512:(ow-iw)/2:(oh-ih)/2:color=0x00000000",
            ],
        ),
    }
    if profile not in profiles:
        raise ValueError("Unknown FFmpeg profile.")
    executable = shutil.which("ffmpeg")
    if not executable:
        raise ValueError("FFmpeg is required for explicit media conversion.")
    suffix, mimetype, arguments = profiles[profile]
    with TemporaryDirectory(prefix="apprise-whatsapp-") as directory:
        converted = []
        for index, attachment in enumerate(attachments):
            if not attachment or not 0 < len(attachment) <= 100 * 1024**2:
                raise ValueError("Unreadable or oversized conversion input.")
            source = Path(directory) / f"input-{index}"
            output = Path(directory) / f"output-{index}{suffix}"
            with attachment.open() as stream, source.open("wb") as destination:
                shutil.copyfileobj(stream, destination)
            try:
                subprocess.run(
                    [
                        executable,
                        "-nostdin",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-y",
                        "-protocol_whitelist",
                        "file,pipe",
                        "-format_whitelist",
                        "wav,mp3,aac,amr,ogg,mov,matroska,avi,flac,asf,aiff,au,"
                        "jpeg_pipe,png_pipe,gif,webp_pipe,bmp_pipe,tiff_pipe,"
                        "image2,image2pipe,mpeg,mpegts",
                        "-i",
                        str(source),
                        *arguments,
                        str(output),
                    ],
                    check=True,
                    timeout=120,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )
            except (subprocess.SubprocessError, OSError) as error:
                raise ValueError("FFmpeg conversion failed.") from error
            if not output.is_file() or output.stat().st_size == 0:
                raise ValueError("FFmpeg produced no media.")
            converted.append(
                AttachFile(
                    path=str(output),
                    mimetype=mimetype,
                    name=Path(attachment.name or "attachment").stem + suffix,
                )
            )
        yield converted


def decode_events(payload, depth=0):
    """Normalize trusted SNS/SQS/Lambda/EventBridge and WhatsApp events.

    This is a decoder, not an HTTP endpoint or SNS signature verifier.
    """
    if depth > 8:
        raise ValueError("Event envelope nesting exceeds eight levels.")
    if isinstance(payload, (str, bytes)):
        if len(payload) > 4 * 1024**2:
            raise ValueError("Event exceeds 4 MiB.")
        payload = json.loads(payload)
    if not isinstance(payload, dict):
        raise ValueError("Event must be an object.")
    if "Records" in payload:
        result = []
        for record in payload["Records"]:
            result.extend(
                decode_events(
                    record.get("Sns", {}).get(
                        "Message", record.get("body", record)
                    ),
                    depth + 1,
                )
            )
        return result
    if "Message" in payload:
        if payload.get("Type", "Notification") != "Notification":
            raise ValueError("Only SNS notifications are event data.")
        return decode_events(payload["Message"], depth + 1)
    if payload.get("source") == "aws.social-messaging":
        detail = payload.get("detail", {})
        return [
            {
                "kind": "status" if "status" in detail else "event",
                "message_id": detail.get("messageId"),
                "aws_message_id": detail.get("messageId"),
                "status": detail.get("status"),
                "event_type": payload.get("detail-type"),
                "timestamp": detail.get("eventTimestamp", payload.get("time")),
                "data": deepcopy(detail),
            }
        ]
    if "whatsAppWebhookEntry" in payload:
        records = decode_events(payload["whatsAppWebhookEntry"], depth + 1)
        for record in records:
            record["aws_message_id"] = payload.get("messageId")
        return records
    if "entry" in payload:
        return [
            record
            for entry in payload["entry"]
            for record in decode_events(entry, depth + 1)
        ]
    values = [change.get("value", {}) for change in payload.get("changes", [])]
    if not values and ("messages" in payload or "statuses" in payload):
        values = [payload]
    records = []
    for value in values:
        for message in value.get("messages", []):
            records.append(
                {
                    "kind": "message",
                    "message_id": message.get("id"),
                    "sender": message.get("from"),
                    "type": message.get("type"),
                    "timestamp": message.get("timestamp"),
                    "data": deepcopy(message),
                }
            )
        for status in value.get("statuses", []):
            records.append(
                {
                    "kind": "status",
                    "message_id": status.get("id"),
                    "status": status.get("status"),
                    "recipient": status.get("recipient_id"),
                    "timestamp": status.get("timestamp"),
                    "data": deepcopy(status),
                }
            )
    if not records:
        raise ValueError("No inbound message or status found in this event.")
    return records


def receive_events(client, queue_url, handler, delete=False):
    """Process one SQS batch; acknowledge only after the handler succeeds."""
    response = client.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=10,
        WaitTimeSeconds=20,
    )
    count = 0
    for message in response.get("Messages", []):
        records = decode_events(message["Body"])
        for record in records:
            handler(record)
            count += 1
        if delete:
            client.delete_message(
                QueueUrl=queue_url, ReceiptHandle=message["ReceiptHandle"]
            )
    return count


def template_schema(template):
    """Show template text, header format and required substitution names."""
    if isinstance(template, str):
        template = json.loads(template)
    result = {
        "name": template.get("name"),
        "language": template.get("language"),
        "status": template.get("status"),
        "parameters": {},
        "header_format": None,
    }
    for component in template.get("components", []):
        kind = component.get("type", "").lower()
        if kind == "header":
            result["header_format"] = component.get("format")
        if kind in ("body", "header"):
            result["parameters"][kind] = list(
                dict.fromkeys(
                    re.findall(
                        r"\{\{\s*([a-z_0-9]+)\s*\}\}",
                        component.get("text", ""),
                    )
                )
            )
        elif kind == "buttons":
            result["buttons"] = deepcopy(component.get("buttons", []))
    result["template"] = deepcopy(template)
    return result


def _emit(value):
    """Emit one JSON record, including a flush before queue acknowledgement."""
    sys.stdout.write(json.dumps(value, ensure_ascii=False, default=str) + "\n")
    sys.stdout.flush()


def main(argv=None):
    """Explicit utility commands; sending never runs administration tasks."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("senders")
    listing = commands.add_parser("templates")
    listing.add_argument("--waba", required=True)
    describe = commands.add_parser("describe-template")
    describe.add_argument("--waba", required=True)
    describe.add_argument("--name", required=True)
    describe.add_argument("--language", required=True)
    create = commands.add_parser("create-template")
    create.add_argument("--waba", required=True)
    create.add_argument("--definition", type=Path, required=True)
    configure = commands.add_parser("configure-events")
    configure.add_argument("--waba", required=True)
    configure.add_argument("--topic-arn", required=True)
    decode = commands.add_parser("decode-events")
    decode.add_argument("--file", default="-")
    receive = commands.add_parser("receive-events")
    receive.add_argument("--queue-url", required=True)
    receive.add_argument("--ack", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "decode-events":
        with (
            nullcontext(sys.stdin)
            if args.file == "-"
            else Path(args.file).open(encoding="utf-8")
        ) as stream:
            for event in decode_events(stream.read(4 * 1024**2 + 1)):
                _emit(event)
        return 0
    try:
        import boto3
        from botocore.config import Config
    except ImportError:
        parser.error("Install boto3 to use AWS management commands.")
    session = boto3.Session(region_name=args.region)
    service = "sqs" if args.command == "receive-events" else "socialmessaging"
    with closing(
        session.client(
            service,
            config=Config(
                connect_timeout=10,
                read_timeout=30,
                retries={"total_max_attempts": 1, "mode": "standard"},
            ),
        )
    ) as client:
        operation = {
            "templates": "list_whatsapp_message_templates",
            "describe-template": "get_whatsapp_message_template",
            "create-template": "create_whatsapp_message_template",
        }.get(args.command)
        if operation and not hasattr(client, operation):
            parser.error("Upgrade boto3 for WhatsApp template administration.")
        if args.command == "receive-events":
            receive_events(client, args.queue_url, _emit, delete=args.ack)
        elif args.command == "senders":
            for page in client.get_paginator(
                "list_linked_whatsapp_business_accounts"
            ).paginate():
                for account in page.get("linkedAccounts", []):
                    _emit(
                        client.get_linked_whatsapp_business_account(
                            id=account["id"]
                        )["account"]
                    )
        elif args.command == "templates":
            for page in client.get_paginator(
                "list_whatsapp_message_templates"
            ).paginate(id=args.waba):
                for template in page.get("templates", []):
                    _emit(template)
        elif args.command == "describe-template":
            response = client.get_whatsapp_message_template(
                id=args.waba,
                templateName=args.name,
                templateLanguageCode=args.language,
            )
            _emit(template_schema(response["template"]))
        elif args.command == "create-template":
            definition = json.loads(
                args.definition.read_text(encoding="utf-8")
            )
            if not isinstance(definition, dict):
                raise ValueError("A template definition must be an object.")
            _emit(
                client.create_whatsapp_message_template(
                    id=args.waba,
                    templateDefinition=json.dumps(definition).encode("utf-8"),
                )
            )
        elif args.command == "configure-events":
            _emit(
                client.put_whatsapp_business_account_event_destinations(
                    id=args.waba,
                    eventDestinations=[
                        {"eventDestinationArn": args.topic_arn}
                    ],
                )
            )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        # Only the explicitly invoked CLI catches exceptions at this boundary.
        sys.stderr.write(
            f"AWS WhatsApp utility failed: {type(error).__name__}\n"
        )
        sys.exit(1)
