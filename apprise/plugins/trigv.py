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

# Steps to get your API key:
#  1. Visit https://trigv.com and create a workspace.
#  2. Under workspace settings, generate an ingest API key. It looks
#     like: trgv_AbCdEfGh_0123456789abcdef0123456789abcdef
#  3. Decide which channel slug(s) you want the alert delivered to (the
#     "general" channel is used if you do not specify one).
#
#  Your Apprise URL should be assembled as:
#     trigvs://{api_key}/{channel}
#
#  Multiple channels may be notified in one call by separating them
#  with a slash:
#     trigvs://{api_key}/{channel1}/{channel2}
#
# Resources:
# - https://trigv.com/docs/learn/api-keys

from json import dumps

import requests

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import parse_list, validate_regex
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

# Our channel used when none is otherwise specified
DEFAULT_CHANNEL = "general"

# Our ingest endpoint when no self-hosted hostname is provided
DEFAULT_NOTIFY_URL = "https://api.trigv.com/api/v1/events"

# Map our Apprise notify types onto the levels Trigv understands
TRIGV_LEVELS = {
    NotifyType.INFO: "info",
    NotifyType.SUCCESS: "success",
    NotifyType.WARNING: "warning",
    NotifyType.FAILURE: "error",
}

# Valid values for our urgency selector
TRIGV_URGENCIES = (
    "standard",
    "time_sensitive",
)

# Extend HTTP Error Messages
TRIGV_HTTP_ERROR_MAP = {
    401: "Unauthorized - Invalid API key.",
    403: "Forbidden - Revoked key, missing scope, or inactive workspace.",
    404: "Not found - Channel does not exist.",
    422: "Validation error - Check payload fields.",
    429: "Rate limit exceeded.",
}


class NotifyTrigv(NotifyBase):
    """A wrapper for Trigv push notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Trigv"

    # The services URL
    service_url = "https://trigv.com/"

    # The default protocol
    protocol = "trigv"

    # The default secure protocol
    secure_protocol = "trigvs"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://trigv.com/docs/learn/api-keys"

    # Trigv Notification (ingest) URL
    notify_url = DEFAULT_NOTIFY_URL

    # Trigv's ingest API only accepts a public image URL reference
    # (image_url) inside the JSON payload; there is no endpoint for
    # uploading raw file bytes, so Apprise attachments are not wired in.
    attachment_support = False

    # The maximum allowable characters allowed in the title
    title_maxlen = 255

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 1000

    # Define object URL templates
    templates = (
        "{schema}://{api_key}",
        "{schema}://{api_key}/{targets}",
        "{schema}://{api_key}@{host}/{targets}",
        "{schema}://{api_key}@{host}:{port}/{targets}",
        "{schema}://{api_key}@{host}",
    )

    # Define our template tokens
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
            # A single channel entry within our list of targets
            "target_channel": {
                "name": _("Target Channel"),
                "type": "string",
                "map_to": "targets",
            },
            "targets": {
                "name": _("Targets"),
                "type": "list:string",
            },
            "host": {
                "name": _("API Hostname"),
                "type": "string",
            },
            "port": {
                "name": _("Port"),
                "type": "int",
                "min": 1,
                "max": 65535,
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            # The project-wide convention for supplying targets
            "to": {
                "alias_of": "targets",
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
            "urgency": {
                "name": _("Urgency"),
                "type": "choice:string",
                "values": TRIGV_URGENCIES,
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
        targets=None,
        supplemental_url=None,
        image_url=None,
        urgency=None,
        event_type=None,
        priority=None,
        **kwargs,
    ):
        """Initialize Trigv Object."""
        super().__init__(**kwargs)

        # Our workspace ingest API key is required
        self.api_key = validate_regex(api_key, *VALIDATE_API_KEY)
        if not self.api_key:
            msg = f"An invalid Trigv API Key ({api_key}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Build our list of channels to notify; validate each one as
        # we go so a single bad entry fails loudly instead of silently
        self.targets = []
        for target in parse_list(targets):
            channel = validate_regex(target, *VALIDATE_CHANNEL)
            if not channel:
                msg = (
                    f"An invalid Trigv channel slug ({target}) was specified."
                )
                self.logger.warning(msg)
                raise TypeError(msg)

            self.targets.append(channel)

        # No channel specified; fall back to our default one
        if not self.targets:
            self.targets.append(DEFAULT_CHANNEL)

        # These are all optional payload enrichments
        self.supplemental_url = supplemental_url
        self.image_url = image_url
        self.event_type = event_type

        # Pushover-style priority; ignore anything we can't parse as
        # an int rather than rejecting the whole notification
        if priority is None:
            self.priority = None
        else:
            try:
                self.priority = int(priority)
            except (TypeError, ValueError):
                self.priority = None

        # Resolve our urgency selector, falling back to our default
        self.urgency = (
            self.template_args["urgency"]["default"]
            if urgency is None
            else str(urgency).lower()
        )
        if self.urgency not in TRIGV_URGENCIES:
            msg = f"An invalid Trigv urgency ({urgency}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # A custom hostname (e.g. a local/self-hosted ingest gateway)
        # overrides our default api.trigv.com endpoint; a port can be
        # supplied alongside it the same way any other Apprise URL does
        if self.host:
            schema = "https" if self.secure else "http"
            port = f":{self.port}" if self.port else ""
            self.notify_url = f"{schema}://{self.host}{port}/api/v1/events"
        else:
            self.notify_url = DEFAULT_NOTIFY_URL

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform Trigv Notification."""

        # Trigv requires a title; fall back to our app description
        resolved_title = title if title else (self.app_desc or "Apprise Alert")
        if not body and not title:
            body = resolved_title

        # Prepare our headers; shared across every channel we notify
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        # Our urgency is the same for every channel, so resolve it once
        urgency = self._resolve_urgency(notify_type)

        # Track whether any channel failed to be notified
        has_error = False

        for channel in self.targets:
            # Prepare our payload
            payload = {
                "channel": channel,
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

            # Trigv's own API field is delivery_urgency; our shorter
            # urgency= is only the Apprise-facing parameter name
            payload["delivery_urgency"] = urgency

            self.logger.debug(
                "Trigv POST URL:"
                f" {self.notify_url} (cert_verify={self.verify_certificate!r})"
            )
            self.logger.debug(f"Trigv Payload: {payload!s}")

            # Always call throttle before any remote server i/o is made
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

                # Trigv returns 202 on a new event and 200 on an
                # idempotent duplicate; both are success
                ok_codes = (requests.codes.ok, requests.codes.accepted)
                if r.status_code not in ok_codes:
                    status_str = NotifyTrigv.http_response_code_lookup(
                        r.status_code, TRIGV_HTTP_ERROR_MAP
                    )

                    self.logger.warning(
                        "Failed to send Trigv notification to "
                        "{}: {}{}error={}.".format(
                            channel,
                            status_str,
                            ", " if status_str else "",
                            r.status_code,
                        )
                    )

                    self.logger.debug(
                        "Response Details:\r\n%r", (r.content or b"")[:2000]
                    )

                    # Mark our failure and move onto the next channel
                    has_error = True
                    continue

                # We were successful
                self.logger.info("Sent Trigv notification to %s.", channel)

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending Trigv "
                    f"notification to {channel}."
                )
                self.logger.debug(f"Socket Exception: {e!s}")
                has_error = True

        return not has_error

    def _resolve_urgency(self, notify_type):
        """Map explicit urgency, Pushover-style priority, or defaults."""

        # An explicitly requested urgency always wins
        if self.urgency != "standard":
            return self.urgency

        # A Pushover-style priority of 1 or higher implies urgency
        if self.priority is not None and self.priority >= 1:
            return "time_sensitive"

        # Escalate failures to time-sensitive delivery by default
        if notify_type == NotifyType.FAILURE:
            return "time_sensitive"

        return "standard"

    def __len__(self):
        """Returns the number of channels this instance will notify."""
        # We always have at least our default channel to fall back on
        return len(self.targets) if self.targets else 1

    @property
    def url_identifier(self):
        """Returns identifiers that make this URL unique.

        Targets/channels are never included here; they identify where
        we deliver to, not the connection itself.
        """

        return (
            self.secure_protocol if self.secure else self.protocol,
            self.api_key,
            self.host,
            self.port,
        )

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Prepare our parameters
        params = {}

        if self.supplemental_url:
            params["url"] = self.supplemental_url

        if self.image_url:
            params["image_url"] = self.image_url

        if self.urgency != "standard":
            params["urgency"] = self.urgency

        if self.event_type:
            params["event_type"] = self.event_type

        if self.priority is not None:
            params["priority"] = self.priority

        # Extend our parameters with the ones on our parent class
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Omit the path entirely when we're only using our default
        # channel; otherwise render every channel we notify
        targets_path = (
            ""
            if self.targets == [DEFAULT_CHANNEL]
            else "/"
            + "/".join(
                NotifyTrigv.quote(target, safe="") for target in self.targets
            )
        )

        # A custom hostname is rendered as a user@host URL
        if self.host:
            return (
                "{schema}://{api_key}@{host}{port}{targets_path}/?{params}"
            ).format(
                schema=self.secure_protocol if self.secure else self.protocol,
                api_key=self.pprint(self.api_key, privacy, safe=""),
                host=self.host,
                port="" if not self.port else f":{self.port}",
                targets_path=targets_path,
                params=NotifyTrigv.urlencode(params),
            )

        # Otherwise our API key is the sole hostname component
        return "{schema}://{api_key}{targets_path}/?{params}".format(
            schema=self.secure_protocol if self.secure else self.protocol,
            api_key=self.pprint(self.api_key, privacy, safe=""),
            targets_path=targets_path,
            params=NotifyTrigv.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments to re-instantiate."""

        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            return results

        # Every path entry is a channel we should notify
        results["targets"] = NotifyTrigv.split_path(results["fullpath"])

        # Our API key is either the user portion of a user@host URL,
        # or the host itself when no custom hostname is in play
        if results.get("user"):
            results["api_key"] = NotifyTrigv.unquote(results["user"])
        else:
            results["api_key"] = NotifyTrigv.unquote(results["host"])
            results["host"] = None

        qsd = results["qsd"]

        # ?to= is our standard way to add more targets
        if "to" in qsd and len(qsd["to"]):
            results["targets"] += NotifyTrigv.parse_list(qsd["to"])

        if "url" in qsd and len(qsd["url"]):
            results["supplemental_url"] = NotifyTrigv.unquote(qsd["url"])

        if "image_url" in qsd and len(qsd["image_url"]):
            results["image_url"] = NotifyTrigv.unquote(qsd["image_url"])

        if "urgency" in qsd and len(qsd["urgency"]):
            results["urgency"] = NotifyTrigv.unquote(qsd["urgency"])

        if "event_type" in qsd and len(qsd["event_type"]):
            results["event_type"] = NotifyTrigv.unquote(qsd["event_type"])

        if "priority" in qsd and len(qsd["priority"]):
            results["priority"] = qsd["priority"]

        return results
