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
import sys

from apprise.utils.xml import flatten_xml_response

KEEP_MAP = {
    "RequestId": "request_id",
    "MessageId": "message_id",
}


def test_flatten_xml_response_extracts_mapped_tags():
    """Tags listed in keep_map are pulled out under their mapped key."""
    response = flatten_xml_response(
        """
        <PublishResponse>
            <PublishResult>
                <MessageId>abc-123</MessageId>
            </PublishResult>
            <ResponseMetadata>
                <RequestId>req-456</RequestId>
            </ResponseMetadata>
        </PublishResponse>
        """,
        KEEP_MAP,
    )

    assert response["type"] == "PublishResponse"
    assert response["message_id"] == "abc-123"
    assert response["request_id"] == "req-456"


def test_flatten_xml_response_repeated_tag_keeps_last_value():
    """Repeated mapped tags retain the last value in document order."""
    response = flatten_xml_response(
        "<Response>"
        "<RequestId>first</RequestId>"
        "<RequestId>last</RequestId>"
        "</Response>",
        KEEP_MAP,
    )

    assert response["request_id"] == "last"


def test_flatten_xml_response_strips_root_namespace():
    """A namespace on the root tag doesn't stop tags from being matched."""
    response = flatten_xml_response(
        '<PublishResponse xmlns="http://sns.amazonaws.com/doc/2010-03-31/">'
        "<RequestId>req-456</RequestId>"
        "</PublishResponse>",
        KEEP_MAP,
    )

    assert response["type"] == "PublishResponse"
    assert response["request_id"] == "req-456"


def test_flatten_xml_response_empty_known_tag_is_blank_not_a_crash():
    """A self-closed or empty known tag yields "" instead of raising.

    <Message/> has no .text at all (it's None), and the old
    implementation called .strip() on that None directly.
    """
    response = flatten_xml_response(
        "<ErrorResponse><Message/></ErrorResponse>",
        {"Message": "error_message"},
    )

    assert response["type"] == "ErrorResponse"
    assert response["error_message"] == ""


def test_flatten_xml_response_whitespace_only_tag_is_blank():
    """A tag containing only whitespace is trimmed down to an empty
    string, same as an empty tag."""
    response = flatten_xml_response(
        "<ErrorResponse><Message>   </Message></ErrorResponse>",
        {"Message": "error_message"},
    )

    assert response["error_message"] == ""


def test_flatten_xml_response_survives_deeply_nested_xml():
    """A response nested far past Python's default recursion limit still
    parses instead of raising a RecursionError.

    The old implementation walked the tree with a recursive helper, so
    one recursive call was made per level of nesting.
    """
    depth = sys.getrecursionlimit() + 1000

    xml = ("<a>" * depth) + "leaf-value" + ("</a>" * depth)

    response = flatten_xml_response(xml, {"a": "value"})

    assert response["type"] == "a"
    assert response["value"] == "leaf-value"


def test_flatten_xml_response_invalid_xml_returns_defaults():
    """Malformed XML falls back to the defaults instead of raising."""
    response = flatten_xml_response(
        "<Bad Response>", KEEP_MAP, defaults={"request_id": None}
    )

    assert response["type"] is None
    assert response["request_id"] is None


def test_flatten_xml_response_non_string_input_returns_defaults():
    """A non-string response (e.g. None, after a connection failure)
    falls back to the defaults instead of raising."""
    response = flatten_xml_response(
        None, KEEP_MAP, defaults={"request_id": None}
    )

    assert response["type"] is None
    assert response["request_id"] is None


def test_flatten_xml_response_defaults_not_mutated():
    """The defaults dictionary passed in is never modified in place."""
    defaults = {"request_id": None}

    response = flatten_xml_response(
        "<PublishResponse><RequestId>req-456</RequestId></PublishResponse>",
        KEEP_MAP,
        defaults=defaults,
    )

    assert defaults == {"request_id": None}
    assert response["request_id"] == "req-456"


def test_flatten_xml_response_unmapped_tags_are_ignored():
    """Tags that aren't listed in keep_map are left out of the result."""
    response = flatten_xml_response(
        "<PublishResponse><Extra>ignored</Extra></PublishResponse>",
        KEEP_MAP,
    )

    assert "Extra" not in response
    assert "extra" not in response
