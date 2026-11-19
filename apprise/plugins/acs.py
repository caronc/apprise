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

# Azure Communication Services (ACS) Email
#
# You need an Azure Communication Services resource with a connected
# Email Communication Services domain. From the resource in the Azure
# portal, open "Keys" to find the Endpoint and an Access Key. The sender
# (from) address must be one of the MailFrom addresses of the connected
# domain, for example DoNotReply@<guid>.azurecomm.net.
#
# The schema to use the plugin looks like this:
#    {schema}://{from_email}/{access_key}/{endpoint}/{targets}
#
# The access key is base64 and may contain slashes. A base64 key never
# contains a dot, so the first path entry with a dot is the endpoint.
# A key with "//" in it must have each "/" written as %2F, or be passed
# with ?key= instead.
#
# API Reference:
#  - https://learn.microsoft.com/en-us/rest/api/communication/email/send
#  - https://learn.microsoft.com/en-us/azure/communication-services/
#       tutorials/hmac-header-tutorial

from __future__ import annotations

import base64
import binascii
from email.utils import formataddr, formatdate
import hashlib
import hmac
from json import dumps
import logging
import re
from typing import Any, Optional

import requests

from .. import exception
from ..common import NotifyFormat, NotifyType
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..utils.parse import is_email, parse_emails, validate_regex
from ..utils.sanitize import sanitize_payload
from .base import NotifyBase

# Extend HTTP Error Messages
ACS_HTTP_ERROR_MAP = {
    400: "The request was invalid; check the from address and recipients.",
    401: "The access key or request signature was rejected.",
    403: "The sender is not allowed to send from this domain.",
    404: "The endpoint or API version was not found.",
    429: "The rate limit was exceeded.",
    500: "Azure Communication Services had an internal error.",
    503: "Azure Communication Services is unavailable.",
}

# Accept an endpoint with or without its scheme and trailing slash.
IS_ENDPOINT = re.compile(
    r"^\s*(https?://)?(?P<host>[a-z0-9][a-z0-9.-]*\.[a-z]{2,})/*\s*$", re.I
)


class NotifyACS(NotifyBase):
    """A wrapper for Azure Communication Services Email Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Azure Communication Services"

    # The services URL
    service_url = "https://azure.microsoft.com/products/communication-services"

    # The default secure protocol
    secure_protocol = "acs"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/acs/"

    # ACS takes either an html or a plainText body, HTML is the default
    notify_format = (NotifyFormat.HTML, NotifyFormat.TEXT)

    # The Email Send API path and version
    notify_path = "/emails:send?api-version=2023-03-31"

    # Support attachments
    attachment_support = True

    # The default sending limit is 30 emails per minute
    request_rate_per_sec = 2.0

    # The default subject to use if one isn't specified.
    default_empty_subject = "<no subject>"

    # Define object templates
    templates = (
        "{schema}://{from_email}/{access_key}/{endpoint}",
        "{schema}://{from_email}/{access_key}/{endpoint}/{targets}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "from_email": {
                "name": _("Source Email"),
                "type": "email",
                "required": True,
            },
            "access_key": {
                "name": _("Access Key"),
                "type": "string",
                "private": True,
                "required": True,
                "regex": (r"^[A-Z0-9+/=]+$", "i"),
            },
            "endpoint": {
                "name": _("Hostname"),
                "type": "string",
                "required": True,
            },
            "target_email": {
                "name": _("Target Email"),
                "type": "email",
                "map_to": "targets",
            },
            "targets": {
                "name": _("Targets"),
                "type": "list:string",
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "from": {
                "alias_of": "from_email",
            },
            "key": {
                "alias_of": "access_key",
            },
            "endpoint": {
                "alias_of": "endpoint",
            },
            "to": {
                "alias_of": "targets",
            },
            "cc": {
                "name": _("Carbon Copy"),
                "type": "list:string",
            },
            "bcc": {
                "name": _("Blind Carbon Copy"),
                "type": "list:string",
            },
            "reply": {
                "name": _("Reply To"),
                "type": "list:string",
                "map_to": "reply_to",
            },
        },
    )

    def __init__(
        self,
        from_email: str,
        access_key: str,
        endpoint: str,
        targets: Optional[Any] = None,
        cc: Optional[Any] = None,
        bcc: Optional[Any] = None,
        reply_to: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Azure Communication Services Email Object."""
        super().__init__(**kwargs)

        result = is_email(from_email)
        if not result:
            msg = f"An invalid ACS From email ({from_email}) was specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # ACS takes the display name from the domain, not the request
        self.from_email = result["full_email"]

        self.access_key = validate_regex(
            access_key, *self.template_tokens["access_key"]["regex"]
        )
        try:
            if not self.access_key:
                raise ValueError()
            self._secret = base64.b64decode(self.access_key, validate=True)

        except (ValueError, binascii.Error):
            msg = "An invalid ACS Access Key was specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg) from None

        match = IS_ENDPOINT.match(endpoint) if endpoint else None
        if not match:
            msg = f"An invalid ACS Endpoint ({endpoint}) was specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        self.endpoint = match.group("host").lower()

        # For tracking our email -> name lookups
        self.names = {}

        self.targets = []
        for recipient in parse_emails(targets):
            result = is_email(recipient)
            if result:
                self.targets.append(result["full_email"])
                self.names[result["full_email"]] = result["name"] or False
                continue

            self.logger.warning(
                "Dropped invalid ACS email (%s) specified.", recipient
            )

        if not self.targets and not targets:
            # With no targets at all we notify ourselves
            self.targets.append(self.from_email)

        self.cc = self._parse_list(cc, "Carbon Copy")
        self.bcc = self._parse_list(bcc, "Blind Carbon Copy")
        self.reply_to = self._parse_list(reply_to, "Reply To")

    def _parse_list(self, emails: Optional[Any], label: str) -> set[str]:
        """Validate a list of emails, index any names, and drop bad ones."""
        valid = set()
        for recipient in parse_emails(emails):
            result = is_email(recipient)
            if result:
                valid.add(result["full_email"])
                self.names[result["full_email"]] = result["name"] or False
                continue

            self.logger.warning(
                "Dropped invalid ACS %s email (%s) specified.",
                label,
                recipient,
            )

        return valid

    def _address(self, email: str) -> dict[str, str]:
        """Build an ACS address object."""
        name = self.names.get(email)
        return (
            {"address": email, "displayName": name}
            if name
            else {"address": email}
        )

    def _sign(self, body: bytes) -> dict[str, str]:
        """Return the HMAC-SHA256 headers ACS needs for this request body."""
        date = formatdate(usegmt=True)
        content_hash = base64.b64encode(hashlib.sha256(body).digest()).decode(
            "utf-8"
        )
        string_to_sign = (
            f"POST\n{self.notify_path}\n{date};{self.endpoint};{content_hash}"
        )
        signature = base64.b64encode(
            hmac.new(
                self._secret, string_to_sign.encode("utf-8"), hashlib.sha256
            ).digest()
        ).decode("utf-8")

        return {
            "x-ms-date": date,
            "x-ms-content-sha256": content_hash,
            "Authorization": (
                "HMAC-SHA256 SignedHeaders=x-ms-date;host;x-ms-content-sha256"
                f"&Signature={signature}"
            ),
        }

    @property
    def url_identifier(self) -> tuple[Any, ...]:
        """Returns all of the identifiers that make this URL unique from
        another similar one.

        Targets or end points should never be identified here.
        """
        return (
            self.secure_protocol,
            self.from_email,
            self.access_key,
            self.endpoint,
        )

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # Our URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        for key, emails in (
            ("cc", self.cc),
            ("bcc", self.bcc),
            ("reply", self.reply_to),
        ):
            if emails:
                params[key] = ",".join(
                    (
                        formataddr((self.names[e], e), charset="utf-8")
                        if self.names.get(e) and key != "bcc"
                        else e
                    )
                    for e in sorted(emails)
                )

        has_targets = not (
            len(self.targets) == 1 and self.targets[0] == self.from_email
        )

        return (
            "{schema}://{from_email}/{key}/{endpoint}/{targets}?{params}"
        ).format(
            schema=self.secure_protocol,
            # never encode email since it plays a huge role in our hostname
            from_email=self.from_email,
            key=self.pprint(self.access_key, privacy, safe=""),
            endpoint=self.endpoint,
            targets=(
                "/".join(NotifyACS.quote(x, safe="@") for x in self.targets)
                if has_targets
                else ""
            ),
            params=NotifyACS.urlencode(params),
        )

    def __len__(self) -> int:
        """Returns the number of targets associated with this notification."""
        # Always return at least 1 so the framework counts this instance
        return max(1, len(self.targets))

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        attach: Optional[Any] = None,
        body_format: Optional[NotifyFormat] = None,
        **kwargs: Any,
    ) -> bool:
        """Perform Azure Communication Services Email Notification."""

        if not self.targets:
            self.logger.warning("There are no valid ACS email targets.")
            return False

        notify_url = f"https://{self.endpoint}{self.notify_path}"

        # Place the body in the field matching the format for this send
        content_key = (
            "plainText"
            if self.resolve_format(body_format) == NotifyFormat.TEXT
            else "html"
        )

        payload_ = {
            "senderAddress": self.from_email,
            "content": {
                "subject": title if title else self.default_empty_subject,
                content_key: body,
            },
            "userEngagementTrackingDisabled": True,
        }

        if attach and self.attachment_support:
            attachments = []
            for no, attachment in enumerate(attach, start=1):
                try:
                    if not attachment:
                        raise exception.AppriseFileNotFound(attachment.url())

                    attachments.append(
                        {
                            "name": (
                                attachment.name
                                if attachment.name
                                else f"file{no:03}.dat"
                            ),
                            "contentType": attachment.mimetype,
                            "contentInBase64": attachment.base64(),
                        }
                    )

                except exception.AppriseException:
                    self.logger.error(
                        "Could not access ACS attachment %s.",
                        attachment.url(privacy=True),
                    )
                    return False

                self.logger.debug(
                    "Appending ACS attachment %s",
                    attachment.url(privacy=True),
                )

            payload_["attachments"] = attachments

        # error tracking (used for function return)
        has_error = False

        for target in self.targets:
            # Skip a target that already accepted this message so
            # a retry does not deliver it twice.
            if self.is_delivered(target):
                continue

            payload = payload_.copy()
            recipients = {"to": [self._address(target)]}

            cc = self.cc - self.bcc - {target}
            if cc:
                recipients["cc"] = [self._address(e) for e in sorted(cc)]

            bcc = self.bcc - {target}
            if bcc:
                recipients["bcc"] = [{"address": e} for e in sorted(bcc)]

            payload["recipients"] = recipients

            reply_to = self.reply_to - {target}
            if reply_to:
                payload["replyTo"] = [
                    self._address(e) for e in sorted(reply_to)
                ]

            # The signature covers these exact bytes
            data = dumps(payload).encode("utf-8")
            headers = {
                "User-Agent": self.app_id,
                "Content-Type": "application/json",
                **self._sign(data),
            }

            if self.logger.isEnabledFor(logging.DEBUG):
                # Attachments can make the payload large, so only show
                # it when debugging.
                self.logger.debug(
                    "ACS POST URL: %s (cert_verify=%r)",
                    notify_url,
                    self.verify_certificate,
                )
                self.logger.debug("ACS Payload: %s", sanitize_payload(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.post(
                    notify_url,
                    data=data,
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                    allow_redirects=self.redirects,
                )
                if r.status_code not in (
                    requests.codes.ok,
                    requests.codes.accepted,
                ):
                    status_str = NotifyACS.http_response_code_lookup(
                        r.status_code, ACS_HTTP_ERROR_MAP
                    )

                    self.logger.warning(
                        "Failed to send ACS notification to %s: %s%serror=%s.",
                        target,
                        status_str,
                        ", " if status_str else "",
                        r.status_code,
                    )

                    self.logger.debug(
                        "Response Details:\r\n%r", (r.content or b"")[:2000]
                    )

                    has_error = True
                    continue

                self.logger.info("Sent ACS notification to %s.", target)

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending ACS "
                    "notification to %s.",
                    target,
                )
                self.logger.debug("Socket Exception: %s", str(e))

                has_error = True
                continue

            # Delivered; a retry can safely skip this target.
            self.mark_delivered(target)

        return not has_error

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""

        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        qsd = results["qsd"]
        results["from_email"] = None

        if "from" in qsd and len(qsd["from"]):
            results["from_email"] = NotifyACS.unquote(qsd["from"])

        elif results.get("user") and results.get("host"):
            results["from_email"] = "{}@{}".format(
                NotifyACS.unquote(results["user"]),
                NotifyACS.unquote(results["host"]),
            )

        access_key = (
            NotifyACS.unquote(qsd["key"])
            if "key" in qsd and len(qsd["key"])
            else None
        )
        endpoint = (
            NotifyACS.unquote(qsd["endpoint"])
            if "endpoint" in qsd and len(qsd["endpoint"])
            else None
        )

        # Split on "/" only; a base64 key may hold "//" or a trailing "/"
        entries = [
            NotifyACS.unquote(x)
            for x in (results["fullpath"] or "").lstrip("/").split("/")
        ]

        key_parts = []
        while entries and (access_key is None or endpoint is None):
            entry = entries.pop(0)
            if "." in entry:
                if endpoint is None:
                    endpoint = entry
                else:
                    entries.insert(0, entry)
                break

            key_parts.append(entry)

        if access_key is None and key_parts:
            access_key = "/".join(key_parts)

        results["access_key"] = access_key
        results["endpoint"] = endpoint

        # Everything left over is a target
        results["targets"] = NotifyACS.split_path("/".join(entries))

        # The 'to' makes it easier to use yaml configuration
        if "to" in qsd and len(qsd["to"]):
            results["targets"] += NotifyACS.parse_list(qsd["to"])

        if "cc" in qsd and len(qsd["cc"]):
            results["cc"] = qsd["cc"]

        if "bcc" in qsd and len(qsd["bcc"]):
            results["bcc"] = qsd["bcc"]

        if "reply" in qsd and len(qsd["reply"]):
            results["reply_to"] = qsd["reply"]

        return results
