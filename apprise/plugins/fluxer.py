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
#  https://api.fluxer.app/webhooks/417429632418316298/\
#         JHZ7lQml277CDHmQKMHI8qBe7bk2ZwO5UKjCiOAF7711o33MyqU344Qpgv7YTpadV
#
#  Simplified, it looks like this:
#     https://api.fluxer.app/webhooks/WEBHOOK_ID/WEBHOOK_TOKEN
#  or:
#     https://api.fluxer.app/v1/webhooks/WEBHOOK_ID/WEBHOOK_TOKEN
#
#  This plugin will simply work using the url of:
#     fluxer://WEBHOOK_ID/WEBHOOK_TOKEN
#
from __future__ import annotations

import contextlib
from datetime import datetime, timedelta, timezone
from itertools import chain
from json import dumps
import re
from typing import Any

import requests

from ..attachment.base import AttachBase
from ..common import NotifyFormat, NotifyImageSize, NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import (
    is_hostname,
    is_ipaddr,
    parse_bool,
    parse_list,
    validate_regex,
)
from .base import NotifyBase

# Used to detect user/role IDs and @here/@everyone tokens.
USER_ROLE_DETECTION_RE = re.compile(
    r"\s*(?:<?@(?P<role>&?)(?P<id>[0-9]+)>?|@(?P<value>[a-z0-9]+))",
    re.I,
)


class FluxerMode:
    """Define Fluxer Notification Modes."""

    # App posts upstream to the developer API on Fluxer's website
    CLOUD = "cloud"

    # Running a dedicated private Fluxer Server
    PRIVATE = "private"


FLUXER_MODES = (
    FluxerMode.CLOUD,
    FluxerMode.PRIVATE,
)


class NotifyFluxer(NotifyBase):
    """A wrapper for Fluxer Webhook Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Fluxer"

    # The Services URL
    service_url = "https://fluxer.app/"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/fluxer/"

    # The default protocol
    protocol = "fluxer"

    # The default secure protocol
    secure_protocol = "fluxers"

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_256

    # Discord is kind enough to return how many more requests we're allowed to
    # continue to make within it's header response as:
    # Retry-After: number of seconds to try again
    request_rate_per_sec = 0

    # Support attachments
    attachment_support = True

    # Maximum number of attachments allowed per message
    fluxer_max_files = 10

    # The default period of time to wait if we can not determine the reason
    # for the 429 (to many) request
    default_delay_sec = 1.0

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 2000

    # The 2000 characters above defined by the body_maxlen include that of the
    # title. Setting this to True ensures overflow options behave properly
    overflow_amalgamate_title = True

    # Fluxer limit for number of embed fields per message
    fluxer_max_fields = 10

    # If our hostname matches the following we automatically enforce cloud
    # mode
    __auto_cloud_host = re.compile(r"fluxer\.app", re.IGNORECASE)

    # Default upstream/cloud host if none is defined
    cloud_notify_host = "https://api.fluxer.app"

    # Webhook URLs used by the Fluxer API.
    notify_url = "{prefix}/webhooks/{webhook_id}/{webhook_token}"

    templates = (
        "{schema}://{webhook_id}/{webhook_token}",
        "{schema}://{host}/{webhook_id}/{webhook_token}",
        "{schema}://{host}:{port}/{webhook_id}/{webhook_token}",
        "{schema}://{botname}@{webhook_id}/{webhook_token}",
        "{schema}://{botname}@{host}:{port}/{webhook_id}/{webhook_token}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "host": {
                "name": _("Hostname"),
                "type": "string",
            },
            "port": {
                "name": _("Port"),
                "type": "int",
                "min": 1,
                "max": 65535,
            },
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
                "regex": (r"^[0-9]{10,}$", "i"),
            },
            "webhook_token": {
                "name": _("Webhook Token"),
                "type": "string",
                "private": True,
                "required": True,
                "regex": (r"^[A-Za-z0-9_\-]{16,}$", "i"),
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "mode": {
                "name": _("Mode"),
                "type": "choice:string",
                "values": FLUXER_MODES,
                "default": FluxerMode.CLOUD,
            },
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
            "thread": {
                "name": _("Thread ID"),
                "type": "string",
            },
            "thread_name": {
                "name": _("Thread Name"),
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
            "ping": {
                "name": _("Ping Users/Roles"),
                "type": "list:string",
            },
            "name": {
                "alias_of": "botname",
            },
        },
    )

    def __init__(
        self,
        webhook_id: str,
        webhook_token: str,
        mode: str | None = None,
        tts: bool = False,
        avatar: bool = True,
        footer: bool = False,
        footer_logo: bool = True,
        include_image: bool = False,
        fields: bool = True,
        avatar_url: str | None = None,
        href: str | None = None,
        thread: str | None = None,
        thread_name: str | None = None,
        flags: int | None = None,
        ping: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Fluxer Object."""

        super().__init__(**kwargs)

        # Webhook ID (associated with project)
        self.webhook_id = validate_regex(
            webhook_id, *self.template_tokens["webhook_id"]["regex"]
        )
        if not self.webhook_id:
            msg = f"An invalid Fluxer Webhook ID ({webhook_id}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Webhook Token (associated with project)
        self.webhook_token = validate_regex(
            webhook_token, *self.template_tokens["webhook_token"]["regex"]
        )
        if not self.webhook_token:
            msg = (
                "An invalid Fluxer Webhook Token "
                f"({webhook_token}) was specified."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # Prepare our mode
        self.mode = (
            mode.strip().lower()
            if isinstance(mode, str)
            else self.template_args["mode"]["default"]
        )

        if self.mode not in FLUXER_MODES:
            msg = f"An invalid Fluxer Mode ({mode}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        if not self.host and self.mode == FluxerMode.PRIVATE:
            # No host provided
            msg = f"An invalid Fluxer Hostname ({self.host}) was provided."
            self.logger.warning(msg)
            raise TypeError(msg)

        if self.mode == FluxerMode.PRIVATE and \
                self.__auto_cloud_host.search(self.host):
            # Is a Fluxer Cloud API
            self.mode = FluxerMode.CLOUD
            self.logger.warning(
                "Fluxer mode changed to %s mode because fluxer.app found "
                "in %s",
                self.mode,
                self.host,
            )

        # Text To Speech
        self.tts = tts if isinstance(tts, bool) \
            else parse_bool(tts, self.template_args["tts"]["default"])

        # Avatar
        self.avatar = avatar if isinstance(avatar, bool) \
            else parse_bool(avatar, self.template_args["avatar"]["default"])

        # Footer
        self.footer = footer if isinstance(footer, bool) \
            else parse_bool(footer, self.template_args["footer"]["default"])

        # Footer Logo
        self.footer_logo = footer_logo if isinstance(footer_logo, bool) \
            else parse_bool(
                footer_logo, self.template_args["footer_logo"]["default"])

        # Include Image
        self.include_image = include_image if isinstance(include_image, bool) \
            else parse_bool(
                include_image, self.template_args["image"]["default"])

        # Fields
        self.fields = fields if isinstance(fields, bool) \
            else parse_bool(fields, self.template_args["fields"]["default"])

        self.thread_id = thread
        self.thread_name = thread_name

        self.avatar_url = avatar_url
        self.href = href

        if flags:
            try:
                self.flags = int(flags)
                if self.flags < self.template_args["flags"]["min"]:
                    raise ValueError()

            except (TypeError, ValueError):
                msg = (
                    f"An invalid Fluxer flags setting ({flags}) was specified."
                )
                self.logger.warning(msg)
                raise TypeError(msg) from None
        else:
            self.flags = None

        self.ping: list[str] = parse_list(ping)

        self.ratelimit_reset = datetime.now(timezone.utc).replace(tzinfo=None)
        self.ratelimit_remaining = self.default_delay_sec

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        attach=None,
        **kwargs: Any,
    ) -> bool:

        """Perform Fluxer Notification."""

        # Prepare our headers:
        payload = {
            "tts": self.tts,
            # If Text-To-Speech is set to True, then we do not want to wait
            # for the whole message before continuing. Otherwise, we wait
            "wait": self.tts is False,
        }

        # Acquire image_url
        image_url = self.image_url(notify_type)

        if self.avatar and (image_url or self.avatar_url):
            payload["avatar_url"] = (
                self.avatar_url if self.avatar_url else image_url
            )

        if self.user:
            # Optionally override the default username of the webhook
            payload["username"] = self.user

        if self.thread_name:
            payload["thread_name"] = self.thread_name

        params = {"thread_id": self.thread_id} if self.thread_id else None

        if self.notify_format == NotifyFormat.MARKDOWN:
            if self.ping:
                payload.update(self.ping_payload(body, " ".join(self.ping)))
            else:
                payload.update(self.ping_payload(body))

        elif self.ping:
            payload.update(self.ping_payload(" ".join(self.ping)))

        if body:
            fields: list[dict[str, str]] = []

            if self.notify_format == NotifyFormat.MARKDOWN:
                embed: dict[str, Any] = {
                    "author": {
                        "name": self.app_id,
                        "url": self.app_url,
                    },
                    "description": body,
                    "color": self.color(notify_type, int),
                }

                # Fluxer strictly validates fields; omit 'title' if it's empty
                if title:
                    embed["title"] = title

                payload["embeds"] = [embed]

                if self.href:
                    payload["embeds"][0]["url"] = self.href

                if self.footer:
                    logo_url = self.image_url(notify_type, logo=True)
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
                            : self.fluxer_max_fields
                        ]
                        fields = fields[self.fluxer_max_fields :]

            else:
                # TEXT or HTML:
                # - No ping detection unless ping= was provided.
                # - If ping= was provided, ping_payload() already generated
                #   payload["content"] starting with "👉 ...", and we append
                #   it.
                payload["content"] = (
                    body if not title else f"{title}\r\n{body}"
                ) + payload.get("content", "")

            if not self._send(payload, params=params):
                # We failed to post our message
                return False

            # Send remaining fields (if any)
            if fields:
                payload["embeds"][0]["description"] = ""
                for i in range(0, len(fields), self.fluxer_max_fields):
                    payload["embeds"][0]["fields"] = fields[
                        i : i + self.fluxer_max_fields
                    ]
                    if not self._send(payload, params=params):
                        return False

        if attach and self.attachment_support:

            # Update our payload; the idea is to preserve it's other detected
            # and assigned values for re-use here too
            payload.update({
                # Text-To-Speech can be off so we don't read the filename
                "tts": False,
                # no tts; no need to wait
                "wait": False,
            })

            #
            # Remove our text/title based content for attachment use
            #
            payload.pop("embeds", None)
            payload.pop("allow_mentions", None)

            #
            # Send our attachments
            #
            for attachment in attach:
                self.logger.info(
                    f"Posting Fluxer Attachment {attachment.name}"
                )

                if not self._send(payload, params=params, attach=attachment):
                    # We failed to post our message
                    return False

        return True

    def _send(
        self,
        payload: dict[str, Any],
        params: dict[str, str] | None = None,
        rate_limit: int = 1,
        attach: AttachBase | None = None,
        **kwargs: Any,
    ) -> bool:
        """Wrapper to the requests (post) object."""

        # Our headers
        headers = {
            "User-Agent": self.app_id,
        }

        if self.mode == FluxerMode.CLOUD:
            prefix = self.cloud_notify_host

        else:
            # Prepare our Fluxer Template URL
            schema = "https" if self.secure else "http"

            # Construct Notify URL
            prefix = f"{schema}://{self.host}"
            if isinstance(self.port, int):
                prefix += f":{self.port}"

        notify_url = self.notify_url.format(
            prefix=prefix,
            webhook_id=self.webhook_id,
            webhook_token=self.webhook_token,
        )

        safe_url = self.notify_url.format(
            prefix=prefix,
            webhook_id=self.pprint(self.webhook_id, True, safe=""),
            webhook_token=self.pprint(self.webhook_token, True, safe=""),
        )

        self.logger.debug(
            "Fluxer POST URL: %s (cert_verify=%r)",
            safe_url,
            self.verify_certificate,
        )
        self.logger.debug("Fluxer Payload: %s", payload)

        wait: float | None = None

        if self.ratelimit_remaining <= 0.0:
            now = datetime.now(timezone.utc).replace(tzinfo=None)

            if now >= self.ratelimit_reset:
                # Our block window has passed; clear it so we do not keep
                # re-entering this logic on subsequent sends.
                self.ratelimit_remaining = 1.0
                wait = None

            else:
                wait = (self.ratelimit_reset - now).total_seconds()

        self.throttle(wait=wait)

        # Perform some simple error checking
        if isinstance(attach, AttachBase):
            if not attach:
                # We could not access the attachment
                self.logger.error(
                    f"Could not access attachment {attach.url(privacy=True)}."
                )
                return False

            self.logger.debug(
                f"Posting Fluxer attachment {attach.url(privacy=True)}"
            )

        # Our attachment path (if specified)
        files = None
        data: dict[str, Any] | str
        try:

            # Open our attachment path if required:
            if attach:
                #
                # Fluxer requires content to be provided
                #
                payload.update({
                    "content": attach.name,
                    "attachments": [{
                        "id": 0,
                        "filename": attach.name,
                    }],
                })
                files = {
                    "files[0]": (
                        attach.name,
                        # file handle is safely closed in `finally`; inline
                        # open is intentional
                        open(attach.path, "rb"),  # noqa: SIM115
                        # Explicitly declare the file type so the server
                        # doesn't hang
                        attach.mimetype,
                    )
                }
                data = {
                    "payload_json": dumps(payload),
                }
            else:
                headers["Content-Type"] = "application/json; charset=utf-8"
                data = dumps(payload)

            r = requests.post(
                notify_url,
                params=params,
                data=data,
                files=files,
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )

            if r.status_code == requests.codes.too_many_requests:
                # Determine a delay (seconds) using Retry-After
                delay = self.default_delay_sec
                try:
                    ra = r.headers.get("Retry-After")
                    if ra is not None:
                        delay = float(ra)

                except (TypeError, ValueError):
                    delay = self.default_delay_sec

                # Enforce a minimum delay
                delay = max(self.default_delay_sec, delay)

                # Put ourselves into a blocked state until ratelimit_reset
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                self.ratelimit_remaining = 0.0
                self.ratelimit_reset = now + timedelta(seconds=delay)

                self.logger.warning(
                    "Fluxer rate limiting in effect; blocking for %.2f "
                    "second(s)",
                    delay,
                )

                if rate_limit > 0:
                    # Prevent file handle leak before recursion
                    if files:
                        for file_info in files.values():
                            with contextlib.suppress(Exception):
                                file_info[1].close()
                        files = None

                    # Recursive retry; next _send() invocation will hit the
                    # ratelimit_remaining<=0 gate and sleep via throttle()
                    return self._send(
                        payload=payload,
                        params=params,
                        rate_limit=rate_limit - 1,
                        attach=attach,
                        **kwargs,
                    )

                # No retries left
                return False

            if r.status_code not in (
                requests.codes.ok,
                requests.codes.no_content,
            ):
                status_str = NotifyBase.http_response_code_lookup(
                    r.status_code
                )

                self.logger.warning(
                    "Failed to send Fluxer notification: %s, error=%d.",
                    status_str,
                    r.status_code,
                )

                self.logger.debug(
                    "Response Details:\r\n%r", (r.content or b"")[:2000]
                )
                return False

            self.logger.info("Sent Fluxer notification.")

            # Reset Rate Limiting (a bit of a hacky approach for now)
            # TODO: Learn more about how ratelimiting works with Fluxer
            self.ratelimit_reset = \
                datetime.now(timezone.utc).replace(tzinfo=None)
            self.ratelimit_remaining = self.default_delay_sec

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending Fluxer notification."
            )
            self.logger.debug("Socket Exception: %s", e)
            return False

        except OSError as e:
            self.logger.warning(
                "An I/O error occurred while reading attachment(s)")
            self.logger.debug(f"I/O Exception: {e!s}")
            return False

        finally:
            # Close our file (if it's open) stored in the second element
            # of our files tuple (index 1)
            if files:
                for file_info in files.values():
                    with contextlib.suppress(Exception):
                        file_info[1].close()

        return True

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        params: dict[str, str] = {
            "mode": self.mode,
            "tts": "yes" if self.tts else "no",
            "avatar": "yes" if self.avatar else "no",
            "footer": "yes" if self.footer else "no",
            "footer_logo": "yes" if self.footer_logo else "no",
            "image": "yes" if self.include_image else "no",
            "fields": "yes" if self.fields else "no",
        }

        if self.avatar_url:
            params["avatar_url"] = self.avatar_url

        if self.flags is not None:
            params["flags"] = str(self.flags)

        if self.href:
            params["href"] = self.href

        if self.thread_id:
            params["thread"] = self.thread_id

        if self.thread_name:
            params["thread_name"] = self.thread_name

        if self.ping:
            params["ping"] = ",".join(self.ping)

        botname = f"{self.user}@" if self.user else ""

        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        if self.mode == FluxerMode.PRIVATE:
            default_port = 443 if self.secure else 80
            port = (
                ""
                if self.port is None or self.port == default_port
                else f":{self.port}"
            )

            schema = self.secure_protocol if self.secure else self.protocol
            return (
                "{schema}://{bname}{host}{port}/{webhook_id}/{webhook_token}"
                "/?{params}".format(
                    schema=schema,
                    bname=botname,
                    host=self.host,
                    port=port,
                    webhook_id=self.pprint(self.webhook_id, privacy, safe=""),
                    webhook_token=self.pprint(
                        self.webhook_token, privacy, safe=""
                    ),
                    params=NotifyFluxer.urlencode(params),
                )
            )

        # Cloud Mode
        return (
            "{schema}://{bname}{webhook_id}/{webhook_token}/?{params}".format(
                schema=self.protocol,
                bname=botname,
                webhook_id=self.pprint(self.webhook_id, privacy, safe=""),
                webhook_token=self.pprint(
                    self.webhook_token, privacy, safe=""
                ),
                params=NotifyFluxer.urlencode(params),
            )
        )

    @property
    def url_identifier(self) -> tuple[Any, ...]:
        """Returns all of the identifiers that make this URL unique."""
        kwargs = (
            (
                self.secure_protocol
                if self.mode == FluxerMode.CLOUD
                else (self.secure_protocol if self.secure else self.protocol)
            ),
            self.host if self.mode == FluxerMode.PRIVATE else "",
            (
                "" if self.mode == FluxerMode.CLOUD
                else (self.port if self.port else (443 if self.secure else 80))
            ),
            self.webhook_id,
            self.webhook_token,
        )

        return kwargs

    @staticmethod
    def parse_url(url: str) -> dict[str, Any] | None:
        """Parses the URL and returns arguments for instantiating this object.

        Syntax:
          fluxer://webhook_id/webhook_token
        """

        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Tokenize our URL
        tokens = [
            NotifyFluxer.unquote(results["host"]),
            *NotifyFluxer.split_path(results["fullpath"]),
        ]

        # Text To Speech
        results["tts"] = parse_bool(results["qsd"].get(
            "tts", NotifyFluxer.template_args["tts"]["default"]))

        # Mode override
        if "mode" in results["qsd"] and results["qsd"]["mode"]:
            results["mode"] = NotifyFluxer.unquote(
                results["qsd"]["mode"].strip().lower()
            )

        else:
            # We can try to detect the mode based on the validity of the
            # hostname.
            #
            # This isn't a surfire way to do things though; it's best to
            # specify the mode= flag
            results["mode"] = (
                FluxerMode.PRIVATE
                if (
                    (
                        is_hostname(results["host"])
                        or is_ipaddr(results["host"])
                    )
                    and len(tokens) > 2
                )
                else FluxerMode.CLOUD
            )

        results["footer"] = parse_bool(
            results["qsd"].get(
                "footer", NotifyFluxer.template_args["footer"]["default"]
            )
        )
        results["footer_logo"] = parse_bool(
            results["qsd"].get(
                "footer_logo",
                NotifyFluxer.template_args["footer_logo"]["default"]
            )
        )
        results["fields"] = parse_bool(
            results["qsd"].get(
                "fields", NotifyFluxer.template_args["fields"]["default"]
            )
        )
        results["include_image"] = parse_bool(
            results["qsd"].get(
                "image", NotifyFluxer.template_args["image"]["default"]
            )
        )

        if "botname" in results["qsd"]:
            results["user"] = NotifyFluxer.unquote(results["qsd"]["botname"])

        elif "name" in results["qsd"]:
            results["user"] = NotifyFluxer.unquote(results["qsd"]["name"])

        if "flags" in results["qsd"]:
            results["flags"] = NotifyFluxer.unquote(results["qsd"]["flags"])

        if "avatar_url" in results["qsd"]:
            results["avatar_url"] = NotifyFluxer.unquote(
                results["qsd"]["avatar_url"]
            )

        if "href" in results["qsd"]:
            results["href"] = NotifyFluxer.unquote(results["qsd"]["href"])
            results["format"] = NotifyFormat.MARKDOWN

        elif "url" in results["qsd"]:
            results["href"] = NotifyFluxer.unquote(results["qsd"]["url"])
            results["format"] = NotifyFormat.MARKDOWN

        # Update Avatar Icon
        results["avatar"] = parse_bool(results["qsd"].get(
            "avatar", NotifyFluxer.template_args["avatar"]["default"]))

        if "thread" in results["qsd"]:
            results["thread"] = NotifyFluxer.unquote(results["qsd"]["thread"])
            results["format"] = NotifyFormat.MARKDOWN

        if "thread_name" in results["qsd"]:
            results["thread_name"] = NotifyFluxer.unquote(
                results["qsd"]["thread_name"]
            )

        if "ping" in results["qsd"]:
            results["ping"] = NotifyFluxer.unquote(results["qsd"]["ping"])

        # Pop our tokens from back to front
        results["webhook_token"] = None if not tokens else tokens.pop()
        results["webhook_id"] = None if not tokens else tokens.pop()

        return results

    @staticmethod
    def parse_native_url(url: str) -> dict[str, Any] | None:
        """
        Supported:
          - https://api.fluxer.app/webhooks/WEBHOOK_ID/WEBHOOK_TOKEN
          - https://api.fluxer.app/v1/webhooks/WEBHOOK_ID/WEBHOOK_TOKEN
        """

        result = re.match(
            r"^https?://(api\.)?fluxer\.app/"
            r"(?:(?:v[0-9]+/)?webhooks)/"
            r"(?P<webhook_id>[0-9]+)/"
            r"(?P<webhook_token>[A-Z0-9_-]+)/?"
            r"(?P<params>\?.+)?$",
            url,
            re.I,
        )

        if result:
            return NotifyFluxer.parse_url(
                "{schema}://{webhook_id}/{webhook_token}/{params}".format(
                    schema=NotifyFluxer.secure_protocol,
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
        """Build allow_mentions + mention content."""

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
            markdown: str) -> tuple[str, list[dict[str, str]]]:
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

            fields.append({
                "name": d.get("name", "").strip("#`* \r\n\t\v"),
                "value": "```{}\n{}```".format(
                    "md" if d.get("value") else "",
                    (d.get("value").strip() + "\n" if d.get("value") else ""),
                ),
            })

        return description, fields
