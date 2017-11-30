# -*- coding: utf-8 -*-
#
# Boxcar Notify Wrapper
#
# Copyright (C) 2017 Chris Caron <lead2gold@gmail.com>
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

from json import dumps
from urllib import unquote
import requests
import re

from .NotifyBase import NotifyBase
from .NotifyBase import HTTP_ERROR_MAP

# Used to validate Tags, Aliases and Devices
IS_TAG = re.compile(r'^[A-Za-z0-9]{1,63}$')
IS_ALIAS = re.compile(r'^[@]?[A-Za-z0-9]+$')
IS_DEVICETOKEN = re.compile(r'^[A-Za-z0-9]{64}$')

# Used to break apart list of potential tags by their delimiter
# into a usable list.
TAGS_LIST_DELIM = re.compile(r'[ \t\r\n,\\/]+')


class NotifyBoxcar(NotifyBase):
    """
    A wrapper for Boxcar Notifications
    """

    # The default simple (insecure) protocol
    protocol = 'boxcar'

    # The default secure protocol
    secure_protocol = 'boxcars'

    def __init__(self, recipients=None, **kwargs):
        """
        Initialize Boxcar Object
        """
        super(NotifyBoxcar, self).__init__(
            title_maxlen=250, body_maxlen=10000, **kwargs)

        if self.secure:
            self.schema = 'https'

        else:
            self.schema = 'http'

        # Initialize tag list
        self.tags = list()

        # Initialize alias list
        self.aliases = list()

        # Initialize device_token list
        self.device_tokens = list()

        if recipients is None:
            recipients = []

        elif isinstance(recipients, basestring):
            recipients = filter(bool, TAGS_LIST_DELIM.split(
                recipients,
            ))

        elif not isinstance(recipients, (tuple, list)):
            recipients = []

        # Validate recipients and drop bad ones:
        for recipient in recipients:
            if IS_DEVICETOKEN.match(recipient):
                # store valid device
                self.device_tokens.append(recipient)

            elif IS_TAG.match(recipient):
                # store valid tag
                self.tags.append(recipient)

            elif IS_ALIAS.match(recipient):
                # store valid tag/alias
                self.aliases.append(recipient)

            else:
                self.logger.warning(
                    'Dropped invalid tag/alias/device_token '
                    '(%s) specified.' % recipient,
                )
                continue

    def notify(self, title, body, notify_type, **kwargs):
        """
        Perform Boxcar Notification
        """

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json'
        }

        # prepare Boxcar Object
        payload = {
            'badge': 'auto',
            'alert': '%s:\r\n%s' % (title, body),
        }

        if self.tags:
            payload['tags'] = self.tags

        if self.aliases:
            payload['aliases'] = self.aliases

        if self.device_tokens:
            payload['device_tokens'] = self.device_tokens

        auth = None
        if self.user:
            auth = (self.user, self.password)

        url = '%s://%s' % (self.schema, self.host)
        if isinstance(self.port, int):
            url += ':%d' % self.port

        url += '/api/push'

        self.logger.debug('Boxcar POST URL: %s (cert_verify=%r)' % (
            url, self.verify_certificate,
        ))
        self.logger.debug('Boxcar Payload: %s' % str(payload))
        try:
            r = requests.post(
                url,
                data=dumps(payload),
                headers=headers,
                auth=auth,
                verify=self.verify_certificate,
            )
            if r.status_code != requests.codes.ok:
                try:
                    self.logger.warning(
                        'Failed to send Boxcar notification: '
                        '%s (error=%s).' % (
                            HTTP_ERROR_MAP[r.status_code],
                            r.status_code))
                except KeyError:
                    self.logger.warning(
                        'Failed to send Boxcar notification '
                        '(error=%s).' % (
                            r.status_code))

                # Return; we're done
                return False

        except requests.ConnectionError as e:
            self.logger.warning(
                'A Connection error occured sending Boxcar '
                'notification to %s.' % (
                    self.host))

            self.logger.debug('Socket Exception: %s' % str(e))

            # Return; we're done
            return False

        return True

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns it broken apart into a dictionary.

        """
        results = NotifyBase.parse_url(url)

        if not results:
            # We're done early
            return None

        # Acquire our recipients and include them in the response
        try:
            recipients = unquote(results['fullpath'])

        except (AttributeError, KeyError):
            # no recipients detected
            recipients = ''

        # Store our recipients
        results['recipients'] = recipients

        return results
