# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2025, Chris Caron <lead2gold@gmail.com>
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

# To use this service you will need a Twilio account to which you can get your
# AUTH_TOKEN and ACCOUNT SID right from your console/dashboard at:
#     https://www.twilio.com/console
#
# You will also need to send the SMS From a phone number or account id name.

# This is identified as the source (or where the SMS message will originate
# from). Activated phone numbers can be found on your dashboard here:
#  - https://www.twilio.com/console/phone-numbers/incoming
#
# Alternatively, you can open your wallet and request a different Twilio
# phone # from:
#    https://www.twilio.com/console/phone-numbers/search
#
# or consider purchasing a short-code from here:
#    https://www.twilio.com/docs/glossary/what-is-a-short-code
#
from json import loads
import re

import requests

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import is_phone_no, parse_phone_no, validate_regex
from .base import NotifyBase

# Twilio Mode Detection
MODE_DETECT_RE = re.compile(
    r"\s*((?P<mode>[^:]+)\s*:\s*)?(?P<phoneno>.+)$", re.I
)


class TwilioMessageMode:
    """Twilio Message Mode."""

    # SMS/MMS
    TEXT = "T"

    # via WhatsApp
    WHATSAPP = "W"


class NotifyTwilio(NotifyBase):
    """A wrapper for Twilio Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Twilio"

    # The services URL
    service_url = "https://www.twilio.com/"

    # All notification requests are secure
    secure_protocol = "twilio"

    # Allow 300 requests per minute.
    # 60/300 = 0.2
    request_rate_per_sec = 0.20

    # the number of seconds undelivered messages should linger for
    # in the Twilio queue
    validity_period = 14400

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_twilio"

    # Twilio uses the http protocol with JSON requests
    notify_url = (
        "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    )

    # The maximum length of the body
    body_maxlen = 160

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Define object templates
    templates = (
        "{schema}://{account_sid}:{auth_token}@{from_phone}",
        "{schema}://{account_sid}:{auth_token}@{from_phone}/{targets}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "account_sid": {
                "name": _("Account SID"),
                "type": "string",
                "private": True,
                "required": True,
                "regex": (r"^AC[a-f0-9]+$", "i"),
            },
            "auth_token": {
                "name": _("Auth Token"),
                "type": "string",
                "private": True,
                "required": True,
                "regex": (r"^[a-z0-9]+$", "i"),
            },
            "from_phone": {
                "name": _("From Phone No"),
                "type": "string",
                "required": True,
                "regex": (r"^([a-z]+:)?\+?[0-9\s)(+-]+$", "i"),
                "map_to": "source",
            },
            "target_phone": {
                "name": _("Target Phone No"),
                "type": "string",
                "prefix": "+",
                "regex": (r"^([a-z]+:)?[0-9\s)(+-]+$", "i"),
                "map_to": "targets",
            },
            "short_code": {
                "name": _("Target Short Code"),
                "type": "string",
                "regex": (r"^[0-9]{5,6}$", "i"),
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
            "from": {
                "alias_of": "from_phone",
            },
            "sid": {
                "alias_of": "account_sid",
            },
            "token": {
                "alias_of": "auth_token",
            },
            "apikey": {
                "name": _("API Key"),
                "type": "string",
                "private": True,
                "regex": (r"^SK[a-f0-9]+$", "i"),
            },
        },
    )

    def __init__(
        self,
        account_sid,
        auth_token,
        source,
        targets=None,
        apikey=None,
        **kwargs,
    ):
        """Initialize Twilio Object."""
        super().__init__(**kwargs)

        # The Account SID associated with the account
        self.account_sid = validate_regex(
            account_sid, *self.template_tokens["account_sid"]["regex"]
        )
        if not self.account_sid:
            msg = (
                f"An invalid Twilio Account SID ({account_sid}) was specified."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # The Authentication Token associated with the account
        self.auth_token = validate_regex(
            auth_token, *self.template_tokens["auth_token"]["regex"]
        )
        if not self.auth_token:
            msg = (
                "An invalid Twilio Authentication Token "
                f"({auth_token}) was specified."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # The API Key associated with the account (optional)
        self.apikey = validate_regex(
            apikey, *self.template_args["apikey"]["regex"]
        )

        # Detect mode
        result = MODE_DETECT_RE.match(source)
        if not result:
            msg = (
                "The Account (From) Phone # or Short-code specified "
                f"({source}) is invalid."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # prepare our default mode to use for all numbers that follow in
        # target definitions
        self.default_mode = (
            TwilioMessageMode.WHATSAPP
            if result.group("mode") and result.group("mode")[0].lower() == "w"
            else TwilioMessageMode.TEXT
        )

        result = is_phone_no(result.group("phoneno"), min_len=5)
        if not result:
            msg = (
                "The Account (From) Phone # or Short-code specified "
                f"({source}) is invalid."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store The Source Phone # and/or short-code
        self.source = result["full"]

        if len(self.source) < 11 or len(self.source) > 14:
            # https://www.twilio.com/docs/glossary/what-is-a-short-code
            # A short code is a special 5 or 6 digit telephone number
            # that's shorter than a full phone number.
            if len(self.source) not in (5, 6):
                msg = (
                    "The Account (From) Phone # specified "
                    f"({source}) is invalid."
                )
                self.logger.warning(msg)
                raise TypeError(msg)

            # else... it as a short code so we're okay

        else:
            # We're dealing with a phone number; so we need to just
            # place a plus symbol at the end of it
            self.source = f"+{self.source}"

        # Parse our targets
        self.targets = []

        for entry in parse_phone_no(targets, prefix=True):
            # Detect mode
            # w: (or whatsapp:) will trigger whatsapp message otherwise
            #   sms/mms as normal
            result = MODE_DETECT_RE.match(entry)
            mode = (
                TwilioMessageMode.WHATSAPP
                if result.group("mode")
                and result.group("mode")[0].lower() == "w"
                else self.default_mode
            )

            # Validate targets and drop bad ones:
            result = is_phone_no(result.group("phoneno"))
            if not result:
                self.logger.warning(
                    f"Dropped invalid phone # ({entry}) specified.",
                )
                continue

            # We can't send twilio messages using short-codes as our source
            if (
                len(self.source) in (5, 6)
                and mode is TwilioMessageMode.WHATSAPP
            ):
                self.logger.warning(
                    "Dropped WhatsApp phone # "
                    f"({entry}) because source provided was a short-code.",
                )
                continue

            # store valid phone number
            self.targets.append((mode, "+{}".format(result["full"])))

        return

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform Twilio Notification."""

        if not self.targets and len(self.source) in (5, 6):
            # Generate a warning since we're a short-code.  We need
            # a number to message at minimum
            self.logger.warning("There are no valid Twilio targets to notify.")
            return False

        # error tracking (used for function return)
        has_error = False

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Accept": "application/json",
        }

        # Prepare our payload
        payload = {
            "Body": body,
            # The From and To gets populated in the loop below
            "From": None,
            "To": None,
        }

        # Prepare our Twilio URL
        url = self.notify_url.format(sid=self.account_sid)

        # Create a copy of the targets list
        targets = list(self.targets)

        # Set up our authentication. Prefer the API Key if provided.
        auth = (self.apikey or self.account_sid, self.auth_token)

        if len(targets) == 0:
            # No sources specified, use our own phone no
            targets.append((self.default_mode, self.source))

        while len(targets):
            # Get our target to notify
            (mode, target) = targets.pop(0)

            # Prepare our user
            if mode is TwilioMessageMode.TEXT:
                payload["From"] = self.source
                payload["To"] = target

            else:  # WhatsApp support (via Twilio)
                payload["From"] = f"whatsapp:{self.source}"
                payload["To"] = f"whatsapp:{target}"

            # Some Debug Logging
            self.logger.debug(
                "Twilio POST URL:"
                f" {url} (cert_verify={self.verify_certificate})"
            )
            self.logger.debug(f"Twilio Payload: {payload}")

            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.post(
                    url,
                    auth=auth,
                    data=payload,
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )

                if r.status_code not in (
                    requests.codes.created,
                    requests.codes.ok,
                ):
                    # We had a problem
                    status_str = NotifyBase.http_response_code_lookup(
                        r.status_code
                    )

                    # set up our status code to use
                    status_code = r.status_code

                    try:
                        # Update our status response if we can
                        json_response = loads(r.content)
                        status_code = json_response.get("code", status_code)
                        status_str = json_response.get("message", status_str)

                    except (AttributeError, TypeError, ValueError):
                        # ValueError = r.content is Unparsable
                        # TypeError = r.content is None
                        # AttributeError = r is None

                        # We could not parse JSON response.
                        # We will just use the status we already have.
                        pass

                    self.logger.warning(
                        "Failed to send Twilio notification to {}: "
                        "{}{}error={}.".format(
                            target,
                            status_str,
                            ", " if status_str else "",
                            status_code,
                        )
                    )

                    self.logger.debug(f"Response Details:\r\n{r.content}")

                    # Mark our failure
                    has_error = True
                    continue

                else:
                    self.logger.info(f"Sent Twilio notification to {target}.")

            except requests.RequestException as e:
                self.logger.warning(
                    f"A Connection error occurred sending Twilio:{target} "
                    + "notification."
                )
                self.logger.debug(f"Socket Exception: {e!s}")

                # Mark our failure
                has_error = True
                continue

        return not has_error

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (
            self.secure_protocol,
            self.account_sid,
            self.auth_token,
            self.source,
        )

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Our URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        if self.apikey is not None:
            # apikey specified; pass it back on the url
            params["apikey"] = self.apikey

        return "{schema}://{sid}:{token}@{source}/{targets}/?{params}".format(
            schema=self.secure_protocol,
            sid=self.pprint(
                self.account_sid, privacy, mode=PrivacyMode.Tail, safe=""
            ),
            token=self.pprint(self.auth_token, privacy, safe=""),
            source=NotifyTwilio.quote(
                (
                    self.source
                    if self.default_mode is TwilioMessageMode.TEXT
                    else f"w:{self.source}"
                ),
                safe="",
            ),
            targets="/".join([
                NotifyTwilio.quote(
                    (x[1] if x[0] is TwilioMessageMode.TEXT else f"w:{x[1]}"),
                    safe="",
                )
                for x in self.targets
            ]),
            params=NotifyTwilio.urlencode(params),
        )

    def __len__(self):
        """Returns the number of targets associated with this notification."""
        targets = len(self.targets)
        return targets if targets > 0 else 1

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)

        if not results:
            # We're done early as we couldn't load the results
            return results

        # Get our entries; split_path() looks after unquoting content for us
        # by default
        results["targets"] = NotifyTwilio.split_path(results["fullpath"])

        # The hostname is our source number
        results["source"] = NotifyTwilio.unquote(results["host"])

        # Get our account_side and auth_token from the user/pass config
        results["account_sid"] = NotifyTwilio.unquote(results["user"])
        results["auth_token"] = NotifyTwilio.unquote(results["password"])

        # Auth Token
        if "token" in results["qsd"] and len(results["qsd"]["token"]):
            # Extract the account sid from an argument
            results["auth_token"] = NotifyTwilio.unquote(
                results["qsd"]["token"]
            )

        # Account SID
        if "sid" in results["qsd"] and len(results["qsd"]["sid"]):
            # Extract the account sid from an argument
            results["account_sid"] = NotifyTwilio.unquote(
                results["qsd"]["sid"]
            )

        # API Key
        if "apikey" in results["qsd"] and len(results["qsd"]["apikey"]):
            results["apikey"] = results["qsd"]["apikey"]

        # Support the 'from'  and 'source' variable so that we can support
        # targets this way too.
        # The 'from' makes it easier to use yaml configuration
        if "from" in results["qsd"] and len(results["qsd"]["from"]):
            results["source"] = NotifyTwilio.unquote(results["qsd"]["from"])
        if "source" in results["qsd"] and len(results["qsd"]["source"]):
            results["source"] = NotifyTwilio.unquote(results["qsd"]["source"])

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifyTwilio.parse_phone_no(
                results["qsd"]["to"], prefix=True
            )

        return results
