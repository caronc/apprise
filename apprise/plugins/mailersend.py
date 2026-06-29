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

# MailerSend is a transactional email delivery platform.
#
# To use this plugin you need an API token with at least the Email send
# permission, and a verified sending domain or sender address.
#
# Setup steps:
#  1. Visit https://www.mailersend.com/ and sign in or create an account.
#  2. Go to Settings -> API Tokens and create a token with at least the
#     "Email" send permission.
#  3. Verify at least one sender domain or address in your MailerSend
#     account.  The "From Email" used in Apprise must belong to a verified
#     sending domain.
#  4. Build your Apprise URL using the syntax below.
#
# Apprise URL format:
#   mailersend://APIKey:FromEmail
#   mailersend://APIKey:FromEmail/ToEmail
#   mailersend://APIKey:FromEmail/ToEmail1/ToEmail2/ToEmailN
#
# In the URL:
#   - APIKey    : your MailerSend API token
#   - FromEmail : a verified sender address (local-part@domain)
#   - ToEmail   : one or more recipient addresses in the URL path;
#                 if omitted the FromEmail is used as the recipient
#
# Optional query-string parameters:
#   - ?to=extra@example.com      additional recipients (comma-separated)
#   - ?cc=cc@example.com         Carbon Copy recipients
#   - ?bcc=bcc@example.com       Blind Carbon Copy recipients
#   - ?reply=reply@example.com   Reply-To address
#
# API Reference:
#   https://developers.mailersend.com/api/v1/email.html

from json import dumps
import logging

import requests

from .. import exception
from ..common import NotifyFormat, NotifyType
from ..conversion import convert_between
from ..locale import gettext_lazy as _
from ..utils.parse import is_email, parse_list, validate_regex
from ..utils.sanitize import sanitize_payload
from .base import NotifyBase

# Extend HTTP Error Messages for MailerSend responses
MAILERSEND_HTTP_ERROR_MAP = {
    401: "Unauthorized - Invalid or missing API token.",
    403: "Forbidden - API token lacks send permission.",
    422: "Unprocessable Entity - Validation error in request.",
    429: "Too Many Requests - Rate limit exceeded.",
}


class NotifyMailerSend(NotifyBase):
    """A wrapper for MailerSend Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "MailerSend"

    # The services URL
    service_url = "https://www.mailersend.com/"

    # The default secure protocol
    secure_protocol = "mailersend"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/mailersend/"

    # The MailerSend Email API endpoint
    notify_url = "https://api.mailersend.com/v1/email"

    # Default to HTML notifications
    notify_format = NotifyFormat.HTML

    # Support attachments
    attachment_support = True

    # Allow 300 requests per minute
    # 60/300 = 0.2
    request_rate_per_sec = 0.2

    # The default subject to use if one isn't specified.
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
                "regex": (r"^[a-zA-Z0-9._-]+$", "i"),
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
                "type": "string",
                "map_to": "reply_to",
            },
        },
    )

    def __init__(
        self,
        apikey,
        from_email,
        targets=None,
        reply_to=None,
        cc=None,
        bcc=None,
        **kwargs,
    ):
        """Initialize MailerSend Object."""
        super().__init__(**kwargs)

        # API Key
        self.apikey = validate_regex(
            apikey, *self.template_tokens["apikey"]["regex"]
        )
        if not self.apikey:
            msg = f"An invalid MailerSend API Key ({apikey}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Validate and store the From Email
        result = is_email(from_email)
        if not result:
            msg = f"Invalid MailerSend From email specified: {from_email}"
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store the verified from address
        self.from_email = result["full_email"]

        # Reply-to address
        self.reply_to = None
        if reply_to:
            result = is_email(reply_to)
            if not result:
                msg = (
                    "An invalid MailerSend Reply To"
                    f" ({reply_to}) was specified."
                )
                self.logger.warning(msg)
                raise TypeError(msg)

            self.reply_to = result["full_email"]

        # Acquire Targets (To Emails)
        self.targets = []

        # Acquire Carbon Copies
        self.cc = set()

        # Acquire Blind Carbon Copies
        self.bcc = set()

        # Validate recipients (to:) and drop bad ones
        if targets:
            for recipient in parse_list(targets):
                result = is_email(recipient)
                if result:
                    self.targets.append(result["full_email"])
                    continue

                self.logger.warning(
                    "Dropped invalid MailerSend email (%s) specified.",
                    recipient,
                )

        else:
            # Use the sender as the default recipient
            self.targets.append(self.from_email)

        # Validate recipients (cc:) and drop bad ones
        for recipient in parse_list(cc):
            result = is_email(recipient)
            if result:
                self.cc.add(result["full_email"])
                continue

            self.logger.warning(
                "Dropped invalid MailerSend Carbon Copy email (%s) specified.",
                recipient,
            )

        # Validate recipients (bcc:) and drop bad ones
        for recipient in parse_list(bcc):
            result = is_email(recipient)
            if result:
                self.bcc.add(result["full_email"])
                continue

            self.logger.warning(
                "Dropped invalid MailerSend Blind Carbon"
                " Copy email (%s) specified.",
                recipient,
            )

        return

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another similar one.

        Targets or end points should never be identified here.
        """
        return (self.secure_protocol, self.apikey, self.from_email)

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified
        arguments."""

        # Our URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        if len(self.cc) > 0:
            # Handle our Carbon Copy Addresses
            params["cc"] = ",".join(self.cc)

        if len(self.bcc) > 0:
            # Handle our Blind Carbon Copy Addresses
            params["bcc"] = ",".join(self.bcc)

        if self.reply_to:
            # Handle our Reply-To address
            params["reply"] = self.reply_to

        # A simple boolean check as to whether we display our target
        # emails or not
        has_targets = not (
            len(self.targets) == 1 and self.targets[0] == self.from_email
        )

        return "{schema}://{apikey}:{from_email}/{targets}?{params}".format(
            schema=self.secure_protocol,
            apikey=self.pprint(self.apikey, privacy, safe=""),
            # Never encode email since it plays a huge role in our
            # hostname
            from_email=self.from_email,
            targets=(
                ""
                if not has_targets
                else "/".join(
                    [NotifyMailerSend.quote(x, safe="@") for x in self.targets]
                )
            ),
            params=NotifyMailerSend.urlencode(params),
        )

    def __len__(self):
        """Returns the number of targets associated with this
        notification."""
        return max(len(self.targets), 1)

    def send(
        self,
        body,
        title="",
        notify_type=NotifyType.INFO,
        attach=None,
        **kwargs,
    ):
        """Perform MailerSend Notification."""

        if not self.targets:
            # Nothing to send to
            self.logger.warning(
                "There are no MailerSend email recipients to notify"
            )
            return False

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": "Bearer {}".format(self.apikey),
        }

        # Determine whether the body is HTML or plain text
        use_html = self.notify_format == NotifyFormat.HTML

        # Build a base payload template reused per recipient
        payload_ = {
            "from": {
                "email": self.from_email,
            },
            # Placeholder; filled per target below
            "to": [{"email": None}],
            "subject": title if title else self.default_empty_subject,
        }

        # Assign body fields; provide both html and text
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
            # Prepare our attachment list
            attachments = []

            for no, attachment in enumerate(attach, start=1):
                # Perform some simple error checking
                if not attachment:
                    # We could not access the attachment
                    self.logger.error(
                        "Could not access MailerSend attachment %s.",
                        attachment.url(privacy=True),
                    )
                    return False

                try:
                    attachments.append(
                        {
                            "content": attachment.base64(),
                            "filename": (
                                attachment.name
                                if attachment.name
                                else "file{:03}.dat".format(no)
                            ),
                            "disposition": "attachment",
                        }
                    )

                except exception.AppriseException:
                    # We could not access the attachment
                    self.logger.error(
                        "Could not access MailerSend attachment %s.",
                        attachment.url(privacy=True),
                    )
                    return False

                self.logger.debug(
                    "Appending MailerSend attachment %s.",
                    attachment.url(privacy=True),
                )

            # Append attachments to the base payload template
            payload_.update({"attachments": attachments})

        if self.reply_to:
            # Set the Reply-To address
            payload_["reply_to"] = {"email": self.reply_to}

        # Track overall success
        has_error = False

        targets = list(self.targets)
        while len(targets) > 0:
            target = targets.pop(0)

            # Build a fresh copy of the payload for this recipient
            payload = payload_.copy()

            # The cc and bcc lists must not contain the target address
            cc = self.cc - self.bcc - {target}
            bcc = self.bcc - {target}

            # Set our main recipient
            payload["to"] = [{"email": target}]

            if cc:
                payload["cc"] = [{"email": e} for e in cc]

            if bcc:
                payload["bcc"] = [{"email": e} for e in bcc]

            # Some Debug Logging
            if self.logger.isEnabledFor(logging.DEBUG):
                # Due to attachments, output can be quite heavy and
                # I/O intensive; only emit debug payload if required
                self.logger.debug(
                    "MailerSend POST URL: %s (cert_verify=%r)",
                    self.notify_url,
                    self.verify_certificate,
                )
                self.logger.debug(
                    "MailerSend Payload: %s",
                    sanitize_payload(payload),
                )

            # Always call throttle before any remote server I/O
            self.throttle()
            try:
                r = requests.post(
                    self.notify_url,
                    data=dumps(payload),
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                    allow_redirects=self.redirects,
                )
                if r.status_code not in (
                    requests.codes.ok,
                    requests.codes.accepted,
                ):
                    # We had a failure
                    status_str = NotifyMailerSend.http_response_code_lookup(
                        r.status_code,
                        MAILERSEND_HTTP_ERROR_MAP,
                    )

                    self.logger.warning(
                        "Failed to send MailerSend"
                        " notification to %s:"
                        " %s%serror=%s.",
                        target,
                        status_str,
                        ", " if status_str else "",
                        r.status_code,
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
                        "Sent MailerSend notification to %s.",
                        target,
                    )

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending"
                    " MailerSend notification to %s.",
                    target,
                )
                self.logger.debug("Socket Exception: %s", str(e))

                # Mark our failure
                has_error = True
                continue

        return not has_error

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow
        us to re-instantiate this object."""

        results = NotifyBase.parse_url(url)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Our URL looks like this:
        #    {schema}://{apikey}:{from_email}/{targets}
        #
        # which equates to:
        #    {schema}://{user}:{password}@{host}/{email1}/{email2}/...
        #                 ^       ^         ^
        #                 |       |         |
        #              apikey     +---from email---+

        if not results.get("user"):
            # An API Key was not properly specified
            return None

        if not results.get("password"):
            # A From Email was not properly specified
            return None

        # Prepare our API Key
        results["apikey"] = NotifyMailerSend.unquote(results["user"])

        # Reconstruct the From Email from password and host
        results["from_email"] = "{}@{}".format(
            NotifyMailerSend.unquote(results["password"]),
            NotifyMailerSend.unquote(results["host"]),
        )

        # Acquire targets from the URL path
        results["targets"] = NotifyMailerSend.split_path(results["fullpath"])

        # Support ?to= for additional targets
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifyMailerSend.parse_list(
                results["qsd"]["to"]
            )

        # Handle Carbon Copy Addresses
        if "cc" in results["qsd"] and len(results["qsd"]["cc"]):
            results["cc"] = NotifyMailerSend.parse_list(results["qsd"]["cc"])

        # Handle Blind Carbon Copy Addresses
        if "bcc" in results["qsd"] and len(results["qsd"]["bcc"]):
            results["bcc"] = NotifyMailerSend.parse_list(results["qsd"]["bcc"])

        # Handle Reply-To Address
        if "reply" in results["qsd"] and len(results["qsd"]["reply"]):
            results["reply_to"] = NotifyMailerSend.unquote(
                results["qsd"]["reply"]
            )

        return results
