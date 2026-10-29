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

# To use this service you will need a Gupshup account:
#     https://www.gupshup.io/
#
#  1. Sign in to the Gupshup console and create a WhatsApp app.  The
#     name you give it is your App Name (e.g. DemoAPI).
#  2. Copy the API Key shown in the top right corner of the console.
#  3. Note the WhatsApp Business phone number linked to your app.  While
#     testing in the sandbox this is Gupshup's number, 917834811114.
#
#  Your Apprise URL should be assembled as:
#     gupshup://{app}:{apikey}@{source}/{to_phone}
#     gupshup://{app}:{apikey}@{source}/{to_phone}/{to_phone}
#
#  WhatsApp only delivers free-form text to someone who messaged your
#  number within the last 24 hours.  Outside of that window an approved
#  template is needed; pick one with ?template={template_id} and fill
#  its placeholders with :1=value, :body=1 (the message body) or
#  :type=2 (the notification type).
#
#  Gupshup's API key interface only accepts media that is already hosted
#  at a public URL.  Uploading a file needs the separate Partner API, so
#  attachments are not supported.
#
# Resources:
# - https://docs.gupshup.io/reference/msg
# - https://docs.gupshup.io/docs/session-messages
# - https://docs.gupshup.io/docs/template-messages

from __future__ import annotations

from json import dumps, loads
import re
from typing import Any, Optional

import requests

from ..common import NotifyType
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..utils.parse import is_phone_no, parse_phone_no, validate_regex
from .base import NotifyBase

# Extend HTTP Error Messages
GUPSHUP_HTTP_ERROR_MAP = {
    400: "Bad Request - Check the phone numbers and message.",
    401: "Unauthorized - Invalid API Key.",
    429: "Too many requests were made.",
}

# A template placeholder key; a position number or what to fill in
IS_TEMPLATE_KEY = re.compile(
    r"^\s*((?P<index>[1-9][0-9]*)|(?P<map>body|type))\s*$", re.I
)


class NotifyGupshup(NotifyBase):
    """A wrapper for Gupshup WhatsApp Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Gupshup"

    # The services URL
    service_url = "https://www.gupshup.io/"

    # The default secure protocol
    secure_protocol = "gupshup"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/gupshup/"

    # Free-form WhatsApp message URL
    notify_url = "https://api.gupshup.io/wa/api/v1/msg"

    # Approved WhatsApp template message URL
    template_url = "https://api.gupshup.io/wa/api/v1/template/msg"

    # The maximum length of a WhatsApp text message
    body_maxlen = 4096

    # WhatsApp messages have no title field.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Define object URL templates
    templates = ("{schema}://{app}:{apikey}@{source}/{targets}",)

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "app": {
                "name": _("App Name"),
                "type": "string",
                "required": True,
            },
            "apikey": {
                "name": _("API Key"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "source": {
                "name": _("Source Phone No"),
                "type": "string",
                "prefix": "+",
                "required": True,
                "regex": (r"^[0-9\s)(+-]+$", "i"),
            },
            "target_phone": {
                "name": _("Target Phone No"),
                "type": "string",
                "prefix": "+",
                "regex": (r"^[0-9\s)(+-]+$", "i"),
                "map_to": "targets",
            },
            "targets": {
                "name": _("Targets"),
                "type": "list:string",
                "required": True,
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "app": {
                "alias_of": "app",
            },
            "key": {
                "alias_of": "apikey",
            },
            "from": {
                "alias_of": "source",
            },
            "source": {
                "alias_of": "source",
            },
            "template": {
                "name": _("Template ID"),
                "type": "string",
            },
            "to": {
                "alias_of": "targets",
            },
        },
    )

    # Define any kwargs we're using
    template_kwargs = {
        "template_mapping": {
            "name": _("Template Mapping"),
            "prefix": ":",
        },
    }

    def __init__(
        self,
        app: Optional[str] = None,
        apikey: Optional[str] = None,
        source: Optional[str] = None,
        targets: Optional[Any] = None,
        template: Optional[str] = None,
        template_mapping: Optional[dict[str, str]] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Gupshup Object."""
        super().__init__(**kwargs)

        # Our App Name
        self.app = validate_regex(app)
        if not self.app:
            msg = "A Gupshup App Name must be specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Our API Key
        self.apikey = validate_regex(apikey)
        if not self.apikey:
            msg = "A Gupshup API Key must be specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # The WhatsApp Business number we send from
        result = is_phone_no(source)
        if not result:
            msg = (
                f"An invalid Gupshup Source Phone No ({source}) was specified."
            )
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Gupshup wants the digits only
        self.source = result["full"]

        # An approved template is optional
        self.template = None
        if template:
            self.template = validate_regex(template)
            if not self.template:
                msg = (
                    "An invalid Gupshup Template ID "
                    f"({template}) was specified."
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

        # The template placeholders exactly as the user gave them
        self.template_mapping = {}

        # Each placeholder position and what fills it.  A plain string is
        # sent as-is, while "body" and "type" are filled in at send time.
        self.template_params = {}

        for key, value in (template_mapping or {}).items():
            matched = IS_TEMPLATE_KEY.match(key)
            if not matched:
                msg = (
                    "An invalid Gupshup template placeholder "
                    f"(:{key}) was specified."
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

            if matched.group("index"):
                # A fixed value placed at the position given
                index = int(matched.group("index"))
                fill = ("text", value)

            else:
                # The body or type placed at the position given as value
                position = IS_TEMPLATE_KEY.match(value)
                if not (position and position.group("index")):
                    msg = (
                        "An invalid Gupshup template placeholder "
                        f"(:{key}={value}) was specified."
                    )
                    self.logger.warning(msg)
                    raise AppriseImproperlyConfigured(msg)

                index = int(position.group("index"))
                fill = (matched.group("map").lower(), None)

            if index in self.template_params:
                msg = (
                    "The Gupshup template placeholder "
                    f"({index}) was assigned more than once."
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

            self.template_params[index] = fill
            self.template_mapping[key] = value

        # The phone numbers we will notify
        self.targets = []

        # Anything we could not make sense of; kept for url()
        self.invalid_targets = []

        for target in parse_phone_no(targets):
            # Parse each phone number we found
            result = is_phone_no(target)
            if result:
                self.targets.append(result["full"])
                continue

            self.logger.warning(
                "Dropped invalid Gupshup phone # (%s) specified.", target
            )
            self.invalid_targets.append(target)

        return

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        **kwargs: Any,
    ) -> bool:
        """Perform Gupshup Notification."""

        if not self.targets:
            # We have nothing to notify
            self.logger.warning("There are no Gupshup targets to notify.")
            return False

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Accept": "application/json",
            "apikey": self.apikey,
        }

        # Prepare our payload; the phone number is filled in below
        payload = {
            "source": self.source,
            "src.name": self.app,
            "destination": None,
        }

        if self.template:
            # What the "body" and "type" placeholders are filled with
            fills = {"body": body, "type": notify_type.value}

            # Fill each placeholder in position order
            params = [
                fills.get(kind, value)
                for _index, (kind, value) in sorted(
                    self.template_params.items()
                )
            ]

            # Send an approved template
            url = self.template_url
            payload["template"] = dumps(
                {"id": self.template, "params": params}
            )

        else:
            # Send a free-form text message
            url = self.notify_url
            payload["channel"] = "whatsapp"
            payload["message"] = dumps({"type": "text", "text": body})

        # error tracking (used for function return)
        has_error = False

        for target in self.targets:
            # Skip a target that already accepted this message so a retry
            # does not deliver it twice.
            if self.is_delivered(target):
                continue

            # Address this copy of our message
            payload["destination"] = target

            self.logger.debug(
                "Gupshup POST URL: %s (cert_verify=%r)",
                url,
                self.verify_certificate,
            )
            self.logger.debug("Gupshup Payload: %s", payload)

            # Always call throttle before any remote server i/o is made
            self.throttle()

            try:
                r = requests.post(
                    url,
                    data=payload,
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                    allow_redirects=self.redirects,
                )

                try:
                    content = loads(r.content)

                except (AttributeError, TypeError, ValueError):
                    # The response was not JSON; rely on the status code
                    content = {}

                # A successful response looks like:
                # {"status": "submitted", "messageId": "ee4a68a0-..."}
                #
                # An error response looks like:
                # {"status": "error", "message": "Authentication Failed"}
                if not isinstance(content, dict):
                    content = {}

                if (
                    not 200 <= r.status_code < 300
                    or content.get("status") == "error"
                ):
                    # Prefer Gupshup's own explanation when it gave one
                    status_str = content.get(
                        "message"
                    ) or NotifyGupshup.http_response_code_lookup(
                        r.status_code, GUPSHUP_HTTP_ERROR_MAP
                    )

                    self.logger.warning(
                        "Failed to send Gupshup notification to %s: "
                        "%s%serror=%s.",
                        target,
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

                self.logger.info("Sent Gupshup notification to %s.", target)

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending Gupshup "
                    "notification to %s.",
                    target,
                )
                self.logger.debug("Socket Exception: %s", str(e))

                # Mark our failure
                has_error = True
                continue

            # Delivered; a retry can safely skip this target.
            self.mark_delivered(target)

        return not has_error

    def __len__(self) -> int:
        """Returns the number of targets associated with this notification."""
        # Always return at least 1 so the framework counts this instance
        return len(self.targets) if self.targets else 1

    @property
    def url_identifier(self) -> tuple[Any, ...]:
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        # The app, its API Key and its sending number identify the account
        return (self.secure_protocol, self.app, self.apikey, self.source)

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # Our URL parameters
        params = {}

        if self.template:
            params["template"] = self.template

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Template placeholders are prefixed with a ':' sign
        params.update({f":{k}": v for k, v in self.template_mapping.items()})

        return "{schema}://{app}:{apikey}@{source}/{targets}?{params}".format(
            schema=self.secure_protocol,
            app=NotifyGupshup.quote(self.app, safe=""),
            apikey=self.pprint(self.apikey, privacy, safe=""),
            source=self.source,
            targets="/".join(
                NotifyGupshup.quote(x, safe="+")
                for x in (self.targets + self.invalid_targets)
            ),
            params=NotifyGupshup.urlencode(params),
        )

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Our App Name and API Key
        results["app"] = NotifyGupshup.unquote(results["user"])
        results["apikey"] = NotifyGupshup.unquote(results["password"])

        # The host is the number we send from
        results["source"] = NotifyGupshup.unquote(results["host"])

        # Our phone numbers are in the path
        results["targets"] = NotifyGupshup.split_path(results["fullpath"])

        # Allow the App Name to be given as ?app= instead
        if results["qsd"].get("app"):
            results["app"] = NotifyGupshup.unquote(results["qsd"]["app"])

        # Allow the API Key to be given as ?key= instead
        if results["qsd"].get("key"):
            results["apikey"] = NotifyGupshup.unquote(results["qsd"]["key"])

        # Support ?from= and ?source= for the sending number
        if results["qsd"].get("from"):
            results["source"] = NotifyGupshup.unquote(results["qsd"]["from"])

        if results["qsd"].get("source"):
            results["source"] = NotifyGupshup.unquote(results["qsd"]["source"])

        # Support ?template= for an approved template
        if results["qsd"].get("template"):
            results["template"] = NotifyGupshup.unquote(
                results["qsd"]["template"]
            )

        # Support ?to= for targets
        if results["qsd"].get("to"):
            results["targets"] += NotifyGupshup.parse_phone_no(
                results["qsd"]["to"]
            )

        # Store our template placeholders
        results["template_mapping"] = {
            NotifyGupshup.unquote(x): NotifyGupshup.unquote(y)
            for x, y in results["qsd:"].items()
        }

        return results
