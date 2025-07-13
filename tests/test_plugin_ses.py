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
import sys
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, AppriseAttachment
from apprise.plugins.ses import NotifySES

logging.disable(logging.CRITICAL)

if hasattr(sys, "pypy_version_info"):
    raise pytest.skip(
        reason="Skipping test cases which stall on PyPy",
        allow_module_level=True,
    )

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

AWS_SES_GOOD_RESPONSE = """
    <SendRawEmailResponse
         xmlns="http://ses.amazonaws.com/doc/2010-12-01/">
      <SendRawEmailResult>
        <MessageId>
           010f017d87656ee2-a2ea291f-79ea-
           44f3-9d25-00d041de3007-000000</MessageId>
      </SendRawEmailResult>
      <ResponseMetadata>
        <RequestId>7abb454e-904b-4e46-a23c-2f4d2fc127a6</RequestId>
      </ResponseMetadata>
    </SendRawEmailResponse>
    """

TEST_ACCESS_KEY_ID = "AHIAJGNT76XIMXDBIJYA"
TEST_ACCESS_KEY_SECRET = "bu1dHSdO22pfaaVy/wmNsdljF4C07D3bndi9PQJ9"
TEST_REGION = "us-east-2"

# Our Testing URLs
apprise_url_tests = (
    (
        "ses://",
        {
            "instance": TypeError,
        },
    ),
    (
        "ses://:@/",
        {
            "instance": TypeError,
        },
    ),
    (
        "ses://user@example.com/T1JJ3T3L2",
        {
            # Just Token 1 provided
            "instance": TypeError,
        },
    ),
    (
        "ses://user@example.com/T1JJ3TD4JD/TIiajkdnlazk7FQ/",
        {
            # Missing a region
            "instance": TypeError,
        },
    ),
    (
        "ses://T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcevi7FQ/us-west-2",
        {
            # No email
            "instance": TypeError,
        },
    ),
    (
        "ses://user@example.com/T1JJ3TD4JD/TIiajkdnlazk7FQ/user2@example.com",
        {
            # Missing a region (but has email)
            "instance": TypeError,
        },
    ),
    (
        (
            "ses://user@example.com/T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcevi7FQ/"
            "us-west-2?reply=invalid-email"
        ),
        {
            # An invalid reply-to address
            "instance": TypeError,
            # Our response expected server response
            "requests_response_text": AWS_SES_GOOD_RESPONSE,
        },
    ),
    (
        (
            "ses://user@example.com/T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcevi7FQ/"
            "us-west-2"
        ),
        {
            # we have a valid URL and we'll use our own email as a target
            "instance": NotifySES,
            # Our response expected server response
            "requests_response_text": AWS_SES_GOOD_RESPONSE,
        },
    ),
    (
        (
            "ses://user@example.com/T1JJ3TD4JD/TIiajkdnlazk7FQ/us-west-2/"
            "user2@example.ca/user3@example.eu"
        ),
        {
            # Multi Email Suppport
            "instance": NotifySES,
            # Our response expected server response
            "requests_response_text": AWS_SES_GOOD_RESPONSE,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "ses://user@example.com/T...D/****/us-west-2",
        },
    ),
    (
        (
            "ses://user@example.com/T1JJ3T3L2/A1BRTD4JD/TIiajkdnlaevi7FQ/us-east-1"
            "?to=user2@example.ca"
        ),
        {
            # leveraging to: keyword
            "instance": NotifySES,
            # Our response expected server response
            "requests_response_text": AWS_SES_GOOD_RESPONSE,
        },
    ),
    (
        (
            "ses://?from=user@example.com&region=us-west-2&access=T1JJ3T3L2"
            "&secret=A1BRTD4JD/TIiajkdnlaevi7FQ"
            "&reply=No One <noreply@yahoo.ca>"
            "&bcc=user.bcc@example.com,user2.bcc@example.com,invalid-email"
            "&cc=user.cc@example.com,user2.cc@example.com,invalid-email"
            "&to=user2@example.ca"
        ),
        {
            # leveraging a ton of our keywords
            # We also test invlid emails specified on the bcc and cc list
            "instance": NotifySES,
            # Our response expected server response
            "requests_response_text": AWS_SES_GOOD_RESPONSE,
        },
    ),
    (
        (
            "ses://user@example.com/T1JJ3T3L2/A1BRTD4JD/TIiacevi7FQ/us-west-2/"
            "?name=From%20Name&to=user2@example.ca,invalid-email"
        ),
        {
            # leveraging a ton of our keywords
            "instance": NotifySES,
            # Our response expected server response
            "requests_response_text": AWS_SES_GOOD_RESPONSE,
        },
    ),
    (
        (
            "ses://user@example.com/T1JJ3T3L2/A1BRTD4JD/TIiacevi7FQ/us-west-2/"
            "?format=text"
        ),
        {
            # Send email as a text (instead of HTML)
            "instance": NotifySES,
            # Our response expected server response
            "requests_response_text": AWS_SES_GOOD_RESPONSE,
        },
    ),
    (
        (
            "ses://user@example.com/T1JJ3T3L2/A1BRTD4JD/TIiacevi7FQ/us-west-2/"
            "?to=invalid-email"
        ),
        {
            # An invalid email will get dropped during the initialization
            # we'll have no targets to notify afterwards
            "instance": NotifySES,
            # Our response expected server response
            "requests_response_text": AWS_SES_GOOD_RESPONSE,
            # As a result, we won't be able to notify anyone
            "notify_response": False,
        },
    ),
    (
        (
            "ses://user@example.com/T1JJ3T3L2/A1BRTD4JD/TIiacevi7FQ/us-west-2/"
            "user2@example.com"
        ),
        {
            "instance": NotifySES,
            # Our response expected server response
            "requests_response_text": AWS_SES_GOOD_RESPONSE,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        (
            "ses://user@example.com/T1JJ3T3L2/A1BRTD4JD/TIiajkdnlavi7FQ/us-west-2/"
            "user2@example.com"
        ),
        {
            "instance": NotifySES,
            # Our response expected server response
            "requests_response_text": AWS_SES_GOOD_RESPONSE,
            # Throws a series of connection and transfer exceptions when this
            # flag is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_ses_urls():
    """NotifySES() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


# We initialize a post object just incase a test fails below
# we don't want it sending any notifications upstream
@mock.patch("requests.post")
def test_plugin_ses_edge_cases(mock_post):
    """NotifySES() Edge Cases."""

    # Initializes the plugin with a valid access, but invalid access key
    with pytest.raises(TypeError):
        # No access_key_id specified
        NotifySES(
            from_addr="user@example.eu",
            access_key_id=None,
            secret_access_key=TEST_ACCESS_KEY_SECRET,
            region_name=TEST_REGION,
            targets="user@example.ca",
        )

    with pytest.raises(TypeError):
        # No secret_access_key specified
        NotifySES(
            from_addr="user@example.eu",
            access_key_id=TEST_ACCESS_KEY_ID,
            secret_access_key=None,
            region_name=TEST_REGION,
            targets="user@example.ca",
        )

    with pytest.raises(TypeError):
        # No region_name specified
        NotifySES(
            from_addr="user@example.eu",
            access_key_id=TEST_ACCESS_KEY_ID,
            secret_access_key=TEST_ACCESS_KEY_SECRET,
            region_name=None,
            targets="user@example.ca",
        )

    # No recipients
    obj = NotifySES(
        from_addr="user@example.eu",
        access_key_id=TEST_ACCESS_KEY_ID,
        secret_access_key=TEST_ACCESS_KEY_SECRET,
        region_name=TEST_REGION,
        targets=None,
    )

    # The object initializes properly but would not be able to send anything
    assert obj.notify(body="test", title="test") is False

    # The phone number is invalid, and without it, there is nothing
    # to notify; we
    obj = NotifySES(
        from_addr="user@example.eu",
        access_key_id=TEST_ACCESS_KEY_ID,
        secret_access_key=TEST_ACCESS_KEY_SECRET,
        region_name=TEST_REGION,
        targets="invalid-email",
    )

    # The object initializes properly but would not be able to send anything
    assert obj.notify(body="test", title="test") is False


def test_plugin_ses_url_parsing():
    """NotifySES() URL Parsing."""

    # No recipients
    results = NotifySES.parse_url(
        "ses://{}/{}/{}/{}/".format(
            "user@example.com",
            TEST_ACCESS_KEY_ID,
            TEST_ACCESS_KEY_SECRET,
            TEST_REGION,
        )
    )

    # Confirm that there were no recipients found
    assert len(results["targets"]) == 0
    assert "region_name" in results
    assert results["region_name"] == TEST_REGION
    assert "access_key_id" in results
    assert results["access_key_id"] == TEST_ACCESS_KEY_ID
    assert "secret_access_key" in results
    assert results["secret_access_key"] == TEST_ACCESS_KEY_SECRET

    # Detect recipients
    results = NotifySES.parse_url(
        "ses://{}/{}/{}/{}/{}/{}/".format(
            "user@example.com",
            TEST_ACCESS_KEY_ID,
            TEST_ACCESS_KEY_SECRET,
            # Uppercase Region won't break anything
            TEST_REGION.upper(),
            "user1@example.ca",
            "user2@example.eu",
        )
    )

    # Confirm that our recipients were found
    assert len(results["targets"]) == 2
    assert "user1@example.ca" in results["targets"]
    assert "user2@example.eu" in results["targets"]
    assert "region_name" in results
    assert results["region_name"] == TEST_REGION
    assert "access_key_id" in results
    assert results["access_key_id"] == TEST_ACCESS_KEY_ID
    assert "secret_access_key" in results
    assert results["secret_access_key"] == TEST_ACCESS_KEY_SECRET


def test_plugin_ses_aws_response_handling():
    """NotifySES() AWS Response Handling."""
    # Not a string
    response = NotifySES.aws_response_to_dict(None)
    assert response["type"] is None
    assert response["request_id"] is None

    # Invalid XML
    response = NotifySES.aws_response_to_dict(
        '<Bad Response xmlns="http://ses.amazonaws.com/doc/2010-03-31/">'
    )
    assert response["type"] is None
    assert response["request_id"] is None

    # Single Element in XML
    response = NotifySES.aws_response_to_dict(
        "<SingleElement></SingleElement>"
    )
    assert response["type"] == "SingleElement"
    assert response["request_id"] is None

    # Empty String
    response = NotifySES.aws_response_to_dict("")
    assert response["type"] is None
    assert response["request_id"] is None

    response = NotifySES.aws_response_to_dict("""
        <SendRawEmailResponse
             xmlns="http://ses.amazonaws.com/doc/2010-12-01/">
          <SendRawEmailResult>
            <MessageId>
               010f017d87656ee2-a2ea291f-79ea-44f3-9d25-00d041de307</MessageId>
          </SendRawEmailResult>
          <ResponseMetadata>
            <RequestId>7abb454e-904b-4e46-a23c-2f4d2fc127a6</RequestId>
          </ResponseMetadata>
        </SendRawEmailResponse>
        """)
    assert response["type"] == "SendRawEmailResponse"
    assert response["request_id"] == "7abb454e-904b-4e46-a23c-2f4d2fc127a6"
    assert (
        response["message_id"]
        == "010f017d87656ee2-a2ea291f-79ea-44f3-9d25-00d041de307"
    )

    response = NotifySES.aws_response_to_dict("""
        <ErrorResponse xmlns="http://ses.amazonaws.com/doc/2010-03-31/">
            <Error>
                <Type>Sender</Type>
                <Code>InvalidParameter</Code>
                <Message>Invalid parameter</Message>
            </Error>
            <RequestId>b5614883-babe-56ca-93b2-1c592ba6191e</RequestId>
        </ErrorResponse>
        """)
    assert response["type"] == "ErrorResponse"
    assert response["request_id"] == "b5614883-babe-56ca-93b2-1c592ba6191e"
    assert response["error_type"] == "Sender"
    assert response["error_code"] == "InvalidParameter"
    assert response["error_message"] == "Invalid parameter"


@mock.patch("requests.post")
def test_plugin_ses_attachments(mock_post):
    """NotifySES() Attachment Checks."""

    # Prepare Mock return object
    response = mock.Mock()
    response.content = AWS_SES_GOOD_RESPONSE
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    # prepare our attachment
    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, "apprise-test.gif"))

    # Test our markdown
    obj = Apprise.instantiate(
        "ses://{}/{}/{}/{}/".format(
            "user@example.com",
            TEST_ACCESS_KEY_ID,
            TEST_ACCESS_KEY_SECRET,
            TEST_REGION,
        )
    )

    # Send a good attachment
    assert obj.notify(body="test", attach=attach) is True

    # Reset our mock object
    mock_post.reset_mock()

    # Add another attachment so we drop into the area of the PushBullet code
    # that sends remaining attachments (if more detected)
    attach.add(os.path.join(TEST_VAR_DIR, "apprise-test.gif"))

    # Send our attachments
    assert obj.notify(body="test", attach=attach) is True

    # Test our call count
    assert mock_post.call_count == 1

    # Reset our mock object
    mock_post.reset_mock()

    # An invalid attachment will cause a failure
    path = os.path.join(TEST_VAR_DIR, "/invalid/path/to/an/invalid/file.jpg")
    attach = AppriseAttachment(path)
    assert obj.notify(body="test", attach=attach) is False
