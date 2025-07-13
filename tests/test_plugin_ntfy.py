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
import re
from unittest import mock

from helpers import AppriseURLTester
import requests

import apprise
from apprise.plugins.ntfy import NotifyNtfy, NtfyPriority

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# For testing our return response
GOOD_RESPONSE_TEXT = {
    "code": "0",
    "error": "success",
}

# Our Testing URLs
apprise_url_tests = (
    (
        "ntfy://",
        {
            # Initializes okay (as cloud mode) but has no topics to notify
            "instance": NotifyNtfy,
            # invalid topics specified (nothing to notify)
            # as a result the response type will be false
            "requests_response_text": GOOD_RESPONSE_TEXT,
            "response": False,
        },
    ),
    (
        "ntfys://",
        {
            # Initializes okay (as cloud mode) but has no topics to notify
            "instance": NotifyNtfy,
            # invalid topics specified (nothing to notify)
            # as a result the response type will be false
            "requests_response_text": GOOD_RESPONSE_TEXT,
            "response": False,
        },
    ),
    (
        "ntfy://:@/",
        {
            # Initializes okay (as cloud mode) but has no topics to notify
            "instance": NotifyNtfy,
            # invalid topics specified (nothing to notify)
            # as a result the response type will be false
            "requests_response_text": GOOD_RESPONSE_TEXT,
            "response": False,
        },
    ),
    # No topics
    (
        "ntfy://user:pass@localhost?mode=private",
        {
            "instance": NotifyNtfy,
            # invalid topics specified (nothing to notify)
            # as a result the response type will be false
            "requests_response_text": GOOD_RESPONSE_TEXT,
            "response": False,
        },
    ),
    # No valid topics
    (
        "ntfy://user:pass@localhost/#/!/@",
        {
            "instance": NotifyNtfy,
            # invalid topics specified (nothing to notify)
            # as a result the response type will be false
            "requests_response_text": GOOD_RESPONSE_TEXT,
            "response": False,
        },
    ),
    # user/pass combos
    (
        "ntfy://user@localhost/topic/",
        {
            "instance": NotifyNtfy,
            "requests_response_text": GOOD_RESPONSE_TEXT,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "ntfy://user@localhost/topic",
        },
    ),
    # Ntfy cloud mode (enforced)
    (
        "ntfy://ntfy.sh/topic1/topic2/",
        {
            "instance": NotifyNtfy,
            "requests_response_text": GOOD_RESPONSE_TEXT,
        },
    ),
    # No user/pass combo
    (
        "ntfy://localhost/topic1/topic2/",
        {
            "instance": NotifyNtfy,
            "requests_response_text": GOOD_RESPONSE_TEXT,
        },
    ),
    # A Email Testing
    (
        "ntfy://localhost/topic1/?email=user@gmail.com",
        {
            "instance": NotifyNtfy,
            "requests_response_text": GOOD_RESPONSE_TEXT,
        },
    ),
    # Tags
    (
        "ntfy://localhost/topic1/?tags=tag1,tag2,tag3",
        {
            "instance": NotifyNtfy,
            "requests_response_text": GOOD_RESPONSE_TEXT,
        },
    ),
    # Delay
    (
        "ntfy://localhost/topic1/?delay=3600",
        {
            "instance": NotifyNtfy,
            "requests_response_text": GOOD_RESPONSE_TEXT,
        },
    ),
    # Title
    (
        "ntfy://localhost/topic1/?title=A%20Great%20Title",
        {
            "instance": NotifyNtfy,
            "requests_response_text": GOOD_RESPONSE_TEXT,
        },
    ),
    # Click
    (
        "ntfy://localhost/topic1/?click=yes",
        {
            "instance": NotifyNtfy,
            "requests_response_text": GOOD_RESPONSE_TEXT,
        },
    ),
    # Email
    (
        "ntfy://localhost/topic1/?email=user@example.com",
        {
            "instance": NotifyNtfy,
            "requests_response_text": GOOD_RESPONSE_TEXT,
        },
    ),
    # No images
    (
        "ntfy://localhost/topic1/?image=False",
        {
            "instance": NotifyNtfy,
            "requests_response_text": GOOD_RESPONSE_TEXT,
        },
    ),
    # Over-ride Image Path
    (
        "ntfy://localhost/topic1/?avatar_url=ttp://localhost/test.jpg",
        {
            "instance": NotifyNtfy,
            "requests_response_text": GOOD_RESPONSE_TEXT,
        },
    ),
    # Attach
    (
        "ntfy://localhost/topic1/?attach=http://example.com/file.jpg",
        {
            "instance": NotifyNtfy,
            "requests_response_text": GOOD_RESPONSE_TEXT,
        },
    ),
    # Attach with filename over-ride
    (
        (
            "ntfy://localhost/topic1/"
            "?attach=http://example.com/file.jpg&filename=smoke.jpg"
        ),
        {"instance": NotifyNtfy, "requests_response_text": GOOD_RESPONSE_TEXT},
    ),
    # Attach with bad url
    (
        "ntfy://localhost/topic1/?attach=http://-%20",
        {
            "instance": NotifyNtfy,
            "requests_response_text": GOOD_RESPONSE_TEXT,
        },
    ),
    # Auth Token Types (tk_ gets detected as a auth=token)
    (
        "ntfy://tk_abcd123456@localhost/topic1",
        {
            "instance": NotifyNtfy,
            "requests_response_text": GOOD_RESPONSE_TEXT,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "ntfy://t...6@localhost/topic1",
        },
    ),
    # Force an auth token since lack of tk_ prevents auto-detection
    (
        "ntfy://abcd123456@localhost/topic1?auth=token",
        {
            "instance": NotifyNtfy,
            "requests_response_text": GOOD_RESPONSE_TEXT,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "ntfy://a...6@localhost/topic1",
        },
    ),
    # Force an auth token since lack of tk_ prevents auto-detection
    (
        "ntfy://:abcd123456@localhost/topic1?auth=token",
        {
            "instance": NotifyNtfy,
            "requests_response_text": GOOD_RESPONSE_TEXT,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "ntfy://a...6@localhost/topic1",
        },
    ),
    # Token detection already implied when token keyword is set
    (
        "ntfy://localhost/topic1?token=abc1234",
        {
            "instance": NotifyNtfy,
            "requests_response_text": GOOD_RESPONSE_TEXT,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "ntfy://a...4@localhost/topic1",
        },
    ),
    # Token enforced, but since a user/pass provided, only the pass is kept
    (
        "ntfy://user:token@localhost/topic1?auth=token",
        {
            "instance": NotifyNtfy,
            "requests_response_text": GOOD_RESPONSE_TEXT,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "ntfy://t...n@localhost/topic1",
        },
    ),
    # Token mode force, but there was no token provided
    (
        "ntfy://localhost/topic1?auth=token",
        {
            "instance": NotifyNtfy,
            # We'll out-right fail to send the notification
            "response": False,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "ntfy://localhost/topic1",
        },
    ),
    # Priority
    (
        "ntfy://localhost/topic1/?priority=default",
        {
            "instance": NotifyNtfy,
            "requests_response_text": GOOD_RESPONSE_TEXT,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "ntfy://localhost/topic1",
        },
    ),
    # Priority higher
    (
        "ntfy://localhost/topic1/?priority=high",
        {
            "instance": NotifyNtfy,
            "requests_response_text": GOOD_RESPONSE_TEXT,
        },
    ),
    # A topic and port identifier
    (
        "ntfy://user:pass@localhost:8080/topic/",
        {
            "instance": NotifyNtfy,
            # The response text is expected to be the following on a success
            "requests_response_text": GOOD_RESPONSE_TEXT,
        },
    ),
    # A topic (using the to=)
    (
        "ntfys://user:pass@localhost?to=topic",
        {
            "instance": NotifyNtfy,
            # The response text is expected to be the following on a success
            "requests_response_text": GOOD_RESPONSE_TEXT,
        },
    ),
    (
        "https://just/a/random/host/that/means/nothing",
        {
            # Nothing transpires from this
            "instance": None
        },
    ),
    # reference the ntfy.sh url
    (
        "https://ntfy.sh?to=topic",
        {
            "instance": NotifyNtfy,
            # The response text is expected to be the following on a success
            "requests_response_text": GOOD_RESPONSE_TEXT,
        },
    ),
    # Several topics
    (
        "ntfy://user:pass@topic1/topic2/topic3/?mode=cloud",
        {
            "instance": NotifyNtfy,
            # The response text is expected to be the following on a success
            "requests_response_text": GOOD_RESPONSE_TEXT,
        },
    ),
    # Several topics (but do not add ntfy.sh)
    (
        "ntfy://user:pass@ntfy.sh/topic1/topic2/?mode=cloud",
        {
            "instance": NotifyNtfy,
            # The response text is expected to be the following on a success
            "requests_response_text": GOOD_RESPONSE_TEXT,
        },
    ),
    (
        "ntfys://user:web/token@localhost/topic/?mode=invalid",
        {
            # Invalid mode
            "instance": TypeError,
        },
    ),
    (
        "ntfys://token@localhost/topic/?auth=invalid",
        {
            # Invalid Authentication type
            "instance": TypeError,
        },
    ),
    # Invalid hostname on localhost/private mode
    (
        "ntfys://user:web@-_/topic1/topic2/?mode=private",
        {
            "instance": None,
        },
    ),
    (
        "ntfy://user:pass@localhost:8089/topic/topic2",
        {
            "instance": NotifyNtfy,
            # force a failure using basic mode
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "ntfy://user:pass@localhost:8082/topic",
        {
            "instance": NotifyNtfy,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
            "requests_response_text": GOOD_RESPONSE_TEXT,
        },
    ),
    (
        "ntfy://user:pass@localhost:8083/topic1/topic2/",
        {
            "instance": NotifyNtfy,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
            "requests_response_text": GOOD_RESPONSE_TEXT,
        },
    ),
)


def test_plugin_ntfy_chat_urls():
    """NotifyNtfy() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_ntfy_attachments(mock_post):
    """NotifyNtfy() Attachment Checks."""

    # Prepare Mock return object
    response = mock.Mock()
    response.content = GOOD_RESPONSE_TEXT
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    # Test how the notifications work without attachments as they use the
    # JSON type posting instead

    # Reset our mock object
    mock_post.reset_mock()

    # Prepare our object
    obj = apprise.Apprise.instantiate("ntfy://user:pass@localhost:8080/topic")

    # Send a good attachment
    assert obj.notify(title="hello", body="world")
    assert mock_post.call_count == 1

    assert mock_post.call_args_list[0][0][0] == "http://localhost:8080"

    response = json.loads(mock_post.call_args_list[0][1]["data"])
    assert response["topic"] == "topic"
    assert response["title"] == "hello"
    assert response["message"] == "world"
    assert "attach" not in response

    # Reset our mock object
    mock_post.reset_mock()

    # prepare our attachment
    attach = apprise.AppriseAttachment(
        os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    )

    # Prepare our object
    obj = apprise.Apprise.instantiate("ntfy://user:pass@localhost:8084/topic")

    # Send a good attachment
    assert obj.notify(body="test", attach=attach) is True

    # Test our call count; includes both image and message
    assert mock_post.call_count == 1

    assert mock_post.call_args_list[0][0][0] == "http://localhost:8084/topic"

    assert mock_post.call_args_list[0][1]["params"]["message"] == "test"
    assert "title" not in mock_post.call_args_list[0][1]["params"]
    assert (
        mock_post.call_args_list[0][1]["params"]["filename"]
        == "apprise-test.gif"
    )

    # Reset our mock object
    mock_post.reset_mock()

    # Add another attachment so we drop into the area of the PushBullet code
    # that sends remaining attachments (if more detected)
    attach.add(os.path.join(TEST_VAR_DIR, "apprise-test.png"))

    # Send our attachments
    assert obj.notify(body="test", title="wonderful", attach=attach) is True

    # Test our call count
    assert mock_post.call_count == 2
    # Image + Message sent
    assert mock_post.call_args_list[0][0][0] == "http://localhost:8084/topic"
    assert mock_post.call_args_list[0][1]["params"]["message"] == "test"
    assert mock_post.call_args_list[0][1]["params"]["title"] == "wonderful"
    assert (
        mock_post.call_args_list[0][1]["params"]["filename"]
        == "apprise-test.gif"
    )

    # Image no 2 (no message)
    assert mock_post.call_args_list[1][0][0] == "http://localhost:8084/topic"
    assert "message" not in mock_post.call_args_list[1][1]["params"]
    assert "title" not in mock_post.call_args_list[1][1]["params"]
    assert (
        mock_post.call_args_list[1][1]["params"]["filename"]
        == "apprise-test.png"
    )

    # Reset our mock object
    mock_post.reset_mock()

    # An invalid attachment will cause a failure
    path = os.path.join(TEST_VAR_DIR, "/invalid/path/to/an/invalid/file.jpg")
    attach = apprise.AppriseAttachment(path)
    assert obj.notify(body="test", attach=attach) is False

    # Test our call count
    assert mock_post.call_count == 0

    # prepare our attachment
    attach = apprise.AppriseAttachment(
        os.path.join(TEST_VAR_DIR, "apprise-test.gif")
    )

    # Throw an exception on the first call to requests.post()
    mock_post.return_value = None
    for side_effect in (requests.RequestException(), OSError()):
        mock_post.side_effect = side_effect

        # We'll fail now because of our error handling
        assert obj.send(body="test", attach=attach) is False


@mock.patch("requests.post")
def test_plugin_custom_ntfy_edge_cases(mock_post):
    """NotifyNtfy() Edge Cases."""

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok
    response.content = json.dumps(GOOD_RESPONSE_TEXT)

    # Prepare Mock
    mock_post.return_value = response

    results = NotifyNtfy.parse_url(
        "ntfys://abc---,topic2,~~,,?priority=max&tags=smile,de"
    )

    assert isinstance(results, dict)
    assert results["user"] is None
    assert results["password"] is None
    assert results["port"] is None
    assert results["host"] == "abc---,topic2,~~,,"
    assert results["fullpath"] is None
    assert results["path"] is None
    assert results["query"] is None
    assert results["schema"] == "ntfys"
    assert results["url"] == "ntfys://abc---,topic2,~~,,"
    assert isinstance(results["qsd:"], dict) is True
    assert results["qsd"]["priority"] == "max"
    assert results["qsd"]["tags"] == "smile,de"

    instance = NotifyNtfy(**results)
    assert isinstance(instance, NotifyNtfy)
    assert len(instance.topics) == 2
    assert "abc---" in instance.topics
    assert "topic2" in instance.topics

    results = NotifyNtfy.parse_url(
        "ntfy://localhost/topic1/"
        "?attach=http://example.com/file.jpg&filename=smoke.jpg"
    )

    assert isinstance(results, dict)
    assert results["user"] is None
    assert results["password"] is None
    assert results["port"] is None
    assert results["host"] == "localhost"
    assert results["fullpath"] == "/topic1/"
    assert results["path"] == "/topic1/"
    assert results["query"] is None
    assert results["schema"] == "ntfy"
    assert results["url"] == "ntfy://localhost/topic1/"
    assert results["attach"] == "http://example.com/file.jpg"
    assert results["filename"] == "smoke.jpg"

    instance = NotifyNtfy(**results)
    assert isinstance(instance, NotifyNtfy)
    assert len(instance.topics) == 1
    assert "topic1" in instance.topics

    assert (
        instance.notify(
            body="body", title="title", notify_type=apprise.NotifyType.INFO
        )
        is True
    )

    # Test our call count
    assert mock_post.call_count == 1
    assert mock_post.call_args_list[0][0][0] == "http://localhost"

    response = json.loads(mock_post.call_args_list[0][1]["data"])
    assert response["topic"] == "topic1"
    assert response["message"] == "body"
    assert response["title"] == "title"
    assert response["attach"] == "http://example.com/file.jpg"
    assert response["filename"] == "smoke.jpg"

    # Reset our mock object
    mock_post.reset_mock()

    # Markdown Support
    results = NotifyNtfy.parse_url("ntfys://topic/?format=markdown")
    assert isinstance(results, dict)
    instance = NotifyNtfy(**results)

    assert (
        instance.notify(
            body="body", title="title", notify_type=apprise.NotifyType.INFO
        )
        is True
    )

    assert mock_post.call_count == 1
    assert mock_post.call_args_list[0][0][0] == "https://ntfy.sh"
    assert "X-Markdown" in mock_post.call_args_list[0][1]["headers"]


@mock.patch("requests.post")
@mock.patch("requests.get")
def test_plugin_ntfy_config_files(mock_post, mock_get):
    """NotifyNtfy() Config File Cases."""
    content = """
    urls:
      - ntfy://localhost/topic1:
          - priority: 1
            tag: ntfy_int min
          - priority: "1"
            tag: ntfy_str_int min
          - priority: min
            tag: ntfy_str min

          # This will take on normal (default) priority
          - priority: invalid
            tag: ntfy_invalid

      - ntfy://localhost/topic2:
          - priority: 5
            tag: ntfy_int max
          - priority: "5"
            tag: ntfy_str_int max
          - priority: emergency
            tag: ntfy_str max
          - priority: max
            tag: ntfy_str max
    """

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_get.return_value = requests.Request()
    mock_get.return_value.status_code = requests.codes.ok

    # Create ourselves a config object
    ac = apprise.AppriseConfig()
    assert ac.add_config(content=content) is True

    aobj = apprise.Apprise()

    # Add our configuration
    aobj.add(ac)

    # We should be able to read our 8 servers from that
    # 3x min
    # 4x max
    # 1x invalid (so takes on normal priority)
    assert len(ac.servers()) == 8
    assert len(aobj) == 8
    assert len(list(aobj.find(tag="min"))) == 3
    for s in aobj.find(tag="min"):
        assert s.priority == NtfyPriority.MIN

    assert len(list(aobj.find(tag="max"))) == 4
    for s in aobj.find(tag="max"):
        assert s.priority == NtfyPriority.MAX

    assert len(list(aobj.find(tag="ntfy_str"))) == 3
    assert len(list(aobj.find(tag="ntfy_str_int"))) == 2
    assert len(list(aobj.find(tag="ntfy_int"))) == 2

    assert len(list(aobj.find(tag="ntfy_invalid"))) == 1
    assert next(aobj.find(tag="ntfy_invalid")).priority == NtfyPriority.NORMAL

    # A cloud reference without any identifiers; the ntfy:// (insecure mode)
    # is not considered during the id generation as ntfys:// is always
    # implied
    results = NotifyNtfy.parse_url("ntfy://")
    obj = NotifyNtfy(**results)
    new_results = NotifyNtfy.parse_url(obj.url())
    obj2 = NotifyNtfy(**new_results)
    assert obj.url_id() == obj2.url_id()


@mock.patch("requests.post")
def test_plugin_ntfy_internationalized_urls(mock_post):
    """NotifyNtfy() Internationalized URL Support."""

    # Prepare Mock return object
    response = mock.Mock()
    response.content = GOOD_RESPONSE_TEXT
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    # Our input
    title = "My Title"
    body = "My Body"

    # Google Translate promised me this just says 'Apprise Example' (I hope
    # this is the case 🙏).  Below is a URL requiring encoding so that it
    # can be correctly passed into an http header:
    click = "https://通知の例"

    # Prepare our object
    obj = apprise.Apprise.instantiate(f"ntfy://ntfy.sh/topic1?click={click}")

    # Send our notification
    assert obj.notify(title=title, body=body)
    assert mock_post.call_count == 1

    assert mock_post.call_args_list[0][0][0] == "http://ntfy.sh"

    # Verify that our International URL was correctly escaped
    assert (
        "https://%25E9%2580%259A%25E7%259F%25A5%25E3%2581%25AE%25E4%25BE%258B"
        in mock_post.call_args_list[0][1]["headers"]["X-Click"]
    )

    # Validate that we did not obstruct our URL in anyway
    assert apprise.Apprise.instantiate(obj.url()).url() == obj.url()


@mock.patch("requests.post")
def test_plugin_ntfy_message_to_attach(mock_post):
    """NotifyNtfy() large messages converted into attachments."""

    # Prepare Mock return object
    response = mock.Mock()
    response.content = GOOD_RESPONSE_TEXT
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    # Create a very, very big message
    title = "My Title"
    body = "b" * NotifyNtfy.ntfy_json_upstream_size_limit

    for fmt in apprise.NOTIFY_FORMATS:

        # Prepare our object
        obj = apprise.Apprise.instantiate(
            f"ntfy://user:pass@localhost:8080/topic?format={fmt}"
        )

        # Our content will actually transfer as an attachment
        assert obj.notify(title=title, body=body)
        assert mock_post.call_count == 1

        assert (
            mock_post.call_args_list[0][0][0] == "http://localhost:8080/topic"
        )

        response = mock_post.call_args_list[0][1]
        assert "data" in response
        assert response["data"].decode("utf-8").startswith(title)
        assert response["data"].decode("utf-8").endswith(body)
        assert "params" in response
        assert "filename" in response["params"]
        # Our filename is automatically generated (with .txt)
        assert re.match(
            r"^[a-z0-9-]+\.txt$", response["params"]["filename"], re.I
        )

        # Reset our mock object
        mock_post.reset_mock()
