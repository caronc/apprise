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
import re
from unittest import mock

from helpers import AppriseURLTester
import requests

from apprise import Apprise, AppriseAttachment, NotifyType
from apprise.plugins.custom_xml import NotifyXML

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")


# Our Testing URLs
apprise_url_tests = (
    (
        "xml://:@/",
        {
            "instance": None,
        },
    ),
    (
        "xml://",
        {
            "instance": None,
        },
    ),
    (
        "xmls://",
        {
            "instance": None,
        },
    ),
    (
        "xml://localhost",
        {
            "instance": NotifyXML,
        },
    ),
    (
        "xml://user@localhost",
        {
            "instance": NotifyXML,
        },
    ),
    (
        "xml://user@localhost?method=invalid",
        {
            "instance": TypeError,
        },
    ),
    (
        "xml://user:pass@localhost",
        {
            "instance": NotifyXML,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "xml://user:****@localhost",
        },
    ),
    # Test method variations
    (
        "xml://user@localhost?method=put",
        {
            "instance": NotifyXML,
        },
    ),
    (
        "xml://user@localhost?method=get",
        {
            "instance": NotifyXML,
        },
    ),
    (
        "xml://user@localhost?method=post",
        {
            "instance": NotifyXML,
        },
    ),
    (
        "xml://user@localhost?method=head",
        {
            "instance": NotifyXML,
        },
    ),
    (
        "xml://user@localhost?method=delete",
        {
            "instance": NotifyXML,
        },
    ),
    (
        "xml://user@localhost?method=patch",
        {
            "instance": NotifyXML,
        },
    ),
    # Continue testing other cases
    (
        "xml://localhost:8080",
        {
            "instance": NotifyXML,
        },
    ),
    (
        "xml://user:pass@localhost:8080",
        {
            "instance": NotifyXML,
        },
    ),
    (
        "xmls://localhost",
        {
            "instance": NotifyXML,
        },
    ),
    (
        "xmls://user:pass@localhost",
        {
            "instance": NotifyXML,
        },
    ),
    # Continue testing other cases
    (
        "xml://localhost:8080",
        {
            "instance": NotifyXML,
        },
    ),
    (
        "xml://user:pass@localhost:8080",
        {
            "instance": NotifyXML,
        },
    ),
    (
        "xml://localhost",
        {
            "instance": NotifyXML,
        },
    ),
    (
        "xmls://user:pass@localhost",
        {
            "instance": NotifyXML,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "xmls://user:****@localhost",
        },
    ),
    (
        "xml://user@localhost:8080/path/",
        {
            "instance": NotifyXML,
            "privacy_url": "xml://user@localhost:8080/path",
        },
    ),
    (
        "xmls://localhost:8080/path/",
        {
            "instance": NotifyXML,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "xmls://localhost:8080/path/",
        },
    ),
    (
        "xmls://user:pass@localhost:8080",
        {
            "instance": NotifyXML,
        },
    ),
    # Test our GET params
    (
        "xml://localhost:8080/path?-ParamA=Value",
        {
            "instance": NotifyXML,
        },
    ),
    # Test our Headers
    (
        "xml://localhost:8080/path?+HeaderKey=HeaderValue",
        {
            "instance": NotifyXML,
        },
    ),
    (
        "xml://user:pass@localhost:8081",
        {
            "instance": NotifyXML,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "xml://user:pass@localhost:8082",
        {
            "instance": NotifyXML,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "xml://user:pass@localhost:8083",
        {
            "instance": NotifyXML,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_custom_xml_urls():
    """NotifyXML() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_notify_xml_plugin_attachments(mock_post):
    """NotifyXML() Attachments."""

    okay_response = requests.Request()
    okay_response.status_code = requests.codes.ok
    okay_response.content = ""

    # Assign our mock object our return value
    mock_post.return_value = okay_response

    obj = Apprise.instantiate("xml://localhost.localdomain/")
    assert isinstance(obj, NotifyXML)

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
    obj = Apprise.instantiate("xml://no-reply@example.com/")
    assert isinstance(obj, NotifyXML)

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


@mock.patch("requests.post")
@mock.patch("requests.get")
def test_plugin_custom_xml_edge_cases(mock_get, mock_post):
    """NotifyXML() Edge Cases."""

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response
    mock_get.return_value = response

    results = NotifyXML.parse_url(
        "xml://localhost:8080/command?:Message=Body&method=GET"
        "&:Key=value&:,=invalid&:MessageType="
    )

    assert isinstance(results, dict)
    assert results["user"] is None
    assert results["password"] is None
    assert results["port"] == 8080
    assert results["host"] == "localhost"
    assert results["fullpath"] == "/command"
    assert results["path"] == "/"
    assert results["query"] == "command"
    assert results["schema"] == "xml"
    assert results["url"] == "xml://localhost:8080/command"
    assert isinstance(results["qsd:"], dict)
    assert results["qsd:"]["Message"] == "Body"
    assert results["qsd:"]["Key"] == "value"
    assert results["qsd:"][","] == "invalid"

    instance = NotifyXML(**results)
    assert isinstance(instance, NotifyXML)

    # XSD URL is disabled due to custom formatting
    assert instance.xsd_url is None

    response = instance.send(title="title", body="body")
    assert response is True
    assert mock_post.call_count == 0
    assert mock_get.call_count == 1

    details = mock_get.call_args_list[0]
    assert details[0][0] == "http://localhost:8080/command"
    assert instance.url(privacy=False).startswith(
        "xml://localhost:8080/command?"
    )

    # Generate a new URL based on our last and verify key values are the same
    new_results = NotifyXML.parse_url(instance.url(safe=False))
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

    # Test our data set for our key/value pair
    assert re.search(r"<Version>[1-9]+\.[0-9]+</Version>", details[1]["data"])
    assert re.search("<Subject>title</Subject>", details[1]["data"])

    assert re.search("<Message>test</Message>", details[1]["data"]) is None
    assert re.search("<Message>", details[1]["data"]) is None
    # MessageType was removed from the payload
    assert re.search("<MessageType>", details[1]["data"]) is None
    # However we can find our mapped Message to the new value Body
    assert re.search("<Body>body</Body>", details[1]["data"])
    # Custom entry
    assert re.search("<Key>value</Key>", details[1]["data"])

    mock_post.reset_mock()
    mock_get.reset_mock()

    results = NotifyXML.parse_url(
        "xml://localhost:8081/command?method=POST&:New=Value"
    )

    assert isinstance(results, dict)
    assert results["user"] is None
    assert results["password"] is None
    assert results["port"] == 8081
    assert results["host"] == "localhost"
    assert results["fullpath"] == "/command"
    assert results["path"] == "/"
    assert results["query"] == "command"
    assert results["schema"] == "xml"
    assert results["url"] == "xml://localhost:8081/command"
    assert isinstance(results["qsd:"], dict)
    assert results["qsd:"]["New"] == "Value"

    instance = NotifyXML(**results)
    assert isinstance(instance, NotifyXML)

    # XSD URL is disabled due to custom formatting
    assert instance.xsd_url is None

    response = instance.send(title="title", body="body")
    assert response is True
    assert mock_post.call_count == 1
    assert mock_get.call_count == 0

    details = mock_post.call_args_list[0]
    assert details[0][0] == "http://localhost:8081/command"
    assert instance.url(privacy=False).startswith(
        "xml://localhost:8081/command?"
    )

    # Generate a new URL based on our last and verify key values are the same
    new_results = NotifyXML.parse_url(instance.url(safe=False))
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

    # Test our data set for our key/value pair
    assert re.search(r"<Version>[1-9]+\.[0-9]+</Version>", details[1]["data"])
    assert re.search(r"<MessageType>info</MessageType>", details[1]["data"])
    assert re.search(r"<Subject>title</Subject>", details[1]["data"])
    # No over-ride
    assert re.search(r"<Message>body</Message>", details[1]["data"])

    mock_post.reset_mock()
    mock_get.reset_mock()

    results = NotifyXML.parse_url(
        "xmls://localhost?method=POST&:Message=Body&:Subject=Title&:Version"
    )

    assert isinstance(results, dict)
    assert results["user"] is None
    assert results["password"] is None
    assert results["port"] is None
    assert results["host"] == "localhost"
    assert results["fullpath"] is None
    assert results["path"] is None
    assert results["query"] is None
    assert results["schema"] == "xmls"
    assert results["url"] == "xmls://localhost"
    assert isinstance(results["qsd:"], dict)
    assert results["qsd:"]["Version"] == ""
    assert results["qsd:"]["Message"] == "Body"
    assert results["qsd:"]["Subject"] == "Title"

    instance = NotifyXML(**results)
    assert isinstance(instance, NotifyXML)

    # XSD URL is disabled due to custom formatting
    assert instance.xsd_url is None

    response = instance.send(title="title", body="body")
    assert response is True
    assert mock_post.call_count == 1
    assert mock_get.call_count == 0

    details = mock_post.call_args_list[0]
    assert details[0][0] == "https://localhost"
    assert instance.url(privacy=False).startswith("xmls://localhost")

    # Generate a new URL based on our last and verify key values are the same
    new_results = NotifyXML.parse_url(instance.url(safe=False))

    # Test that the Version has been dropped
    assert (
        re.search(r"<Version>[1-9]+\.[0-9]+</Version>", details[1]["data"])
        is None
    )

    # Test our data set for our key/value pair
    assert re.search(r"<MessageType>info</MessageType>", details[1]["data"])

    # Subject is swapped for Title
    assert re.search(r"<Subject>title</Subject>", details[1]["data"]) is None
    assert re.search(r"<Title>title</Title>", details[1]["data"])

    # Message is swapped for Body
    assert re.search(r"<Message>body</Message>", details[1]["data"]) is None
    assert re.search(r"<Body>body</Body>", details[1]["data"])
