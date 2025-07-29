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

import gc
import mimetypes
import os
import sys

import pytest

from apprise import (
    AttachmentManager,
    ConfigurationManager,
    NotificationManager,
)

sys.path.append(os.path.join(os.path.dirname(__file__), "helpers"))

# Grant access to our Notification Manager Singleton
N_MGR = NotificationManager()
# Grant access to our Config Manager Singleton
C_MGR = ConfigurationManager()
# Grant access to our Attachment Manager Singleton
A_MGR = AttachmentManager()


@pytest.fixture(scope="function", autouse=True)
def mimetypes_always_available():
    """A pytest session fixture which ensures mimetypes is set correctly
    pointing to our temporary mime.types file."""
    files = (os.path.join(os.path.dirname(__file__), "var", "mime.types"),)
    mimetypes.init(files=files)


@pytest.fixture(scope="function", autouse=True)
def no_throttling_everywhere(session_mocker):
    """A pytest session fixture which disables throttling on all notifiers.

    It is automatically enabled.
    """
    # Ensure we're working with a clean slate for each test
    N_MGR.unload_modules()
    C_MGR.unload_modules()
    A_MGR.unload_modules()

    for plugin in N_MGR.plugins():
        session_mocker.patch.object(plugin, "request_rate_per_sec", 0)


@pytest.fixture(scope="function", autouse=True)
def collect_all_garbage(session_mocker):
    """A pytest session fixture to ensure no __del__ cleanup call from one
    plugin will cause testing issues with another.

    Run garbage collection after every test
    """
    # Force garbage collection
    gc.collect()
