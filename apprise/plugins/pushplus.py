#
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

# PushPlus is a Chinese notification platform that delivers messages via
# WeChat and several other channels.  You can find its API documentation at:
#   https://www.pushplus.plus/doc/guide/api.html
#
# To obtain your personal token:
#   1. Register or sign in at https://www.pushplus.plus/
#   2. Copy the token shown on the dashboard under the "Push" section.
#
# Group (topic) sending is also supported.  After creating a group under
# "Group Push" in the PushPlus console, use the group code as the topic:
#   https://www.pushplus.plus/doc/guide/group.html
#
# Basic Apprise URL forms:
#
#   Personal notification (WeChat default):
#     pushplus://{token}
#
#   Group topic -- one notification per topic:
#     pushplus://{token}/{topic}
#     pushplus://{token}/{topic1}/{topic2}
#
#   Select a delivery channel (mode= and channel= are synonyms):
#     pushplus://{token}?channel=mail
#     pushplus://{token}?mode=cp
#
#   Topic + delivery channel:
#     pushplus://{token}/{topic}?channel=mail
#
#   Webhook channel with a named endpoint -- two equivalent forms:
#     pushplus://{token}?channel=webhook&name={webhook_name}
#     pushplus://{webhook_name}@{token}
#
#   When the schema://{name}@{token} form is used and no explicit channel=
#   is given, the webhook channel is implied automatically.
#
#   Native PushPlus API URL (also accepted by parse_native_url):
#     https://www.pushplus.plus/send?token={token}
#
# Schema alias for WeCom users:
#   wecom://{token}    -- identical to pushplus://{token}?channel=cp
#
# For direct WeCom Application API notifications (without PushPlus as
# intermediary), use the wechat:// plugin instead.
#
# API References:
#   https://www.pushplus.plus/doc/guide/api.html
#   https://www.pushplus.plus/doc/guide/group.html

import json
import re

import requests

from ..common import NotifyFormat, NotifyType
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import parse_list, validate_regex
from .base import NotifyBase

# PushPlus application-level response codes.
# The HTTP status is always 200; the real result lives in the JSON body.
# Reference: https://www.pushplus.plus/doc/guide/api.html
PUSHPLUS_RESPONSE_CODES = {
    200: "Request succeeded.",
    900: "System exception.",
    903: "Sending failed.",
    905: "Request parameter error.",
    907: "Token does not exist.",
    908: "User is blocked.",
    909: "Content requires review before sending.",
    912: "No available service package.",
}

# Map Apprise's standard notify_format values to the PushPlus template
# identifiers.  PushPlus uses these to render the body server-side before
# delivery -- the content itself does not change; only the rendering hint.
PUSHPLUS_FORMAT_MAP = {
    NotifyFormat.HTML: "html",
    NotifyFormat.MARKDOWN: "markdown",
    NotifyFormat.TEXT: "txt",
}

# Default PushPlus template when the format has no explicit mapping
PUSHPLUS_FORMAT_DEFAULT = "html"


class PushPlusChannel:
    """Defines the PushPlus delivery channels.

    The channel controls where the rendered notification is delivered.
    It is supplied as the channel= (or mode=) query parameter in the
    Apprise URL, e.g. pushplus://{token}?channel=mail.
    """

    # Deliver via WeChat (PushPlus default)
    WECHAT = "wechat"

    # Deliver via a configured webhook endpoint
    WEBHOOK = "webhook"

    # Deliver via WeCom (WeChat Work / Enterprise WeChat).
    # The API value "cp" is PushPlus's internal identifier for this channel.
    # Both "cp" and the friendly alias "wecom" are accepted; both resolve here.
    WECOM = "cp"

    # Deliver via email
    MAIL = "mail"

    # Deliver via SMS
    SMS = "sms"


# All valid PushPlus delivery channels (these are the API values)
PUSHPLUS_CHANNELS = (
    PushPlusChannel.WECHAT,
    PushPlusChannel.WEBHOOK,
    PushPlusChannel.WECOM,
    PushPlusChannel.MAIL,
    PushPlusChannel.SMS,
)

# The PushPlus default delivery channel (WeChat)
PUSHPLUS_CHANNEL_DEFAULT = PushPlusChannel.WECHAT

# A group topic has no special prefix; alphanumeric codes up to 50 chars.
IS_TOPIC = re.compile(
    r"^(?P<topic>[a-z0-9_-]{1,50})$",
    re.I,
)

# Schema names that auto-select a specific delivery channel when used
# in place of the default "pushplus" schema.  Mirrors the Kodi/XBMC pattern.
# wechat:// belongs to the separate direct WeCom Application API plugin.
PUSHPLUS_SCHEMA_MAP = {
    # wecom:// forces channel=cp (WeCom / Enterprise WeChat)
    "wecom": PushPlusChannel.WECOM,
}


class NotifyPushplus(NotifyBase):
    """A wrapper for PushPlus Notifications."""

    # The default descriptive name associated with the Notification
    service_name = _("Pushplus")

    # The services URL
    service_url = "https://www.pushplus.plus/"

    # The default protocol; wecom:// is accepted as a schema alias.
    # wechat:// belongs to the direct WeCom Application API plugin and
    # is intentionally not listed here.
    secure_protocol = ("pushplus", "wecom")

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/pushplus/"

    # URL used to POST notifications
    notify_url = "https://www.pushplus.plus/send"

    # Maximum body length documented by PushPlus
    body_maxlen = 20000

    # Title is capped at a safe limit (not explicitly documented by PushPlus)
    title_maxlen = 200

    # Default to HTML since PushPlus renders HTML by default
    notify_format = NotifyFormat.HTML

    # Define object URL templates
    templates = (
        # No topics: personal notification with optional ?channel= override
        "{schema}://{token}",
        # Topics in path: one API call per topic
        "{schema}://{token}/{targets}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "token": {
                "name": _("User Token"),
                "type": "string",
                "private": True,
                "required": True,
                # PushPlus tokens are 32-64 alphanumeric/underscore/dash chars
                "regex": (r"^[a-z0-9_-]{32,64}$", "i"),
            },
            # Group topics go directly in the URL path with no prefix
            "targets": {
                "name": _("Group Topics"),
                "type": "list:string",
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            # Allow the token to be supplied as a query parameter
            "token": {
                "alias_of": "token",
            },
            # ?to= is the standard Apprise alias for targets (topics)
            "to": {
                "alias_of": "targets",
            },
            # Delivery channel -- selects where the message is delivered.
            # One of the PUSHPLUS_CHANNELS values (wechat is the default).
            "channel": {
                "name": _("Channel"),
                "type": "choice:string",
                "values": PUSHPLUS_CHANNELS,
                "default": PUSHPLUS_CHANNEL_DEFAULT,
            },
            # mode= is an alias for channel=; the two are fully synonymous.
            "mode": {
                "alias_of": "channel",
            },
            # ?topic= backward-compat alias that maps to targets
            "topic": {
                "alias_of": "targets",
            },
            # Webhook endpoint name; only meaningful when channel=webhook.
            # The URL parameter is ?name= but the __init__ kwarg is webhook=
            # to avoid shadowing URLBase.name.
            "name": {
                "name": _("Webhook Name"),
                "type": "string",
                "map_to": "webhook",
            },
        },
    )

    def __init__(
        self, token, targets=None, channel=None, webhook=None, **kwargs
    ):
        """Initialize Pushplus Object."""
        super().__init__(**kwargs)

        # Validate the required user token
        self.token = validate_regex(
            token,
            *self.template_tokens["token"]["regex"],
        )
        if not self.token:
            msg = "The Pushplus token ({}) is invalid.".format(token)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Resolve the delivery channel from the schema alias when the URL
        # was entered as wechat:// or wecom:// instead of pushplus://.
        # self.schema is set by NotifyBase from the parsed URL protocol.
        schema_channel = PUSHPLUS_SCHEMA_MAP.get((self.schema or "").lower())

        # Determine the active delivery channel:
        #   1. Explicit channel= / mode= argument (already resolved by
        #      the caller since mode is an alias_of channel in template_args)
        #   2. Schema-implied channel (wechat:// or wecom://)
        #   3. Default (WeChat)
        if channel:
            # Normalise the 'wecom' friendly alias to the API value 'cp'
            if channel.lower() == "wecom":
                channel = PushPlusChannel.WECOM
            self.channel = next(
                (c for c in PUSHPLUS_CHANNELS if c == channel.lower()),
                None,
            )
            if not self.channel:
                msg = "The Pushplus channel ({}) is not valid.".format(channel)
                self.logger.warning(msg)
                raise TypeError(msg)

        elif schema_channel:
            # Schema-implied channel (wechat:// or wecom://)
            self.channel = schema_channel

        else:
            # Default to WeChat
            self.channel = PUSHPLUS_CHANNEL_DEFAULT

        # Resolved group topics -- one API call is made per topic
        self.topics = []

        # Preserve unrecognised targets for round-trip fidelity in url()
        self.invalid_targets = []

        # Parse each target from the list -- only plain topics are valid here
        for target in parse_list(targets):
            result = IS_TOPIC.match(target)
            if result:
                self.topics.append(result.group("topic"))
                continue

            # Unrecognised entry -- log and preserve
            self.logger.warning("Dropped invalid Pushplus topic: %s", target)
            self.invalid_targets.append(target)

        # Store the webhook name; only meaningful when channel=webhook.
        # Kept as self.webhook (not self.name) to avoid shadowing URLBase.name.
        # Arrives via the ?name= URL parameter (mapped to webhook= by map_to).
        self.webhook = (
            webhook if isinstance(webhook, str) and webhook else None
        )

        return

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform PushPlus Notification."""

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
        }

        # Derive the PushPlus rendering template from Apprise's standard
        # notify_format.  This is a server-side rendering hint only; the
        # content payload does not change.
        pp_template = PUSHPLUS_FORMAT_MAP.get(
            self.notify_format, PUSHPLUS_FORMAT_DEFAULT
        )

        # When no topics are configured, fall back to a single personal send
        # by iterating over a list containing None as the sole entry.
        topics_to_notify = self.topics if self.topics else [None]

        # Track whether any individual send failed
        has_error = False

        for topic in topics_to_notify:
            # Build the payload for this particular topic
            payload = {
                # Authentication token
                "token": self.token,
                # Fall back to the body when no title is provided
                "title": title if title else body,
                # Notification body content
                "content": body,
                # Rendering template derived from notify_format
                "template": pp_template,
                # Delivery channel
                "channel": self.channel,
            }

            # Add the group topic when sending to a specific group
            if topic:
                payload["topic"] = topic

            # Add the webhook name when the webhook channel is selected
            if self.channel == PushPlusChannel.WEBHOOK and self.webhook:
                payload["webhook"] = self.webhook

            # Debug logging so the caller can inspect what will be sent
            self.logger.debug(
                "PushPlus POST URL: %s (cert_verify=%r)",
                self.notify_url,
                self.verify_certificate,
            )
            self.logger.debug("PushPlus Payload: %r", payload)

            # Always throttle before each remote server I/O call
            self.throttle()

            try:
                r = requests.post(
                    self.notify_url,
                    headers=headers,
                    # Encode explicitly for non-ASCII (e.g. Chinese) chars
                    data=json.dumps(payload, ensure_ascii=False).encode(
                        "utf-8"
                    ),
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )

                if r.status_code != requests.codes.ok:
                    # HTTP-level failure -- log it and move on
                    status_str = NotifyPushplus.http_response_code_lookup(
                        r.status_code
                    )
                    self.logger.warning(
                        "Failed to send PushPlus notification: "
                        "{}{}error={}.".format(
                            status_str,
                            ", " if status_str else "",
                            r.status_code,
                        )
                    )
                    self.logger.debug(
                        "Response Details:\r\n%r",
                        (r.content or b"")[:2000],
                    )
                    # Mark our failure and continue with the next topic
                    has_error = True
                    continue

                # PushPlus always returns HTTP 200; the real result is in
                # the JSON body where code == 200 means success.
                try:
                    content = json.loads(r.content)
                except (AttributeError, TypeError, ValueError):
                    # ValueError = r.content is unparsable
                    # TypeError  = r.content is None
                    # AttributeError = r is None
                    content = {}

                # Check the application-level status code
                api_code = content.get("code") if content else None
                if api_code != 200:
                    # Application-level failure
                    error_str = PUSHPLUS_RESPONSE_CODES.get(
                        api_code,
                        # Fall back to the msg field, then a generic string
                        (
                            content.get("msg", "Unknown error")
                            if content
                            else "Unknown error"
                        ),
                    )
                    self.logger.warning(
                        "Failed to send PushPlus notification: "
                        "code={}: {}.".format(api_code, error_str)
                    )
                    self.logger.debug(
                        "Response Details:\r\n%r",
                        content if content else (r.content or b"")[:2000],
                    )
                    # Mark our failure and continue with the next topic
                    has_error = True
                    continue

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending"
                    " PushPlus notification."
                )
                self.logger.debug("Socket Exception: %s", str(e))
                # Mark our failure and continue with the next topic
                has_error = True
                continue

            # Notification delivered for this topic
            self.logger.info(
                "Sent PushPlus notification%s.",
                " to topic {}".format(topic) if topic else "",
            )

        return not has_error

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another similar one.

        Targets or end points should never be identified here.
        """
        # The token is the sole connection identity for PushPlus
        return (self.secure_protocol[0], self.token)

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # When channel=webhook with a named endpoint, use the compact
        # {name}@pushplus://{token} form.  Both ?channel=webhook and ?name=
        # are implied by the user@ prefix and omitted from the query string.
        webhook_prefix = (
            self.channel == PushPlusChannel.WEBHOOK and self.webhook
        )

        # Start with an empty params dict
        params = {}

        # When not using the webhook prefix form, include ?channel= when it
        # differs from the default.  The schema alias (wechat:// / wecom://)
        # is never emitted here -- we always normalise back to pushplus://
        # plus ?channel= for clarity.
        if not webhook_prefix and self.channel != PUSHPLUS_CHANNEL_DEFAULT:
            params["channel"] = self.channel

        # Merge in standard Apprise URL parameters (verify, format, etc.)
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Build the targets path from group topics and any invalid entries
        targets = list(self.topics) + list(self.invalid_targets)

        # Masked token for the URL
        token_str = self.pprint(
            self.token,
            privacy,
            mode=PrivacyMode.Secret,
            safe="",
        )

        # When using the webhook prefix form, the endpoint name goes in the
        # user@ position (schema://name@token) -- channel=webhook and ?name=
        # are both implied by the user@ presence and omitted from params.
        if webhook_prefix:
            name_str = NotifyPushplus.quote(self.webhook, safe="")
            if targets:
                return "{schema}://{name}@{token}/{targets}/?{params}".format(
                    schema=self.secure_protocol[0],
                    name=name_str,
                    token=token_str,
                    targets="/".join(
                        NotifyPushplus.quote(t, safe="") for t in targets
                    ),
                    params=NotifyPushplus.urlencode(params),
                )
            return "{schema}://{name}@{token}/?{params}".format(
                schema=self.secure_protocol[0],
                name=name_str,
                token=token_str,
                params=NotifyPushplus.urlencode(params),
            )

        if targets:
            # One or more topics: include them in the URL path
            return "{schema}://{token}/{targets}/?{params}".format(
                schema=self.secure_protocol[0],
                token=token_str,
                targets="/".join(
                    NotifyPushplus.quote(t, safe="") for t in targets
                ),
                params=NotifyPushplus.urlencode(params),
            )

        # No topics -- simple personal notification URL
        return "{schema}://{token}/?{params}".format(
            schema=self.secure_protocol[0],
            token=token_str,
            params=NotifyPushplus.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to
        re-instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Prefer ?token= query parameter over the URL host field
        if "token" in results["qsd"] and results["qsd"]["token"]:
            # Token was supplied as a query parameter
            results["token"] = NotifyPushplus.unquote(results["qsd"]["token"])
        else:
            # Token is the URL host
            results["token"] = NotifyPushplus.unquote(results["host"])

        # Collect group topics from the URL path
        results["targets"] = NotifyPushplus.split_path(results["fullpath"])

        # ?to= appends additional targets (comma/space delimited supported)
        if "to" in results["qsd"] and results["qsd"]["to"]:
            results["targets"] += NotifyPushplus.parse_list(
                results["qsd"]["to"]
            )

        # ?topic= backward-compat alias also appends topics
        if "topic" in results["qsd"] and results["qsd"]["topic"]:
            results["targets"] += NotifyPushplus.parse_list(
                results["qsd"]["topic"]
            )

        # Extract the delivery channel from ?channel= or its alias ?mode=
        # mode= takes lower priority; channel= wins if both are present.
        if "mode" in results["qsd"] and results["qsd"]["mode"]:
            results["channel"] = NotifyPushplus.unquote(results["qsd"]["mode"])
        if "channel" in results["qsd"] and results["qsd"]["channel"]:
            results["channel"] = NotifyPushplus.unquote(
                results["qsd"]["channel"]
            )

        # Extract the webhook name -- users specify it as ?name= in the URL.
        # We store it internally as 'webhook' to avoid shadowing URLBase.name.
        if "name" in results["qsd"] and results["qsd"]["name"]:
            results["webhook"] = NotifyPushplus.unquote(results["qsd"]["name"])

        # Support the {webhook_name}@pushplus://{token} short form.
        # When user@ is present, it identifies the webhook endpoint name.
        # If no channel was explicitly given, webhook is the implied channel.
        if results.get("user"):
            # Use user@ as the webhook name when ?name= was not also supplied
            if "webhook" not in results:
                results["webhook"] = NotifyPushplus.unquote(results["user"])
            # Imply webhook channel when no explicit channel was specified
            if "channel" not in results:
                results["channel"] = PushPlusChannel.WEBHOOK

        return results

    @staticmethod
    def parse_native_url(url):
        """Support native PushPlus API URLs of the form:
        https://www.pushplus.plus/send?token=TOKEN[&other_params]
        """
        result = re.match(
            r"^https?://www\.pushplus\.plus/send"
            r"(?:\?(?P<params>[^#]+))?$",
            url,
            re.I,
        )
        if result:
            params = result.group("params") or ""
            # The token must be present as a query parameter
            tok = re.search(
                r"(?:(?:^|&))token=(?P<token>[a-z0-9_-]+)",
                params,
                re.I,
            )
            if tok:
                # Re-build as an Apprise URL.  Preserve all existing params
                # so that topic, channel, and name all round-trip correctly.
                return NotifyPushplus.parse_url(
                    "{schema}://{token}/?{params}".format(
                        schema=NotifyPushplus.secure_protocol[0],
                        token=tok.group("token"),
                        params=params,
                    )
                )
        return None
