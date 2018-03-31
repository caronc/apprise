# -*- coding: utf-8 -*-
#
# Stride Notify Wrapper
#
# Copyright (C) 2018 Chris Caron <lead2gold@gmail.com>
#
# This file is part of apprise.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.

# When you sign-up with stride.com they'll ask if you want to join a channel
# or create your own.
#
# Once you get set up, you'll have the option of creating a channel.
#
# Now you'll want to connect apprise up. To do this, you need to go to
# the App Manager an choose to 'Connect your own app'. It will get you
# to provide a 'token name' which can be whatever you want.  Call it
# 'Apprise' if you want (it really doesn't matter) and then click the
# 'Create' button.
#
# When it completes it will generate a token that looks something like:
#     HQFtq4pF8rKFOlKTm9Th
#
# This will become your AUTH_TOKEN
#
# It will also provide you a conversation URL that might look like:
#  https://api.atlassian.com/site/ce171c45-79ae-4fec-a73d-5a4b7a322872/\
#       conversation/a54a80b3-eaad-4564-9a3a-f6653bcfb100/message
#
#  Simplified, it looks like this:
#  https://api.atlassian.com/site/CLOUD_ID/conversation/CONVO_ID/message
#
#  This plugin will simply work using the url of:
#     stride://AUTH_TOKEN/CLOUD_ID/CONVO_ID
#
import requests
import re
from json import dumps

from .NotifyBase import NotifyBase
from .NotifyBase import HTTP_ERROR_MAP
from ..common import NotifyImageSize

# A Simple UUID4 checker
IS_VALID_TOKEN = re.compile(
    r'([0-9a-f]{8})-*([0-9a-f]{4})-*(4[0-9a-f]{3})-*'
    r'([89ab][0-9a-f]{3})-*([0-9a-f]{12})', re.I)


class NotifyStride(NotifyBase):
    """
    A wrapper to Stride Notifications

    """

    # The default secure protocol
    secure_protocol = 'stride'

    # Stride Webhook
    notify_url = 'https://api.atlassian.com/site/{cloud_id}/' \
                 'conversation/{convo_id}/message'

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_256

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 2000

    def __init__(self, auth_token, cloud_id, convo_id, **kwargs):
        """
        Initialize Stride Object

        """
        super(NotifyStride, self).__init__(**kwargs)

        if not auth_token:
            raise TypeError(
                'An invalid Authorization token was specified.'
            )

        if not cloud_id:
            raise TypeError('No Cloud ID was specified.')

        cloud_id_re = IS_VALID_TOKEN.match(cloud_id)
        if cloud_id_re is None:
            raise TypeError('The specified Cloud ID is not a valid UUID.')

        if not convo_id:
            raise TypeError('No Conversation ID was specified.')

        convo_id_re = IS_VALID_TOKEN.match(convo_id)
        if convo_id_re is None:
            raise TypeError(
                'The specified Conversation ID is not a valid UUID.')

        # Store our validated token
        self.cloud_id = '{0}-{1}-{2}-{3}-{4}'.format(
            cloud_id_re.group(0),
            cloud_id_re.group(1),
            cloud_id_re.group(2),
            cloud_id_re.group(3),
            cloud_id_re.group(4),
        )

        # Store our validated token
        self.convo_id = '{0}-{1}-{2}-{3}-{4}'.format(
            convo_id_re.group(0),
            convo_id_re.group(1),
            convo_id_re.group(2),
            convo_id_re.group(3),
            convo_id_re.group(4),
        )

        self.auth_token = auth_token

        return

    def notify(self, title, body, notify_type, **kwargs):
        """
        Perform Stride Notification
        """

        headers = {
            'User-Agent': self.app_id,
            'Authorization': 'Bearer {auth_token}'.format(
                auth_token=self.auth_token),
            'Content-Type': 'application/json',
        }

        # Prepare JSON Object
        payload = {
            "body": {
                "version": 1,
                "type": "doc",
                "content": [{
                    "type": "paragraph",
                    "content": [{
                        "type": "text",
                        "text": body,
                    }],
                }],
            }
        }

        # Construct Notify URL
        notify_url = self.notify_url.format(
            cloud_id=self.cloud_id,
            convo_id=self.convo_id,
        )

        self.logger.debug('Stride POST URL: %s (cert_verify=%r)' % (
            notify_url, self.verify_certificate,
        ))
        self.logger.debug('Stride Payload: %s' % str(payload))
        try:
            r = requests.post(
                notify_url,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
            )
            if r.status_code not in (
                    requests.codes.ok, requests.codes.no_content):
                # We had a problem
                try:
                    self.logger.warning(
                        'Failed to send Stride notification: '
                        '%s (error=%s).' % (
                            HTTP_ERROR_MAP[r.status_code],
                            r.status_code))

                except KeyError:
                    self.logger.warning(
                        'Failed to send Stride notification '
                        '(error=%s).' % r.status_code)

                self.logger.debug('Response Details: %s' % r.raw.read())

                # Return; we're done
                return False

            else:
                self.logger.info('Sent Stride notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occured sending Stride '
                'notification.'
            )
            self.logger.debug('Socket Exception: %s' % str(e))
            return False

        return True

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to substantiate this object.

        Syntax:
          stride://auth_token/cloud_id/convo_id

        """
        results = NotifyBase.parse_url(url)

        if not results:
            # We're done early as we couldn't load the results
            return results

        # Store our Authentication Token
        auth_token = results['host']

        # Now fetch our tokens
        try:
            (ta, tb) = [x for x in filter(bool, NotifyBase.split_path(
                results['fullpath']))][0:2]

        except (ValueError, AttributeError, IndexError):
            # Force some bad values that will get caught
            # in parsing later
            ta = None
            tb = None

        results['cloud_id'] = ta
        results['convo_id'] = tb
        results['auth_token'] = auth_token

        return results
