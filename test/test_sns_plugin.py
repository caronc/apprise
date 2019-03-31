# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 Chris Caron <lead2gold@gmail.com>
# All rights reserved.
#
# This code is licensed under the MIT License.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files(the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and / or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions :
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import mock
import requests
from apprise import plugins
from apprise import Apprise

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)


TEST_ACCESS_KEY_ID = 'AHIAJGNT76XIMXDBIJYA'
TEST_ACCESS_KEY_SECRET = 'bu1dHSdO22pfaaVy/wmNsdljF4C07D3bndi9PQJ9'
TEST_REGION = 'us-east-2'


def test_object_initialization():
    """
    API: NotifySNS Plugin() initialization

    """

    # Initializes the plugin with a valid access, but invalid access key
    try:
        # No access_key_id specified
        plugins.NotifySNS(
            access_key_id=None,
            secret_access_key=TEST_ACCESS_KEY_SECRET,
            region_name=TEST_REGION,
            targets='+1800555999',
        )
        # The entries above are invalid, our code should never reach here
        assert(False)

    except TypeError:
        # Exception correctly caught
        assert(True)

    try:
        # No secret_access_key specified
        plugins.NotifySNS(
            access_key_id=TEST_ACCESS_KEY_ID,
            secret_access_key=None,
            region_name=TEST_REGION,
            targets='+1800555999',
        )
        # The entries above are invalid, our code should never reach here
        assert(False)

    except TypeError:
        # Exception correctly caught
        assert(True)

    try:
        # No region_name specified
        plugins.NotifySNS(
            access_key_id=TEST_ACCESS_KEY_ID,
            secret_access_key=TEST_ACCESS_KEY_SECRET,
            region_name=None,
            targets='+1800555999',
        )
        # The entries above are invalid, our code should never reach here
        assert(False)

    except TypeError:
        # Exception correctly caught
        assert(True)

    try:
        # No recipients
        plugins.NotifySNS(
            access_key_id=TEST_ACCESS_KEY_ID,
            secret_access_key=TEST_ACCESS_KEY_SECRET,
            region_name=TEST_REGION,
            targets=None,
        )
        # Still valid even without recipients
        assert(True)

    except TypeError:
        # Exception correctly caught
        assert(False)

    try:
        # No recipients - garbage recipients object
        plugins.NotifySNS(
            access_key_id=TEST_ACCESS_KEY_ID,
            secret_access_key=TEST_ACCESS_KEY_SECRET,
            region_name=TEST_REGION,
            targets=object(),
        )
        # Still valid even without recipients
        assert(True)

    except TypeError:
        # Exception correctly caught
        assert(False)

    try:
        # The phone number is invalid, and without it, there is nothing
        # to notify
        plugins.NotifySNS(
            access_key_id=TEST_ACCESS_KEY_ID,
            secret_access_key=TEST_ACCESS_KEY_SECRET,
            region_name=TEST_REGION,
            targets='+1809',
        )
        # The recipient is invalid, but it's still okay; this Notification
        # still becomes pretty much useless at this point though
        assert(True)

    except TypeError:
        # Exception correctly caught
        assert(False)

    try:
        # The phone number is invalid, and without it, there is nothing
        # to notify; we
        plugins.NotifySNS(
            access_key_id=TEST_ACCESS_KEY_ID,
            secret_access_key=TEST_ACCESS_KEY_SECRET,
            region_name=TEST_REGION,
            targets='#(invalid-topic-because-of-the-brackets)',
        )
        # The recipient is invalid, but it's still okay; this Notification
        # still becomes pretty much useless at this point though
        assert(True)

    except TypeError:
        # Exception correctly caught
        assert(False)


def test_url_parsing():
    """
    API: NotifySNS Plugin() URL Parsing

    """

    # No recipients
    results = plugins.NotifySNS.parse_url('sns://%s/%s/%s/' % (
        TEST_ACCESS_KEY_ID,
        TEST_ACCESS_KEY_SECRET,
        TEST_REGION)
    )

    # Confirm that there were no recipients found
    assert(len(results['targets']) == 0)
    assert('region_name' in results)
    assert(TEST_REGION == results['region_name'])
    assert('access_key_id' in results)
    assert(TEST_ACCESS_KEY_ID == results['access_key_id'])
    assert('secret_access_key' in results)
    assert(TEST_ACCESS_KEY_SECRET == results['secret_access_key'])

    # Detect recipients
    results = plugins.NotifySNS.parse_url('sns://%s/%s/%s/%s/%s/' % (
        TEST_ACCESS_KEY_ID,
        TEST_ACCESS_KEY_SECRET,
        # Uppercase Region won't break anything
        TEST_REGION.upper(),
        '+18001234567',
        'MyTopic')
    )

    # Confirm that our recipients were found
    assert(len(results['targets']) == 2)
    assert('+18001234567' in results['targets'])
    assert('MyTopic' in results['targets'])
    assert('region_name' in results)
    assert(TEST_REGION == results['region_name'])
    assert('access_key_id' in results)
    assert(TEST_ACCESS_KEY_ID == results['access_key_id'])
    assert('secret_access_key' in results)
    assert(TEST_ACCESS_KEY_SECRET == results['secret_access_key'])


def test_object_parsing():
    """
    API: NotifySNS Plugin() Object Parsing

    """

    # Create our object
    a = Apprise()

    # Now test failing variations of our URL
    assert(a.add('sns://') is False)
    assert(a.add('sns://nosecret') is False)
    assert(a.add('sns://nosecret/noregion/') is False)

    # This is valid, but a rather useless URL; there is nothing to notify
    assert(a.add('sns://norecipient/norecipient/us-west-2') is True)
    assert(len(a) == 1)

    # Parse a good one
    assert(a.add('sns://oh/yeah/us-west-2/abcdtopic/+12223334444') is True)
    assert(len(a) == 2)

    assert(a.add('sns://oh/yeah/us-west-2/12223334444') is True)
    assert(len(a) == 3)


def test_aws_response_handling():
    """
    API: NotifySNS Plugin() AWS Response Handling

    """
    # Not a string
    response = plugins.NotifySNS.aws_response_to_dict(None)
    assert(response['type'] is None)
    assert(response['request_id'] is None)

    # Invalid XML
    response = plugins.NotifySNS.aws_response_to_dict(
        '<Bad Response xmlns="http://sns.amazonaws.com/doc/2010-03-31/">')
    assert(response['type'] is None)
    assert(response['request_id'] is None)

    # Single Element in XML
    response = plugins.NotifySNS.aws_response_to_dict(
        '<SingleElement></SingleElement>')
    assert(response['type'] == 'SingleElement')
    assert(response['request_id'] is None)

    # Empty String
    response = plugins.NotifySNS.aws_response_to_dict('')
    assert(response['type'] is None)
    assert(response['request_id'] is None)

    response = plugins.NotifySNS.aws_response_to_dict(
        """
        <PublishResponse xmlns="http://sns.amazonaws.com/doc/2010-03-31/">
            <PublishResult>
                <MessageId>5e16935a-d1fb-5a31-a716-c7805e5c1d2e</MessageId>
            </PublishResult>
            <ResponseMetadata>
                <RequestId>dc258024-d0e6-56bb-af1b-d4fe5f4181a4</RequestId>
            </ResponseMetadata>
        </PublishResponse>
        """)
    assert(response['type'] == 'PublishResponse')
    assert(response['request_id'] == 'dc258024-d0e6-56bb-af1b-d4fe5f4181a4')
    assert(response['message_id'] == '5e16935a-d1fb-5a31-a716-c7805e5c1d2e')

    response = plugins.NotifySNS.aws_response_to_dict(
        """
         <CreateTopicResponse xmlns="http://sns.amazonaws.com/doc/2010-03-31/">
           <CreateTopicResult>
             <TopicArn>arn:aws:sns:us-east-1:000000000000:abcd</TopicArn>
                </CreateTopicResult>
            <ResponseMetadata>
                <RequestId>604bef0f-369c-50c5-a7a4-bbd474c83d6a</RequestId>
            </ResponseMetadata>
        </CreateTopicResponse>
        """)
    assert(response['type'] == 'CreateTopicResponse')
    assert(response['request_id'] == '604bef0f-369c-50c5-a7a4-bbd474c83d6a')
    assert(response['topic_arn'] == 'arn:aws:sns:us-east-1:000000000000:abcd')

    response = plugins.NotifySNS.aws_response_to_dict(
        """
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
    assert(response['type'] == 'ErrorResponse')
    assert(response['request_id'] == 'b5614883-babe-56ca-93b2-1c592ba6191e')
    assert(response['error_type'] == 'Sender')
    assert(response['error_code'] == 'InvalidParameter')
    assert(response['error_message'].startswith('Invalid parameter:'))
    assert(response['error_message'].endswith('required parameter'))


@mock.patch('requests.post')
def test_aws_topic_handling(mock_post):
    """
    API: NotifySNS Plugin() AWS Topic Handling

    """
    # Disable Throttling to speed testing
    plugins.NotifySNS.request_rate_per_sec = 0

    arn_response = \
        """
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
        """
        Since Publishing a token requires 2 posts, we need to return our
        response depending on what step we're on
        """

        # A request
        robj = mock.Mock()
        robj.content = ''
        robj.status_code = requests.codes.ok

        if data.find('=CreateTopic') >= 0:
            # Topic Post Failure
            robj.status_code = requests.codes.bad_request

        return robj

    # Assign ourselves a new function
    mock_post.side_effect = post

    # Create our object
    a = Apprise()

    a.add([
        # Single Topic
        'sns://T1JJ3T3L2/A1BRTD4JD/TIiajkdnl/us-west-2/TopicA',
        # Multi-Topic
        'sns://T1JJ3T3L2/A1BRTD4JD/TIiajkdnl/us-east-1/TopicA/TopicB/'
        # Topic-Mix
        'sns://T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkce/us-west-2/' \
        '12223334444/TopicA'])

    # CreateTopic fails
    assert(a.notify(title='', body='test') is False)

    def post(url, data, **kwargs):
        """
        Since Publishing a token requires 2 posts, we need to return our
        response depending on what step we're on
        """

        # A request
        robj = mock.Mock()
        robj.content = ''
        robj.status_code = requests.codes.ok

        if data.find('=CreateTopic') >= 0:
            robj.content = arn_response

        # Manipulate Topic Publishing only (not phone)
        elif data.find('=Publish') >= 0 and data.find('TopicArn=') >= 0:
            # Topic Post Failure
            robj.status_code = requests.codes.bad_request

        return robj

    # Assign ourselves a new function
    mock_post.side_effect = post

    # Publish fails
    assert(a.notify(title='', body='test') is False)

    # Disable our side effect
    mock_post.side_effect = None

    # Handle case where TopicArn is missing:
    robj = mock.Mock()
    robj.content = "<CreateTopicResponse></CreateTopicResponse>"
    robj.status_code = requests.codes.ok

    # Assign ourselves a new function
    mock_post.return_value = robj
    assert(a.notify(title='', body='test') is False)

    # Handle case where we fails get a bad response
    robj = mock.Mock()
    robj.content = ''
    robj.status_code = requests.codes.bad_request
    mock_post.return_value = robj
    assert(a.notify(title='', body='test') is False)

    # Handle case where we get a valid response and TopicARN
    robj = mock.Mock()
    robj.content = arn_response
    robj.status_code = requests.codes.ok
    mock_post.return_value = robj
    # We would have failed to make Post
    assert(a.notify(title='', body='test') is True)
