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

import json

# Disable logging for a cleaner testing output
import logging
import os
from unittest import mock

from helpers import AppriseURLTester
import requests

from apprise import Apprise, AppriseAttachment, NotifyType
from apprise.plugins.custom_json import NotifyJSON

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# Our Testing URLs
apprise_url_tests = (
    (
        "json://:@/",
        {
            "instance": None,
        },
    ),
    (
        "json://",
        {
            "instance": None,
        },
    ),
    (
        "jsons://",
        {
            "instance": None,
        },
    ),
    (
        "json://localhost",
        {
            "instance": NotifyJSON,
        },
    ),
    (
        "json://user@localhost?method=invalid",
        {
            "instance": TypeError,
        },
    ),
    (
        "json://user:pass@localhost",
        {
            "instance": NotifyJSON,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "json://user:****@localhost",
        },
    ),
    (
        "json://user@localhost",
        {
            "instance": NotifyJSON,
        },
    ),
    # Test method variations
    (
        "json://user@localhost?method=put",
        {
            "instance": NotifyJSON,
        },
    ),
    (
        "json://user@localhost?method=get",
        {
            "instance": NotifyJSON,
        },
    ),
    (
        "json://user@localhost?method=post",
        {
            "instance": NotifyJSON,
        },
    ),
    (
        "json://user@localhost?method=head",
        {
            "instance": NotifyJSON,
        },
    ),
    (
        "json://user@localhost?method=delete",
        {
            "instance": NotifyJSON,
        },
    ),
    (
        "json://user@localhost?method=patch",
        {
            "instance": NotifyJSON,
        },
    ),
    # Continue testing other cases
    (
        "json://localhost:8080",
        {
            "instance": NotifyJSON,
        },
    ),
    (
        "json://user:pass@localhost:8080",
        {
            "instance": NotifyJSON,
        },
    ),
    (
        "jsons://localhost",
        {
            "instance": NotifyJSON,
        },
    ),
    (
        "jsons://user:pass@localhost",
        {
            "instance": NotifyJSON,
        },
    ),
    (
        "jsons://localhost:8080/path/",
        {
            "instance": NotifyJSON,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "jsons://localhost:8080/path/",
        },
    ),
    # Test our GET params
    (
        "json://localhost:8080/path?-ParamA=Value",
        {
            "instance": NotifyJSON,
        },
    ),
    (
        "jsons://user:password@localhost:8080",
        {
            "instance": NotifyJSON,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "jsons://user:****@localhost:8080",
        },
    ),
    # Test our Headers
    (
        "json://localhost:8080/path?+HeaderKey=HeaderValue",
        {
            "instance": NotifyJSON,
        },
    ),
    (
        "json://user:pass@localhost:8081",
        {
            "instance": NotifyJSON,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "json://user:pass@localhost:8082",
        {
            "instance": NotifyJSON,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "json://user:pass@localhost:8083",
        {
            "instance": NotifyJSON,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_custom_json_urls():
    """NotifyJSON() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
@mock.patch("requests.get")
def test_plugin_custom_json_edge_cases(mock_get, mock_post):
    """NotifyJSON() Edge Cases."""

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response
    mock_get.return_value = response

    # This string also tests that type is set to nothing
    results = NotifyJSON.parse_url(
        "json://localhost:8080/command?"
        ":message=msg&:test=value&method=GET"
        "&:type="
    )

    assert isinstance(results, dict)
    assert results["user"] is None
    assert results["password"] is None
    assert results["port"] == 8080
    assert results["host"] == "localhost"
    assert results["fullpath"] == "/command"
    assert results["path"] == "/"
    assert results["query"] == "command"
    assert results["schema"] == "json"
    assert results["url"] == "json://localhost:8080/command"
    assert isinstance(results["qsd:"], dict)
    assert results["qsd:"]["message"] == "msg"
    # empty special mapping
    assert results["qsd:"]["type"] == ""

    instance = NotifyJSON(**results)
    assert isinstance(instance, NotifyJSON)

    response = instance.send(title="title", body="body")
    assert response is True
    assert mock_post.call_count == 0
    assert mock_get.call_count == 1

    details = mock_get.call_args_list[0]
    assert details[0][0] == "http://localhost:8080/command"
    assert "title" in details[1]["data"]
    dataset = json.loads(details[1]["data"])
    assert dataset["title"] == "title"
    assert "message" not in dataset
    assert "msg" in dataset
    # type was set to nothing which implies it should be removed
    assert "type" not in dataset
    # message over-ride was provided; the body is now in `msg` and not
    # `message`
    assert dataset["msg"] == "body"

    assert "test" in dataset
    assert dataset["test"] == "value"

    assert instance.url(privacy=False).startswith(
        "json://localhost:8080/command?"
    )

    # Generate a new URL based on our last and verify key values are the same
    new_results = NotifyJSON.parse_url(instance.url(safe=False))
    for k in (
        "user",
        "password",
        "port",
        "host",
        "fullpath",
        "path",
        "query",
        "schema",
        "url",
        "method",
    ):
        assert new_results[k] == results[k]


@mock.patch("requests.post")
def test_notify_json_plugin_attachments(mock_post):
    """NotifyJSON() Attachments."""

    okay_response = requests.Request()
    okay_response.status_code = requests.codes.ok
    okay_response.content = ""

    # Assign our mock object our return value
    mock_post.return_value = okay_response

    obj = Apprise.instantiate("json://localhost.localdomain/")
    assert isinstance(obj, NotifyJSON)

    # Test Valid Attachment
    path = os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    attach = AppriseAttachment(path)
    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is True
    )

    # Test invalid attachment
    path = os.path.join(TEST_VAR_DIR, "/invalid/path/to/an/invalid/file.jpg")
    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=path,
        )
        is False
    )

    # Test Valid Attachment (load 3)
    path = (
        os.path.join(TEST_VAR_DIR, "apprise-test.gif"),
        os.path.join(TEST_VAR_DIR, "apprise-test.gif"),
        os.path.join(TEST_VAR_DIR, "apprise-test.gif"),
    )
    attach = AppriseAttachment(path)

    # Return our good configuration
    mock_post.side_effect = None
    mock_post.return_value = okay_response
    with mock.patch("builtins.open", side_effect=OSError()):
        # We can't send the message we can't open the attachment for reading
        assert (
            obj.notify(
                body="body",
                title="title",
                notify_type=NotifyType.INFO,
                attach=attach,
            )
            is False
        )

    # test the handling of our batch modes
    obj = Apprise.instantiate("json://no-reply@example.com/")
    assert isinstance(obj, NotifyJSON)

    # Now send an attachment normally without issues
    mock_post.reset_mock()
    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is True
    )
    assert mock_post.call_count == 1


# Based on incomming webhook details defined here:
# https://kb.synology.com/en-au/DSM/help/Chat/chat_integration
@mock.patch("requests.post")
def test_plugin_custom_form_for_synology(mock_post):
    """NotifyJSON() Synology Chat Test Case."""

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    # This is rather confusing, it may be easier to leverage the
    # synology:// and synologys:// plugins instead, but this is just to prove
    # that the same message can be sent using the json:// plugin.

    results = NotifyJSON.parse_url(
        "jsons://localhost:8081/webapi/entry.cgi?"
        "-api=SYNO.Chat.External&-method=incoming&-version=2&-token=abc123"
        "&:message=text&:version=&:type=&:title=&:attachments"
        "&:file_url=https://i.redd.it/my2t4d2fx0u31.jpg"
    )

    assert isinstance(results, dict)
    assert results["user"] is None
    assert results["password"] is None
    assert results["port"] == 8081
    assert results["host"] == "localhost"
    assert results["fullpath"] == "/webapi/entry.cgi"
    assert results["path"] == "/webapi/"
    assert results["query"] == "entry.cgi"
    assert results["schema"] == "jsons"
    assert results["url"] == "jsons://localhost:8081/webapi/entry.cgi"
    assert isinstance(results["qsd:"], dict)
    # Header Entries
    assert results["qsd-"]["api"] == "SYNO.Chat.External"
    assert results["qsd-"]["method"] == "incoming"
    assert results["qsd-"]["version"] == "2"
    assert results["qsd-"]["token"] == "abc123"

    instance = NotifyJSON(**results)
    assert isinstance(instance, NotifyJSON)

    response = instance.send(title="title", body="body")
    assert response is True
    assert mock_post.call_count == 1

    details = mock_post.call_args_list[0]
    assert details[0][0] == "https://localhost:8081/webapi/entry.cgi"

    params = details[1]["params"]
    assert params.get("api") == "SYNO.Chat.External"
    assert params.get("method") == "incoming"
    assert params.get("version") == "2"
    assert params.get("token") == "abc123"

    payload = json.loads(details[1]["data"])
    assert "version" not in payload
    assert "title" not in payload
    assert "message" not in payload
    assert "type" not in payload
    assert payload.get("text") == "body"
    assert payload.get("file_url") == "https://i.redd.it/my2t4d2fx0u31.jpg"
