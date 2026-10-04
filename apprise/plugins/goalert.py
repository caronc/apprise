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

# GoAlert is a self-hosted on-call scheduling, alerting and escalation
# platform.  Apprise raises (and optionally closes) alerts through its
# Generic API.
#
# Steps to get your integration key:
#  1. Sign in to GoAlert and open the Service that should receive alerts.
#  2. Under Integration Keys, click the + button.
#  3. Give the key a name such as "Apprise", choose the "Generic API"
#     type and save it.
#  4. Copy the generated URL; it looks like:
#     https://goalert.example.com/api/v2/generic/incoming?token=\
#         ab12cd34-ab12-4c5d-8e9f-0123456789ab
#
#  The token is the integration key.  Your Apprise URL should be
#  assembled as:
#     goalerts://goalert.example.com/ab12cd34-ab12-4c5d-8e9f-0123456789ab
#
#  Each integration key belongs to one GoAlert Service, so adding more
#  keys to the path raises the alert in each of those services.
#
#  GoAlert has no file upload support on this API, so attachments are
#  not supported.
#
# Resources:
# - https://github.com/target/goalert
# - https://github.com/target/goalert/blob/master/web/src/app/\
#       documentation/sections/IntegrationKeys.md

from __future__ import annotations

from json import dumps
import re
from typing import Any, Optional, Union

import requests

from ..common import NotifyFormat, NotifyType
from ..conversion import commonmark_decode_backslash_escapes
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..utils.parse import URL_PATH_SAFE_CHARS, parse_list
from .base import NotifyBase

# Integration keys used by the Generic API are always UUIDs
IS_INTEGRATION_KEY = re.compile(
    r"^\s*(?P<key>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}"
    r"-[0-9a-f]{4}-[0-9a-f]{12})\s*$",
    re.I,
)

# The Generic API endpoint (relative to the GoAlert server and path)
GOALERT_API_PATH = "api/v2/generic/incoming"


class GoAlertAction:
    """Tracks the actions supported by the GoAlert plugin."""

    # Close alerts on success, raise them otherwise
    MAP = "map"

    # Always raise (or update) an alert
    TRIGGER = "trigger"

    # Always close matching alerts
    CLOSE = "close"


# Define our GoAlert Actions
GOALERT_ACTIONS = (
    GoAlertAction.MAP,
    GoAlertAction.TRIGGER,
    GoAlertAction.CLOSE,
)

# Extend HTTP Error Messages
GOALERT_HTTP_ERROR_MAP = {
    400: "Bad Request - Invalid payload.",
    401: "Unauthorized - Invalid Integration Key.",
    403: "Forbidden - Invalid Integration Key.",
    429: "Too many requests were made.",
}


class NotifyGoAlert(NotifyBase):
    """A wrapper for GoAlert Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "GoAlert"

    # The services URL
    service_url = "https://goalert.me/"

    # The default protocol
    protocol = "goalert"

    # The default secure protocol
    secure_protocol = "goalerts"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/goalert/"

    # The alert summary is sent as SMS and voice, and is limited to 1KiB
    title_maxlen = 1024

    # The alert details are limited to 6KiB
    body_maxlen = 6144

    # GoAlert renders the alert details as markdown
    notify_format = NotifyFormat.MARKDOWN

    # Define object templates
    templates = (
        "{schema}://{host}/{targets}",
        "{schema}://{host}:{port}/{targets}",
        "{schema}://{host}{path}{targets}",
        "{schema}://{host}:{port}{path}{targets}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "host": {
                "name": _("Hostname"),
                "type": "string",
                "required": True,
            },
            "port": {
                "name": _("Port"),
                "type": "int",
                "min": 1,
                "max": 65535,
            },
            "path": {
                "name": _("Path"),
                "type": "string",
                "map_to": "fullpath",
                "default": "/",
            },
            "targets": {
                "name": _("Integration Keys"),
                "type": "list:string",
                "private": True,
                "required": True,
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "to": {
                "alias_of": "targets",
            },
            "token": {
                "alias_of": "targets",
            },
            "action": {
                "name": _("Action"),
                "type": "choice:string",
                "values": GOALERT_ACTIONS,
                "default": GOALERT_ACTIONS[0],
            },
            "dedup": {
                "name": _("Deduplication Key"),
                "type": "string",
            },
        },
    )

    # Key/value pairs to attach to the alert as metadata
    template_kwargs = {
        "meta": {
            "name": _("Metadata"),
            "prefix": "+",
        },
    }

    def __init__(
        self,
        targets: Optional[Union[str, list[str]]] = None,
        action: Optional[str] = None,
        dedup: Optional[str] = None,
        meta: Optional[dict[str, str]] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize GoAlert Object."""
        super().__init__(**kwargs)

        # Resolve our action; partial names such as "c" are accepted
        if action and isinstance(action, str):
            self.action = next(
                (
                    a
                    for a in GOALERT_ACTIONS
                    if a.startswith(action.strip().lower())
                ),
                None,
            )
            if not self.action:
                msg = f"The GoAlert action specified ({action}) is invalid."
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

        else:
            # Default to mapping our notification type
            self.action = self.template_args["action"]["default"]

        # An optional key so repeated notifications update one alert
        self.dedup = dedup.strip() if isinstance(dedup, str) else None

        # Store any metadata to attach to the alert
        self.meta = {}
        if meta:
            self.meta.update(meta)

        # Our valid integration keys, and any we could not use
        self.targets = []
        self.invalid_targets = []

        for target in parse_list(targets):
            # Validate our integration key
            result = IS_INTEGRATION_KEY.match(target)
            if result:
                # Store our key in lowercase so duplicates line up
                self.targets.append(result.group("key").lower())
                continue

            # Keep the bad key so it survives in our URL
            self.logger.warning(
                "Ignoring invalid GoAlert integration key (%s).",
                target,
            )
            self.invalid_targets.append(target)

        return

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        body_passthrough: bool = False,
        **kwargs: Any,
    ) -> bool:
        """Perform GoAlert Notification."""

        if not self.targets:
            # There is no one to notify; we're done
            self.logger.warning(
                "There are no GoAlert integration keys to notify."
            )
            return False

        # Work out whether we raise or close the alert
        close = self.action == GoAlertAction.CLOSE or (
            self.action == GoAlertAction.MAP
            and notify_type == NotifyType.SUCCESS
        )

        # The summary is plain text sent by SMS and voice.  Without a
        # title, fall back to the body without the markdown escapes
        # Apprise added to it.
        summary = (
            title
            if title
            else (
                body
                if body_passthrough
                else commonmark_decode_backslash_escapes(body)
            )[: self.title_maxlen]
        )

        # Prepare our payload
        payload = {
            "summary": summary,
            "details": body,
        }

        # Close any matching alerts
        if close:
            payload["action"] = "close"

        # Let repeated notifications update the same alert
        if self.dedup:
            payload["dedup"] = self.dedup

        # Attach our metadata
        if self.meta:
            payload["meta"] = self.meta

        # Our sub-path, if GoAlert is not hosted at the server root
        fullpath = self.fullpath.strip("/")

        # Prepare our URL
        url = "{schema}://{host}{port}/{path}{api}".format(
            schema="https" if self.secure else "http",
            host=self.host,
            port="" if not self.port else f":{self.port}",
            path=(
                NotifyGoAlert.quote(f"{fullpath}/", safe=URL_PATH_SAFE_CHARS)
                if fullpath
                else ""
            ),
            api=GOALERT_API_PATH,
        )

        # Track whether any key failed
        has_error = False

        for key in self.targets:
            # Skip a key that already accepted this alert
            if self.is_delivered(key):
                continue

            # Prepare our headers; the key is passed as a bearer token
            headers = {
                "User-Agent": self.app_id,
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            }

            self.logger.debug(
                "GoAlert POST URL: %s (cert_verify=%s)",
                url,
                self.verify_certificate,
            )
            self.logger.debug("GoAlert Payload: %s", payload)

            # Always call throttle before any remote server i/o is made
            self.throttle()

            try:
                r = requests.post(
                    url,
                    data=dumps(payload),
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                    allow_redirects=self.redirects,
                )

                if r.status_code not in (
                    requests.codes.ok,
                    requests.codes.created,
                    requests.codes.accepted,
                    requests.codes.no_content,
                ):
                    # We had a problem
                    status_str = NotifyGoAlert.http_response_code_lookup(
                        r.status_code, GOALERT_HTTP_ERROR_MAP
                    )

                    self.logger.warning(
                        "Failed to send GoAlert notification to %s: "
                        "%s%serror=%s.",
                        self.pprint(key, privacy=True, safe=""),
                        status_str,
                        ", " if status_str else "",
                        r.status_code,
                    )

                    self.logger.debug(
                        "Response Details:\r\n%r", (r.content or b"")[:2000]
                    )

                    # Mark our failure
                    has_error = True
                    continue

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending GoAlert "
                    "notification to %s.",
                    self.host,
                )
                self.logger.debug("Socket Exception: %s", str(e))

                # Mark our failure
                has_error = True
                continue

            # Delivered; a retry can safely skip this key
            self.logger.info("Sent GoAlert notification.")
            self.mark_delivered(key)

        return not has_error

    @property
    def url_identifier(self) -> tuple[Any, ...]:
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        # The server and its path identify the connection
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.host,
            self.port if self.port else (443 if self.secure else 80),
            self.fullpath.strip("/"),
        )

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {
            "action": self.action,
        }

        if self.dedup:
            params["dedup"] = self.dedup

        # Keys we could not use are kept so nothing is lost
        if self.invalid_targets:
            params["to"] = ",".join(self.invalid_targets)

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Metadata is prefixed with a '+' sign
        params.update({f"+{k}": v for k, v in self.meta.items()})

        # Our default port
        default_port = 443 if self.secure else 80

        # Our sub-path entries come first, followed by our keys
        entries = [
            NotifyGoAlert.quote(e, safe="")
            for e in NotifyGoAlert.split_path(self.fullpath)
        ]
        entries.extend(self.pprint(k, privacy, safe="") for k in self.targets)

        return "{schema}://{host}{port}/{entries}?{params}".format(
            schema=self.secure_protocol if self.secure else self.protocol,
            # never encode hostname since we're expecting it to be a valid one
            host=self.host,
            port=(
                ""
                if self.port is None or self.port == default_port
                else f":{self.port}"
            ),
            entries="".join(f"{e}/" for e in entries),
            params=NotifyGoAlert.urlencode(params),
        )

    def __len__(self) -> int:
        """Returns the number of targets associated with this notification."""
        # Always return at least 1 so the framework counts this instance
        return len(self.targets) if self.targets else 1

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Integration keys are UUIDs, so anything else in the path is
        # where GoAlert is hosted on the server
        results["targets"] = []
        path = []
        for entry in NotifyGoAlert.split_path(results["fullpath"]):
            if IS_INTEGRATION_KEY.match(entry):
                results["targets"].append(entry)

            else:
                path.append(entry)

        # Re-assemble our full path
        results["fullpath"] = (
            "/" if not path else "/{}/".format("/".join(path))
        )

        # Support ?to= and ?token= for integration keys
        for key in ("to", "token"):
            if key in results["qsd"] and results["qsd"][key]:
                results["targets"] += parse_list(
                    NotifyGoAlert.unquote(results["qsd"][key])
                )

        # Store our action (if defined)
        if "action" in results["qsd"] and results["qsd"]["action"]:
            results["action"] = NotifyGoAlert.unquote(results["qsd"]["action"])

        # Store our deduplication key (if defined)
        if "dedup" in results["qsd"] and results["qsd"]["dedup"]:
            results["dedup"] = NotifyGoAlert.unquote(results["qsd"]["dedup"])

        # Store any metadata defined
        results["meta"] = {
            NotifyGoAlert.unquote(x): NotifyGoAlert.unquote(y)
            for x, y in results["qsd+"].items()
        }

        return results
