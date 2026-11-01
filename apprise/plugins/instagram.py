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

# Instagram notifications are sent as direct messages from an Instagram
# professional (Business or Creator) account.
#
# Steps:
#  1. Switch your Instagram account to a professional account.
#  2. On Instagram, open Settings > Messages and story replies >
#     Message controls and turn on "Allow access to messages".
#  3. Visit https://developers.facebook.com/apps, create a "Business" app
#     and add the Instagram product to it.
#  4. Open Instagram > API setup with Instagram business login, add your
#     account and click "Generate token".  Copy the access token.
#  5. Find the Instagram-scoped ID (IGSID) of each person to message.
#     They must have sent your account a message first, then:
#       https://graph.instagram.com/v26.0/me/conversations
#         ?platform=instagram&fields=participants&access_token={token}
#
# Instagram only accepts a message within 24 hours of the person's last
# message to your account.  Messages your account sends to itself are not
# limited this way.
#
# A Facebook Page access token (it starts with EAA) for a Page linked to
# the Instagram account is also accepted.  It is sent to graph.facebook.com
# instead of graph.instagram.com.
#
# URL syntax:
#   instagram://{token}/{igsid}
#   instagram://{token}/{igsid1}/{igsid2}/{igsidN}
#
# Resources:
# - https://developers.facebook.com/docs/instagram-platform/
#     instagram-api-with-instagram-login/messaging-api
# - https://developers.facebook.com/docs/messenger-platform/instagram/
#     features/attachment-upload

from __future__ import annotations

from json import dumps, loads
import re
from typing import Any, Optional

import requests

from ..apprise_attachment import AppriseAttachment
from ..attachment.base import AttachBase
from ..common import NotifyFormat, NotifyType
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..utils.parse import parse_list, validate_regex
from .base import NotifyBase

# Instagram-scoped IDs (IGSID) are made up of digits only
IS_IGSID = re.compile(r"^[0-9]+$")

# Match each MIME type to its Instagram attachment type; anything else is
# sent as a file.
INSTAGRAM_ATTACHMENT_TYPES = (
    ("image/", "image"),
    ("audio/", "audio"),
    ("video/", "video"),
)


class NotifyInstagram(NotifyBase):
    """A wrapper for Instagram Direct Message Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Instagram"

    # The services URL
    service_url = "https://www.instagram.com/"

    # The default secure protocol
    secure_protocol = "instagram"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/instagram/"

    # Facebook Graph version; bump this when Meta deprecates the current one.
    # Release schedule: https://developers.facebook.com/docs/graph-api/changelog
    graph_version = "v26.0"

    # Messages are posted on behalf of the account that owns the token
    notify_url = "https://{host}/{version}/me/messages"

    # Instagram Login tokens and Facebook Page tokens use different hosts
    instagram_host = "graph.instagram.com"
    facebook_host = "graph.facebook.com"

    # Meta allows far more than this, but keep a short gap between calls
    request_rate_per_sec = 0.2

    # Images, audio, video and files can be sent
    attachment_support = True

    # Instagram direct messages are plain text
    notify_format = NotifyFormat.TEXT

    # There is no title field, so Apprise adds the title to the body
    title_maxlen = 0

    # Instagram accepts up to 1000 bytes of text per message
    body_maxlen = 1000

    # Define object URL templates
    templates = ("{schema}://{token}/{targets}",)

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "token": {
                "name": _("Access Token"),
                "type": "string",
                "private": True,
                "required": True,
                "regex": (r"^[a-z0-9_-]+$", "i"),
            },
            "target_user": {
                "name": _("Target User ID"),
                "type": "string",
                "regex": (r"^[0-9]+$", ""),
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
            "token": {
                "alias_of": "token",
            },
            "to": {
                "alias_of": "targets",
            },
        },
    )

    def __init__(
        self,
        token: Optional[str] = None,
        targets: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Instagram Object."""
        super().__init__(**kwargs)

        # The access token that sends on behalf of the Instagram account
        self.token = validate_regex(
            token, *self.template_tokens["token"]["regex"]
        )
        if not self.token:
            msg = f"An invalid Instagram Access Token ({token}) was specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Facebook Page tokens start with EAA and must use the Facebook host
        self.api_host = (
            self.facebook_host
            if self.token.startswith("EAA")
            else self.instagram_host
        )

        # Store the people we will message
        self.targets = []

        # Keep invalid targets so url() can reproduce the original URL
        self.invalid_targets = []

        for target in parse_list(targets):
            # Instagram user IDs are made up of digits only
            if not IS_IGSID.match(target):
                self.logger.warning(
                    "Dropped invalid Instagram user ID (%s) specified.",
                    target,
                )
                self.invalid_targets.append(target)
                continue

            # A valid person to message
            self.targets.append(target)

    def _post(
        self,
        target: str,
        message: dict[str, Any],
        attachment: Optional[AttachBase] = None,
    ) -> bool:
        """Send one message (and optionally one file) to ``target``."""
        # Prepare our URL
        url = self.notify_url.format(
            host=self.api_host, version=self.graph_version
        )

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Accept": "application/json",
            "Authorization": f"Bearer {self.token}",
        }

        # The person receiving this message
        recipient = {"id": target}

        self.logger.debug(
            "Instagram POST URL: %s (cert_verify=%r)",
            url,
            self.verify_certificate,
        )
        self.logger.debug("Instagram Payload: %s", message)

        # Always call throttle before any remote server i/o is made
        self.throttle()

        files = None
        try:
            if attachment:
                # A file is uploaded alongside the message as form data.
                # requests sets the multipart Content-Type for us.
                files = {
                    "filedata": (
                        attachment.name or "attachment.dat",
                        attachment.open(),
                        attachment.mimetype,
                    ),
                }
                data = {
                    "recipient": dumps(recipient),
                    "message": dumps(message),
                }

            else:
                # A text message is sent as JSON
                headers["Content-Type"] = "application/json"
                data = dumps({"recipient": recipient, "message": message})

            r = requests.post(
                url,
                data=data,
                headers=headers,
                files=files,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )

            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = NotifyInstagram.http_response_code_lookup(
                    r.status_code
                )

                # Meta explains the failure in an error object when it can
                try:
                    error = loads(r.content)["error"]
                    status_str = error.get("message") or status_str

                except (AttributeError, TypeError, ValueError, KeyError):
                    # The response was empty, not JSON, or had no error
                    # object, so keep the HTTP status description.
                    pass

                self.logger.warning(
                    "Failed to send Instagram notification to %s: "
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
                return False

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending Instagram "
                "notification to %s.",
                target,
            )
            self.logger.debug("Socket Exception: %s", str(e))

            # Mark our failure
            return False

        except OSError as e:
            self.logger.warning(
                "An I/O error occurred while reading %s.",
                attachment.name or "attachment",
            )
            self.logger.debug("I/O Exception: %s", str(e))

            # Mark our failure
            return False

        finally:
            # Close the file whether we succeeded or failed
            if files:
                files["filedata"][1].close()

        return True

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        attach: Optional[AppriseAttachment] = None,
        **kwargs: Any,
    ) -> bool:
        """Perform Instagram Notification."""
        if not self.targets:
            # A notification needs at least one valid target
            self.logger.warning(
                "There are no valid Instagram targets to notify."
            )
            return False

        # Check every attachment is reachable before sending anything
        attach = attach or []
        for attachment in attach:
            if not attachment:
                self.logger.warning(
                    "Could not access Instagram attachment %s.",
                    attachment.url(privacy=True),
                )
                return False

        # error tracking (used for function return)
        has_error = False

        for target in self.targets:
            # Send the text unless an earlier attempt already delivered it
            if body and not self.is_delivered(target):
                if not self._post(target, {"text": body}):
                    # Leave this target's attachments for a retry
                    has_error = True
                    continue

                self.logger.info("Sent Instagram notification to %s.", target)

                # Delivered; a retry can safely skip this text
                self.mark_delivered(target)

            # Each attachment is uploaded and sent as its own message
            for no, attachment in enumerate(attach, start=1):
                key = ("attachment", target, no)

                # Skip a file that an earlier attempt already delivered
                if self.is_delivered(key):
                    continue

                # Pick the Instagram attachment type from the MIME type
                kind = next(
                    (
                        k
                        for p, k in INSTAGRAM_ATTACHMENT_TYPES
                        if attachment.mimetype.startswith(p)
                    ),
                    "file",
                )

                message = {"attachment": {"type": kind, "payload": {}}}
                if not self._post(target, message, attachment=attachment):
                    # Leave the remaining attachments for a retry
                    has_error = True
                    break

                # Delivered; a retry can safely skip this file
                self.mark_delivered(key)

        return not has_error

    def __len__(self) -> int:
        """Returns the number of targets associated with this notification."""
        # Always return at least 1 so the framework counts this instance
        return max(1, len(self.targets))

    @property
    def url_identifier(self) -> tuple[Any, ...]:
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        # The token identifies the sending account
        return (self.secure_protocol, self.token)

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""
        # Include shared notification URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        return "{schema}://{token}/{targets}/?{params}".format(
            schema=self.secure_protocol,
            token=self.pprint(self.token, privacy, safe=""),
            targets="/".join(
                NotifyInstagram.quote(t, safe="")
                for t in self.targets + self.invalid_targets
            ),
            params=NotifyInstagram.urlencode(params),
        )

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # The access token is stored in the hostname
        results["token"] = NotifyInstagram.unquote(results["host"])

        # Every path entry is a person to message
        results["targets"] = NotifyInstagram.split_path(results["fullpath"])

        # Support the ?token= argument
        if results["qsd"].get("token"):
            results["token"] = NotifyInstagram.unquote(results["qsd"]["token"])

            # With ?token= in use, the hostname is a target instead
            if results["host"]:
                results["targets"].insert(
                    0, NotifyInstagram.unquote(results["host"])
                )

        # Support the ?to= argument
        if results["qsd"].get("to"):
            results["targets"] += NotifyInstagram.parse_list(
                results["qsd"]["to"]
            )

        return results
