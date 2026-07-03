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
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
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

# SerwerSMS is a Polish SMS gateway service available at https://serwersms.pl
#
# To use this service you will need a SerwerSMS account:
#  1. Visit https://serwersms.pl and sign up for an account.
#  2. Note your login username and password from your account settings.
#  3. Configure your sender name in the SerwerSMS panel (up to 11
#     alphanumeric characters, pre-approved by the carrier).
#
# You can send to individual phone numbers or to contact groups defined
# in your SerwerSMS account:
#  - Phone targets use a leading + followed by the country code and number.
#  - Group targets use a leading # followed by the numeric group ID.
#
# When an attachment is provided, the message is automatically sent as MMS
# via the send_mms endpoint instead of the standard send_sms endpoint.
#
# Your Apprise URLs should be assembled as:
#   serwersms://username:password@SenderName/+48123456789
#   serwersms://username:password@SenderName/+48123456789/%23123
#
# Where %23 is the URL-encoded form of # (the group prefix).
#
# API Reference: https://api2.serwersms.pl/

from itertools import chain
from json import dumps, loads
import re

import requests

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import (
    is_phone_no,
    parse_list,
    validate_regex,
)
from .base import NotifyBase

# Sender validation regex is defined in template_tokens["sender"]["regex"].

# Matches a group ID target, optionally prefixed with # or %23
SERWERSMS_GROUP_REGEX = re.compile(
    r"^\s*(\#|\%23)(?P<group>[0-9]+)\s*$",
    re.I,
)


class SerwerSMSCategory:
    """Tracks the target type for a SerwerSMS destination."""

    # Individual phone number delivery
    PHONE = "phone"

    # Contact group delivery
    GROUP = "group"


class NotifySerwerSMS(NotifyBase):
    """A wrapper for SerwerSMS Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "SerwerSMS"

    # The services URL
    service_url = "https://serwersms.pl"

    # All notification requests are sent over HTTPS
    secure_protocol = "serwersms"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/serwersms/"

    # SerwerSMS SMS API endpoint
    notify_url = "https://api2.serwersms.pl/messages/send_sms"

    # SerwerSMS MMS API endpoint (used automatically when attachments
    # are provided)
    notify_url_mms = "https://api2.serwersms.pl/messages/send_mms"

    # The maximum length of an SMS body
    body_maxlen = 160

    # A title can not be used for SMS messages; any title will be
    # prepended into the body automatically by the framework.
    title_maxlen = 0

    # Attachments are supported; the plugin switches to MMS automatically
    # when one is provided
    attachment_support = True

    # Define object URL templates
    templates = (
        "{schema}://{user}:{password}@{sender}/{targets}",
        "{schema}://{user}:{password}@{sender}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
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
            "sender": {
                "name": _("Sender Name"),
                "type": "string",
                "required": True,
                "regex": (r"^[a-z0-9][a-z0-9 _-]{0,10}$", "i"),
            },
            "target_phone": {
                "name": _("Target Phone No"),
                "type": "string",
                "prefix": "+",
                "regex": (r"^[0-9\s)(+-]+$", "i"),
                "map_to": "targets",
            },
            "target_group": {
                "name": _("Target Group ID"),
                "type": "string",
                "prefix": "#",
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
            "to": {
                "alias_of": "targets",
            },
            "sender": {
                "alias_of": "sender",
            },
            "from": {
                "alias_of": "sender",
            },
        },
    )

    def __init__(self, sender=None, targets=None, **kwargs):
        """Initialize SerwerSMS Object."""
        super().__init__(**kwargs)

        # Validate username
        if not self.user:
            msg = "A SerwerSMS username must be specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Validate password
        if not self.password:
            msg = "A SerwerSMS password must be specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Validate sender name
        self.sender = validate_regex(
            sender,
            *self.template_tokens["sender"]["regex"],
        )
        if not self.sender:
            msg = "A SerwerSMS sender name ({}) is invalid.".format(sender)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Parse our targets into phones and groups
        self.target_phones = []
        self.target_groups = []

        # Preserve invalid entries for URL round-trip fidelity
        self.invalid_targets = []

        for target in parse_list(targets):
            # Check for group ID first (prefixed with # or %23)
            result = SERWERSMS_GROUP_REGEX.match(target)
            if result:
                # Store the numeric group ID
                self.target_groups.append(result.group("group"))
                continue

            # Try as a phone number
            result = is_phone_no(target)
            if result:
                self.target_phones.append(result["full"])
                continue

            # Target did not match any known format
            self.logger.warning(
                "Dropped invalid SerwerSMS target: %s.", target
            )
            self.invalid_targets.append(target)

        return

    def send(
        self,
        body,
        title="",
        notify_type=NotifyType.INFO,
        attach=None,
        **kwargs,
    ):
        """Perform SerwerSMS SMS/MMS Notification."""

        # Abort early when there is nothing to deliver
        if not self.target_phones and not self.target_groups:
            self.logger.warning("There are no SerwerSMS targets to notify.")
            return False

        # error tracking variable
        has_error = False

        # Auto-select MMS when attachments are provided
        use_mms = bool(attach and self.attachment_support and len(attach))

        # Prepare our headers; Content-Type is omitted for MMS because
        # requests sets it automatically with the multipart boundary
        headers = {"User-Agent": self.app_id}
        if not use_mms:
            headers["Content-Type"] = "application/json"

        # Base fields shared by every API call
        base_fields = {
            "username": self.user,
            "password": self.password,
            "text": body,
            "sender": self.sender,
        }

        # Build a unified call list: (display_label, target_payload_field)
        # Each entry is (label_str, {extra_field: value})
        calls = [
            ("+{}".format(p), {"phone": "+{}".format(p)})
            for p in self.target_phones
        ] + [
            ("group {}".format(g), {"group_id": g}) for g in self.target_groups
        ]

        for label, extra in calls:
            # Assemble the per-target fields
            fields = dict(base_fields)
            fields.update(extra)

            # Always call throttle before any remote server i/o is made
            self.throttle()

            if use_mms:
                # Delegate to the MMS helper
                if not self._send_mms(label, fields, attach, headers):
                    has_error = True
                continue

            # Debug logging
            self.logger.debug(
                "SerwerSMS POST URL: %s (cert_verify=%s)",
                self.notify_url,
                self.verify_certificate,
            )
            self.logger.debug("SerwerSMS Payload: %s", fields)

            try:
                r = requests.post(
                    self.notify_url,
                    data=dumps(fields),
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                    allow_redirects=self.redirects,
                )

                if r.status_code != requests.codes.ok:
                    # HTTP-level failure
                    status_str = NotifyBase.http_response_code_lookup(
                        r.status_code
                    )
                    self.logger.warning(
                        "Failed to send SerwerSMS notification to {}: "
                        "{}{}error={}.".format(
                            label,
                            status_str,
                            ", " if status_str else "",
                            r.status_code,
                        )
                    )
                    self.logger.debug(
                        "Response Details:\r\n%r",
                        (r.content or b"")[:2000],
                    )

                    # Mark our failure
                    has_error = True
                    continue

                # Parse JSON response body
                try:
                    content = loads(r.content)
                    if not isinstance(content, dict):
                        content = {}

                except (AttributeError, TypeError, ValueError):
                    content = {}
                    self.logger.debug(
                        "Failed to parse SerwerSMS JSON response; body: %r",
                        (r.content or b"")[:2000],
                    )

                if not content.get("success"):
                    # API-level failure reported in the response body
                    error = content.get("error", {})
                    if error:
                        self.logger.warning(
                            "Failed to send SerwerSMS notification to {}: "
                            "API error {} - {}.".format(
                                label,
                                error.get("code", "unknown"),
                                error.get("message", ""),
                            )
                        )

                    else:
                        self.logger.warning(
                            "Failed to send SerwerSMS notification to {}: "
                            "unexpected API response.".format(label)
                        )

                    # Mark our failure
                    has_error = True
                    continue

                self.logger.info("Sent SerwerSMS notification to %s.", label)

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending SerwerSMS "
                    "notification to %s.",
                    label,
                )
                self.logger.debug("Socket Exception: %s", str(e))

                # Mark our failure
                has_error = True
                continue

        return not has_error

    def _send_mms(self, label, fields, attach, headers):
        """Send MMS via the SerwerSMS MMS endpoint."""

        # Build attachment file handles and multipart file list
        handles = []
        files = []
        attach_ok = True

        for attachment in attach:
            # Guard 1: accessibility check
            if not attachment:
                attach_ok = False
                break

            # Guard 2: I/O error check
            try:
                handle = attachment.open()

            except OSError:
                attach_ok = False
                break

            handles.append(handle)
            files.append(
                ("file", (attachment.name, handle, attachment.mimetype))
            )

        try:
            if not attach_ok:
                self.logger.warning(
                    "Failed to send SerwerSMS MMS notification to %s; "
                    "could not access attachment.",
                    label,
                )
                return False

            # Debug logging
            self.logger.debug(
                "SerwerSMS MMS POST URL: %s (cert_verify=%s)",
                self.notify_url_mms,
                self.verify_certificate,
            )
            self.logger.debug("SerwerSMS MMS Fields: %s", fields)

            try:
                r = requests.post(
                    self.notify_url_mms,
                    data=fields,
                    headers=headers,
                    files=files,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                    allow_redirects=self.redirects,
                )

                if r.status_code != requests.codes.ok:
                    # HTTP-level failure
                    status_str = NotifyBase.http_response_code_lookup(
                        r.status_code
                    )
                    self.logger.warning(
                        "Failed to send SerwerSMS MMS notification "
                        "to {}: {}{}error={}.".format(
                            label,
                            status_str,
                            ", " if status_str else "",
                            r.status_code,
                        )
                    )
                    self.logger.debug(
                        "Response Details:\r\n%r",
                        (r.content or b"")[:2000],
                    )
                    return False

                # Parse JSON response body
                try:
                    content = loads(r.content)
                    if not isinstance(content, dict):
                        content = {}

                except (AttributeError, TypeError, ValueError):
                    content = {}
                    self.logger.debug(
                        "Failed to parse SerwerSMS MMS JSON response; "
                        "body: %r",
                        (r.content or b"")[:2000],
                    )

                if not content.get("success"):
                    # API-level failure reported in the response body
                    error = content.get("error", {})
                    if error:
                        self.logger.warning(
                            "Failed to send SerwerSMS MMS notification "
                            "to {}: API error {} - {}.".format(
                                label,
                                error.get("code", "unknown"),
                                error.get("message", ""),
                            )
                        )

                    else:
                        self.logger.warning(
                            "Failed to send SerwerSMS MMS notification "
                            "to {}: unexpected API response.".format(label)
                        )

                    return False

                self.logger.info(
                    "Sent SerwerSMS MMS notification to %s.", label
                )
                return True

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending SerwerSMS MMS "
                    "notification to %s.",
                    label,
                )
                self.logger.debug("Socket Exception: %s", str(e))
                return False

        finally:
            # Always close file handles
            for handle in handles:
                handle.close()

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another similar one.

        Targets or end points should never be identified here.
        """
        return (self.secure_protocol, self.user, self.sender)

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Prepare our parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        return (
            "{schema}://{user}:{password}@{sender}/{targets}?{params}".format(
                schema=self.secure_protocol,
                user=self.pprint(self.user, privacy, safe=""),
                password=self.pprint(
                    self.password,
                    privacy,
                    mode=PrivacyMode.Secret,
                    safe="",
                ),
                sender=NotifySerwerSMS.quote(self.sender, safe=""),
                targets="/".join(
                    [
                        # + is safe so phone numbers are human-readable;
                        # # is not safe so group IDs become %23 and survive
                        # re-parsing by parse_url()
                        NotifySerwerSMS.quote(t, safe="+")
                        for t in chain(
                            # Phone targets
                            ["+{}".format(p) for p in self.target_phones],
                            # Group targets -- # encoded as %23
                            ["#{}".format(g) for g in self.target_groups],
                            # Preserve invalid entries for round-trip fidelity
                            self.invalid_targets,
                        )
                    ]
                ),
                params=NotifySerwerSMS.urlencode(params),
            )
        )

    def __len__(self):
        """Returns the number of targets associated with this notification."""
        return max(1, len(self.target_phones) + len(self.target_groups))

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to
        re-instantiate this object."""

        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # The sender name occupies the host position in the URL
        results["sender"] = NotifySerwerSMS.unquote(results["host"])

        # Gather targets from the URL path
        results["targets"] = NotifySerwerSMS.split_path(results["fullpath"])

        # Support ?to= as a comma-separated target override
        if "to" in results["qsd"] and results["qsd"]["to"]:
            results["targets"] += NotifySerwerSMS.parse_list(
                results["qsd"]["to"]
            )

        # Support ?from= as a sender name override (lower priority than
        # ?sender= so ?sender= wins when both appear)
        if "from" in results["qsd"] and results["qsd"]["from"]:
            results["sender"] = NotifySerwerSMS.unquote(results["qsd"]["from"])

        if "sender" in results["qsd"] and results["qsd"]["sender"]:
            results["sender"] = NotifySerwerSMS.unquote(
                results["qsd"]["sender"]
            )

        return results
