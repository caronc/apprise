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

from inspect import cleandoc
from json import loads

# Disable logging for a cleaner testing output
import logging
import os

import pytest
import requests

from apprise import Apprise
from apprise.config import ConfigBase

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")


@pytest.fixture
def request_mock(mocker):
    """Prepare requests mock."""
    mock_post = mocker.patch("requests.post")
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_post.return_value.content = ""
    return mock_post


def test_plugin_title_maxlen(request_mock):
    """Plugin title maxlen blending support."""
    # Load our configuration
    result, _ = ConfigBase.config_parse_yaml(cleandoc("""
    urls:

      # Our JSON plugin allows for a title definition; we enforce a html format
      - json://user:pass@example.ca?format=html
      # Telegram has a title_maxlen of 0
      - tgram://123456789:AABCeFGhIJKLmnOPqrStUvWxYZ12345678U/987654321
    """))

    # Verify we loaded correctly
    assert isinstance(result, list)
    assert len(result) == 2
    assert len(result[0].tags) == 0

    aobj = Apprise()
    aobj.add(result)
    assert len(aobj) == 2

    title = "Hello World"
    body = "Foo Bar"
    assert aobj.notify(title=title, body=body)

    # If a batch, there is only 1 post
    assert request_mock.call_count == 2

    details = request_mock.call_args_list[0]
    assert details[0][0] == "http://example.ca"
    payload = loads(details[1]["data"])
    assert payload["message"] == body
    assert payload["title"] == "Hello World"

    details = request_mock.call_args_list[1]
    assert (
        details[0][0]
        == "https://api.telegram.org/bot123456789:"
        "AABCeFGhIJKLmnOPqrStUvWxYZ12345678U/sendMessage"
    )
    payload = loads(details[1]["data"])
    # HTML in Title is escaped
    assert payload["text"] == "<b>Hello World</b>\r\nFoo Bar"

    # Reset our mock object
    request_mock.reset_mock()
    #
    # Reverse the configuration file and expect the same results
    #
    result, _config = ConfigBase.config_parse_yaml(cleandoc("""
    urls:

      # Telegram has a title_maxlen of 0
      - tgram://123456789:AABCeFGhIJKLmnOPqrStUvWxYZ12345678U/987654321
      # Our JSON plugin allows for a title definition; we enforce a html format
      - json://user:pass@example.ca?format=html
    """))

    # Verify we loaded correctly
    assert isinstance(result, list)
    assert len(result) == 2
    assert len(result[0].tags) == 0

    aobj = Apprise()
    aobj.add(result)
    assert len(aobj) == 2

    title = "Hello World"
    body = "Foo Bar"
    assert aobj.notify(title=title, body=body)

    # If a batch, there is only 1 post
    assert request_mock.call_count == 2

    details = request_mock.call_args_list[0]
    assert (
        details[0][0]
        == "https://api.telegram.org/bot123456789:"
        "AABCeFGhIJKLmnOPqrStUvWxYZ12345678U/sendMessage"
    )
    payload = loads(details[1]["data"])

    # HTML in Title is escaped
    assert payload["text"] == "<b>Hello World</b>\r\nFoo Bar"

    details = request_mock.call_args_list[1]
    assert details[0][0] == "http://example.ca"
    payload = loads(details[1]["data"])
    assert payload["message"] == body
    assert payload["title"] == "Hello World"
