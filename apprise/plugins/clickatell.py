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

from itertools import chain

# To use this service you will need a Clickatell account to which you can get
# your API_TOKEN at:
#     https://www.clickatell.com/
import requests

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import is_phone_no, parse_phone_no, validate_regex
from .base import NotifyBase


class NotifyClickatell(NotifyBase):
    """A wrapper for Clickatell Notifications."""

    # The default descriptive name associated with the Notification
    service_name = _("Clickatell")

    # The services URL
    service_url = "https://www.clickatell.com/"

    # All notification requests are secure
    secure_protocol = "clickatell"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_clickatell"

    # Clickatell API Endpoint
    notify_url = "https://platform.clickatell.com/messages/http/send"

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    templates = (
        "{schema}://{apikey}/{targets}",
        "{schema}://{source}@{apikey}/{targets}",
    )

    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "apikey": {
                "name": _("API Token"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "source": {
                "name": _("From Phone No"),
                "type": "string",
                "regex": (r"^[0-9\s)(+-]+$", "i"),
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

    template_args = dict(
        NotifyBase.template_args,
        **{
            "apikey": {"alias_of": "apikey"},
            "to": {
                "alias_of": "targets",
            },
            "from": {
                "alias_of": "source",
            },
        },
    )

    def __init__(self, apikey, source=None, targets=None, **kwargs):
        """Initialize Clickatell Object."""

        super().__init__(**kwargs)

        self.apikey = validate_regex(apikey)
        if not self.apikey:
            msg = f"An invalid Clickatell API Token ({apikey}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        self.source = None
        if source:
            result = is_phone_no(source)
            if not result:
                msg = (
                    "The Account (From) Phone # specified "
                    f"({source}) is invalid."
                )
                self.logger.warning(msg)

                raise TypeError(msg)

            # Tidy source
            self.source = result["full"]

        # Used for URL generation afterwards only
        self._invalid_targets = []

        # Parse our targets
        self.targets = []

        for target in parse_phone_no(targets, prefix=True):
            # Validate targets and drop bad ones:
            result = is_phone_no(target)
            if not result:
                self.logger.warning(
                    f"Dropped invalid phone # ({target}) specified.",
                )
                self._invalid_targets.append(target)
                continue

            # store valid phone number
            self.targets.append(result["full"])

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (self.apikey, self.source)

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        return "{schema}://{source}{apikey}/{targets}/?{params}".format(
            schema=self.secure_protocol,
            source=f"{self.source}@" if self.source else "",
            apikey=self.pprint(self.apikey, privacy, safe="="),
            targets="/".join([
                NotifyClickatell.quote(t, safe="")
                for t in chain(self.targets, self._invalid_targets)
            ]),
            params=self.urlencode(params),
        )

    def __len__(self):
        """Returns the number of targets associated with this notification.

        Always return 1 at least
        """
        return len(self.targets) if self.targets else 1

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform Clickatell Notification."""

        if not self.targets:
            # There were no targets to notify
            self.logger.warning("There were no Clickatell targets to notify")
            return False

        headers = {
            "User-Agent": self.app_id,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        params_base = {
            "apiKey": self.apikey,
            "from": self.source,
            "content": body,
        }

        # error tracking (used for function return)
        has_error = False

        for target in self.targets:
            params = params_base.copy()
            params["to"] = target

            # Some Debug Logging
            self.logger.debug(
                "Clickatell GET URL:"
                f" {self.notify_url} (cert_verify={self.verify_certificate})"
            )
            self.logger.debug(f"Clickatell Payload: {params}")

            # Always call throttle before any remote server i/o is made
            self.throttle()

            try:
                r = requests.get(
                    self.notify_url,
                    params=params,
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )

                if (
                    r.status_code != requests.codes.ok
                    and r.status_code != requests.codes.accepted
                ):
                    # We had a problem
                    status_str = self.http_response_code_lookup(r.status_code)

                    self.logger.warning(
                        "Failed to send Clickatell notification: "
                        "{}{}error={}.".format(
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
                        "Sent Clickatell notification to %s", target
                    )

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending Clickatell: to %s ",
                    target,
                )
                self.logger.debug(f"Socket Exception: {e!s}")
                # Mark our failure
                has_error = True
                continue

        return not has_error

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't parse the URL
            return results

        results["targets"] = NotifyClickatell.split_path(results["fullpath"])
        results["apikey"] = NotifyClickatell.unquote(results["host"])

        if results["user"]:
            results["source"] = NotifyClickatell.unquote(results["user"])

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifyClickatell.parse_phone_no(
                results["qsd"]["to"]
            )

        # Support the 'from'  and 'source' variable so that we can support
        # targets this way too.
        # The 'from' makes it easier to use yaml configuration
        if "from" in results["qsd"] and len(results["qsd"]["from"]):
            results["source"] = NotifyClickatell.unquote(
                results["qsd"]["from"]
            )

        return results
