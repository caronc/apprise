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

# Signup @ https://www.sparkpost.com
#
# Ensure you've added a Senders Domain and have generated yourself an
# API Key at:
#   https://app.sparkpost.com/dashboard

# Note: For SMTP Access, your API key must have at least been granted the
#   'Send via SMTP' privileges.

# From here you can click on the domain you're interested in. You can acquire
# the API Key from here which will look something like:
#    1e1d479fcf1a87527e9411e083c700689fa1acdc
#
# Knowing this, you can buid your sparkpost url as follows:
#  sparkpost://{user}@{domain}/{apikey}
#  sparkpost://{user}@{domain}/{apikey}/{email}
#
# You can email as many addresses as you want as:
#  sparkpost://{user}@{domain}/{apikey}/{email1}/{email2}/{emailN}
#
#  The {user}@{domain} effectively assembles the 'from' email address
#  the email will be transmitted from.  If no email address is specified
#  then it will also become the 'to' address as well.
#
#  The {domain} must cross reference a domain you've set up with Spark Post
#
# API Documentation: https://developers.sparkpost.com/api/
# Specifically: https://developers.sparkpost.com/api/transmissions/
import contextlib
from email.utils import formataddr
from json import dumps, loads

import requests

from .. import exception
from ..common import NotifyFormat, NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import is_email, parse_bool, parse_emails, validate_regex
from .base import NotifyBase

# Provide some known codes SparkPost uses and what they translate to:
# Based on https://www.sparkpost.com/docs/tech-resources/extended-error-codes/
SPARKPOST_HTTP_ERROR_MAP = {
    400: "A bad request was made to the server",
    401: "Invalid User ID and/or Unauthorized User",
    403: "Permission Denied; the provided API Key was not valid",
    404: "There is a problem with the server query URI.",
    405: "Invalid HTTP method",
    420: "Sending limit reached.",
    422: "Invalid data/format/type/length",
    429: "To many requests per sec; rate limit",
}


class SparkPostRegion:
    """Regions."""

    US = "us"
    EU = "eu"


# SparkPost APIs
SPARKPOST_API_LOOKUP = {
    SparkPostRegion.US: "https://api.sparkpost.com/api/v1",
    SparkPostRegion.EU: "https://api.eu.sparkpost.com/api/v1",
}

# A List of our regions we can use for verification
SPARKPOST_REGIONS = (
    SparkPostRegion.US,
    SparkPostRegion.EU,
)


class NotifySparkPost(NotifyBase):
    """A wrapper for SparkPost Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "SparkPost"

    # The services URL
    service_url = "https://sparkpost.com/"

    # Support attachments
    attachment_support = True

    # All notification requests are secure
    secure_protocol = "sparkpost"

    # SparkPost advertises they allow 300 requests per minute.
    # 60/300 = 0.2
    request_rate_per_sec = 0.20

    # Words straight from their website:
    #    https://developers.sparkpost.com/api/#header-rate-limiting
    # These limits are dynamic, but as a general rule, wait 1 to 5 seconds
    # after receiving a 429 response before requesting again.

    # As a simple work around, this is what we will do... Wait X seconds
    # (defined below) before trying again when we get a 429 error
    sparkpost_retry_wait_sec = 5

    # The maximum number of times we'll retry to send our message when we've
    # reached a throttling situatin before giving up
    sparkpost_retry_attempts = 3

    # The maximum amount of emails that can reside within a single
    # batch transfer based on:
    #  https://www.sparkpost.com/docs/tech-resources/\
    #       smtp-rest-api-performance/#sending-via-the-transmission-rest-api
    default_batch_size = 2000

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_sparkpost"

    # Default Notify Format
    notify_format = NotifyFormat.HTML

    # Define object templates
    templates = (
        "{schema}://{user}@{host}:{apikey}/",
        "{schema}://{user}@{host}:{apikey}/{targets}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "user": {
                "name": _("User Name"),
                "type": "string",
                "required": True,
            },
            "host": {
                "name": _("Domain"),
                "type": "string",
                "required": True,
            },
            "apikey": {
                "name": _("API Key"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "targets": {
                "name": _("Target Emails"),
                "type": "list:string",
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "name": {
                "name": _("From Name"),
                "type": "string",
                "map_to": "from_name",
            },
            "region": {
                "name": _("Region Name"),
                "type": "choice:string",
                "values": SPARKPOST_REGIONS,
                "default": SparkPostRegion.US,
                "map_to": "region_name",
            },
            "to": {
                "alias_of": "targets",
            },
            "cc": {
                "name": _("Carbon Copy"),
                "type": "list:string",
            },
            "bcc": {
                "name": _("Blind Carbon Copy"),
                "type": "list:string",
            },
            "batch": {
                "name": _("Batch Mode"),
                "type": "bool",
                "default": False,
            },
        },
    )

    # Define any kwargs we're using
    template_kwargs = {
        "headers": {
            "name": _("Email Header"),
            "prefix": "+",
        },
        "tokens": {
            "name": _("Template Tokens"),
            "prefix": ":",
        },
    }

    def __init__(
        self,
        apikey,
        targets,
        cc=None,
        bcc=None,
        from_name=None,
        region_name=None,
        headers=None,
        tokens=None,
        batch=None,
        **kwargs,
    ):
        """Initialize SparkPost Object."""
        super().__init__(**kwargs)

        # API Key (associated with project)
        self.apikey = validate_regex(apikey)
        if not self.apikey:
            msg = f"An invalid SparkPost API Key ({apikey}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Validate our username
        if not self.user:
            msg = "No SparkPost username was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Acquire Email 'To'
        self.targets = []

        # Acquire Carbon Copies
        self.cc = set()

        # Acquire Blind Carbon Copies
        self.bcc = set()

        # For tracking our email -> name lookups
        self.names = {}

        # Store our region
        try:
            self.region_name = (
                self.template_args["region"]["default"]
                if region_name is None
                else region_name.lower()
            )

            if self.region_name not in SPARKPOST_REGIONS:
                # allow the outer except to handle this common response
                raise IndexError()

        except (AttributeError, IndexError, TypeError):
            # Invalid region specified
            msg = f"The SparkPost region specified ({region_name}) is invalid."
            self.logger.warning(msg)
            raise TypeError(msg) from None

        # Get our From username (if specified)
        self.from_name = from_name

        # Get our from email address
        self.from_addr = f"{self.user}@{self.host}"

        if not is_email(self.from_addr):
            # Parse Source domain based on from_addr
            msg = f"Invalid ~From~ email format: {self.from_addr}"
            self.logger.warning(msg)
            raise TypeError(msg)

        self.headers = {}
        if headers:
            # Store our extra headers
            self.headers.update(headers)

        self.tokens = {}
        if tokens:
            # Store our template tokens
            self.tokens.update(tokens)

        # Prepare Batch Mode Flag
        self.batch = (
            self.template_args["batch"]["default"] if batch is None else batch
        )

        if targets:
            # Validate recipients (to:) and drop bad ones:
            for recipient in parse_emails(targets):
                result = is_email(recipient)
                if result:
                    self.targets.append((
                        result["name"] if result["name"] else False,
                        result["full_email"],
                    ))
                    continue

                self.logger.warning(
                    f"Dropped invalid To email ({recipient}) specified.",
                )

        else:
            # If our target email list is empty we want to add ourselves to it
            self.targets.append(
                (self.from_name if self.from_name else False, self.from_addr)
            )

        # Validate recipients (cc:) and drop bad ones:
        for recipient in parse_emails(cc):
            email = is_email(recipient)
            if email:
                self.cc.add(email["full_email"])

                # Index our name (if one exists)
                self.names[email["full_email"]] = (
                    email["name"] if email["name"] else False
                )
                continue

            self.logger.warning(
                f"Dropped invalid Carbon Copy email ({recipient}) specified.",
            )

        # Validate recipients (bcc:) and drop bad ones:
        for recipient in parse_emails(bcc):
            email = is_email(recipient)
            if email:
                self.bcc.add(email["full_email"])

                # Index our name (if one exists)
                self.names[email["full_email"]] = (
                    email["name"] if email["name"] else False
                )
                continue

            self.logger.warning(
                "Dropped invalid Blind Carbon Copy email "
                f"({recipient}) specified.",
            )

    def __post(self, payload, retry):
        """Performs the actual post and returns the response."""
        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": self.apikey,
        }

        # Prepare our URL as it's based on our hostname
        url = f"{SPARKPOST_API_LOOKUP[self.region_name]}/transmissions/"

        # Some Debug Logging
        self.logger.debug(
            "SparkPost POST URL:"
            f" {url} (cert_verify={self.verify_certificate})"
        )

        if "attachments" in payload["content"]:
            # Since we print our payload; attachments make it a bit too noisy
            # we just strip out the data block to accomodate it
            log_payload = {k: v for k, v in payload.items() if k != "content"}
            log_payload["content"] = {
                k: v
                for k, v in payload["content"].items()
                if k != "attachments"
            }
            log_payload["content"]["attachments"] = [
                {k: v for k, v in x.items() if k != "data"}
                for x in payload["content"]["attachments"]
            ]
        else:
            # No tidying is needed
            log_payload = payload

        self.logger.debug(f"SparkPost Payload: {log_payload}")

        wait = None

        # For logging output of success and errors; we get a head count
        # of our outbound details:
        verbose_dest = (
            ", ".join([x["address"]["email"] for x in payload["recipients"]])
            if len(payload["recipients"]) <= 3
            else "{} recipients".format(len(payload["recipients"]))
        )

        # Initialize our response object
        json_response = {}

        # Set ourselves a status code
        status_code = -1

        while 1:  # pragma: no branch

            # Always call throttle before any remote server i/o is made
            self.throttle(wait=wait)
            try:
                r = requests.post(
                    url,
                    data=dumps(payload),
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )

                # A Good response (200) looks like this:
                #     "results": {
                #       "total_rejected_recipients": 0,
                #       "total_accepted_recipients": 1,
                #       "id": "11668787484950529"
                #        }
                #     }
                #
                # A Bad response looks like this:
                # {
                #   "errors": [
                #     {
                #       "description":
                #            "Unconfigured or unverified sending domain.",
                #       "code": "7001",
                #       "message": "Invalid domain"
                #     }
                #   ]
                # }
                #
                with contextlib.suppress(
                        AttributeError, TypeError, ValueError):
                    # Load our JSON Object if we can
                    # ValueError = r.content is Unparsable
                    # TypeError = r.content is None
                    # AttributeError = r is None
                    json_response = loads(r.content)

                status_code = r.status_code

                payload["recipients"] = []
                if status_code == requests.codes.ok:
                    self.logger.info(
                        f"Sent SparkPost notification to {verbose_dest}."
                    )
                    return status_code, json_response

                # We had a problem if we get here
                status_str = NotifyBase.http_response_code_lookup(
                    status_code, SPARKPOST_API_LOOKUP
                )

                self.logger.warning(
                    "Failed to send SparkPost notification to {}: "
                    "{}{}error={}.".format(
                        verbose_dest,
                        status_str,
                        ", " if status_str else "",
                        status_code,
                    )
                )

                self.logger.debug(f"Response Details:\r\n{r.content}")

                if status_code == requests.codes.too_many_requests and retry:
                    retry = retry - 1
                    if retry > 0:
                        wait = self.sparkpost_retry_wait_sec
                        continue

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending SparkPost "
                    "notification"
                )
                self.logger.debug(f"Socket Exception: {e!s}")

            # Anything else and we're done
            return status_code, json_response

        # Our code will never reach here (outside of infinite while loop above)

    def send(
        self,
        body,
        title="",
        notify_type=NotifyType.INFO,
        attach=None,
        **kwargs,
    ):
        """Perform SparkPost Notification."""

        if not self.targets:
            # There is no one to email; we're done
            self.logger.warning(
                "There are no SparkPost Email recipients to notify"
            )
            return False

        # Initialize our has_error flag
        has_error = False

        # Send in batches if identified to do so
        batch_size = 1 if not self.batch else self.default_batch_size

        reply_to = formataddr(
            (self.from_name if self.from_name else False, self.from_addr),
            charset="utf-8",
        )

        payload = {
            "options": {
                # When set to True, an image is included with the email which
                # is used to detect if the user looked at the image or not.
                "open_tracking": False,
                # Track if links were clicked that were found within email
                "click_tracking": False,
            },
            "content": {
                "from": {
                    "name": (
                        self.from_name if self.from_name else self.app_desc
                    ),
                    "email": self.from_addr,
                },
                # SparkPost does not allow empty subject lines or lines that
                # only contain whitespace; Since Apprise allows an empty title
                # parameter we swap empty title entries with the period
                "subject": title if title.strip() else ".",
                "reply_to": reply_to,
            },
        }

        if self.notify_format == NotifyFormat.HTML:
            payload["content"]["html"] = body

        else:
            payload["content"]["text"] = body

        if attach and self.attachment_support:
            # Prepare ourselves an attachment object
            payload["content"]["attachments"] = []

            for no, attachment in enumerate(attach, start=1):
                # Perform some simple error checking
                if not attachment:
                    # We could not access the attachment
                    self.logger.error(
                        "Could not access SparkPost attachment"
                        f" {attachment.url(privacy=True)}."
                    )
                    return False

                try:
                    # Prepare API Upload Payload
                    payload["content"]["attachments"].append({
                        "name": (
                            attachment.name
                            if attachment.name
                            else f"file{no:03}.dat"
                        ),
                        "type": attachment.mimetype,
                        "data": attachment.base64(),
                    })

                except exception.AppriseException:
                    # We could not access the attachment
                    self.logger.error(
                        "Could not access SparkPost attachment"
                        f" {attachment.url(privacy=True)}."
                    )
                    return False

                self.logger.debug(
                    "Appending SparkPost attachment"
                    f" {attachment.url(privacy=True)}"
                )

        # Take a copy of our token dictionary
        tokens = self.tokens.copy()

        # Apply some defaults template values
        tokens["app_body"] = body
        tokens["app_title"] = title
        tokens["app_type"] = notify_type.value
        tokens["app_id"] = self.app_id
        tokens["app_desc"] = self.app_desc
        tokens["app_color"] = self.color(notify_type)
        tokens["app_url"] = self.app_url

        # Store our tokens if they're identified
        payload["substitution_data"] = self.tokens

        # Create a copy of the targets list
        emails = list(self.targets)

        for index in range(0, len(emails), batch_size):
            # Generate our email listing
            payload["recipients"] = []

            # Initialize our cc list
            cc = self.cc - self.bcc

            # Initialize our bcc list
            bcc = set(self.bcc)

            # Initialize our headers
            headers = self.headers.copy()

            for addr in self.targets[index : index + batch_size]:
                entry = {
                    "address": {
                        "email": addr[1],
                    }
                }

                # Strip target out of cc list if in To
                cc = cc - {addr[1]}

                # Strip target out of bcc list if in To
                bcc = bcc - {addr[1]}

                if addr[0]:
                    entry["address"]["name"] = addr[0]

                # Add our recipient to our list
                payload["recipients"].append(entry)

            if cc:
                # Handle our cc List
                for addr in cc:
                    entry = {
                        "address": {
                            "email": addr,
                            "header_to":
                            # Take the first email in the To
                            self.targets[index : index + batch_size][0][1],
                        },
                    }

                    if self.names.get(addr):
                        entry["address"]["name"] = self.names[addr]

                    # Add our recipient to our list
                    payload["recipients"].append(entry)

                headers["CC"] = ",".join(cc)

            # Handle our bcc
            for addr in bcc:
                # Add our recipient to our list
                payload["recipients"].append({
                    "address": {
                        "email": addr,
                        "header_to":
                        # Take the first email in the To
                        self.targets[index : index + batch_size][0][1],
                    },
                })

            if headers:
                payload["content"]["headers"] = headers

            # Send our message
            status_code, response = self.__post(
                payload, self.sparkpost_retry_attempts
            )

            # Failed
            if status_code != requests.codes.ok:
                has_error = True

        return not has_error

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (self.secure_protocol, self.user, self.apikey, self.host)

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {
            "region": self.region_name,
            "batch": "yes" if self.batch else "no",
        }

        # Append our headers into our parameters
        params.update({f"+{k}": v for k, v in self.headers.items()})

        # Append our template tokens into our parameters
        params.update({f":{k}": v for k, v in self.tokens.items()})

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        if self.from_name is not None:
            # from_name specified; pass it back on the url
            params["name"] = self.from_name

        if self.cc:
            # Handle our Carbon Copy Addresses
            params["cc"] = ",".join([
                "{}{}".format(
                    "" if not e not in self.names else f"{self.names[e]}:",
                    e,
                )
                for e in self.cc
            ])

        if self.bcc:
            # Handle our Blind Carbon Copy Addresses
            params["bcc"] = ",".join(self.bcc)

        # a simple boolean check as to whether we display our target emails
        # or not
        has_targets = not (
            len(self.targets) == 1 and self.targets[0][1] == self.from_addr
        )

        return "{schema}://{user}@{host}/{apikey}/{targets}/?{params}".format(
            schema=self.secure_protocol,
            host=self.host,
            user=NotifySparkPost.quote(self.user, safe=""),
            apikey=self.pprint(self.apikey, privacy, safe=""),
            targets=(
                ""
                if not has_targets
                else "/".join([
                    NotifySparkPost.quote(
                        "{}{}".format("" if not e[0] else f"{e[0]}:", e[1]),
                        safe="",
                    )
                    for e in self.targets
                ])
            ),
            params=NotifySparkPost.urlencode(params),
        )

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

        # Get our entries; split_path() looks after unquoting content for us
        # by default
        results["targets"] = NotifySparkPost.split_path(results["fullpath"])

        # Our very first entry is reserved for our api key
        try:
            results["apikey"] = results["targets"].pop(0)

        except IndexError:
            # We're done - no API Key found
            results["apikey"] = None

        if "name" in results["qsd"] and len(results["qsd"]["name"]):
            # Extract from name to associate with from address
            results["from_name"] = NotifySparkPost.unquote(
                results["qsd"]["name"]
            )

        if "region" in results["qsd"] and len(results["qsd"]["region"]):
            # Extract region
            results["region_name"] = NotifySparkPost.unquote(
                results["qsd"]["region"]
            )

        # Handle 'to' email address
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"].append(results["qsd"]["to"])

        # Handle Carbon Copy Addresses
        if "cc" in results["qsd"] and len(results["qsd"]["cc"]):
            results["cc"] = results["qsd"]["cc"]

        # Handle Blind Carbon Copy Addresses
        if "bcc" in results["qsd"] and len(results["qsd"]["bcc"]):
            results["bcc"] = results["qsd"]["bcc"]

        # Add our Meta Headers that the user can provide with their outbound
        # emails
        results["headers"] = {
            NotifyBase.unquote(x): NotifyBase.unquote(y)
            for x, y in results["qsd+"].items()
        }

        # Add our template tokens (if defined)
        results["tokens"] = {
            NotifyBase.unquote(x): NotifyBase.unquote(y)
            for x, y in results["qsd:"].items()
        }

        # Get Batch Mode Flag
        results["batch"] = parse_bool(
            results["qsd"].get(
                "batch", NotifySparkPost.template_args["batch"]["default"]
            )
        )

        return results
