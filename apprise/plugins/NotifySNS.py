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

import re

# Phase 1; use boto3 for a proof of concept
import boto3
from botocore.exceptions import ClientError
from botocore.exceptions import EndpointConnectionError

from .NotifyBase import NotifyBase
from ..utils import compat_is_basestring

# Some Phone Number Detection
IS_PHONE_NO = re.compile(r'^\+?(?P<phone>[0-9\s)(+-]+)\s*$')

# Topic Detection
# Summary: 256 Characters max, only alpha/numeric plus underscore (_) and
#          dash (-) additionally allowed.
#
#   Soure: https://docs.aws.amazon.com/AWSSimpleQueueService/latest\
#                   /SQSDeveloperGuide/sqs-limits.html#limits-queues
#
# Allow a starting hashtag (#) specification to help eliminate possible
# ambiguity between a topic that is comprised of all digits and a phone number
IS_TOPIC = re.compile(r'^#?(?P<name>[A-Za-z0-9_-]+)\s*$')

# Used to break apart list of potential tags by their delimiter
# into a usable list.
LIST_DELIM = re.compile(r'[ \t\r\n,\\/]+')

# Because our AWS Access Key Secret contains slashes, we actually use the
# region as a delimiter. This is a bit hacky; but it's much easier than having
# users of this product search though this Access Key Secret and escape all
# of the forward slashes!
IS_REGION = re.compile(
        r'^\s*(?P<country>[a-z]{2})-(?P<area>[a-z]+)-(?P<no>[0-9]+)\s*$', re.I)


class NotifySNS(NotifyBase):
    """
    A wrapper for AWS SNS (Amazon Simple Notification)
    """

    # The default descriptive name associated with the Notification
    service_name = 'AWS Simple Notification Service (SNS)'

    # The services URL
    service_url = 'https://aws.amazon.com/sns/'

    # The default secure protocol
    secure_protocol = 'sns'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_sns'

    # The maximum length of the body
    body_maxlen = 256

    def __init__(self, access_key_id, secret_access_key, region_name,
                 recipients=None, **kwargs):
        """
        Initialize Notify AWS SNS Object
        """
        super(NotifySNS, self).__init__(**kwargs)

        # Initialize topic list
        self.topics = list()

        # Initialize numbers list
        self.phone = list()

        # Store our AWS API Key
        self.access_key_id = access_key_id

        # Store our AWS API Secret Access key
        self.secret_access_key = secret_access_key

        # Acquire our AWS Region Name:
        # eg. us-east-1, cn-north-1, us-west-2, ...
        self.region_name = region_name

        if not access_key_id:
            raise TypeError(
                'An invalid AWS Access Key ID was specified.'
            )

        if not secret_access_key:
            raise TypeError(
                'An invalid AWS Secret Access Key was specified.'
            )

        if not (region_name and IS_REGION.match(region_name)):
            raise TypeError(
                'An invalid AWS Region was specified.'
            )

        if recipients is None:
            recipients = []

        elif compat_is_basestring(recipients):
            recipients = [x for x in filter(bool, LIST_DELIM.split(
                recipients,
            ))]

        elif not isinstance(recipients, (set, tuple, list)):
            recipients = []

        # Validate recipients and drop bad ones:
        for recipient in recipients:
            result = IS_PHONE_NO.match(recipient)
            if result:
                # Further check our phone # for it's digit count
                # if it's less than 10, then we can assume it's
                # a poorly specified phone no and spit a warning
                result = ''.join(re.findall(r'\d+', result.group('phone')))
                if len(result) < 11 or len(result) > 14:
                    self.logger.warning(
                        'Dropped invalid phone # '
                        '(%s) specified.' % recipient,
                    )
                    continue

                # store valid phone number
                self.phone.append('+{}'.format(result))
                continue

            result = IS_TOPIC.match(recipient)
            if result:
                # store valid topic
                self.topics.append(result.group('name'))
                continue

            self.logger.warning(
                'Dropped invalid phone/topic '
                '(%s) specified.' % recipient,
            )

        if len(self.phone) == 0 and len(self.topics) == 0:
            self.logger.warning(
                'There are no valid recipient identified to notify.')

    def notify(self, title, body, notify_type, **kwargs):
        """
        wrapper to send_notification since we can alert more then one channel
        """

        # Create an SNS client
        client = boto3.client(
            "sns",
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name=self.region_name,
        )

        # Initiaize our error tracking
        has_error = False

        # Create a copy of our phone #'s and topics to notify against
        phone = list(self.phone)
        topics = list(self.topics)

        while len(phone) > 0:
            # Get Phone No
            no = phone.pop(0)

            try:
                if not client.publish(PhoneNumber=no, Message=body):

                    # toggle flag
                    has_error = True

            except ClientError as e:
                self.logger.warning("The credentials specified were invalid.")
                self.logger.debug('AWS Exception: %s' % str(e))

                # We can take an early exit at this point since there
                # is no need to potentialy get this error message again
                # for the remaining (if any) topic/phone to process
                return False

            except EndpointConnectionError as e:
                self.logger.warning(
                    "The region specified is invalid.")
                self.logger.debug('AWS Exception: %s' % str(e))

                # We can take an early exit at this point since there
                # is no need to potentialy get this error message again
                # for the remaining (if any) topic/phone to process
                return False

            if len(phone) + len(topics) > 0:
                # Prevent thrashing requests
                self.throttle()

        # Send all our defined topic id's
        while len(topics):
            # Get Topic
            topic = topics.pop(0)

            # Create the topic if it doesn't exist; nothing breaks if it does
            topic = client.create_topic(Name=topic)

            # Get the Amazon Resource Name
            topic_arn = topic['TopicArn']

            # Publish a message.
            try:
                if not client.publish(Message=body, TopicArn=topic_arn):

                    # toggle flag
                    has_error = True

            except ClientError as e:
                self.logger.warning(
                    "The credentials specified were invalid.")
                self.logger.debug('AWS Exception: %s' % str(e))

                # We can take an early exit at this point since there
                # is no need to potentialy get this error message again
                # for the remaining (if any) topics to process
                return False

            except EndpointConnectionError as e:
                self.logger.warning(
                    "The region specified is invalid.")
                self.logger.debug('AWS Exception: %s' % str(e))

                # We can take an early exit at this point since there
                # is no need to potentialy get this error message again
                # for the remaining (if any) topic/phone to process
                return False

            if len(topics) > 0:
                # Prevent thrashing requests
                self.throttle()

        return not has_error

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to substantiate this object.

        """
        results = NotifyBase.parse_url(url)

        if not results:
            # We're done early as we couldn't load the results
            return results

        #
        # Apply our settings now
        #

        # The AWS Access Key ID is stored in the hostname
        access_key_id = results['host']

        # Our AWS Access Key Secret contains slashes in it which unfortunately
        # means it is of variable length after the hostname.  Since we require
        # that the user provides the region code, we intentionally use this
        # as our delimiter to detect where our Secret is.
        secret_access_key = None
        region_name = None

        # We need to iterate over each entry in the fullpath and find our
        # region. Once we get there we stop and build our secret from our
        # accumulated data.
        secret_access_key_parts = list()

        # Section 1: Get Region and Access Secret
        index = 0
        for i, entry in enumerate(NotifyBase.split_path(results['fullpath'])):

            # Are we at the region yet?
            result = IS_REGION.match(entry)
            if result:
                # We found our Region; Rebuild our access key secret based on
                # all entries we found prior to this:
                secret_access_key = '/'.join(secret_access_key_parts)

                # Ensure region is nicely formatted
                region_name = "{country}-{area}-{no}".format(
                    country=result.group('country').lower(),
                    area=result.group('area').lower(),
                    no=result.group('no'),
                )

                # Track our index as we'll use this to grab the remaining
                # content in the next Section
                index = i + 1

                # We're done with Section 1
                break

            # Store our secret parts
            secret_access_key_parts.append(entry)

        # Section 2: Get our Recipients (basically all remaining entries)
        results['recipients'] = [
            NotifyBase.unquote(x) for x in filter(bool, NotifyBase.split_path(
                results['fullpath']))][index:]

        # Store our other detected data (if at all)
        results['region_name'] = region_name
        results['access_key_id'] = access_key_id
        results['secret_access_key'] = secret_access_key

        # Return our result set
        return results
