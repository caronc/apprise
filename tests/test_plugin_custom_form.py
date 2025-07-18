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

# Disable logging for a cleaner testing output
import logging
import os
from unittest import mock

from helpers import AppriseURLTester
import requests

from apprise import Apprise, AppriseAttachment, NotifyType
from apprise.plugins.custom_form import NotifyForm

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# Our Testing URLs
apprise_url_tests = (
    (
        "form://:@/",
        {
            "instance": None,
        },
    ),
    (
        "form://",
        {
            "instance": None,
        },
    ),
    (
        "forms://",
        {
            "instance": None,
        },
    ),
    (
        "form://localhost",
        {
            "instance": NotifyForm,
        },
    ),
    (
        "form://user@localhost?method=invalid",
        {
            "instance": TypeError,
        },
    ),
    (
        "form://user:pass@localhost",
        {
            "instance": NotifyForm,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "form://user:****@localhost",
        },
    ),
    (
        "form://user@localhost",
        {
            "instance": NotifyForm,
        },
    ),
    # Test method variations
    (
        "form://user@localhost?method=put",
        {
            "instance": NotifyForm,
        },
    ),
    (
        "form://user@localhost?method=get",
        {
            "instance": NotifyForm,
        },
    ),
    (
        "form://user@localhost?method=post",
        {
            "instance": NotifyForm,
        },
    ),
    (
        "form://user@localhost?method=head",
        {
            "instance": NotifyForm,
        },
    ),
    (
        "form://user@localhost?method=delete",
        {
            "instance": NotifyForm,
        },
    ),
    (
        "form://user@localhost?method=patch",
        {
            "instance": NotifyForm,
        },
    ),
    # Custom payload options
    (
        "form://localhost:8080?:key=value&:key2=value2",
        {
            "instance": NotifyForm,
        },
    ),
    # Continue testing other cases
    (
        "form://localhost:8080",
        {
            "instance": NotifyForm,
        },
    ),
    (
        "form://user:pass@localhost:8080",
        {
            "instance": NotifyForm,
        },
    ),
    (
        "forms://localhost",
        {
            "instance": NotifyForm,
        },
    ),
    (
        "forms://user:pass@localhost",
        {
            "instance": NotifyForm,
        },
    ),
    (
        "forms://localhost:8080/path/",
        {
            "instance": NotifyForm,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "forms://localhost:8080/path/",
        },
    ),
    (
        "forms://user:password@localhost:8080",
        {
            "instance": NotifyForm,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "forms://user:****@localhost:8080",
        },
    ),
    # Test our GET params
    (
        "form://localhost:8080/path?-ParamA=Value",
        {
            "instance": NotifyForm,
        },
    ),
    # Test our Headers
    (
        "form://localhost:8080/path?+HeaderKey=HeaderValue",
        {
            "instance": NotifyForm,
        },
    ),
    (
        "form://user:pass@localhost:8081",
        {
            "instance": NotifyForm,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "form://user:pass@localhost:8082",
        {
            "instance": NotifyForm,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "form://user:pass@localhost:8083",
        {
            "instance": NotifyForm,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_custom_form_urls():
    """NotifyForm() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_custom_form_attachments(mock_post):
    """NotifyForm() Attachments."""

    okay_response = requests.Request()
    okay_response.status_code = requests.codes.ok
    okay_response.content = ""

    # Assign our mock object our return value
    mock_post.return_value = okay_response

    obj = Apprise.instantiate("form://user@localhost.localdomain/?method=post")
    assert isinstance(obj, NotifyForm)

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

    mock_post.return_value = None
    mock_post.side_effect = OSError()
    # We can't send the message if we can't read the attachment
    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=attach,
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

    # Fail on the 2nd attempt (but not the first)
    with mock.patch("builtins.open", side_effect=[None, OSError(), None]):
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

    # Test file exception handling when performing post
    mock_post.return_value = None
    mock_post.side_effect = OSError()
    assert (
        obj.notify(
            body="body",
            title="title",
            notify_type=NotifyType.INFO,
            attach=attach,
        )
        is False
    )

    #
    # Test attach-as
    #

    # Assign our mock object our return value
    mock_post.return_value = okay_response
    mock_post.side_effect = None

    obj = Apprise.instantiate(
        "form://user@localhost.localdomain/?attach-as=file"
    )
    assert isinstance(obj, NotifyForm)

    # Test Single Valid Attachment
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

    # Test Valid Attachment (load 3) (produces a warning)
    path = (
        os.path.join(TEST_VAR_DIR, "apprise-test.gif"),
        os.path.join(TEST_VAR_DIR, "apprise-test.gif"),
        os.path.join(TEST_VAR_DIR, "apprise-test.gif"),
    )
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

    # Test our other variations of accepted values
    # we support *, :, ?, ., +, %, and $
    for attach_as in (
        "file*",
        "*file",
        "file*file",
        "file:",
        ":file",
        "file:file",
        "file?",
        "?file",
        "file?file",
        "file.",
        ".file",
        "file.file",
        "file+",
        "+file",
        "file+file",
        "file$",
        "$file",
        "file$file",
    ):

        obj = Apprise.instantiate(
            f"form://user@localhost.localdomain/?attach-as={attach_as}"
        )
        assert isinstance(obj, NotifyForm)

        # Test Single Valid Attachment
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

        # Test Valid Attachment (load 3) (produces a warning)
        path = (
            os.path.join(TEST_VAR_DIR, "apprise-test.gif"),
            os.path.join(TEST_VAR_DIR, "apprise-test.gif"),
            os.path.join(TEST_VAR_DIR, "apprise-test.gif"),
        )
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

    # Test invalid attach-as input
    obj = Apprise.instantiate("form://user@localhost.localdomain/?attach-as={")
    assert obj is None


@mock.patch("requests.post")
@mock.patch("requests.get")
def test_plugin_custom_form_edge_cases(mock_get, mock_post):
    """NotifyForm() Edge Cases."""

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response
    mock_get.return_value = response

    results = NotifyForm.parse_url(
        "form://localhost:8080/command?:message=msg&:abcd=test&method=POST"
    )

    assert isinstance(results, dict)
    assert results["user"] is None
    assert results["password"] is None
    assert results["port"] == 8080
    assert results["host"] == "localhost"
    assert results["fullpath"] == "/command"
    assert results["path"] == "/"
    assert results["query"] == "command"
    assert results["schema"] == "form"
    assert results["url"] == "form://localhost:8080/command"
    assert isinstance(results["qsd:"], dict) is True
    assert results["qsd:"]["abcd"] == "test"
    assert results["qsd:"]["message"] == "msg"

    instance = NotifyForm(**results)
    assert isinstance(instance, NotifyForm)

    response = instance.send(title="title", body="body")
    assert response is True
    assert mock_post.call_count == 1
    assert mock_get.call_count == 0

    details = mock_post.call_args_list[0]
    assert details[0][0] == "http://localhost:8080/command"
    assert "abcd" in details[1]["data"]
    assert details[1]["data"]["abcd"] == "test"
    assert "title" in details[1]["data"]
    assert details[1]["data"]["title"] == "title"
    assert "message" not in details[1]["data"]
    # message over-ride was provided; the body is now in `msg` and not
    # `message`
    assert "msg" in details[1]["data"]
    assert details[1]["data"]["msg"] == "body"

    assert instance.url(privacy=False).startswith(
        "form://localhost:8080/command?"
    )

    # Generate a new URL based on our last and verify key values are the same
    new_results = NotifyForm.parse_url(instance.url(safe=False))
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
        "payload",
        "method",
    ):
        assert new_results[k] == results[k]

    # Reset our mock configuration
    mock_post.reset_mock()
    mock_get.reset_mock()

    results = NotifyForm.parse_url(
        "form://localhost:8080/command?:type=&:message=msg&method=POST"
    )

    assert isinstance(results, dict)
    assert results["user"] is None
    assert results["password"] is None
    assert results["port"] == 8080
    assert results["host"] == "localhost"
    assert results["fullpath"] == "/command"
    assert results["path"] == "/"
    assert results["query"] == "command"
    assert results["schema"] == "form"
    assert results["url"] == "form://localhost:8080/command"
    assert isinstance(results["qsd:"], dict) is True
    assert results["qsd:"]["message"] == "msg"

    instance = NotifyForm(**results)
    assert isinstance(instance, NotifyForm)

    response = instance.send(title="title", body="body")
    assert response is True
    assert mock_post.call_count == 1
    assert mock_get.call_count == 0

    details = mock_post.call_args_list[0]
    assert details[0][0] == "http://localhost:8080/command"
    assert "title" in details[1]["data"]
    assert details[1]["data"]["title"] == "title"

    # type was removed from response object
    assert "type" not in details[1]["data"]

    # message over-ride was provided; the body is now in `msg` and not
    # `message`
    assert details[1]["data"]["msg"] == "body"

    # 'body' is over-ridden by 'test' passed inline with the URL
    assert "message" not in details[1]["data"]
    assert "msg" in details[1]["data"]
    assert details[1]["data"]["msg"] == "body"

    assert instance.url(privacy=False).startswith(
        "form://localhost:8080/command?"
    )

    # Generate a new URL based on our last and verify key values are the same
    new_results = NotifyForm.parse_url(instance.url(safe=False))
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
        "payload",
        "method",
    ):
        assert new_results[k] == results[k]

    # Reset our mock configuration
    mock_post.reset_mock()
    mock_get.reset_mock()

    results = NotifyForm.parse_url(
        "form://localhost:8080/command?:message=test&method=GET"
    )

    assert isinstance(results, dict)
    assert results["user"] is None
    assert results["password"] is None
    assert results["port"] == 8080
    assert results["host"] == "localhost"
    assert results["fullpath"] == "/command"
    assert results["path"] == "/"
    assert results["query"] == "command"
    assert results["schema"] == "form"
    assert results["url"] == "form://localhost:8080/command"
    assert isinstance(results["qsd:"], dict) is True
    assert results["qsd:"]["message"] == "test"

    instance = NotifyForm(**results)
    assert isinstance(instance, NotifyForm)

    response = instance.send(title="title", body="body")
    assert response is True
    assert mock_post.call_count == 0
    assert mock_get.call_count == 1

    details = mock_get.call_args_list[0]
    assert details[0][0] == "http://localhost:8080/command"

    assert "title" in details[1]["params"]
    assert details[1]["params"]["title"] == "title"
    # 'body' is over-ridden by 'test' passed inline with the URL
    assert "message" not in details[1]["params"]
    assert "test" in details[1]["params"]
    assert details[1]["params"]["test"] == "body"

    assert instance.url(privacy=False).startswith(
        "form://localhost:8080/command?"
    )

    # Generate a new URL based on our last and verify key values are the same
    new_results = NotifyForm.parse_url(instance.url(safe=False))
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
        "payload",
        "method",
    ):
        assert new_results[k] == results[k]
