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

# Facebook Messenger notifications are sent as messages from a Facebook
# Page to the people who have messaged that Page.
#
# Steps:
#  1. Create (or use) a Facebook Page to send the notifications from.
#  2. Visit https://developers.facebook.com/apps, create a "Business" app
#     and add the Messenger product to it.
#  3. Open Messenger > Messenger API Settings, connect your Page and click
#     "Generate token".  Copy the Page access token.
#  4. Find the Page-scoped ID (PSID) of each person to message.  They must
#     have sent your Page a message first, then:
#       https://graph.facebook.com/v26.0/me/conversations
#         ?fields=participants&access_token={token}
#
# A regular message is only accepted within 24 hours of the person's last
# message to your Page.  To reach them after that, create a Utility
# template on your Page with one {{1}} parameter and add ?template= to the
# URL.  The notification body fills in {{1}}.
#
# URL syntax:
#   messenger://{token}/{psid}
#   messenger://{token}/{psid1}/{psid2}/{psidN}
#   messenger://{token}/{psid}?template={name}&lang={language}
#
# Resources:
# - https://developers.facebook.com/docs/messenger-platform/send-messages
# - https://developers.facebook.com/documentation/business-messaging/
#     messenger-platform/send-messages/utility-messages

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

# Page-scoped IDs (PSID) are made up of digits only
IS_PSID = re.compile(r"^[0-9]+$")

# Match each MIME type to its Messenger attachment type; anything else is
# sent as a file.
MESSENGER_ATTACHMENT_TYPES = (
    ("image/", "image"),
    ("audio/", "audio"),
    ("video/", "video"),
)


class NotifyMessenger(NotifyBase):
    """A wrapper for Facebook Messenger Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Facebook Messenger"

    # The services URL
    service_url = "https://www.messenger.com/"

    # The default secure protocol
    secure_protocol = "messenger"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/messenger/"

    # Facebook Graph version; bump this when Meta deprecates the current one.
    # Release schedule: https://developers.facebook.com/docs/graph-api/changelog
    graph_version = "v26.0"

    # Messages are posted on behalf of the Page that owns the token
    notify_url = "https://graph.facebook.com/{version}/me/messages"

    # Meta allows far more than this, but keep a short gap between calls
    request_rate_per_sec = 0.2

    # Images, audio, video and files can be sent
    attachment_support = True

    # Messenger messages are plain text
    notify_format = NotifyFormat.TEXT

    # There is no title field, so Apprise adds the title to the body
    title_maxlen = 0

    # Messenger accepts up to 2000 characters of text per message
    body_maxlen = 2000

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
            "template": {
                "name": _("Template Name"),
                "type": "string",
                "regex": (r"^[^\s]+$", "i"),
            },
            "language": {
                "name": _("Language"),
                "type": "string",
                "default": "en",
                "regex": (r"^[^0-9\s]+$", "i"),
            },
            "lang": {
                "alias_of": "language",
            },
        },
    )

    def __init__(
        self,
        token: Optional[str] = None,
        targets: Optional[Any] = None,
        template: Optional[str] = None,
        language: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Facebook Messenger Object."""
        super().__init__(**kwargs)

        # The Page access token that sends on behalf of the Page
        self.token = validate_regex(
            token, *self.template_tokens["token"]["regex"]
        )
        if not self.token:
            msg = f"An invalid Messenger Access Token ({token}) was specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # An optional Utility template lets us message people outside of
        # the 24 hour window.
        self.template = None
        if template:
            self.template = validate_regex(
                template, *self.template_args["template"]["regex"]
            )
            if not self.template:
                msg = (
                    "An invalid Messenger Template Name "
                    f"({template}) was specified."
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

        # The language the template was created in
        self.language = self.template_args["language"]["default"]
        if language:
            self.language = validate_regex(
                language, *self.template_args["language"]["regex"]
            )
            if not self.language:
                msg = (
                    "An invalid Messenger Template Language Code "
                    f"({language}) was specified."
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

        # Store the people we will message
        self.targets = []

        # Keep invalid targets so url() can reproduce the original URL
        self.invalid_targets = []

        for target in parse_list(targets):
            # Messenger user IDs are made up of digits only
            if not IS_PSID.match(target):
                self.logger.warning(
                    "Dropped invalid Messenger user ID (%s) specified.",
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
        messaging_type: str = "UPDATE",
        attachment: Optional[AttachBase] = None,
    ) -> bool:
        """Send one message (and optionally one file) to ``target``."""
        # Prepare our URL
        url = self.notify_url.format(version=self.graph_version)

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Accept": "application/json",
            "Authorization": f"Bearer {self.token}",
        }

        # The person receiving this message
        recipient = {"id": target}

        self.logger.debug(
            "Messenger POST URL: %s (cert_verify=%r)",
            url,
            self.verify_certificate,
        )
        self.logger.debug("Messenger Payload: %s", message)

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
                    "messaging_type": messaging_type,
                    "message": dumps(message),
                }

            else:
                # A text message is sent as JSON
                headers["Content-Type"] = "application/json"
                data = dumps(
                    {
                        "recipient": recipient,
                        "messaging_type": messaging_type,
                        "message": message,
                    }
                )

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
                status_str = NotifyMessenger.http_response_code_lookup(
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
                    "Failed to send Messenger notification to %s: "
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
                "A Connection error occurred sending Messenger "
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
        """Perform Facebook Messenger Notification."""
        if not self.targets:
            # A notification needs at least one valid target
            self.logger.warning(
                "There are no valid Messenger targets to notify."
            )
            return False

        # Check every attachment is reachable before sending anything
        attach = attach or []
        for attachment in attach:
            if not attachment:
                self.logger.warning(
                    "Could not access Messenger attachment %s.",
                    attachment.url(privacy=True),
                )
                return False

        # A template carries the body as its {{1}} parameter, otherwise
        # the body is sent as a regular text message.
        message, messaging_type = (
            (
                {
                    "template": {
                        "name": self.template,
                        "language": {"code": self.language},
                        "components": [
                            {
                                "type": "body",
                                "parameters": [
                                    {"type": "text", "text": body},
                                ],
                            }
                        ],
                    }
                },
                "UTILITY",
            )
            if self.template
            else ({"text": body}, "UPDATE")
        )

        # error tracking (used for function return)
        has_error = False

        for target in self.targets:
            # Send the text unless an earlier attempt already delivered it
            if body and not self.is_delivered(target):
                if not self._post(target, message, messaging_type):
                    # Leave this target's attachments for a retry
                    has_error = True
                    continue

                self.logger.info("Sent Messenger notification to %s.", target)

                # Delivered; a retry can safely skip this text
                self.mark_delivered(target)

            # Each attachment is uploaded and sent as its own message
            for no, attachment in enumerate(attach, start=1):
                key = ("attachment", target, no)

                # Skip a file that an earlier attempt already delivered
                if self.is_delivered(key):
                    continue

                # Pick the Messenger attachment type from the MIME type
                kind = next(
                    (
                        k
                        for p, k in MESSENGER_ATTACHMENT_TYPES
                        if attachment.mimetype.startswith(p)
                    ),
                    "file",
                )

                if not self._post(
                    target,
                    {"attachment": {"type": kind, "payload": {}}},
                    attachment=attachment,
                ):
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
        # The token identifies the sending Page
        return (self.secure_protocol, self.token)

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""
        # Only templates need a name and language
        params = (
            {"template": self.template, "lang": self.language}
            if self.template
            else {}
        )

        # Include shared notification URL parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return "{schema}://{token}/{targets}/?{params}".format(
            schema=self.secure_protocol,
            token=self.pprint(self.token, privacy, safe=""),
            targets="/".join(
                NotifyMessenger.quote(t, safe="")
                for t in self.targets + self.invalid_targets
            ),
            params=NotifyMessenger.urlencode(params),
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
        results["token"] = NotifyMessenger.unquote(results["host"])

        # Every path entry is a person to message
        results["targets"] = NotifyMessenger.split_path(results["fullpath"])

        # Support the ?token= argument
        if results["qsd"].get("token"):
            results["token"] = NotifyMessenger.unquote(results["qsd"]["token"])

            # With ?token= in use, the hostname is a target instead
            if results["host"]:
                results["targets"].insert(
                    0, NotifyMessenger.unquote(results["host"])
                )

        # Support the ?to= argument
        if results["qsd"].get("to"):
            results["targets"] += NotifyMessenger.parse_list(
                results["qsd"]["to"]
            )

        # The Utility template to send
        if results["qsd"].get("template"):
            results["template"] = NotifyMessenger.unquote(
                results["qsd"]["template"]
            )

        # The template language; ?language= wins over ?lang=
        if results["qsd"].get("lang"):
            results["language"] = NotifyMessenger.unquote(
                results["qsd"]["lang"]
            )

        if results["qsd"].get("language"):
            results["language"] = NotifyMessenger.unquote(
                results["qsd"]["language"]
            )

        return results
