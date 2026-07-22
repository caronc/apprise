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

# Pinglet - Push notifications with topic feeds
# Website: https://pinglet.co.uk
#
# Notifications are published to a topic within a namespace:
#   POST https://{host}/{namespace}/{topic}
#   Authorization: Bearer {apikey}
#   {"title": "...", "message": "...", "priority": "normal",
#    "level": "success", "badges": {...}, "data": {...}}
#
# Apprise URL examples:
#   pinglets://{apikey}@app.pinglet.co.uk/{namespace}/{topic}
#   pinglets://{apikey}@app.pinglet.co.uk/acme/deploys?priority=urgent
#   pinglets://{apikey}@my.host/acme/deploys?:CPU=95%25&+region=eu-west

from json import dumps

import requests

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import validate_regex
from .base import NotifyBase


# Priorities (delivery intrusiveness; separate from the display level)
class PingletPriority:
    SILENT = "silent"
    NORMAL = "normal"
    URGENT = "urgent"


PINGLET_PRIORITIES = (
    PingletPriority.SILENT,
    PingletPriority.NORMAL,
    PingletPriority.URGENT,
)

PINGLET_PRIORITY_MAP = {
    # Maps against string 'silent'
    "s": PingletPriority.SILENT,
    # Maps against string 'normal'
    "n": PingletPriority.NORMAL,
    # Maps against string 'urgent'
    "u": PingletPriority.URGENT,
}

# Maps the Apprise notification type to Pinglet's display-only level
PINGLET_LEVEL_MAP = {
    NotifyType.INFO.value: "info",
    NotifyType.SUCCESS.value: "success",
    NotifyType.WARNING.value: "warning",
    NotifyType.FAILURE.value: "error",
}


class NotifyPinglet(NotifyBase):
    """A wrapper for Pinglet Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Pinglet"

    # The services URL
    service_url = "https://pinglet.co.uk/"

    # The default protocol
    protocol = "pinglet"

    # The default secure protocol
    secure_protocol = "pinglets"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/pinglet/"

    # Pinglet API keys are limited to 120 requests/min
    request_rate_per_sec = 0.5

    # Pinglet rejects payloads larger then 4KB (title, message, badges,
    # metadata and envelope combined); leave head-room for everything
    # that is not the message body
    body_maxlen = 3000

    # Pinglet renders at most 3 badges (pills) per notification; keys and
    # values that exceed the below lengths are rejected by the server, so
    # they are truncated client-side instead
    max_badge_count = 3
    max_badge_key_len = 24
    max_badge_value_len = 32

    # Metadata (data) key/value length limits
    max_data_key_len = 64
    max_data_value_len = 256

    # Define object templates
    templates = (
        "{schema}://{token}@{host}/{namespace}/{topic}",
        "{schema}://{token}@{host}:{port}/{namespace}/{topic}",
        "{schema}://{token}@{host}{path}{namespace}/{topic}",
        "{schema}://{token}@{host}:{port}{path}{namespace}/{topic}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "token": {
                "name": _("API Key"),
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
            "namespace": {
                "name": _("Namespace"),
                "type": "string",
                "required": True,
            },
            "topic": {
                "name": _("Topic"),
                "type": "string",
                "required": True,
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "priority": {
                "name": _("Priority"),
                "type": "choice:string",
                "values": PINGLET_PRIORITIES,
                "default": PingletPriority.NORMAL,
            },
            "token": {
                "alias_of": "token",
            },
        },
    )

    # Define any kwargs we're using
    template_kwargs = {
        "badges": {
            "name": _("Badges"),
            "prefix": ":",
        },
        "data": {
            "name": _("Metadata"),
            "prefix": "+",
        },
    }

    def __init__(
        self,
        token,
        namespace,
        topic,
        priority=None,
        badges=None,
        data=None,
        **kwargs,
    ):
        """Initialize Pinglet Object."""
        super().__init__(**kwargs)

        # Our API Key
        self.token = validate_regex(token)
        if not self.token:
            msg = f"An invalid Pinglet API Key ({token}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # The Namespace the topic resides in
        self.namespace = validate_regex(namespace)
        if not self.namespace:
            msg = f"An invalid Pinglet Namespace ({namespace}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # The Topic to publish to (auto-created on first publish)
        self.topic = validate_regex(topic)
        if not self.topic:
            msg = f"An invalid Pinglet Topic ({topic}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # prepare our fullpath
        self.fullpath = kwargs.get("fullpath")
        if not isinstance(self.fullpath, str) or not self.fullpath:
            self.fullpath = "/"

        # The Priority of the message
        self.priority = (
            NotifyPinglet.template_args["priority"]["default"]
            if priority is None
            else next(
                (
                    v
                    for k, v in PINGLET_PRIORITY_MAP.items()
                    if str(priority).lower().startswith(k)
                ),
                NotifyPinglet.template_args["priority"]["default"],
            )
        )

        # Badges (pills rendered on the feed card); the server rejects
        # over-length keys/values outright, so truncate to keep the
        # notification deliverable
        self.badges = {}
        if badges:
            for key, value in badges.items():
                if len(self.badges) >= self.max_badge_count:
                    self.logger.warning(
                        "Pinglet renders at most %d badges; "
                        "additional entries were ignored.",
                        self.max_badge_count,
                    )
                    break

                if (
                    len(key) > self.max_badge_key_len
                    or len(str(value)) > self.max_badge_value_len
                ):
                    self.logger.warning("Pinglet badge %s was truncated.", key)

                self.badges[key[: self.max_badge_key_len]] = str(value)[
                    : self.max_badge_value_len
                ]

        # Metadata key/value pairs (shown on the detail sheet)
        self.data = {}
        if data:
            for key, value in data.items():
                if (
                    len(key) > self.max_data_key_len
                    or len(str(value)) > self.max_data_value_len
                ):
                    self.logger.warning(
                        "Pinglet metadata %s was truncated.", key
                    )

                self.data[key[: self.max_data_key_len]] = str(value)[
                    : self.max_data_value_len
                ]

        return

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform Pinglet Notification."""

        schema = "https" if self.secure else "http"
        url = f"{schema}://{self.host}"
        if self.port:
            url += f":{self.port}"

        # Append our namespace/topic path
        url += f"{self.fullpath}{self.namespace}/{self.topic}"

        # Prepare Pinglet Object
        payload = {
            "message": body,
            "priority": self.priority,
            "level": PINGLET_LEVEL_MAP.get(
                notify_type.value
                if isinstance(notify_type, NotifyType)
                else str(notify_type),
                "info",
            ),
        }

        if title:
            payload["title"] = title

        if self.badges:
            payload["badges"] = self.badges

        if self.data:
            payload["data"] = self.data

        # Our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }

        self.logger.debug(
            "Pinglet POST URL:"
            f" {url} (cert_verify={self.verify_certificate!r})"
        )
        self.logger.debug(f"Pinglet Payload: {payload!s}")

        # Always call throttle before the requests are made
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
            if r.status_code < 200 or r.status_code >= 300:
                # We had a problem
                status_str = NotifyPinglet.http_response_code_lookup(
                    r.status_code
                )

                self.logger.warning(
                    "Failed to send Pinglet notification: "
                    "{}{}error={}.".format(
                        status_str, ", " if status_str else "", r.status_code
                    )
                )

                self.logger.debug(
                    "Response Details:\r\n%r", (r.content or b"")[:2000]
                )

                # Mark our failure
                return False

            else:
                self.logger.info("Sent Pinglet notification.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending Pinglet "
                f"notification to {self.host}."
            )
            self.logger.debug(f"Socket Exception: {e!s}")

            # Mark our failure
            return False

        return True

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.token,
            self.host,
            self.port if self.port else (443 if self.secure else 80),
            self.fullpath.rstrip("/"),
            self.namespace,
            self.topic,
        )

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {
            "priority": self.priority,
        }

        # Append our badges into our parameters
        params.update({f":{k}": v for k, v in self.badges.items()})

        # Append our metadata into our parameters
        params.update({f"+{k}": v for k, v in self.data.items()})

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Our default port
        default_port = 443 if self.secure else 80
        return (
            "{schema}://{token}@{hostname}{port}{fullpath}"
            "{namespace}/{topic}/?{params}".format(
                schema=self.secure_protocol if self.secure else self.protocol,
                token=self.pprint(
                    self.token, privacy, mode=PrivacyMode.Secret, safe=""
                ),
                # never encode hostname since we're expecting it to be valid
                hostname=self.host,
                port=(
                    ""
                    if self.port is None or self.port == default_port
                    else f":{self.port}"
                ),
                fullpath=NotifyPinglet.quote(self.fullpath, safe="/"),
                namespace=NotifyPinglet.quote(self.namespace, safe=""),
                topic=NotifyPinglet.quote(self.topic, safe=""),
                params=NotifyPinglet.urlencode(params),
            )
        )

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url)
        if not results:
            # We're done early
            return results

        # Retrieve our escaped entries found on the fullpath
        entries = NotifyBase.split_path(results["fullpath"])

        # The last two entries are our namespace/topic
        try:
            results["topic"] = entries.pop()

        except IndexError:
            results["topic"] = None

        try:
            results["namespace"] = entries.pop()

        except IndexError:
            results["namespace"] = None

        # Re-assemble our full path (anything left is a path prefix such
        # as a reverse-proxy mount point)
        results["fullpath"] = (
            "/" if not entries else "/{}/".format("/".join(entries))
        )

        # Our API Key is the user component of the URL...
        results["token"] = (
            NotifyPinglet.unquote(results["user"]) if results["user"] else None
        )

        # ... but it can also be provided as ?token=
        if "token" in results["qsd"] and len(results["qsd"]["token"]):
            results["token"] = NotifyPinglet.unquote(results["qsd"]["token"])

        # Set our priority
        if "priority" in results["qsd"] and len(results["qsd"]["priority"]):
            results["priority"] = NotifyPinglet.unquote(
                results["qsd"]["priority"]
            )

        # Store our badges (:key=value)
        results["badges"] = {
            NotifyPinglet.unquote(x): NotifyPinglet.unquote(y)
            for x, y in results["qsd:"].items()
        }

        # Store our metadata (+key=value)
        results["data"] = {
            NotifyPinglet.unquote(x): NotifyPinglet.unquote(y)
            for x, y in results["qsd+"].items()
        }

        return results
