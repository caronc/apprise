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

# To use this service you will need a SMSC account (https://smsc.ru/)
#
#  1. Sign up at https://smsc.ru/ (also available as smsc.kz).
#  2. Add funds to your account to cover SMS/MMS credit costs.
#  3. Note your account login and password -- these are used directly
#     in the Apprise URL.
#
#  The Apprise URL format is:
#    smsc://login:password@ToPhoneNo
#    smsc://login:password@ToPhoneNo1/ToPhoneNo2/ToPhoneNoN
#
#  Optionally include a sender ID (up to 11 alphanumeric or 15 numeric
#  chars):
#    smsc://login:password@ToPhoneNo?sender=MySender
#
#  Transliterate Cyrillic characters to Latin:
#    smsc://login:password@ToPhoneNo?translit=yes
#
#  If one or more file attachments are provided, the message is
#  automatically sent as MMS instead of SMS.
#
# API documentation:
#   https://smsc.ru/api/http/
#   https://smsc.ru/api/http/send/
from json import loads

import requests

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import (
    is_phone_no,
    parse_bool,
    parse_phone_no,
    validate_regex,
)
from .base import NotifyBase

# SMSC send endpoint
SMSC_API_URL = "https://smsc.ru/sys/send.php"

# JSON response format identifier
SMSC_FMT_JSON = 3

# Maximum sender ID lengths
SMSC_SENDER_ALPHA_MAXLEN = 11
SMSC_SENDER_NUMERIC_MAXLEN = 15

# SMSC HTTP error map
SMSC_HTTP_ERROR_MAP = {
    400: "Bad request -- invalid parameters.",
    401: "Unauthorized -- invalid credentials.",
    403: "Forbidden -- access denied.",
    500: "Internal server error.",
}

# SMSC API error codes returned in JSON response
SMSC_API_ERROR_MAP = {
    1: "Invalid parameter(s) in request.",
    2: "Invalid login or password.",
    3: "Insufficient account funds.",
    4: "IP address temporarily blocked.",
    5: "Invalid date/time specified.",
    6: "Message forbidden by content filters.",
    7: "Invalid phone number format.",
    8: "Message body is required.",
    9: "Too many phone numbers specified.",
    10: "No phone numbers available for delivery.",
    99: "Internal server error.",
}


class NotifySMSC(NotifyBase):
    """A wrapper for SMSC Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "SMSC"

    # The services URL
    service_url = "https://smsc.ru/"

    # The default secure protocol (SMSC uses HTTPS only)
    secure_protocol = "smsc"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/smsc/"

    # SMSC send API endpoint
    notify_url = SMSC_API_URL

    # SMS body max length
    body_maxlen = 160

    # A title can not be used for SMS Messages -- any title (if defined)
    # gets prepended into the body automatically.
    title_maxlen = 0

    # Attachments are supported; the plugin auto-switches to MMS mode
    # when one or more attachments are provided.
    attachment_support = True

    # Define the SMSC URL schema
    templates = ("{schema}://{user}:{password}@{targets}",)

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "user": {
                "name": _("Login"),
                "type": "string",
                "required": True,
            },
            "password": {
                "name": _("Password"),
                "type": "string",
                "private": True,
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
                "required": True,
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
                "name": _("Sender ID"),
                "type": "string",
            },
            "translit": {
                "name": _("Transliterate"),
                "type": "bool",
                "default": False,
            },
        },
    )

    def __init__(
        self,
        targets=None,
        sender=None,
        translit=None,
        **kwargs,
    ):
        """Initialize SMSC Object."""
        super().__init__(**kwargs)

        # Validate login
        if not self.user:
            msg = "An SMSC login must be specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Validate password
        if not self.password:
            msg = "An SMSC password must be specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Optional sender ID
        self.sender = None
        if sender:
            self.sender = validate_regex(sender)
            if not self.sender:
                msg = f"The SMSC sender ID specified ({sender}) is invalid."
                self.logger.warning(msg)
                raise TypeError(msg)

        # Transliteration flag
        self.translit = (
            self.template_args["translit"]["default"]
            if translit is None
            else bool(translit)
        )

        # Parse our targets (phone numbers)
        self.targets = []

        for target in parse_phone_no(targets):
            # Validate each phone number
            result = is_phone_no(target)
            if not result:
                self.logger.warning(
                    "Dropped invalid SMSC phone # (%s).", target
                )
                continue

            self.targets.append(result["full"])

        return

    def send(
        self,
        body,
        title="",
        notify_type=NotifyType.INFO,
        attach=None,
        **kwargs,
    ):
        """Perform SMSC Notification."""

        # Verify we have targets
        if not self.targets:
            self.logger.warning("No SMSC targets to notify.")
            return False

        # Determine whether to send SMS or MMS
        use_mms = bool(attach and self.attachment_support and len(attach))

        if use_mms:
            return self._send_mms(body, attach)

        return self._send_sms(body)

    def _base_params(self):
        """Build the common query parameters shared by SMS and MMS."""

        # Comma-separated list of recipient phone numbers
        phones = ",".join(self.targets)

        # Base parameters
        params = {
            "login": self.user,
            "psw": self.password,
            "phones": phones,
            "fmt": SMSC_FMT_JSON,
        }

        # Include sender ID if configured
        if self.sender:
            params["sender"] = self.sender

        # Include transliteration flag when enabled
        if self.translit:
            params["translit"] = 1

        return params

    def _send_sms(self, body):
        """Send a plain SMS message."""

        # Build our parameters
        params = self._base_params()
        params["mes"] = body

        self.logger.debug(
            "SMSC POST URL: %s (cert_verify=%s)",
            self.notify_url,
            self.verify_certificate,
        )
        self.logger.debug("SMSC Params: %s", params)

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                self.notify_url,
                data=params,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )
            self.logger.trace("SMSC Response: %s", r.content)

            if r.status_code != requests.codes.ok:
                status_str = NotifySMSC.http_response_code_lookup(
                    r.status_code, SMSC_HTTP_ERROR_MAP
                )
                self.logger.warning(
                    "Failed to send SMSC SMS: %s%serror=%s.",
                    status_str,
                    ", " if status_str else "",
                    r.status_code,
                )
                self.logger.debug("Response Details:\r\n%s", r.content)
                return False

            # Parse the JSON response; guard against null/non-dict replies
            try:
                content = loads(r.content)
                if not isinstance(content, dict):
                    content = {}

            except (AttributeError, TypeError, ValueError):
                content = {}

            # Check for API-level error embedded in an otherwise 200 response
            if "error_code" in content:
                err_code = content.get("error_code", 0)
                err_msg = content.get(
                    "error",
                    SMSC_API_ERROR_MAP.get(err_code, "Unknown error."),
                )
                self.logger.warning(
                    "SMSC API error (code=%s): %s", err_code, err_msg
                )
                return False

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending SMSC SMS."
            )
            self.logger.debug("Socket Exception: %s", str(e))
            return False

        self.logger.info("Sent SMSC SMS notification.")
        return True

    def _send_mms(self, body, attach):
        """Send an MMS message with one or more file attachments."""

        # Build common parameters and mark as MMS
        params = self._base_params()
        params["mes"] = body
        params["mms"] = 1

        self.logger.debug(
            "SMSC MMS POST URL: %s (cert_verify=%s)",
            self.notify_url,
            self.verify_certificate,
        )
        self.logger.debug("SMSC MMS Params: %s", params)

        # Build multipart file list and track open handles
        handles = []
        files = []
        attach_ok = True

        try:
            for idx, attachment in enumerate(attach):
                # Guard 1: verify the attachment is accessible
                if not attachment:
                    self.logger.warning(
                        "Could not access SMSC attachment %s.",
                        attachment.url(privacy=True),
                    )
                    attach_ok = False
                    break

                # Guard 2: open the file (OSError guard)
                try:
                    handle = attachment.open()

                except OSError as exc:
                    self.logger.warning(
                        "An I/O error occurred reading SMSC attachment %s.",
                        attachment.name or "attachment",
                    )
                    self.logger.debug("I/O Exception: %s", str(exc))
                    attach_ok = False
                    break

                # Track handle for cleanup
                handles.append(handle)
                files.append(
                    (
                        "mes{}".format(idx),
                        (
                            attachment.name or "attachment.dat",
                            handle,
                            attachment.mimetype,
                        ),
                    )
                )

            if not attach_ok:
                return False

            # Always call throttle before any remote server i/o is made
            self.throttle()

            try:
                # Send multipart/form-data; do NOT set Content-Type --
                # requests sets the multipart boundary automatically.
                r = requests.post(
                    self.notify_url,
                    data=params,
                    files=files,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                    allow_redirects=self.redirects,
                )
                self.logger.trace("SMSC MMS Response: %s", r.content)

                if r.status_code != requests.codes.ok:
                    status_str = NotifySMSC.http_response_code_lookup(
                        r.status_code, SMSC_HTTP_ERROR_MAP
                    )
                    self.logger.warning(
                        "Failed to send SMSC MMS: %s%serror=%s.",
                        status_str,
                        ", " if status_str else "",
                        r.status_code,
                    )
                    self.logger.debug("Response Details:\r\n%s", r.content)
                    return False

                # Parse the JSON response; guard against null/non-dict replies
                try:
                    content = loads(r.content)
                    if not isinstance(content, dict):
                        content = {}

                except (AttributeError, TypeError, ValueError):
                    content = {}

                # Check for API-level error in an otherwise 200 response
                if "error_code" in content:
                    err_code = content.get("error_code", 0)
                    err_msg = content.get(
                        "error",
                        SMSC_API_ERROR_MAP.get(err_code, "Unknown error."),
                    )
                    self.logger.warning(
                        "SMSC MMS API error (code=%s): %s",
                        err_code,
                        err_msg,
                    )
                    return False

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending SMSC MMS."
                )
                self.logger.debug("Socket Exception: %s", str(e))
                return False

        finally:
            # Guard 3: close all open file handles regardless of outcome
            for handle in handles:
                handle.close()

        self.logger.info("Sent SMSC MMS notification.")
        return True

    def __len__(self):
        """Returns the number of targets associated with this notification."""
        return len(self.targets) if self.targets else 1

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another similar one.

        Targets or end points should never be identified here.
        """
        return (
            self.secure_protocol,
            self.user,
            self.password,
        )

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Prepare optional parameters
        params = {}
        if self.sender:
            params["sender"] = self.sender

        if self.translit != self.template_args["translit"]["default"]:
            params["translit"] = "yes" if self.translit else "no"

        # Merge standard URL parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return "{schema}://{user}:{password}@{targets}/?{params}".format(
            schema=self.secure_protocol,
            user=self.pprint(self.user, privacy, safe=""),
            password=self.pprint(
                self.password,
                privacy,
                mode=PrivacyMode.Secret,
                safe="",
            ),
            targets="/".join(
                [NotifySMSC.quote(t, safe="+") for t in self.targets]
            ),
            params=NotifySMSC.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow
        us to re-instantiate this object."""

        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            return results

        # The host is the first phone number target
        results["targets"] = [
            NotifySMSC.unquote(results["host"]),
            *NotifySMSC.split_path(results["fullpath"]),
        ]

        # Support ?to= as an alias for targets
        if "to" in results["qsd"] and results["qsd"]["to"]:
            results["targets"] += NotifySMSC.parse_phone_no(
                results["qsd"]["to"]
            )

        # Optional sender ID
        if "sender" in results["qsd"] and results["qsd"]["sender"]:
            results["sender"] = NotifySMSC.unquote(results["qsd"]["sender"])

        # Transliteration flag
        if "translit" in results["qsd"] and results["qsd"]["translit"]:
            results["translit"] = parse_bool(results["qsd"]["translit"])

        return results
