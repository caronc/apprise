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

# Groundmail is a transactional email API.
#
# To use this plugin you need a Groundmail API key.
#
# Setup steps:
#  1. Visit https://groundmail.dev/ and sign in or create an account.
#  2. Go to API Keys and create a key with the "Send emails" permission.
#     Keys start with gm_.
#  3. Verify a sending domain.  The "From Email" used in Apprise must
#     belong to a verified domain.
#
#     Before you verify a domain you can send from the shared sender
#     noreply@mail.groundmail.dev, but only to the email address on your
#     Groundmail account.
#  4. Build your Apprise URL using the syntax below.
#
# Apprise URL format:
#   groundmail://APIKey:FromEmail
#   groundmail://APIKey:FromEmail/ToEmail
#   groundmail://APIKey:FromEmail/ToEmail1/ToEmail2/ToEmailN
#
# In the URL:
#   - APIKey    : your Groundmail API key (gm_...)
#   - FromEmail : a sender address on a verified domain (local-part@domain)
#   - ToEmail   : one or more recipient addresses in the URL path;
#                 if omitted the FromEmail is used as the recipient
#
# Optional query-string parameters:
#   - ?name=Apprise              the sender's display name
#   - ?to=extra@example.com      additional recipients (comma-separated)
#   - ?cc=cc@example.com         Carbon Copy recipients
#   - ?bcc=bcc@example.com       Blind Carbon Copy recipients
#   - ?reply=reply@example.com   Reply-To address(es)
#
# API Reference:
#   https://docs.groundmail.dev/emails

from email.utils import formataddr
from json import dumps
import logging
from uuid import uuid4

import requests

from .. import exception
from ..common import NotifyFormat, NotifyType
from ..conversion import convert_between
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..utils.parse import is_email, parse_emails, validate_regex
from ..utils.sanitize import sanitize_payload
from .base import NotifyBase

GROUNDMAIL_HTTP_ERROR_MAP = {
    400: "Check that the parameters were correct.",
    401: "The API key used was missing or invalid.",
    403: (
        "The From address is not on a verified domain, or the recipient "
        "is not permitted for this sender."
    ),
    404: "The resource was not found.",
    409: "The request is already being processed.",
    422: "The recipient is suppressed or was rejected.",
    429: "The rate or sending limit was exceeded.",
    502: "The email could not be handed off for delivery.",
    503: "Email delivery is temporarily unavailable.",
}


class NotifyGroundmail(NotifyBase):
    """A wrapper for Groundmail Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Groundmail"

    # The services URL
    service_url = "https://groundmail.dev"

    # The default secure protocol
    secure_protocol = "groundmail"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/groundmail/"

    # The Groundmail Email API endpoint
    notify_url = "https://api.groundmail.dev/emails"

    # Groundmail accepts both an HTML and a plain text body. HTML remains
    # the default.
    notify_format = (NotifyFormat.HTML, NotifyFormat.TEXT)

    # Support attachments
    attachment_support = True

    # Free accounts may send 60 emails per minute.
    # 60/60 = 1.0
    request_rate_per_sec = 1.0

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
                "type": "email",
                "required": True,
            },
            "target_email": {
                "name": _("Target Email"),
                "type": "email",
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
            "from": {
                "name": _("From Address"),
                "type": "string",
                "map_to": "from_addr",
            },
            "name": {
                "name": _("From Name"),
                "type": "string",
                "map_to": "from_addr",
            },
            "apikey": {
                "name": _("API Key"),
                "type": "string",
                "map_to": "apikey",
            },
            "reply": {
                "name": _("Reply To"),
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
        from_addr,
        targets=None,
        cc=None,
        bcc=None,
        reply_to=None,
        **kwargs,
    ):
        """Initialize Notify Groundmail Object."""
        super().__init__(**kwargs)

        # API Key
        self.apikey = validate_regex(
            apikey, *self.template_tokens["apikey"]["regex"]
        )
        if not self.apikey:
            msg = f"An invalid Groundmail API Key ({apikey}) was specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

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
            msg = f"Invalid ~From~ email specified: {from_addr}"
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

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
                f"Dropped invalid Reply To email ({recipient}) specified.",
            )

        return

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another similar one.

        Targets or end points should never be identified here.
        """
        return (self.secure_protocol, self.apikey, self.from_addr)

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Our URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        if self.cc:
            # Handle our Carbon Copy Addresses
            params["cc"] = ",".join(
                [
                    formataddr(
                        (self.names.get(e, False), e),
                        # Swap comma for its escaped url code (if
                        # detected) since we use it as a delimiter
                        charset="utf-8",
                    ).replace(",", "%2C")
                    for e in self.cc
                ]
            )

        if len(self.bcc) > 0:
            # Handle our Blind Carbon Copy Addresses
            params["bcc"] = ",".join(self.bcc)

        if self.reply_to:
            # Handle our Reply-To Addresses
            params["reply"] = ",".join(
                [
                    formataddr(
                        (self.names.get(e, False), e),
                        # Swap comma for its escaped url code (if
                        # detected) since we use it as a delimiter
                        charset="utf-8",
                    ).replace(",", "%2C")
                    for e in self.reply_to
                ]
            )

        # a simple boolean check as to whether we display our target emails
        # or not
        has_targets = not (
            len(self.targets) == 1 and self.targets[0] == self.from_addr[1]
        )

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
                    [NotifyGroundmail.quote(x, safe="@") for x in self.targets]
                )
            ),
            params=NotifyGroundmail.urlencode(params),
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
        body_format=None,
        **kwargs,
    ):
        """Perform Groundmail Notification."""

        if not self.targets:
            # Nothing to send to
            self.logger.warning(
                "There are no Groundmail email recipients to notify"
            )
            return False

        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.apikey}",
        }

        # error tracking (used for function return)
        has_error = False

        # Resolve the requested delivery representation for this send.
        # Groundmail accepts both html and text fields, so the resolved
        # format decides which field receives the original body.
        use_html = self.resolve_format(body_format) == NotifyFormat.HTML

        payload_ = {
            "from": formataddr(self.from_addr, charset="utf-8"),
            # A subject is a requirement, so if none is specified we must
            # set a default with at least 1 character or Groundmail will
            # deny our request
            "subject": title if title else self.default_empty_subject,
        }

        # Assign both body fields so the email has an HTML part and a
        # plain-text alternative regardless of the selected source.
        if use_html:
            payload_["html"] = body
            payload_["text"] = convert_between(
                NotifyFormat.HTML, NotifyFormat.TEXT, body
            )

        else:
            payload_["text"] = body
            payload_["html"] = convert_between(
                NotifyFormat.TEXT, NotifyFormat.HTML, body
            )

        if attach and self.attachment_support:
            attachments = []

            # Send our attachments
            for no, attachment in enumerate(attach, start=1):
                # Perform some simple error checking
                if not attachment:
                    # We could not access the attachment
                    self.logger.error(
                        "Could not access Groundmail attachment"
                        f" {attachment.url(privacy=True)}."
                    )
                    return False

                try:
                    attachments.append(
                        {
                            "name": (
                                attachment.name
                                if attachment.name
                                else f"file{no:03}.dat"
                            ),
                            "content_type": attachment.mimetype,
                            "data": attachment.base64(),
                        }
                    )

                except exception.AppriseException:
                    # We could not access the attachment
                    self.logger.error(
                        "Could not access Groundmail attachment"
                        f" {attachment.url(privacy=True)}."
                    )
                    return False

                self.logger.debug(
                    "Appending Groundmail attachment"
                    f" {attachment.url(privacy=True)}"
                )

            # Append our attachments to the payload
            payload_.update(
                {
                    "attachments": attachments,
                }
            )

        targets = list(self.targets)
        while len(targets) > 0:
            target = targets.pop(0)

            # Skip a target that already accepted this message so
            # a retry does not deliver it twice.
            if self.is_delivered(target):
                continue

            # Create a copy of our template
            payload = payload_.copy()

            # unique cc/bcc list management
            cc = self.cc - self.bcc - {target}
            bcc = self.bcc - {target}

            # handle our reply to
            reply_to = self.reply_to - {target}

            # Format our cc addresses to support the Name field
            cc = [
                formataddr(
                    (self.names.get(addr, False), addr), charset="utf-8"
                )
                for addr in cc
            ]

            # Format our reply-to addresses to support the Name field
            reply_to = [
                formataddr(
                    (self.names.get(addr, False), addr), charset="utf-8"
                )
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

            # Groundmail honours an Idempotency-Key header.  The key is
            # kept across retries of this notification, so if a response
            # is lost after the email was accepted, the retry does not
            # send it a second time.
            idempotency_key = self.recall(f"idempotency:{target}")
            if idempotency_key is None:
                idempotency_key = str(uuid4())
                self.remember(f"idempotency:{target}", idempotency_key)

            target_headers = headers.copy()
            target_headers["Idempotency-Key"] = idempotency_key

            # Some Debug Logging
            if self.logger.isEnabledFor(logging.DEBUG):
                # Due to attachments; output can be quite heavy and io
                # intensive.
                # To accommodate this, we only show our debug payload
                # information if required.
                self.logger.debug(
                    "Groundmail POST URL:"
                    f" {self.notify_url} "
                    f"(cert_verify={self.verify_certificate!r})"
                )
                self.logger.debug(
                    "Groundmail Payload: %s", sanitize_payload(payload)
                )

            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.post(
                    self.notify_url,
                    data=dumps(payload),
                    headers=target_headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                    allow_redirects=self.redirects,
                )
                if r.status_code not in (
                    requests.codes.ok,
                    requests.codes.created,
                    requests.codes.accepted,
                ):
                    # We had a problem
                    status_str = NotifyGroundmail.http_response_code_lookup(
                        r.status_code, GROUNDMAIL_HTTP_ERROR_MAP
                    )

                    self.logger.warning(
                        "Failed to send Groundmail notification to {}: "
                        "{}{}error={}.".format(
                            target,
                            status_str,
                            ", " if status_str else "",
                            r.status_code,
                        )
                    )

                    self.logger.debug(
                        "Response Details:\r\n%r", (r.content or b"")[:2000]
                    )

                    # Mark our failure
                    has_error = True
                    continue

                else:
                    self.logger.info(
                        f"Sent Groundmail notification to {target}."
                    )

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending Groundmail "
                    f"notification to {target}."
                )
                self.logger.debug(f"Socket Exception: {e!s}")

                # Mark our failure
                has_error = True
                continue

            # Delivered; a retry can safely skip this target.
            self.mark_delivered(target)

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
            results["apikey"] = NotifyGroundmail.unquote(
                results["qsd"]["apikey"]
            )

        else:
            results["apikey"] = NotifyGroundmail.unquote(results["user"])

        # Our Targets
        results["targets"] = []

        # Attempt to detect 'from' email address
        if "from" in results["qsd"] and len(results["qsd"]["from"]):
            results["from_addr"] = NotifyGroundmail.unquote(
                results["qsd"]["from"]
            )

            if results.get("host"):
                results["targets"].append(
                    NotifyGroundmail.unquote(results["host"])
                )

        else:
            # Prepare our From Email Address
            results["from_addr"] = "{}@{}".format(
                NotifyGroundmail.unquote(
                    results["password"]
                    if results["password"]
                    else results["user"]
                ),
                NotifyGroundmail.unquote(results["host"]),
            )

        if "name" in results["qsd"] and len(results["qsd"]["name"]):
            results["from_addr"] = formataddr(
                (
                    NotifyGroundmail.unquote(results["qsd"]["name"]),
                    results["from_addr"],
                ),
                charset="utf-8",
            )

        # Acquire our targets
        results["targets"].extend(
            NotifyGroundmail.split_path(results["fullpath"])
        )

        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifyGroundmail.parse_list(
                results["qsd"]["to"]
            )

        # Handle Carbon Copy Addresses
        if "cc" in results["qsd"] and len(results["qsd"]["cc"]):
            results["cc"] = NotifyGroundmail.parse_list(results["qsd"]["cc"])

        # Handle Blind Carbon Copy Addresses
        if "bcc" in results["qsd"] and len(results["qsd"]["bcc"]):
            results["bcc"] = NotifyGroundmail.parse_list(results["qsd"]["bcc"])

        # Handle Reply To Addresses
        if "reply" in results["qsd"] and len(results["qsd"]["reply"]):
            results["reply_to"] = results["qsd"]["reply"]

        return results
