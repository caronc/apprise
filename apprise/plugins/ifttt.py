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

# For this plugin to work, you need to add the Maker applet to your profile
# Simply visit https://ifttt.com/search and search for 'Webhooks'
# Or if you're signed in, click here: https://ifttt.com/maker_webhooks
# and click 'Connect'
#
# You'll want to visit the settings of this Applet and pay attention to the
# URL. For example, it might look like this:
#               https://maker.ifttt.com/use/a3nHB7gA9TfBQSqJAHklod
#
# In the above example a3nHB7gA9TfBQSqJAHklod becomes your {webhook_id}
# You will need this to make this notification work correctly
#
# For each event you create you will assign it a name (this will be known as
# the {event} when building your URL.
from json import dumps
import re

import requests

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import parse_list, validate_regex
from .base import NotifyBase


class NotifyIFTTT(NotifyBase):
    """A wrapper for IFTTT Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "IFTTT"

    # The services URL
    service_url = "https://ifttt.com/"

    # The default protocol
    secure_protocol = "ifttt"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_ifttt"

    # Even though you'll add 'Ingredients' as {{ Value1 }} to your Applets,
    # you must use their lowercase value in the HTTP POST.
    ifttt_default_key_prefix = "value"

    # The default IFTTT Key to use when mapping the title text to the IFTTT
    # event. The idea here is if someone wants to over-ride the default and
    # change it to another Ingredient Name (in 2018, you were limited to have
    # value1, value2, and value3).
    ifttt_default_title_key = "value1"

    # The default IFTTT Key to use when mapping the body text to the IFTTT
    # event. The idea here is if someone wants to over-ride the default and
    # change it to another Ingredient Name (in 2018, you were limited to have
    # value1, value2, and value3).
    ifttt_default_body_key = "value2"

    # The default IFTTT Key to use when mapping the body text to the IFTTT
    # event. The idea here is if someone wants to over-ride the default and
    # change it to another Ingredient Name (in 2018, you were limited to have
    # value1, value2, and value3).
    ifttt_default_type_key = "value3"

    # IFTTT uses the http protocol with JSON requests
    notify_url = (
        "https://maker.ifttt.com/trigger/{event}/with/key/{webhook_id}"
    )

    # Define object templates
    templates = ("{schema}://{webhook_id}/{events}",)

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "webhook_id": {
                "name": _("Webhook ID"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "events": {
                "name": _("Events"),
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
                "alias_of": "events",
            },
        },
    )

    # Define our token control
    template_kwargs = {
        "add_tokens": {
            "name": _("Add Tokens"),
            "prefix": "+",
        },
        "del_tokens": {
            "name": _("Remove Tokens"),
            "prefix": "-",
        },
    }

    def __init__(
        self, webhook_id, events, add_tokens=None, del_tokens=None, **kwargs
    ):
        """Initialize IFTTT Object.

        add_tokens can optionally be a dictionary of key/value pairs that you
        want to include in the IFTTT post to the server.

        del_tokens can optionally be a list/tuple/set of tokens that you want
        to eliminate from the IFTTT post.  There isn't much real functionality
        to this one unless you want to remove reference to Value1, Value2,
        and/or Value3
        """
        super().__init__(**kwargs)

        # Webhook ID (associated with project)
        self.webhook_id = validate_regex(webhook_id)
        if not self.webhook_id:
            msg = f"An invalid IFTTT Webhook ID ({webhook_id}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store our Events we wish to trigger
        self.events = parse_list(events)
        if not self.events:
            msg = "You must specify at least one event you wish to trigger on."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Tokens to include in post
        self.add_tokens = {}
        if add_tokens:
            self.add_tokens.update(add_tokens)

        # Tokens to remove
        self.del_tokens = []
        if del_tokens is not None:
            if isinstance(del_tokens, (list, tuple, set)):
                self.del_tokens = del_tokens

            elif isinstance(del_tokens, dict):
                # Convert the dictionary into a list
                self.del_tokens = set(del_tokens.keys())

            else:
                msg = (
                    f"del_token must be a list; {type(del_tokens)!s} was"
                    " provided"
                )
                self.logger.warning(msg)
                raise TypeError(msg)

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform IFTTT Notification."""

        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
        }

        # prepare JSON Object
        payload = {
            self.ifttt_default_title_key: title,
            self.ifttt_default_body_key: body,
            self.ifttt_default_type_key: notify_type,
        }

        # Add any new tokens expected (this can also potentially override
        # any entries defined above)
        payload.update(self.add_tokens)

        # Eliminate fields flagged for removal otherwise ensure all tokens are
        # lowercase since that is what the IFTTT server expects from us.
        payload = {
            x.lower(): y
            for x, y in payload.items()
            if x not in self.del_tokens
        }

        # error tracking (used for function return)
        has_error = False

        # Create a copy of our event lit
        events = list(self.events)

        while len(events):

            # Retrive an entry off of our event list
            event = events.pop(0)

            # URL to transmit content via
            url = self.notify_url.format(
                webhook_id=self.webhook_id,
                event=event,
            )

            self.logger.debug(
                "IFTTT POST URL:"
                f" {url} (cert_verify={self.verify_certificate!r})"
            )
            self.logger.debug(f"IFTTT Payload: {payload!s}")

            # Always call throttle before any remote server i/o is made
            self.throttle()

            try:
                r = requests.post(
                    url,
                    data=dumps(payload),
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )
                self.logger.debug(
                    f"IFTTT HTTP response headers: {r.headers!r}"
                )
                self.logger.debug(f"IFTTT HTTP response body: {r.content!r}")

                if r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = NotifyIFTTT.http_response_code_lookup(
                        r.status_code
                    )

                    self.logger.warning(
                        "Failed to send IFTTT notification to {}: "
                        "{}{}error={}.".format(
                            event,
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
                    self.logger.info(f"Sent IFTTT notification to {event}.")

            except requests.RequestException as e:
                self.logger.warning(
                    f"A Connection error occurred sending IFTTT:{event} "
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
        return (self.secure_protocol, self.webhook_id)

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Our URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        # Store any new key/value pairs added to our list
        params.update({f"+{k}": v for k, v in self.add_tokens})
        params.update({f"-{k}": "" for k in self.del_tokens})

        return "{schema}://{webhook_id}@{events}/?{params}".format(
            schema=self.secure_protocol,
            webhook_id=self.pprint(self.webhook_id, privacy, safe=""),
            events="/".join(
                [NotifyIFTTT.quote(x, safe="") for x in self.events]
            ),
            params=NotifyIFTTT.urlencode(params),
        )

    def __len__(self):
        """Returns the number of targets associated with this notification."""
        return len(self.events)

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Our API Key is the hostname if no user is specified
        results["webhook_id"] = (
            results["user"] if results["user"] else results["host"]
        )

        # Unquote our API Key
        results["webhook_id"] = NotifyIFTTT.unquote(results["webhook_id"])

        # Parse our add_token and del_token arguments (if specified)
        results["add_token"] = results["qsd+"]
        results["del_token"] = results["qsd-"]

        # Our Event
        results["events"] = []
        if results["user"]:
            # If a user was defined, then the hostname is actually a event
            # too
            results["events"].append(NotifyIFTTT.unquote(results["host"]))

        # Now fetch the remaining tokens
        results["events"].extend(NotifyIFTTT.split_path(results["fullpath"]))

        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["events"] += NotifyIFTTT.parse_list(results["qsd"]["to"])

        return results

    @staticmethod
    def parse_native_url(url):
        """
        Support https://maker.ifttt.com/use/WEBHOOK_ID/EVENT_ID
        """

        result = re.match(
            r"^https?://maker\.ifttt\.com/use/"
            r"(?P<webhook_id>[A-Z0-9_-]+)"
            r"((?P<events>(/[A-Z0-9_-]+)+))?"
            r"/?(?P<params>\?.+)?$",
            url,
            re.I,
        )

        if result:
            return NotifyIFTTT.parse_url(
                "{schema}://{webhook_id}{events}{params}".format(
                    schema=NotifyIFTTT.secure_protocol,
                    webhook_id=result.group("webhook_id"),
                    events=(
                        ""
                        if not result.group("events")
                        else "@{}".format(result.group("events"))
                    ),
                    params=(
                        ""
                        if not result.group("params")
                        else result.group("params")
                    ),
                )
            )

        return None
