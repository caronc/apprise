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

# For this to work correctly you need to create a webhook. To do this just
# click on the little gear icon next to the channel you're part of. From
# here you'll be able to access the Webhooks menu and create a new one.
#
#  When you've completed, you'll get a URL that looks a little like this:
#  https://discord.com/api/webhooks/417429632418316298/\
#         JHZ7lQml277CDHmQKMHI8qBe7bk2ZwO5UKjCiOAF7711o33MyqU344Qpgv7YTpadV_js
#
#  Simplified, it looks like this:
#     https://discord.com/api/webhooks/WEBHOOK_ID/WEBHOOK_TOKEN
#
#  This plugin will simply work using the url of:
#     discord://WEBHOOK_ID/WEBHOOK_TOKEN
#
# API Documentation on Webhooks:
#    - https://discord.com/developers/docs/resources/webhook
#
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from itertools import chain
from json import dumps, loads
from json.decoder import JSONDecodeError
import re
from typing import Any

import requests

from ..apprise_attachment import AppriseAttachment
from ..attachment.base import AttachBase
from ..common import NotifyFormat, NotifyImageSize, NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import parse_bool, parse_list, validate_regex
from ..utils.templates import TemplateType, apply_template
from .base import NotifyBase

# Used to detect user/role IDs and @here/@everyone tokens.
USER_ROLE_DETECTION_RE = re.compile(
    r"\s*(?:<?@(?P<role>&?)(?P<id>[0-9]+)>?|@(?P<value>[a-z0-9]+))", re.I
)


class NotifyDiscord(NotifyBase):
    """A wrapper to Discord Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Discord"

    # The services URL
    service_url = "https://discord.com/"

    # The default secure protocol
    secure_protocol = "discord"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/discord/"

    # Discord Webhook
    notify_url = "https://discord.com/api/webhooks"

    # Support attachments
    attachment_support = True

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_256

    # Discord is kind enough to return how many more requests we're allowed to
    # continue to make within it's header response as:
    # X-RateLimit-Reset: The epoc time (in seconds) we can expect our
    #                    rate-limit to be reset.
    # X-RateLimit-Remaining: an integer identifying how many requests we're
    #                        still allow to make.
    request_rate_per_sec = 0

    # Taken right from google.auth.helpers:
    clock_skew = timedelta(seconds=10)

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 2000

    # The 2000 characters above defined by the body_maxlen include that of the
    # title.  Setting this to True ensures overflow options behave properly
    overflow_amalgamate_title = True

    # Discord has a limit of the number of fields you can include in an
    # embeds message. This value allows the discord message to safely
    # break into multiple messages to handle these cases.
    discord_max_fields = 10

    # There is no reason we should exceed 35KB when reading in a JSON
    # file. If it is more than this, then it is not accepted
    max_discord_template_size = 35000

    # Maximum number of attachments Discord accepts in a single message
    discord_max_attachments = 10

    # Maximum total attachment bytes per message.
    # Discord's documented default is 25 MiB for most users.
    discord_max_attach_bytes = 25 * 1024 * 1024

    # Define object templates
    templates = (
        "{schema}://{webhook_id}/{webhook_token}",
        "{schema}://{botname}@{webhook_id}/{webhook_token}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "botname": {
                "name": _("Bot Name"),
                "type": "string",
                "map_to": "user",
            },
            "webhook_id": {
                "name": _("Webhook ID"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "webhook_token": {
                "name": _("Webhook Token"),
                "type": "string",
                "private": True,
                "required": True,
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "tts": {
                "name": _("Text To Speech"),
                "type": "bool",
                "default": False,
            },
            "avatar": {
                "name": _("Avatar Image"),
                "type": "bool",
                "default": True,
            },
            "avatar_url": {
                "name": _("Avatar URL"),
                "type": "string",
            },
            "href": {
                "name": _("URL"),
                "type": "string",
            },
            "url": {
                "alias_of": "href",
            },
            # Send a message to the specified thread within a webhook's
            # channel. The thread will automatically be unarchived.
            "thread": {
                "name": _("Thread ID"),
                "type": "string",
            },
            "footer": {
                "name": _("Display Footer"),
                "type": "bool",
                "default": False,
            },
            "footer_logo": {
                "name": _("Footer Logo"),
                "type": "bool",
                "default": True,
            },
            "fields": {
                "name": _("Use Fields"),
                "type": "bool",
                "default": True,
            },
            "flags": {
                "name": _("Discord Flags"),
                "type": "int",
                "min": 0,
            },
            "image": {
                "name": _("Include Image"),
                "type": "bool",
                "default": False,
                "map_to": "include_image",
            },
            # Explicit ping targets. Examples:
            #  - ping=12345,67890
            #  - ping=<@12345>,<@&67890>,@here
            "ping": {
                "name": _("Ping Users/Roles"),
                "type": "list:string",
            },
            "template": {
                "name": _("Template Path"),
                "type": "string",
                "private": True,
            },
            # When True (default) multiple attachments are grouped into
            # batches and sent in a single message where possible.
            # Set to no/false to revert to one attachment per message.
            "batch": {
                "name": _("Batch Attachments"),
                "type": "bool",
                "default": True,
            },
        },
    )

    # Define our token control
    template_kwargs = {
        "tokens": {
            "name": _("Template Tokens"),
            "prefix": ":",
        },
    }

    def __init__(
        self,
        webhook_id: str,
        webhook_token: str,
        tts: bool = False,
        avatar: bool = True,
        footer: bool = False,
        footer_logo: bool = True,
        include_image: bool = False,
        fields: bool = True,
        avatar_url: str | None = None,
        href: str | None = None,
        thread: str | None = None,
        flags: int | None = None,
        ping: list[str] | None = None,
        template: str | None = None,
        tokens: dict | None = None,
        batch: bool | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Discord Object."""
        super().__init__(**kwargs)

        # Webhook ID (associated with project)
        self.webhook_id = validate_regex(webhook_id)
        if not self.webhook_id:
            msg = (
                f"An invalid Discord Webhook ID ({webhook_id}) was specified."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # Webhook Token (associated with project)
        self.webhook_token = validate_regex(webhook_token)
        if not self.webhook_token:
            msg = (
                "An invalid Discord Webhook Token "
                f"({webhook_token}) was specified."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # Text To Speech
        self.tts = tts

        # Over-ride Avatar Icon
        self.avatar = avatar

        # Place a footer
        self.footer = footer

        # include a footer_logo in footer
        self.footer_logo = footer_logo

        # Place a thumbnail image inline with the message body
        self.include_image = include_image

        # Use Fields
        self.fields = fields

        # Specified Thread ID
        self.thread_id = thread

        # Avatar URL
        # This allows a user to provide an over-ride to the otherwise
        # dynamically generated avatar url images
        self.avatar_url = avatar_url

        # A URL to have the title link to
        self.href = href

        # A URL to have the title link to
        if flags:
            try:
                self.flags = int(flags)
                if self.flags < NotifyDiscord.template_args["flags"]["min"]:
                    raise ValueError()

            except (TypeError, ValueError):
                msg = (
                    f"An invalid Discord flags setting ({flags}) was "
                    "specified."
                )
                self.logger.warning(msg)
                raise TypeError(msg) from None
        else:
            self.flags = None

        # Ping targets (tokens from URL, already split by parse_list)
        self.ping: list[str] = parse_list(ping)

        # When True, group multiple attachments into a single message
        # where count and size limits allow; False reverts to one per
        # message (old behaviour)
        self.batch = (
            self.template_args["batch"]["default"]
            if batch is None
            else parse_bool(
                batch,
                default=self.template_args["batch"]["default"],
            )
        )

        self.ratelimit_reset = datetime.now(timezone.utc).replace(tzinfo=None)

        # Default to 1.0
        self.ratelimit_remaining = 1.0

        # Our template object is just an AppriseAttachment object
        self.template = AppriseAttachment(asset=self.asset)
        if template:
            # Add our definition to our template
            self.template.add(template)
            if not len(self.template):
                # add() failed (unsupported schema, unparseable URL, etc.)
                msg = "The Discord template specified could not be loaded."
                self.logger.warning(msg)
                raise TypeError(msg)

            # Enforce maximum file size
            self.template[0].max_file_size = self.max_discord_template_size

        # Template functionality
        self.tokens: dict = {}
        if isinstance(tokens, dict):
            self.tokens.update(tokens)

        elif tokens:
            msg = (
                "The specified Discord Template Tokens "
                f"({tokens}) are not identified as a dictionary."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # else: NoneType - this is okay

        return

    def gen_payload(
        self, body, title="", notify_type=NotifyType.INFO, **kwargs
    ):
        """Return a validated Discord webhook payload from template,
        or False on failure."""

        # Acquire the first template attachment
        template = self.template[0]
        if not template:
            # We could not access the attachment
            self.logger.error(
                "Could not access Discord template"
                f" {template.url(privacy=True)}."
            )
            return False

        # Acquire our image URL for potential token substitution
        image_url = self.image_url(notify_type)

        # Take a copy of our token dictionary
        tokens = self.tokens.copy()

        # Apply our standard template variable defaults
        tokens["app_body"] = body
        tokens["app_title"] = title
        tokens["app_type"] = notify_type.value
        tokens["app_id"] = self.app_id
        tokens["app_desc"] = self.app_desc
        tokens["app_color"] = self.color(notify_type)
        # app_color_hex is an explicit alias for app_color, provided so
        # templates can name the hex variant unambiguously alongside
        # app_color_int
        tokens["app_color_hex"] = self.color(notify_type)
        # Discord embed payloads require color as a decimal integer;
        # app_color_int provides that while app_color stays hex for
        # consistency with all other template-capable plugins
        tokens["app_color_int"] = self.color(notify_type, int)
        tokens["app_image_url"] = image_url
        tokens["app_url"] = self.app_url

        # Templates are always JSON; enforce JSON escaping
        tokens["app_mode"] = TemplateType.JSON

        # Stringify substitutions before JSON escaping; preserve app_mode
        safe_tokens = {
            k: (
                v
                if k == "app_mode" or isinstance(v, str)
                else ("" if v is None else str(v))
            )
            for k, v in tokens.items()
        }

        try:
            with open(template.path) as fp:
                content = apply_template(fp.read(), **safe_tokens)

        except OSError:
            self.logger.error(
                "Discord template"
                f" {template.url(privacy=True)} could not be read."
            )
            return False

        # Parse and validate as JSON
        try:
            content = loads(content)

        except (JSONDecodeError, ValueError) as e:
            self.logger.error(
                "Discord template"
                f" {template.url(privacy=True)} contains invalid JSON."
            )
            self.logger.debug(f"JSONDecodeError: {e}")
            return False

        # Template must parse to a JSON object, not an array or scalar
        if not isinstance(content, dict):
            self.logger.error(
                "Discord template"
                f" {template.url(privacy=True)} must be a JSON object"
                " (got {}).".format(type(content).__name__)
            )
            return False

        # A Discord webhook payload must have a non-empty 'content' string
        # or a non-empty 'embeds' list containing embed dicts
        has_content = (
            isinstance(content.get("content"), str) and content["content"]
        )
        has_embeds = (
            isinstance(content.get("embeds"), list) and content["embeds"]
        )
        if not (has_content or has_embeds):
            self.logger.error(
                "Discord template"
                f" {template.url(privacy=True)} must contain"
                " a non-empty 'content' string or a non-empty 'embeds'"
                " list."
            )
            return False

        # If embeds is present, each entry must be a JSON object (dict)
        if has_embeds and not all(
            isinstance(e, dict) for e in content["embeds"]
        ):
            self.logger.error(
                "Discord template"
                f" {template.url(privacy=True)} contains"
                " an embed entry that is not a JSON object."
            )
            return False

        # Return the validated payload content dict
        return content

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        attach: list[AttachBase] | None = None,
        **kwargs: Any,
    ) -> bool:
        """Perform Discord Notification."""

        payload: dict[str, Any] = {
            "tts": self.tts,
            # If Text-To-Speech is set to True, then we do not want to wait
            # for the whole message before continuing. Otherwise, we wait
            "wait": self.tts is False,
        }

        if self.flags:
            # Set our flag if defined:
            payload["flags"] = self.flags

        # Acquire image_url
        image_url = self.image_url(notify_type)

        if self.avatar and (image_url or self.avatar_url):
            payload["avatar_url"] = (
                self.avatar_url if self.avatar_url else image_url
            )

        if self.user:
            # Optionally override the default username of the webhook
            payload["username"] = self.user

        # Associate our thread_id with our message
        params = {"thread_id": self.thread_id} if self.thread_id else None

        # Template mode bypasses ping detection and embed construction;
        # the template defines the complete payload content.
        if not self.template:
            # Ping handling rules:
            # - If ping= is set, it is an additive if in MARKDOWN mode
            #   otherwise it is explicit for TEXT/HTML formats.
            # - Otherwise, ping detection only happens in MARKDOWN mode
            if self.notify_format == NotifyFormat.MARKDOWN:
                if self.ping:
                    payload.update(
                        self.ping_payload(body, " ".join(self.ping))
                    )
                else:
                    payload.update(self.ping_payload(body))

            # TEXT/HTML: no body parsing, ping= is exclusive
            elif self.ping:
                payload.update(self.ping_payload(" ".join(self.ping)))

        if self.template:
            # Generate our payload from the user-supplied template file
            template_payload = self.gen_payload(
                body=body,
                title=title,
                notify_type=notify_type,
                **kwargs,
            )
            if template_payload is False:
                # gen_payload() already logged the error; bail early
                return False

            # Merge template content over our base payload
            payload.update(template_payload)

            if not self._send(payload, params=params):
                # We failed to post our message
                return False

        elif body:
            # Track extra embed fields (if used)
            fields: list[dict[str, str]] = []

            if self.notify_format == NotifyFormat.MARKDOWN:
                # Use embeds for payload
                payload["embeds"] = [
                    {
                        "author": {
                            "name": self.app_id,
                            "url": self.app_url,
                        },
                        "title": title,
                        "description": body,
                        # Our color associated with our notification
                        "color": self.color(notify_type, int),
                    }
                ]

                if self.href:
                    payload["embeds"][0]["url"] = self.href

                if self.footer:
                    # Acquire logo URL
                    logo_url = self.image_url(notify_type, logo=True)

                    # Set Footer text to our app description
                    payload["embeds"][0]["footer"] = {
                        "text": self.app_desc,
                    }

                    if self.footer_logo and logo_url:
                        payload["embeds"][0]["footer"]["icon_url"] = logo_url

                if self.include_image and image_url:
                    payload["embeds"][0]["thumbnail"] = {
                        "url": image_url,
                        "height": 256,
                        "width": 256,
                    }

                if self.fields:
                    # Break titles out so that we can sort them in embeds
                    description, fields = self.extract_markdown_sections(body)

                    # Swap first entry for description
                    payload["embeds"][0]["description"] = description
                    if fields:
                        # Apply our additional parsing for a better
                        # presentation
                        payload["embeds"][0]["fields"] = fields[
                            : self.discord_max_fields
                        ]
                        fields = fields[self.discord_max_fields :]

            else:
                # TEXT or HTML:
                # - No ping detection unless ping= was provided.
                # - If ping= was provided, ping_payload() already generated
                #   payload["content"] starting with "👉 ...", and we
                #   append it.
                payload["content"] = (
                    body if not title else f"{title}\r\n{body}"
                ) + payload.get("content", "")

            if not self._send(payload, params=params):
                # We failed to post our message
                return False

            # Send remaining fields (if any)
            if fields:
                payload["embeds"][0]["description"] = ""
                for i in range(0, len(fields), self.discord_max_fields):
                    payload["embeds"][0]["fields"] = fields[
                        i : i + self.discord_max_fields
                    ]
                    if not self._send(payload):
                        # We failed to post our message
                        return False

        if attach and self.attachment_support:
            # Update our payload; the idea is to preserve it's other detected
            # and assigned values for re-use here too
            payload.update(
                {
                    # Text-To-Speech
                    "tts": False,
                    # Wait until the upload has posted itself before continuing
                    "wait": True,
                }
            )

            #
            # Remove our text/title based content for attachment use
            #
            payload.pop("embeds", None)
            payload.pop("content", None)
            payload.pop("allow_mentions", None)

            #
            # Build attachment batches in strict serial order.
            # Each batch respects the per-message attachment count and
            # total byte limits.  When batch=False every attachment is
            # its own message (legacy one-per-message behaviour).
            #
            max_per = self.discord_max_attachments if self.batch else 1

            batches: list[list[AttachBase]] = []
            current: list[AttachBase] = []
            current_size = 0

            for attachment in attach:
                # Size is only needed for byte-limit batching; skip the
                # stat()/download() it triggers when batching is off
                size = (
                    (len(attachment) if attachment else 0) if self.batch else 0
                )

                if current and (
                    len(current) >= max_per
                    or (
                        self.batch
                        and current_size + size > self.discord_max_attach_bytes
                    )
                ):
                    # Current batch is full; flush and start a new one
                    batches.append(current)
                    current = []
                    current_size = 0

                current.append(attachment)
                current_size += size

            # current always holds at least the last attachment here
            batches.append(current)

            #
            # Send each attachment batch
            #
            for batch in batches:
                if not self._send(payload, params=params, attach=batch):
                    # We failed to post our attachment batch
                    return False

        # Otherwise return
        return True

    def _send(
        self,
        payload: dict[str, Any],
        attach: list[AttachBase] | None = None,
        params: dict[str, str] | None = None,
        rate_limit: int = 1,
        **kwargs: Any,
    ) -> bool:
        """Wrapper to the requests (post) object."""

        # Our headers
        headers = {
            "User-Agent": self.app_id,
        }

        # Construct Notify URL
        notify_url = (
            f"{self.notify_url}/{self.webhook_id}/{self.webhook_token}"
        )

        self.logger.debug(
            "Discord POST URL:"
            f" {notify_url} (cert_verify={self.verify_certificate!r})"
        )
        self.logger.debug(f"Discord Payload: {payload!s}")

        wait: float | None = None

        if self.ratelimit_remaining <= 0.0:
            # Determine how long we should wait for or if we should wait at
            # all. This isn't fool-proof because we can't be sure the client
            # time (calling this script) is completely synced up with the
            # Discord server.  One would hope we're on NTP and our clocks are
            # the same allowing this to role smoothly:

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            if now < self.ratelimit_reset:
                # We need to throttle for the difference in seconds
                wait = abs(
                    (
                        self.ratelimit_reset - now + self.clock_skew
                    ).total_seconds()
                )

        # Always call throttle before any remote server i/o is made;
        self.throttle(wait=wait)

        # File handles opened for this call; all closed in `finally`
        handles: list[Any] = []
        # Multipart file list built from the attach batch
        files: list[Any] | None = None
        attach_ok = True

        try:
            # Open our attachment path(s) if required:
            if attach:
                files = []
                for idx, attachment in enumerate(attach):
                    # Verify accessibility before opening
                    if not attachment:
                        self.logger.warning(
                            "Could not access Discord attachment %s.",
                            attachment.url(privacy=True),
                        )
                        attach_ok = False
                        break

                    self.logger.debug(
                        "Posting Discord attachment %s",
                        attachment.url(privacy=True),
                    )

                    # Catch OSError per attachment open
                    try:
                        handle = attachment.open()
                    except OSError as e:
                        self.logger.warning(
                            "An I/O error occurred while reading %s.",
                            attachment.name or "attachment",
                        )
                        self.logger.debug("I/O Exception: %s", str(e))
                        attach_ok = False
                        break

                    # Register handle before appending to files
                    handles.append(handle)
                    files.append(
                        (
                            f"files[{idx}]",
                            (
                                attachment.name,
                                handle,
                                attachment.mimetype,
                            ),
                        )
                    )

                if not attach_ok:
                    return False

            else:
                headers["Content-Type"] = "application/json; charset=utf-8"

            r = requests.post(
                notify_url,
                params=params,
                data=(
                    {"payload_json": dumps(payload)}
                    if files
                    else dumps(payload)
                ),
                headers=headers,
                files=files,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )

            # Handle rate limiting (if specified)
            try:
                # Store our rate limiting (if provided)
                self.ratelimit_remaining = float(
                    r.headers.get("X-RateLimit-Remaining")
                )
                self.ratelimit_reset = datetime.fromtimestamp(
                    int(r.headers.get("X-RateLimit-Reset")), timezone.utc
                ).replace(tzinfo=None)

            except (TypeError, ValueError):
                # This is returned if we could not retrieve this
                # information gracefully accept this state and move on
                pass

            if r.status_code not in (
                requests.codes.ok,
                requests.codes.no_content,
            ):
                # We had a problem
                status_str = NotifyBase.http_response_code_lookup(
                    r.status_code
                )

                if (
                    r.status_code == requests.codes.too_many_requests
                    and rate_limit > 0
                ):
                    # handle rate limiting
                    self.logger.warning(
                        "Discord rate limiting in effect; "
                        "blocking for %.2f second(s)",
                        self.ratelimit_remaining,
                    )

                    # Try one more time before failing
                    return self._send(
                        payload=payload,
                        attach=attach,
                        params=params,
                        rate_limit=rate_limit - 1,
                        **kwargs,
                    )

                self.logger.warning(
                    "Failed to send Discord %s: %s%serror=%s.",
                    (
                        "{} attachment(s)".format(len(attach))
                        if attach
                        else "notification"
                    ),
                    status_str,
                    ", " if status_str else "",
                    r.status_code,
                )

                self.logger.debug(
                    "Response Details:\r\n%r", (r.content or b"")[:2000]
                )

                # Return; we're done
                return False

            else:
                if attach:
                    self.logger.info(
                        "Sent Discord %d attachment(s).", len(attach)
                    )
                else:
                    self.logger.info("Sent Discord notification.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred posting to Discord."
            )
            self.logger.debug(f"Socket Exception: {e!s}")
            return False

        except OSError as e:
            # Catches I/O errors from requests.post() and any unexpected
            # file-system errors not caught by the per-attachment check above
            self.logger.warning("An I/O error occurred posting to Discord.")
            self.logger.debug(f"I/O Exception: {e!s}")
            return False

        finally:
            # Close all handles regardless of success or failure
            for handle in handles:
                handle.close()

        return True

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        params: dict[str, str] = {
            "tts": "yes" if self.tts else "no",
            "avatar": "yes" if self.avatar else "no",
            "footer": "yes" if self.footer else "no",
            "footer_logo": "yes" if self.footer_logo else "no",
            "image": "yes" if self.include_image else "no",
            "fields": "yes" if self.fields else "no",
            "batch": "yes" if self.batch else "no",
        }

        if self.avatar_url:
            params["avatar_url"] = self.avatar_url

        if self.flags:
            params["flags"] = str(self.flags)

        if self.href:
            params["href"] = self.href

        if self.thread_id:
            params["thread"] = self.thread_id

        if self.ping:
            # Let Apprise urlencode handle list formatting
            params["ping"] = ",".join(self.ping)

        if self.template:
            # Include our template reference
            params["template"] = NotifyDiscord.quote(
                self.template[0].url(), safe=""
            )

        # Store any template token entries if specified
        params.update({f":{k}": v for k, v in self.tokens.items()})

        # Ensure our botname is set
        botname = f"{self.user}@" if self.user else ""

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return (
            "{schema}://{bname}{webhook_id}/{webhook_token}/?{params}".format(
                schema=self.secure_protocol,
                bname=botname,
                webhook_id=self.pprint(self.webhook_id, privacy, safe=""),
                webhook_token=self.pprint(
                    self.webhook_token, privacy, safe=""
                ),
                params=NotifyDiscord.urlencode(params),
            )
        )

    @property
    def url_identifier(self) -> tuple[str, str, str]:
        """Returns all of the identifiers that make this URL unique."""
        return (self.secure_protocol, self.webhook_id, self.webhook_token)

    @staticmethod
    def parse_url(url: str) -> dict[str, Any] | None:
        """Parses the URL and returns arguments for instantiating this object.

        Syntax:
          discord://webhook_id/webhook_token
        """
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Store our webhook ID
        webhook_id = NotifyDiscord.unquote(results["host"])

        # Now fetch our tokens
        try:
            webhook_token = NotifyDiscord.split_path(results["fullpath"])[0]

        except IndexError:
            # Force some bad values that will get caught
            # in parsing later
            webhook_token = None

        results["webhook_id"] = webhook_id
        results["webhook_token"] = webhook_token

        # Text To Speech
        results["tts"] = parse_bool(results["qsd"].get("tts", False))

        # Use sections
        # effectively detect multiple fields and break them off
        # into sections
        results["fields"] = parse_bool(results["qsd"].get("fields", True))

        # Use Footer
        results["footer"] = parse_bool(results["qsd"].get("footer", False))

        # Use Footer Logo
        results["footer_logo"] = parse_bool(
            results["qsd"].get("footer_logo", True)
        )

        # Update Avatar Icon
        results["avatar"] = parse_bool(results["qsd"].get("avatar", True))

        # Boolean to include an image or not
        results["include_image"] = parse_bool(
            results["qsd"].get(
                "image", NotifyDiscord.template_args["image"]["default"]
            )
        )

        if "botname" in results["qsd"]:
            # Alias to User
            results["user"] = NotifyDiscord.unquote(results["qsd"]["botname"])

        if "flags" in results["qsd"]:
            # Alias to User
            results["flags"] = NotifyDiscord.unquote(results["qsd"]["flags"])

        # Extract avatar url if it was specified
        if "avatar_url" in results["qsd"]:
            results["avatar_url"] = NotifyDiscord.unquote(
                results["qsd"]["avatar_url"]
            )

        # Extract url if it was specified
        if "href" in results["qsd"]:
            results["href"] = NotifyDiscord.unquote(results["qsd"]["href"])

        elif "url" in results["qsd"]:
            results["href"] = NotifyDiscord.unquote(results["qsd"]["url"])
            # Markdown is implied
            results["format"] = NotifyFormat.MARKDOWN

        # Extract thread id if it was specified
        if "thread" in results["qsd"]:
            results["thread"] = NotifyDiscord.unquote(results["qsd"]["thread"])
            # Markdown is implied
            results["format"] = NotifyFormat.MARKDOWN

        # Extract ping targets, comma/space separated
        if "ping" in results["qsd"]:
            results["ping"] = NotifyDiscord.unquote(results["qsd"]["ping"])

        # Template Handling
        if "template" in results["qsd"] and results["qsd"]["template"]:
            results["template"] = NotifyDiscord.unquote(
                results["qsd"]["template"]
            )

        # Store our template tokens
        results["tokens"] = results["qsd:"]

        # Batch attachments flag
        results["batch"] = parse_bool(
            results["qsd"].get(
                "batch",
                NotifyDiscord.template_args["batch"]["default"],
            )
        )

        return results

    @staticmethod
    def parse_native_url(url: str) -> dict[str, Any] | None:
        """
        Support https://discord.com/api/webhooks/WEBHOOK_ID/WEBHOOK_TOKEN
        Support Legacy URL as well:
            https://discordapp.com/api/webhooks/WEBHOOK_ID/WEBHOOK_TOKEN
        """

        result = re.match(
            r"^https?://discord(app)?\.com/api/webhooks/"
            r"(?P<webhook_id>[0-9]+)/"
            r"(?P<webhook_token>[A-Z0-9_-]+)/?"
            r"(?P<params>\?.+)?$",
            url,
            re.I,
        )

        if result:
            return NotifyDiscord.parse_url(
                "{schema}://{webhook_id}/{webhook_token}/{params}".format(
                    schema=NotifyDiscord.secure_protocol,
                    webhook_id=result.group("webhook_id"),
                    webhook_token=result.group("webhook_token"),
                    params=(
                        ""
                        if not result.group("params")
                        else result.group("params")
                    ),
                )
            )

        return None

    def ping_payload(self, *args: str) -> dict[str, Any]:
        """
        Takes one or more strings and applies the payload associated with
        pinging the users detected within.

        This returns a dict that may contain:
          - allow_mentions
          - content (starting with "👉 " and containing mention tokens)
        """

        payload: dict[str, Any] = {}

        roles: set[str] = set()
        users: set[str] = set()
        parse: set[str] = set()

        for arg in args:
            # parse for user id's <@123> and role IDs <@&456>
            results = USER_ROLE_DETECTION_RE.findall(arg)
            if not results:
                continue

            for is_role, no, value in results:
                if value:
                    parse.add(value)

                elif is_role:
                    roles.add(no)

                else:  # is_user
                    users.add(no)

        if not (roles or users or parse):
            # Nothing to add
            return payload

        payload["allow_mentions"] = {
            "parse": list(parse),
            "users": list(users),
            "roles": list(roles),
        }

        payload["content"] = "👉 " + " ".join(
            chain(
                [f"@{value}" for value in parse],
                [f"<@&{value}>" for value in roles],
                [f"<@{value}>" for value in users],
            )
        )

        return payload

    @staticmethod
    def extract_markdown_sections(
        markdown: str,
    ) -> tuple[str, list[dict[str, str]]]:
        """Extract headers and their corresponding sections into embed
        fields."""

        # Search for any header information found without it's own section
        # identifier
        match = re.match(
            r"^\s*(?P<desc>[^\s#]+.*?)(?=\s*$|[\r\n]+\s*#)",
            markdown,
            flags=re.S,
        )

        description = match.group("desc").strip() if match else ""
        if description:
            # Strip description from our string since it has been handled
            # now.
            markdown = re.sub(re.escape(description), "", markdown, count=1)

        regex = re.compile(
            r"\s*#[# \t\v]*(?P<name>[^\n]+)(\n|\s*$)"
            r"\s*((?P<value>[^#].+?)(?=\s*$|[\r\n]+\s*#))?",
            flags=re.S,
        )

        common = regex.finditer(markdown)
        fields: list[dict[str, str]] = []
        for el in common:
            d = el.groupdict()

            fields.append(
                {
                    "name": d.get("name", "").strip("#`* \r\n\t\v"),
                    "value": "```{}\n{}```".format(
                        "md" if d.get("value") else "",
                        (
                            d.get("value").strip() + "\n"
                            if d.get("value")
                            else ""
                        ),
                    ),
                }
            )

        return description, fields
