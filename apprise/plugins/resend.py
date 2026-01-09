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

# You will need an API Key for this plugin to work.
# From the Settings -> API Keys you can click "Create API Key" if you don't
# have one already. The key must have at least the "Mail Send" permission
# to work.
#
# The schema to use the plugin looks like this:
#    {schema}://{apikey}:{from_addr}
#
# Your {from_addr} must be comprissed of your Resend Authenticated
# Domain.

# Simple API Reference:
#  - https://resend.com/onboarding

from email.utils import formataddr
from json import dumps
import logging

import requests

from .. import exception
from ..common import NotifyFormat, NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import is_email, parse_emails, validate_regex
from ..utils.sanitize import sanitize_payload
from .base import NotifyBase

RESEND_HTTP_ERROR_MAP = {
    200: "Successful request.",
    400: "Check that the parameters were correct.",
    401: "The API key used was missing.",
    403: "The API key used was invalid.",
    404: "The resource was not found.",
    429: "The rate limit was exceeded.",
}


class NotifyResend(NotifyBase):
    """A wrapper for Notify Resend Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Resend"

    # The services URL
    service_url = "https://resend.com"

    # The default secure protocol
    secure_protocol = "resend"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/resend/"

    # Default to markdown
    notify_format = NotifyFormat.HTML

    # The default Email API URL to use
    notify_url = "https://api.resend.com/emails"

    # Support attachments
    attachment_support = True

    # Allow 300 requests per minute.
    # 60/300 = 0.2
    request_rate_per_sec = 0.2

    # The default subject to use if one isn't specified.
    default_empty_subject = "<no subject>"

    # Define object templates
    templates = (
        "{schema}://{apikey}:{from_addr}",
        "{schema}://{apikey}:{from_addr}/{targets}",
    )

    # Define our template arguments
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "apikey": {
                "name": _("API Key"),
                "type": "string",
                "private": True,
                "required": True,
                "regex": (r"^[A-Z0-9._-]+$", "i"),
            },
            "from_addr": {
                "name": _("Source Email"),
                "type": "string",
                "required": True,
            },
            "target_email": {
                "name": _("Target Email"),
                "type": "string",
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
            "cc": {
                "name": _("Carbon Copy"),
                "type": "list:string",
            },
            "bcc": {
                "name": _("Blind Carbon Copy"),
                "type": "list:string",
            },
            "reply": {
                "name": _("Reply To"),
                "type": "list:string",
                "map_to": "reply_to",
            },
            "from": {
                "map_to": "from_addr",
            },
            "name": {
                "name": _("From Name"),
                "map_to": "from_addr",
            },
            "apikey": {
                "map_to": "apikey",
            },
        },
    )

    def __init__(
        self, apikey, from_addr, targets=None, cc=None, bcc=None,
        reply_to=None, **kwargs):
        """Initialize Notify Resend Object."""
        super().__init__(**kwargs)

        # API Key (associated with project)
        self.apikey = validate_regex(
            apikey, *self.template_tokens["apikey"]["regex"]
        )
        if not self.apikey:
            msg = f"An invalid Resend API Key ({apikey}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Acquire Targets (To Emails)
        self.targets = []

        # Acquire Carbon Copies
        self.cc = set()

        # Acquire Blind Carbon Copies
        self.bcc = set()

        # Acquire Reply To
        self.reply_to = set()

        # For tracking our email -> name lookups
        self.names = {}

        result = is_email(from_addr)
        if not result:
            # Invalid from
            msg = "Invalid ~From~ email specified: {}".format(from_addr)
            self.logger.warning(msg)
            raise TypeError(msg)

        # initialize our from address
        self.from_addr = (
            result["name"] if result["name"] is not None else False,
            result["full_email"],
        )

        # Update our Name if specified
        self.names[self.from_addr[1]] = (
            result["name"] if result["name"] else False
        )

        # Acquire our targets
        targets = parse_emails(targets)
        if targets:
            # Validate recipients (to:) and drop bad ones:
            for recipient in targets:

                result = is_email(recipient)
                if result:
                    self.targets.append(result["full_email"])
                    continue

                self.logger.warning(
                    f"Dropped invalid email ({recipient}) specified.",
                )
        else:
            # If our target email list is empty we want to add ourselves to it
            self.targets.append(self.from_addr[1])

        # Validate recipients (cc:) and drop bad ones:
        for recipient in parse_emails(cc):

            result = is_email(recipient)
            if result:
                self.cc.add(result["full_email"])

                # Index our name (if one exists)
                self.names[result["full_email"]] = (
                    result["name"] if result["name"] else False
                )
                continue

            self.logger.warning(
                f"Dropped invalid Carbon Copy email ({recipient}) specified.",
            )

        # Validate recipients (bcc:) and drop bad ones:
        for recipient in parse_emails(bcc):

            result = is_email(recipient)
            if result:
                self.bcc.add(result["full_email"])
                continue

            self.logger.warning(
                "Dropped invalid Blind Carbon Copy email "
                f"({recipient}) specified.",
            )

        # Validate recipients (reply-to:) and drop bad ones:
        for recipient in parse_emails(reply_to):
            result = is_email(recipient)
            if result:
                self.reply_to.add(result["full_email"])

                # Index our name (if one exists)
                self.names[result["full_email"]] = (
                    result["name"] if result["name"] else False
                )
                continue

            self.logger.warning(
                "Dropped invalid Reply To email ({}) specified.".format(
                    recipient
                ),
            )

        return

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (self.secure_protocol, self.apikey, self.from_addr)

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Our URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        if self.cc:
            # Handle our Carbon Copy Addresses
            params["cc"] = ",".join([
                formataddr(
                    (self.names.get(e, False), e),
                    # Swap comma for it's escaped url code (if detected) since
                    # we're using that as a delimiter
                    charset="utf-8",
                ).replace(",", "%2C")
                for e in self.cc
            ])

        if len(self.bcc) > 0:
            # Handle our Blind Carbon Copy Addresses
            params["bcc"] = ",".join(self.bcc)

        if self.reply_to:
            # Handle our Reply-To Addresses
            params["reply"] = ",".join([
                formataddr(
                    (self.names.get(e, False), e),
                    # Swap comma for its escaped url code (if detected) since
                    # we're using that as a delimiter
                    charset="utf-8",
                ).replace(",", "%2C")
                for e in self.reply_to
            ])

        # a simple boolean check as to whether we display our target emails
        # or not
        has_targets = not (
            len(self.targets) == 1 and self.targets[0] == self.from_addr[1])

        if self.from_addr[0] and self.from_addr[0] != self.app_id:
            # A custom name was provided
            params["name"] = self.from_addr[0]

        return "{schema}://{apikey}:{from_addr}/{targets}?{params}".format(
            schema=self.secure_protocol,
            apikey=self.pprint(self.apikey, privacy, safe=""),
            # never encode email since it plays a huge role in our hostname
            from_addr=self.from_addr[1],
            targets=(
                ""
                if not has_targets
                else "/".join(
                    [NotifyResend.quote(x, safe="@") for x in self.targets]
                )
            ),
            params=NotifyResend.urlencode(params),
        )

    def __len__(self):
        """Returns the number of targets associated with this notification."""
        return len(self.targets)

    def send(
        self,
        body,
        title="",
        notify_type=NotifyType.INFO,
        attach=None,
        **kwargs,
    ):
        """Perform Resend Notification."""

        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.apikey}",
        }

        # error tracking (used for function return)
        has_error = False

        # Prepare our from_name
        self.from_addr[0] \
            if self.from_addr[0] is not False else self.app_id

        _payload = {
            "from": formataddr(self.from_addr, charset="utf-8"),
            # A subject is a requirement, so if none is specified we must
            # set a default with at least 1 character or Resend will deny
            # our request
            "subject": title if title else self.default_empty_subject,
            (
                "text" if self.notify_format == NotifyFormat.TEXT else "html"
            ): body,
        }

        if attach and self.attachment_support:
            attachments = []

            # Send our attachments
            for no, attachment in enumerate(attach, start=1):
                # Perform some simple error checking
                if not attachment:
                    # We could not access the attachment
                    self.logger.error(
                        "Could not access Resend attachment"
                        f" {attachment.url(privacy=True)}."
                    )
                    return False

                try:
                    attachments.append({
                        "content": attachment.base64(),
                        "filename": (
                            attachment.name
                            if attachment.name
                            else f"file{no:03}.dat"
                        ),
                        "type": "application/octet-stream",
                        "disposition": "attachment",
                    })

                except exception.AppriseException:
                    # We could not access the attachment
                    self.logger.error(
                        "Could not access Resend attachment"
                        f" {attachment.url(privacy=True)}."
                    )
                    return False

                self.logger.debug(
                    "Appending Resend attachment"
                    f" {attachment.url(privacy=True)}"
                )

            # Append our attachments to the payload
            _payload.update({
                "attachments": attachments,
            })

        targets = list(self.targets)
        while len(targets) > 0:
            target = targets.pop(0)

            # Create a copy of our template
            payload = _payload.copy()

            # unique cc/bcc list management
            cc = self.cc - self.bcc - {target}
            bcc = self.bcc - {target}

            # handle our reply to
            reply_to = self.reply_to - {target}

            # Format our cc addresses to support the Name field
            cc = [
                formataddr((self.names.get(addr, False), addr),
                           charset="utf-8")
                for addr in cc
            ]

            # Format our reply-to addresses to support the Name field
            reply_to = [
                formataddr((self.names.get(addr, False), addr),
                           charset="utf-8")
                for addr in reply_to
            ]

            # Set our target
            payload["to"] = target

            if cc:
                payload["cc"] = cc

            if len(bcc):
                payload["bcc"] = list(bcc)

            if reply_to:
                payload["reply_to"] = reply_to

            # Some Debug Logging
            if self.logger.isEnabledFor(logging.DEBUG):
                # Due to attachments; output can be quite heavy and io
                # intensive.
                # To accommodate this, we only show our debug payload
                # information if required.
                self.logger.debug(
                    "Resend POST URL:"
                    f" {self.notify_url} "
                    f"(cert_verify={self.verify_certificate!r})"
                )
                self.logger.debug(
                    "Resend Payload: %s", sanitize_payload(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.post(
                    self.notify_url,
                    data=dumps(payload),
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )
                if r.status_code not in (
                    requests.codes.ok,
                    requests.codes.accepted,
                ):
                    # We had a problem
                    status_str = NotifyResend.http_response_code_lookup(
                        r.status_code, RESEND_HTTP_ERROR_MAP
                    )

                    self.logger.warning(
                        "Failed to send Resend notification to {}: "
                        "{}{}error={}.".format(
                            target,
                            status_str,
                            ", " if status_str else "",
                            r.status_code,
                        )
                    )

                    self.logger.debug(
                        "Response Details:\r\n%r", (r.content or b"")[:2000])

                    # Mark our failure
                    has_error = True
                    continue

                else:
                    self.logger.info(f"Sent Resend notification to {target}.")

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending Resend "
                    f"notification to {target}."
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
            # We're done early as we couldn't load the results
            return results

        # Our URL looks like this:
        #    {schema}://{apikey}:{from_addr}/{targets}
        #
        # which actually equates to:
        #    {schema}://{user}:{password}@{host}/{email1}/{email2}/etc..
        #                 ^       ^         ^
        #                 |       |         |
        #              apikey     -from addr-

        # Prepare our API Key
        if "apikey" in results["qsd"] and len(results["qsd"]["apikey"]):
            results["apikey"] = \
                NotifyResend.unquote(results["qsd"]["apikey"])

        else:
            results["apikey"] = NotifyResend.unquote(results["user"])

        # Our Targets
        results["targets"] = []

        # Attempt to detect 'from' email address
        if "from" in results["qsd"] and len(results["qsd"]["from"]):
            results["from_addr"] = NotifyResend.unquote(results["qsd"]["from"])

            if results.get("host"):
                results["targets"].append(
                    NotifyResend.unquote(results["host"]))

        else:
            # Prepare our From Email Address
            results["from_addr"] = "{}@{}".format(
                NotifyResend.unquote(
                    results["password"]
                    if results["password"] else results["user"]),
                NotifyResend.unquote(results["host"]),
            )

        if "name" in results["qsd"] and len(results["qsd"]["name"]):
            results["from_addr"] = formataddr((
                NotifyResend.unquote(results["qsd"]["name"]),
                results["from_addr"]), charset="utf-8")

        # Acquire our targets
        results["targets"].extend(NotifyResend.split_path(results["fullpath"]))

        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifyResend.parse_list(results["qsd"]["to"])

        # Handle Carbon Copy Addresses
        if "cc" in results["qsd"] and len(results["qsd"]["cc"]):
            results["cc"] = NotifyResend.parse_list(results["qsd"]["cc"])

        # Handle Blind Carbon Copy Addresses
        if "bcc" in results["qsd"] and len(results["qsd"]["bcc"]):
            results["bcc"] = NotifyResend.parse_list(results["qsd"]["bcc"])

        # Handle Reply To Addresses
        if "reply" in results["qsd"] and len(results["qsd"]["reply"]):
            results["reply_to"] = results["qsd"]["reply"]

        return results
