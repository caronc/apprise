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

"""Outbound WhatsApp notifications through AWS End User Messaging Social."""

from copy import deepcopy
from json import dumps, loads
import math
import re
from uuid import uuid4

from ..common import NotifyType
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.awswhatsapp import transcode_attachments
from ..utils.parse import is_phone_no, parse_phone_no
from .base import NotifyBase

try:
    import boto3
    from boto3.exceptions import Boto3Error
    from botocore.config import Config
    from botocore.exceptions import BotoCoreError, ClientError

    AWS_WHATSAPP_SUPPORT_ENABLED = True
except ImportError:
    AWS_WHATSAPP_SUPPORT_ENABLED = False


# AWS/WhatsApp limits, in bytes. MIME validation happens before any uploads.
MEDIA_TYPES = {
    "image/jpeg": ("image", 5 * 1024**2),
    "image/png": ("image", 5 * 1024**2),
    "image/webp": ("sticker", 100 * 1024),
    **dict.fromkeys(
        ("audio/aac", "audio/amr", "audio/mpeg", "audio/mp4", "audio/ogg"),
        ("audio", 16 * 1024**2),
    ),
    **dict.fromkeys(
        ("video/mp4", "video/3gp", "video/3gpp"),
        ("video", 16 * 1024**2),
    ),
    **dict.fromkeys(
        (
            "text/plain",
            "application/pdf",
            "application/msword",
            "application/vnd.ms-excel",
            "application/vnd.ms-powerpoint",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ),
        ("document", 100 * 1024**2),
    ),
}


class NotifyAWSWhatsApp(NotifyBase):
    """Send text or approved templates using SendWhatsAppMessage."""

    enabled = AWS_WHATSAPP_SUPPORT_ENABLED
    requirements = {"packages_required": "boto3 >= 1.35.50"}
    service_name = "AWS End User Messaging Social (WhatsApp)"
    service_url = "https://aws.amazon.com/end-user-messaging/"
    secure_protocol = "awswhatsapp"
    setup_url = "https://appriseit.com/services/aws-whatsapp/"
    title_maxlen = 0
    body_maxlen = 1024
    attachment_support = True
    request_rate_per_sec = 0.2

    templates = (
        "{schema}://{region}/{from_phone_id}/{targets}",
        "{schema}://{access_key_id}:{secret_access_key}@"
        "{region}/{from_phone_id}/{targets}",
    )
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "region": {
                "name": _("Region"),
                "type": "string",
                "required": True,
                "map_to": "region_name",
            },
            "access_key_id": {
                "name": _("Access Key ID"),
                "type": "string",
                "private": True,
            },
            "secret_access_key": {
                "name": _("Secret Access Key"),
                "type": "string",
                "private": True,
            },
            "from_phone_id": {
                "name": _("From Phone ID"),
                "type": "string",
                "required": True,
            },
            "targets": {
                "name": _("Targets"),
                "type": "list:string",
                "required": True,
            },
            "target_phone": {
                "name": _("Target Phone No"),
                "type": "string",
                "prefix": "+",
                "map_to": "targets",
            },
        },
    )
    template_args = dict(
        NotifyBase.template_args,
        **{
            "to": {"alias_of": "targets"},
            "token": {
                "name": _("Session Token"),
                "type": "string",
                "private": True,
                "map_to": "session_token",
            },
            "template": {"name": _("Template Name"), "type": "string"},
            "components": {
                "name": _("Template Mapping"),
                "type": "string",
                "map_to": "template_components",
            },
            "transcode": {
                "name": _("Media Type"),
                "type": "choice:string",
                "values": ("none", "image", "audio", "video", "sticker"),
                "default": "none",
            },
            "bucket": {
                "name": _("S3 Bucket"),
                "type": "string",
            },
            "prefix": {
                "name": _("Path Prefix"),
                "type": "string",
                "default": "apprise/",
            },
            "lang": {
                "name": _("Language"),
                "type": "string",
                "default": "en_US",
                "map_to": "language",
            },
            "version": {
                "name": _("API Version"),
                "type": "string",
                "default": "v23.0",
                "map_to": "meta_api_version",
            },
        },
    )
    template_kwargs = {
        "template_mapping": {
            "name": _("Template Mapping"),
            "prefix": ":",
        },
    }

    def __init__(
        self,
        region_name,
        from_phone_id,
        targets=None,
        access_key_id=None,
        secret_access_key=None,
        session_token=None,
        template=None,
        language="en_US",
        meta_api_version="v23.0",
        template_mapping=None,
        template_components=None,
        bucket=None,
        prefix="apprise/",
        transcode="none",
        **kwargs,
    ):
        """Validate settings without credential discovery or network access."""
        super().__init__(**kwargs)
        for value, pattern, label in (
            (region_name, r"[a-z]{2}(?:-[a-z]+)+-\d+", "region"),
            (from_phone_id, r"phone-number-id-[a-zA-Z0-9]+", "sender ID"),
            (language, r"[a-z]{2,3}(?:_[A-Z]{2})?", "language"),
            (meta_api_version, r"v\d+\.\d+", "API version"),
        ):
            if not isinstance(value, str) or not re.fullmatch(pattern, value):
                raise AppriseImproperlyConfigured(
                    f"An invalid AWS WhatsApp {label} was specified."
                )
        if bool(access_key_id) != bool(secret_access_key) or (
            session_token and not access_key_id
        ):
            raise AppriseImproperlyConfigured(
                "AWS explicit credentials require both access and secret keys."
            )
        if template is not None and (
            not isinstance(template, str)
            or not re.fullmatch(r"[a-z0-9_]+", template)
        ):
            raise AppriseImproperlyConfigured(
                "Invalid WhatsApp template name."
            )

        self.region_name = region_name
        self.from_phone_id = from_phone_id
        self.access_key_id = access_key_id or None
        self.secret_access_key = secret_access_key or None
        self.session_token = session_token or None
        self.template = template
        if bucket is not None and (
            not isinstance(bucket, str)
            or not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket)
        ):
            raise AppriseImproperlyConfigured("Invalid S3 staging bucket.")
        self.bucket = bucket
        if (
            not isinstance(prefix, str)
            or not prefix.strip("/")
            or re.search(r"[\x00-\x1f\x7f]", prefix)
            or len(prefix.strip("/").encode("utf-8")) > 991
        ):
            raise AppriseImproperlyConfigured("Invalid S3 staging prefix.")
        self.prefix = prefix.strip("/") + "/"
        self.language = language
        self.meta_api_version = meta_api_version
        self.template_mapping = dict(template_mapping or {})
        self.components = {}
        for key, value in self.template_mapping.items():
            if key in ("body", "type"):
                if not re.fullmatch(r"[1-9][0-9]*|[a-z_]+", str(value)):
                    raise AppriseImproperlyConfigured(
                        "Invalid template parameter."
                    )
                index = int(value) if str(value).isdigit() else str(value)
                content = key
            elif re.fullmatch(r"[1-9][0-9]*", str(key)):
                index, content = int(key), str(value)
            elif re.fullmatch(r"[a-z_]+", str(key)):
                index, content = str(key), str(value)
            else:
                raise AppriseImproperlyConfigured("Invalid template mapping.")
            if index in self.components:
                raise AppriseImproperlyConfigured("Duplicate template index.")
            self.components[index] = (key in ("body", "type"), content)
        indices = list(self.components)
        positional = all(isinstance(index, int) for index in indices)
        named = all(isinstance(index, str) for index in indices)
        if indices and (
            not template
            or not (positional or named)
            or (
                positional
                and sorted(indices) != list(range(1, len(indices) + 1))
            )
        ):
            raise AppriseImproperlyConfigured(
                "Use consecutive positions or named parameters in a template."
            )

        self.template_components = self._validate_components(
            template_components, template, bool(self.components)
        )
        if transcode not in ("none", "image", "audio", "video", "sticker"):
            raise AppriseImproperlyConfigured("Invalid transcoding profile.")
        self.transcode = transcode

        self.targets = []
        for target in parse_phone_no(targets):
            if target.startswith("#") or target.endswith("@g.us"):
                raise AppriseImproperlyConfigured(
                    "WhatsApp group recipients are not supported."
                )
            number = is_phone_no(target)
            if not number:
                raise AppriseImproperlyConfigured(
                    "An invalid WhatsApp recipient was specified."
                )
            number = "+{}".format(number["full"])
            if number not in self.targets:
                self.targets.append(number)

    def send(
        self,
        body,
        title="",
        notify_type=NotifyType.INFO,
        attach=None,
        **kwargs,
    ):
        """Optionally convert media before validating and sending it."""
        if not self.enabled or not self.targets:
            return False
        if self.transcode == "none" or not attach:
            return self._send(body, title, notify_type, attach, **kwargs)
        try:
            with transcode_attachments(attach, self.transcode) as converted:
                return self._send(
                    body, title, notify_type, converted, **kwargs
                )
        except (OSError, ValueError) as error:
            self.logger.warning(
                "AWS WhatsApp media conversion failed: %s",
                type(error).__name__,
            )
            return False

    def _send(
        self,
        body,
        title="",
        notify_type=NotifyType.INFO,
        attach=None,
        **kwargs,
    ):
        """Send each recipient separately and preserve partial successes."""
        if not self.targets or not self.enabled:
            return False
        if self.template and kwargs.get("total", 1) > 1:
            self.logger.warning(
                "WhatsApp templates require one message piece."
            )
            return False

        if attach and any(
            component["type"] == "header"
            for component in self.template_components
        ):
            self.logger.warning(
                "Use an attachment header or an explicit header, not both."
            )
            return False

        attachments = []
        if attach and self.attachment_support:
            if not self.bucket:
                self.logger.warning(
                    "AWS WhatsApp attachments require bucket=."
                )
                return False

            for attachment in attach:
                if not attachment:
                    self.logger.warning(
                        "Could not read AWS WhatsApp attachment."
                    )
                    return False
                kind, limit = MEDIA_TYPES.get(attachment.mimetype, (None, 0))
                if not kind or not 0 < len(attachment) <= limit:
                    self.logger.warning(
                        "Unsupported AWS WhatsApp attachment type or size."
                    )
                    return False
                attachments.append((attachment, kind))
            if self.template and (
                len(attachments) != 1
                or attachments[0][1] not in ("image", "video", "document")
            ):
                self.logger.warning(
                    "A media template requires one image, video or document."
                )
                return False

        if not (body or self.template or attachments):
            return False

        credentials = {}
        if self.access_key_id:
            credentials = {
                "aws_access_key_id": self.access_key_id,
                "aws_secret_access_key": self.secret_access_key,
                "aws_session_token": self.session_token,
            }
        try:
            session = boto3.Session(**credentials)
            config = Config(
                connect_timeout=self.socket_connect_timeout,
                read_timeout=self.socket_read_timeout,
                # No idempotency token: retrying an ambiguous timeout can
                # deliver the same notification twice.
                retries={"total_max_attempts": 1, "mode": "standard"},
            )
            client = session.client(
                "socialmessaging",
                region_name=self.region_name,
                verify=self.verify_certificate,
                config=config,
            )
        except (BotoCoreError, ClientError):
            self.logger.warning("Could not initialize AWS WhatsApp client.")
            return False

        has_error = False
        s3 = None
        try:
            media = []
            for index, (attachment, kind) in enumerate(attachments):
                media_id = self.recall(("media", index), per_message=True)
                if not media_id:
                    if s3 is None:
                        try:
                            s3 = session.client(
                                "s3",
                                region_name=self.region_name,
                                verify=self.verify_certificate,
                                config=config,
                            )
                        except (BotoCoreError, ClientError):
                            self.logger.warning(
                                "Could not initialize S3 client."
                            )
                            return False
                    media_id = self._upload_media(client, s3, attachment)
                    if not media_id:
                        return False
                    self.remember(("media", index), media_id, per_message=True)
                content = {"id": media_id}
                if kind == "document":
                    content["filename"] = attachment.name
                media.append((kind, content))

            for target in self.targets:
                if self.is_delivered(target):
                    continue
                payload = {
                    "messaging_product": "whatsapp",
                    "to": target,
                    "type": "template" if self.template else "text",
                }
                if self.template:
                    template = {
                        "name": self.template,
                        "language": {"code": self.language},
                    }
                    if self.template_components:
                        template["components"] = self._render_components(
                            self.template_components,
                            {"$body": body, "$type": notify_type.value},
                        )
                    if self.components:
                        values = {"body": body, "type": notify_type.value}
                        template.setdefault("components", []).extend(
                            [
                                {
                                    "type": "body",
                                    "parameters": [
                                        {
                                            "type": "text",
                                            **(
                                                {"parameter_name": index}
                                                if isinstance(index, str)
                                                else {}
                                            ),
                                            "text": values[value]
                                            if mapped
                                            else value,
                                        }
                                        for index, (mapped, value) in sorted(
                                            self.components.items()
                                        )
                                    ],
                                }
                            ]
                        )
                    payload["template"] = template
                    if media:
                        kind, content = media[0]
                        # Filenames belong to document messages, not headers.
                        template.setdefault("components", []).append(
                            {
                                "type": "header",
                                "parameters": [
                                    {
                                        "type": kind,
                                        kind: {"id": content["id"]},
                                    }
                                ],
                            }
                        )
                else:
                    payload["text"] = {"body": body}
                delivered = True
                body_key = ("body", target)
                if (self.template or body) and not self.is_delivered(body_key):
                    if self._send_payload(client, payload):
                        self.mark_delivered(body_key)
                    else:
                        delivered = False
                if not self.template:
                    for index, (kind, content) in enumerate(media):
                        key = ("attachment", target, index)
                        if self.is_delivered(key, per_message=True):
                            continue
                        if self._send_payload(
                            client,
                            {
                                "messaging_product": "whatsapp",
                                "to": target,
                                "type": kind,
                                kind: content,
                            },
                        ):
                            self.mark_delivered(key, per_message=True)
                        else:
                            delivered = False
                if delivered:
                    self.mark_delivered(target)
                else:
                    has_error = True
        finally:
            if s3 is not None:
                s3.close()
            client.close()
        return not has_error

    @staticmethod
    def _validate_components(components, template, mapped_body):
        """Validate explicit template headers, body parameters and buttons."""
        if components is None:
            return []
        try:
            if isinstance(components, str):
                components = loads(components)
            components = deepcopy(components)
            serialized = dumps(components, allow_nan=False)
            if len(serialized.encode("utf-8")) > 65536:
                raise ValueError("Template components exceed 64 KiB.")
            if not template or not isinstance(components, list):
                raise ValueError("Components require a template and a list.")
            seen = set()
            for component in components:
                if not isinstance(component, dict):
                    raise ValueError("Each component must be an object.")
                kind = component.get("type")
                if kind not in ("header", "body", "button"):
                    raise ValueError("Invalid template component type.")
                parameters = component.get("parameters")
                if not isinstance(parameters, list) or not parameters:
                    raise ValueError("Components require parameters.")
                key = kind
                if kind == "button":
                    index = str(component.get("index", ""))
                    if not re.fullmatch(r"[0-9]", index):
                        raise ValueError(
                            "Button index must be between 0 and 9."
                        )
                    component["index"] = index
                    subtype = component.get("sub_type")
                    parameter_type = {
                        "url": "text",
                        "quick_reply": "payload",
                        "copy_code": "coupon_code",
                        "flow": "action",
                    }.get(subtype)
                    if not parameter_type or len(parameters) != 1:
                        raise ValueError(
                            "Invalid button subtype or parameters."
                        )
                    if parameters[0].get("type") != parameter_type:
                        raise ValueError("Button parameter type mismatch.")
                    key = (kind, index)
                if key in seen or (kind == "body" and mapped_body):
                    raise ValueError("Duplicate template component.")
                seen.add(key)
                if kind == "header" and len(parameters) != 1:
                    raise ValueError(
                        "A header requires exactly one parameter."
                    )
                for parameter in parameters:
                    if not isinstance(parameter, dict):
                        raise ValueError("Parameters must be objects.")
                    ptype = parameter.get("type")
                    if ptype in ("text", "payload", "coupon_code"):
                        if (
                            not isinstance(parameter.get(ptype), str)
                            or not parameter[ptype]
                        ):
                            raise ValueError(
                                "Text parameters must be nonempty strings."
                            )
                        if kind in ("header", "body") and ptype != "text":
                            raise ValueError("Invalid header parameter type.")
                    elif ptype == "location" and kind == "header":
                        location = parameter.get("location", {})
                        for name, limit in (
                            ("latitude", 90),
                            ("longitude", 180),
                        ):
                            value = location.get(name)
                            if (
                                isinstance(value, bool)
                                or not math.isfinite(float(value))
                                or abs(float(value)) > limit
                            ):
                                raise ValueError(
                                    "Invalid location coordinates."
                                )
                        if not all(
                            isinstance(location.get(name), str)
                            and location[name]
                            for name in ("name", "address")
                        ):
                            raise ValueError(
                                "Location requires a name and address."
                            )
                    elif (
                        ptype in ("image", "video", "document")
                        and kind == "header"
                    ):
                        media = parameter.get(ptype)
                        if (
                            not isinstance(media, dict)
                            or len(set(media) & {"id", "link"}) != 1
                        ):
                            raise ValueError(
                                "Media requires one ID or HTTPS link."
                            )
                        field = "id" if "id" in media else "link"
                        if (
                            not isinstance(media[field], str)
                            or not media[field]
                        ):
                            raise ValueError("Invalid header media reference.")
                        if field == "link" and not media[field].startswith(
                            "https://"
                        ):
                            raise ValueError(
                                "Header media links require HTTPS."
                            )
                    elif ptype == "action" and kind == "button":
                        if not isinstance(parameter.get("action"), dict):
                            raise ValueError("Flow action must be an object.")
                    else:
                        raise ValueError(
                            "Unsupported template parameter type."
                        )
            return deepcopy(components)
        except (
            ValueError,
            TypeError,
            AttributeError,
            RecursionError,
        ) as error:
            raise AppriseImproperlyConfigured(
                "Invalid WhatsApp template components."
            ) from error

    @staticmethod
    def _render_components(value, mappings):
        """Resolve exact dynamic text values without interpreting syntax."""
        if isinstance(value, str):
            return (
                value[1:]
                if value.startswith("$$")
                else mappings.get(value, value)
            )
        if isinstance(value, list):
            return [
                NotifyAWSWhatsApp._render_components(item, mappings)
                for item in value
            ]
        if isinstance(value, dict):
            return {
                key: NotifyAWSWhatsApp._render_components(item, mappings)
                for key, item in value.items()
            }
        return value

    def _upload_media(self, client, s3, attachment):
        """Stage a private S3 object, import it to WhatsApp and remove it."""
        key = f"{self.prefix}{uuid4().hex}"
        try:
            with attachment.open() as stream:
                s3.upload_fileobj(
                    stream,
                    self.bucket,
                    key,
                    ExtraArgs={"ContentType": attachment.mimetype},
                )
            url = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=300,
            )
            self.throttle()
            response = client.post_whatsapp_message_media(
                originationPhoneNumberId=self.from_phone_id,
                sourceS3PresignedUrl={
                    "url": url,
                    "headers": {"Content-Type": attachment.mimetype},
                },
            )
            media_id = response.get("mediaId")
            if media_id:
                return media_id
            self.logger.warning("AWS WhatsApp returned no media ID.")
        except (Boto3Error, BotoCoreError, ClientError, OSError):
            self.logger.warning("AWS WhatsApp media upload failed.")
        finally:
            try:
                s3.delete_object(Bucket=self.bucket, Key=key)
            except (BotoCoreError, ClientError):
                self.logger.warning(
                    "Could not remove temporary AWS WhatsApp S3 object."
                )
        return None

    def _send_payload(self, client, payload):
        """Return whether AWS accepted one text, template or media message."""
        self.throttle()
        try:
            response = client.send_whatsapp_message(
                originationPhoneNumberId=self.from_phone_id,
                metaApiVersion=self.meta_api_version,
                message=dumps(payload, ensure_ascii=False).encode("utf-8"),
            )
        except ClientError as error:
            self.logger.warning(
                "AWS WhatsApp request failed: %s.",
                error.response.get("Error", {}).get("Code", "Unknown"),
            )
            return False
        except BotoCoreError:
            self.logger.warning("AWS WhatsApp connection failed.")
            return False
        if not response.get("messageId"):
            self.logger.warning("AWS WhatsApp returned no message ID.")
            return False
        self.logger.info(
            "AWS WhatsApp accepted message %s.", response["messageId"]
        )
        return True

    @property
    def url_identifier(self):
        """Identify the AWS account, region and sender."""
        return (
            self.secure_protocol,
            self.region_name,
            self.from_phone_id,
            self.access_key_id,
        )

    def url(self, privacy=False, *args, **kwargs):
        """Serialize settings, optionally masking credentials."""
        params = self.url_parameters(privacy=privacy, *args, **kwargs)
        params.update(lang=self.language, version=self.meta_api_version)
        if self.template:
            params["template"] = self.template
        if self.template_components:
            params["components"] = (
                "****" if privacy else dumps(self.template_components)
            )
        if self.transcode != "none":
            params["transcode"] = self.transcode
        if self.bucket:
            params["bucket"] = self.bucket
        if self.prefix != "apprise/":
            params["prefix"] = self.prefix
        if self.session_token:
            params["token"] = (
                self.pprint(
                    self.session_token,
                    privacy,
                    mode=PrivacyMode.Secret,
                    safe="",
                )
                if privacy
                else self.session_token
            )
        params.update({f":{k}": v for k, v in self.template_mapping.items()})
        auth = ""
        if self.access_key_id:
            auth = "{}:{}@".format(
                self.pprint(self.access_key_id, privacy, safe=""),
                self.pprint(
                    self.secret_access_key,
                    privacy,
                    mode=PrivacyMode.Secret,
                    safe="",
                ),
            )
        return "{schema}://{auth}{region}/{sender}/{targets}/?{params}".format(
            schema=self.secure_protocol,
            auth=auth,
            region=self.region_name,
            sender=self.from_phone_id,
            targets="/".join(self.quote(x, safe="") for x in self.targets),
            params=self.urlencode(params),
        )

    def __len__(self):
        """Return the recipient count."""
        return len(self.targets) or 1

    @staticmethod
    def parse_url(url):
        """Parse region, sender, recipients and optional AWS credentials."""
        results = NotifyBase.parse_url(url)
        if not results:
            return results
        parts = NotifyAWSWhatsApp.split_path(results["fullpath"])
        results["region_name"] = results["host"]
        results["from_phone_id"] = parts.pop(0) if parts else ""
        results["targets"] = parts
        results["access_key_id"] = NotifyAWSWhatsApp.unquote(results["user"])
        results["secret_access_key"] = NotifyAWSWhatsApp.unquote(
            results["password"]
        )
        for query, name in (
            ("token", "session_token"),
            ("template", "template"),
            ("lang", "language"),
            ("version", "meta_api_version"),
            ("bucket", "bucket"),
            ("prefix", "prefix"),
            ("components", "template_components"),
            ("transcode", "transcode"),
        ):
            if query in results["qsd"]:
                results[name] = results["qsd"][query]
        if results["qsd"].get("to"):
            results["targets"] += parse_phone_no(results["qsd"]["to"])
        results["template_mapping"] = results["qsd:"]
        return results

    @staticmethod
    def runtime_deps():
        """Expose the optional SDK packages to the plugin manager."""
        return ("boto3", "botocore", "s3transfer", "jmespath")
