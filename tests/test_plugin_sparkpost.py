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

from json import dumps

# Disable logging for a cleaner testing output
import logging
import os
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, AppriseAttachment, NotifyType
from apprise.plugins.sparkpost import NotifySparkPost

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# Our Testing URLs
apprise_url_tests = (
    (
        "sparkpost://",
        {
            "instance": TypeError,
        },
    ),
    (
        "sparkpost://:@/",
        {
            "instance": TypeError,
        },
    ),
    # No Token specified
    (
        "sparkpost://user@localhost.localdomain",
        {
            "instance": TypeError,
        },
    ),
    # Token is valid, but no user name specified
    (
        "sparkpost://localhost.localdomain/{}".format("a" * 32),
        {
            "instance": TypeError,
        },
    ),
    # Invalid from email address
    (
        'sparkpost://"@localhost.localdomain/{}'.format("b" * 32),
        {
            "instance": TypeError,
        },
    ),
    # No To email address, but everything else is valid
    (
        "sparkpost://user@localhost.localdomain/{}".format("c" * 32),
        {
            "instance": NotifySparkPost,
            "requests_response_text": {
                "results": {
                    "total_rejected_recipients": 0,
                    "total_accepted_recipients": 1,
                    "id": "11668787484950529",
                }
            },
        },
    ),
    (
        "sparkpost://user@localhost.localdomain/{}?format=markdown".format(
            "d" * 32
        ),
        {
            "instance": NotifySparkPost,
            "requests_response_text": {
                "results": {
                    "total_rejected_recipients": 0,
                    "total_accepted_recipients": 1,
                    "id": "11668787484950529",
                }
            },
        },
    ),
    (
        "sparkpost://user@localhost.localdomain/{}?format=html".format(
            "d" * 32
        ),
        {
            "instance": NotifySparkPost,
            "requests_response_text": {
                "results": {
                    "total_rejected_recipients": 0,
                    "total_accepted_recipients": 1,
                    "id": "11668787484950529",
                }
            },
        },
    ),
    (
        "sparkpost://user@localhost.localdomain/{}?format=text".format(
            "d" * 32
        ),
        {
            "instance": NotifySparkPost,
            "requests_response_text": {
                "results": {
                    "total_rejected_recipients": 0,
                    "total_accepted_recipients": 1,
                    "id": "11668787484950529",
                }
            },
        },
    ),
    # valid url with region specified (case insensitve)
    (
        "sparkpost://user@localhost.localdomain/{}?region=uS".format("d" * 32),
        {
            "instance": NotifySparkPost,
            "requests_response_text": {
                "results": {
                    "total_rejected_recipients": 0,
                    "total_accepted_recipients": 1,
                    "id": "11668787484950529",
                }
            },
        },
    ),
    # valid url with region specified (case insensitve)
    (
        "sparkpost://user@localhost.localdomain/{}?region=EU".format("e" * 32),
        {
            "instance": NotifySparkPost,
            "requests_response_text": {
                "results": {
                    "total_rejected_recipients": 0,
                    "total_accepted_recipients": 1,
                    "id": "11668787484950529",
                }
            },
        },
    ),
    # headers
    (
        "sparkpost://user@localhost.localdomain/{}"
        "?+X-Customer-Campaign-ID=Apprise".format("f" * 32),
        {
            "instance": NotifySparkPost,
            "requests_response_text": {
                "results": {
                    "total_rejected_recipients": 0,
                    "total_accepted_recipients": 1,
                    "id": "11668787484950529",
                }
            },
        },
    ),
    # template tokens
    (
        "sparkpost://user@localhost.localdomain/{}"
        "?:name=Chris&:status=admin".format("g" * 32),
        {
            "instance": NotifySparkPost,
            "requests_response_text": {
                "results": {
                    "total_rejected_recipients": 0,
                    "total_accepted_recipients": 1,
                    "id": "11668787484950529",
                }
            },
        },
    ),
    # bcc and cc
    (
        "sparkpost://user@localhost.localdomain/{}"
        "?bcc=user@example.com&cc=user2@example.com".format("h" * 32),
        {
            "instance": NotifySparkPost,
            "requests_response_text": {
                "results": {
                    "total_rejected_recipients": 0,
                    "total_accepted_recipients": 1,
                    "id": "11668787484950529",
                }
            },
        },
    ),
    # invalid url with region specified (case insensitve)
    (
        "sparkpost://user@localhost.localdomain/{}?region=invalid".format(
            "a" * 32
        ),
        {
            "instance": TypeError,
        },
    ),
    # One 'To' Email address
    (
        "sparkpost://user@localhost.localdomain/{}/test@example.com".format(
            "a" * 32
        ),
        {
            "instance": NotifySparkPost,
            "requests_response_text": {
                "results": {
                    "total_rejected_recipients": 0,
                    "total_accepted_recipients": 1,
                    "id": "11668787484950529",
                }
            },
        },
    ),
    # Invalid 'To' Email address
    (
        "sparkpost://user@localhost.localdomain/{}/invalid".format("i" * 32),
        {
            "instance": NotifySparkPost,
            # Expected notify() response
            "notify_response": False,
        },
    ),
    # Multiple 'To', 'Cc', and 'Bcc' addresses (with invalid ones)
    (
        "sparkpost://user@example.com/{}/{}?bcc={}&cc={}".format(
            "j" * 32,
            "/".join(
                ("user1@example.com", "invalid", "User2:user2@example.com")
            ),
            ",".join(("user3@example.com", "i@v", "User1:user1@example.com")),
            ",".join(("user4@example.com", "g@r@b", "Da:user5@example.com")),
        ),
        {
            "instance": NotifySparkPost,
            "requests_response_text": {
                "results": {
                    "total_rejected_recipients": 0,
                    "total_accepted_recipients": 1,
                    "id": "11668787484950529",
                }
            },
        },
    ),
    (
        "sparkpost://user@localhost.localdomain/{}?to=test@example.com".format(
            "k" * 32
        ),
        {
            "instance": NotifySparkPost,
            "requests_response_text": {
                "results": {
                    "total_rejected_recipients": 0,
                    "total_accepted_recipients": 1,
                    "id": "11668787484950529",
                }
            },
        },
    ),
    # One To Email address, a from name specified too
    (
        "sparkpost://user@localhost.localdomain/{}/"
        'test@example.com?name="Frodo"'.format("l" * 32),
        {
            "instance": NotifySparkPost,
            "requests_response_text": {
                "results": {
                    "total_rejected_recipients": 0,
                    "total_accepted_recipients": 1,
                    "id": "11668787484950529",
                }
            },
        },
    ),
    # Test invalid JSON response
    (
        "sparkpost://user@localhost.localdomain/{}".format("m" * 32),
        {
            "instance": NotifySparkPost,
            "requests_response_text": "{",
        },
    ),
    (
        "sparkpost://user@localhost.localdomain/{}".format("n" * 32),
        {
            "instance": NotifySparkPost,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "sparkpost://user@localhost.localdomain/{}".format("o" * 32),
        {
            "instance": NotifySparkPost,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "sparkpost://user@localhost.localdomain/{}".format("p" * 32),
        {
            "instance": NotifySparkPost,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_sparkpost_urls():
    """NotifySparkPost() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_sparkpost_throttling(mock_post):
    """NotifySparkPost() Throttling."""

    NotifySparkPost.sparkpost_retry_wait_sec = 0.1
    NotifySparkPost.sparkpost_retry_attempts = 3

    # API Key
    apikey = "abc123"
    user = "user"
    host = "example.com"
    targets = f"{user}@{host}"

    # Exception should be thrown about the fact no user was specified
    with pytest.raises(TypeError):
        NotifySparkPost(apikey=apikey, targets=targets, host=host)

    # Exception should be thrown about the fact no private key was specified
    with pytest.raises(TypeError):
        NotifySparkPost(apikey=None, targets=targets, user=user, host=host)

    okay_response = requests.Request()
    okay_response.status_code = requests.codes.ok
    okay_response.content = dumps({
        "results": {
            "total_rejected_recipients": 0,
            "total_accepted_recipients": 1,
            "id": "11668787484950529",
        }
    })

    retry_response = requests.Request()
    retry_response.status_code = requests.codes.too_many_requests
    retry_response.content = dumps({
        "errors": [{
            "description": "Unconfigured or unverified sending domain.",
            "code": "7001",
            "message": "Invalid domain",
        }]
    })

    # Prepare Mock (force 2 retry responses and then one okay)
    mock_post.side_effect = (retry_response, retry_response, okay_response)

    obj = Apprise.instantiate(
        f"sparkpost://user@localhost.localdomain/{apikey}"
    )
    assert isinstance(obj, NotifySparkPost)

    # We'll successfully perform the notification as we're within
    # our retry limit
    assert obj.notify("test") is True

    mock_post.reset_mock()
    mock_post.side_effect = (retry_response, retry_response, retry_response)

    # Now we are less than our expected limit check so we will fail
    assert obj.notify("test") is False


@mock.patch("requests.post")
def test_plugin_sparkpost_attachments(mock_post):
    """NotifySparkPost() Attachments."""
    NotifySparkPost.sparkpost_retry_wait_sec = 0.1
    NotifySparkPost.sparkpost_retry_attempts = 3

    okay_response = requests.Request()
    okay_response.status_code = requests.codes.ok
    okay_response.content = dumps({
        "results": {
            "total_rejected_recipients": 0,
            "total_accepted_recipients": 1,
            "id": "11668787484950529",
        }
    })

    # Assign our mock object our return value
    mock_post.return_value = okay_response

    # API Key
    apikey = "abc123"

    obj = Apprise.instantiate(
        f"sparkpost://user@localhost.localdomain/{apikey}"
    )
    assert isinstance(obj, NotifySparkPost)

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

    with mock.patch("base64.b64encode", side_effect=OSError()):
        # We can't send the message if we fail to parse the data
        assert (
            obj.notify(
                body="body",
                title="title",
                notify_type=NotifyType.INFO,
                attach=attach,
            )
            is False
        )

    obj = Apprise.instantiate(
        f"sparkpost://no-reply@example.com/{apikey}/"
        "user1@example.com/user2@example.com?batch=yes"
    )
    assert isinstance(obj, NotifySparkPost)

    # As a batch mode, both emails can be lumped into 1
    assert len(obj) == 1

    # Force our batch to break into separate messages
    obj.default_batch_size = 1

    # We'll send 2 messages no
    assert len(obj) == 2
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
    assert mock_post.call_count == 2

    # single batch
    mock_post.reset_mock()
    # We'll send 1 message
    obj.default_batch_size = 2

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
