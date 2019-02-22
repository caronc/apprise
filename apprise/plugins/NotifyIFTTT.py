# -*- coding: utf-8 -*-
#
# IFTTT (If-This-Then-That)
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
#
# For this plugin to work, you need to add the Maker applet to your profile
# Simply visit https://ifttt.com/search and search for 'Webhooks'
# Or if you're signed in, click here: https://ifttt.com/maker_webhooks
# and click 'Connect'
#
# You'll want to visit the settings of this Applet and pay attention to the
# URL. For example, it might look like this:
#               https://maker.ifttt.com/use/a3nHB7gA9TfBQSqJAHklod
#
# In the above example a3nHB7gA9TfBQSqJAHklod becomes your {webhook_id}
# You will need this to make this notification work correctly
#
# For each event you create you will assign it a name (this will be known as
# the {event} when building your URL.
import requests
from json import dumps

from .NotifyBase import NotifyBase
from .NotifyBase import HTTP_ERROR_MAP
from ..common import NotifyType
from ..utils import parse_list


class NotifyIFTTT(NotifyBase):
    """
    A wrapper for IFTTT Notifications

    """

    # The default descriptive name associated with the Notification
    service_name = 'IFTTT'

    # The services URL
    service_url = 'https://ifttt.com/'

    # The default protocol
    secure_protocol = 'ifttt'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_ifttt'

    # Even though you'll add 'Ingredients' as {{ Value1 }} to your Applets,
    # you must use their lowercase value in the HTTP POST.
    ifttt_default_key_prefix = 'value'

    # The default IFTTT Key to use when mapping the title text to the IFTTT
    # event. The idea here is if someone wants to over-ride the default and
    # change it to another Ingredient Name (in 2018, you were limited to have
    # value1, value2, and value3).
    ifttt_default_title_key = 'value1'

    # The default IFTTT Key to use when mapping the body text to the IFTTT
    # event. The idea here is if someone wants to over-ride the default and
    # change it to another Ingredient Name (in 2018, you were limited to have
    # value1, value2, and value3).
    ifttt_default_body_key = 'value2'

    # The default IFTTT Key to use when mapping the body text to the IFTTT
    # event. The idea here is if someone wants to over-ride the default and
    # change it to another Ingredient Name (in 2018, you were limited to have
    # value1, value2, and value3).
    ifttt_default_type_key = 'value3'

    # IFTTT uses the http protocol with JSON requests
    notify_url = 'https://maker.ifttt.com/' \
                 'trigger/{event}/with/key/{webhook_id}'

    def __init__(self, webhook_id, events, add_tokens=None, del_tokens=None,
                 **kwargs):
        """
        Initialize IFTTT Object

        add_tokens can optionally be a dictionary of key/value pairs
        that you want to include in the IFTTT post to the server.

        del_tokens can optionally be a list/tuple/set of tokens
        that you want to eliminate from the IFTTT post.  There isn't
        much real functionality to this one unless you want to remove
        reference to Value1, Value2, and/or Value3

        """
        super(NotifyIFTTT, self).__init__(**kwargs)

        if not webhook_id:
            raise TypeError('You must specify the Webhooks webhook_id.')

        # Store our Events we wish to trigger
        self.events = parse_list(events)

        if not self.events:
            raise TypeError(
                'You must specify at least one event you wish to trigger on.')

        # Store our APIKey
        self.webhook_id = webhook_id

        # Tokens to include in post
        self.add_tokens = {}
        if add_tokens:
            self.add_tokens.update(add_tokens)

        # Tokens to remove
        self.del_tokens = []
        if del_tokens is not None:
            if isinstance(del_tokens, (list, tuple, set)):
                self.del_tokens = del_tokens

            else:
                raise TypeError(
                    'del_token must be a list; {} was provided'.format(
                        str(type(del_tokens))))

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform IFTTT Notification
        """

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
        }

        # prepare JSON Object
        payload = {
            self.ifttt_default_title_key: title,
            self.ifttt_default_body_key: body,
            self.ifttt_default_type_key: notify_type,
        }

        # Add any new tokens expected (this can also potentially override
        # any entries defined above)
        payload.update(self.add_tokens)

        # Eliminate fields flagged for removal otherwise ensure all tokens are
        # lowercase since that is what the IFTTT server expects from us.
        payload = {x.lower(): y for x, y in payload.items()
                   if x not in self.del_tokens}

        # Track our failures
        error_count = 0

        # Create a copy of our event lit
        events = list(self.events)

        while len(events):

            # Retrive an entry off of our event list
            event = events.pop(0)

            # URL to transmit content via
            url = self.notify_url.format(
                webhook_id=self.webhook_id,
                event=event,
            )

            self.logger.debug('IFTTT POST URL: %s (cert_verify=%r)' % (
                url, self.verify_certificate,
            ))
            self.logger.debug('IFTTT Payload: %s' % str(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()

            try:
                r = requests.post(
                    url,
                    data=dumps(payload),
                    headers=headers,
                    verify=self.verify_certificate,
                )
                self.logger.debug(
                    u"IFTTT HTTP response headers: %r" % r.headers)
                self.logger.debug(
                    u"IFTTT HTTP response body: %r" % r.content)

                if r.status_code != requests.codes.ok:
                    # We had a problem
                    try:
                        self.logger.warning(
                            'Failed to send IFTTT:%s '
                            'notification: %s (error=%s).' % (
                                event,
                                HTTP_ERROR_MAP[r.status_code],
                                r.status_code))

                    except KeyError:
                        self.logger.warning(
                            'Failed to send IFTTT:%s '
                            'notification (error=%s).' % (
                                event, r.status_code))

                    # self.logger.debug('Response Details: %s' % r.content)
                    error_count += 1

                else:
                    self.logger.info(
                        'Sent IFTTT notification to Event %s.' % event)

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occured sending IFTTT:%s ' % (
                        event) + 'notification.'
                )
                self.logger.debug('Socket Exception: %s' % str(e))
                error_count += 1

        return (error_count == 0)

    def url(self):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any arguments set
        args = {
            'format': self.notify_format,
            'overflow': self.overflow_mode,
        }

        # Store any new key/value pairs added to our list
        args.update({'+{}'.format(k): v for k, v in self.add_tokens})
        args.update({'-{}'.format(k): '' for k in self.del_tokens})

        return '{schema}://{webhook_id}@{events}/?{args}'.format(
            schema=self.secure_protocol,
            webhook_id=self.webhook_id,
            events='/'.join([self.quote(x, safe='') for x in self.events]),
            args=self.urlencode(args),
        )

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

        # Our Event
        results['events'] = list()
        results['events'].append(results['host'])

        # Our API Key
        results['webhook_id'] = results['user']

        # Now fetch the remaining tokens
        results['events'].extend([x for x in filter(
            bool, NotifyBase.split_path(results['fullpath']))][0:])

        return results
