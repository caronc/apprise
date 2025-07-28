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

# Sign-up with https://burstsms.com/
#
# Define your API Secret here and acquire your API Key
#  - https://can.transmitsms.com/profile
#
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


class BurstSMSCountryCode:
    # Australia
    AU = "au"
    # New Zeland
    NZ = "nz"
    # United Kingdom
    UK = "gb"
    # United States
    US = "us"


BURST_SMS_COUNTRY_CODES = (
    BurstSMSCountryCode.AU,
    BurstSMSCountryCode.NZ,
    BurstSMSCountryCode.UK,
    BurstSMSCountryCode.US,
)


class NotifyBurstSMS(NotifyBase):
    """A wrapper for Burst SMS Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Burst SMS"

    # The services URL
    service_url = "https://burstsms.com/"

    # The default protocol
    secure_protocol = "burstsms"

    # The maximum amount of SMS Messages that can reside within a single
    # batch transfer based on:
    #  https://developer.transmitsms.com/#74911cf8-dec6-4319-a499-7f535a7fd08c
    default_batch_size = 500

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_burst_sms"

    # Burst SMS uses the http protocol with JSON requests
    notify_url = "https://api.transmitsms.com/send-sms.json"

    # The maximum length of the body
    body_maxlen = 160

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Define object templates
    templates = ("{schema}://{apikey}:{secret}@{sender_id}/{targets}",)

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "apikey": {
                "name": _("API Key"),
                "type": "string",
                "required": True,
                "regex": (r"^[a-z0-9]+$", "i"),
                "private": True,
            },
            "secret": {
                "name": _("API Secret"),
                "type": "string",
                "private": True,
                "required": True,
                "regex": (r"^[a-z0-9]+$", "i"),
            },
            "sender_id": {
                "name": _("Sender ID"),
                "type": "string",
                "required": True,
                "map_to": "source",
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
            "from": {
                "alias_of": "sender_id",
            },
            "key": {
                "alias_of": "apikey",
            },
            "secret": {
                "alias_of": "secret",
            },
            "country": {
                "name": _("Country"),
                "type": "choice:string",
                "values": BURST_SMS_COUNTRY_CODES,
                "default": BurstSMSCountryCode.US,
            },
            # Validity
            # Expire a message send if it is undeliverable (defined in minutes)
            # If set to Zero (0); this is the default and sets the max validity
            # period
            "validity": {"name": _("validity"), "type": "int", "default": 0},
            "batch": {
                "name": _("Batch Mode"),
                "type": "bool",
                "default": False,
            },
        },
    )

    def __init__(
        self,
        apikey,
        secret,
        source,
        targets=None,
        country=None,
        validity=None,
        batch=None,
        **kwargs,
    ):
        """Initialize Burst SMS Object."""
        super().__init__(**kwargs)

        # API Key (associated with project)
        self.apikey = validate_regex(
            apikey, *self.template_tokens["apikey"]["regex"]
        )
        if not self.apikey:
            msg = f"An invalid Burst SMS API Key ({apikey}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # API Secret (associated with project)
        self.secret = validate_regex(
            secret, *self.template_tokens["secret"]["regex"]
        )
        if not self.secret:
            msg = f"An invalid Burst SMS API Secret ({secret}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        if not country:
            self.country = self.template_args["country"]["default"]

        else:
            self.country = country.lower().strip()
            if country not in BURST_SMS_COUNTRY_CODES:
                msg = (
                    f"An invalid Burst SMS country ({country}) was specified."
                )
                self.logger.warning(msg)
                raise TypeError(msg)

        # Set our Validity
        self.validity = self.template_args["validity"]["default"]
        if validity:
            try:
                self.validity = int(validity)

            except (ValueError, TypeError):
                msg = (
                    f"The Burst SMS Validity specified ({validity}) is"
                    " invalid."
                )
                self.logger.warning(msg)
                raise TypeError(msg) from None

        # Prepare Batch Mode Flag
        self.batch = (
            self.template_args["batch"]["default"] if batch is None else batch
        )

        # The Sender ID
        self.source = validate_regex(source)
        if not self.source:
            msg = f"The Account Sender ID specified ({source}) is invalid."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Parse our targets
        self.targets = []

        for target in parse_phone_no(targets):
            # Validate targets and drop bad ones:
            result = is_phone_no(target)
            if not result:
                self.logger.warning(
                    f"Dropped invalid phone # ({target}) specified.",
                )
                continue

            # store valid phone number
            self.targets.append(result["full"])

        return

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform Burst SMS Notification."""

        if not self.targets:
            self.logger.warning(
                "There are no valid Burst SMS targets to notify."
            )
            return False

        # error tracking (used for function return)
        has_error = False

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Accept": "application/json",
        }

        # Prepare our authentication
        auth = (self.apikey, self.secret)

        # Prepare our payload
        payload = {
            "countrycode": self.country,
            "message": body,
            # Sender ID
            "from": self.source,
            # The to gets populated in the loop below
            "to": None,
        }

        # Send in batches if identified to do so
        batch_size = 1 if not self.batch else self.default_batch_size

        # Create a copy of the targets list
        targets = list(self.targets)

        for index in range(0, len(targets), batch_size):

            # Prepare our user
            payload["to"] = ",".join(self.targets[index : index + batch_size])

            # Some Debug Logging
            self.logger.debug(
                "Burst SMS POST URL:"
                f" {self.notify_url} (cert_verify={self.verify_certificate})"
            )
            self.logger.debug(f"Burst SMS Payload: {payload}")

            # Always call throttle before any remote server i/o is made
            self.throttle()

            try:
                r = requests.post(
                    self.notify_url,
                    data=payload,
                    headers=headers,
                    auth=auth,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )

                if r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = NotifyBurstSMS.http_response_code_lookup(
                        r.status_code
                    )

                    self.logger.warning(
                        "Failed to send Burst SMS notification to {} "
                        "target(s): {}{}error={}.".format(
                            len(self.targets[index : index + batch_size]),
                            status_str,
                            ", " if status_str else "",
                            r.status_code,
                        )
                    )

                    self.logger.debug(f"Response Details:\r\n{r.content}")

                    # Mark our failure
                    has_error = True
                    continue

                else:
                    self.logger.info(
                        "Sent Burst SMS notification to "
                        f"{len(self.targets[index : index + batch_size])} "
                        "target(s)."
                    )

            except requests.RequestException as e:
                self.logger.warning(
                    f"A Connection error occurred sending Burst SMS "
                    "notification to "
                    f"{len(self.targets[index : index + batch_size])} "
                    "target(s)."
                )
                self.logger.debug(f"Socket Exception: {e!s}")

                # Mark our failure
                has_error = True
                continue

        return not has_error

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {
            "country": self.country,
            "batch": "yes" if self.batch else "no",
        }

        if self.validity:
            params["validity"] = str(self.validity)

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return "{schema}://{key}:{secret}@{source}/{targets}/?{params}".format(
            schema=self.secure_protocol,
            key=self.pprint(self.apikey, privacy, safe=""),
            secret=self.pprint(
                self.secret, privacy, mode=PrivacyMode.Secret, safe=""
            ),
            source=NotifyBurstSMS.quote(self.source, safe=""),
            targets="/".join(
                [NotifyBurstSMS.quote(x, safe="") for x in self.targets]
            ),
            params=NotifyBurstSMS.urlencode(params),
        )

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (self.secure_protocol, self.apikey, self.secret, self.source)

    def __len__(self):
        """Returns the number of targets associated with this notification."""
        #
        # Factor batch into calculation
        #
        batch_size = 1 if not self.batch else self.default_batch_size
        targets = len(self.targets)
        if batch_size > 1:
            targets = int(targets / batch_size) + (
                1 if targets % batch_size else 0
            )

        return targets if targets > 0 else 1

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # The hostname is our source (Sender ID)
        results["source"] = NotifyBurstSMS.unquote(results["host"])

        # Get any remaining targets
        results["targets"] = NotifyBurstSMS.split_path(results["fullpath"])

        # Get our account_side and auth_token from the user/pass config
        results["apikey"] = NotifyBurstSMS.unquote(results["user"])
        results["secret"] = NotifyBurstSMS.unquote(results["password"])

        # API Key
        if "key" in results["qsd"] and len(results["qsd"]["key"]):
            # Extract the API Key from an argument
            results["apikey"] = NotifyBurstSMS.unquote(results["qsd"]["key"])

        # API Secret
        if "secret" in results["qsd"] and len(results["qsd"]["secret"]):
            # Extract the API Secret from an argument
            results["secret"] = NotifyBurstSMS.unquote(
                results["qsd"]["secret"]
            )

        # Support the 'from'  and 'source' variable so that we can support
        # targets this way too.
        # The 'from' makes it easier to use yaml configuration
        if "from" in results["qsd"] and len(results["qsd"]["from"]):
            results["source"] = NotifyBurstSMS.unquote(results["qsd"]["from"])
        if "source" in results["qsd"] and len(results["qsd"]["source"]):
            results["source"] = NotifyBurstSMS.unquote(
                results["qsd"]["source"]
            )

        # Support country
        if "country" in results["qsd"] and len(results["qsd"]["country"]):
            results["country"] = NotifyBurstSMS.unquote(
                results["qsd"]["country"]
            )

        # Support validity value
        if "validity" in results["qsd"] and len(results["qsd"]["validity"]):
            results["validity"] = NotifyBurstSMS.unquote(
                results["qsd"]["validity"]
            )

        # Get Batch Mode Flag
        if "batch" in results["qsd"] and len(results["qsd"]["batch"]):
            results["batch"] = parse_bool(results["qsd"]["batch"])

        # Support the 'to' variable so that we can support rooms this way too
        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifyBurstSMS.parse_phone_no(
                results["qsd"]["to"]
            )

        return results
