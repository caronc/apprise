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
#   https://www.pushplus.plus/doc/function/more.html
#
# Basic Apprise URL forms:
#
#   Personal notification (WeChat default):
#     pushplus://{token}
#
#   Group topic -- one notification per topic:
#     pushplus://{token}/{topic}
#     pushplus://{token}/{topic1}/{topic2}
#     pushplus://{token}/#{topic}
#
#   Friend / user notification (via 'to' parameter):
#     pushplus://{token}/@{friend_token}
#     pushplus://{token}/@{friend1}/@{friend2}
#
#   Select a delivery channel (mode= and channel= are synonyms):
#     pushplus://{token}?channel=mail
#     pushplus://{token}?mode=cp
#     pushplus://{token}?channel=app
#
#   Topic + delivery channel:
#     pushplus://{token}/{topic}?channel=mail
#
#   Several delivery channels at once (sent with PushPlus's batchSend):
#     pushplus://{token}?channel=wechat,mail
#
#   Channel configuration parameter (e.g. webhook code):
#     pushplus://{token}?channel=webhook&option={webhook_code}
#     pushplus://{token}?channel=webhook&name={webhook_name}
#     pushplus://{webhook_name}@{token}
#
#   With several channels, option= holds one code per channel, in the
#   same order and comma separated.  Leave a spot empty when a channel
#   needs no code:
#     pushplus://{token}?channel=wechat,webhook&option=,{webhook_code}
#
#   Special PushPlus message templates (html, txt and markdown are picked
#   with the standard ?format= option instead):
#     pushplus://{token}?template=json
#
#   Have PushPlus post the delivery result to your own server:
#     pushplus://{token}?callback=https://example.com/callback
#
#   When the schema://{name}@{token} form is used and no explicit channel=
#   is given, the webhook channel is implied automatically.
#
#   Native PushPlus API URLs (also accepted by parse_native_url):
#     https://www.pushplus.plus/send?token={token}
#     https://www.pushplus.plus/send/{token}
#     https://www.pushplus.plus/batchSend?token={token}
#
# Schema alias for WeCom users:
#   wecom://{token}    -- identical to pushplus://{token}?channel=cp
#
# For direct WeCom Application API notifications (without PushPlus as
# intermediary), use the wechat:// plugin instead.
#
# API References:
#   https://www.pushplus.plus/doc/
#   https://www.pushplus.plus/doc/guide/api.html
#   https://www.pushplus.plus/doc/guide/code.html
#   https://www.pushplus.plus/doc/guide/callback.html
#   https://www.pushplus.plus/doc/function/friend.html
#   https://www.pushplus.plus/doc/function/more.html
#   https://www.pushplus.plus/doc/help/limit.html

from __future__ import annotations

import json
import re
from typing import Any, Optional, Union

import requests

from ..common import NotifyFormat, NotifyType
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import parse_list, validate_regex
from .base import NotifyBase

# PushPlus application-level response codes.
# The HTTP status is always 200; the real result lives in the JSON body.
# Reference: https://www.pushplus.plus/doc/guide/code.html
PUSHPLUS_RESPONSE_CODES = {
    200: "Request succeeded.",
    302: "Not logged in.",
    401: "Request unauthorized.",
    403: "Request IP not authorized.",
    500: "System exception.",
    600: "Data exception.",
    805: "Unauthorized view.",
    888: "Insufficient points.",
    900: "User account restricted or rate limit reached.",
    903: "Invalid user token.",
    905: "Account not real-name verified.",
    907: "Token does not exist.",
    908: "User is blocked.",
    909: "Content requires review before sending.",
    912: "No available service package.",
    999: "Server validation error.",
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

# Special PushPlus templates that ?format= cannot pick.  The form, doc and
# excel templates are left out because they need a pushId as well.
PUSHPLUS_TEMPLATES = (
    "json",
    "cloudMonitor",
    "jenkins",
    "route",
    "pay",
)


class PushPlusChannel:
    """Defines the PushPlus delivery channels.

    The channel controls where the rendered notification is delivered.
    It is supplied as the channel= (or mode=) query parameter in the
    Apprise URL, e.g. pushplus://{token}?channel=mail.
    """

    # Deliver via WeChat service account (PushPlus default)
    WECHAT = "wechat"

    # Deliver via official Pushplus mobile App (Android, HarmonyOS, iOS)
    APP = "app"

    # Deliver via browser extension or desktop application
    EXTENSION = "extension"

    # Deliver via a configured webhook endpoint
    WEBHOOK = "webhook"

    # Deliver via WeChat ClawBot
    CLAWBOT = "clawbot"

    # Deliver via China Mobile ClawBot (SMS)
    CMCC = "cmcc"

    # Deliver via QQ Bot
    QQ = "qq"

    # Deliver via WeCom (WeChat Work / Enterprise WeChat).
    # The API value "cp" is PushPlus's internal identifier for this channel.
    # Both "cp" and the friendly alias "wecom" are accepted; both resolve here.
    WECOM = "cp"

    # Deliver via email
    MAIL = "mail"

    # Deliver via SMS
    SMS = "sms"

    # Deliver via voice call
    VOICE = "voice"


# All valid PushPlus delivery channels (these are the API values)
PUSHPLUS_CHANNELS = (
    PushPlusChannel.WECHAT,
    PushPlusChannel.APP,
    PushPlusChannel.EXTENSION,
    PushPlusChannel.WEBHOOK,
    PushPlusChannel.CLAWBOT,
    PushPlusChannel.CMCC,
    PushPlusChannel.QQ,
    PushPlusChannel.WECOM,
    PushPlusChannel.MAIL,
    PushPlusChannel.SMS,
    PushPlusChannel.VOICE,
)

# The PushPlus default delivery channel (WeChat)
PUSHPLUS_CHANNEL_DEFAULT = PushPlusChannel.WECHAT

# A group code or friend token (without its # or @ prefix): letters,
# digits, underscores and dashes, up to 50 characters.
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

    # URL used to POST to several channels at once
    batch_url = "https://www.pushplus.plus/batchSend"

    # Maximum body length documented by PushPlus
    body_maxlen = 20000

    # Title length limit documented by PushPlus (for a verified account)
    title_maxlen = 100

    # Default to HTML since PushPlus renders HTML by default
    notify_format = NotifyFormat.HTML

    # Define object URL templates
    templates = (
        # No targets: personal notification with optional ?channel= override
        "{schema}://{token}",
        # Targets in path: group topics and/or @friends
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
            # A group topic; the # prefix is optional when typed in a URL
            "target_topic": {
                "name": _("Target Topic"),
                "type": "string",
                "prefix": "#",
                "map_to": "targets",
            },
            # A friend token; the @ prefix is required
            "target_user": {
                "name": _("Target User"),
                "type": "string",
                "prefix": "@",
                "map_to": "targets",
            },
            # Targets: group topics and/or @friends
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
            # Allow the token to be supplied as a query parameter
            "token": {
                "alias_of": "token",
            },
            # ?to= is the standard Apprise alias for targets
            "to": {
                "alias_of": "targets",
            },
            # Delivery channel -- selects where the message is delivered.
            # One or more PUSHPLUS_CHANNELS values, comma separated
            # (wechat is the default).
            "channel": {
                "name": _("Channel"),
                "type": "list:string",
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
            # Channel configuration parameter (e.g. webhook code)
            "option": {
                "name": _("Channel Option"),
                "type": "string",
            },
            # Webhook endpoint name; the older way to set the option above.
            # The URL parameter is ?name= but the __init__ kwarg is webhook=
            # to avoid shadowing URLBase.name.
            "name": {
                "name": _("Webhook Name"),
                "type": "string",
                "map_to": "webhook",
            },
            # ?webhook= is accepted as another spelling of ?name=
            "webhook": {
                "alias_of": "name",
            },
            # Special PushPlus template (json, jenkins, etc.)
            "template": {
                "name": _("Template"),
                "type": "choice:string",
                "values": PUSHPLUS_TEMPLATES,
            },
            # Address PushPlus posts the delivery result to
            "callback": {
                "name": _("Callback URL"),
                "type": "string",
                "map_to": "callback_url",
            },
            # ?callbackUrl= is PushPlus's own name for the same thing
            "callbackurl": {
                "alias_of": "callback",
            },
        },
    )

    def __init__(
        self,
        token: str,
        targets: Optional[Union[str, list[str]]] = None,
        channel: Optional[str] = None,
        webhook: Optional[str] = None,
        option: Optional[str] = None,
        template: Optional[str] = None,
        callback_url: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
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
            raise AppriseImproperlyConfigured(msg)

        # Resolve the delivery channel from the schema alias when the URL
        # was entered as wechat:// or wecom:// instead of pushplus://.
        # self.schema is set by NotifyBase from the parsed URL protocol.
        schema_channel = PUSHPLUS_SCHEMA_MAP.get((self.schema or "").lower())

        # Determine the active delivery channel:
        #   1. Explicit channel= / mode= argument (already resolved by
        #      the caller since mode is an alias_of channel in template_args)
        #   2. Schema-implied channel (wecom://)
        #   3. Default (WeChat)
        if channel:
            # Several channels may be given, comma separated.  Their order
            # is kept because PushPlus pairs each one with its option code.
            # The 'wecom' friendly alias is normalised to the API value 'cp'.
            channels_split = [
                "cp" if c.strip().lower() == "wecom" else c.strip().lower()
                for c in channel.split(",")
                if c.strip()
            ]
            for ch in channels_split:
                if ch not in PUSHPLUS_CHANNELS:
                    msg = "The Pushplus channel ({}) is not valid.".format(ch)
                    self.logger.warning(msg)
                    raise AppriseImproperlyConfigured(msg)

            self.channel = ",".join(channels_split)

        elif schema_channel:
            # Schema-implied channel (wecom://)
            self.channel = schema_channel

        else:
            # Default to WeChat
            self.channel = PUSHPLUS_CHANNEL_DEFAULT

        # Resolved group topics -- one API call is made per topic
        self.topics = []

        # Resolved friend tokens / user accounts (for to= parameter)
        self.friends = []

        # Preserve unrecognised targets for round-trip fidelity in url()
        self.invalid_targets = []

        # Parse each target from the list:
        # - Starts with '@': friend token or user ID (recipient `to`)
        # - Starts with '#': group topic
        # - Plain alphanumeric string: group topic (backward-compatible)
        for target in parse_list(targets):
            if target.startswith("@"):
                user = target[1:].strip()
                if user and IS_TOPIC.match(user):
                    self.friends.append(user)
                    continue

            elif target.startswith("#"):
                topic = target[1:].strip()
                if topic and IS_TOPIC.match(topic):
                    self.topics.append(topic)
                    continue

            else:
                result = IS_TOPIC.match(target)
                if result:
                    self.topics.append(result.group("topic"))
                    continue

            # Unrecognised entry -- log and preserve
            self.logger.warning("Dropped invalid Pushplus target: %s", target)
            self.invalid_targets.append(target)

        # Channel configuration option (priority: option > webhook)
        if isinstance(option, str) and option.strip():
            self.option = option.strip()
        elif isinstance(webhook, str) and webhook.strip():
            self.option = webhook.strip()
        else:
            self.option = None

        # Backward compatibility: self.webhook mirrors self.option
        self.webhook = self.option

        # Optional special template (json, jenkins, etc.).  Matching ignores
        # case, but PushPlus is sent its own spelling (e.g. cloudMonitor).
        self.template = None
        if isinstance(template, str) and template.strip():
            self.template = next(
                (
                    t
                    for t in PUSHPLUS_TEMPLATES
                    if t.lower() == template.strip().lower()
                ),
                None,
            )
            if not self.template:
                msg = "The Pushplus template ({}) is not valid.".format(
                    template
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

        # Optional callback URL
        self.callback_url = (
            callback_url.strip()
            if isinstance(callback_url, str) and callback_url.strip()
            else None
        )

        return

    def _post_payload(
        self, url: str, payload: dict[str, Any], headers: dict[str, str]
    ) -> bool:
        """Helper to post a payload to Pushplus; returns True on success."""

        # Debug logging so the caller can inspect what will be sent
        self.logger.debug(
            "PushPlus POST URL: %s (cert_verify=%r)",
            url,
            self.verify_certificate,
        )
        self.logger.debug("PushPlus Payload: %r", payload)

        # Always throttle before each remote server I/O call
        self.throttle()

        try:
            r = requests.post(
                url,
                headers=headers,
                # Encode explicitly for non-ASCII (e.g. Chinese) chars
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )

            if r.status_code != requests.codes.ok:
                # HTTP-level failure -- log it and move on
                status_str = NotifyPushplus.http_response_code_lookup(
                    r.status_code
                )
                self.logger.warning(
                    "Failed to send PushPlus notification: %s%serror=%s.",
                    status_str,
                    ", " if status_str else "",
                    r.status_code,
                )
                self.logger.debug(
                    "Response Details:\r\n%r",
                    (r.content or b"")[:2000],
                )
                return False

            # PushPlus always returns HTTP 200; the real result is in
            # the JSON body where code == 200 means success.
            try:
                content = json.loads(r.content)

            except (AttributeError, TypeError, ValueError):
                # ValueError = r.content is unparsable
                # TypeError  = r.content is None
                # AttributeError = r is None
                content = {}
                self.logger.debug(
                    "Failed to parse PushPlus JSON response; body: %r",
                    (r.content or b"")[:2000],
                )

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
                    "Failed to send PushPlus notification: code=%s: %s.",
                    api_code,
                    error_str,
                )
                self.logger.debug(
                    "Response Details:\r\n%r",
                    content if content else (r.content or b"")[:2000],
                )
                return False

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending PushPlus notification."
            )
            self.logger.debug("Socket Exception: %s", str(e))
            return False

        # PushPlus accepted the request
        return True

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        **kwargs: Any,
    ) -> bool:
        """Perform PushPlus Notification."""

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
        }

        # Template selection: explicit override or derived from notify_format.
        # This is a server-side rendering hint only; the content payload
        # does not change.
        pp_template = (
            self.template
            if self.template
            else PUSHPLUS_FORMAT_MAP.get(
                self.notify_format, PUSHPLUS_FORMAT_DEFAULT
            )
        )

        # Batch send URL if multiple channels are comma-separated
        endpoint = self.batch_url if "," in self.channel else self.notify_url

        # Fields shared by every request this notification makes
        base_payload = {
            # Authentication token
            "token": self.token,
            # Fall back to the body when no title is provided
            "title": title if title else body,
            # Notification body content
            "content": body,
            # Rendering template
            "template": pp_template,
            # Delivery channel(s)
            "channel": self.channel,
        }

        # Add the channel configuration code when one was given
        if self.option:
            base_payload["option"] = self.option
            # If channel is webhook, also set webhook for compat
            if self.channel == PushPlusChannel.WEBHOOK:
                base_payload["webhook"] = self.option

        # Ask PushPlus to report the delivery result to this address
        if self.callback_url:
            base_payload["callbackUrl"] = self.callback_url

        # Track whether any individual send failed
        has_error = False

        # 1. Group topics -- one API call is made per topic
        if self.topics:
            for topic in self.topics:
                # Skip a target that already accepted this message so
                # a retry does not deliver it twice.
                if self.is_delivered(topic):
                    continue

                # Add the group topic for this request
                payload = dict(base_payload)
                payload["topic"] = topic

                if not self._post_payload(endpoint, payload, headers):
                    # Mark our failure and continue with the next topic
                    has_error = True
                    continue

                # Notification delivered for this topic
                self.logger.info(
                    "Sent PushPlus notification to topic %s.", topic
                )

                # Delivered; a retry can safely skip this target.
                self.mark_delivered(topic)

        # 2. Friend recipients -- the "to" field takes up to 10 friends
        if self.friends:
            batch_size = 10
            for i in range(0, len(self.friends), batch_size):
                # Join this batch of friends for the "to" field
                batch = self.friends[i : i + batch_size]
                batch_str = ",".join(batch)
                batch_key = f"@{batch_str}"

                # Skip a batch that already accepted this message
                if self.is_delivered(batch_key):
                    continue

                # Add the friends for this request
                payload = dict(base_payload)
                payload["to"] = batch_str

                if not self._post_payload(endpoint, payload, headers):
                    # Mark our failure and continue with the next batch
                    has_error = True
                    continue

                # Notification delivered to this batch of friends
                self.logger.info(
                    "Sent PushPlus notification to friend(s) %s.", batch_str
                )

                # Delivered; a retry can safely skip this batch.
                self.mark_delivered(batch_key)

        # 3. Personal notification (no topics and no friends)
        if (
            not self.topics
            and not self.friends
            and not self.is_delivered(None)
        ):
            payload = dict(base_payload)
            if not self._post_payload(endpoint, payload, headers):
                # Mark our failure
                has_error = True

            else:
                # Notification delivered; a retry can safely skip it.
                self.logger.info("Sent PushPlus notification.")
                self.mark_delivered(None)

        return not has_error

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another similar one.

        Targets or end points should never be identified here.
        """
        # The token is the sole connection identity for PushPlus
        return (self.secure_protocol[0], self.token)

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # When channel=webhook with a named endpoint / option, use the compact
        # {name}@pushplus://{token} form.  Both ?channel=webhook and ?name=
        # are implied by the user@ prefix and omitted from the query string.
        webhook_prefix = (
            self.channel == PushPlusChannel.WEBHOOK and self.option
        )

        # Start with an empty params dict
        params = {}

        # When not using the webhook prefix form, include ?channel= when it
        # differs from the default.  The schema alias (wechat:// / wecom://)
        # is never emitted here -- we always normalise back to pushplus://
        # plus ?channel= for clarity.
        if not webhook_prefix and self.channel != PUSHPLUS_CHANNEL_DEFAULT:
            params["channel"] = self.channel

        # If channel option is present and not using the webhook user@ prefix
        if not webhook_prefix and self.option:
            params["option"] = self.option

        # Explicit template override
        if self.template:
            params["template"] = self.template

        # Callback URL
        if self.callback_url:
            params["callback"] = self.callback_url

        # Merge in standard Apprise URL parameters (verify, format, etc.)
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Build targets path from #topics, @friends, and invalid entries
        targets = (
            [f"#{t}" for t in self.topics]
            + [f"@{f}" for f in self.friends]
            + list(self.invalid_targets)
        )

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
            name_str = NotifyPushplus.quote(self.option, safe="")
            if targets:
                return "{schema}://{name}@{token}/{targets}/?{params}".format(
                    schema=self.secure_protocol[0],
                    name=name_str,
                    token=token_str,
                    targets="/".join(
                        NotifyPushplus.quote(t, safe="@#") for t in targets
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
            # One or more targets: include them in the URL path
            return "{schema}://{token}/{targets}/?{params}".format(
                schema=self.secure_protocol[0],
                token=token_str,
                targets="/".join(
                    NotifyPushplus.quote(t, safe="@#") for t in targets
                ),
                params=NotifyPushplus.urlencode(params),
            )

        # No targets -- simple personal notification URL
        return "{schema}://{token}/?{params}".format(
            schema=self.secure_protocol[0],
            token=token_str,
            params=NotifyPushplus.urlencode(params),
        )

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
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

        # Collect targets from the URL path
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

        # Extract channel configuration option / webhook name:
        if "option" in results["qsd"] and results["qsd"]["option"]:
            opt = NotifyPushplus.unquote(results["qsd"]["option"])
            results["option"] = opt
            results["webhook"] = opt
        elif "webhook" in results["qsd"] and results["qsd"]["webhook"]:
            opt = NotifyPushplus.unquote(results["qsd"]["webhook"])
            results["option"] = opt
            results["webhook"] = opt
        elif "name" in results["qsd"] and results["qsd"]["name"]:
            opt = NotifyPushplus.unquote(results["qsd"]["name"])
            results["option"] = opt
            results["webhook"] = opt

        # Support the {webhook_name}@pushplus://{token} short form.
        # When user@ is present, it identifies the webhook endpoint name.
        # If no channel was explicitly given, webhook is the implied channel.
        if results.get("user"):
            # Use user@ as the webhook name when no query parameter set one
            if "webhook" not in results:
                opt = NotifyPushplus.unquote(results["user"])
                results["webhook"] = opt
                results["option"] = opt
            # Imply webhook channel when no explicit channel was specified
            if "channel" not in results:
                results["channel"] = PushPlusChannel.WEBHOOK

        # Message template
        if "template" in results["qsd"] and results["qsd"]["template"]:
            results["template"] = NotifyPushplus.unquote(
                results["qsd"]["template"]
            )

        # Callback URL; ?callback= wins over PushPlus's own ?callbackUrl=
        # spelling (query keys arrive lowercased, hence callbackurl)
        for key in ("callbackurl", "callback"):
            if key in results["qsd"] and results["qsd"][key]:
                results["callback_url"] = NotifyPushplus.unquote(
                    results["qsd"][key]
                )

        return results

    @staticmethod
    def parse_native_url(url: str) -> Optional[dict[str, Any]]:
        """Support native PushPlus API URLs of the form:
        https://www.pushplus.plus/send?token=TOKEN[&other_params]
        https://www.pushplus.plus/send/{token}[?other_params]
        https://www.pushplus.plus/batchSend?token=TOKEN[&other_params]
        """
        result = re.match(
            r"^https?://(?:www\.)?pushplus\.plus/(?:send|batchSend)"
            r"(?:/(?P<path_token>[a-z0-9_-]{32,64}))?"
            r"(?:\?(?P<params>[^#]+))?$",
            url,
            re.I,
        )
        if result:
            params = result.group("params") or ""
            path_token = result.group("path_token")

            # The token is either in the path or a query parameter
            if path_token:
                tok_val = path_token
            else:
                tok = re.search(
                    r"(?:(?:^|&))token=(?P<token>[a-z0-9_-]+)",
                    params,
                    re.I,
                )
                tok_val = tok.group("token") if tok else None

            if tok_val:
                # Re-build as an Apprise URL. Preserve all existing params
                # so that topic, channel, and option all round-trip correctly.
                query_str = f"?{params}" if params else ""
                return NotifyPushplus.parse_url(
                    "{schema}://{token}/{query}".format(
                        schema=NotifyPushplus.secure_protocol[0],
                        token=tok_val,
                        query=query_str,
                    )
                )
        return None
