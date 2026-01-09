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

# API Reference: https://developers.brevo.com/reference/getting-started-1

from json import dumps
import logging
from os.path import splitext

import requests

from .. import exception
from ..common import NotifyFormat, NotifyType
from ..conversion import convert_between
from ..locale import gettext_lazy as _
from ..utils.parse import is_email, parse_list, validate_regex
from ..utils.sanitize import sanitize_payload
from .base import NotifyBase

# Extend HTTP Error Messages (most common Brevo SMTP errors)
BREVO_HTTP_ERROR_MAP = {
    400: "Bad Request - Invalid payload or missing parameters.",
    401: "Unauthorized - Invalid Brevo API key.",
    402: "Payment Required - Plan limitation or credit issue.",
    429: "Too Many Requests - Rate limit exceeded.",
}

# Comprehensive list of Brevo-supported extensions for Transactional Emails
# Source: Brevo API Documentation & Transactional Attachment Guidelines
BREVO_VALID_EXTENSIONS = (
    # Documents & Text
    "xlsx", "xls", "ods", "docx", "docm", "doc", "csv", "pdf", "txt",
    "rtf", "msg", "pub", "mobi", "ppt", "pptx", "eps", "odt", "ics",
    "xml", "css", "html", "htm", "shtml",
    # Images
    "gif", "jpg", "jpeg", "png", "tif", "tiff", "bmp", "cgm",
    # Archives
    "zip", "tar", "ez", "pkpass",
    # Audio
    "mp3", "m4a", "m4v", "wma", "ogg", "flac", "wav", "aif", "aifc", "aiff",
    # Video
    "mp4", "mov", "avi", "mkv", "mpeg", "mpg", "wmv"
)


class NotifyBrevo(NotifyBase):
    """A wrapper for Notify Brevo Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Brevo"

    # The services URL
    service_url = "https://www.brevo.com/"

    # The default secure protocol
    secure_protocol = "brevo"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/brevo/"

    # Default to markdown
    notify_format = NotifyFormat.HTML

    # The default Email API URL to use
    notify_url = "https://api.brevo.com/v3/smtp/email"

    # Support attachments
    attachment_support = True

    # Allow 300 requests per minute.
    # 60/300 = 0.2
    request_rate_per_sec = 0.2

    # The default subject to use if one isn't specified.
    default_empty_subject = "<no subject>"

    # Define object templates
    templates = (
        "{schema}://{apikey}:{from_email}",
        "{schema}://{apikey}:{from_email}/{targets}",
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
                "name": _("Reply To Email"),
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
        """Initialize Notify Brevo Object."""
        super().__init__(**kwargs)

        # API Key (associated with project)
        self.apikey = validate_regex(
            apikey, *self.template_tokens["apikey"]["regex"]
        )
        if not self.apikey:
            msg = f"An invalid Brevo API Key ({apikey}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        result = is_email(from_email)
        if not result:
            msg = f"Invalid ~From~ email specified: {from_email}"
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store email address
        self.from_email = result["full_email"]

        # Reply-to
        self.reply_to = None
        if reply_to:
            result = is_email(reply_to)
            if not result:
                msg = "An invalid Brevo Reply To ({}) was specified.".format(
                    f"{reply_to}")
                self.logger.warning(msg)
                raise TypeError(msg)

            self.reply_to = (
                    result["name"] if result["name"] else False,
                    result["full_email"],
                )

        # Acquire Targets (To Emails)
        self.targets = []

        # Acquire Carbon Copies
        self.cc = set()

        # Acquire Blind Carbon Copies
        self.bcc = set()

        # Validate recipients (to:) and drop bad ones:
        if targets:
            for recipient in parse_list(targets):

                result = is_email(recipient)
                if result:
                    self.targets.append(result["full_email"])
                    continue

                self.logger.warning(
                    f"Dropped invalid email ({recipient}) specified.",
                )
        else:
            # add ourselves
            self.targets.append(self.from_email)

        # Validate recipients (cc:) and drop bad ones:
        for recipient in parse_list(cc):

            result = is_email(recipient)
            if result:
                self.cc.add(result["full_email"])
                continue

            self.logger.warning(
                f"Dropped invalid Carbon Copy email ({recipient}) specified.",
            )

        # Validate recipients (bcc:) and drop bad ones:
        for recipient in parse_list(bcc):

            result = is_email(recipient)
            if result:
                self.bcc.add(result["full_email"])
                continue

            self.logger.warning(
                "Dropped invalid Blind Carbon Copy email "
                f"({recipient}) specified.",
            )

        return

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (self.secure_protocol, self.apikey, self.from_email)

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Our URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        if len(self.cc) > 0:
            # Handle our Carbon Copy Addresses
            params["cc"] = ",".join(self.cc)

        if len(self.bcc) > 0:
            # Handle our Blind Carbon Copy Addresses
            params["bcc"] = ",".join(self.bcc)

        if self.reply_to:
            # Handle our reply to address
            params["reply"] = (
                "{} <{}>".format(*self.reply_to)
                if self.reply_to[0]
                else self.reply_to[1]
            )

        # a simple boolean check as to whether we display our target emails
        # or not
        has_targets = not (
            len(self.targets) == 1 and self.targets[0] == self.from_email
        )

        return "{schema}://{apikey}:{from_email}/{targets}?{params}".format(
            schema=self.secure_protocol,
            apikey=self.pprint(self.apikey, privacy, safe=""),
            # never encode email since it plays a huge role in our hostname
            from_email=self.from_email,
            targets=(
                ""
                if not has_targets
                else "/".join(
                    [NotifyBrevo.quote(x, safe="") for x in self.targets]
                )
            ),
            params=NotifyBrevo.urlencode(params),
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
        """Perform Brevo Notification."""

        if not self.targets:
            # There is no one to email; we're done
            self.logger.warning(
                "There are no Brevo email recipients to notify")
            return False

        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "api-key": self.apikey,
        }

        # error tracking (used for function return)
        has_error = False

        # A Simple Email Payload Template
        _payload = {
            "sender": {
                "email": self.from_email,
            },
            # Placeholder, filled per target
            "to": [{"email": None}],
            "subject": title if title else self.default_empty_subject,
        }
        # Body selection
        use_html = self.notify_format == NotifyFormat.HTML

        if use_html:
            # body already normalised; keep your existing logic
            _payload["htmlContent"] = body
            _payload["textContent"] = convert_between(
                NotifyFormat.HTML, NotifyFormat.TEXT, body
            )
        else:
            # Plain text requested, but Brevo still wants HTML
            _payload["textContent"] = body
            _payload["htmlContent"] = convert_between(
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
                        "Could not access Brevo attachment"
                        f" {attachment.url(privacy=True)}."
                    )
                    return False

                # Brevo does not track content/mime type and relies 100%
                # entirely on the filename extension as to whether or not it
                # will accept it or not.
                #
                # The below prepares a safe_name (which can't be .dat like
                # other plugins since Brevo rejects that type). For this
                # reason .txt is chosen intentionally for this circumstance.

                # Use the attachment name if available, otherwise default to a
                # generic name
                raw_name = attachment.name \
                    if attachment.name else f"file{no:03}.txt"

                # If the filename does NOT match a supported extension, append
                # .txt
                _, ext = splitext(raw_name)
                safe_name = f"{raw_name}.txt" if (
                    not ext or ext[1:].lower()
                    not in BREVO_VALID_EXTENSIONS) else raw_name

                try:
                    attachments.append({
                        "content": attachment.base64(),
                        "name": safe_name,
                    })

                except exception.AppriseException:
                    # We could not access the attachment
                    self.logger.error(
                        "Could not access Brevo attachment"
                        f" {attachment.url(privacy=True)}."
                    )
                    return False

                self.logger.debug(
                    "Appending Brevo attachment"
                    f" {attachment.url(privacy=True)}"
                )

            # Append our attachments to the payload
            _payload.update({
                "attachment": attachments,
            })

        if self.reply_to:
            _payload["replyTo"] = {"email": self.reply_to[1]}

        targets = list(self.targets)
        while len(targets) > 0:
            target = targets.pop(0)

            # Create a copy of our template
            payload = _payload.copy()

            # the cc, bcc, to field must be unique or SendMail will fail, the
            # below code prepares this by ensuring the target isn't in the cc
            # list or bcc list. It also makes sure the cc list does not contain
            # any of the bcc entries
            cc = self.cc - self.bcc - {target}
            bcc = self.bcc - {target}

            # Set our main recipient
            payload["to"] = [{"email": target}]

            if len(cc):
                payload["cc"] = [{"email": email} for email in cc]

            if len(bcc):
                payload["bcc"] = [{"email": email} for email in bcc]

            # Some Debug Logging
            if self.logger.isEnabledFor(logging.DEBUG):
                # Due to attachments; output can be quite heavy and io
                # intensive.
                # To accommodate this, we only show our debug payload
                # information if required.
                self.logger.debug(
                    "Brevo POST URL:"
                    f" {self.notify_url} "
                    f"(cert_verify={self.verify_certificate!r})"
                )
                self.logger.debug(
                    "Brevo Payload: %s", sanitize_payload(payload))

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
                    requests.codes.created,
                ):
                    # We had a problem
                    status_str = NotifyBrevo.http_response_code_lookup(
                        r.status_code, BREVO_HTTP_ERROR_MAP
                    )

                    self.logger.warning(
                        "Failed to send Brevo notification to {}: "
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
                    self.logger.info(
                        f"Sent Brevo notification to {target}."
                    )

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending Brevo "
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

        results = NotifyBase.parse_url(url)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Our URL looks like this:
        #    {schema}://{apikey}:{from_email}/{targets}
        #
        # which actually equates to:
        #    {schema}://{user}:{password}@{host}/{email1}/{email2}/etc..
        #                 ^       ^         ^
        #                 |       |         |
        #              apikey     -from addr-

        if not results.get("user"):
            # An API Key as not properly specified
            return None

        if not results.get("password"):
            # A From Email was not correctly specified
            return None

        # Prepare our API Key
        results["apikey"] = NotifyBrevo.unquote(results["user"])

        # Prepare our From Email Address
        results["from_email"] = "{}@{}".format(
            NotifyBrevo.unquote(results["password"]),
            NotifyBrevo.unquote(results["host"]),
        )

        # Acquire our targets
        results["targets"] = NotifyBrevo.split_path(results["fullpath"])

        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifyBrevo.parse_list(
                results["qsd"]["to"]
            )

        # Handle Carbon Copy Addresses
        if "cc" in results["qsd"] and len(results["qsd"]["cc"]):
            results["cc"] = NotifyBrevo.parse_list(results["qsd"]["cc"])

        # Handle Blind Carbon Copy Addresses
        if "bcc" in results["qsd"] and len(results["qsd"]["bcc"]):
            results["bcc"] = NotifyBrevo.parse_list(results["qsd"]["bcc"])

        # Handle Reply To Address
        if "reply" in results["qsd"] and len(results["qsd"]["reply"]):
            results["reply_to"] = NotifyBrevo.unquote(results["qsd"]["reply"])

        return results
