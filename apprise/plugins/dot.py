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
#   - refreshNow: bool, optional, default true; show content immediately; controls when the message appears
#   - deviceId: string, required; device serial number; distinguishes different devices
#   - title: string, optional; text title; rendered on the screen as the title line
#   - message: string, optional; text content; rendered on the screen as the body
#   - signature: string, optional; text signature; rendered on the screen as the footer/signature line
#   - icon: string, optional; base64-encoded PNG icon (40px × 40px); rendered in the lower-left corner
#   - link: string, optional; http/https URL or custom scheme; tap-to-interact target
#
# Image API Fields:
#   - refreshNow: bool, optional, default true; show content immediately; controls when the image appears
#   - deviceId: string, required; device serial number; distinguishes different devices
#   - image: string, required; base64-encoded PNG image (296px × 152px); rendered on the screen as the image payload
#   - link: string, optional; http/https URL or custom scheme; tap-to-interact target
#   - border: number, optional, default 0; 0 = white border, 1 = black border; controls the frame color
#   - ditherType: string, optional, default DIFFUSION; dithering mode (DIFFUSION, ORDERED, NONE); controls dithering strategy
#   - ditherKernel: string, optional, default FLOYD_STEINBERG; dithering kernel (THRESHOLD, ATKINSON, BURKES, FLOYD_STEINBERG, SIERRA2, STUCKI, JARVIS_JUDICE_NINKE, DIFFUSION_ROW, DIFFUSION_COLUMN, DIFFUSION_2D); controls dithering algorithm
#
import base64
import json

import requests

from ..common import NotifyImageSize, NotifyType
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import parse_bool
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
    # Dot devices are marketed as "Quote/0"; keep this alias for discoverability

    # The services URL
    service_url = "https://dot.mindreset.tech"

    # The default protocol
    protocol = "dot"

    # The default secure protocol
    secure_protocol = "dot"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://dot.mindreset.tech/docs/service/studio/api/text_api"

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_128

    # Supported API modes
    SUPPORTED_MODES = ("text", "image")
    DEFAULT_MODE = "text"

    # Define object templates
    templates = (
        "{schema}://{apikey}@{device_id}/{mode}",
        "{schema}://{apikey}@{device_id}/{mode}/",
    )

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
            "title": {
                "name": _("Text Title"),
                "type": "string",
            },
            "message": {
                "name": _("Text Content"),
                "type": "string",
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
    # - icon (Text API): base64-encoded PNG icon (40px × 40px) rendered in the lower-left corner
    # - image (Image API): base64-encoded PNG image (296px × 152px) delivered via the image parameter or runtime attachments

    def __init__(
        self,
        apikey=None,
        device_id=None,
        mode=DEFAULT_MODE,
        refresh_now=True,
        signature=None,
        icon=None,
        link=None,
        border=0,
        dither_type="DIFFUSION",
        dither_kernel="FLOYD_STEINBERG",
        image_data=None,
        **kwargs,
    ):
        """Initialize Notify Dot Object."""
        super().__init__(**kwargs)

        # API Key (from user)
        self.apikey = apikey

        # Device ID (Device Serial Number - uniquely identifies the Dot device)
        self.device_id = device_id

        # Refresh Now flag (whether to display immediately; controls the display timing; default True)
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

        # Signature (Text API field: footer/signature string rendered on screen)
        self.signature = signature if isinstance(signature, str) else None

        # Icon (Text API field: base64-encoded PNG icon 40px × 40px rendered in the lower-left corner)
        # Note: this is distinct from the Image API "image" field
        self.icon = icon if isinstance(icon, str) else None

        # Image Data (Image API field: base64-encoded PNG image 296px × 152px)
        self.image_data = image_data if isinstance(image_data, str) else None
        if self.mode == "text" and self.image_data:
            self.logger.warning(
                "Image data provided in text mode; ignoring configurable image payload."
            )
            self.image_data = None

        # Link (http/https URL or custom scheme used for tap-to-interact navigation)
        self.link = link if isinstance(link, str) else None

        # Border (Image API field: 0 = white border, 1 = black border; default 0)
        try:
            self.border = int(border)
            if self.border not in (0, 1):
                raise ValueError()
        except (TypeError, ValueError):
            self.border = 0
            self.logger.warning(
                "The specified Dot border ({}) is not valid. Must be 0 or 1. Using default 0.",
                border,
            )

        # Dither Type (Image API field: dithering mode; DIFFUSION, ORDERED, NONE; default DIFFUSION)
        self.dither_type = (
            dither_type.upper()
            if isinstance(dither_type, str)
            and dither_type.upper() in DOT_DITHER_TYPES
            else "DIFFUSION"
        )

        # Dither Kernel (Image API field: dithering kernel; THRESHOLD, ATKINSON, BURKES, FLOYD_STEINBERG, SIERRA2, STUCKI, JARVIS_JUDICE_NINKE, DIFFUSION_ROW, DIFFUSION_COLUMN, DIFFUSION_2D; default FLOYD_STEINBERG)
        self.dither_kernel = (
            dither_kernel.upper()
            if isinstance(dither_kernel, str)
            and dither_kernel.upper() in DOT_DITHER_KERNELS
            else "FLOYD_STEINBERG"
        )

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
            image_data = (
                self.image_data if isinstance(self.image_data, str) else None
            )

            if not image_data and attach:
                for attachment in attach:
                    try:
                        image_data = attachment.base64()
                        if image_data:
                            break
                    except Exception:
                        continue

            if not image_data:
                self.logger.warning(
                    "Image API mode selected but no image data was provided."
                )
                return False

            # Use Image API
            # Image API fields:
            # - refreshNow: bool, controls whether the device displays immediately
            # - deviceId: string, identifies the Dot device (required)
            # - image: string, base64-encoded PNG image (296px × 152px) rendered on the screen (required)
            # - link: string, optional tap-to-interact target
            # - border: number, optional frame color (0 = white, 1 = black)
            # - ditherType: string, optional dithering mode (DIFFUSION, ORDERED, NONE)
            # - ditherKernel: string, optional dithering kernel (THRESHOLD, ATKINSON, BURKES, FLOYD_STEINBERG, SIERRA2, STUCKI, JARVIS_JUDICE_NINKE, DIFFUSION_ROW, DIFFUSION_COLUMN, DIFFUSION_2D)
            payload = {
                "refreshNow": self.refresh_now,
                "deviceId": self.device_id,
                "image": image_data,  # Image payload shown on screen
            }

            if self.link:
                payload["link"] = self.link  # Tap-to-interact destination

            if self.border is not None:
                payload["border"] = self.border  # Frame color selection

            if self.dither_type:
                payload["ditherType"] = self.dither_type  # Dithering mode

            if self.dither_kernel:
                payload["ditherKernel"] = (
                    self.dither_kernel
                )  # Dithering kernel

            api_url = self.image_api_url

        else:
            if attach:
                self.logger.debug(
                    "Attachments supplied but ignored in Dot text mode."
                )
            # Use Text API
            # Text API fields:
            # - refreshNow: bool, controls whether the device displays immediately
            # - deviceId: string, identifies the Dot device (required)
            # - title: string, optional title rendered on screen
            # - message: string, optional body text rendered on screen
            # - signature: string, optional footer rendered on screen
            # - icon: string, optional base64-encoded PNG icon (40px × 40px) rendered in the lower-left corner
            # - link: string, optional tap-to-interact target
            payload = {
                "refreshNow": self.refresh_now,
                "deviceId": self.device_id,
            }

            if title:
                payload["title"] = title  # Title displayed on screen
            elif self.app_desc:
                payload["title"] = self.app_desc

            if body:
                payload["message"] = body  # Body text displayed on screen

            if self.signature:
                payload["signature"] = (
                    self.signature
                )  # Footer/signature displayed on screen

            if self.icon:
                # Text API icon payload
                payload["icon"] = self.icon

            if self.link:
                payload["link"] = self.link

            api_url = self.text_api_url

        self.logger.debug(
            "Dot POST URL:"
            f" {api_url} (cert_verify={self.verify_certificate!r})"
        )
        self.logger.debug(f"Dot Payload: {json.dumps(payload, indent=2)}")

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

            self.logger.debug(f"Response Details:\r\n{r.content}")

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
            self.protocol,
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
            schema=self.protocol,
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
        if "user" in results and results["user"]:
            results["apikey"] = NotifyDot.unquote(results["user"])

        # Extract device ID from hostname
        if "host" in results and results["host"]:
            results["device_id"] = NotifyDot.unquote(results["host"])

        # Refresh Now
        if "refresh" in results["qsd"] and results["qsd"]["refresh"]:
            results["refresh_now"] = parse_bool(
                results["qsd"]["refresh"].strip()
            )

        # Signature
        if "signature" in results["qsd"] and results["qsd"]["signature"]:
            results["signature"] = NotifyDot.unquote(
                results["qsd"]["signature"].strip()
            )

        # Icon
        if "icon" in results["qsd"] and results["qsd"]["icon"]:
            results["icon"] = NotifyDot.unquote(results["qsd"]["icon"].strip())

        # Link
        if "link" in results["qsd"] and results["qsd"]["link"]:
            results["link"] = NotifyDot.unquote(results["qsd"]["link"].strip())

        # Border
        if "border" in results["qsd"] and results["qsd"]["border"]:
            try:
                results["border"] = int(results["qsd"]["border"].strip())
            except (TypeError, ValueError):
                pass

        # Dither Type
        if "dither_type" in results["qsd"] and results["qsd"]["dither_type"]:
            results["dither_type"] = NotifyDot.unquote(
                results["qsd"]["dither_type"].strip()
            )

        # Dither Kernel
        if (
            "dither_kernel" in results["qsd"]
            and results["qsd"]["dither_kernel"]
        ):
            results["dither_kernel"] = NotifyDot.unquote(
                results["qsd"]["dither_kernel"].strip()
            )

        # Image (Image API)
        if "image" in results["qsd"] and results["qsd"]["image"]:
            results["image_data"] = NotifyDot.unquote(
                results["qsd"]["image"].strip()
            )

        return results
