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


# OpsiMate is a self-hosted operations console that collects alerts from
# many monitoring sources.  Its Custom Alerts API accepts alerts from any
# tool that can make an HTTP request:
#  1. Install OpsiMate (https://docs.opsimate.dev/).
#  2. Find the API token of your installation.  It is the API_TOKEN of
#     the server (security.api_token in its config file); a default
#     installation ships with the token "opsimate".
#  3. Note the host and port the OpsiMate server listens on.
#
#  Your Apprise URL should be assembled as:
#     opsimate://{apikey}@{host}
#     opsimate://{apikey}@{host}:{port}
#     opsimates://{apikey}@{host}:{port}/{path}
#
#  Each notification fires (or resolves) one alert.  Apprise's title is the
#  alert name and its body the alert summary.  The notification type picks
#  the severity: a failure is critical, a warning is warning and an info or
#  success is info.  Add ?severity= to always use one severity, and
#  ?click= to attach a link back to wherever the alert came from.
#
#  Every alert carries an id.  OpsiMate updates the alert that already
#  carries the same id instead of adding a row, so a check that fires every
#  minute keeps one alert open rather than one per minute.  The id is
#  derived from the alert name unless ?dedup= names one.  Because of this,
#  with the default ?action=map a success notification resolves the alert a
#  failure with the same title raised: a tool that reports "down" as a
#  failure and "up" as a success keeps OpsiMate's active alert view clean
#  by itself.  A resolve leaves the severity out, so the alert keeps the
#  severity it was fired with.
#
#  The Custom Alerts API has no way to upload files, so attachments are
#  not supported.
#
# Resources:
# - https://docs.opsimate.dev/docs/integrations/custom-alerts

from __future__ import annotations

from hashlib import sha256
from json import dumps, loads
from typing import Any, Optional

import requests

from ..common import NotifyType
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..utils.parse import URL_PATH_SAFE_CHARS, parse_choice, validate_regex
from .base import NotifyBase

# Extend HTTP Error Messages
OPSIMATE_HTTP_ERROR_MAP = {
    400: "Validation error - OpsiMate rejected the alert payload.",
    401: "Authentication error - the OpsiMate API token is not valid.",
}


class OpsiMateSeverity:
    """The severities OpsiMate accepts."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


# Map Apprise notification types to OpsiMate severities
OPSIMATE_SEVERITY_MAP = {
    NotifyType.INFO: OpsiMateSeverity.INFO,
    NotifyType.SUCCESS: OpsiMateSeverity.INFO,
    NotifyType.WARNING: OpsiMateSeverity.WARNING,
    NotifyType.FAILURE: OpsiMateSeverity.CRITICAL,
}

# The severities a user can force with ?severity=
OPSIMATE_SEVERITIES = (
    OpsiMateSeverity.INFO,
    OpsiMateSeverity.WARNING,
    OpsiMateSeverity.CRITICAL,
)


class OpsiMateStatus:
    """The alert states OpsiMate accepts."""

    FIRING = "firing"
    RESOLVED = "resolved"


class OpsiMateAction:
    """Tracks the actions supported by the OpsiMate plugin."""

    # Resolve alerts on success, fire them otherwise
    MAP = "map"

    # Always fire (or update) the alert
    TRIGGER = "trigger"

    # Always resolve the alert that shares the same id
    RESOLVE = "resolve"


# Define our OpsiMate actions
OPSIMATE_ACTIONS = (
    OpsiMateAction.MAP,
    OpsiMateAction.TRIGGER,
    OpsiMateAction.RESOLVE,
)


class NotifyOpsiMate(NotifyBase):
    """A wrapper for OpsiMate Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "OpsiMate"

    # The services URL
    service_url = "https://opsimate.dev/"

    # The default protocol
    protocol = "opsimate"

    # The default secure protocol
    secure_protocol = "opsimates"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/opsimate/"

    # OpsiMate is self-hosted and normally on the local network, so there
    # is no need to throttle
    request_rate_per_sec = 0

    # The Custom Alerts API has no field for files
    attachment_support = False

    # Our Custom Alerts API path
    notify_path = "api/v1/alerts/custom"

    # The tag every alert carries (unless overridden) so OpsiMate shows
    # where it came from
    opsimate_source_tag = "apprise"

    # Define object URL templates
    templates = (
        "{schema}://{apikey}@{host}",
        "{schema}://{apikey}@{host}:{port}",
        "{schema}://{apikey}@{host}{path}",
        "{schema}://{apikey}@{host}:{port}{path}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "apikey": {
                "name": _("API Token"),
                "type": "string",
                "private": True,
                "required": True,
            },
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
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "apikey": {
                "alias_of": "apikey",
            },
            "token": {
                "alias_of": "apikey",
            },
            "action": {
                "name": _("Action"),
                "type": "choice:string",
                "values": OPSIMATE_ACTIONS,
                "default": OPSIMATE_ACTIONS[0],
            },
            "dedup": {
                "name": _("Deduplication Key"),
                "type": "string",
            },
            "click": {
                "name": _("Click"),
                "type": "string",
            },
            # The severity is automatically determined, however you can
            # optionally over-ride its value and force it to be what you want
            "severity": {
                "name": _("Severity"),
                "type": "choice:string",
                "values": OPSIMATE_SEVERITIES,
            },
        },
    )

    # Define any kwargs we're using.  These are not called "tags" because
    # Apprise already uses that name for its own tag filtering.
    template_kwargs = {
        "xtags": {
            "name": _("Tags"),
            "prefix": "+",
        },
    }

    def __init__(
        self,
        apikey: str,
        action: Optional[str] = None,
        dedup: Optional[str] = None,
        click: Optional[str] = None,
        severity: Optional[str] = None,
        xtags: Optional[dict[str, str]] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize OpsiMate Object."""
        super().__init__(**kwargs)

        # The API token of the OpsiMate server
        self.apikey = validate_regex(apikey)
        if not self.apikey:
            msg = "An invalid OpsiMate API token ({}) was specified.".format(
                apikey
            )
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Resolve our action; partial names such as "r" are accepted
        if action and isinstance(action, str) and action.strip():
            self.action = parse_choice(action, OPSIMATE_ACTIONS)
            if not self.action:
                msg = "The OpsiMate action specified ({}) is invalid.".format(
                    action
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

        else:
            # Default to mapping our notification type
            self.action = self.template_args["action"]["default"]

        # A fixed alert id; every notification then addresses one alert
        self.dedup = dedup.strip() if dedup and dedup.strip() else None

        # A link back to wherever the alert came from
        self.click = click.strip() if click and click.strip() else None

        # A fixed severity; partial names such as "c" are accepted
        self.severity = None
        if severity and isinstance(severity, str) and severity.strip():
            self.severity = parse_choice(severity, OPSIMATE_SEVERITIES)
            if not self.severity:
                msg = (
                    "The OpsiMate severity specified ({}) is invalid.".format(
                        severity
                    )
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

        # Extra tags shown on the alert
        self.xtags = dict(xtags) if xtags else {}

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        **kwargs: Any,
    ) -> bool:
        """Perform OpsiMate Notification."""

        # The title names the alert.  Without one, the first line of the
        # body stands in for it.
        alert_name = title.strip() if title else ""
        if not alert_name:
            alert_name = (
                body.strip().split("\n", 1)[0].strip()[: self.title_maxlen]
            )

        # The id ties repeats of the same alert together.  OpsiMate updates
        # the alert that carries it instead of creating another, so the
        # same name must always yield the same id.
        alert_id = self.dedup
        if not alert_id:
            alert_id = "apprise-{}".format(
                sha256(alert_name.lower().encode("utf-8")).hexdigest()[:16]
            )

        # Map resolves on success and fires the alert otherwise
        status = (
            OpsiMateStatus.RESOLVED
            if self.action == OpsiMateAction.RESOLVE
            or (
                self.action == OpsiMateAction.MAP
                and notify_type == NotifyType.SUCCESS
            )
            else OpsiMateStatus.FIRING
        )

        # Our tags; the source identifies Apprise unless one was given
        tags = {"source": self.opsimate_source_tag}
        tags.update(self.xtags)

        # Prepare our payload
        payload = {
            "id": alert_id,
            "alertName": alert_name,
            "summary": body,
            "status": status,
            "tags": tags,
        }

        if status == OpsiMateStatus.FIRING:
            # A resolve leaves the severity out so OpsiMate keeps the one
            # the alert was fired with
            payload["severity"] = (
                self.severity
                if self.severity
                else OPSIMATE_SEVERITY_MAP[notify_type]
            )

        if self.click:
            # OpsiMate shows its links on the alert; "Source" is the label
            # it gives its own link back to an alert's origin
            payload["links"] = [{"label": "Source", "url": self.click}]

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-api-token": self.apikey,
        }

        # Our sub-path, if OpsiMate is not hosted at the server root
        fullpath = self.fullpath.strip("/")

        # Prepare our URL
        notify_url = "{schema}://{host}{port}/{path}{api}".format(
            schema="https" if self.secure else "http",
            host=self.host,
            port="" if not self.port else ":{}".format(self.port),
            path=(
                NotifyOpsiMate.quote(
                    "{}/".format(fullpath), safe=URL_PATH_SAFE_CHARS
                )
                if fullpath
                else ""
            ),
            api=self.notify_path,
        )

        self.logger.debug(
            "OpsiMate POST URL: %s (cert_verify=%s)",
            notify_url,
            self.verify_certificate,
        )
        self.logger.debug("OpsiMate Payload: %s", payload)

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                notify_url,
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
                status_str = NotifyOpsiMate.http_response_code_lookup(
                    r.status_code, OPSIMATE_HTTP_ERROR_MAP
                )

                self.logger.warning(
                    "Failed to send OpsiMate alert: %s%serror=%s.",
                    status_str,
                    ", " if status_str else "",
                    r.status_code,
                )

                if r.status_code == requests.codes.bad_request:
                    # OpsiMate names the fields it rejected; pass that on
                    self.logger.warning(
                        "OpsiMate validation error: %s",
                        self._validation_details(r.content),
                    )

                self.logger.debug(
                    "Response Details:\r\n%r", (r.content or b"")[:2000]
                )

                # Return; we're done
                return False

            self.logger.info(
                "Sent OpsiMate alert (%s): %s", status, alert_name
            )

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending OpsiMate alert to %s.",
                self.host,
            )
            self.logger.debug("Socket Exception: %s", str(e))

            # Return; we're done
            return False

        return True

    @staticmethod
    def _validation_details(content: Any) -> str:
        """Reduces OpsiMate's 400 response to the message its details
        carry, falling back to the raw body when it is not what we expect."""
        try:
            response = loads(content)
            details = response.get("details") or []
            messages = [
                "{}: {}".format(
                    ".".join(str(p) for p in detail.get("path", [])),
                    detail.get("message", ""),
                )
                for detail in details
                if isinstance(detail, dict)
            ]
            return (
                "; ".join(messages)
                if messages
                else str(response.get("error", response))
            )

        except (AttributeError, TypeError, ValueError):
            # ValueError = content is unparsable
            # TypeError = content is None
            # AttributeError = response is not a dictionary
            return repr((content or b"")[:2000])

    @property
    def url_identifier(self) -> tuple[Any, ...]:
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.apikey,
            self.host,
            self.port if self.port else (443 if self.secure else 80),
            self.fullpath.rstrip("/"),
        )

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {
            "action": self.action,
        }

        if self.dedup:
            params["dedup"] = self.dedup

        if self.click:
            params["click"] = self.click

        if self.severity:
            params["severity"] = self.severity

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Our tags are passed along as +key=value entries
        params.update({"+{}".format(k): v for k, v in self.xtags.items()})

        default_port = 443 if self.secure else 80
        return "{schema}://{apikey}@{host}{port}{fullpath}?{params}".format(
            schema=self.secure_protocol if self.secure else self.protocol,
            apikey=self.pprint(self.apikey, privacy, safe=""),
            # never encode hostname since we're expecting it to be a valid one
            host=self.host,
            port=(
                ""
                if self.port is None or self.port == default_port
                else ":{}".format(self.port)
            ),
            fullpath=NotifyOpsiMate.quote(self.fullpath, safe="/"),
            params=NotifyOpsiMate.urlencode(params),
        )

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parses the URL and returns enough arguments that can allow us to
        re-instantiate this object."""
        results = NotifyBase.parse_url(url)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Our API token leads the host
        results["apikey"] = (
            NotifyOpsiMate.unquote(results["user"])
            if results.get("user")
            else None
        )

        # Support ?apikey= and ?token= for an easier yaml configuration
        for key in ("apikey", "token"):
            if key in results["qsd"] and results["qsd"][key]:
                results["apikey"] = NotifyOpsiMate.unquote(results["qsd"][key])
                break

        # What to do with the alert
        if "action" in results["qsd"] and results["qsd"]["action"]:
            results["action"] = NotifyOpsiMate.unquote(
                results["qsd"]["action"]
            )

        # A fixed alert id
        if "dedup" in results["qsd"] and results["qsd"]["dedup"]:
            results["dedup"] = NotifyOpsiMate.unquote(results["qsd"]["dedup"])

        # A link back to wherever the alert came from
        if "click" in results["qsd"] and results["qsd"]["click"]:
            results["click"] = NotifyOpsiMate.unquote(results["qsd"]["click"])

        # A fixed severity
        if "severity" in results["qsd"] and results["qsd"]["severity"]:
            results["severity"] = NotifyOpsiMate.unquote(
                results["qsd"]["severity"]
            )

        # Store our +key=value tag entries
        results["xtags"] = {
            NotifyOpsiMate.unquote(x): NotifyOpsiMate.unquote(y)
            for x, y in results["qsd+"].items()
        }

        return results
