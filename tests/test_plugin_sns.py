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
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise
from apprise.plugins.sns import NotifySNS

logging.disable(logging.CRITICAL)


TEST_ACCESS_KEY_ID = "AHIAJGNT76XIMXDBIJYA"
TEST_ACCESS_KEY_SECRET = "bu1dHSdO22pfaaVy/wmNsdljF4C07D3bndi9PQJ9"
TEST_REGION = "us-east-2"

# Our Testing URLs
apprise_url_tests = (
    (
        "sns://",
        {
            "instance": TypeError,
        },
    ),
    (
        "sns://:@/",
        {
            "instance": TypeError,
        },
    ),
    (
        "sns://T1JJ3T3L2",
        {
            # Just Token 1 provided
            "instance": TypeError,
        },
    ),
    (
        "sns://T1JJ3TD4JD/TIiajkdnlazk7FQ/",
        {
            # Missing a region
            "instance": TypeError,
        },
    ),
    (
        "sns://T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcevi7FQ/us-west-2/12223334444",
        {
            # we have a valid URL and one number to text
            "instance": NotifySNS,
        },
    ),
    (
        (
            "sns://?access=T1JJ3T3L2&secret=A1BRTD4JD/TIiajkdnlazkcevi7FQ"
            "&region=us-west-2&to=12223334444"
        ),
        {
            # Initialize using get parameters instead
            "instance": NotifySNS,
        },
    ),
    (
        "sns://T1JJ3TD4JD/TIiajkdnlazk7FQ/us-west-2/12223334444/12223334445",
        {
            # Multi SNS Suppport
            "instance": NotifySNS,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "sns://T...D/****/us-west-2",
        },
    ),
    (
        (
            "sns://T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/us-east-1"
            "?to=12223334444"
        ),
        {
            # Missing a topic and/or phone No
            "instance": NotifySNS,
        },
    ),
    (
        "sns://T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcevi7FQ/us-west-2/12223334444",
        {
            "instance": NotifySNS,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "sns://T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcevi7FQ/us-west-2/15556667777",
        {
            "instance": NotifySNS,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_sns_urls():
    """NotifySNS() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


# We initialize a post object just incase a test fails below
# we don't want it sending any notifications upstream
@mock.patch("requests.post")
def test_plugin_sns_edge_cases(mock_post):
    """NotifySNS() Edge Cases."""
    target = "+1800555999"
    # Initializes the plugin with a valid access, but invalid access key
    with pytest.raises(TypeError):
        # No access_key_id specified
        NotifySNS(
            access_key_id=None,
            secret_access_key=TEST_ACCESS_KEY_SECRET,
            region_name=TEST_REGION,
            targets=target,
        )

    with pytest.raises(TypeError):
        # No secret_access_key specified
        NotifySNS(
            access_key_id=TEST_ACCESS_KEY_ID,
            secret_access_key=None,
            region_name=TEST_REGION,
            targets=target,
        )

    with pytest.raises(TypeError):
        # No region_name specified
        NotifySNS(
            access_key_id=TEST_ACCESS_KEY_ID,
            secret_access_key=TEST_ACCESS_KEY_SECRET,
            region_name=None,
            targets=target,
        )

    # No recipients
    obj = NotifySNS(
        access_key_id=TEST_ACCESS_KEY_ID,
        secret_access_key=TEST_ACCESS_KEY_SECRET,
        region_name=TEST_REGION,
        targets=None,
    )

    # The object initializes properly but would not be able to send anything
    assert obj.notify(body="test", title="test") is False

    # The phone number is invalid, and without it, there is nothing
    # to notify
    obj = NotifySNS(
        access_key_id=TEST_ACCESS_KEY_ID,
        secret_access_key=TEST_ACCESS_KEY_SECRET,
        region_name=TEST_REGION,
        targets="+1809",
    )

    # The object initializes properly but would not be able to send anything
    assert obj.notify(body="test", title="test") is False

    # The phone number is invalid, and without it, there is nothing
    # to notify; we
    obj = NotifySNS(
        access_key_id=TEST_ACCESS_KEY_ID,
        secret_access_key=TEST_ACCESS_KEY_SECRET,
        region_name=TEST_REGION,
        targets="#(invalid-topic-because-of-the-brackets)",
    )

    # The object initializes properly but would not be able to send anything
    assert obj.notify(body="test", title="test") is False


def test_plugin_sns_url_parsing():
    """NotifySNS() URL Parsing."""

    # No recipients
    results = NotifySNS.parse_url(
        f"sns://{TEST_ACCESS_KEY_ID}/{TEST_ACCESS_KEY_SECRET}/{TEST_REGION}/"
    )

    # Confirm that there were no recipients found
    assert len(results["targets"]) == 0
    assert "region_name" in results
    assert results["region_name"] == TEST_REGION
    assert "access_key_id" in results
    assert results["access_key_id"] == TEST_ACCESS_KEY_ID
    assert "secret_access_key" in results
    assert results["secret_access_key"] == TEST_ACCESS_KEY_SECRET

    target = "+18001234567"
    topic = "MyTopic"

    # Detect recipients
    results = NotifySNS.parse_url(
        f"sns://{TEST_ACCESS_KEY_ID}/"
        f"{TEST_ACCESS_KEY_SECRET}/"
        f"{TEST_REGION.upper()}/"
        f"{target}/"
        f"{topic}/"
    )

    # Confirm that our recipients were found
    assert len(results["targets"]) == 2
    assert target in results["targets"]
    assert topic in results["targets"]
    assert "region_name" in results
    assert results["region_name"] == TEST_REGION
    assert "access_key_id" in results
    assert results["access_key_id"] == TEST_ACCESS_KEY_ID
    assert "secret_access_key" in results
    assert results["secret_access_key"] == TEST_ACCESS_KEY_SECRET


def test_plugin_sns_object_parsing():
    """NotifySNS() Object Parsing."""

    # Create our object
    a = Apprise()

    # Now test failing variations of our URL
    assert a.add("sns://") is False
    assert a.add("sns://nosecret") is False
    assert a.add("sns://nosecret/noregion/") is False

    # This is valid but without valid recipients; while it's still a valid URL
    # it won't do much when the user goes to send a notification
    assert a.add("sns://norecipient/norecipient/us-west-2") is True
    assert len(a) == 1

    # Parse a good one
    assert a.add("sns://oh/yeah/us-west-2/abcdtopic/+12223334444") is True
    assert len(a) == 2

    assert a.add("sns://oh/yeah/us-west-2/12223334444") is True
    assert len(a) == 3


def test_plugin_sns_aws_response_handling():
    """NotifySNS() AWS Response Handling."""
    # Not a string
    response = NotifySNS.aws_response_to_dict(None)
    assert response["type"] is None
    assert response["request_id"] is None

    # Invalid XML
    response = NotifySNS.aws_response_to_dict(
        '<Bad Response xmlns="http://sns.amazonaws.com/doc/2010-03-31/">'
    )
    assert response["type"] is None
    assert response["request_id"] is None

    # Single Element in XML
    response = NotifySNS.aws_response_to_dict(
        "<SingleElement></SingleElement>"
    )
    assert response["type"] == "SingleElement"
    assert response["request_id"] is None

    # Empty String
    response = NotifySNS.aws_response_to_dict("")
    assert response["type"] is None
    assert response["request_id"] is None

    response = NotifySNS.aws_response_to_dict("""
        <PublishResponse xmlns="http://sns.amazonaws.com/doc/2010-03-31/">
            <PublishResult>
                <MessageId>5e16935a-d1fb-5a31-a716-c7805e5c1d2e</MessageId>
            </PublishResult>
            <ResponseMetadata>
                <RequestId>dc258024-d0e6-56bb-af1b-d4fe5f4181a4</RequestId>
            </ResponseMetadata>
        </PublishResponse>
        """)
    assert response["type"] == "PublishResponse"
    assert response["request_id"] == "dc258024-d0e6-56bb-af1b-d4fe5f4181a4"
    assert response["message_id"] == "5e16935a-d1fb-5a31-a716-c7805e5c1d2e"

    response = NotifySNS.aws_response_to_dict("""
         <CreateTopicResponse xmlns="http://sns.amazonaws.com/doc/2010-03-31/">
           <CreateTopicResult>
             <TopicArn>arn:aws:sns:us-east-1:000000000000:abcd</TopicArn>
                </CreateTopicResult>
            <ResponseMetadata>
                <RequestId>604bef0f-369c-50c5-a7a4-bbd474c83d6a</RequestId>
            </ResponseMetadata>
        </CreateTopicResponse>
        """)
    assert response["type"] == "CreateTopicResponse"
    assert response["request_id"] == "604bef0f-369c-50c5-a7a4-bbd474c83d6a"
    assert response["topic_arn"] == "arn:aws:sns:us-east-1:000000000000:abcd"

    response = NotifySNS.aws_response_to_dict("""
        <ErrorResponse xmlns="http://sns.amazonaws.com/doc/2010-03-31/">
            <Error>
                <Type>Sender</Type>
                <Code>InvalidParameter</Code>
                <Message>Invalid parameter: TopicArn or TargetArn Reason:
                no value for required parameter</Message>
            </Error>
            <RequestId>b5614883-babe-56ca-93b2-1c592ba6191e</RequestId>
        </ErrorResponse>
        """)
    assert response["type"] == "ErrorResponse"
    assert response["request_id"] == "b5614883-babe-56ca-93b2-1c592ba6191e"
    assert response["error_type"] == "Sender"
    assert response["error_code"] == "InvalidParameter"
    assert response["error_message"].startswith("Invalid parameter:")
    assert response["error_message"].endswith("required parameter")


@mock.patch("requests.post")
def test_plugin_sns_aws_topic_handling(mock_post):
    """NotifySNS() AWS Topic Handling."""

    arn_response = """
         <CreateTopicResponse xmlns="http://sns.amazonaws.com/doc/2010-03-31/">
           <CreateTopicResult>
             <TopicArn>arn:aws:sns:us-east-1:000000000000:abcd</TopicArn>
                </CreateTopicResult>
            <ResponseMetadata>
                <RequestId>604bef0f-369c-50c5-a7a4-bbd474c83d6a</RequestId>
            </ResponseMetadata>
        </CreateTopicResponse>
        """

    def post(url, data, **kwargs):
        """Since Publishing a token requires 2 posts, we need to return our
        response depending on what step we're on."""

        # A request
        robj = mock.Mock()
        robj.text = ""
        robj.status_code = requests.codes.ok

        if data.find("=CreateTopic") >= 0:
            # Topic Post Failure
            robj.status_code = requests.codes.bad_request

        return robj

    # Assign ourselves a new function
    mock_post.side_effect = post

    # Create our object
    a = Apprise()

    a.add([
        # Single Topic
        "sns://T1JJ3T3L2/A1BRTD4JD/TIiajkdnl/us-west-2/TopicA",
        # Multi-Topic
        "sns://T1JJ3T3L2/A1BRTD4JD/TIiajkdnl/us-east-1/TopicA/TopicB/"
        # Topic-Mix
        "sns://T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkce/us-west-2/"
        "12223334444/TopicA",
    ])

    # CreateTopic fails
    assert a.notify(title="", body="test") is False

    def post(url, data, **kwargs):
        """Since Publishing a token requires 2 posts, we need to return our
        response depending on what step we're on."""

        # A request
        robj = mock.Mock()
        robj.text = ""
        robj.status_code = requests.codes.ok

        if data.find("=CreateTopic") >= 0:
            robj.text = arn_response

        # Manipulate Topic Publishing only (not phone)
        elif data.find("=Publish") >= 0 and data.find("TopicArn=") >= 0:
            # Topic Post Failure
            robj.status_code = requests.codes.bad_request

        return robj

    # Assign ourselves a new function
    mock_post.side_effect = post

    # Publish fails
    assert a.notify(title="", body="test") is False

    # Disable our side effect
    mock_post.side_effect = None

    # Handle case where TopicArn is missing:
    robj = mock.Mock()
    robj.text = "<CreateTopicResponse></CreateTopicResponse>"
    robj.status_code = requests.codes.ok

    # Assign ourselves a new function
    mock_post.return_value = robj
    assert a.notify(title="", body="test") is False

    # Handle case where we fails get a bad response
    robj = mock.Mock()
    robj.text = ""
    robj.status_code = requests.codes.bad_request
    mock_post.return_value = robj
    assert a.notify(title="", body="test") is False

    # Handle case where we get a valid response and TopicARN
    robj = mock.Mock()
    robj.text = arn_response
    robj.status_code = requests.codes.ok
    mock_post.return_value = robj
    # We would have failed to make Post
    assert a.notify(title="", body="test") is True
