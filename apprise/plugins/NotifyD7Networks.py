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

# To use this service you will need a D7 Networks account from their website
# at https://d7networks.com/
#
# After you've established your account you can get your api login credentials
# (both user and password) from the API Details section from within your
# account profile area:  https://d7networks.com/accounts/profile/

import six
import requests
import base64
from json import dumps
from json import loads

from .NotifyBase import NotifyBase
from ..URLBase import PrivacyMode
from ..common import NotifyType
from ..utils import is_phone_no
from ..utils import parse_phone_no
from ..utils import parse_bool
from ..AppriseLocale import gettext_lazy as _

# Extend HTTP Error Messages
D7NETWORKS_HTTP_ERROR_MAP = {
    401: 'Invalid Argument(s) Specified.',
    403: 'Unauthorized - Authentication Failure.',
    412: 'A Routing Error Occured',
    500: 'A Serverside Error Occured Handling the Request.',
}


# Priorities
class D7SMSPriority(object):
    """
    D7 Networks SMS Message Priority
    """
    LOW = 0
    MODERATE = 1
    NORMAL = 2
    HIGH = 3


D7NETWORK_SMS_PRIORITIES = (
    D7SMSPriority.LOW,
    D7SMSPriority.MODERATE,
    D7SMSPriority.NORMAL,
    D7SMSPriority.HIGH,
)


class NotifyD7Networks(NotifyBase):
    """
    A wrapper for D7 Networks Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'D7 Networks'

    # The services URL
    service_url = 'https://d7networks.com/'

    # All notification requests are secure
    secure_protocol = 'd7sms'

    # Allow 300 requests per minute.
    # 60/300 = 0.2
    request_rate_per_sec = 0.20

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_d7networks'

    # D7 Networks batch notification URL
    notify_batch_url = 'http://rest-api.d7networks.com/secure/sendbatch'

    # D7 Networks single notification URL
    notify_url = 'http://rest-api.d7networks.com/secure/send'

    # The maximum length of the body
    body_maxlen = 160

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Define object templates
    templates = (
        '{schema}://{user}:{password}@{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'user': {
            'name': _('Username'),
            'type': 'string',
            'required': True,
        },
        'password': {
            'name': _('Password'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'target_phone': {
            'name': _('Target Phone No'),
            'type': 'string',
            'prefix': '+',
            'regex': (r'^[0-9\s)(+-]+$', 'i'),
            'map_to': 'targets',
        },
        'targets': {
            'name': _('Targets'),
            'type': 'list:string',
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'priority': {
            'name': _('Priority'),
            'type': 'choice:int',
            'min': D7SMSPriority.LOW,
            'max': D7SMSPriority.HIGH,
            'values': D7NETWORK_SMS_PRIORITIES,

            # The website identifies that the default priority is low; so
            # this plugin will honor that same default
            'default': D7SMSPriority.LOW,
        },
        'batch': {
            'name': _('Batch Mode'),
            'type': 'bool',
            'default': False,
        },
        'to': {
            'alias_of': 'targets',
        },
        'source': {
            # Originating address,In cases where the rewriting of the sender's
            # address is supported or permitted by the SMS-C. This is used to
            # transmit the message, this number is transmitted as the
            # originating address and is completely optional.
            'name': _('Originating Address'),
            'type': 'string',
            'map_to': 'source',

        },
        'from': {
            'alias_of': 'source',
        },
    })

    def __init__(self, targets=None, priority=None, source=None, batch=False,
                 **kwargs):
        """
        Initialize D7 Networks Object
        """
        super(NotifyD7Networks, self).__init__(**kwargs)

        # The Priority of the message
        if priority not in D7NETWORK_SMS_PRIORITIES:
            self.priority = self.template_args['priority']['default']

        else:
            self.priority = priority

        # Prepare Batch Mode Flag
        self.batch = batch

        # Setup our source address (if defined)
        self.source = None \
            if not isinstance(source, six.string_types) else source.strip()

        if not (self.user and self.password):
            msg = 'A D7 Networks user/pass was not provided.'
            self.logger.warning(msg)
            raise TypeError(msg)

        # Parse our targets
        self.targets = list()
        for target in parse_phone_no(targets):
            # Validate targets and drop bad ones:
            result = result = is_phone_no(target)
            if not result:
                self.logger.warning(
                    'Dropped invalid phone # '
                    '({}) specified.'.format(target),
                )
                continue

            # store valid phone number
            self.targets.append(result['full'])

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Depending on whether we are set to batch mode or single mode this
        redirects to the appropriate handling
        """

        if len(self.targets) == 0:
            # There were no services to notify
            self.logger.warning('There were no D7 Networks targets to notify.')
            return False

        # error tracking (used for function return)
        has_error = False

        auth = '{user}:{password}'.format(
            user=self.user, password=self.password)
        if six.PY3:
            # Python 3's versio of b64encode() expects a byte array and not
            # a string.  To accomodate this, we encode the content here
            auth = auth.encode('utf-8')

        # Prepare our headers
        headers = {
            'User-Agent': self.app_id,
            'Accept': 'application/json',
            'Authorization': 'Basic {}'.format(base64.b64encode(auth))
        }

        # Our URL varies depending if we're doing a batch mode or not
        url = self.notify_batch_url if self.batch else self.notify_url

        # use the list directly
        targets = list(self.targets)

        while len(targets):

            if self.batch:
                # Prepare our payload
                payload = {
                    'globals': {
                        'priority': self.priority,
                        'from': self.source if self.source else self.app_id,
                    },
                    'messages': [{
                        'to': self.targets,
                        'content': body,
                    }],
                }

                # Reset our targets so we don't keep going. This is required
                # because we're in batch mode; we only need to loop once.
                targets = []

            else:
                # We're not in a batch mode; so get our next target
                # Get our target(s) to notify
                target = targets.pop(0)

                # Prepare our payload
                payload = {
                    'priority': self.priority,
                    'content': body,
                    'to': target,
                    'from': self.source if self.source else self.app_id,
                }

            # Some Debug Logging
            self.logger.debug(
                'D7 Networks POST URL: {} (cert_verify={})'.format(
                    url, self.verify_certificate))
            self.logger.debug('D7 Networks Payload: {}' .format(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.post(
                    url,
                    data=dumps(payload),
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )

                if r.status_code not in (
                        requests.codes.created, requests.codes.ok):
                    # We had a problem
                    status_str = \
                        NotifyBase.http_response_code_lookup(
                            r.status_code, D7NETWORKS_HTTP_ERROR_MAP)

                    try:
                        # Update our status response if we can
                        json_response = loads(r.content)
                        status_str = json_response.get('message', status_str)

                    except (AttributeError, TypeError, ValueError):
                        # ValueError = r.content is Unparsable
                        # TypeError = r.content is None
                        # AttributeError = r is None

                        # We could not parse JSON response.
                        # We will just use the status we already have.
                        pass

                    self.logger.warning(
                        'Failed to send D7 Networks SMS notification to {}: '
                        '{}{}error={}.'.format(
                            ', '.join(target) if self.batch else target,
                            status_str,
                            ', ' if status_str else '',
                            r.status_code))

                    self.logger.debug(
                        'Response Details:\r\n{}'.format(r.content))

                    # Mark our failure
                    has_error = True
                    continue

                else:

                    if self.batch:
                        count = len(self.targets)
                        try:
                            # Get our message delivery count if we can
                            json_response = loads(r.content)
                            count = int(json_response.get(
                                'data', {}).get('messageCount', -1))

                        except (AttributeError, TypeError, ValueError):
                            # ValueError = r.content is Unparsable
                            # TypeError = r.content is None
                            # AttributeError = r is None

                            # We could not parse JSON response. Assume that
                            # our delivery is okay for now.
                            pass

                        if count != len(self.targets):
                            has_error = True

                        self.logger.info(
                            'Sent D7 Networks batch SMS notification to '
                            '{} of {} target(s).'.format(
                                count, len(self.targets)))

                    else:
                        self.logger.info(
                            'Sent D7 Networks SMS notification to {}.'.format(
                                target))

                    self.logger.debug(
                        'Response Details:\r\n{}'.format(r.content))

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occurred sending D7 Networks:%s ' % (
                        ', '.join(self.targets)) + 'notification.'
                )
                self.logger.debug('Socket Exception: %s' % str(e))
                # Mark our failure
                has_error = True
                continue

        return not has_error

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'batch': 'yes' if self.batch else 'no',
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        if self.priority != self.template_args['priority']['default']:
            params['priority'] = str(self.priority)

        if self.source:
            params['from'] = self.source

        return '{schema}://{user}:{password}@{targets}/?{params}'.format(
            schema=self.secure_protocol,
            user=NotifyD7Networks.quote(self.user, safe=''),
            password=self.pprint(
                self.password, privacy, mode=PrivacyMode.Secret, safe=''),
            targets='/'.join(
                [NotifyD7Networks.quote(x, safe='') for x in self.targets]),
            params=NotifyD7Networks.urlencode(params))

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to re-instantiate this object.

        """
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Initialize our targets
        results['targets'] = list()

        # The store our first target stored in the hostname
        results['targets'].append(NotifyD7Networks.unquote(results['host']))

        # Get our entries; split_path() looks after unquoting content for us
        # by default
        results['targets'].extend(
            NotifyD7Networks.split_path(results['fullpath']))

        # Set our priority
        if 'priority' in results['qsd'] and len(results['qsd']['priority']):
            _map = {
                'l': D7SMSPriority.LOW,
                '0': D7SMSPriority.LOW,
                'm': D7SMSPriority.MODERATE,
                '1': D7SMSPriority.MODERATE,
                'n': D7SMSPriority.NORMAL,
                '2': D7SMSPriority.NORMAL,
                'h': D7SMSPriority.HIGH,
                '3': D7SMSPriority.HIGH,
            }
            try:
                results['priority'] = \
                    _map[results['qsd']['priority'][0].lower()]

            except KeyError:
                # No priority was set
                pass

        # Support the 'from'  and 'source' variable so that we can support
        # targets this way too.
        # The 'from' makes it easier to use yaml configuration
        if 'from' in results['qsd'] and len(results['qsd']['from']):
            results['source'] = \
                NotifyD7Networks.unquote(results['qsd']['from'])
        if 'source' in results['qsd'] and len(results['qsd']['source']):
            results['source'] = \
                NotifyD7Networks.unquote(results['qsd']['source'])

        # Get Batch Mode Flag
        results['batch'] = \
            parse_bool(results['qsd'].get('batch', False))

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyD7Networks.parse_phone_no(results['qsd']['to'])

        return results
