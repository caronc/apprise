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

import re

import requests

from ..common import NotifyImageSize, NotifyType
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from .base import NotifyBase


class FORMPayloadField:
    """Identifies the fields available in the FORM Payload."""

    VERSION = "version"
    TITLE = "title"
    MESSAGE = "message"
    MESSAGETYPE = "type"


# Defines the method to send the notification
METHODS = ("POST", "GET", "DELETE", "PUT", "HEAD", "PATCH")


class NotifyForm(NotifyBase):
    """A wrapper for Form Notifications."""

    # Support
    # - file*
    # - file?
    # - file*name
    # - file?name
    # - ?file
    # - *file
    # - file
    # The code will convert the ? or * to the digit increments
    __attach_as_re = re.compile(
        r"((?P<match1>(?P<id1a>[a-z0-9_-]+)?"
        r"(?P<wc1>[*?+$:.%]+)(?P<id1b>[a-z0-9_-]+))"
        r"|(?P<match2>(?P<id2>[a-z0-9_-]+)(?P<wc2>[*?+$:.%]?)))",
        re.IGNORECASE,
    )

    # Our count
    attach_as_count = "{:02d}"

    # the default attach_as value
    attach_as_default = f"file{attach_as_count}"

    # The default descriptive name associated with the Notification
    service_name = "Form"

    # The default protocol
    protocol = "form"

    # The default secure protocol
    secure_protocol = "forms"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_Custom_Form"

    # Support attachments
    attachment_support = True

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_128

    # Disable throttle rate for Form requests since they are normally
    # local anyway
    request_rate_per_sec = 0

    # Define the FORM version to place in all payloads
    # Version: Major.Minor,  Major is only updated if the entire schema is
    # changed. If just adding new items (or removing old ones, only increment
    # the Minor!
    form_version = "1.0"

    # Define object templates
    templates = (
        "{schema}://{host}",
        "{schema}://{host}:{port}",
        "{schema}://{user}@{host}",
        "{schema}://{user}@{host}:{port}",
        "{schema}://{user}:{password}@{host}",
        "{schema}://{user}:{password}@{host}:{port}",
    )

    # Define our tokens; these are the minimum tokens required required to
    # be passed into this function (as arguments). The syntax appends any
    # previously defined in the base package and builds onto them
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "host": {
                "name": _("Hostname"),
                "type": "string",
                "required": True,
            },
            "port": {
                "name": _("Port"),
                "type": "int",
                "min": 1,
                "max": 65535,
            },
            "user": {
                "name": _("Username"),
                "type": "string",
            },
            "password": {
                "name": _("Password"),
                "type": "string",
                "private": True,
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "method": {
                "name": _("Fetch Method"),
                "type": "choice:string",
                "values": METHODS,
                "default": METHODS[0],
            },
            "attach-as": {
                "name": _("Attach File As"),
                "type": "string",
                "default": "file*",
                "map_to": "attach_as",
            },
        },
    )

    # Define any kwargs we're using
    template_kwargs = {
        "headers": {
            "name": _("HTTP Header"),
            "prefix": "+",
        },
        "payload": {
            "name": _("Payload Extras"),
            "prefix": ":",
        },
        "params": {
            "name": _("GET Params"),
            "prefix": "-",
        },
    }

    def __init__(
        self,
        headers=None,
        method=None,
        payload=None,
        params=None,
        attach_as=None,
        **kwargs,
    ):
        """Initialize Form Object.

        headers can be a dictionary of key/value pairs that you want to
        additionally include as part of the server headers to post with
        """
        super().__init__(**kwargs)

        self.fullpath = kwargs.get("fullpath")
        if not isinstance(self.fullpath, str):
            self.fullpath = ""

        self.method = (
            self.template_args["method"]["default"]
            if not isinstance(method, str)
            else method.upper()
        )

        if self.method not in METHODS:
            msg = f"The method specified ({method}) is invalid."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Custom File Attachment Over-Ride Support
        if not isinstance(attach_as, str):
            # Default value
            self.attach_as = self.attach_as_default
            self.attach_multi_support = True

        else:
            result = self.__attach_as_re.match(attach_as.strip())
            if not result:
                msg = f"The attach-as specified ({attach_as}) is invalid."
                self.logger.warning(msg)
                raise TypeError(msg)

            self.attach_as = ""
            self.attach_multi_support = False
            if result.group("match1"):
                if result.group("id1a"):
                    self.attach_as += result.group("id1a")

                self.attach_as += self.attach_as_count
                self.attach_multi_support = True
                self.attach_as += result.group("id1b")

            else:  # result.group('match2'):
                self.attach_as += result.group("id2")
                if result.group("wc2"):
                    self.attach_as += self.attach_as_count
                    self.attach_multi_support = True

        # A payload map allows users to over-ride the default mapping if
        # they're detected with the :overide=value.  Normally this would
        # create a new key and assign it the value specified.  However
        # if the key you specify is actually an internally mapped one,
        # then a re-mapping takes place using the value
        self.payload_map = {
            FORMPayloadField.VERSION: FORMPayloadField.VERSION,
            FORMPayloadField.TITLE: FORMPayloadField.TITLE,
            FORMPayloadField.MESSAGE: FORMPayloadField.MESSAGE,
            FORMPayloadField.MESSAGETYPE: FORMPayloadField.MESSAGETYPE,
        }

        self.params = {}
        if params:
            # Store our extra headers
            self.params.update(params)

        self.headers = {}
        if headers:
            # Store our extra headers
            self.headers.update(headers)

        self.payload_overrides = {}
        self.payload_extras = {}
        if payload:
            # Store our extra payload entries
            self.payload_extras.update(payload)
            for key in list(self.payload_extras.keys()):
                # Any values set in the payload to alter a system related one
                # alters the system key.  Hence :message=msg maps the 'message'
                # variable that otherwise already contains the payload to be
                # 'msg' instead (containing the payload)
                if key in self.payload_map:
                    self.payload_map[key] = self.payload_extras[key]
                    self.payload_overrides[key] = self.payload_extras[key]
                    del self.payload_extras[key]

        return

    def send(
        self,
        body,
        title="",
        notify_type=NotifyType.INFO,
        attach=None,
        **kwargs,
    ):
        """Perform Form Notification."""

        # Prepare HTTP Headers
        headers = {
            "User-Agent": self.app_id,
        }

        # Apply any/all header over-rides defined
        headers.update(self.headers)

        # Track our potential attachments
        files = []
        if attach and self.attachment_support:
            for no, attachment in enumerate(attach, start=1):
                # Perform some simple error checking
                if not attachment:
                    # We could not access the attachment
                    self.logger.error(
                        "Could not access attachment"
                        f" {attachment.url(privacy=True)}."
                    )
                    return False

                try:
                    files.append((
                        (
                            self.attach_as.format(no)
                            if self.attach_multi_support
                            else self.attach_as
                        ),
                        (
                            (
                                attachment.name
                                if attachment.name
                                else f"file{no:03}.dat"
                            ),
                            # file handle is safely closed in `finally`; inline
                            # open is intentional
                            open(attachment.path, "rb"),  # noqa: SIM115
                            attachment.mimetype,
                        ),
                    ))

                except OSError as e:
                    self.logger.warning(
                        "An I/O error occurred while opening {}.".format(
                            attachment.name if attachment else "attachment"
                        )
                    )
                    self.logger.debug(f"I/O Exception: {e!s}")
                    return False

            if not self.attach_multi_support and no > 1:
                self.logger.warning(
                    "Multiple attachments provided while "
                    "form:// Multi-Attachment Support not enabled"
                )

        # prepare Form Object
        payload = {}

        for key, value in (
            (FORMPayloadField.VERSION, self.form_version),
            (FORMPayloadField.TITLE, title),
            (FORMPayloadField.MESSAGE, body),
            (FORMPayloadField.MESSAGETYPE, notify_type),
        ):

            if not self.payload_map[key]:
                # Do not store element in payload response
                continue
            payload[self.payload_map[key]] = value

        # Apply any/all payload over-rides defined
        payload.update(self.payload_extras)

        auth = None
        if self.user:
            auth = (self.user, self.password)

        # Set our schema
        schema = "https" if self.secure else "http"

        url = f"{schema}://{self.host}"
        if isinstance(self.port, int):
            url += f":{self.port}"

        url += self.fullpath

        self.logger.debug(
            f"Form {self.method} URL:"
            f" {url} (cert_verify={self.verify_certificate!r})"
        )
        self.logger.debug(f"Form Payload: {payload!s}")

        # Always call throttle before any remote server i/o is made
        self.throttle()

        if self.method == "GET":
            method = requests.get
            payload.update(self.params)

        elif self.method == "PUT":
            method = requests.put

        elif self.method == "PATCH":
            method = requests.patch

        elif self.method == "DELETE":
            method = requests.delete

        elif self.method == "HEAD":
            method = requests.head

        else:  # POST
            method = requests.post

        try:
            r = method(
                url,
                files=files if files else None,
                data=payload if self.method != "GET" else None,
                params=payload if self.method == "GET" else self.params,
                headers=headers,
                auth=auth,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )
            if r.status_code < 200 or r.status_code >= 300:
                # We had a problem
                status_str = NotifyForm.http_response_code_lookup(
                    r.status_code
                )

                self.logger.warning(
                    "Failed to send Form %s notification: %s%serror=%s.",
                    self.method,
                    status_str,
                    ", " if status_str else "",
                    str(r.status_code),
                )

                self.logger.debug(f"Response Details:\r\n{r.content}")

                # Return; we're done
                return False

            else:
                self.logger.info("Sent Form %s notification.", self.method)

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending Form "
                f"notification to {self.host}."
            )
            self.logger.debug(f"Socket Exception: {e!s}")

            # Return; we're done
            return False

        except OSError as e:
            self.logger.warning(
                "An I/O error occurred while reading one of the "
                "attached files."
            )
            self.logger.debug(f"I/O Exception: {e!s}")
            return False

        finally:
            for file in files:
                # Ensure all files are closed
                file[1][1].close()

        return True

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.user,
            self.password,
            self.host,
            self.port if self.port else (443 if self.secure else 80),
            self.fullpath.rstrip("/"),
        )

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {
            "method": self.method,
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Append our headers into our parameters
        params.update({f"+{k}": v for k, v in self.headers.items()})

        # Append our GET params into our parameters
        params.update({f"-{k}": v for k, v in self.params.items()})

        # Append our payload extra's into our parameters
        params.update({f":{k}": v for k, v in self.payload_extras.items()})
        params.update({f":{k}": v for k, v in self.payload_overrides.items()})

        if self.attach_as != self.attach_as_default:
            # Provide Attach-As extension details
            params["attach-as"] = self.attach_as

        # Determine Authentication
        auth = ""
        if self.user and self.password:
            auth = "{user}:{password}@".format(
                user=NotifyForm.quote(self.user, safe=""),
                password=self.pprint(
                    self.password, privacy, mode=PrivacyMode.Secret, safe=""
                ),
            )
        elif self.user:
            auth = "{user}@".format(
                user=NotifyForm.quote(self.user, safe=""),
            )

        default_port = 443 if self.secure else 80
        return "{schema}://{auth}{hostname}{port}{fullpath}?{params}".format(
            schema=self.secure_protocol if self.secure else self.protocol,
            auth=auth,
            # never encode hostname since we're expecting it to be a valid one
            hostname=self.host,
            port=(
                ""
                if self.port is None or self.port == default_port
                else f":{self.port}"
            ),
            fullpath=(
                NotifyForm.quote(self.fullpath, safe="/")
                if self.fullpath
                else "/"
            ),
            params=NotifyForm.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # store any additional payload extra's defined
        results["payload"] = {
            NotifyForm.unquote(x): NotifyForm.unquote(y)
            for x, y in results["qsd:"].items()
        }

        # Add our headers that the user can potentially over-ride if they wish
        # to to our returned result set and tidy entries by unquoting them
        results["headers"] = {
            NotifyForm.unquote(x): NotifyForm.unquote(y)
            for x, y in results["qsd+"].items()
        }

        # Add our GET paramters in the event the user wants to pass these along
        results["params"] = {
            NotifyForm.unquote(x): NotifyForm.unquote(y)
            for x, y in results["qsd-"].items()
        }

        # Allow Attach-As Support which over-rides the name of the filename
        # posted with the form://
        # the default is file01, file02, file03, etc
        if "attach-as" in results["qsd"] and len(results["qsd"]["attach-as"]):
            results["attach_as"] = results["qsd"]["attach-as"]

        # Set method if not otherwise set
        if "method" in results["qsd"] and len(results["qsd"]["method"]):
            results["method"] = NotifyForm.unquote(results["qsd"]["method"])

        return results
