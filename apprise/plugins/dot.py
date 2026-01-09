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

#
# API: https://dot.mindreset.tech/docs/service/studio/api/text_api
#      https://dot.mindreset.tech/docs/service/studio/api/image_api
#
# Text API Fields:
#   - refreshNow (bool, optional, default true): controls display timing.
#   - deviceId (string, required): unique device serial.
#   - title (string, optional): title text shown on screen.
#   - message (string, optional): body text shown on screen.
#   - signature (string, optional): footer/signature text.
#   - icon (string, optional): base64 PNG icon (40px x 40px).
#   - link (string, optional): tap-to-interact target URL.
#
# Image API Fields:
#   - refreshNow (bool, optional, default true): controls display timing.
#   - deviceId (string, required): unique device serial.
#   - image (string, required): base64 PNG image (296px x 152px).
#   - link (string, optional): tap-to-interact target URL.
#   - border (number, optional, default 0): 0=white, 1=black frame.
#   - ditherType (string, optional, default DIFFUSION): dithering mode.
#   - ditherKernel (string, optional, default FLOYD_STEINBERG):
#     dithering kernel.

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


class NotifyDot(NotifyBase):
    """A wrapper for Dot. Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Dot."
    # Alias: devices marketed as "Quote/0" remain discoverable.

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

    # Supported API modes
    SUPPORTED_MODES = ("text", "image")

    DEFAULT_MODE = "text"

    # Define object templates
    templates = ("{schema}://{apikey}@{device_id}/{mode}/",)

    # Define our template arguments
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
            "mode": {
                "name": _("API Mode"),
                "type": "choice:string",
                "values": SUPPORTED_MODES,
                "default": DEFAULT_MODE,
                "map_to": "mode",
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
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
        },
    )
    # Note:
    # - icon (Text API): base64 PNG icon (40px x 40px) in lower-left corner.
    #   Can be provided via `icon` parameter or first attachment.
    # - image (Image API): base64 PNG image (296px x 152px) supplied via
    #   configuration `image` parameter or first attachment.
    # - Only the first attachment is used; multiple attachments trigger a
    #   warning.

    def __init__(
        self,
        apikey=None,
        device_id=None,
        mode=DEFAULT_MODE,
        refresh_now=True,
        signature=None,
        icon=None,
        link=None,
        border=None,
        dither_type=None,
        dither_kernel=None,
        image_data=None,
        **kwargs,
    ):
        """Initialize Notify Dot Object."""
        super().__init__(**kwargs)

        # API Key (from user)
        self.apikey = apikey

        # Device ID tracks the Dot hardware serial.
        self.device_id = device_id

        # Refresh Now flag: True shows content immediately (default).
        self.refresh_now = parse_bool(refresh_now, default=True)

        # API mode ("text" or "image")
        self.mode = (
            mode.lower()
            if isinstance(mode, str) and mode.lower() in self.SUPPORTED_MODES
            else self.DEFAULT_MODE
        )
        if (
            not isinstance(mode, str)
            or mode.lower() not in self.SUPPORTED_MODES
        ):
            self.logger.warning(
                "Unsupported Dot mode (%s) specified; defaulting to '%s'.",
                mode,
                self.mode,
            )

        # Signature text used by the Text API footer.
        self.signature = signature if isinstance(signature, str) else None

        # Icon for the Text API (base64 PNG 40x40, lower-left corner).
        # Note: distinct from the Image API "image" field.
        self.icon = icon if isinstance(icon, str) else None

        # Image payload for the Image API (base64 PNG 296x152).
        self.image_data = image_data if isinstance(image_data, str) else None
        if self.mode == "text" and self.image_data:
            self.logger.warning(
                "Image data provided in text mode; ignoring configurable"
                " image payload."
            )
            self.image_data = None

        # Link for tap-to-interact navigation.
        self.link = link if isinstance(link, str) else None

        # Border for the Image API
        self.border = border

        # Dither type for Image API
        self.dither_type = dither_type

        # Dither kernel for the Image API
        self.dither_kernel = dither_kernel

        # Text API endpoint
        self.text_api_url = "https://dot.mindreset.tech/api/open/text"

        # Image API endpoint
        self.image_api_url = "https://dot.mindreset.tech/api/open/image"

        return

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

        # Prepare our headers
        headers = {
            "Authorization": f"Bearer {self.apikey}",
            "Content-Type": "application/json",
            "User-Agent": self.app_id,
        }

        if self.mode == "image":
            if title or body:
                self.logger.warning(
                    "Title and body are not supported in image mode "
                    "and will be ignored."
                )

            image_data = (
                self.image_data if isinstance(self.image_data, str) else None
            )

            # Use first attachment as image if no image_data provided
            # attachment.base64() returns base64-encoded string for API
            if not image_data and attach and self.attachment_support:
                if len(attach) > 1:
                    self.logger.warning(
                        "Multiple attachments provided; only the first "
                        "one will be used as image."
                    )
                try:
                    attachment = attach[0]
                    if attachment:
                        # Convert attachment to base64-encoded string
                        image_data = attachment.base64()
                except Exception as e:
                    self.logger.warning(f"Failed to process attachment: {e!s}")

            if not image_data:
                self.logger.warning(
                    "Image API mode selected but no image data was provided."
                )
                return False

            # Use Image API
            # Image API payload:
            #   refreshNow: display timing control.
            #   deviceId: Dot device serial (required).
            #   image: base64 PNG 296x152 (required).
            #   link: optional tap target.
            #   border: optional frame color.
            #   ditherType: optional dithering mode.
            #   ditherKernel: optional dithering kernel.
            payload = {
                "refreshNow": self.refresh_now,
                "deviceId": self.device_id,
                "image": image_data,  # Image payload shown on screen
            }

            if self.link:
                payload["link"] = self.link

            if self.border is not None:
                payload["border"] = self.border

            if self.dither_type is not None:
                payload["ditherType"] = self.dither_type

            if self.dither_kernel is not None:
                payload["ditherKernel"] = self.dither_kernel

            api_url = self.image_api_url

        else:
            # Use Text API
            # Text API payload:
            #   refreshNow: display timing control.
            #   deviceId: Dot device serial (required).
            #   title: optional title on screen.
            #   message: optional body on screen.
            #   signature: optional footer text.
            #   icon: optional base64 PNG icon (40x40).
            #   link: optional tap target.
            payload = {
                "refreshNow": self.refresh_now,
                "deviceId": self.device_id,
            }

            if title:
                payload["title"] = title

            if body:
                payload["message"] = body

            if self.signature:
                payload["signature"] = (
                    self.signature
                )  # Footer/signature displayed on screen

            # Use first attachment as icon if no icon provided
            # attachment.base64() returns base64-encoded string for API
            icon_data = self.icon
            if not icon_data and attach and self.attachment_support:
                if len(attach) > 1:
                    self.logger.warning(
                        "Multiple attachments provided; only the first "
                        "one will be used as icon."
                    )
                try:
                    attachment = attach[0]
                    if attachment:
                        # Convert attachment to base64-encoded string
                        icon_data = attachment.base64()
                except Exception as e:
                    self.logger.warning(f"Failed to process attachment: {e!s}")

            if icon_data:
                # Text API icon payload
                payload["icon"] = icon_data

            if self.link:
                payload["link"] = self.link

            api_url = self.text_api_url

        # Some Debug Logging
        if self.logger.isEnabledFor(logging.DEBUG):
            # Due to attachments; output can be quite heavy and io intensive
            # To accommodate this, we only show our debug payload information
            # if required.
            self.logger.debug(
                "Dot POST URL:"
                f" {api_url} (cert_verify={self.verify_certificate!r})"
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
                self.logger.info(f"Sent Dot notification to {self.device_id}.")
                return True

            # We had a problem
            status_str = NotifyDot.http_response_code_lookup(r.status_code)

            self.logger.warning(
                "Failed to send Dot notification to {}: "
                "{}{}error={}.".format(
                    self.device_id,
                    status_str,
                    ", " if status_str else "",
                    r.status_code,
                )
            )

            self.logger.debug(
                "Response Details:\r\n%r", (r.content or b"")[:2000])

            return False

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending Dot "
                f"notification to {self.device_id}."
            )
            self.logger.debug(f"Socket Exception: {e!s}")

            return False

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

        # Define any URL parameters
        params = {
            "refresh": "yes" if self.refresh_now else "no",
        }

        if self.mode == "text":
            if self.signature:
                params["signature"] = self.signature

            if self.icon:
                params["icon"] = self.icon

            if self.link:
                params["link"] = self.link

        else:  # image mode
            if self.image_data:
                params["image"] = self.image_data

            if self.link:
                params["link"] = self.link

            if self.border is not None:
                params["border"] = str(self.border)

            if self.dither_type and self.dither_type != "DIFFUSION":
                params["dither_type"] = self.dither_type

            if self.dither_kernel and self.dither_kernel != "FLOYD_STEINBERG":
                params["dither_kernel"] = self.dither_kernel

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        mode_segment = f"/{self.mode}/"

        return "{schema}://{apikey}@{device_id}{mode}?{params}".format(
            schema=self.secure_protocol,
            apikey=self.pprint(
                self.apikey, privacy, mode=PrivacyMode.Secret, safe=""
            ),
            device_id=NotifyDot.quote(self.device_id, safe=""),
            mode=mode_segment,
            params=NotifyDot.urlencode(params),
        )

    def __len__(self):
        """Returns the number of targets associated with this notification."""
        return 1 if self.device_id else 0

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""

        results = NotifyBase.parse_url(url)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Determine API mode from path (default to text)
        mode = NotifyDot.DEFAULT_MODE
        path_tokens = NotifyDot.split_path(results.get("fullpath"))
        if path_tokens:
            candidate = path_tokens.pop(0).lower()
            if candidate in NotifyDot.SUPPORTED_MODES:
                mode = candidate
            else:
                NotifyDot.logger.warning(
                    "Unsupported Dot mode (%s) detected; defaulting to '%s'.",
                    candidate,
                    NotifyDot.DEFAULT_MODE,
                )
        results["mode"] = mode
        remaining_path = "/".join(path_tokens)
        results["fullpath"] = "/" + remaining_path if remaining_path else "/"
        results["path"] = remaining_path

        # Extract API key from user
        user = results.get("user")
        if user:
            results["apikey"] = NotifyDot.unquote(user)

        # Extract device ID from hostname
        host = results.get("host")
        if host:
            results["device_id"] = NotifyDot.unquote(host)

        # Refresh Now
        refresh_value = results["qsd"].get("refresh")
        if refresh_value:
            results["refresh_now"] = parse_bool(refresh_value.strip())

        # Signature
        signature_value = results["qsd"].get("signature")
        if signature_value:
            results["signature"] = NotifyDot.unquote(signature_value.strip())

        # Icon
        icon_value = results["qsd"].get("icon")
        if icon_value:
            results["icon"] = NotifyDot.unquote(icon_value.strip())

        # Link
        link_value = results["qsd"].get("link")
        if link_value:
            results["link"] = NotifyDot.unquote(link_value.strip())

        # Border
        border_value = results["qsd"].get("border")
        if border_value:
            with suppress(TypeError, ValueError):
                results["border"] = int(border_value.strip())

        # Dither Type
        dither_type_value = results["qsd"].get("dither_type")
        if dither_type_value:
            results["dither_type"] = NotifyDot.unquote(
                dither_type_value.strip()
            )

        # Dither Kernel
        dither_kernel_value = results["qsd"].get("dither_kernel")
        if dither_kernel_value:
            results["dither_kernel"] = NotifyDot.unquote(
                dither_kernel_value.strip()
            )

        # Image (Image API)
        image_value = results["qsd"].get("image")
        if image_value:
            results["image_data"] = NotifyDot.unquote(image_value.strip())

        return results
