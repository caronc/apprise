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

# Nextcloud Talk supports two ways to post a message:
#  1. As a user, with a username and an app password:
#     nctalks://{user}:{password}@{host}/{room_token}
#
#  2. As a bot (Nextcloud Talk 17.1 / Nextcloud 27.1 or newer).  An admin
#     installs the bot with a shared secret and the "response" feature:
#       occ talk:bot:install --feature response \
#           "Apprise" "{secret}" "https://localhost"
#     then enables it in each conversation it should post to.  Use:
#     nctalks://{host}/{room_token}?secret={secret}
#
# Resources:
# - https://nextcloud-talk.readthedocs.io/en/latest/bots/

from __future__ import annotations

from hashlib import sha256
import hmac
from json import dumps
import secrets
from typing import Any, Optional

import requests

from ..common import NotifyType
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import parse_bool, parse_list
from .base import NotifyBase


class NotifyNextcloudTalk(NotifyBase):
    """A wrapper for Nextcloud Talk Notifications."""

    # The default descriptive name associated with the Notification
    service_name = _("Nextcloud Talk")

    # The services URL
    service_url = "https://nextcloud.com/talk"

    # Insecure protocol (for those self hosted requests)
    protocol = "nctalk"

    # The default protocol (this is secure for notica)
    secure_protocol = "nctalks"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/nextcloudtalk/"

    # Nextcloud title length
    title_maxlen = 255

    # Defines the maximum allowable characters per message.
    body_maxlen = 32000

    # The 32000 characters above defined by the body_maxlen include that of
    # the title.  Setting this to True ensures overflow options behave
    # properly
    overflow_amalgamate_title = True

    # Define object templates
    templates = (
        "{schema}://{user}:{password}@{host}/{targets}",
        "{schema}://{user}:{password}@{host}:{port}/{targets}",
        "{schema}://{host}/{targets}?secret={secret}",
        "{schema}://{host}:{port}/{targets}?secret={secret}",
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
            "user": {
                "name": _("Username"),
                "type": "string",
                "required": True,
            },
            "password": {
                "name": _("Password"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "secret": {
                "name": _("Secret"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "target_room_id": {
                "name": _("Room ID"),
                "type": "string",
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
            "secret": {"alias_of": "secret"},
            "silent": {
                "name": _("Silent Notification"),
                "type": "bool",
                "default": False,
            },
            "url_prefix": {
                "name": _("URL Prefix"),
                "type": "string",
            },
        },
    )

    # Define any kwargs we're using
    template_kwargs = {
        "headers": {
            "name": _("HTTP Header"),
            "prefix": "+",
        },
    }

    def __init__(
        self,
        targets: Optional[Any] = None,
        headers: Optional[dict[str, str]] = None,
        url_prefix: Optional[str] = None,
        secret: Optional[str] = None,
        silent: Optional[bool] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Nextcloud Talk Object."""
        super().__init__(**kwargs)

        # A bot secret switches us to the bot API; otherwise a user and
        # password are required
        self.secret = secret
        if not self.secret and (self.user is None or self.password is None):
            msg = "Specify a Nextcloud Talk user and password or bot secret."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Store our targets
        self.targets = parse_list(targets)

        # Silent messages do not trigger chat notifications
        self.silent = (
            self.template_args["silent"]["default"]
            if silent is None
            else bool(silent)
        )

        # Support URL Prefix
        self.url_prefix = "" if not url_prefix else url_prefix.strip("/")

        self.headers = {}
        if headers:
            # Store our extra headers
            self.headers.update(headers)

        return

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        **kwargs: Any,
    ) -> bool:
        """Perform Nextcloud Talk Notification."""

        if len(self.targets) == 0:
            # There were no services to notify
            self.logger.warning(
                "There were no Nextcloud Talk targets to notify."
            )
            return False

        # Prepare our Header
        headers = {
            "User-Agent": self.app_id,
            "OCS-APIRequest": "true",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        # Apply any/all header over-rides defined
        headers.update(self.headers)

        # error tracking (used for function return)
        has_error = False

        # Create a copy of the targets list
        targets = list(self.targets)
        while len(targets):
            target = targets.pop(0)

            # Skip a target that already accepted this message so
            # a retry does not deliver it twice.
            if self.is_delivered(target):
                continue

            # Prepare our Payload
            if not body:
                payload = {
                    "message": title if title else self.app_desc,
                }
            else:
                payload = {
                    "message": (
                        title + "\r\n" + body
                        if title
                        else self.app_desc + "\r\n" + body
                    ),
                }

            # Only send the silent flag when it is used
            if self.silent:
                payload["silent"] = True

            # Nextcloud Talk URL
            notify_url = (
                "{schema}://{host}{url_prefix}"
                "/ocs/v2.php/apps/spreed/api/v1/{endpoint}"
            )

            notify_url = notify_url.format(
                schema="https" if self.secure else "http",
                host=(
                    self.host
                    if not isinstance(self.port, int)
                    else f"{self.host}:{self.port}"
                ),
                url_prefix=f"/{self.url_prefix}" if self.url_prefix else "",
                endpoint=(
                    f"bot/{target}/message"
                    if self.secret
                    else f"chat/{target}"
                ),
            )

            self.logger.debug(
                "Nextcloud Talk POST URL: %s (cert_verify=%r)",
                notify_url,
                self.verify_certificate,
            )
            self.logger.debug("Nextcloud Talk Payload: %s", payload)

            if self.secret:
                # Bots sign each message with the shared secret.  The
                # signature covers the random value followed by the
                # message text (not the JSON payload).
                random = secrets.token_hex(32)
                headers["X-Nextcloud-Talk-Bot-Random"] = random
                headers["X-Nextcloud-Talk-Bot-Signature"] = hmac.new(
                    self.secret.encode("utf-8"),
                    (random + payload["message"]).encode("utf-8"),
                    sha256,
                ).hexdigest()

            # Always call throttle before any remote server i/o is made
            self.throttle()

            try:
                r = requests.post(
                    notify_url,
                    data=dumps(payload),
                    headers=headers,
                    # Bots authenticate with the signature headers
                    auth=None if self.secret else (self.user, self.password),
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                    allow_redirects=self.redirects,
                )
                if r.status_code not in (
                    requests.codes.created,
                    requests.codes.ok,
                ):
                    # We had a problem
                    status_str = NotifyNextcloudTalk.http_response_code_lookup(
                        r.status_code
                    )

                    self.logger.warning(
                        "Failed to send Nextcloud Talk notification:"
                        "{}{}error={}.".format(
                            status_str,
                            ", " if status_str else "",
                            r.status_code,
                        )
                    )

                    self.logger.debug(
                        "Response Details:\r\n%r", (r.content or b"")[:2000]
                    )

                    # track our failure
                    has_error = True
                    continue

                else:
                    self.logger.info("Sent Nextcloud Talk notification.")

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending Nextcloud Talk "
                    "notification."
                )
                self.logger.debug(f"Socket Exception: {e!s}")

                # track our failure
                has_error = True
                continue

            # Delivered; a retry can safely skip this target.
            self.mark_delivered(target)

        return not has_error

    @property
    def url_identifier(self) -> tuple[Any, ...]:
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        # A bot connection is identified by its secret alone.  Any user
        # and password are ignored in bot mode and dropped by url().
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.user if not self.secret else None,
            self.password if not self.secret else None,
            self.host,
            self.port,
            self.secret,
        )

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # Our default set of parameters
        params = {
            "silent": "yes" if self.silent else "no",
        }
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Append our headers into our parameters
        params.update({f"+{k}": v for k, v in self.headers.items()})
        if self.url_prefix:
            params["url_prefix"] = self.url_prefix

        # Store our bot secret (urlencode() quotes it for us)
        if self.secret:
            params["secret"] = self.pprint(
                self.secret, privacy, mode=PrivacyMode.Secret, quote=False
            )

        # Determine Authentication
        auth = (
            ""
            if self.secret
            else "{user}:{password}@".format(
                user=NotifyNextcloudTalk.quote(self.user, safe=""),
                password=self.pprint(
                    self.password, privacy, mode=PrivacyMode.Secret, safe=""
                ),
            )
        )

        default_port = 443 if self.secure else 80
        return "{schema}://{auth}{hostname}{port}/{targets}?{params}".format(
            schema=self.secure_protocol if self.secure else self.protocol,
            auth=auth,
            # never encode hostname since we're expecting it to be a
            # valid one
            hostname=self.host,
            port=(
                ""
                if self.port is None or self.port == default_port
                else f":{self.port}"
            ),
            targets="/".join(
                [NotifyNextcloudTalk.quote(x) for x in self.targets]
            ),
            params=NotifyNextcloudTalk.urlencode(params),
        )

    def __len__(self):
        """Returns the number of targets associated with this notification."""
        targets = len(self.targets)
        return targets if targets else 1

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""

        results = NotifyBase.parse_url(url)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Fetch our targets
        results["targets"] = NotifyNextcloudTalk.split_path(
            results["fullpath"]
        )

        # Support the bot secret; query values arrive already unquoted
        if "secret" in results["qsd"]:
            results["secret"] = results["qsd"]["secret"]

        # Support silent notifications
        results["silent"] = parse_bool(results["qsd"].get("silent", False))

        # Support URL Prefixes
        if "url_prefix" in results["qsd"] and len(
            results["qsd"]["url_prefix"]
        ):
            results["url_prefix"] = NotifyNextcloudTalk.unquote(
                results["qsd"]["url_prefix"]
            )

        # Add our headers that the user can potentially over-ride if they wish
        # to to our returned result set and tidy entries by unquoting them
        results["headers"] = {
            NotifyNextcloudTalk.unquote(x): NotifyNextcloudTalk.unquote(y)
            for x, y in results["qsd+"].items()
        }

        return results
