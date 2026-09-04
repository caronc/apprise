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

from datetime import datetime, tzinfo
import math
from os.path import abspath, dirname, isfile, join
import re
from typing import Any, Optional, Union
from uuid import uuid4

from .common import (
    NotifyFormat,
    NotifyImageSize,
    NotifyType,
    PersistentStoreMode,
)
from .manager_plugins import NotificationManager
from .utils.time import zoneinfo

# Grant access to our Notification Manager Singleton
N_MGR = NotificationManager()


class AppriseAsset:
    """Provide shared application settings, paths, and delivery limits.

    Private attributes are excluded from configuration. Callers use their
    public constructor arguments; ``_uid`` and ``_recursion`` remain internal
    compatibility exceptions.
    """

    # Application Identifier
    app_id = "Apprise"

    # Application Description
    app_desc = "Apprise Notifications"

    # Provider URL
    app_url = "https://github.com/caronc/apprise"

    # A Simple Mapping of Colors; For every NOTIFY_TYPE identified,
    # there should be a mapping to it's color here:
    html_notify_map = {
        NotifyType.INFO: "#3AA3E3",
        NotifyType.SUCCESS: "#3AA337",
        NotifyType.FAILURE: "#A32037",
        NotifyType.WARNING: "#CACF29",
    }

    # The default color to return if a mapping isn't found in our table above
    default_html_color = "#888888"

    # Ascii Notification
    ascii_notify_map = {
        NotifyType.INFO: "[i]",
        NotifyType.SUCCESS: "[+]",
        NotifyType.FAILURE: "[!]",
        NotifyType.WARNING: "[~]",
    }

    # The default ascii to return if a mapping isn't found in our table above
    default_ascii_chars = "[?]"

    # The default image extension to use
    default_extension = ".png"

    # The default image size if one isn't specified
    default_image_size = NotifyImageSize.XY_256

    # The default theme
    theme = "default"

    # Image URL Mask
    image_url_mask = (
        "https://github.com/caronc/apprise/raw/master/apprise/assets/"
        "themes/{THEME}/apprise-{TYPE}-{XY}{EXTENSION}"
    )

    # Application Logo
    image_url_logo = (
        "https://github.com/caronc/apprise/raw/master/apprise/assets/"
        "themes/{THEME}/apprise-logo.png"
    )

    # Image Path Mask
    image_path_mask = abspath(
        join(
            dirname(__file__),
            "assets",
            "themes",
            "{THEME}",
            "apprise-{TYPE}-{XY}{EXTENSION}",
        )
    )

    # This value can also be set on calls to Apprise.notify(). This allows
    # you to let Apprise upfront the type of data being passed in.  This
    # must be of type NotifyFormat. Possible values could be:
    # - NotifyFormat.TEXT
    # - NotifyFormat.MARKDOWN
    # - NotifyFormat.HTML
    # - None
    #
    # If no format is specified (hence None), then no special pre-formatting
    # actions will take place during a notification. This has been and always
    # will be the default.
    body_format = None

    # Always attempt to send notifications asynchronous (as the same time
    # if possible)
    # This is a Python 3 supported option only. If set to False, then
    # notifications are sent sequentially (one after another)
    async_mode = True

    # Support :smile:, and other alike keywords swapping them for their
    # unicode value. A value of None leaves the interpretation up to the
    # end user to control (allowing them to specify emojis=yes on the
    # URL)
    interpret_emojis = None

    # Whether or not to interpret escapes found within the input text prior
    # to passing it upstream. Such as converting \t to an actual tab and \n
    # to a new line.
    interpret_escapes = False

    # Default number of retries after a first notification failure.
    # Individual plugins may override this via their ?retry= URL parameter
    # or the 'retry:' YAML key.  Clamped to [0, APPRISE_MAX_SERVICE_RETRY].
    default_service_retry = 0

    # Default wait (in seconds) between retry attempts.  Individual plugins
    # may override this via their ?wait= URL parameter or the 'wait:' YAML
    # key.  Clamped to [0.0, APPRISE_MAX_SERVICE_WAIT].
    default_service_wait = 0.5

    # When True, as soon as any independent OR tag chain exhausts all its
    # priority groups without success, notify() / async_notify() return False
    # immediately without running further escalation rounds for the surviving
    # chains.  When False (the default), all chains are allowed to complete
    # regardless of whether another chain has already failed.
    abort_on_chain_failure = False

    # Defines the encoding of the content passed into Apprise
    encoding = "utf-8"

    # Automatically generate our Pretty Good Privacy (PGP) keys if one isn't
    # present and our environment configuration allows for it.
    # For example, a case where the environment wouldn't allow for it would be
    # if Persistent Storage was set to `memory`
    pgp_autogen = True

    # Automatically generate our Privacy Enhanced Mail (PEM) keys if one isn't
    # present and our environment configuration allows for it.
    # For example, a case where the environment wouldn't allow for it would be
    # if Persistent Storage was set to `memory`
    pem_autogen = True

    # For more detail see CWE-312 @
    #    https://cwe.mitre.org/data/definitions/312.html
    #
    # By enabling this, the logging output has additional overhead applied to
    # it preventing secure password and secret information from being
    # displayed in the logging. Since there is overhead involved in performing
    # this cleanup; system owners who run in a very isolated environment may
    # choose to disable this for a slight performance bump. It is recommended
    # that you leave this option as is otherwise.
    secure_logging = True

    # By default, HTTP redirects (3xx responses) are followed, matching the
    # behaviour of the underlying requests library. Set this to False to
    # disable redirect following globally across all plugins without having
    # to add redirect=no to every individual URL. Individual URLs can still
    # override this via the redirect= parameter.
    http_redirects = True

    # Optionally specify one or more path to attempt to scan for Python modules
    # By default, no paths are scanned.
    __plugin_paths = []

    # Optionally set the location of the persistent storage
    # By default there is no path and thus persistent storage is not used
    __storage_path = None

    # Optionally define the default salt to apply to all persistent storage
    # namespace generation (unless over-ridden)
    __storage_salt = b""

    # Optionally define the namespace length of the directories created by
    # the storage. If this is set to zero, then the length is pre-determined
    # by the generator (sha1, md5, sha256, etc)
    __storage_idlen = 8

    # Set storage to auto
    __storage_mode = PersistentStoreMode.AUTO

    # Internal settings are not loaded from YAML configuration.

    # AppriseAPI passes this internal counter between chained servers to
    # prevent notification loops. Its constructor support is retained for
    # compatibility with https://github.com/caronc/apprise-api.
    _recursion = 0

    # AppriseAPI preserves this internal source identifier across chained
    # requests. Its constructor support is retained for compatibility.
    _uid = str(uuid4())

    # AppriseAPI still passes these private arguments. All other internal
    # settings must use their validated public constructor arguments.
    _KWARGS_INTERNAL_ALLOWLIST = frozenset({"_recursion", "_uid"})

    # Default timezone to use (pass in timezone value)
    # A list of timezones can be found here:
    # https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
    # You can specify things such as 'America/Montreal'
    # If no timezone is specified, then the one detected on the system
    # is used
    _tzinfo = None

    # Default budget for one service, including retries and waits. Apprise
    # reports TIMEOUT after this many seconds; 0 disables the service limit.
    _service_timeout = 60.0

    # A safety ceiling on the combined title + body character count, checked
    # before any format conversion or splitting begins. 0 disables the check
    # entirely, which is the default.
    _payload_max_size = 0

    # A title or body at or below this length may remain whole when the other
    # side can retain its minimum.
    _payload_buffer_threshold = 10

    # Minimum reserved for the other side. If it cannot fit, title and body
    # share the cap proportionally.
    _payload_min_buffer = 25

    # Keep result logs in memory unless disk-backed capture is configured.
    # Apprise reads this setting from its existing asset when it notifies.
    _result_log_memory_size = 0

    # A zero disk allowance preserves the existing memory-only behavior.
    # When enabled, both limits cover the complete notification call.
    _result_log_disk_size = 0

    def __init__(
        self,
        plugin_paths: Optional[list[str]] = None,
        storage_path: Optional[str] = None,
        storage_mode: Optional[Union[str, PersistentStoreMode]] = None,
        storage_salt: Optional[Union[str, bytes]] = None,
        storage_idlen: Optional[int] = None,
        timezone: Optional[Union[str, tzinfo]] = None,
        service_timeout: Optional[Union[int, float]] = None,
        payload_max_size: Optional[int] = None,
        payload_buffer_threshold: Optional[int] = None,
        payload_min_buffer: Optional[int] = None,
        result_log_memory_size: Optional[int] = None,
        result_log_disk_size: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize shared settings and delivery limits.

        Zero disables ``service_timeout`` and ``payload_max_size``.
        ``payload_buffer_threshold`` and ``payload_min_buffer`` control how a
        capped payload is shared between title and body; see
        ``enforce_payload_max_size()``. Result logs use disk after their memory
        allowance; a zero disk size keeps them in memory. ``None`` keeps each
        class default.
        """
        # Assign default arguments if specified
        for key, value in kwargs.items():
            if not hasattr(AppriseAsset, key):
                raise AttributeError(
                    f"AppriseAsset init(): An invalid key {key} was specified."
                )

            if key.startswith("_") and (
                key not in self._KWARGS_INTERNAL_ALLOWLIST
            ):
                raise AttributeError(
                    f"AppriseAsset init(): {key} can not be set directly; "
                    "use its dedicated keyword argument instead."
                )

            setattr(self, key, value)

        if plugin_paths:
            # Load any decorated modules if defined
            self.__plugin_paths = plugin_paths
            N_MGR.module_detection(plugin_paths)

        if storage_path:
            # Define our persistent storage path
            self.__storage_path = storage_path

        if storage_mode:
            # Define how our persistent storage behaves
            try:
                self.__storage_mode = (
                    storage_mode
                    if isinstance(storage_mode, NotifyFormat)
                    else PersistentStoreMode(storage_mode.lower())
                )

            except (AttributeError, ValueError, TypeError):
                err = (
                    f"An invalid persistent store mode ({storage_mode}) was "
                    "specified."
                )
                raise AttributeError(err) from None

        if isinstance(storage_idlen, int):
            # Define the number of characters utilized from our namespace lengh
            if storage_idlen < 0:
                # Unsupported type
                raise ValueError(
                    "AppriseAsset storage_idlen(): Value must "
                    "be an integer and > 0"
                )

            # Store value
            self.__storage_idlen = storage_idlen

        if isinstance(timezone, tzinfo):
            self._tzinfo = timezone

        elif timezone is not None:
            self._tzinfo = zoneinfo(timezone)
            if not self._tzinfo:
                raise AttributeError(
                    "AppriseAsset timezone provided is invalid"
                ) from None
        else:
            # Default our timezone to what is detected on the system
            self._tzinfo = datetime.now().astimezone().tzinfo

        if service_timeout is not None:
            # Store all durations as floats and reject bool values.
            if not isinstance(service_timeout, (int, float)) or isinstance(
                service_timeout, bool
            ):
                raise TypeError(
                    "AppriseAsset service_timeout must be an int or float."
                )

            if not math.isfinite(service_timeout) or service_timeout < 0:
                # Use 0 for no timeout; infinity is unsafe on some platforms.
                raise ValueError(
                    "AppriseAsset service_timeout must be >= 0 and "
                    "finite (0 disables the timeout entirely)."
                )

            self._service_timeout = float(service_timeout)

        if payload_max_size is not None:
            # Reject booleans even though ``bool`` subclasses ``int``.
            if not isinstance(payload_max_size, int) or isinstance(
                payload_max_size, bool
            ):
                raise TypeError(
                    "AppriseAsset payload_max_size must be an int."
                )

            if payload_max_size < 0:
                raise ValueError(
                    "AppriseAsset payload_max_size must be >= 0 "
                    "(0 disables the cap entirely)."
                )

            self._payload_max_size = payload_max_size

        if payload_buffer_threshold is not None:
            # Reject booleans even though ``bool`` subclasses ``int``.
            if not isinstance(payload_buffer_threshold, int) or isinstance(
                payload_buffer_threshold, bool
            ):
                raise TypeError(
                    "AppriseAsset payload_buffer_threshold must be an int."
                )

            if payload_buffer_threshold < 0:
                raise ValueError(
                    "AppriseAsset payload_buffer_threshold must be >= 0."
                )

            self._payload_buffer_threshold = payload_buffer_threshold

        if payload_min_buffer is not None:
            # Reject booleans even though ``bool`` subclasses ``int``.
            if not isinstance(payload_min_buffer, int) or isinstance(
                payload_min_buffer, bool
            ):
                raise TypeError(
                    "AppriseAsset payload_min_buffer must be an int."
                )

            if payload_min_buffer < 0:
                raise ValueError(
                    "AppriseAsset payload_min_buffer must be >= 0."
                )

            self._payload_min_buffer = payload_min_buffer

        if result_log_memory_size is not None:
            # Booleans are integers in Python, but are not valid byte limits.
            if not isinstance(result_log_memory_size, int) or isinstance(
                result_log_memory_size, bool
            ):
                raise TypeError(
                    "AppriseAsset result_log_memory_size must be an int."
                )

            if result_log_memory_size < 0:
                raise ValueError(
                    "AppriseAsset result_log_memory_size must be >= 0."
                )

            self._result_log_memory_size = result_log_memory_size

        if result_log_disk_size is not None:
            # Keep this strict so later storage calculations are predictable.
            if not isinstance(result_log_disk_size, int) or isinstance(
                result_log_disk_size, bool
            ):
                raise TypeError(
                    "AppriseAsset result_log_disk_size must be an int."
                )

            if result_log_disk_size < 0:
                raise ValueError(
                    "AppriseAsset result_log_disk_size must be >= 0."
                )

            self._result_log_disk_size = result_log_disk_size

        if storage_salt is not None:
            # Define the number of characters utilized from our namespace lengh

            if isinstance(storage_salt, bytes):
                self.__storage_salt = storage_salt

            elif isinstance(storage_salt, str):
                try:
                    self.__storage_salt = storage_salt.encode(self.encoding)

                except UnicodeEncodeError:
                    # Bad data; don't pass it along
                    raise ValueError(
                        "AppriseAsset namespace_salt(): "
                        "Value provided could not be encoded"
                    ) from None

            else:  # Unsupported
                raise ValueError(
                    "AppriseAsset namespace_salt(): Value provided must be "
                    "string or bytes object"
                )

    def enforce_payload_max_size(
        self, title: str, body: str
    ) -> tuple[str, str]:
        """Apply the configured input cap to ``title`` and ``body``.

        Checked in order, the first match decides the split:

        1. An absent side never competes for room: an empty title leaves
           the whole cap for the body, and vice versa.
        2. A short side (length <= ``payload_buffer_threshold``) is shown
           whole if the other side can still keep at least
           ``payload_min_buffer`` characters (or its own full length, if
           shorter) out of what remains. This is checked for the title
           first, then the body.
        3. Otherwise, title and body share the cap in proportion to their
           original lengths. When the cap allows, each nonempty side keeps
           at least one character.

        Very small caps may produce short fragments, but proportional sharing
        avoids dropping one side when space is available for both.
        """
        if not self._payload_max_size:
            return title, body

        cap = self._payload_max_size
        total = len(title) + len(body)
        if total <= cap:
            return title, body

        if not title:
            return "", body[:cap]

        if not body:
            return title[:cap], ""

        threshold = self._payload_buffer_threshold
        min_buffer = self._payload_min_buffer

        if len(title) <= threshold:
            # A short title is worth showing whole, but only if the body
            # can still keep its own minimum out of what's left.
            body_reserve = min(len(body), min_buffer)
            if len(title) + body_reserve <= cap:
                return title, body[: cap - len(title)]

        if len(body) <= threshold:
            # Same guarantee, mirrored for a short body.
            title_reserve = min(len(title), min_buffer)
            if len(body) + title_reserve <= cap:
                return title[: cap - len(body)], body

        # If neither guarantee applies, share the cap proportionally.
        title_budget = (len(title) * cap) // total
        body_budget = cap - title_budget

        # Rounding can zero out a small, nonempty title entirely; borrow
        # one character from body's share when it can spare it.
        if not title_budget and body_budget > 0:
            title_budget = 1
            body_budget -= 1

        return title[:title_budget], body[:body_budget]

    def color(
        self,
        notify_type: NotifyType,
        color_type: Optional[type] = None,
    ) -> Union[str, int, tuple[int, int, int]]:
        """Returns an HTML mapped color based on passed in notify type.

        if color_type is:
           None    then a standard hex string is returned as
                   a string format ('#000000').

           int     then the integer representation is returned
           tuple   then the the red, green, blue is returned in a tuple
        """

        # Attempt to get the type, otherwise return a default grey
        # if we couldn't look up the entry
        color = self.html_notify_map.get(notify_type, self.default_html_color)
        if color_type is None:
            # This is the default return type
            return color

        elif color_type is int:
            # Convert the color to integer
            return AppriseAsset.hex_to_int(color)

        # The only other type is tuple
        elif color_type is tuple:
            return AppriseAsset.hex_to_rgb(color)

        # Unsupported type
        raise ValueError(
            "AppriseAsset html_color(): An invalid color_type was specified."
        )

    def ascii(self, notify_type: NotifyType) -> str:
        """Returns an ascii representation based on passed in notify type."""
        # look our response up
        return self.ascii_notify_map.get(notify_type, self.default_ascii_chars)

    def image_url(
        self,
        notify_type: NotifyType,
        image_size: Optional[NotifyImageSize] = None,
        logo: bool = False,
        extension: Optional[str] = None,
    ) -> Optional[str]:
        """Apply our mask to our image URL.

        if logo is set to True, then the logo_url is used instead
        """

        url_mask = self.image_url_logo if logo else self.image_url_mask
        if not url_mask:
            # No image to return
            return None

        if extension is None:
            extension = self.default_extension

        if image_size is None:
            image_size = self.default_image_size

        re_map = {
            "{THEME}": self.theme if self.theme else "",
            "{TYPE}": notify_type.value,
            "{XY}": image_size.value,
            "{EXTENSION}": extension,
        }

        # Iterate over above list and store content accordingly
        re_table = re.compile(
            r"(" + "|".join(re_map.keys()) + r")",
            re.IGNORECASE,
        )

        return re_table.sub(lambda x: re_map[x.group()], url_mask)

    def image_path(
        self,
        notify_type: NotifyType,
        image_size: NotifyImageSize,
        must_exist: bool = True,
        extension: Optional[str] = None,
    ) -> Optional[str]:
        """Apply our mask to our image file path."""

        if not self.image_path_mask:
            # No image to return
            return None

        if extension is None:
            extension = self.default_extension

        re_map = {
            "{THEME}": self.theme if self.theme else "",
            "{TYPE}": notify_type.value,
            "{XY}": image_size.value,
            "{EXTENSION}": extension,
        }

        # Iterate over above list and store content accordingly
        re_table = re.compile(
            r"(" + "|".join(re_map.keys()) + r")",
            re.IGNORECASE,
        )

        # Acquire our path
        path = re_table.sub(lambda x: re_map[x.group()], self.image_path_mask)
        if must_exist and not isfile(path):
            return None

        # Return what we parsed
        return path

    def image_raw(
        self,
        notify_type: NotifyType,
        image_size: NotifyImageSize,
        extension: Optional[str] = None,
    ) -> Optional[bytes]:
        """Returns the raw image if it can (otherwise the function returns
        None)"""

        path = self.image_path(
            notify_type=notify_type,
            image_size=image_size,
            extension=extension,
        )
        if path:
            try:
                with open(path, "rb") as fd:
                    return fd.read()

            except OSError:
                # We can't access the file
                return None

        return None

    def details(self) -> dict[str, str]:
        """Returns the details associated with the AppriseAsset object."""
        return {
            "app_id": self.app_id,
            "app_desc": self.app_desc,
            "default_extension": self.default_extension,
            "theme": self.theme,
            "image_path_mask": self.image_path_mask,
            "image_url_mask": self.image_url_mask,
            "image_url_logo": self.image_url_logo,
        }

    @staticmethod
    def hex_to_rgb(value: str) -> tuple[int, int, int]:
        """Takes a hex string (such as #00ff00) and returns a tuple in the form
        of (red, green, blue)

        eg: #00ff00 becomes : (0, 65535, 0)
        """
        value = value.lstrip("#")
        lv = len(value)
        return tuple(
            int(value[i : i + lv // 3], 16) for i in range(0, lv, lv // 3)
        )

    @staticmethod
    def hex_to_int(value: str) -> int:
        """Takes a hex string (such as #00ff00) and returns its integer
        equivalent.

        eg: #00000f becomes : 15
        """
        return int(value.lstrip("#"), 16)

    @property
    def plugin_paths(self) -> list[str]:
        """Return the plugin paths defined."""
        return self.__plugin_paths

    @property
    def storage_path(self) -> Optional[str]:
        """Return the persistent storage path defined."""
        return self.__storage_path

    @property
    def storage_mode(self) -> PersistentStoreMode:
        """Return the persistent storage mode defined."""

        return self.__storage_mode

    @property
    def storage_salt(self) -> bytes:
        """Return the provided namespace salt; this is always of type bytes."""
        return self.__storage_salt

    @property
    def storage_idlen(self) -> int:
        """Return the persistent storage id length."""

        return self.__storage_idlen

    @property
    def result_log_memory_size(self) -> int:
        """Return the result-log memory allowance in bytes."""
        return self._result_log_memory_size

    @property
    def result_log_disk_size(self) -> int:
        """Return the result-log disk allowance in bytes."""
        return self._result_log_disk_size

    @property
    def tzinfo(self) -> tzinfo:
        """Return the timezone object"""
        return self._tzinfo
