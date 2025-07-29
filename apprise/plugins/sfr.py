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

# For this to work correctly you need to have a valid SFR DMC service account
# to whicthe API password can be generated. A "space" is also necessary
# (space = a logical separation between clients), which will give you a
# specific spaceId
#
# Expected credentials looks a little like this:
# serviceId: 84920958892    - Random numbers
# servicePassword: XxXXxXXx - Random characters
# spaceId: 984348           - Random numbers
#
# 1. Visit https://www.sfr.fr/
#
# 2. Url will look like this
#    https://www.dmc.sfr-sh.fr/DmcWS/1.5.8/JsonService/<apiGroup>/<apicall>

import json

import requests

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import is_phone_no, parse_phone_no
from .base import NotifyBase


class NotifySFR(NotifyBase):
    """A wrapper for SFR French Telecom DMC API."""

    # The default descriptive name associated with the Notification
    service_name = _("Société Française du Radiotéléphone")

    # The services URL
    service_url = "https://www.sfr.fr/"

    # The default protocol
    protocol = "sfr"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_sfr"

    # SFR api
    notify_url = (
        "https://www.dmc.sfr-sh.fr/DmcWS/1.5.8/JsonService/"
        "MessagesUnitairesWS/addSingleCall"  # this is the actual api call
    )

    # The maximum length of the body
    body_maxlen = 160

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Define object templates
    templates = ("{schema}://{user}:{password}@{space_id}/{targets}",)

    # Define our tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "user": {
                "name": _("Service ID"),
                "type": "string",
                "required": True,
            },
            "password": {
                "name": _("Service Password"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "space_id": {
                "name": _("Space ID"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "target": {
                "name": _("Recipient Phone Number"),
                "type": "string",
                "regex": (r"^\+?[0-9\s)(+-]+$", "i"),
                "map_to": "targets",
            },
            "targets": {
                "name": _("Targets"),
                "type": "list:string",
                "required": True,
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "lang": {
                "name": _("Language"),
                "type": "string",
                "default": "fr_FR",
                "required": True,
            },
            "sender": {
                "name": _("Sender Name"),
                "type": "string",
                "required": True,
                "default": "",
            },
            "from": {"alias_of": "sender"},
            "media": {
                "name": _("Media Type"),
                "type": "string",
                "required": True,
                "default": "SMSUnicode",
                "values": ["SMS", "SMSLong", "SMSUnicode", "SMSUnicodeLong"],
            },
            "timeout": {
                "name": _("Timeout"),
                "type": "int",
                "default": 2880,
                "required": False,
            },
            "voice": {
                "name": _("TTS Voice"),
                "type": "string",
                "default": "claire08s",
                "values": ["claire08s", "laura8k"],
                "required": False,
            },
            "to": {
                "alias_of": "targets",
            },
        },
    )

    def __init__(
        self,
        space_id=None,
        targets=None,
        lang=None,
        sender=None,
        media=None,
        timeout=None,
        voice=None,
        **kwargs,
    ):
        """Initialize SFR Object."""
        super().__init__(**kwargs)

        if not (self.user and self.password):
            msg = (
                "A SFR user (serviceId) and password (servicePassword) "
                "combination was not provided."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        self.space_id = space_id
        if not self.space_id:
            msg = "A SFR Space ID is required."
            self.logger.warning(msg)
            raise TypeError(msg)

        self.voice = voice if voice else self.template_args["voice"]["default"]
        self.lang = lang if lang else self.template_args["lang"]["default"]
        self.media = media if media else self.template_args["media"]["default"]
        self.sender = (
            sender if sender else self.template_args["sender"]["default"]
        )

        # Set our Time to Live Flag
        self.timeout = self.template_args["timeout"]["default"]
        try:
            self.timeout = int(timeout)

        except (ValueError, TypeError):
            # set default timeout
            self.timeout = 2880
            pass

        # Parse our targets
        self.targets = []

        for target in parse_phone_no(targets):
            # Validate targets and drop bad ones:
            result = is_phone_no(target)
            if not result:
                self.logger.warning(
                    f"Dropped invalid phone # ({target}) specified.",
                )
                continue

            # store valid phone number
            self.targets.append(result["full"])

        if not self.targets:
            msg = (
                "No receiver phone number has been provided. Please "
                "provide as least one valid phone number."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        return

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform the SFR notification."""

        # error tracking (used for function return)
        has_error = False

        # Create a copy of the targets list
        targets = list(self.targets)

        # Construct the authentication JSON
        auth_payload = json.dumps({
            "serviceId": self.user,
            "servicePassword": self.password,
            "spaceId": self.space_id,
            "lang": self.lang,
        })

        base_payload = {
            # Can be 'SMS', 'SMSLong', 'SMSUnicode', or 'SMSUnicodeLong'
            "media": self.media,
            # Content of the message
            "textMsg": body,
            # Receiver's phone number (set below)
            "to": None,
            # Optional, default to ''
            "from": self.sender,
            # Optional, default 2880 minutes
            "timeout": self.timeout,
            # Optional, default to French voice
            "ttsVoice": self.voice,
        }

        while len(targets):
            # Get our target to notify
            target = targets.pop(0)

            # Prepare our target phone no
            base_payload["to"] = target

            # Always call throttle before any remote server i/o is made
            self.throttle()

            # Finalize our payload
            payload = {
                "authenticate": auth_payload,
                "messageUnitaire": json.dumps(base_payload, ensure_ascii=True),
            }

            # Some Debug Logging
            self.logger.debug(
                "SFR POST URL:"
                f" {self.notify_url} (cert_verify={self.verify_certificate})"
            )
            self.logger.debug(f"SFR Payload: {payload}")

            try:
                r = requests.post(
                    self.notify_url,
                    params=payload,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )

                try:
                    content = json.loads(r.content)

                except (AttributeError, TypeError, ValueError):
                    # ValueError = r.content is Unparsable
                    # TypeError = r.content is None
                    # AttributeError = r is None
                    content = {}

                # Check if the request was successfull
                if r.status_code not in (
                    requests.codes.ok,
                    requests.codes.no_content,
                ):
                    # We had a problem
                    status_str = NotifySFR.http_response_code_lookup(
                        r.status_code
                    )

                    self.logger.warning(
                        "Failed to send SFR notification to {}: "
                        "{}{}error={}.".format(
                            target,
                            status_str,
                            ", " if status_str else "",
                            r.status_code,
                        )
                    )

                    self.logger.debug(f"Response Details:\r\n{r.content}")

                    # Mark our failure
                    has_error = True
                    continue

                # SFR returns a code 200 even if the authentication fails
                # It then indicates in the content['success'] field the
                # Actual state of the transaction
                if not content.get("success", False):
                    self.logger.warning(
                        "SFR Notification to {} was not sent by the server: "
                        "server_error={}, fatal={}.".format(
                            target,
                            content.get("errorCode", "UNKNOWN"),
                            content.get("fatal", "True"),
                        )
                    )

                    # Mark our failure
                    has_error = True
                    continue

                self.logger.info(f"Sent SFR notification to {target}.")

            except requests.RequestException as e:
                self.logger.warning(
                    f"A Connection error occurred sending SFR:{target} "
                    "notification."
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
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.user,
            self.password,
            self.space_id,
        )

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""
        # Define any URL parameters
        params = {
            "from": self.sender,
            "timeout": str(self.timeout),
            "voice": self.voice,
            "lang": self.lang,
            "media": self.media,
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return "{schema}://{user}:{password}@{sid}/{targets}?{params}".format(
            schema=self.secure_protocol if self.secure else self.protocol,
            user=self.user,
            password=self.pprint(
                self.password,
                privacy,
                mode=PrivacyMode.Secret,
                safe="",
            ),
            sid=self.pprint(self.space_id, privacy, safe=""),
            targets="/".join(
                [NotifySFR.quote(x, safe="") for x in self.targets]
            ),
            params=self.urlencode(params),
        )

    def __len__(self):
        """Returns the number of targets associated with this notification."""
        return len(self.targets)

    @staticmethod
    def parse_url(url):
        """Parse the URL and return arguments required to initialize this
        plugin."""
        # NotifyBase.parse_url() will make the initial parsing of your string
        # very easy to use. It will tokenize the entire URL for you.  The
        # tokens are then passed into your __init__() function you defined to
        # generate you're object

        results = NotifyBase.parse_url(url, verify_host=False)

        if not results:
            # We're done early as we couldn't load the results
            return results

        # Extract user and password
        results["space_id"] = results.get("host")
        results["targets"] = NotifySFR.split_path(results["fullpath"])

        # Extract additional parameters
        qsd = results.get("qsd", {})
        results["sender"] = NotifySFR.unquote(
            qsd.get("sender", qsd.get("from"))
        )
        results["timeout"] = NotifySFR.unquote(qsd.get("timeout"))
        results["voice"] = NotifySFR.unquote(qsd.get("voice"))
        results["lang"] = NotifySFR.unquote(qsd.get("lang"))
        results["media"] = NotifySFR.unquote(qsd.get("media"))

        # Support the 'to' variable so that we can support rooms this way too
        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifySFR.parse_phone_no(
                results["qsd"]["to"]
            )

        return results
