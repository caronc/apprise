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

# Trigv API reference: https://trigv.com/docs/learn/api-keys
# Ingest: POST https://api.trigv.com/api/v1/events
# Auth: Authorization: Bearer trgv_{8}_{32}

from json import dumps

import requests

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import validate_regex
from .base import NotifyBase

# Workspace ingest API key: trgv_{8 alphanumeric}_{32 alphanumeric}
VALIDATE_API_KEY = (
    r"^trgv_[a-zA-Z0-9]{8}_[a-zA-Z0-9]{32}$",
    "i",
)

# Channel slug (workspace-defined; max 120 on server)
VALIDATE_CHANNEL = (
    r"^[a-z0-9][a-z0-9_-]{0,119}$",
    "i",
)

DEFAULT_CHANNEL = "general"
DEFAULT_NOTIFY_URL = "https://api.trigv.com/api/v1/events"

TRIGV_LEVELS = {
    NotifyType.INFO: "info",
    NotifyType.SUCCESS: "success",
    NotifyType.WARNING: "warning",
    NotifyType.FAILURE: "error",
}

TRIGV_DELIVERY_URGENCIES = (
    "standard",
    "time_sensitive",
)

TRIGV_HTTP_ERROR_MAP = {
    401: "Unauthorized - Invalid API key.",
    403: "Forbidden - Revoked key, missing scope, or inactive workspace.",
    404: "Not found - Channel does not exist.",
    422: "Validation error - Check payload fields.",
    429: "Rate limit exceeded.",
}


class NotifyTrigv(NotifyBase):
    """A wrapper for Trigv push notifications."""

    service_name = "Trigv"

    service_url = "https://trigv.com/"

    protocol = "trigv"

    secure_protocol = "trigvs"

    setup_url = "https://trigv.com/docs/learn/api-keys"

    notify_url = DEFAULT_NOTIFY_URL

    title_maxlen = 255

    body_maxlen = 1000

    templates = (
        "{schema}://{api_key}",
        "{schema}://{api_key}/{channel}",
        "{schema}://{api_key}@{host}/{channel}",
        "{schema}://{api_key}@{host}",
    )

    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "api_key": {
                "name": _("API Key"),
                "type": "string",
                "private": True,
                "required": True,
                "regex": VALIDATE_API_KEY,
            },
            "channel": {
                "name": _("Channel slug"),
                "type": "string",
                "regex": VALIDATE_CHANNEL,
                "default": DEFAULT_CHANNEL,
            },
            "host": {
                "name": _("API Hostname"),
                "type": "string",
            },
        },
    )

    template_args = dict(
        NotifyBase.template_args,
        **{
            "channel": {
                "name": _("Channel slug"),
                "type": "string",
                "regex": VALIDATE_CHANNEL,
            },
            "url": {
                "name": _("URL"),
                "map_to": "supplemental_url",
                "type": "string",
            },
            "image_url": {
                "name": _("Image URL"),
                "type": "string",
            },
            "delivery_urgency": {
                "name": _("Delivery urgency"),
                "type": "choice:string",
                "values": TRIGV_DELIVERY_URGENCIES,
                "default": "standard",
            },
            "event_type": {
                "name": _("Event type"),
                "type": "string",
            },
            "priority": {
                "name": _("Priority (Pushover compatibility)"),
                "type": "int",
            },
        },
    )

    def __init__(
        self,
        api_key,
        channel=None,
        supplemental_url=None,
        image_url=None,
        delivery_urgency=None,
        event_type=None,
        priority=None,
        **kwargs,
    ):
        """Initialize Trigv Object."""
        super().__init__(**kwargs)

        self.api_key = validate_regex(api_key, *VALIDATE_API_KEY)
        if not self.api_key:
            msg = f"An invalid Trigv API Key ({api_key}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        self.channel = (
            DEFAULT_CHANNEL
            if not channel
            else validate_regex(channel, *VALIDATE_CHANNEL)
        )
        if not self.channel:
            msg = f"An invalid Trigv channel slug ({channel}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        self.supplemental_url = supplemental_url
        self.image_url = image_url
        self.event_type = event_type
        self.priority = priority

        self.delivery_urgency = (
            self.template_args["delivery_urgency"]["default"]
            if delivery_urgency is None
            else str(delivery_urgency).lower()
        )
        if self.delivery_urgency not in TRIGV_DELIVERY_URGENCIES:
            msg = (
                "An invalid Trigv delivery urgency "
                f"({delivery_urgency}) was specified."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        if self.host:
            schema = "https" if self.secure else "http"
            port = f":{self.port}" if self.port else ""
            self.notify_url = f"{schema}://{self.host}{port}/api/v1/events"
        else:
            self.notify_url = DEFAULT_NOTIFY_URL

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform Trigv Notification."""

        resolved_title = title if title else (self.app_desc or "Apprise Alert")
        if not body and not title:
            body = resolved_title

        payload = {
            "channel": self.channel,
            "title": resolved_title[: self.title_maxlen],
            "level": TRIGV_LEVELS.get(notify_type, "info"),
        }

        if body:
            payload["description"] = body[: self.body_maxlen]

        if self.supplemental_url:
            payload["url"] = self.supplemental_url

        if self.image_url:
            payload["image_url"] = self.image_url

        if self.event_type:
            payload["event_type"] = self.event_type

        payload["delivery_urgency"] = self._resolve_delivery_urgency(
            notify_type
        )

        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        self.logger.debug(
            "Trigv POST URL:"
            f" {self.notify_url} (cert_verify={self.verify_certificate!r})"
        )
        self.logger.debug(f"Trigv Payload: {payload!s}")

        self.throttle()

        try:
            r = requests.post(
                self.notify_url,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )

            ok_codes = (requests.codes.ok, requests.codes.accepted)
            if r.status_code not in ok_codes:
                status_str = NotifyTrigv.http_response_code_lookup(
                    r.status_code, TRIGV_HTTP_ERROR_MAP
                )

                self.logger.warning(
                    "Failed to send Trigv notification: {}{}error={}.".format(
                        status_str, ", " if status_str else "", r.status_code
                    )
                )

                self.logger.debug(
                    "Response Details:\r\n%r", (r.content or b"")[:2000]
                )

                return False

            self.logger.info("Sent Trigv notification.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending Trigv notification."
            )
            self.logger.debug(f"Socket Exception: {e!s}")
            return False

        return True

    def _resolve_delivery_urgency(self, notify_type):
        """Map explicit urgency, Pushover-style priority, or defaults."""

        if self.delivery_urgency != "standard":
            return self.delivery_urgency

        if self.priority is not None:
            try:
                priority = int(self.priority)
            except (TypeError, ValueError):
                priority = 0

            if priority >= 1:
                return "time_sensitive"

        if notify_type == NotifyType.FAILURE:
            return "time_sensitive"

        return "standard"

    @property
    def url_identifier(self):
        """Returns identifiers that make this URL unique."""

        return (
            self.secure_protocol if self.secure else self.protocol,
            self.api_key,
            self.host,
            self.port,
        )

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        params = {}

        if self.channel != DEFAULT_CHANNEL:
            params["channel"] = self.channel

        if self.supplemental_url:
            params["url"] = self.supplemental_url

        if self.image_url:
            params["image_url"] = self.image_url

        if self.delivery_urgency != "standard":
            params["delivery_urgency"] = self.delivery_urgency

        if self.event_type:
            params["event_type"] = self.event_type

        if self.priority is not None:
            params["priority"] = self.priority

        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        if self.host:
            channel_path = (
                f"/{NotifyTrigv.quote(self.channel, safe='')}"
                if self.channel
                else ""
            )
            return (
                "{schema}://{api_key}@{host}{port}{channel_path}/?{params}"
            ).format(
                schema=self.secure_protocol if self.secure else self.protocol,
                api_key=self.pprint(self.api_key, privacy, safe=""),
                host=self.host,
                port="" if not self.port else f":{self.port}",
                channel_path=channel_path,
                params=NotifyTrigv.urlencode(params),
            )

        channel_path = (
            f"/{NotifyTrigv.quote(self.channel, safe='')}"
            if self.channel != DEFAULT_CHANNEL
            else ""
        )

        return "{schema}://{api_key}{channel_path}/?{params}".format(
            schema=self.secure_protocol if self.secure else self.protocol,
            api_key=self.pprint(self.api_key, privacy, safe=""),
            channel_path=channel_path,
            params=NotifyTrigv.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments to re-instantiate."""

        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            return results

        entries = NotifyTrigv.split_path(results["fullpath"])

        if results.get("user"):
            results["api_key"] = NotifyTrigv.unquote(results["user"])
        else:
            results["api_key"] = NotifyTrigv.unquote(results["host"])
            results["host"] = None

        if entries:
            results["channel"] = NotifyTrigv.unquote(entries[0])

        qsd = results["qsd"]

        if "channel" in qsd and len(qsd["channel"]):
            results["channel"] = NotifyTrigv.unquote(qsd["channel"])

        if "url" in qsd and len(qsd["url"]):
            results["supplemental_url"] = NotifyTrigv.unquote(qsd["url"])

        if "image_url" in qsd and len(qsd["image_url"]):
            results["image_url"] = NotifyTrigv.unquote(qsd["image_url"])

        if "delivery_urgency" in qsd and len(qsd["delivery_urgency"]):
            results["delivery_urgency"] = NotifyTrigv.unquote(
                qsd["delivery_urgency"]
            )

        if "event_type" in qsd and len(qsd["event_type"]):
            results["event_type"] = NotifyTrigv.unquote(qsd["event_type"])

        if "priority" in qsd and len(qsd["priority"]):
            results["priority"] = qsd["priority"]

        return results
