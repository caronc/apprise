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
from botocore.exceptions import ClientError
from botocore.exceptions import EndpointConnectionError

from apprise import plugins
from apprise import Apprise

TEST_ACCESS_KEY_ID = 'AHIAJGNT76XIMXDBIJYA'
TEST_ACCESS_KEY_SECRET = 'bu1dHSdO22pfaaVy/wmNsdljF4C07D3bndi9PQJ9'
TEST_REGION = 'us-east-2'


@mock.patch('boto3.client')
def test_object_notifications(mock_client):
    """
    API: NotifySNS Plugin() notifications

    """

    # Create our object
    a = Apprise()
    assert(a.add('sns://oh/yeah/us-west-2/12223334444') is True)
    # Multi Number Support
    assert(a.add('sns://oh/yeah/us-west-2/12223334444/12223334445') is True)

    # Set a successful notification
    client = mock.Mock()
    client.publish.return_value = True
    mock_client.return_value = client
    assert(a.notify(title='', body='apprise notification') is True)

    # Set an unsuccessful notification
    client = mock.Mock()
    client.publish.return_value = False
    mock_client.return_value = client
    assert(a.notify(title='', body='apprise notification') is False)

    client = mock.Mock()
    client.publish.return_value = True
    client.publish.side_effect = \
        ClientError({'ResponseMetadata': {'RetryAttempts': 1}}, '')
    mock_client.return_value = client
    assert(a.notify(title='', body='apprise notification') is False)

    client = mock.Mock()
    client.publish.return_value = True
    client.publish.side_effect = EndpointConnectionError(endpoint_url='')
    mock_client.return_value = client
    assert(a.notify(title='', body='apprise notification') is False)

    # Create a new object
    a = Apprise()
    assert(a.add('sns://oh/yeah/us-east-2/ATopic') is True)
    # Multi-Topic
    assert(a.add('sns://oh/yeah/us-east-2/ATopic/AnotherTopic') is True)

    # Set a successful notification
    client = mock.Mock()
    client.publish.return_value = True
    client.create_topic.return_value = {'TopicArn': 'goodtopic'}
    mock_client.return_value = client
    assert(a.notify(title='', body='apprise notification') is True)

    # Set an unsuccessful notification
    client = mock.Mock()
    client.publish.return_value = False
    client.create_topic.return_value = {'TopicArn': 'goodtopic'}
    mock_client.return_value = client
    assert(a.notify(title='', body='apprise notification') is False)

    client = mock.Mock()
    client.publish.return_value = True
    client.publish.side_effect = \
        ClientError({'ResponseMetadata': {'RetryAttempts': 1}}, '')
    client.create_topic.return_value = {'TopicArn': 'goodtopic'}
    mock_client.return_value = client
    assert(a.notify(title='', body='apprise notification') is False)

    client = mock.Mock()
    client.publish.return_value = True
    client.publish.side_effect = EndpointConnectionError(endpoint_url='')
    client.create_topic.return_value = {'TopicArn': 'goodtopic'}
    mock_client.return_value = client
    assert(a.notify(title='', body='apprise notification') is False)

    # Create a new object
    a = Apprise()
    # Combiniation handling
    assert(a.add('sns://oh/yeah/us-west-2/12223334444/ATopicToo') is True)

    client = mock.Mock()
    client.publish.return_value = True
    client.create_topic.return_value = {'TopicArn': 'goodtopic'}
    mock_client.return_value = client
    assert(a.notify(title='', body='apprise notification') is True)


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
            recipients='+1800555999',
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
            recipients='+1800555999',
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
            recipients='+1800555999',
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
            recipients=None,
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
            recipients=object(),
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
            recipients='+1809',
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
            recipients='#(invalid-topic-because-of-the-brackets)',
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
    assert(len(results['recipients']) == 0)
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
    assert(len(results['recipients']) == 2)
    assert('+18001234567' in results['recipients'])
    assert('MyTopic' in results['recipients'])
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
