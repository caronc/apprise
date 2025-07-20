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

# One Signal requires that you've signed up with the service and
# generated yourself an API Key and APP ID.

# Sources:
#  - https://documentation.onesignal.com/docs/accounts-and-keys
#  - https://documentation.onesignal.com/reference/create-notification

from itertools import chain
from json import dumps

import requests

from ..common import NotifyImageSize, NotifyType
from ..locale import gettext_lazy as _
from ..utils.base64 import decode_b64_dict, encode_b64_dict
from ..utils.parse import is_email, parse_bool, parse_list, validate_regex
from .base import NotifyBase


class OneSignalCategory:
    """We define the different category types that we can notify via
    OneSignal."""

    PLAYER = "include_player_ids"
    EMAIL = "include_email_tokens"
    USER = "include_external_user_ids"
    SEGMENT = "included_segments"


ONESIGNAL_CATEGORIES = (
    OneSignalCategory.PLAYER,
    OneSignalCategory.EMAIL,
    OneSignalCategory.USER,
    OneSignalCategory.SEGMENT,
)


class NotifyOneSignal(NotifyBase):
    """A wrapper for OneSignal Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "OneSignal"

    # The services URL
    service_url = "https://onesignal.com"

    # The default protocol
    secure_protocol = "onesignal"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_onesignal"

    # Notification
    notify_url = "https://api.onesignal.com/notifications"

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_72

    # The maximum allowable batch sizes per message
    default_batch_size = 2000

    # Define object templates
    templates = (
        "{schema}://{app}@{apikey}/{targets}",
        "{schema}://{template}:{app}@{apikey}/{targets}",
    )

    # Define our template
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            # The App_ID is a UUID
            # such as: 8250eaf6-1a58-489e-b136-7c74a864b434
            "app": {
                "name": _("App ID"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "template": {
                "name": _("Template"),
                "type": "string",
                "private": True,
            },
            "apikey": {
                "name": _("API Key"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "target_player": {
                "name": _("Target Player ID"),
                "type": "string",
                "map_to": "targets",
            },
            "target_email": {
                "name": _("Target Email"),
                "type": "string",
                "map_to": "targets",
            },
            "target_user": {
                "name": _("Target User"),
                "type": "string",
                "prefix": "@",
                "map_to": "targets",
            },
            "target_segment": {
                "name": _("Include Segment"),
                "type": "string",
                "prefix": "#",
                "map_to": "targets",
            },
            "targets": {
                "name": _("Targets"),
                "type": "list:string",
                "required": True,
            },
        },
    )

    template_args = dict(
        NotifyBase.template_args,
        **{
            "to": {
                "alias_of": "targets",
            },
            "image": {
                "name": _("Include Image"),
                "type": "bool",
                "default": True,
                "map_to": "include_image",
            },
            "batch": {
                "name": _("Batch Mode"),
                "type": "bool",
                "default": False,
            },
            "contents": {
                "name": _("Enable Contents"),
                "type": "bool",
                "default": True,
                "map_to": "use_contents",
            },
            "decode": {
                "name": _("Decode Template Args"),
                "type": "bool",
                "default": False,
                "map_to": "decode_tpl_args",
            },
            "template": {
                "alias_of": "template",
            },
            "subtitle": {
                "name": _("Subtitle"),
                "type": "string",
            },
            "language": {
                "name": _("Language"),
                "type": "string",
                "default": "en",
            },
        },
    )

    # Define our token control
    template_kwargs = {
        "custom": {
            "name": _("Custom Data"),
            "prefix": ":",
        },
        "postback": {
            "name": _("Postback Data"),
            "prefix": "+",
        },
    }

    def __init__(
        self,
        app,
        apikey,
        targets=None,
        include_image=True,
        template=None,
        subtitle=None,
        language=None,
        batch=None,
        use_contents=None,
        decode_tpl_args=None,
        custom=None,
        postback=None,
        **kwargs,
    ):
        """Initialize OneSignal."""
        super().__init__(**kwargs)

        # The apikey associated with the account
        self.apikey = validate_regex(apikey)
        if not self.apikey:
            msg = f"An invalid OneSignal API key ({apikey}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # The App ID associated with the account
        self.app = validate_regex(app)
        if not self.app:
            msg = f"An invalid OneSignal Application ID ({app}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Prepare Batch Mode Flag
        self.batch_size = (
            self.default_batch_size
            if (
                batch
                if batch is not None
                else self.template_args["batch"]["default"]
            )
            else 1
        )

        # Prepare Use Contents Flag
        self.use_contents = bool(
            use_contents
            if use_contents is not None
            else self.template_args["contents"]["default"]
        )

        # Prepare Decode Template Arguments Flag
        self.decode_tpl_args = bool(
            decode_tpl_args
            if decode_tpl_args is not None
            else self.template_args["decode"]["default"]
        )

        # Place a thumbnail image inline with the message body
        self.include_image = include_image

        # Our Assorted Types of Targets
        self.targets = {
            OneSignalCategory.PLAYER: [],
            OneSignalCategory.EMAIL: [],
            OneSignalCategory.USER: [],
            OneSignalCategory.SEGMENT: [],
        }

        # Assign our template (if defined)
        self.template_id = template

        # Assign our subtitle (if defined)
        self.subtitle = subtitle

        # Our Language
        self.language = (
            language.strip().lower()[0:2]
            if language
            else NotifyOneSignal.template_args["language"]["default"]
        )

        if not self.language or len(self.language) != 2:
            msg = f"An invalid OneSignal Language ({language}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Sort our targets
        for _target in parse_list(targets):
            target = _target.strip()
            if len(target) < 2:
                self.logger.debug(f"Ignoring OneSignal Entry: {target}")
                continue

            if target.startswith(
                NotifyOneSignal.template_tokens["target_user"]["prefix"]
            ):

                self.targets[OneSignalCategory.USER].append(target)
                self.logger.debug(
                    "Detected OneSignal UserID:"
                    f" {self.targets[OneSignalCategory.USER][-1]}"
                )
                continue

            if target.startswith(
                NotifyOneSignal.template_tokens["target_segment"]["prefix"]
            ):

                self.targets[OneSignalCategory.SEGMENT].append(target)
                self.logger.debug(
                    "Detected OneSignal Include Segment:"
                    f" {self.targets[OneSignalCategory.SEGMENT][-1]}"
                )
                continue

            result = is_email(target)
            if result:
                self.targets[OneSignalCategory.EMAIL].append(
                    result["full_email"]
                )
                self.logger.debug(
                    "Detected OneSignal Email:"
                    f" {self.targets[OneSignalCategory.EMAIL][-1]}"
                )

            else:
                # Add element as Player ID
                self.targets[OneSignalCategory.PLAYER].append(target)
                self.logger.debug(
                    "Detected OneSignal Player ID:"
                    f" {self.targets[OneSignalCategory.PLAYER][-1]}"
                )

        # Custom Data
        self.custom_data = {}
        if custom and isinstance(custom, dict):
            if self.decode_tpl_args:
                custom = decode_b64_dict(custom)

            self.custom_data.update(custom)

        elif custom:
            msg = (
                "The specified OneSignal Custom Data "
                f"({custom}) are not identified as a dictionary."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # Postback Data
        self.postback_data = {}
        if postback and isinstance(postback, dict):
            self.postback_data.update(postback)

        elif postback:
            msg = (
                "The specified OneSignal Postback Data "
                f"({postback}) are not identified as a dictionary."
            )
            self.logger.warning(msg)
            raise TypeError(msg)
        return

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform OneSignal Notification."""

        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Basic {self.apikey}",
        }

        has_error = False
        sent_count = 0

        payload = {
            "app_id": self.app,
            "contents": {
                self.language: body,
            },
            # Sending true wakes your app from background to run custom native
            # code (Apple interprets this as content-available=1).
            # Note: Not applicable if the app is in the "force-quit" state
            #      (i.e app was swiped away). Omit the contents field to
            #      prevent displaying a visible notification.
            "content_available": True,
        }

        if self.template_id:
            # Store template information
            payload["template_id"] = self.template_id

            if not self.use_contents:
                # Only if a template is defined can contents be removed
                del payload["contents"]

        # Set our data if defined
        if self.custom_data:
            payload.update({
                "custom_data": self.custom_data,
            })

        # Set our postback data if defined
        if self.postback_data:
            payload.update({
                "data": self.postback_data,
            })

        if title:
            # Display our title if defined
            payload.update(
                {
                    "headings": {
                        self.language: title,
                    }
                }
            )

        if self.subtitle:
            payload.update({
                "subtitle": {
                    self.language: self.subtitle,
                },
            })

        # Acquire our large_icon image URL (if set)
        image_url = (
            None if not self.include_image else self.image_url(notify_type)
        )
        if image_url:
            payload["large_icon"] = image_url

        # Acquire our small_icon image URL (if set)
        image_url = (
            None
            if not self.include_image
            else self.image_url(notify_type, image_size=NotifyImageSize.XY_32)
        )
        if image_url:
            payload["small_icon"] = image_url

        for category in ONESIGNAL_CATEGORIES:
            # Create a pointer to our list of targets for specified category
            targets = self.targets[category]
            for index in range(0, len(targets), self.batch_size):
                payload[category] = targets[index : index + self.batch_size]

                # Track our sent count
                sent_count += len(payload[category])

                self.logger.debug(
                    "OneSignal POST URL:"
                    f" {self.notify_url} "
                    f"(cert_verify={self.verify_certificate!r})"
                )
                self.logger.debug(f"OneSignal Payload: {payload!s}")

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
                        requests.codes.no_content,
                    ):
                        # We had a problem
                        status_str = NotifyOneSignal.http_response_code_lookup(
                            r.status_code
                        )

                        self.logger.warning(
                            "Failed to send OneSignal notification: "
                            "{}{}error={}.".format(
                                status_str,
                                ", " if status_str else "",
                                r.status_code,
                            )
                        )

                        self.logger.debug("Response Details:\r\n%s", r.content)

                        has_error = True

                    else:
                        self.logger.info("Sent OneSignal notification.")

                except requests.RequestException as e:
                    self.logger.warning(
                        "A Connection error occurred sending OneSignal "
                        "notification."
                    )
                    self.logger.debug("Socket Exception: %s", str(e))

                    has_error = True

        if not sent_count:
            # There is no one to notify; we need to capture this and not
            # return a valid
            self.logger.warning("There are no OneSignal targets to notify")
            return False

        return not has_error

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (
            self.secure_protocol,
            self.template_id,
            self.app,
            self.apikey,
        )

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {
            "image": "yes" if self.include_image else "no",
            "batch": "yes" if self.batch_size > 1 else "no",
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        custom_data, needs_decoding = encode_b64_dict(self.custom_data)
        # custom_data, needs_decoding = self.custom_data, False
        # Save our template data
        params.update({f":{k}": v for k, v in custom_data.items()})

        # Save our postback data
        params.update({f"+{k}": v for k, v in self.postback_data.items()})

        if self.use_contents != self.template_args["contents"]["default"]:
            params["contents"] = "yes" if self.use_contents else "no"

        if (
            self.decode_tpl_args != self.template_args["decode"]["default"]
            or needs_decoding
        ):
            params["decode"] = (
                "yes" if (self.decode_tpl_args or needs_decoding) else "no"
            )

        return "{schema}://{tp_id}{app}@{apikey}/{targets}?{params}".format(
            schema=self.secure_protocol,
            tp_id=(
                "{}:".format(self.pprint(self.template_id, privacy, safe=""))
                if self.template_id
                else ""
            ),
            app=self.pprint(self.app, privacy, safe=""),
            apikey=self.pprint(self.apikey, privacy, safe=""),
            targets="/".join(
                chain(
                    [
                        NotifyOneSignal.quote(x)
                        for x in self.targets[OneSignalCategory.PLAYER]
                    ],
                    [
                        NotifyOneSignal.quote(x)
                        for x in self.targets[OneSignalCategory.EMAIL]
                    ],
                    [
                        NotifyOneSignal.quote(
                            "{}{}".format(
                                NotifyOneSignal.template_tokens["target_user"][
                                    "prefix"
                                ],
                                x,
                            ),
                            safe="",
                        )
                        for x in self.targets[OneSignalCategory.USER]
                    ],
                    [
                        NotifyOneSignal.quote(
                            "{}{}".format(
                                NotifyOneSignal.template_tokens[
                                    "target_segment"
                                ]["prefix"],
                                x,
                            ),
                            safe="",
                        )
                        for x in self.targets[OneSignalCategory.SEGMENT]
                    ],
                )
            ),
            params=NotifyOneSignal.urlencode(params),
        )

    def __len__(self):
        """Returns the number of targets associated with this notification."""
        #
        # Factor batch into calculation
        #
        if self.batch_size > 1:
            # Batches can only be sent by group (you can't combine groups into
            # a single batch)
            total_targets = 0
            for _k, m in self.targets.items():
                targets = len(m)
                total_targets += int(targets / self.batch_size) + (
                    1 if targets % self.batch_size else 0
                )
            return total_targets

        # Normal batch count; just count the targets
        return sum([len(m) for _, m in self.targets.items()])

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        if not results.get("password"):
            # The APP ID identifier associated with the account
            results["app"] = NotifyOneSignal.unquote(results["user"])

        else:
            # The APP ID identifier associated with the account
            results["app"] = NotifyOneSignal.unquote(results["password"])
            # The Template ID
            results["template"] = NotifyOneSignal.unquote(results["user"])

        # Get Image Boolean (if set)
        results["include_image"] = parse_bool(
            results["qsd"].get(
                "image", NotifyOneSignal.template_args["image"]["default"]
            )
        )

        # Get Batch Boolean (if set)
        results["batch"] = parse_bool(
            results["qsd"].get(
                "batch", NotifyOneSignal.template_args["batch"]["default"]
            )
        )

        # Get Use Contents Boolean (if set)
        results["use_contents"] = parse_bool(
            results["qsd"].get(
                "contents",
                NotifyOneSignal.template_args["contents"]["default"],
            )
        )

        # Get Use Contents Boolean (if set)
        results["decode_tpl_args"] = parse_bool(
            results["qsd"].get(
                "decode", NotifyOneSignal.template_args["decode"]["default"]
            )
        )

        # The API Key is stored in the hostname
        results["apikey"] = NotifyOneSignal.unquote(results["host"])

        # Get our Targets
        results["targets"] = NotifyOneSignal.split_path(results["fullpath"])

        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifyOneSignal.parse_list(
                results["qsd"]["to"]
            )

        if "app" in results["qsd"] and len(results["qsd"]["app"]):
            results["app"] = NotifyOneSignal.unquote(results["qsd"]["app"])

        if "apikey" in results["qsd"] and len(results["qsd"]["apikey"]):
            results["apikey"] = NotifyOneSignal.unquote(
                results["qsd"]["apikey"]
            )

        if "template" in results["qsd"] and len(results["qsd"]["template"]):
            results["template"] = NotifyOneSignal.unquote(
                results["qsd"]["template"]
            )

        if "subtitle" in results["qsd"] and len(results["qsd"]["subtitle"]):
            results["subtitle"] = NotifyOneSignal.unquote(
                results["qsd"]["subtitle"]
            )

        if "lang" in results["qsd"] and len(results["qsd"]["lang"]):
            results["language"] = NotifyOneSignal.unquote(
                results["qsd"]["lang"]
            )

        # Store our custom data
        results["custom"] = results["qsd:"]

        # Store our postback data
        results["postback"] = results["qsd+"]

        return results
