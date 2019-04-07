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

# At the time I created this plugin, their website had lots of issues with the
# Firefox Browser.  I fell back to Chrome and had no problems.

# To use this plugin, you need to first access https://teams.webex.com and
# make yourself an account if you don't already have one. You'll want to
# create at least one 'space' before getting the 'incoming webhook'.
#
# Next you'll need to install the 'Incoming webhook' plugin found under
# the 'other' category here: https://apphub.webex.com/integrations/

# These links may not always work as time goes by and websites always
# change, but at the time of creating this plugin this was a direct link
# to it: https://apphub.webex.com/integrations/incoming-webhooks-cisco-systems

# If you're logged in, you'll be able to click on the 'Connect' button. From
# there you'll need to accept the permissions it will ask of you. Give the
# webhook a name such as 'apprise'.
# When you're complete, you will recieve a URL that looks something like this:
# https://api.ciscospark.com/v1/webhooks/incoming/\
#       Y3lzY29zcGkyazovL3VzL1dFQkhPT0sajkkzYWU4fTMtMGE4Yy00
#
# The last part of the URL is all you need to be interested in. Think of this
# url as:
#   https://api.ciscospark.com/v1/webhooks/incoming/{token}
#
# You will need to assemble all of your URLs for this plugin to work as:
#   wxteams://{token}
#
# Resources
# - https://developer.webex.com/docs/api/basics - markdown/post syntax
# - https://developer.cisco.com/ecosystem/webex/apps/\
#       incoming-webhooks-cisco-systems/ - Simple webhook example

import re
import requests
from json import dumps

from .NotifyBase import NotifyBase
from ..common import NotifyType
from ..common import NotifyFormat

# Token required as part of the API request
VALIDATE_TOKEN = re.compile(r'[a-z0-9]{80}', re.I)

# Extend HTTP Error Messages
# Based on: https://developer.webex.com/docs/api/basics/rate-limiting
WEBEX_HTTP_ERROR_MAP = {
    401: 'Unauthorized - Invalid Token.',
    415: 'Unsuported media specified',
    429: 'To many consecutive requests were made.',
    503: 'Service is overloaded, try again later',
}


class NotifyWebexTeams(NotifyBase):
    """
    A wrapper for Webex Teams Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Cisco Webex Teams'

    # The services URL
    service_url = 'https://webex.teams.com/'

    # The default secure protocol
    secure_protocol = 'wxteams'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_wxteams'

    # Webex Teams uses the http protocol with JSON requests
    notify_url = 'https://api.ciscospark.com/v1/webhooks/incoming/'

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 1000

    # We don't support titles for Webex notifications
    title_maxlen = 0

    # Default to markdown; fall back to text
    notify_format = NotifyFormat.MARKDOWN

    def __init__(self, token, **kwargs):
        """
        Initialize Webex Teams Object
        """
        super(NotifyWebexTeams, self).__init__(**kwargs)

        if not token:
            msg = 'The Webex Teams token is not specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        if not VALIDATE_TOKEN.match(token.strip()):
            msg = 'The Webex Teams token specified ({}) is invalid.'\
                .format(token)
            self.logger.warning(msg)
            raise TypeError(msg)

        # The token associated with the account
        self.token = token.strip()

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Webex Teams Notification
        """

        # Setup our headers
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
        }

        # Prepare our URL
        url = '{}/{}'.format(self.notify_url, self.token)

        payload = {
            'markdown' if (self.notify_format == NotifyFormat.MARKDOWN)
            else 'text': body,
        }

        self.logger.debug('Webex Teams POST URL: %s (cert_verify=%r)' % (
            url, self.verify_certificate,
        ))
        self.logger.debug('Webex Teams Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()
        try:
            r = requests.post(
                url,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
            )
            if r.status_code not in (
                    requests.codes.ok, requests.codes.no_content):
                # We had a problem
                status_str = \
                    NotifyWebexTeams.http_response_code_lookup(
                        r.status_code)

                self.logger.warning(
                    'Failed to send Webex Teams notification: '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))

                return False

            else:
                self.logger.info(
                    'Sent Webex Teams notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occured sending Webex Teams '
                'notification.'
            )
            self.logger.debug('Socket Exception: %s' % str(e))

            return False

        return True

    def url(self):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any arguments set
        args = {
            'format': self.notify_format,
            'overflow': self.overflow_mode,
            'verify': 'yes' if self.verify_certificate else 'no',
        }

        return '{schema}://{token}/?{args}'.format(
            schema=self.secure_protocol,
            token=NotifyWebexTeams.quote(self.token, safe=''),
            args=NotifyWebexTeams.urlencode(args),
        )

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to substantiate this object.

        """
        results = NotifyBase.parse_url(url, verify_host=False)

        if not results:
            # We're done early as we couldn't load the results
            return results

        # The first token is stored in the hostname
        results['token'] = NotifyWebexTeams.unquote(results['host'])

        return results
