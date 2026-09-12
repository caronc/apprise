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

import gc
import logging
import mimetypes
import os
import sys

import pytest

from apprise import (
    AttachmentManager,
    ConfigurationManager,
    NotificationManager,
)
from apprise.logger import logger as apprise_logger

sys.path.append(os.path.join(os.path.dirname(__file__), "helpers"))

# Grant access to our Notification Manager Singleton
N_MGR = NotificationManager()
# Grant access to our Config Manager Singleton
C_MGR = ConfigurationManager()
# Grant access to our Attachment Manager Singleton
A_MGR = AttachmentManager()


@pytest.fixture(scope="function", autouse=True)
def mimetypes_always_available():
    """Use the test MIME database for every test."""
    files = (os.path.join(os.path.dirname(__file__), "var", "mime.types"),)
    mimetypes.init(files=files)


@pytest.fixture(scope="function", autouse=True)
def no_throttling_everywhere(mocker):
    """Disable plugin throttling for every test.

    Function-scoped cleanup prevents patches from accumulating across the
    suite and slowing final teardown.
    """
    # Ensure we're working with a clean slate for each test
    N_MGR.unload_modules()
    C_MGR.unload_modules()
    A_MGR.unload_modules()

    for plugin in N_MGR.plugins():
        mocker.patch.object(plugin, "request_rate_per_sec", 0)


@pytest.fixture(scope="function", autouse=True)
def _reset_apprise_logger_state():
    """Reset shared logger state around every test.

    CLI tests change the Apprise and asyncio loggers. Restoring their levels
    and handlers prevents those changes from affecting later log assertions.
    """
    asyncio_logger = logging.getLogger("asyncio")

    original_level = apprise_logger.level
    original_handlers = list(apprise_logger.handlers)
    original_asyncio_level = asyncio_logger.level
    original_asyncio_handlers = list(asyncio_logger.handlers)

    apprise_logger.setLevel(logging.NOTSET)
    asyncio_logger.setLevel(logging.NOTSET)
    asyncio_logger.handlers[:] = []
    yield
    apprise_logger.setLevel(original_level)
    apprise_logger.handlers[:] = original_handlers
    asyncio_logger.setLevel(original_asyncio_level)
    asyncio_logger.handlers[:] = original_asyncio_handlers


@pytest.fixture(scope="function", autouse=True)
def collect_all_garbage():
    """Collect garbage after each test to isolate plugin finalizers."""
    # Force garbage collection
    gc.collect()
