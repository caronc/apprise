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

# To use this service you will need an 800.com account
#
#  1. Visit https://www.800.com and sign in or create an account.
#  2. Go to User Settings (top-right avatar -> Settings).
#  3. In the API section, click "Generate Token".
#  4. Copy the token immediately -- it is only displayed once.
#
#  Your Apprise URL should be assembled as:
#    eight00com://TOKEN@FromPhoneNo
#    eight00com://TOKEN@FromPhoneNo/ToPhoneNo
#    eight00com://TOKEN@FromPhoneNo/ToPhoneNo1/ToPhoneNo2
#
#  Where:
#    TOKEN       : Your 800.com Personal Access Token
#    FromPhoneNo : Your text-enabled 800.com number (e.g. 8005551234)
#    ToPhoneNo   : Recipient phone number(s)
#
# The API also supports MMS (picture messaging).  Apprise will
# automatically send any provided attachments as MMS when possible.
#
# API Reference:
#   https://api.800.com/docs

from json import dumps

import requests

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import is_phone_no, parse_phone_no, validate_regex
from .base import NotifyBase

# Extend HTTP Error Messages
EIGHT00COM_HTTP_ERROR_MAP = {
    401: "Unauthorized - Invalid or missing Bearer Token.",
    422: "Validation Error - Check sender/recipient number format.",
    429: "Too many requests - Rate limit exceeded.",
}


class NotifyEight00com(NotifyBase):
    """A wrapper for 800.com SMS/MMS Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "800.com"

    # The services URL
    service_url = "https://www.800.com"

    # All notification requests are sent over HTTPS
    secure_protocol = "eight00com"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/eight00com/"

    # 800.com REST API endpoint for outbound messages
    notify_url = "https://api.800.com/message"

    # The maximum SMS body length (800.com supports long-form texts
    # up to 600 characters)
    body_maxlen = 600

    # A title cannot be used for SMS messages; setting this to zero
    # causes any title to be prepended to the body automatically.
    title_maxlen = 0

    # 800.com supports MMS (picture messaging / attachments)
    attachment_support = True

    # Define object URL templates
    templates = (
        "{schema}://{token}@{from_phone}",
        "{schema}://{token}@{from_phone}/{targets}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "token": {
                "name": _("API Token"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "from_phone": {
                "name": _("From Phone No"),
                "type": "string",
                "regex": (r"^\+?[0-9\s)(+-]+$", "i"),
                "map_to": "source",
                "required": True,
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
            "from": {
                "name": _("From Phone No"),
                "type": "string",
                "map_to": "source",
            },
            "to": {
                "alias_of": "targets",
            },
        },
    )

    def __init__(self, token=None, source=None, targets=None, **kwargs):
        """Initialize 800.com Object."""
        super().__init__(**kwargs)

        # Validate our Personal Access Token
        self.token = validate_regex(token)
        if not self.token:
            msg = "An 800.com Personal Access Token must be specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Validate the from (source) phone number
        result = is_phone_no(source)
        if not result:
            msg = "The 800.com from phone # ({}) is invalid.".format(source)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store our source number as digits only
        self.source = result["full"]

        # Parse our targets list
        self.targets = []

        # Track if we encountered any error parsing targets
        has_error = False
        for target in parse_phone_no(targets):
            # Validate each target phone number
            result = is_phone_no(target)
            if result:
                self.targets.append(result["full"])
                continue

            has_error = True
            self.logger.warning(
                "Dropped invalid 800.com phone # (%s).",
                target,
            )

        if not targets and not has_error:
            # Default: send to ourselves when no target is provided
            self.targets.append(self.source)

        return

    def send(
        self,
        body,
        title="",
        notify_type=NotifyType.INFO,
        attach=None,
        **kwargs,
    ):
        """Perform 800.com SMS/MMS Notification."""

        # Ensure we have at least one target
        if not self.targets:
            self.logger.warning("No 800.com targets to notify.")
            return False

        # Prepare our authorization header (shared by SMS and MMS)
        headers = {
            "User-Agent": self.app_id,
            "Authorization": "Bearer {}".format(self.token),
        }

        # Error tracking variable
        has_error = False

        # Work through a copy so the original list is preserved
        targets = list(self.targets)
        while targets:
            # Pop the next recipient
            target = targets.pop(0)

            # Build the E.164-style sender and recipient strings
            sender = "+{}".format(self.source)
            recipient = "+{}".format(target)

            self.logger.debug(
                "800.com POST URL: %s (cert_verify=%s)",
                self.notify_url,
                self.verify_certificate,
            )

            if attach and self.attachment_support:
                # Send as MMS with attachment(s)
                if not self._send_mms(
                    sender, recipient, body, attach, headers
                ):
                    has_error = True

            else:
                # Send as a plain SMS
                if not self._send_sms(sender, recipient, body, headers):
                    has_error = True

        return not has_error

    def _send_sms(self, sender, recipient, body, headers):
        """Send a plain text SMS via the 800.com REST API."""

        # Prepare our JSON payload
        payload = {
            "sender": sender,
            "recipient": recipient,
            "message": body,
        }

        # Copy headers and add JSON content type
        sms_headers = dict(headers)
        sms_headers["Content-Type"] = "application/json"

        self.logger.debug("800.com SMS Payload: %s", payload)

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                self.notify_url,
                data=dumps(payload),
                headers=sms_headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )

            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = NotifyEight00com.http_response_code_lookup(
                    r.status_code, EIGHT00COM_HTTP_ERROR_MAP
                )
                self.logger.warning(
                    "Failed to send 800.com SMS to %s: %s%serror=%s.",
                    recipient,
                    status_str,
                    ", " if status_str else "",
                    r.status_code,
                )
                self.logger.debug(
                    "Response Details:\r\n%r",
                    (r.content or b"")[:2000],
                )
                return False

            else:
                self.logger.info("Sent 800.com SMS to %s.", recipient)

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending 800.com SMS to %s.",
                recipient,
            )
            self.logger.debug("Socket Exception: %s", str(e))
            return False

        return True

    def _send_mms(self, sender, recipient, body, attach, headers):
        """Send an MMS with one or more attachments via the 800.com API.

        Uses Pattern B (multi-file multipart/form-data).
        """

        # Accumulate open file handles for cleanup in the finally block
        handles = []
        files = []
        attach_ok = True

        try:
            for attachment in attach:
                # Guard 1: verify the attachment is accessible
                if not attachment:
                    self.logger.warning(
                        "Could not access 800.com attachment %s.",
                        attachment.url(privacy=True),
                    )
                    attach_ok = False
                    break

                # Guard 2: catch I/O errors when opening the file
                try:
                    handle = attachment.open()
                except OSError as exc:
                    self.logger.warning(
                        "An I/O error occurred reading 800.com attachment %s.",
                        attachment.name,
                    )
                    self.logger.debug("I/O Exception: %s", str(exc))
                    attach_ok = False
                    break

                # Register handle immediately so finally closes it
                handles.append(handle)
                files.append(
                    (
                        "media[]",
                        (
                            attachment.name,
                            handle,
                            attachment.mimetype,
                        ),
                    )
                )

            if not attach_ok:
                # Bail early; finally block will close any open handles
                return False

            # Prepare the multipart form fields.
            # Do NOT set Content-Type -- requests sets the multipart
            # boundary header automatically when files is not None.
            data = {
                "sender": sender,
                "recipient": recipient,
                "message": body,
            }

            self.logger.debug("800.com MMS data: %s", data)

            # Always call throttle before any remote server i/o is made
            self.throttle()

            r = requests.post(
                self.notify_url,
                data=data,
                headers=headers,
                files=files,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )

            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = NotifyEight00com.http_response_code_lookup(
                    r.status_code, EIGHT00COM_HTTP_ERROR_MAP
                )
                self.logger.warning(
                    "Failed to send 800.com MMS to %s: %s%serror=%s.",
                    recipient,
                    status_str,
                    ", " if status_str else "",
                    r.status_code,
                )
                self.logger.debug(
                    "Response Details:\r\n%r",
                    (r.content or b"")[:2000],
                )
                return False

            else:
                self.logger.info("Sent 800.com MMS to %s.", recipient)

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending 800.com MMS to %s.",
                recipient,
            )
            self.logger.debug("Socket Exception: %s", str(e))
            return False

        finally:
            # Guard 3: close every file handle regardless of outcome
            for handle in handles:
                handle.close()

        return True

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (self.secure_protocol, self.source, self.token)

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified
        arguments."""

        # Prepare our standard parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        # Omit the target list when the only target is ourselves
        targets = (
            []
            if len(self.targets) == 1 and self.targets[0] == self.source
            else self.targets
        )

        return "{schema}://{token}@{source}/{targets}?{params}".format(
            schema=self.secure_protocol,
            token=self.pprint(self.token, privacy, safe=""),
            source=self.source,
            targets="/".join(
                NotifyEight00com.quote(x, safe="+") for x in targets
            ),
            params=NotifyEight00com.urlencode(params),
        )

    def __len__(self):
        """Returns the number of targets associated with this
        notification."""
        return len(self.targets) if self.targets else 1

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow
        us to re-instantiate this object."""

        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            return results

        # Support ?from= to specify the source number separately,
        # in which case the hostname becomes an additional target.
        if "from" in results["qsd"] and len(results["qsd"]["from"]):
            results["source"] = NotifyEight00com.unquote(
                results["qsd"]["from"]
            )
            results["targets"] = [
                *NotifyEight00com.parse_phone_no(results["host"]),
                *NotifyEight00com.split_path(results["fullpath"]),
            ]

        else:
            # Hostname is the source (from) phone number
            results["source"] = NotifyEight00com.unquote(results["host"])
            # Path entries are target phone numbers
            results["targets"] = NotifyEight00com.split_path(
                results["fullpath"]
            )

        # Support ?to= as an alias for targets
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifyEight00com.parse_phone_no(
                results["qsd"]["to"]
            )

        # Support ?token= to override the token in the URL user field
        if "token" in results["qsd"] and len(results["qsd"]["token"]):
            results["token"] = NotifyEight00com.unquote(
                results["qsd"]["token"]
            )

        else:
            # Token lives in the user position of the URL
            results["token"] = NotifyEight00com.unquote(results["user"] or "")

        return results
