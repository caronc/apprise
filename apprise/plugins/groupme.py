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

# GroupMe Bot API Notifications
#
# To use this plugin you first need a GroupMe Bot:
#  1. Sign in at https://dev.groupme.com/bots using your GroupMe account.
#  2. Click "Create Bot", choose a group, give your bot a name, and submit.
#  3. Copy the bot_id shown in the bot list -- it looks like a hexadecimal
#     string (e.g. 68ca900a7d17f9b9891a73af2a).
#
# Basic Apprise URL (text messages only):
#   groupme://{bot_id}
#
# To also send image attachments you need your personal access token:
#  1. Visit https://dev.groupme.com/ and log in.
#  2. Click on "Access Token" in the top-right corner.
#  3. Copy the displayed token.
#
# Apprise URL with attachment support:
#   groupme://{bot_id}/{access_token}
#
# The access token may also be supplied as a query parameter:
#   groupme://{bot_id}?token={access_token}
#
# API References:
#   https://dev.groupme.com/tutorials/bots
#   https://dev.groupme.com/docs/image_service

from json import dumps, loads

import requests

from ..common import NotifyFormat, NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import validate_regex
from .base import NotifyBase

# GroupMe Bot post endpoint
GROUPME_BOT_URL = "https://api.groupme.com/v3/bots/post"

# GroupMe image-service upload endpoint
GROUPME_IMAGE_URL = "https://image.groupme.com/pictures"

# HTTP error messages specific to GroupMe
GROUPME_HTTP_ERROR_MAP = {
    401: "Unauthorized - Invalid or expired access token.",
    400: "Bad Request - Malformed payload or missing required fields.",
    404: "Not Found - The specified bot_id does not exist.",
    429: "Too many requests; rate-limit exceeded.",
}


class NotifyGroupMe(NotifyBase):
    """A wrapper for GroupMe Bot Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "GroupMe"

    # The services URL
    service_url = "https://groupme.com/"

    # The default secure protocol
    secure_protocol = "groupme"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/groupme/"

    # GroupMe Bot API post endpoint
    notify_url = GROUPME_BOT_URL

    # GroupMe image-service upload endpoint
    groupme_image_url = GROUPME_IMAGE_URL

    # GroupMe does not have a native title field
    title_maxlen = 0

    # GroupMe bot messages are limited to 1000 characters
    body_maxlen = 1000

    # GroupMe image attachments are supported when an access token is
    # provided (required for the image-service upload step)
    attachment_support = True

    # GroupMe renders plain text; no markdown support in bot messages
    notify_format = NotifyFormat.TEXT

    # Define object URL templates
    templates = (
        "{schema}://{bot_id}",
        "{schema}://{bot_id}/{token}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "bot_id": {
                "name": _("Bot ID"),
                "type": "string",
                "private": True,
                "required": True,
            },
            # Access token lives in the URL path; also accepted as ?token=
            "token": {
                "name": _("Access Token"),
                "type": "string",
                "private": True,
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            # Allow bot_id to also be supplied as a query parameter
            "bot_id": {
                "alias_of": "bot_id",
            },
            # ?token= is accepted as a query-parameter alias for the
            # path-positioned token
            "token": {
                "alias_of": "token",
            },
        },
    )

    def __init__(self, bot_id, token=None, **kwargs):
        """Initialize GroupMe Object."""
        super().__init__(**kwargs)

        # Validate the Bot ID
        self.bot_id = validate_regex(bot_id, r"^[a-z0-9]+$", "i")
        if not self.bot_id:
            msg = "A GroupMe bot_id must be specified ({}).".format(bot_id)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store the optional access token (needed for image uploads)
        self.token = validate_regex(token) if token else None

        return

    def send(
        self,
        body,
        title="",
        notify_type=NotifyType.INFO,
        attach=None,
        **kwargs,
    ):
        """Perform GroupMe Bot Notification."""

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json; charset=utf-8",
        }

        # Prepare our base payload
        payload = {
            "bot_id": self.bot_id,
            "text": body,
        }

        # Handle image attachments
        groupme_attachments = []
        if attach and self.attachment_support:
            if not self.token:
                # Warn but do not abort -- text still gets sent
                self.logger.warning(
                    "GroupMe image attachments require an access token;"
                    " skipping attachments."
                )

            else:
                # Upload each attachment and collect image URLs
                for attachment in attach:
                    # Only image MIME types are accepted by GroupMe's image
                    # service; skip non-image files with a warning.
                    # Note: mimetype is None for inaccessible files, so we
                    # fall through to _upload_image() which handles that.
                    mimetype = attachment.mimetype or ""
                    if mimetype and not mimetype.startswith("image/"):
                        self.logger.warning(
                            "GroupMe image service only supports images;"
                            " skipping %s (%s).",
                            attachment.name or "attachment",
                            mimetype,
                        )
                        continue

                    image_url = self._upload_image(attachment)
                    if image_url is None:
                        # Upload failed -- abort the entire send
                        return False

                    groupme_attachments.append(
                        {
                            "type": "image",
                            "url": image_url,
                        }
                    )

        if groupme_attachments:
            # Include the uploaded image URLs in the payload
            payload["attachments"] = groupme_attachments

        self.logger.debug(
            "GroupMe POST URL: %s (cert_verify=%s)",
            self.notify_url,
            self.verify_certificate,
        )
        self.logger.debug("GroupMe Payload: %s", str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                self.notify_url,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )

            if r.status_code not in (
                requests.codes.ok,
                requests.codes.accepted,
            ):
                # We had a failure
                status_str = NotifyGroupMe.http_response_code_lookup(
                    r.status_code, GROUPME_HTTP_ERROR_MAP
                )

                self.logger.warning(
                    "Failed to send GroupMe notification:"
                    " {}{}error={}.".format(
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
                self.logger.info("Sent GroupMe notification.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred posting to GroupMe."
            )
            self.logger.debug("Socket Exception: %s", str(e))
            return False

        return True

    def _upload_image(self, attachment):
        """Upload an image attachment to GroupMe's image service.

        Returns the hosted image URL on success, or None on failure.
        """

        # Guard 1: verify the attachment is accessible before opening
        if not attachment:
            self.logger.warning(
                "Could not access GroupMe attachment %s.",
                attachment.url(privacy=True),
            )
            return None

        # Prepare the upload headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": attachment.mimetype,
            "X-Access-Token": self.token,
        }

        self.logger.debug(
            "GroupMe image upload URL: %s (cert_verify=%s)",
            self.groupme_image_url,
            self.verify_certificate,
        )

        # Always call throttle before any remote server i/o is made
        self.throttle()

        fh = None
        try:
            # Guard 2: OSError is caught by the except below
            fh = attachment.open()

            r = requests.post(
                self.groupme_image_url,
                data=fh,
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )

            if r.status_code != requests.codes.ok:
                # Upload was rejected by the image service
                status_str = NotifyGroupMe.http_response_code_lookup(
                    r.status_code, GROUPME_HTTP_ERROR_MAP
                )
                self.logger.warning(
                    "Failed to upload GroupMe image: {}{}error={}.".format(
                        status_str,
                        ", " if status_str else "",
                        r.status_code,
                    )
                )
                self.logger.debug(
                    "Response Details:\r\n%r", (r.content or b"")[:2000]
                )
                return None

            # Parse the response to extract the hosted image URL
            try:
                content = loads(r.content)

            except (AttributeError, TypeError, ValueError):
                content = {}

            # The image URL is nested under payload.url
            image_url = (
                content.get("payload", {}).get("url") if content else None
            )
            if not image_url:
                self.logger.warning(
                    "GroupMe image service returned no URL for %s.",
                    attachment.name or "attachment",
                )
                return None

            # Return the hosted image URL
            return image_url

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred uploading GroupMe image."
            )
            self.logger.debug("Socket Exception: %s", str(e))
            return None

        except OSError as e:
            self.logger.warning(
                "An I/O error occurred reading GroupMe attachment %s.",
                attachment.name or "attachment",
            )
            self.logger.debug("I/O Exception: %s", str(e))
            return None

        finally:
            # Guard 3: always close the file handle
            if fh is not None:
                fh.close()

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (self.secure_protocol, self.bot_id)

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Acquire any global URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        if self.token:
            # Emit the access token in the URL path (canonical form)
            return "{schema}://{bot_id}/{token}/?{params}".format(
                schema=self.secure_protocol,
                bot_id=self.pprint(self.bot_id, privacy, safe=""),
                token=self.pprint(self.token, privacy, safe=""),
                params=NotifyGroupMe.urlencode(params),
            )

        return "{schema}://{bot_id}/?{params}".format(
            schema=self.secure_protocol,
            bot_id=self.pprint(self.bot_id, privacy, safe=""),
            params=NotifyGroupMe.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow
        us to re-instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # bot_id is in the host position
        results["bot_id"] = NotifyGroupMe.unquote(results["host"])

        # Allow ?bot_id= to override the host-supplied bot ID
        if "bot_id" in results["qsd"] and results["qsd"]["bot_id"]:
            results["bot_id"] = NotifyGroupMe.unquote(results["qsd"]["bot_id"])

        # Token may appear as the first path segment
        entries = NotifyGroupMe.split_path(results["fullpath"])
        if entries:
            results["token"] = entries.pop(0)

        # ?token= query parameter overrides path-supplied token
        if "token" in results["qsd"] and results["qsd"]["token"]:
            results["token"] = NotifyGroupMe.unquote(results["qsd"]["token"])

        return results
