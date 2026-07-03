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

# To use the Notifyre notification service you need an API token.
#
# Steps:
#  1. Sign up at https://notifyre.com/ and log in.
#  2. Navigate to Settings > Developer.
#  3. Click "New" to create an API token.
#  4. Copy the token -- it is only shown once.
#
# SMS (default mode):
#   notifyre://{apikey}/{phoneno}
#   notifyre://{apikey}/{phoneno1}/{phoneno2}
#   notifyre://{apikey}/{phoneno}?from=+15551234567
#   notifyre://{apikey}/{phoneno}?campaign=MyCampaign
#
# Fax mode (?mode=fax):
#   notifyre://{apikey}/{faxno}?mode=fax
#   notifyre://{apikey}/{faxno}?mode=fax&from=+15551234567
#   notifyre://{apikey}/{faxno}?mode=fax&template=MyTemplate
#   notifyre://{apikey}/{faxno}?mode=fax&hq=no
#   notifyre://{apikey}/{faxno}?mode=fax&ref=ClientRef
#   notifyre://{apikey}/{faxno}?mode=fax&header=Confidential
#   notifyre://{apikey}/{faxno}?mode=fax&campaign=MyCampaign
#
# In fax mode, Apprise attachments are base64-encoded and sent as fax
# document pages.  Supported attachment types include PDF, DOCX, PNG,
# JPEG, TIFF, and many others.  The notification body is always included
# as a plain-text cover page prepended before any attachments.
#
# API reference:
#   https://docs.notifyre.com/

import base64
from json import dumps, loads

import requests

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import is_phone_no, parse_bool, parse_phone_no
from .base import NotifyBase

# Notifyre REST API versioned base
NOTIFYRE_API_VERSION = "20220711"

# SMS send endpoint
NOTIFYRE_SMS_URL = "https://api.notifyre.com/{}/sms/send".format(
    NOTIFYRE_API_VERSION
)

# Fax send endpoint
NOTIFYRE_FAX_URL = "https://api.notifyre.com/{}/fax/send".format(
    NOTIFYRE_API_VERSION
)


class NotifyreMode:
    """Delivery modes supported by the Notifyre plugin."""

    # SMS text message delivery
    SMS = "sms"

    # Fax delivery -- supports attachments as fax document pages
    FAX = "fax"


# Delivery mode choices
NOTIFYRE_MODES = (
    NotifyreMode.SMS,
    NotifyreMode.FAX,
)


class NotifyNotifyre(NotifyBase):
    """A wrapper for Notifyre Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Notifyre"

    # The services URL
    service_url = "https://notifyre.com/"

    # The default secure protocol
    secure_protocol = "notifyre"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/notifyre/"

    # Fax mode supports document attachments (base64-encoded pages)
    attachment_support = True

    # A title can not be used for SMS/Fax; setting this to zero causes any
    # title to be prepended to the body before send() is called.
    title_maxlen = 0

    # Define object URL templates
    templates = ("{schema}://{apikey}/{targets}",)

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "apikey": {
                "name": _("API Key"),
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
            "mode": {
                "name": _("Mode"),
                "type": "choice:string",
                "values": NOTIFYRE_MODES,
                "default": NotifyreMode.SMS,
            },
            "from": {
                "name": _("Source Phone No"),
                "type": "string",
                "map_to": "source",
            },
            "campaign": {
                "name": _("Campaign Name"),
                "type": "string",
            },
            "template": {
                "name": _("Template Name"),
                "type": "string",
            },
            "ref": {
                "name": _("Client Reference"),
                "type": "string",
            },
            "hq": {
                "name": _("High Quality"),
                "type": "bool",
                "default": True,
            },
            "header": {
                "name": _("Fax Header"),
                "type": "string",
            },
        },
    )

    def __init__(
        self,
        apikey,
        targets=None,
        mode=None,
        source=None,
        campaign=None,
        template=None,
        ref=None,
        hq=None,
        header=None,
        **kwargs,
    ):
        """Initialize Notifyre Object."""

        # Default mode before super().__init__() so the body_maxlen property
        # never accesses an undefined self.mode during base class setup.
        self.mode = NotifyreMode.SMS

        super().__init__(**kwargs)

        # Validate API key
        if not apikey:
            msg = "A Notifyre API key must be specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store our API key
        self.apikey = apikey

        # Resolve delivery mode
        if mode and isinstance(mode, str):
            _mode = mode.lower().strip()
            self.mode = next(
                (m for m in NOTIFYRE_MODES if m.startswith(_mode)),
                None,
            )
            if self.mode not in NOTIFYRE_MODES:
                msg = "The Notifyre mode specified ({}) is invalid.".format(
                    mode
                )
                self.logger.warning(msg)
                raise TypeError(msg)

        else:
            # Default to SMS
            self.mode = NotifyreMode.SMS

        # Optional source (sender) phone/fax number
        self.source = None
        if source:
            result = is_phone_no(source)
            if not result:
                msg = (
                    "The Notifyre source (From) phone # "
                    "({}) is invalid.".format(source)
                )
                self.logger.warning(msg)
                raise TypeError(msg)

            # Store normalised number with country code prefix
            self.source = "+{}".format(result["full"])

        # Campaign name -- defaults to the Apprise application ID
        self.campaign = (
            campaign.strip()
            if isinstance(campaign, str) and campaign.strip()
            else self.app_id
        )

        # Fax-specific optional fields
        self.template = template.strip() if isinstance(template, str) else ""
        self.ref = ref.strip() if isinstance(ref, str) else ""
        self.hq = parse_bool(hq) if hq is not None else True
        self.header = header.strip() if isinstance(header, str) else ""

        # Parse target phone/fax numbers and drop invalid entries
        self.targets = []
        for target in parse_phone_no(targets):
            result = is_phone_no(target)
            if not result:
                self.logger.warning(
                    "Dropped invalid Notifyre phone # (%s) specified.",
                    target,
                )
                continue

            # Store normalised number with country code prefix
            self.targets.append("+{}".format(result["full"]))

        return

    @property
    def body_maxlen(self):
        """Maximum body length varies by mode.

        SMS is limited to 160 characters per segment; fax has no
        meaningful API-side limit so a generous ceiling is used.
        """
        return 160 if self.mode == NotifyreMode.SMS else 32768

    def send(
        self,
        body,
        title="",
        notify_type=NotifyType.INFO,
        attach=None,
        **kwargs,
    ):
        """Perform Notifyre Notification."""

        # No targets to notify
        if not self.targets:
            self.logger.warning("No Notifyre targets to notify.")
            return False

        return (
            self._send_fax(body, attach=attach)
            if self.mode == NotifyreMode.FAX
            else self._send_sms(body, attach=attach)
        )

    def _send_sms(self, body, attach=None):
        """Send an SMS notification to all targets."""

        # Attachments are not supported in SMS mode
        if attach and self.attachment_support:
            self.logger.warning(
                "Notifyre SMS does not support attachments;"
                " use fax mode instead."
            )

        # Prepare headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
            "x-api-token": self.apikey,
        }

        # Build recipient list
        recipients = [
            {"type": "mobile_number", "value": t} for t in self.targets
        ]

        # Build payload
        payload = {
            "body": body,
            "recipients": recipients,
            "from": self.source or "",
            "campaignName": self.campaign,
        }

        self.logger.debug(
            "Notifyre SMS POST URL: %s (cert_verify=%s)",
            NOTIFYRE_SMS_URL,
            self.verify_certificate,
        )
        self.logger.debug("Notifyre SMS Payload: %s", payload)

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                NOTIFYRE_SMS_URL,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )
            self.logger.trace("Notifyre SMS Response: %s", r.content)

            # Defensive JSON parse -- never call r.json()
            try:
                content = loads(r.content)
                if not isinstance(content, dict):
                    content = {}
            except (AttributeError, TypeError, ValueError):
                content = {}
                self.logger.debug(
                    "Failed to parse Notifyre JSON response; body: %r",
                    (r.content or b"")[:2000],
                )

            if r.status_code != requests.codes.ok:
                # We had a failure
                status_str = NotifyNotifyre.http_response_code_lookup(
                    r.status_code
                )
                self.logger.warning(
                    "Failed to send Notifyre SMS: %s%serror=%s.",
                    status_str,
                    ", " if status_str else "",
                    r.status_code,
                )
                self.logger.debug("Response Details:\r\n%s", r.content)
                return False

            if not content.get("success", True):
                # API returned success=false on an HTTP 200
                self.logger.warning(
                    "Notifyre SMS failed: %s",
                    content.get("message", "Unknown error"),
                )
                return False

            self.logger.info("Sent Notifyre SMS notification.")
            return True

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending Notifyre SMS."
            )
            self.logger.debug("Socket Exception: %s", str(e))
            return False

    def _send_fax(self, body, attach=None):
        """Send a fax notification with optional document attachments."""

        # Prepare headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
            "x-api-token": self.apikey,
        }

        # Fax documents list -- body text is always the first page
        documents = []

        # Encode the body text as a plain-text fax document
        if body:
            documents.append(
                {
                    "base64Str": base64.b64encode(body.encode("utf-8")).decode(
                        "utf-8"
                    ),
                    "contentType": "text/plain",
                }
            )

        # Add file attachments as additional fax pages
        handles = []
        attach_ok = True

        try:
            if attach:
                for attachment in attach:
                    # Guard 1: verify accessibility before opening
                    if not attachment:
                        self.logger.warning(
                            "Could not access Notifyre fax attachment %s.",
                            attachment.url(privacy=True),
                        )
                        attach_ok = False
                        break

                    # Guard 2: OSError on open
                    try:
                        handle = attachment.open()
                    except OSError as exc:
                        self.logger.warning(
                            "An I/O error occurred reading Notifyre"
                            " attachment %s.",
                            attachment.name,
                        )
                        self.logger.debug("I/O Exception: %s", str(exc))
                        attach_ok = False
                        break

                    # Register handle for cleanup before attempting read
                    handles.append(handle)

                    # Read file content for base64 encoding
                    try:
                        file_bytes = handle.read()
                    except OSError as exc:
                        self.logger.warning(
                            "An I/O error occurred reading Notifyre"
                            " attachment %s.",
                            attachment.name,
                        )
                        self.logger.debug("I/O Exception: %s", str(exc))
                        attach_ok = False
                        break

                    # Encode file as a base64 fax document page
                    documents.append(
                        {
                            "base64Str": base64.b64encode(file_bytes).decode(
                                "utf-8"
                            ),
                            "contentType": attachment.mimetype,
                        }
                    )

            if not attach_ok:
                return False

            # At least one document must be present
            if not documents:
                self.logger.warning("Notifyre fax has no content to send.")
                return False

            # Build fax recipient list
            recipients = [
                {"type": "fax_number", "value": t} for t in self.targets
            ]

            # Build fax payload
            payload = {
                "templateName": self.template,
                "recipients": recipients,
                "sendFrom": self.source or "",
                "isHighQuality": self.hq,
                "clientReference": self.ref,
                "documents": documents,
                "header": self.header,
                "subject": body if body else "",
                "campaignName": self.campaign,
                "scheduledDate": None,
            }

            self.logger.debug(
                "Notifyre Fax POST URL: %s (cert_verify=%s)",
                NOTIFYRE_FAX_URL,
                self.verify_certificate,
            )
            self.logger.debug("Notifyre Fax Payload: %s", payload)

            # Always call throttle before any remote server i/o is made
            self.throttle()

            try:
                r = requests.post(
                    NOTIFYRE_FAX_URL,
                    data=dumps(payload),
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                    allow_redirects=self.redirects,
                )
                self.logger.trace("Notifyre Fax Response: %s", r.content)

                # Defensive JSON parse -- never call r.json()
                try:
                    content = loads(r.content)
                    if not isinstance(content, dict):
                        content = {}
                except (AttributeError, TypeError, ValueError):
                    content = {}
                    self.logger.debug(
                        "Failed to parse Notifyre JSON response; body: %r",
                        (r.content or b"")[:2000],
                    )

                if r.status_code != requests.codes.ok:
                    # We had a failure
                    status_str = NotifyNotifyre.http_response_code_lookup(
                        r.status_code
                    )
                    self.logger.warning(
                        "Failed to send Notifyre fax: %s%serror=%s.",
                        status_str,
                        ", " if status_str else "",
                        r.status_code,
                    )
                    self.logger.debug("Response Details:\r\n%s", r.content)
                    return False

                if not content.get("success", True):
                    # API returned success=false on an HTTP 200
                    self.logger.warning(
                        "Notifyre fax failed: %s",
                        content.get("message", "Unknown error"),
                    )
                    return False

                self.logger.info("Sent Notifyre fax notification.")
                return True

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending Notifyre fax."
                )
                self.logger.debug("Socket Exception: %s", str(e))
                return False

        finally:
            # Guard 3: close all file handles whether we succeeded or failed
            for handle in handles:
                handle.close()

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another similar one.

        Targets or end points should never be identified here.
        """
        return (
            self.secure_protocol,
            self.mode,
            self.apikey,
        )

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Build URL parameters
        params = {"mode": self.mode}

        if self.source:
            # Include source phone number in parameters
            params["from"] = self.source

        # Include campaign if it differs from the default app ID
        if self.campaign != self.app_id:
            params["campaign"] = self.campaign

        # Include fax-specific parameters when set
        if self.template:
            params["template"] = self.template

        if self.ref:
            params["ref"] = self.ref

        if not self.hq:
            # Only include hq when it is non-default (default is True)
            params["hq"] = "no"

        if self.header:
            params["header"] = self.header

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return "{schema}://{apikey}/{targets}/?{params}".format(
            schema=self.secure_protocol,
            apikey=self.pprint(self.apikey, privacy, safe=""),
            targets="/".join(
                NotifyNotifyre.quote(t, safe="+") for t in self.targets
            ),
            params=NotifyNotifyre.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow
        us to re-instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # API key is encoded in the URL host field
        results["apikey"] = NotifyNotifyre.unquote(results["host"])

        # Targets are path entries
        results["targets"] = NotifyNotifyre.split_path(results["fullpath"])

        # ?to= provides additional targets (comma-separated)
        if "to" in results["qsd"] and results["qsd"]["to"]:
            results["targets"] += NotifyNotifyre.parse_phone_no(
                results["qsd"]["to"]
            )

        # ?mode= selects delivery mode
        if "mode" in results["qsd"] and results["qsd"]["mode"]:
            results["mode"] = NotifyNotifyre.unquote(results["qsd"]["mode"])

        # ?from= specifies the sender phone/fax number
        if "from" in results["qsd"] and results["qsd"]["from"]:
            results["source"] = NotifyNotifyre.unquote(results["qsd"]["from"])

        # ?campaign= sets the campaign name
        if "campaign" in results["qsd"] and results["qsd"]["campaign"]:
            results["campaign"] = NotifyNotifyre.unquote(
                results["qsd"]["campaign"]
            )

        # ?template= sets the fax template name
        if "template" in results["qsd"] and results["qsd"]["template"]:
            results["template"] = NotifyNotifyre.unquote(
                results["qsd"]["template"]
            )

        # ?ref= sets the client reference
        if "ref" in results["qsd"] and results["qsd"]["ref"]:
            results["ref"] = NotifyNotifyre.unquote(results["qsd"]["ref"])

        # ?hq= sets high-quality fax flag (bool)
        if "hq" in results["qsd"] and results["qsd"]["hq"]:
            results["hq"] = parse_bool(results["qsd"]["hq"])

        # ?header= sets the fax cover page header string
        if "header" in results["qsd"] and results["qsd"]["header"]:
            results["header"] = NotifyNotifyre.unquote(
                results["qsd"]["header"]
            )

        return results
