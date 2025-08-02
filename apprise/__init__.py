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

__title__ = "Apprise"
__version__ = "1.9.4"
__author__ = "Chris Caron"
__license__ = "BSD 2-Clause"
__copywrite__ = "Copyright (C) 2025 Chris Caron <lead2gold@gmail.com>"
__email__ = "lead2gold@gmail.com"
__status__ = "Production"

from . import decorators, exception
from .apprise import Apprise
from .apprise_attachment import AppriseAttachment
from .apprise_config import AppriseConfig
from .asset import AppriseAsset
from .attachment.base import AttachBase
from .common import (
    CONFIG_FORMATS,
    CONTENT_INCLUDE_MODES,
    CONTENT_LOCATIONS,
    NOTIFY_FORMATS,
    NOTIFY_IMAGE_SIZES,
    NOTIFY_TYPES,
    OVERFLOW_MODES,
    PERSISTENT_STORE_MODES,
    PERSISTENT_STORE_STATES,
    ConfigFormat,
    ContentIncludeMode,
    ContentLocation,
    NotifyFormat,
    NotifyImageSize,
    NotifyType,
    OverflowMode,
    PersistentStoreMode,
)
from .config.base import ConfigBase
from .locale import AppriseLocale

# Inherit our logging with our additional entries added to it
from .logger import LogCapture, logger, logging
from .manager_attachment import AttachmentManager
from .manager_config import ConfigurationManager
from .manager_plugins import NotificationManager
from .persistent_store import PersistentStore
from .plugins.base import NotifyBase
from .url import PrivacyMode, URLBase

# Set default logging handler to avoid "No handler found" warnings.
logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = [
    "CONFIG_FORMATS",
    "CONTENT_INCLUDE_MODES",
    "CONTENT_LOCATIONS",
    "NOTIFY_FORMATS",
    "NOTIFY_IMAGE_SIZES",
    "NOTIFY_TYPES",
    "OVERFLOW_MODES",
    "PERSISTENT_STORE_MODES",
    "PERSISTENT_STORE_STATES",
    # Core
    "Apprise",
    "AppriseAsset",
    "AppriseAttachment",
    "AppriseConfig",
    "AppriseLocale",
    "AttachBase",
    "AttachmentManager",
    "ConfigBase",
    "ConfigFormat",
    "ConfigurationManager",
    "ContentIncludeMode",
    "ContentLocation",
    "LogCapture",
    # Managers
    "NotificationManager",
    "NotifyBase",
    "NotifyFormat",
    "NotifyImageSize",
    # Reference
    "NotifyType",
    "OverflowMode",
    "PersistentStore",
    "PersistentStoreMode",
    "PrivacyMode",
    "URLBase",
    # Decorator
    "decorators",
    # Exceptions
    "exception",
    # Logging
    "logger",
    "logging",
]
