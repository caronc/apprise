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
#
# API Source:
#   https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages
#
# The setup is split across two Meta portals:
#  - https://business.facebook.com  (Business Manager — System Users & tokens)
#  - https://developers.facebook.com (Developer Dashboard — App & Phone ID)
#
# 1. Create a Meta Business Manager account at https://business.facebook.com
#    (or use an existing one).  WhatsApp Business Accounts (WABAs) and System
#    Users live here.
# 2. Create a Meta Developer account at https://developers.facebook.com and
#    create a new App.  Add WhatsApp as a product.  If prompted, select the
#    "Business" app type and choose "Connect to Customers (WhatsApp)" as the
#    use case (you may need to click "Customise Use Case" on the home page).
# 3. In Business Manager, go to Settings > Users > System Users, create a
#    System User (Admin or Employee role), click "Add Assets", assign your
#    WhatsApp app, and grant the whatsapp_business_messaging permission.
#    Then click "Generate Token" and copy it — this is your permanent token.
# 4. Switch back to the Developer Dashboard, open your app, then go to
#    WhatsApp > API Setup (or Getting Started) to find your From Phone Number
#    ID.  This is NOT your actual phone number; it is a separate numeric ID
#    (roughly 14 digits) assigned by Meta to the sender number.
# 5. During sandbox testing, verify any recipient phone number through Meta's
#    interface.  For production, your business must be verified and placed on
#    the appropriate messaging tier.

from json import dumps, loads
import re

import requests

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import (
    is_phone_no,
    parse_phone_no,
    validate_regex,
)
from .base import NotifyBase

# Matches the numeric-only portion of a WhatsApp Cloud API group ID after any
# '#' prefix and '@g.us' JID suffix have been stripped.  E.164 phone numbers
# are capped at 15 digits; group IDs are 18-20 digits, so requiring 16+ gives
# an unambiguous separation with no overlap.
IS_GROUP_ID = re.compile(r"^[0-9]{16,}$")


class NotifyWhatsApp(NotifyBase):
    """A wrapper for WhatsApp Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "WhatsApp"

    # The services URL
    service_url = (
        "https://developers.facebook.com/docs/whatsapp/cloud-api/get-started"
    )

    # All notification requests are secure
    secure_protocol = "whatsapp"

    # Allow 300 requests per minute.
    # 60/300 = 0.2
    request_rate_per_sec = 0.20

    # Facebook Graph version; bump this when Meta deprecates the current one.
    # Release schedule: https://developers.facebook.com/docs/graph-api/changelog
    fb_graph_version = "v21.0"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/whatsapp/"

    # WhatsApp Message Notification URL
    notify_url = "https://graph.facebook.com/{fb_ver}/{phone_id}/messages"

    # The maximum length of the body
    body_maxlen = 1024

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Define object templates
    templates = (
        "{schema}://{token}@{from_phone_id}/{targets}",
        "{schema}://{template}:{token}@{from_phone_id}/{targets}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "token": {
                "name": _("Access Token"),
                "type": "string",
                "private": True,
                "required": True,
                "regex": (r"^[a-z0-9]+$", "i"),
            },
            "template": {
                "name": _("Template Name"),
                "type": "string",
                "required": False,
                "regex": (r"^[^\s]+$", "i"),
            },
            "from_phone_id": {
                "name": _("From Phone ID"),
                "type": "string",
                "private": True,
                "required": True,
                "regex": (r"^[0-9]+$", "i"),
            },
            "language": {
                "name": _("Language"),
                "type": "string",
                "default": "en_US",
                "regex": (r"^[^0-9\s]+$", "i"),
            },
            "target_phone": {
                "name": _("Target Phone No"),
                "type": "string",
                "prefix": "+",
                "regex": (r"^[0-9\s)(+-]+$", "i"),
                "map_to": "targets",
            },
            # WhatsApp group IDs are purely numeric and 16+ digits long —
            # safely above the 15-digit E.164 phone number maximum.
            # The '#' prefix in the Apprise URL is recommended for clarity;
            # bare 16+ digit strings are also accepted.
            # The '@g.us' API JID suffix is added automatically at send time.
            "target_group": {
                "name": _("Target Group ID"),
                "type": "string",
                "prefix": "#",
                "regex": (r"^[0-9]{16,}$", "i"),
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
            "from": {
                "alias_of": "from_phone_id",
            },
            "token": {
                "alias_of": "token",
            },
            "template": {
                "alias_of": "template",
            },
            "lang": {
                "alias_of": "language",
            },
            "to": {
                "alias_of": "targets",
            },
        },
    )

    # Our supported mappings and component keys
    component_key_re = re.compile(
        r"(?P<key>((?P<id>[1-9][0-9]*)|(?P<map>body|type)))", re.IGNORECASE
    )

    # Define any kwargs we're using
    template_kwargs = {
        "template_mapping": {
            "name": _("Template Mapping"),
            "prefix": ":",
        },
    }

    def __init__(
        self,
        token,
        from_phone_id,
        template=None,
        targets=None,
        language=None,
        template_mapping=None,
        **kwargs,
    ):
        """Initialize WhatsApp Object."""
        super().__init__(**kwargs)

        # The Access Token associated with the account
        self.token = validate_regex(
            token, *self.template_tokens["token"]["regex"]
        )
        if not self.token:
            msg = f"An invalid WhatsApp Access Token ({token}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # The From Phone ID associated with the account
        self.from_phone_id = validate_regex(
            from_phone_id, *self.template_tokens["from_phone_id"]["regex"]
        )
        if not self.from_phone_id:
            msg = (
                "An invalid WhatsApp From Phone ID "
                f"({from_phone_id}) was specified."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # The template to associate with the message
        if template:
            self.template = validate_regex(
                template, *self.template_tokens["template"]["regex"]
            )
            if not self.template:
                msg = (
                    "An invalid WhatsApp Template Name "
                    f"({template}) was specified."
                )
                self.logger.warning(msg)
                raise TypeError(msg)

            # The Template language Code to use
            if language:
                self.language = validate_regex(
                    language, *self.template_tokens["language"]["regex"]
                )
                if not self.language:
                    msg = (
                        "An invalid WhatsApp Template Language Code "
                        f"({language}) was specified."
                    )
                    self.logger.warning(msg)
                    raise TypeError(msg)
            else:
                self.language = self.template_tokens["language"]["default"]
        else:
            #
            # Message Mode
            #
            self.template = None

        # Parse our targets (phone numbers and/or group IDs).
        #
        # parse_phone_no does the heavy lifting: it handles formatted phone
        # strings ("+1 (555) 987-6543", dashes, spaces, etc.) and, with the
        # default store_unparseable=True, passes through anything it cannot
        # identify as a phone so we can inspect it below.
        # A '#' prefix on a group ID is silently stripped by the phone regex
        # (the digits still match); a '@g.us' JID suffix causes the whole
        # token to be kept as-is (the '@' breaks the phone pattern).
        #
        # For each token after parse_phone_no:
        #   is_phone_no() succeeds -> valid phone, stored as E.164 '+XXX'
        #   is_phone_no() fails    -> strip '@g.us', run IS_GROUP_ID:
        #                            16+ pure digits -> group ('#digits')
        #                            anything else   -> warn and drop
        self.targets = []

        for target in parse_phone_no(targets):
            # Validate as a phone number first
            result = is_phone_no(target)
            if result:
                # Valid phone number; store in E.164 format
                self.targets.append("+{}".format(result["full"]))
                continue

            # Not a valid phone — check whether it is a group ID.
            # Strip both the '#' prefix (retained when parse_phone_no uses
            # its unparseable-store path rather than the phone regex) and the
            # '@g.us' JID suffix (the native Meta API group ID format).
            gid = (
                re.sub(r"@g\.us$", "", target, flags=re.I).strip().lstrip("#")
            )
            if IS_GROUP_ID.match(gid):
                # Store with '#' prefix; '@g.us' is re-added at send time
                self.targets.append(f"#{gid}")
                continue

            # Genuinely invalid — warn and drop
            self.logger.warning(
                f"Dropped invalid WhatsApp target ({target}) specified.",
            )

        self.template_mapping = {}
        if template_mapping:
            # Store our extra payload entries
            self.template_mapping.update(template_mapping)

        # Validate Mapping and prepare Components
        self.components = {}
        self.component_keys = []
        for key, val in self.template_mapping.items():
            matched = self.component_key_re.match(key)
            if not matched:
                msg = (
                    f"An invalid Template Component ID ({key}) was specified."
                )
                self.logger.warning(msg)
                raise TypeError(msg)

            if matched.group("id"):
                #
                # Manual Component Assigment (by id)
                #
                index = matched.group("id")
                map_to = {
                    "type": "text",
                    "text": val,
                }

            else:  # matched.group('map')
                map_to = matched.group("map").lower()
                matched = self.component_key_re.match(val)
                if not (matched and matched.group("id")):
                    msg = (
                        "An invalid Template Component Mapping "
                        f"(:{key}={val}) was specified."
                    )
                    self.logger.warning(msg)
                    raise TypeError(msg)
                index = matched.group("id")

            if index in self.components:
                msg = (
                    "The Template Component index "
                    f"({key}) was already assigned."
                )
                self.logger.warning(msg)
                raise TypeError(msg)

            self.components[index] = map_to
            self.component_keys = self.components.keys()
            # Adjust sorting and assume that the user put the order correctly;
            # if not Facebook just won't be very happy and will reject the
            # message
            sorted(self.component_keys)

        return

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform WhatsApp Notification."""

        if not self.targets:
            self.logger.warning(
                "There are no valid WhatsApp targets to notify."
            )
            return False

        # error tracking (used for function return)
        has_error = False

        # Prepare our URL
        url = self.notify_url.format(
            fb_ver=self.fb_graph_version,
            phone_id=self.from_phone_id,
        )

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }

        payload = {
            "messaging_product": "whatsapp",
            # 'to' and 'recipient_type' are set per-target in the loop below
            "to": None,
        }

        if not self.template:
            #
            # Send Message
            #
            payload.update(
                {
                    # recipient_type is overridden per-target below
                    "recipient_type": "individual",
                    "type": "text",
                    "text": {"body": body},
                }
            )

        else:
            #
            # Send Template
            #
            payload.update(
                {
                    "type": "template",
                    "template": {
                        "name": self.template,
                        "language": {"code": self.language},
                    },
                }
            )

            if self.components:
                payload["template"]["components"] = [
                    {
                        "type": "body",
                        "parameters": [],
                    }
                ]
                for key in self.component_keys:
                    if isinstance(self.components[key], dict):
                        # Manual Assignment
                        payload["template"]["components"][0][
                            "parameters"
                        ].append(self.components[key])
                        continue

                    # Mapping of body and/or notify type
                    payload["template"]["components"][0]["parameters"].append(
                        {
                            "type": "text",
                            "text": (
                                body
                                if self.components[key] == "body"
                                else notify_type.value
                            ),
                        }
                    )

        # Create a copy of the targets list
        targets = list(self.targets)

        while len(targets):
            # Get our target to notify
            target = targets.pop(0)

            # Group targets are stored with a '#' prefix; phone numbers
            # are stored in E.164 format ('+' prefix).
            if target.startswith("#"):
                # Reconstruct the full Meta API group ID (digits + @g.us)
                payload["to"] = "{}@g.us".format(target[1:])
                payload["recipient_type"] = "group"
            else:
                # Individual phone number
                payload["to"] = target
                payload["recipient_type"] = "individual"

            # Some Debug Logging
            self.logger.debug(
                "WhatsApp POST URL:"
                f" {url} (cert_verify={self.verify_certificate})"
            )
            self.logger.debug(f"WhatsApp Payload: {payload}")

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

                if r.status_code not in (
                    requests.codes.created,
                    requests.codes.ok,
                ):
                    # We had a problem
                    status_str = NotifyBase.http_response_code_lookup(
                        r.status_code
                    )

                    # set up our status code to use
                    status_code = r.status_code

                    try:
                        # Update our status response if we can
                        json_response = loads(r.content)
                        status_code = json_response["error"].get(
                            "code", status_code
                        )
                        status_str = json_response["error"].get(
                            "message", status_str
                        )

                    except (AttributeError, TypeError, ValueError, KeyError):
                        # KeyError = r.content is parseable but does not
                        #            contain 'error'
                        # ValueError = r.content is Unparsable
                        # TypeError = r.content is None
                        # AttributeError = r is None

                        # We could not parse JSON response.
                        # We will just use the status we already have.
                        pass

                    self.logger.warning(
                        "Failed to send WhatsApp notification to {}: "
                        "{}{}error={}.".format(
                            target,
                            status_str,
                            ", " if status_str else "",
                            status_code,
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
                        f"Sent WhatsApp notification to {target}."
                    )

            except requests.RequestException as e:
                self.logger.warning(
                    f"A Connection error occurred sending WhatsApp:{target} "
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
        return (self.secure_protocol, self.from_phone_id, self.token)

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {}
        if self.template:
            # Add language to our URL
            params["lang"] = self.language

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Payload body extras prefixed with a ':' sign
        # Append our payload extras into our parameters
        params.update({f":{k}": v for k, v in self.template_mapping.items()})

        return "{schema}://{template}{token}@{from_id}/{targets}/?{params}".format(
            schema=self.secure_protocol,
            from_id=self.pprint(self.from_phone_id, privacy, safe=""),
            token=self.pprint(self.token, privacy, safe=""),
            template=(
                ""
                if not self.template
                else "{}:".format(NotifyWhatsApp.quote(self.template, safe=""))
            ),
            targets="/".join(
                [NotifyWhatsApp.quote(x, safe="") for x in self.targets]
            ),
            params=NotifyWhatsApp.urlencode(params),
        )

    def __len__(self):
        """Returns the number of targets associated with this notification."""
        targets = len(self.targets)
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
        results["targets"] = NotifyWhatsApp.split_path(results["fullpath"])

        # The hostname is our From Phone ID
        results["from_phone_id"] = NotifyWhatsApp.unquote(results["host"])

        # Determine if we have a Template, otherwise load our token
        if results["password"]:
            #
            # Template Mode
            #
            results["template"] = NotifyWhatsApp.unquote(results["user"])
            results["token"] = NotifyWhatsApp.unquote(results["password"])

        else:
            #
            # Message Mode
            #
            results["token"] = NotifyWhatsApp.unquote(results["user"])

        # Access token
        if "token" in results["qsd"] and len(results["qsd"]["token"]):
            # Extract the account sid from an argument
            results["token"] = NotifyWhatsApp.unquote(results["qsd"]["token"])

        # Template
        if "template" in results["qsd"] and len(results["qsd"]["template"]):
            results["template"] = results["qsd"]["template"]

        # Template Language
        if "lang" in results["qsd"] and len(results["qsd"]["lang"]):
            results["language"] = results["qsd"]["lang"]

        # Support the 'from'  and 'source' variable so that we can support
        # targets this way too.
        # The 'from' makes it easier to use yaml configuration
        if "from" in results["qsd"] and len(results["qsd"]["from"]):
            results["from_phone_id"] = NotifyWhatsApp.unquote(
                results["qsd"]["from"]
            )
        if "source" in results["qsd"] and len(results["qsd"]["source"]):
            results["from_phone_id"] = NotifyWhatsApp.unquote(
                results["qsd"]["source"]
            )

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifyWhatsApp.parse_phone_no(
                results["qsd"]["to"]
            )

        # store any additional payload extra's defined
        results["template_mapping"] = {
            NotifyWhatsApp.unquote(x): NotifyWhatsApp.unquote(y)
            for x, y in results["qsd:"].items()
        }

        return results
