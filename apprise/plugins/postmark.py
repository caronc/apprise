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

# Steps to get your Postmark Server API Token:
#  1. Visit https://account.postmarkapp.com/ and sign in.
#  2. Select the server you wish to send from (or create a new one).
#  3. In the server settings, click "API Tokens".
#  4. Copy the Server API Token shown on that page.
#
#  Your sender address (From Email) must be a verified sender signature
#  or belong to a verified sending domain in Postmark.  Visit:
#    https://account.postmarkapp.com/signature_domains
#
#  Build your Apprise URL as follows:
#    postmark://{apikey}:{from_email}
#    postmark://{apikey}:{from_email}/{to_email}
#    postmark://{apikey}:{from_email}/{to_email1}/{to_email2}/{to_emailN}
#
#  Use the optional query parameters to add CC, BCC, Reply-To:
#    postmark://{apikey}:{from_email}?bcc=bcc@example.com
#    postmark://{apikey}:{from_email}?cc=cc@example.com
#    postmark://{apikey}:{from_email}?reply=reply@example.com
#    postmark://{apikey}:{from_email}?name=Display+Name
#
#  API Reference:
#    https://postmarkapp.com/developer/api/email-api

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

# Provide some known codes Postmark uses and what they translate to.
# Reference: https://postmarkapp.com/developer/api/overview#error-codes
POSTMARK_HTTP_ERROR_MAP = {
    401: "Unauthorized - Invalid or missing Server API Token.",
    422: "Unprocessable Entity - Invalid payload or configuration.",
    429: "Too Many Requests - Rate limit exceeded.",
    500: "Internal Server Error.",
}


class NotifyPostmark(NotifyBase):
    """A wrapper for Postmark Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Postmark"

    # The services URL
    service_url = "https://postmarkapp.com/"

    # The default secure protocol
    secure_protocol = "postmark"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/postmark/"

    # Default to HTML
    notify_format = NotifyFormat.HTML

    # The Postmark email API endpoint
    notify_url = "https://api.postmarkapp.com/email"

    # Support attachments
    attachment_support = True

    # Postmark practical send rate is ~50 messages/second.
    # 60 / 50 = 1.2
    request_rate_per_sec = 1.2

    # The default subject to use if one is not specified
    default_empty_subject = "<no subject>"

    # Define object URL templates
    templates = (
        "{schema}://{apikey}:{from_email}",
        "{schema}://{apikey}:{from_email}/{targets}",
    )

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
            "from_email": {
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
            "name": {
                "name": _("From Name"),
                "type": "string",
                "map_to": "from_name",
            },
            "reply": {
                "name": _("Reply To Email"),
                "type": "list:string",
                "map_to": "reply_to",
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
        },
    )

    def __init__(
        self,
        apikey,
        from_email,
        targets=None,
        cc=None,
        bcc=None,
        from_name=None,
        reply_to=None,
        **kwargs,
    ):
        """Initialize Notify Postmark Object."""
        super().__init__(**kwargs)

        # API Key (Server Token)
        self.apikey = validate_regex(apikey)
        if not self.apikey:
            msg = f"An invalid Postmark API Key ({apikey}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Validate our from email address
        result = is_email(from_email)
        if not result:
            msg = (
                f"An invalid Postmark From email ({from_email}) was specified."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store our from address as a (name, email) tuple
        self.from_addr = (
            result["name"] if result["name"] is not None else False,
            result["full_email"],
        )

        # from_name overrides any name embedded in the from email string
        if from_name:
            self.from_addr = (from_name, self.from_addr[1])

        # For tracking email -> display name lookups
        self.names = {}

        # Acquire Targets (To Emails)
        self.targets = []

        # Acquire Carbon Copies
        self.cc = set()

        # Acquire Blind Carbon Copies
        self.bcc = set()

        # Acquire Reply-To addresses
        self.reply_to = set()

        # Validate recipients (to:) and drop bad ones:
        if targets:
            for recipient in parse_emails(targets):
                result = is_email(recipient)
                if result:
                    self.targets.append(result["full_email"])
                    # Index name if one exists
                    self.names[result["full_email"]] = (
                        result["name"] if result["name"] else False
                    )
                    continue

                self.logger.warning(
                    "Dropped invalid Postmark To email "
                    f"({recipient}) specified.",
                )

        else:
            # Default to the from address when no targets are specified
            self.targets.append(self.from_addr[1])

        # Validate recipients (cc:) and drop bad ones:
        for recipient in parse_emails(cc):
            result = is_email(recipient)
            if result:
                self.cc.add(result["full_email"])
                # Index name if one exists
                self.names[result["full_email"]] = (
                    result["name"] if result["name"] else False
                )
                continue

            self.logger.warning(
                "Dropped invalid Postmark Carbon Copy email "
                f"({recipient}) specified.",
            )

        # Validate recipients (bcc:) and drop bad ones:
        for recipient in parse_emails(bcc):
            result = is_email(recipient)
            if result:
                self.bcc.add(result["full_email"])
                continue

            self.logger.warning(
                "Dropped invalid Postmark Blind Carbon Copy "
                f"email ({recipient}) specified.",
            )

        # Validate reply-to addresses and drop bad ones:
        for recipient in parse_emails(reply_to):
            result = is_email(recipient)
            if result:
                self.reply_to.add(result["full_email"])
                # Index name if one exists
                self.names[result["full_email"]] = (
                    result["name"] if result["name"] else False
                )
                continue

            self.logger.warning(
                "Dropped invalid Postmark Reply To email "
                f"({recipient}) specified.",
            )

        return

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (self.secure_protocol, self.apikey, self.from_addr[1])

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Our URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        # Include from display name if one is set
        if self.from_addr[0]:
            params["name"] = self.from_addr[0]

        if self.cc:
            # Handle our Carbon Copy Addresses
            params["cc"] = ",".join(
                [
                    formataddr(
                        (self.names.get(e, False), e),
                        charset="utf-8",
                    ).replace(",", "%2C")
                    for e in self.cc
                ]
            )

        if self.bcc:
            # Handle our Blind Carbon Copy Addresses
            params["bcc"] = ",".join(self.bcc)

        if self.reply_to:
            # Handle our Reply-To Addresses
            params["reply"] = ",".join(
                [
                    formataddr(
                        (self.names.get(e, False), e),
                        charset="utf-8",
                    ).replace(",", "%2C")
                    for e in self.reply_to
                ]
            )

        # Determine whether to display target emails in the URL
        has_targets = not (
            len(self.targets) == 1 and self.targets[0] == self.from_addr[1]
        )

        return "{schema}://{apikey}:{from_email}/{targets}?{params}".format(
            schema=self.secure_protocol,
            apikey=self.pprint(self.apikey, privacy, safe=""),
            # never encode email since it plays a role in our hostname
            from_email=self.from_addr[1],
            targets=(
                ""
                if not has_targets
                else "/".join(
                    [NotifyPostmark.quote(x, safe="@") for x in self.targets]
                )
            ),
            params=NotifyPostmark.urlencode(params),
        )

    def __len__(self):
        """Returns the number of targets associated with this notification."""
        return max(len(self.targets), 1)

    def send(
        self,
        body,
        title="",
        notify_type=NotifyType.INFO,
        attach=None,
        **kwargs,
    ):
        """Perform Postmark Notification."""

        if not self.targets:
            # There is no one to email; we're done
            self.logger.warning(
                "There are no Postmark email recipients to notify"
            )
            return False

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Postmark-Server-Token": self.apikey,
        }

        # error tracking (used for function return)
        has_error = False

        # Prepare the From field (with optional display name)
        from_field = formataddr(self.from_addr, charset="utf-8")

        # Base payload template (shared across all targets)
        payload_ = {
            "From": from_field,
            "Subject": (title if title else self.default_empty_subject),
        }

        # Set body content based on the notify format
        if self.notify_format == NotifyFormat.HTML:
            payload_["HtmlBody"] = body
        else:
            payload_["TextBody"] = body

        if attach and self.attachment_support:
            # Prepare attachment list
            attachments = []

            for no, attachment in enumerate(attach, start=1):
                # Perform some simple error checking
                if not attachment:
                    # We could not access the attachment
                    self.logger.error(
                        "Could not access Postmark attachment"
                        f" {attachment.url(privacy=True)}."
                    )
                    return False

                try:
                    # Append base64-encoded attachment to list
                    attachments.append(
                        {
                            "Name": (
                                attachment.name
                                if attachment.name
                                else f"file{no:03}.dat"
                            ),
                            "Content": attachment.base64(),
                            "ContentType": attachment.mimetype,
                        }
                    )

                except exception.AppriseException:
                    # We could not access the attachment
                    self.logger.error(
                        "Could not access Postmark attachment"
                        f" {attachment.url(privacy=True)}."
                    )
                    return False

                self.logger.debug(
                    "Appending Postmark attachment"
                    f" {attachment.url(privacy=True)}"
                )

            # Append our attachment list to the base payload
            payload_["Attachments"] = attachments

        # Iterate over each recipient target
        targets = list(self.targets)
        while len(targets) > 0:
            target = targets.pop(0)

            # Create a per-target copy of our base payload
            payload = payload_.copy()

            # Unique cc/bcc/reply-to management -- remove target from each
            cc = self.cc - self.bcc - {target}
            bcc = self.bcc - {target}
            reply_to = self.reply_to - {target}

            # Set our main recipient
            payload["To"] = target

            if cc:
                # Format CC addresses with optional display names
                payload["Cc"] = ",".join(
                    [
                        formataddr(
                            (self.names.get(a, False), a),
                            charset="utf-8",
                        )
                        for a in cc
                    ]
                )

            if bcc:
                # BCC addresses (plain, no display names)
                payload["Bcc"] = ",".join(bcc)

            if reply_to:
                # Format Reply-To addresses with optional display names
                payload["ReplyTo"] = ",".join(
                    [
                        formataddr(
                            (self.names.get(a, False), a),
                            charset="utf-8",
                        )
                        for a in reply_to
                    ]
                )

            # Some Debug Logging
            if self.logger.isEnabledFor(logging.DEBUG):
                # Due to attachments, output can be quite heavy; only
                # show the debug payload when debug logging is active.
                self.logger.debug(
                    "Postmark POST URL:"
                    f" {self.notify_url} "
                    f"(cert_verify={self.verify_certificate!r})"
                )
                self.logger.debug(
                    "Postmark Payload: %s", sanitize_payload(payload)
                )

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
                if r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = NotifyPostmark.http_response_code_lookup(
                        r.status_code, POSTMARK_HTTP_ERROR_MAP
                    )

                    self.logger.warning(
                        "Failed to send Postmark notification to "
                        "{}: {}{}error={}.".format(
                            target,
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

                else:
                    self.logger.info(
                        f"Sent Postmark notification to {target}."
                    )

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending Postmark "
                    f"notification to {target}."
                )
                self.logger.debug(f"Socket Exception: {e!s}")

                # Mark our failure
                has_error = True
                continue

        return not has_error

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us
        to re-instantiate this object."""

        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Our URL looks like this:
        #    {schema}://{apikey}:{from_email}/{targets}
        #
        # which actually equates to:
        #    {schema}://{user}:{password}@{host}/{email1}/{email2}/etc
        #                  ^       ^         ^
        #                  |       |         |
        #               apikey    user     domain
        #                              (from email parts)

        # Handle apikey= query param override
        if "apikey" in results["qsd"] and results["qsd"]["apikey"]:
            results["apikey"] = NotifyPostmark.unquote(
                results["qsd"]["apikey"]
            )
        else:
            # Fall back to the user field
            results["apikey"] = NotifyPostmark.unquote(results["user"])

        # Our targets list
        results["targets"] = []

        # Handle from= query param (alternative from address)
        if "from" in results["qsd"] and results["qsd"]["from"]:
            results["from_email"] = NotifyPostmark.unquote(
                results["qsd"]["from"]
            )
            # Treat the host as a target when from= is given explicitly
            if results.get("host"):
                results["targets"].append(
                    NotifyPostmark.unquote(results["host"])
                )

        else:
            # Reconstruct from_email from {password}@{host}
            results["from_email"] = "{}@{}".format(
                NotifyPostmark.unquote(
                    results["password"]
                    if results["password"]
                    else results["user"]
                ),
                NotifyPostmark.unquote(results["host"]),
            )

        # Handle from display name
        if "name" in results["qsd"] and results["qsd"]["name"]:
            results["from_name"] = NotifyPostmark.unquote(
                results["qsd"]["name"]
            )

        # Acquire targets from the URL path
        results["targets"].extend(
            NotifyPostmark.split_path(results["fullpath"])
        )

        # Support ?to= for additional targets
        if "to" in results["qsd"] and results["qsd"]["to"]:
            results["targets"] += NotifyPostmark.parse_list(
                results["qsd"]["to"]
            )

        # Handle Carbon Copy Addresses
        if "cc" in results["qsd"] and results["qsd"]["cc"]:
            results["cc"] = NotifyPostmark.parse_list(results["qsd"]["cc"])

        # Handle Blind Carbon Copy Addresses
        if "bcc" in results["qsd"] and results["qsd"]["bcc"]:
            results["bcc"] = NotifyPostmark.parse_list(results["qsd"]["bcc"])

        # Handle Reply-To Addresses
        if "reply" in results["qsd"] and results["qsd"]["reply"]:
            results["reply_to"] = results["qsd"]["reply"]

        return results
