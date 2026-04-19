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
# API: https://dot.mindreset.tech/docs/service/open/text_api
#      https://dot.mindreset.tech/docs/service/open/image_api
#
# New API endpoints (v2):
#   - Text API: /api/authV2/open/device/:deviceId/text
#   - Image API: /api/authV2/open/device/:deviceId/image
#
# Note: Old endpoints (/api/open/text and /api/open/image) are deprecated
# and will be removed in the future. Requests are automatically forwarded
# to the new endpoints.
#
# Text API Fields:
#   - refreshNow (bool, optional, default true): controls display timing.
#   - title (string, optional): title text shown on screen.
#   - message (string, optional): body text shown on screen.
#   - signature (string, optional): footer/signature text.
#   - icon (string, optional): base64 PNG icon (40px x 40px).
#   - link (string, optional): tap-to-interact target URL.
#   - taskKey (string, optional): specify which text API content to update.
#
# Image API Fields:
#   - refreshNow (bool, optional, default true): controls display timing.
#   - image (string, required): base64 PNG image (296px x 152px).
#   - link (string, optional): tap-to-interact target URL.
#   - border (number, optional, default 0): 0=white, 1=black frame.
#   - ditherType (string, optional, default DIFFUSION): dithering mode.
#   - ditherKernel (string, optional, default FLOYD_STEINBERG):
#     dithering kernel.
#   - taskKey (string, optional): specify which image API content to update.
#
# Mode selection:
#   - text (default): smart dual-send mode.  Body/title go to the Text API;
#     image= param or an attachment goes to the Image API.  When both are
#     present, text is dispatched first, then image.  If only one is
#     available, only that API is called.
#   - image: only the Image API is called; body and title are ignored.
#
#   Providing image= in the URL without an explicit mode= leaves the mode
#   as the default (text), which will send the image alongside any text.

from contextlib import suppress
import json
import logging

import requests

from ..common import NotifyImageSize, NotifyType
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import parse_bool
from ..utils.sanitize import sanitize_payload
from .base import NotifyBase

# Supported Dither Types
DOT_DITHER_TYPES = (
    "DIFFUSION",
    "ORDERED",
    "NONE",
)

# Supported Dither Kernels
DOT_DITHER_KERNELS = (
    "THRESHOLD",
    "ATKINSON",
    "BURKES",
    "FLOYD_STEINBERG",
    "SIERRA2",
    "STUCKI",
    "JARVIS_JUDICE_NINKE",
    "DIFFUSION_ROW",
    "DIFFUSION_COLUMN",
    "DIFFUSION_2D",
)

# Supported API modes; first entry is the default
DOT_MODES = ("text", "image")


class NotifyDot(NotifyBase):
    """A wrapper for Dot. Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Dot."

    # The services URL
    service_url = "https://dot.mindreset.tech"

    # All notification requests are secure
    secure_protocol = "dot"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/dot/"

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_128

    # Support Attachments
    attachment_support = True

    # Define object templates
    templates = ("{schema}://{apikey}@{device_id}/",)

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "apikey": {
                "name": _("API Key"),
                "type": "string",
                "required": True,
                "private": True,
            },
            "device_id": {
                "name": _("Device Serial Number"),
                "type": "string",
                "required": True,
                "map_to": "device_id",
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "mode": {
                "name": _("API Mode"),
                "type": "choice:string",
                "values": DOT_MODES,
                "default": DOT_MODES[0],
            },
            "refresh": {
                "name": _("Refresh Now"),
                "type": "bool",
                "default": True,
                "map_to": "refresh_now",
            },
            "signature": {
                "name": _("Text Signature"),
                "type": "string",
            },
            "icon": {
                "name": _("Icon Base64 (Text API)"),
                "type": "string",
            },
            "image": {
                "name": _("Image Base64 (Image API)"),
                "type": "string",
                "map_to": "image_data",
            },
            "link": {
                "name": _("Link"),
                "type": "string",
            },
            "border": {
                "name": _("Border"),
                "type": "int",
                "min": 0,
                "max": 1,
                "default": 0,
            },
            "dither_type": {
                "name": _("Dither Type"),
                "type": "choice:string",
                "values": DOT_DITHER_TYPES,
                "default": "DIFFUSION",
            },
            "dither_kernel": {
                "name": _("Dither Kernel"),
                "type": "choice:string",
                "values": DOT_DITHER_KERNELS,
                "default": "FLOYD_STEINBERG",
            },
            "task_key": {
                "name": _("Task Key"),
                "type": "string",
            },
        },
    )

    def __init__(
        self,
        apikey=None,
        device_id=None,
        mode=DOT_MODES[0],
        refresh_now=None,
        signature=None,
        icon=None,
        link=None,
        border=None,
        dither_type=None,
        dither_kernel=None,
        image_data=None,
        task_key=None,
        **kwargs,
    ):
        """Initialize Notify Dot Object."""
        super().__init__(**kwargs)

        # API Key (from user)
        self.apikey = apikey

        # Device ID tracks the Dot hardware serial.
        self.device_id = device_id

        # Refresh Now flag: True shows content immediately (default).
        self.refresh_now = (
            parse_bool(
                refresh_now,
                self.template_args["refresh"]["default"],
            )
            if refresh_now is not None
            else self.template_args["refresh"]["default"]
        )

        # API mode
        self.mode = (
            mode.lower()
            if isinstance(mode, str) and mode.lower() in DOT_MODES
            else DOT_MODES[0]
        )
        if not isinstance(mode, str) or mode.lower() not in DOT_MODES:
            self.logger.warning(
                "Unsupported Dot mode (%s) specified; defaulting to '%s'.",
                mode,
                self.mode,
            )

        # Signature text used by the Text API footer.
        self.signature = signature if isinstance(signature, str) else None

        # Icon for the Text API (base64 PNG 40x40, lower-left corner).
        self.icon = icon if isinstance(icon, str) else None

        # Image payload for the Image API (base64 PNG 296x152).
        self.image_data = (
            image_data if image_data and isinstance(image_data, str) else None
        )

        # Link for tap-to-interact navigation.
        self.link = link if isinstance(link, str) else None

        # Border for the Image API
        self.border = border

        # Dither type for Image API
        self.dither_type = dither_type

        # Dither kernel for the Image API
        self.dither_kernel = dither_kernel

        # Task Key for specifying which content to update
        self.task_key = (
            task_key if task_key and isinstance(task_key, str) else None
        )

        # Text API endpoint (v2)
        self.text_api_url = (
            "https://dot.mindreset.tech/api/authV2/open/device/"
            f"{self.device_id}/text"
        )

        # Image API endpoint (v2)
        self.image_api_url = (
            "https://dot.mindreset.tech/api/authV2/open/device/"
            f"{self.device_id}/image"
        )

        return

    def _post(self, api_url, payload, headers):
        """POST payload to api_url; return True on success, False otherwise."""

        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(
                "Dot POST URL: %s (cert_verify=%r)",
                api_url,
                self.verify_certificate,
            )
            self.logger.debug("Dot Payload %s", sanitize_payload(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                api_url,
                data=json.dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )

            if r.status_code == requests.codes.ok:
                self.logger.info(
                    "Sent Dot notification to %s.", self.device_id
                )
                return True

            status_str = NotifyDot.http_response_code_lookup(r.status_code)
            self.logger.warning(
                "Failed to send Dot notification to %s: %s%serror=%d.",
                self.device_id,
                status_str,
                ", " if status_str else "",
                r.status_code,
            )
            self.logger.debug(
                "Response Details:\r\n%r", (r.content or b"")[:2000]
            )
            return False

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending Dot notification to %s.",
                self.device_id,
            )
            self.logger.debug("Socket Exception: %s", str(e))
            return False

    def _send_text(self, body, title, icon_data, headers):
        """Send body/title via the Text API."""
        payload = {"refreshNow": self.refresh_now}

        if title:
            payload["title"] = title
        if body:
            payload["message"] = body
        if self.signature:
            payload["signature"] = self.signature
        if icon_data:
            payload["icon"] = icon_data
        if self.link:
            payload["link"] = self.link
        if self.task_key is not None:
            payload["taskKey"] = self.task_key

        return self._post(self.text_api_url, payload, headers)

    def _send_image(self, image_data, headers):
        """Send image_data via the Image API."""
        payload = {
            "image": image_data,
            "refreshNow": self.refresh_now,
        }

        if self.link:
            payload["link"] = self.link
        if self.border is not None:
            payload["border"] = self.border
        if self.dither_type is not None:
            payload["ditherType"] = self.dither_type
        if self.dither_kernel is not None:
            payload["ditherKernel"] = self.dither_kernel
        if self.task_key is not None:
            payload["taskKey"] = self.task_key

        return self._post(self.image_api_url, payload, headers)

    def _resolve_attachment(self, attach, warn_label):
        """Return base64 string from the first usable attachment, or None."""
        if not (attach and self.attachment_support):
            return None
        if len(attach) > 1:
            self.logger.warning(
                "Multiple attachments provided; only the first"
                " one will be used as %s.",
                warn_label,
            )
        try:
            attachment = attach[0]
            if attachment:
                return attachment.base64()
        except Exception as e:
            self.logger.warning("Failed to process attachment: %s", str(e))
        return None

    def send(
        self,
        body,
        title="",
        notify_type=NotifyType.INFO,
        attach=None,
        **kwargs,
    ):
        """Perform Dot Notification."""

        if not self.apikey:
            self.logger.warning("No API key was specified")
            return False

        if not self.device_id:
            self.logger.warning("No device ID was specified")
            return False

        headers = {
            "Authorization": f"Bearer {self.apikey}",
            "Content-Type": "application/json",
            "User-Agent": self.app_id,
        }

        if self.mode == "image":
            # Image-only mode: body and title are ignored.
            if title or body:
                self.logger.warning(
                    "Title and body are not supported in image mode"
                    " and will be ignored."
                )
            image_data = (
                self.image_data
                if isinstance(self.image_data, str)
                else self._resolve_attachment(attach, "image")
            )
            if not image_data:
                self.logger.warning(
                    "Image mode selected but no image data was provided."
                )
                return False
            return self._send_image(image_data, headers)

        # Text mode (default): smart dual-send.
        # Body/title go to the Text API; image data or attachment goes
        # to the Image API.  Text is always dispatched before image.
        image_data = (
            self.image_data
            if isinstance(self.image_data, str)
            else self._resolve_attachment(attach, "image")
        )
        has_text = bool(body or title)
        has_image = bool(image_data)

        if not has_text and not has_image:
            self.logger.warning(
                "Nothing to send to Dot. device %s.", self.device_id
            )
            return False

        has_error = False
        if has_text and not self._send_text(body, title, self.icon, headers):
            has_error = True

        if has_image and not self._send_image(image_data, headers):
            has_error = True
        return not has_error

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another similar one.
        """
        return (
            self.secure_protocol,
            self.apikey,
            self.device_id,
            self.mode,
        )

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        params = {}
        params["refresh"] = "yes" if self.refresh_now else "no"

        # Include mode only when non-default
        if self.mode != DOT_MODES[0]:
            params["mode"] = self.mode

        if self.signature:
            params["signature"] = self.signature
        if self.icon:
            params["icon"] = self.icon
        if self.image_data:
            params["image"] = self.image_data
        if self.border is not None:
            params["border"] = str(self.border)
        if self.dither_type and self.dither_type != "DIFFUSION":
            params["dither_type"] = self.dither_type
        if self.dither_kernel and self.dither_kernel != "FLOYD_STEINBERG":
            params["dither_kernel"] = self.dither_kernel
        if self.link:
            params["link"] = self.link
        if self.task_key:
            params["task_key"] = self.task_key

        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return "{schema}://{apikey}@{device_id}/?{params}".format(
            schema=self.secure_protocol,
            apikey=self.pprint(
                self.apikey, privacy, mode=PrivacyMode.Secret, safe=""
            ),
            device_id=NotifyDot.quote(self.device_id, safe=""),
            params=NotifyDot.urlencode(params),
        )

    def __len__(self):
        """Returns the number of targets associated with this notification."""
        return 1 if self.device_id else 0

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to
        re-instantiate this object."""

        results = NotifyBase.parse_url(url)
        if not results:
            return results

        # Determine mode: explicit ?mode= wins; path provides backward compat.
        mode = DOT_MODES[0]
        if results["qsd"].get("mode"):
            candidate = results["qsd"]["mode"].lower().strip()
            if candidate in DOT_MODES:
                mode = candidate
            else:
                NotifyDot.logger.warning(
                    "Unsupported Dot mode (%s) specified; defaulting to '%s'.",
                    candidate,
                    DOT_MODES[0],
                )
        else:
            path_tokens = NotifyDot.split_path(results.get("fullpath"))
            if path_tokens:
                candidate = path_tokens[0].lower()
                if candidate in DOT_MODES:
                    mode = candidate
                else:
                    NotifyDot.logger.warning(
                        "Unsupported Dot mode (%s) specified;"
                        " defaulting to '%s'.",
                        candidate,
                        DOT_MODES[0],
                    )
        results["mode"] = mode

        # Extract API key from user
        if results.get("user"):
            results["apikey"] = NotifyDot.unquote(results["user"])

        # Extract device ID from hostname
        if results.get("host"):
            results["device_id"] = NotifyDot.unquote(results["host"])

        # Refresh Now
        refresh_value = results["qsd"].get("refresh")
        if refresh_value:
            results["refresh_now"] = parse_bool(refresh_value.strip())

        # Signature
        if results["qsd"].get("signature"):
            results["signature"] = NotifyDot.unquote(
                results["qsd"]["signature"].strip()
            )

        # Icon
        if results["qsd"].get("icon"):
            results["icon"] = NotifyDot.unquote(results["qsd"]["icon"].strip())

        # Link
        if results["qsd"].get("link"):
            results["link"] = NotifyDot.unquote(results["qsd"]["link"].strip())

        # Border
        if results["qsd"].get("border"):
            with suppress(TypeError, ValueError):
                results["border"] = int(results["qsd"]["border"].strip())

        # Dither Type
        if results["qsd"].get("dither_type"):
            results["dither_type"] = NotifyDot.unquote(
                results["qsd"]["dither_type"].strip()
            )

        # Dither Kernel
        if results["qsd"].get("dither_kernel"):
            results["dither_kernel"] = NotifyDot.unquote(
                results["qsd"]["dither_kernel"].strip()
            )

        # Image (Image API)
        if results["qsd"].get("image"):
            results["image_data"] = NotifyDot.unquote(
                results["qsd"]["image"].strip()
            )

        # Task Key
        if results["qsd"].get("task_key"):
            results["task_key"] = NotifyDot.unquote(
                results["qsd"]["task_key"].strip()
            )

        return results
