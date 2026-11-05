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

from json import dumps
import re

from ..common import NotifyType
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import is_phone_no, parse_phone_no
from .base import NotifyBase

try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import BotoCoreError, ClientError

    AWS_WHATSAPP_SUPPORT_ENABLED = True
except ImportError:
    AWS_WHATSAPP_SUPPORT_ENABLED = False


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
        self.language = language
        self.meta_api_version = meta_api_version
        self.template_mapping = dict(template_mapping or {})
        self.components = {}
        for key, value in self.template_mapping.items():
            if key in ("body", "type"):
                if not re.fullmatch(r"[1-9][0-9]*", str(value)):
                    raise AppriseImproperlyConfigured(
                        "Invalid template index."
                    )
                index, content = int(value), key
            elif re.fullmatch(r"[1-9][0-9]*", str(key)):
                index, content = int(key), str(value)
            else:
                raise AppriseImproperlyConfigured("Invalid template mapping.")
            if index in self.components:
                raise AppriseImproperlyConfigured("Duplicate template index.")
            self.components[index] = (key in ("body", "type"), content)
        if self.components and (
            not template
            or sorted(self.components)
            != list(range(1, len(self.components) + 1))
        ):
            raise AppriseImproperlyConfigured(
                "Template mappings require a template and consecutive indices."
            )

        self.targets = []
        for target in parse_phone_no(targets):
            number = is_phone_no(target)
            if not number:
                raise AppriseImproperlyConfigured(
                    "An invalid WhatsApp recipient was specified."
                )
            number = "+{}".format(number["full"])
            if number not in self.targets:
                self.targets.append(number)

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Send each recipient separately and preserve partial successes."""
        if not self.targets or not self.enabled:
            return False

        credentials = {}
        if self.access_key_id:
            credentials = {
                "aws_access_key_id": self.access_key_id,
                "aws_secret_access_key": self.secret_access_key,
                "aws_session_token": self.session_token,
            }
        try:
            client = boto3.Session(**credentials).client(
                "socialmessaging",
                region_name=self.region_name,
                verify=self.verify_certificate,
                config=Config(
                    connect_timeout=self.socket_connect_timeout,
                    read_timeout=self.socket_read_timeout,
                    # This API has no idempotency token: SDK retries after an
                    # ambiguous timeout could send the same notification twice.
                    retries={"total_max_attempts": 1, "mode": "standard"},
                ),
            )
        except (BotoCoreError, ClientError):
            self.logger.warning("Could not initialize AWS WhatsApp client.")
            return False

        has_error = False
        try:
            for target in self.targets:
                if self.is_delivered(target):
                    continue
                payload = {
                    "messaging_product": "whatsapp",
                    "to": target.lstrip("+"),
                    "type": "template" if self.template else "text",
                }
                if self.template:
                    template = {
                        "name": self.template,
                        "language": {"code": self.language},
                    }
                    if self.components:
                        values = {"body": body, "type": notify_type.value}
                        template["components"] = [
                            {
                                "type": "body",
                                "parameters": [
                                    {
                                        "type": "text",
                                        "text": values[value]
                                        if mapped
                                        else value,
                                    }
                                    for _, (mapped, value) in sorted(
                                        self.components.items()
                                    )
                                ],
                            }
                        ]
                    payload["template"] = template
                else:
                    payload["text"] = {"body": body}
                self.throttle()
                try:
                    response = client.send_whatsapp_message(
                        originationPhoneNumberId=self.from_phone_id,
                        metaApiVersion=self.meta_api_version,
                        message=dumps(payload, ensure_ascii=False).encode(
                            "utf-8"
                        ),
                    )
                except ClientError as error:
                    self.logger.warning(
                        "AWS WhatsApp request failed: %s.",
                        error.response.get("Error", {}).get("Code", "Unknown"),
                    )
                    has_error = True
                    continue
                except BotoCoreError:
                    self.logger.warning("AWS WhatsApp connection failed.")
                    has_error = True
                    continue
                if not response.get("messageId"):
                    self.logger.warning("AWS WhatsApp returned no message ID.")
                    has_error = True
                    continue
                self.mark_delivered(target)
        finally:
            client.close()
        return not has_error

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
