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

# YouLMK (https://youlmk.com) is a hosted notification inbox: anything with
# an HTTP client sends into it, and the receiver decides per sender (a
# "source") how far a message may reach, whether quiet hours hold it and how
# repeats group. A notification lands on the person's phone, in their
# browser, in email, in Slack or on a webhook they own.
#
# Every source has two credentials, shown on its Key screen. Either one works
# here:
#   - the bearer token, "ylk_" followed by 32 characters:
#       youlmk://ylk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
#   - the URL key, "k_" followed by 14 characters:
#       youlmk://k_xxxxxxxxxxxxxx
#
# The priority (low, normal, high, critical) is derived from the Apprise
# notification type unless forced with ?priority=, and each type's mapping
# can be changed (e.g. ?failure=critical). A primary button and a grouping
# key can be set with ?url= and ?group=.
#
# References:
# - https://youlmk.com/docs/http
# - https://youlmk.com/docs/payload

from json import dumps

import requests

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import validate_regex
from .base import NotifyBase

# Extend HTTP Error Messages with YouLMK's own codes
YOULMK_HTTP_ERROR_MAP = {
    401: "Unauthorized - Unknown key or token.",
    402: "Payment Required - The trial's 10 notifications are used.",
    410: "Gone - The key was rotated or the source deleted.",
    413: "Payload Too Large - The body is over 8 KB.",
    422: "Unprocessable - A field is over its limit.",
    429: "Too Many Requests - 60 a minute per key.",
    503: "Service Unavailable - Sending is paused.",
}

# The four priorities a sender may set. The receiver's Reach is the ceiling;
# a priority only moves down from it.
YOULMK_PRIORITIES = (
    "low",
    "normal",
    "high",
    "critical",
)

# The default priority for each Apprise notification type. Each can be
# changed from the URL (e.g. ?failure=critical). "critical" is never a
# default: it may break through quiet hours and Focus when the source allows
# it, so it is opted into.
YOULMK_DEFAULT_PRIORITIES = {
    NotifyType.INFO: "normal",
    NotifyType.SUCCESS: "normal",
    NotifyType.WARNING: "high",
    NotifyType.FAILURE: "high",
}


def youlmk_priority(value):
    """Resolve a full or short-form priority (e.g. 'crit', 'c') to one of
    YouLMK's four, or None when it matches none."""
    value = str(value).strip().lower()
    if not value:
        return None
    return next(
        (
            priority
            for priority in YOULMK_PRIORITIES
            if priority.startswith(value)
        ),
        None,
    )


class NotifyYouLMK(NotifyBase):
    """A wrapper for YouLMK Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "YouLMK"

    # The services URL
    service_url = "https://youlmk.com/"

    # The default secure protocol
    secure_protocol = "youlmk"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/youlmk/"

    # The bearer door (used with a token) and the key door (used with a key)
    notify_url = "https://youlmk.com/v1/notify"
    key_url = "https://youlmk.com/k/{key}"

    # The payload's own limits (https://youlmk.com/docs/payload)
    title_maxlen = 120
    body_maxlen = 2000

    # 60 a minute per key, in bursts of up to 10 a second
    request_rate_per_sec = 1.0

    # An attachment has no place in the payload; an image is a URL the
    # sender already hosts, so file attachments are not wired in
    attachment_support = False

    # Define object URL templates
    templates = ("{schema}://{token}",)

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "token": {
                "name": _("Token or Key"),
                "type": "string",
                "private": True,
                "required": True,
                "regex": (r"^(ylk_[a-z0-9]{32}|k_[a-z0-9]{14})$", "i"),
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "token": {
                "alias_of": "token",
            },
            # Force the priority for every notification regardless of type
            "priority": {
                "name": _("Priority"),
                "type": "choice:string",
                "values": YOULMK_PRIORITIES,
            },
            # Per-type priority overrides; default to YOULMK_DEFAULT_PRIORITIES
            "info": {
                "name": _("Info Priority"),
                "type": "choice:string",
                "values": YOULMK_PRIORITIES,
                "default": YOULMK_DEFAULT_PRIORITIES[NotifyType.INFO],
            },
            "success": {
                "name": _("Success Priority"),
                "type": "choice:string",
                "values": YOULMK_PRIORITIES,
                "default": YOULMK_DEFAULT_PRIORITIES[NotifyType.SUCCESS],
            },
            "warning": {
                "name": _("Warning Priority"),
                "type": "choice:string",
                "values": YOULMK_PRIORITIES,
                "default": YOULMK_DEFAULT_PRIORITIES[NotifyType.WARNING],
            },
            "failure": {
                "name": _("Failure Priority"),
                "type": "choice:string",
                "values": YOULMK_PRIORITIES,
                "default": YOULMK_DEFAULT_PRIORITIES[NotifyType.FAILURE],
            },
            # The primary button's address on every notification. Kept
            # apart from the "url" the parser fills with the Apprise URL
            # itself, hence the map to "link"
            "url": {
                "name": _("Link"),
                "type": "string",
                "map_to": "link",
            },
            # Notifications with the same group within ten minutes become
            # one card with a count; the default is the title
            "group": {
                "name": _("Group"),
                "type": "string",
            },
        },
    )

    def __init__(
        self,
        token,
        priority=None,
        info=None,
        success=None,
        warning=None,
        failure=None,
        link=None,
        group=None,
        **kwargs,
    ):
        """Initialize YouLMK Object."""
        super().__init__(**kwargs)

        # Validate the token or key (ylk_ or k_ prefix)
        self.token = validate_regex(
            token, *self.template_tokens["token"]["regex"]
        )
        if not self.token:
            msg = f"An invalid YouLMK token or key ({token}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # An explicit priority forces every notification to it
        self.priority = None
        if priority:
            self.priority = youlmk_priority(priority)
            if self.priority is None:
                msg = f"An invalid YouLMK priority ({priority}) was specified."
                self.logger.warning(msg)
                raise TypeError(msg)

        # Per-notification-type priority mapping; each type may be overridden
        # from the URL, otherwise it falls back to the default
        self.priority_map = {}
        for ntype, value in (
            (NotifyType.INFO, info),
            (NotifyType.SUCCESS, success),
            (NotifyType.WARNING, warning),
            (NotifyType.FAILURE, failure),
        ):
            if not value:
                self.priority_map[ntype] = YOULMK_DEFAULT_PRIORITIES[ntype]
                continue

            resolved = youlmk_priority(value)
            if resolved is None:
                msg = f"An invalid YouLMK priority ({value}) was specified."
                self.logger.warning(msg)
                raise TypeError(msg)
            self.priority_map[ntype] = resolved

        # The primary button's address, if any
        self.link = link if link else None

        # The grouping key, if any
        self.group = group if group else None

        return

    @property
    def is_token(self):
        """True when the credential is the bearer token, False for the URL
        key."""
        return self.token.lower().startswith("ylk_")

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform YouLMK Notification."""

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json; charset=utf-8",
        }

        # The bearer token goes in the header and the request to the /v1
        # door; the URL key goes in the address of the /k door
        if self.is_token:
            url = self.notify_url
            headers["Authorization"] = f"Bearer {self.token}"

        else:
            url = self.key_url.format(key=self.token)

        # Resolve the priority: an explicit override wins, otherwise the
        # per-notification-type mapping applies
        priority = (
            self.priority if self.priority else self.priority_map[notify_type]
        )

        # A title is required by the door; when Apprise has none, the
        # application descriptor stands in
        title = title if title else self.app_desc
        if not title:
            title = self.app_id

        # Prepare our payload
        payload = {
            "title": title,
            "body": body,
            "priority": priority,
        }

        if self.link:
            payload["url"] = self.link

        if self.group:
            payload["group"] = self.group

        self.logger.debug(
            "YouLMK POST URL: %s (cert_verify=%s)",
            url,
            self.verify_certificate,
        )
        self.logger.debug("YouLMK Payload: %s", str(payload))

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

            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = NotifyYouLMK.http_response_code_lookup(
                    r.status_code, YOULMK_HTTP_ERROR_MAP
                )

                self.logger.warning(
                    "Failed to send YouLMK notification: {}{}error={}.".format(
                        status_str,
                        ", " if status_str else "",
                        r.status_code,
                    )
                )

                self.logger.debug(
                    "Response Details:\r\n%r", (r.content or b"")[:2000]
                )

                # Return; we're done
                return False

            else:
                self.logger.info("Sent YouLMK notification.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred posting to YouLMK."
            )
            self.logger.debug("Socket Exception: %s", str(e))
            return False

        return True

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (
            self.secure_protocol,
            self.token,
        )

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {}
        if self.priority:
            params["priority"] = self.priority

        # Include any per-type priority that differs from the default
        for ntype, key in (
            (NotifyType.INFO, "info"),
            (NotifyType.SUCCESS, "success"),
            (NotifyType.WARNING, "warning"),
            (NotifyType.FAILURE, "failure"),
        ):
            if self.priority_map[ntype] != YOULMK_DEFAULT_PRIORITIES[ntype]:
                params[key] = self.priority_map[ntype]

        if self.link:
            params["url"] = self.link

        if self.group:
            params["group"] = self.group

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return "{schema}://{token}/?{params}".format(
            schema=self.secure_protocol,
            token=self.pprint(self.token, privacy, safe=""),
            params=NotifyYouLMK.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # The token or key is in the host position (case is preserved
        # because verify_host=False skips hostname normalization)
        results["token"] = NotifyYouLMK.unquote(results["host"])

        # Allow ?token= to override the host-supplied credential
        if "token" in results["qsd"] and results["qsd"]["token"]:
            results["token"] = NotifyYouLMK.unquote(results["qsd"]["token"])

        # Allow the priority to be forced for every notification type
        if "priority" in results["qsd"] and results["qsd"]["priority"]:
            results["priority"] = NotifyYouLMK.unquote(
                results["qsd"]["priority"]
            )

        # Allow per-notification-type priority overrides
        for key in ("info", "success", "warning", "failure"):
            if key in results["qsd"] and results["qsd"][key]:
                results[key] = NotifyYouLMK.unquote(results["qsd"][key])

        # The primary button's address; "url" in the results is the Apprise
        # URL itself, so the link is stored under its own name
        if "url" in results["qsd"] and results["qsd"]["url"]:
            results["link"] = NotifyYouLMK.unquote(results["qsd"]["url"])

        # The grouping key
        if "group" in results["qsd"] and results["qsd"]["group"]:
            results["group"] = NotifyYouLMK.unquote(results["qsd"]["group"])

        return results
