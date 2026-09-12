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

from datetime import datetime
from email.header import Header
from email.mime.application import MIMEApplication
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import format_datetime, formataddr, make_msgid
import re
import smtplib
from typing import Optional

from ...common import NotifyFormat, NotifyType, PersistentStoreMode
from ...conversion import convert_between
from ...exception import AppriseImproperlyConfigured
from ...locale import gettext_lazy as _
from ...logger import logger
from ...url import PrivacyMode
from ...utils import pgp as _pgp, wkd as _wkd
from ...utils.parse import (
    is_email,
    is_hostname,
    is_ipaddr,
    parse_bool,
    parse_emails,
)
from ..base import NotifyBase
from . import templates
from .common import (
    SECURE_MODES,
    AppriseEmailException,
    EmailMessage,
    SecureMailMode,
    WebBaseLogin,
)
from .smtp import AppriseSMTPController


class PGPMode:
    """PGP security mode for outbound email."""

    # No PGP applied (default)
    NONE = "no"

    # Sign using the sender's private key; encrypt opportunistically when
    # a recipient public key is available (via WKD or pgppub=)
    SIGN = "sign"

    # Encrypt using the recipient's public key (fails if no key found)
    ENCRYPT = "encrypt"


# Ordered tuple of all valid PGP modes; prefix matching uses this order
PGP_MODES = (
    PGPMode.NONE,
    PGPMode.SIGN,
    PGPMode.ENCRYPT,
)

# The mode used when ?pgp= is absent or empty
PGP_MODE_DEFAULT = PGPMode.NONE


class NotifyEmail(NotifyBase):
    """
    A wrapper to Email Notifications

    """

    # The default descriptive name associated with the Notification
    service_name = "E-Mail"

    # The default simple (insecure) protocol
    protocol = "mailto"

    # The default secure protocol
    secure_protocol = "mailtos"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/email/"

    # Support attachments
    attachment_support = True

    # Our default is to no not use persistent storage beyond in-memory
    # reference; this allows us to auto-generate our config if needed
    storage_mode = PersistentStoreMode.AUTO

    # Email can send either HTML or plain text. HTML remains the default.
    notify_format = (NotifyFormat.HTML, NotifyFormat.TEXT)

    # Default SMTP Timeout (in seconds)
    socket_connect_timeout = 15

    # Define object templates
    templates = (
        "{schema}://{host}",
        "{schema}://{host}:{port}",
        "{schema}://{host}:{port}/{targets}",
        "{schema}://{host}/{targets}",
        "{schema}://{user}@{host}",
        "{schema}://{user}@{host}/{targets}",
        "{schema}://{user}@{host}:{port}",
        "{schema}://{user}@{host}/{targets}",
        "{schema}://{user}@{host}:{port}/{targets}",
        "{schema}://{user}:{password}@{host}",
        "{schema}://{user}:{password}@{host}/{targets}",
        "{schema}://{user}:{password}@{host}:{port}",
        "{schema}://{user}:{password}@{host}:{port}/{targets}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "user": {
                "name": _("User Name"),
                "type": "string",
            },
            "password": {
                "name": _("Password"),
                "type": "string",
                "private": True,
            },
            "host": {
                "name": _("Domain"),
                "type": "string",
                "required": True,
            },
            "port": {
                "name": _("Port"),
                "type": "int",
                "min": 1,
                "max": 65535,
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

    template_args = dict(
        NotifyBase.template_args,
        **{
            "from": {
                "name": _("From Email"),
                "type": "string",
                "map_to": "from_addr",
            },
            "name": {
                "name": _("From Name"),
                "type": "string",
                "map_to": "from_addr",
            },
            "smtp": {
                "name": _("SMTP Server"),
                "type": "string",
                "map_to": "smtp_host",
            },
            "mode": {
                "name": _("Secure Mode"),
                "type": "choice:string",
                "values": SECURE_MODES,
                "default": SecureMailMode.STARTTLS,
                "map_to": "secure_mode",
            },
            "reply": {
                "name": _("Reply To"),
                "type": "list:string",
                "map_to": "reply_to",
            },
            "pgp": {
                "name": _("PGP Security Mode"),
                "type": "choice:string",
                "values": PGP_MODES,
                "default": PGP_MODE_DEFAULT,
                "map_to": "pgp_mode",
            },
            "pgppub": {
                "name": _("PGP Public Key Path"),
                "type": "string",
                "private": True,
                # By default persistent storage is referenced
                "default": "",
                "map_to": "pgp_key",
            },
            "pgpprv": {
                "name": _("PGP Private Key Path"),
                "type": "string",
                "private": True,
                # By default persistent storage is referenced
                "default": "",
                "map_to": "pgp_privkey",
            },
            "wkd": {
                "name": _("Web Key Directory"),
                "type": "bool",
                "default": False,
                "map_to": "use_wkd",
            },
            "inline": {
                "name": _("Inline Attachments"),
                "type": "bool",
                "default": False,
            },
            "to": {
                "name": _("To Email"),
                "type": "string",
                "map_to": "targets",
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

    # Define any kwargs we're using
    template_kwargs = {
        "headers": {
            "name": _("Email Header"),
            "prefix": "+",
        },
    }

    def __init__(
        self,
        smtp_host=None,
        from_addr=None,
        secure_mode=None,
        targets=None,
        cc=None,
        bcc=None,
        reply_to=None,
        headers=None,
        pgp_mode=None,
        pgp_key=None,
        pgp_privkey=None,
        use_wkd=False,
        inline=None,
        **kwargs,
    ):
        """
        Initialize Email Object

        The smtp_host and secure_mode can be automatically detected depending
        on how the URL was built
        """
        super().__init__(**kwargs)

        # Acquire Email 'To'
        self.targets = []

        # Acquire Carbon Copies
        self.cc = set()

        # Acquire Blind Carbon Copies
        self.bcc = set()

        # Acquire Reply To
        self.reply_to = set()

        # For tracking our email -> name lookups
        self.names = {}

        self.headers = {}
        if headers:
            # Store our extra headers
            self.headers.update(headers)

        # Now we want to construct the To and From email
        # addresses from the URL provided
        self.from_addr = [False, ""]

        # Now detect the SMTP Server
        self.smtp_host = smtp_host if isinstance(smtp_host, str) else ""

        # Now detect secure mode
        if secure_mode:
            self.secure_mode = (
                None
                if not isinstance(secure_mode, str)
                else secure_mode.lower()
            )
        else:
            self.secure_mode = (
                SecureMailMode.INSECURE
                if not self.secure
                else self.template_args["mode"]["default"]
            )

        if self.secure_mode not in SECURE_MODES:
            msg = "The secure mode specified ({}) is invalid.".format(
                secure_mode
            )
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

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
                "Dropped invalid Carbon Copy email ({}) specified.".format(
                    recipient
                ),
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
                "({}) specified.".format(recipient),
            )

        # Validate recipients (reply-to:) and drop bad ones:
        for recipient in parse_emails(reply_to):
            email = is_email(recipient)
            if email:
                self.reply_to.add(email["full_email"])

                # Index our name (if one exists)
                self.names[email["full_email"]] = (
                    email["name"] if email["name"] else False
                )
                continue

            self.logger.warning(
                "Dropped invalid Reply To email ({}) specified.".format(
                    recipient
                ),
            )

        # Apply any defaults based on certain known configurations
        self.apply_email_defaults(secure_mode=secure_mode, **kwargs)

        if self.user:
            if self.host:
                # Prepare the bases of our email
                self.from_addr = [
                    self.app_id,
                    "{}@{}".format(
                        re.split(r"[\s@]+", self.user)[0],
                        self.host,
                    ),
                ]

            else:
                result = is_email(self.user)
                if result:
                    # Prepare the bases of our email and include domain
                    self.host = result["domain"]
                    self.from_addr = [self.app_id, self.user]

        if from_addr:
            result = is_email(from_addr)
            if result:
                self.from_addr = (
                    result["name"] if result["name"] else False,
                    result["full_email"],
                )
            else:
                # Only update the string but use the already detected info
                self.from_addr[0] = from_addr

        result = is_email(self.from_addr[1])
        if not result:
            # Parse Source domain based on from_addr
            msg = "Invalid ~From~ email specified: {}".format(
                "{} <{}>".format(self.from_addr[0], self.from_addr[1])
                if self.from_addr[0]
                else "{}".format(self.from_addr[1])
            )
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Store our lookup
        self.names[self.from_addr[1]] = self.from_addr[0]

        if targets:
            # Validate recipients (to:) and drop bad ones:
            for recipient in parse_emails(targets):
                result = is_email(recipient)
                if result:
                    self.targets.append(
                        (
                            result["name"] if result["name"] else False,
                            result["full_email"],
                        )
                    )
                    continue

                self.logger.warning(
                    "Dropped invalid To email ({}) specified.".format(
                        recipient
                    ),
                )

        else:
            # If our target email list is empty we want to add ourselves to it
            self.targets.append((False, self.from_addr[1]))

        if not self.secure and self.secure_mode != SecureMailMode.INSECURE:
            # Enable Secure mode if not otherwise set
            self.secure = True

        if not self.port:
            # Assign our port based on our secure_mode if not otherwise
            # detected
            self.port = SECURE_MODES[self.secure_mode]["default_port"]

        # if there is still no smtp_host then we fall back to the hostname
        if not self.smtp_host:
            self.smtp_host = self.host

        # Track whether pgp_mode was explicitly provided so wkd= implication
        # does not override a deliberate pgp=none choice
        pgp_mode_explicit = pgp_mode is not None

        # Accept unambiguous prefixes such as "e" and "en". Treat "none"
        # as "no", and reject unknown values instead of disabling PGP.
        if not pgp_mode:
            self.pgp_mode = PGP_MODE_DEFAULT

        elif str(pgp_mode).lower() == "none":
            self.pgp_mode = PGPMode.NONE

        else:
            self.pgp_mode = next(
                (m for m in PGP_MODES if m.startswith(str(pgp_mode).lower())),
                None,
            )
            if self.pgp_mode is None:
                msg = f"The Email PGP mode specified ({pgp_mode}) is invalid."
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

        # Parse string values such as "no" correctly.
        self.use_wkd = parse_bool(use_wkd)

        # wkd=yes implies pgp=encrypt when pgp= was not explicitly set
        if self.use_wkd and not pgp_mode_explicit:
            self.pgp_mode = PGPMode.ENCRYPT

        # Build a WKD controller when WKD key discovery is requested
        wkd_ctrl = (
            _wkd.AppriseWKDController(
                asset=self.asset,
                verify_certificate=self.verify_certificate,
                request_timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )
            if self.use_wkd
            else None
        )

        # Prepare our Pretty Good Privacy Object
        self.pgp = _pgp.ApprisePGPController(
            path=self.store.path,
            pub_keyfile=pgp_key,
            prv_keyfile=pgp_privkey,
            email=self.from_addr[1],
            asset=self.asset,
            wkd=wkd_ctrl,
        )

        # We store so we can generate a URL later on
        self.pgp_key = pgp_key

        # Store the private key path so it can be round-tripped via url()
        self.pgp_privkey = pgp_privkey

        if self.pgp_mode != PGP_MODE_DEFAULT and not _pgp.PGP_SUPPORT:
            self.logger.warning(
                "PGP Support is not available on this installation; "
                "ask admin to install PGPy"
            )

        # Store inline attachment mode (RFC 2387); fall back to the
        # template default when the value is None or unrecognisable
        self.inline = parse_bool(
            inline, self.template_args["inline"]["default"]
        )

        return

    def _protocol_headers(self, body):
        """Return protocol headers supplied by an Email subclass."""
        return {}

    def apply_email_defaults(self, secure_mode=None, port=None, **kwargs):
        """Apply provider defaults inferred from the sender address."""

        if self.smtp_host:
            # Preserve an explicitly selected SMTP server.
            return

        # detect our email address using our user/host combo
        from_addr = (
            "{}@{}".format(
                re.split(r"[\s@]+", self.user)[0],
                self.host,
            )
            if self.user
            else self.host
        )

        for i in range(len(templates.EMAIL_TEMPLATES)):  # pragma: no branch
            self.logger.trace(
                "Scanning %s against %s",
                from_addr,
                templates.EMAIL_TEMPLATES[i][0],
            )

            match = templates.EMAIL_TEMPLATES[i][1].match(from_addr)
            if match:
                self.logger.debug(
                    f"Applying {templates.EMAIL_TEMPLATES[i][0]} Defaults"
                )

                # A template may require a specific security mode.
                self.secure = templates.EMAIL_TEMPLATES[i][2].get(
                    "secure", self.secure
                )

                # The SMTP Host check is already done above; if it was
                # specified we wouldn't even reach this part of the code.
                self.smtp_host = templates.EMAIL_TEMPLATES[i][2].get(
                    "smtp_host", self.smtp_host
                )

                # The following can be over-ridden if defined manually in the
                # Apprise URL.  Otherwise they take on the template value
                if not port:
                    self.port = templates.EMAIL_TEMPLATES[i][2].get(
                        "port", self.port
                    )
                if not secure_mode:
                    self.secure_mode = templates.EMAIL_TEMPLATES[i][2].get(
                        "secure_mode", self.secure_mode
                    )

                # Adjust email login based on the defined usertype. If no entry
                # was specified, then we default to having them all set (which
                # basically implies that there are no restrictions and use use
                # whatever was specified)
                login_type = templates.EMAIL_TEMPLATES[i][2].get(
                    "login_type", []
                )
                if login_type:
                    # only apply additional logic to our user if a login_type
                    # was specified.
                    if is_email(self.user):
                        if WebBaseLogin.EMAIL not in login_type:
                            # Email specified but login type
                            # not supported; switch it to user id
                            self.user = match.group("id")

                        else:
                            # Enforce our host information
                            self.host = self.user.split("@")[1]

                    elif WebBaseLogin.USERID not in login_type:
                        # user specified but login type
                        # not supported; switch it to email
                        self.user = "{}@{}".format(self.user, self.host)

                if (
                    "from_user" in templates.EMAIL_TEMPLATES[i][2]
                    and not self.from_addr[1]
                ):
                    # Update our from address if defined
                    self.from_addr[1] = "{}@{}".format(
                        templates.EMAIL_TEMPLATES[i][2]["from_user"], self.host
                    )

                break

    def send(
        self,
        body,
        title="",
        notify_type=NotifyType.INFO,
        attach=None,
        body_format=None,
        **kwargs,
    ):
        """Perform Email Notification."""

        if not self.targets:
            # There is no one to email; we're done
            logger.warning("There are no Email recipients to notify")
            return False

        # error tracking (used for function return)
        has_error = False

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            with AppriseSMTPController(
                host=self.smtp_host,
                port=self.port,
                secure_mode=self.secure_mode,
                user=self.user,
                password=self.password,
                verify_certificate=self.verify_certificate,
                socket_connect_timeout=self.socket_connect_timeout,
            ) as smtp:
                # Prepare our headers
                headers = {
                    "X-Application": self.app_id,
                }
                headers.update(self.headers)

                # Add any protocol headers supplied by a subclass.
                headers.update(self._protocol_headers(body))

                # Build each message in its resolved text or HTML format.
                for message in NotifyEmail.prepare_emails(
                    subject=title,
                    body=body,
                    notify_format=self.resolve_format(body_format),
                    from_addr=self.from_addr,
                    to=self.targets,
                    cc=self.cc,
                    bcc=self.bcc,
                    reply_to=self.reply_to,
                    smtp_host=self.smtp_host,
                    attach=attach,
                    headers=headers,
                    names=self.names,
                    pgp=self.pgp,
                    pgp_mode=self.pgp_mode,
                    inline=self.inline,
                    tzinfo=self.tzinfo,
                ):
                    if smtp.sendmail(
                        self.from_addr[1], message.to_addrs, message.body
                    ):
                        self.logger.info("Sent Email to %s", message.recipient)

                    else:
                        self.logger.warning(
                            'Sending email to "%s" failed.',
                            message.recipient,
                        )

                        # Mark as failure
                        has_error = True

        except (
            OSError,
            smtplib.SMTPException,
            RuntimeError,
            AppriseImproperlyConfigured,
        ) as e:
            self.logger.warning(
                'Connection error while submitting email to "%s"',
                self.smtp_host,
            )
            self.logger.debug(f"Socket Exception: {e}")

            # Mark as failure
            has_error = True

        except AppriseEmailException as e:
            self.logger.debug(f"Socket Exception: {e}")

            # Mark as failure
            has_error = True

        # Reduce our dictionary (eliminate expired keys if any)
        self.pgp.prune()

        return not has_error

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define an URL parameters
        params = {}

        # Always emit pgp= when wkd=yes is set, even when the mode is the
        # default 'none'.  Without this, a URL like ?pgp=none&wkd=yes would
        # round-trip as ?wkd=yes and the wkd=yes→pgp=encrypt implication
        # would silently re-enable encryption on re-parse.
        if self.pgp_mode != PGP_MODE_DEFAULT or self.use_wkd:
            params["pgp"] = self.pgp_mode

        # Store our public key back into the URL when one was supplied;
        # mask the value when building a privacy-safe URL because the key
        # path can reveal local filesystem layout or remote key server URLs
        if self.pgp_key is not None:
            params["pgppub"] = (
                "****"
                if privacy
                else NotifyEmail.quote(self.pgp_key, safe=":\\/")
            )

        # Store the private key path in the URL in the same way; masked
        # in privacy mode because private key paths are sensitive
        if self.pgp_privkey is not None:
            params["pgpprv"] = (
                "****"
                if privacy
                else NotifyEmail.quote(self.pgp_privkey, safe=":\\/")
            )

        # Include wkd= when Web Key Directory lookup is enabled
        if self.use_wkd:
            params["wkd"] = "yes"

        # Emit inline flag only when enabled
        if self.inline:
            params["inline"] = "yes"

        # Append our headers into our parameters
        params.update({"+{}".format(k): v for k, v in self.headers.items()})

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        from_addr = None
        if len(self.targets) == 1 and self.targets[0][1] != self.from_addr[1]:
            # A custom email was provided
            from_addr = self.from_addr[1]

        if self.smtp_host != self.host:
            # Apply our SMTP Host only if it differs from the provided hostname
            params["smtp"] = self.smtp_host

        if self.secure:
            # Mode is only required if we're dealing with a secure connection
            params["mode"] = self.secure_mode

        if self.from_addr[0] and self.from_addr[0] != self.app_id:
            # A custom name was provided
            params["from"] = (
                self.from_addr[0]
                if not from_addr
                else formataddr(
                    (self.from_addr[0], from_addr), charset="utf-8"
                )
            )

        elif from_addr:
            params["from"] = formataddr((False, from_addr), charset="utf-8")

        elif not self.user:
            params["from"] = formataddr(
                (False, self.from_addr[1]), charset="utf-8"
            )

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

        if self.bcc:
            # Handle our Blind Carbon Copy Addresses
            params["bcc"] = ",".join(
                [
                    formataddr(
                        (self.names.get(e, False), e),
                        # Swap comma for its escaped url code (if
                        # detected) since we use it as a delimiter
                        charset="utf-8",
                    ).replace(",", "%2C")
                    for e in self.bcc
                ]
            )

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

        # pull email suffix from username (if present)
        user = None if not self.user else self.user.split("@")[0]

        # Determine Authentication
        auth = ""
        if self.user and self.password:
            auth = "{user}:{password}@".format(
                user=NotifyEmail.quote(user, safe=""),
                password=self.pprint(
                    self.password, privacy, mode=PrivacyMode.Secret, safe=""
                ),
            )
        elif user:
            # user url
            auth = "{user}@".format(
                user=NotifyEmail.quote(user, safe=""),
            )

        # Default Port setup
        default_port = SECURE_MODES[self.secure_mode]["default_port"]

        # a simple boolean check as to whether we display our target emails
        # or not
        has_targets = not (
            len(self.targets) == 1 and self.targets[0][1] == self.from_addr[1]
        )

        return "{schema}://{auth}{hostname}{port}/{targets}?{params}".format(
            schema=self.secure_protocol if self.secure else self.protocol,
            auth=auth,
            # never encode hostname since we're expecting it to be a valid one
            hostname=self.host,
            port=(
                ""
                if self.port is None or self.port == default_port
                else ":{}".format(self.port)
            ),
            targets=(
                ""
                if not has_targets
                else "/".join(
                    [
                        NotifyEmail.quote(
                            "{}{}".format(
                                "" if not e[0] else "{}:".format(e[0]), e[1]
                            ),
                            safe="",
                        )
                        for e in self.targets
                    ]
                )
            ),
            params=NotifyEmail.urlencode(params, safe="*"),
        )

    @property
    def url_identifier(self):
        """
        Returns all of the identifiers that make this URL unique from
        another similar one. Targets or end points should never be identified
        here.
        """
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.user,
            self.password,
            self.host,
            self.smtp_host,
            (
                self.port
                if self.port
                else SECURE_MODES[self.secure_mode]["default_port"]
            ),
        )

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """
        return len(self.targets) if self.targets else 1

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to re-instantiate this object.

        """
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Prepare our target lists
        results["targets"] = []

        if is_ipaddr(results["host"]):
            # Silently move on and do not disrupt any configuration
            pass

        elif not is_hostname(
            results["host"], ipv4=False, ipv6=False, underscore=False
        ):
            if is_email(NotifyEmail.unquote(results["host"])):
                # Don't lose defined email addresses
                results["targets"].append(NotifyEmail.unquote(results["host"]))

            # Clear invalid hosts so a later step can infer one.
            results["host"] = ""

        # Accept PGP mode prefixes and treat "none" as "no".
        pgp_raw = results["qsd"].get("pgp", "")
        if pgp_raw:
            pgp_mode = next(
                (m for m in PGP_MODES if m.startswith(str(pgp_raw).lower())),
                None,
            )
            if pgp_mode is None:
                # Let __init__ report invalid and removed boolean values.
                pgp_mode = pgp_raw
            results["pgp_mode"] = pgp_mode

        # Get Web Key Directory flag
        if "wkd" in results["qsd"] and results["qsd"]["wkd"]:
            results["use_wkd"] = parse_bool(results["qsd"]["wkd"])

        # wkd=yes implies pgp=encrypt when pgp= was not present in the URL
        if results.get("use_wkd") and "pgp_mode" not in results:
            results["pgp_mode"] = PGPMode.ENCRYPT

        # Get PGP Public Key Override (canonical name: pgppub=)
        if "pgppub" in results["qsd"] and results["qsd"]["pgppub"]:
            results["pgp_key"] = NotifyEmail.unquote(results["qsd"]["pgppub"])

        # Get PGP Private Key Override (canonical name: pgpprv=)
        if "pgpprv" in results["qsd"] and results["qsd"]["pgpprv"]:
            results["pgp_privkey"] = NotifyEmail.unquote(
                results["qsd"]["pgpprv"]
            )

        # Get inline attachment flag
        if "inline" in results["qsd"]:
            results["inline"] = parse_bool(
                results["qsd"]["inline"],
                NotifyEmail.template_args["inline"]["default"],
            )

        # The From address is a must; either through the use of templates
        # from= entry and/or merging the user and hostname together, this
        # must be calculated or parse_url will fail.
        from_addr = ""

        # The server we connect to to send our mail to
        smtp_host = ""

        # Get our potential email targets; if none our found we'll just
        # add one to ourselves
        results["targets"] += NotifyEmail.split_path(results["fullpath"])

        # Attempt to detect 'to' email address
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"].append(results["qsd"]["to"])

        # Attempt to detect 'from' email address
        if "from" in results["qsd"] and len(results["qsd"]["from"]):
            from_addr = NotifyEmail.unquote(results["qsd"]["from"])

            if "name" in results["qsd"] and len(results["qsd"]["name"]):
                from_addr = formataddr(
                    (NotifyEmail.unquote(results["qsd"]["name"]), from_addr),
                    charset="utf-8",
                )

        elif "name" in results["qsd"] and len(results["qsd"]["name"]):
            # Extract from name to associate with from address
            from_addr = NotifyEmail.unquote(results["qsd"]["name"])

        # Store SMTP Host if specified
        if "smtp" in results["qsd"] and len(results["qsd"]["smtp"]):
            # Extract the smtp server
            smtp_host = NotifyEmail.unquote(results["qsd"]["smtp"])

        if "mode" in results["qsd"] and len(results["qsd"]["mode"]):
            # Extract the security mode override.
            results["secure_mode"] = results["qsd"]["mode"].lower()

        # Handle Carbon Copy Addresses
        if "cc" in results["qsd"] and len(results["qsd"]["cc"]):
            results["cc"] = results["qsd"]["cc"]

        # Handle Blind Carbon Copy Addresses
        if "bcc" in results["qsd"] and len(results["qsd"]["bcc"]):
            results["bcc"] = results["qsd"]["bcc"]

        # Handle Reply To Addresses
        if "reply" in results["qsd"] and len(results["qsd"]["reply"]):
            results["reply_to"] = results["qsd"]["reply"]

        results["from_addr"] = from_addr
        results["smtp_host"] = smtp_host

        # Add our Meta Headers that the user can provide with their outbound
        # emails
        results["headers"] = {
            NotifyBase.unquote(x): NotifyBase.unquote(y)
            for x, y in results["qsd+"].items()
        }

        return results

    @staticmethod
    def _get_charset(input_string):
        """Use UTF-8 only when text contains non-ASCII characters.

        Encoding ASCII unnecessarily can trigger spam filters such as
        Rspamd's ``SUBJ_EXCESS_QP`` rule.
        """
        if not input_string:
            return None
        return "utf-8" if not all(ord(c) < 128 for c in input_string) else None

    @staticmethod
    def prepare_emails(
        subject,
        body,
        from_addr,
        to,
        cc: Optional[set] = None,
        bcc: Optional[set] = None,
        reply_to: Optional[set] = None,
        # SMTP host used in the Message-ID
        smtp_host=None,
        # Either HTML or plain text
        notify_format=NotifyFormat.HTML,
        attach=None,
        headers: Optional[dict] = None,
        # Display names keyed by address
        names=None,
        # Optional PGP controller
        pgp=None,
        # PGP mode string (PGPMode.NONE / PGPMode.SIGN / PGPMode.ENCRYPT)
        pgp_mode=PGP_MODE_DEFAULT,
        # When True, image attachments are embedded inline (RFC 2387)
        # so HTML bodies can reference them via <img src="cid:filename">
        inline=False,
        # Use the system timezone when none is provided.
        tzinfo=None,
    ):
        """Yield prepared email messages.

        - ``from_addr`` is ``(name, address)``; ``to`` contains those pairs.
        - ``cc`` and ``bcc`` are address sets; ``reply_to`` is one address.
        - ``smtp_host`` forms the Message-ID, and ``notify_format`` selects
          plain text or HTML.
        - ``attach`` contains Apprise attachments; ``headers`` adds headers.
        - ``names`` maps addresses to display names for CC and BCC entries.
        - ``pgp`` supplies signing or encryption. ``PGPMode.SIGN`` may also
          encrypt when a recipient key is available.
        """
        if not to:
            # There is no one to email; we're done
            msg = "There are no Email recipients to notify"
            logger.warning(msg)
            raise AppriseEmailException(msg) from None

        elif pgp and pgp_mode != PGP_MODE_DEFAULT and not _pgp.PGP_SUPPORT:
            msg = "PGP Support unavailable; install PGPy library"
            logger.warning(msg)
            raise AppriseEmailException(msg) from None

        if headers is None:
            headers = {}

        if cc is None:
            cc = set()

        if bcc is None:
            bcc = set()

        if reply_to is None:
            reply_to = set()

        if not names:
            # Prepare a empty dictionary to prevent errors/warnings
            names = {}

        if not smtp_host:
            # Generate a host identifier (used for Message-ID Creation)
            smtp_host = from_addr[1].split("@")[1]

        if not tzinfo:
            # use server time
            tzinfo = datetime.now().astimezone().tzinfo

        logger.debug(f"SMTP Host: {smtp_host}")

        # Create a copy of the targets list
        emails = list(to)
        while len(emails):
            # Get our email to notify
            to_name, to_addr = emails.pop(0)

            # Strip target out of cc list if in To or Bcc
            cc_ = cc - bcc - {to_addr}

            # Strip target out of bcc list if in To
            bcc_ = bcc - {to_addr}

            # Strip target out of reply_to list if in To
            reply_to_ = reply_to - {to_addr}

            # Format our cc addresses to support the Name field
            cc_ = [
                formataddr((names.get(addr, False), addr), charset="utf-8")
                for addr in cc_
            ]

            # Format our bcc addresses to support the Name field
            bcc_ = [
                formataddr((names.get(addr, False), addr), charset="utf-8")
                for addr in bcc_
            ]

            if reply_to_:
                # Format our reply-to addresses to support the Name field
                reply_to = [
                    formataddr((names.get(addr, False), addr), charset="utf-8")
                    for addr in reply_to_
                ]

            logger.debug(
                "Email From: {}".format(formataddr(from_addr, charset="utf-8"))
            )

            logger.debug("Email To: {}".format(to_addr))
            if cc_:
                logger.debug("Email Cc: {}".format(", ".join(cc_)))
            if bcc_:
                logger.debug("Email Bcc: {}".format(", ".join(bcc_)))
            if reply_to_:
                logger.debug("Email Reply-To: {}".format(", ".join(reply_to_)))

            # Prepare inline attachments before building the MIME body:
            # - HTML appends missing image references.
            # - Plain text adds an [Image: name] marker.
            # Non-images remain regular attachments unless explicitly linked.
            cid_refs = set()
            if inline and attach:
                if notify_format == NotifyFormat.HTML:
                    # Collect filenames already referenced via cid:;
                    # decode %20 to spaces so filenames with spaces match
                    # the raw attachment name regardless of how the caller
                    # encoded the URI.
                    cid_refs = {
                        ref.replace("%20", " ")
                        for ref in re.findall(r'cid:([^\s"\'>\)]+)', body)
                    }

                    # Build a set of all attachment filenames so we can
                    # warn about cid: refs that have no matching file
                    _attach_names = {
                        _a.name or f"file{_no:03}.dat"
                        for _no, _a in enumerate(attach, start=1)
                    }

                    # Warn when a cid: reference has no matching attachment.
                    for _ref in sorted(cid_refs - _attach_names):
                        logger.warning(
                            "Email inline: no attachment matches "
                            "cid:%s -- check the filename.",
                            _ref,
                        )

                    # Ignore missing files when selecting the MIME wrapper.
                    # Explicit matching references may use any file type.
                    cid_refs &= _attach_names

                    # Append inline anchors for any image not yet listed
                    img_appends = []
                    for _no, _a in enumerate(attach, start=1):
                        _fname = _a.name or f"file{_no:03}.dat"
                        if (_a.mimetype or "").lower().startswith(
                            "image/"
                        ) and _fname not in cid_refs:
                            img_appends.append(_fname)
                            cid_refs.add(_fname)

                    if img_appends:
                        # Encode spaces as %20 in cid: URIs so filenames
                        # with spaces remain valid HTML attribute values
                        body = body + "".join(
                            '<br/><img src="cid:{}">'.format(
                                n.replace(" ", "%20")
                            )
                            for n in img_appends
                        )

                else:
                    # Plain text: annotate inline images with a short
                    # text placeholder (images cannot be embedded here)
                    txt_imgs = []
                    for _no, _a in enumerate(attach, start=1):
                        _fname = _a.name or f"file{_no:03}.dat"
                        if (_a.mimetype or "").lower().startswith("image/"):
                            txt_imgs.append(_fname)

                    if txt_imgs:
                        body = (
                            body
                            + "\n"
                            + "\n".join(f"[Image: {n}]" for n in txt_imgs)
                        )

            # Prepare Email Message
            if notify_format == NotifyFormat.HTML:
                base = MIMEMultipart("alternative")
                base.attach(
                    MIMEText(
                        convert_between(
                            NotifyFormat.HTML, NotifyFormat.TEXT, body
                        ),
                        "plain",
                        "utf-8",
                    )
                )
                base.attach(MIMEText(body, "html", "utf-8"))

            else:
                base = MIMEText(body, "plain", "utf-8")

            if attach:
                # Use multipart/related when any image will be embedded
                # inline (RFC 2387); otherwise keep multipart/mixed
                mixed = MIMEMultipart("related" if cid_refs else "mixed")
                mixed.attach(base)

                # Now store our attachments
                for no, attachment in enumerate(attach, start=1):
                    if not attachment:
                        # We could not load the attachment; take an early
                        # exit since this isn't what the end user wanted

                        # We could not access the attachment
                        msg = "Could not access attachment {}.".format(
                            attachment.url(privacy=True)
                        )
                        logger.warning(msg)
                        raise AppriseEmailException(msg)

                    logger.debug(
                        "Preparing Email attachment {}".format(
                            attachment.url(privacy=True)
                        )
                    )

                    with attachment.open() as abody:
                        app = MIMEApplication(abody.read())
                        app.set_type(attachment.mimetype)

                        # Prepare our attachment name
                        filename = (
                            attachment.name
                            if attachment.name
                            else f"file{no:03}.dat"
                        )

                        if filename in cid_refs:
                            # Filename is referenced by a cid: anchor in
                            # the HTML body; embed it inline so clients
                            # render it in-place rather than as a download
                            app.add_header(
                                "Content-Disposition",
                                'inline; filename="{}"'.format(
                                    Header(filename, "utf-8")
                                ),
                            )
                            app.add_header(
                                "Content-ID",
                                # Encode spaces so the Content-ID matches
                                # the cid: URI in the HTML anchor
                                "<{}>".format(filename.replace(" ", "%20")),
                            )

                        else:
                            # Non-image or plain-text-email attachment;
                            # keep it as a regular downloadable file
                            app.add_header(
                                "Content-Disposition",
                                'attachment; filename="{}"'.format(
                                    Header(filename, "utf-8")
                                ),
                            )
                        mixed.attach(app)

                base = mixed

            # Suppress a custom Autocrypt value only when the controller
            # supplies one of its own.
            autocrypt_added = False

            if pgp and pgp_mode == PGPMode.SIGN:
                logger.debug("Securing Email with PGP Signature")
                # RFC 3156 requires the signature to be computed over the CRLF
                # to guarantee all recipients can verify against it.
                sig_result = pgp.sign(
                    re.sub(r"(?:\r\n|\n|\r(?!\n))", "\r\n", base.as_string())
                )

                if not sig_result:
                    # Signing was requested but could not be performed;
                    # this is a hard failure for the sign mode.  Include the
                    # plugin-specific hint here (pgp.py logs only generic
                    # debug detail so it stays reusable across plugins).
                    msg = (
                        "Unable to sign email via PGP; supply a private key"
                        " via pgpprv= or place one in the cache directory"
                    )
                    logger.warning(msg)
                    raise AppriseEmailException(msg)

                # Unpack the signature and its hash algorithm label
                sig_str, micalg = sig_result

                # Build the RFC 3156 multipart/signed container
                signed = MIMEMultipart(
                    "signed",
                    micalg=micalg,
                    protocol="application/pgp-signature",
                )

                # First part: the original message body (must not be
                # modified after this point as the signature covers it)
                signed.attach(base)

                # Second part: the detached PGP signature block
                sig_part = MIMEBase("application", "pgp-signature")
                sig_part.set_payload(sig_str)
                sig_part.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename="signature.asc",
                )
                signed.attach(sig_part)

                # Replace base with the signed container so the rest of
                # the function continues to work unchanged
                base = signed

                # Encrypt when the recipient already has a public key.
                # Sign mode remains usable when no recipient key exists.
                enc_content = pgp.encrypt(
                    base.as_string(), to_addr, autogen=False
                )
                if enc_content:
                    logger.debug("PGP public key found; adding encryption")

                    # Wrap the signed body in a multipart/encrypted
                    # container (the signed payload becomes the ciphertext)
                    enc = MIMEMultipart(
                        "encrypted",
                        protocol="application/pgp-encrypted",
                    )

                    # Version identifier part (required by RFC 3156)
                    ver_part = MIMEText("Version: 1", "plain")
                    ver_part.set_type("application/pgp-encrypted")
                    enc.attach(ver_part)

                    # Encrypted data part
                    data_part = MIMEBase("application", "octet-stream")
                    data_part.set_payload(enc_content)
                    enc.attach(data_part)

                    # Replace base with the fully encrypted container
                    base = enc

                # Advertise our key on the outer message so an Autocrypt-aware
                # recipient can encrypt future replies.
                autocrypt = pgp.autocrypt_header()
                if autocrypt:
                    base.add_header("Autocrypt", autocrypt)
                    autocrypt_added = True

            elif pgp and pgp_mode == PGPMode.ENCRYPT:
                logger.debug("Securing Email with PGP Encryption")
                # Set our header information to include in the encryption
                base["From"] = formataddr(
                    (None, from_addr[1]), charset="utf-8"
                )
                base["To"] = formataddr((None, to_addr), charset="utf-8")
                base["Subject"] = Header(
                    subject, NotifyEmail._get_charset(subject)
                )

                # External recipients need an existing key. Self-sends may
                # generate the sender's key when pgp_autogen permits it.
                autogen = (
                    None if to_addr.lower() == from_addr[1].lower() else False
                )
                encrypted_content = pgp.encrypt(
                    base.as_string(), to_addr, autogen=autogen
                )

                if not encrypted_content:
                    # Give Email users a plugin-specific recovery hint.
                    msg = (
                        "Unable to encrypt email via PGP; supply a public key"
                        " via pgppub= or place one in the cache directory"
                    )
                    logger.warning(msg)
                    raise AppriseEmailException(msg)

                # prepare our message
                base = MIMEMultipart(
                    "encrypted", protocol="application/pgp-encrypted"
                )

                # Advertise our key for encrypted replies.
                autocrypt = pgp.autocrypt_header()
                if autocrypt:
                    base.add_header("Autocrypt", autocrypt)
                    autocrypt_added = True

                # Set Encryption Info Part
                enc_payload = MIMEText("Version: 1", "plain")
                enc_payload.set_type("application/pgp-encrypted")
                base.attach(enc_payload)

                # Set Encrypted Data Part
                enc_payload = MIMEBase("application", "octet-stream")
                enc_payload.set_payload(encrypted_content)
                base.attach(enc_payload)

            # Header names are case-insensitive; keep only the first
            # Autocrypt value unless the controller supplied its own.
            autocrypt_seen = autocrypt_added
            for k, v in headers.items():
                if k.strip().lower() == "autocrypt":
                    if autocrypt_seen:
                        continue
                    autocrypt_seen = True
                base[k] = Header(v, NotifyEmail._get_charset(v))

            base["Subject"] = Header(
                subject, NotifyEmail._get_charset(subject)
            )
            base["From"] = formataddr(from_addr, charset="utf-8")
            base["To"] = formataddr((to_name, to_addr), charset="utf-8")
            base["Message-ID"] = make_msgid(domain=smtp_host)
            base["Date"] = format_datetime(datetime.now(tz=tzinfo))

            if cc:
                base["Cc"] = ",".join(cc_)

            if reply_to_:
                base["Reply-To"] = ",".join(reply_to)

            yield EmailMessage(
                recipient=to_addr,
                to_addrs=[to_addr, *list(cc_), *list(bcc_)],
                body=base.as_string(),
            )

    @staticmethod
    def runtime_deps():
        """Return this plugin's optional package names."""
        return ("pgpy",)
