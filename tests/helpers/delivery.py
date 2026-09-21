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


"""Shared responses, attachments, and recorders for delivery tests."""

import contextlib
from json import dumps
import os
from unittest import mock

import requests

from apprise.plugins.base import NotifyBase

# Attachment Directory
TEST_VAR_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "var"
)
ATTACHMENT = os.path.join(TEST_VAR_DIR, "apprise-test.gif")

# Fields a service might look for in a good answer.  It is deliberately
# wide: one answer has to satisfy every service in the fleet, and a field
# a service does not know about is simply ignored.
OK_FIELDS = {
    "ok": True,
    "success": True,
    "status": "success",
    "id": "1",
    "uuid": "1",
    "sid": "1",
    "requestId": "1",
    "code": 0,
    "errcode": 0,
    "error": None,
    "channel": "C1",
    "access_token": "abc",
    "expires_in": 3600,
    "message_id": 1,
    "upload_url": "https://localhost/upload",
    "file_id": "F1",
    "file_name": "apprise-test.gif",
    "file_type": "image/gif",
    "file_url": "https://localhost/x",
    "media_id": 1,
    "media_id_string": "1",
    "content_uri": "mxc://localhost/1",
    "event_id": "e1",
    "room_id": "!r:localhost",
    "user_id": "@u:localhost",
    "url": "https://cdn.example/x",
    "post": {"id": 1},
    "data": {"url": "https://cdn.example/x", "id": "1"},
    "json": {"errors": []},
    "result": {"message_id": 1, "id": "1", "status": "ok"},
    "items": [{"id": "1"}],
    "messages": [{"status": "0", "message-id": "1"}],
}

# The same answer as a JSON document
OK_BODY = dumps(OK_FIELDS)


def ok_response(*args, **kwargs):
    """Return a response a service will treat as a success."""
    response = requests.Request()
    response.status_code = requests.codes.ok
    response.content = OK_BODY
    response.text = OK_BODY
    response.headers = {"Content-Type": "application/json"}
    return response


@contextlib.contextmanager
def delivery_marks():
    """Collect every target a service records while the block runs."""

    recorded = []
    real = NotifyBase.mark_delivered

    def counted(self, key, per_message=False):
        recorded.append(key)
        return real(self, key, per_message)

    with mock.patch.object(NotifyBase, "mark_delivered", counted):
        yield recorded
