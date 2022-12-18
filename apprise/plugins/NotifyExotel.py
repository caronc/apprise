# -*- coding: utf-8 -*-
#
# Copyright (C) 2022 Chris Caron <lead2gold@gmail.com>
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

import requests

from itertools import chain

from .NotifyBase import NotifyBase
from ..URLBase import PrivacyMode
from ..common import NotifyType
from ..utils import is_phone_no
from ..utils import parse_phone_no
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _


class ExotelPriority:
    """
    Priorities
    """
    NORMAL = 'normal'
    HIGH = 'high'


EXOTEL_PRIORITIES = (
    ExotelPriority.NORMAL,
    ExotelPriority.HIGH,
)

EXOTEL_PRIORITY_MAP = {
    # short for 'normal'
    'normal': ExotelPriority.NORMAL,
    # short for 'high'
    '+': ExotelPriority.HIGH,
    'high': ExotelPriority.HIGH,
}


class ExotelEncoding(object):
    """
    The different encodings supported
    """
    TEXT = "plain"
    UNICODE = "unicode"


class ExotelRegion:
    """
    Regions
    """
    US = 'us'

    # India
    IN = 'in'


# Exotel APIs
EXOTEL_API_LOOKUP = {
    ExotelRegion.US: 'https://api.exotel.com/v1/Accounts/{sid}/Sms/send',
    ExotelRegion.IN: 'https://api.in.exotel.com/v1/Accounts/{sid}/Sms/send',
}

# A List of our regions we can use for verification
EXOTEL_REGIONS = (
    ExotelRegion.US,
    ExotelRegion.IN,
)


class NotifyExotel(NotifyBase):
    """
    A wrapper for Exotel Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Exotel'

    # The services URL
    service_url = 'https://exotel.com'

    # The default protocol (nexmo kept for backwards compatibility)
    secure_protocol = 'exotel'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_exotel'

    # The maximum length of the body
    body_maxlen = 2000

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Define object templates
    templates = (
        '{schema}://{sid}:{token}@{from_phone}',
        '{schema}://{sid}:{token}@{from_phone}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'sid': {
            'name': _('Secure ID'),
            'type': 'string',
            'required': True,
            'private': True,
        },
        'token': {
            'name': _('Token'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'from_phone': {
            'name': _('From Phone No'),
            'type': 'string',
            'required': True,
            'regex': (r'^\+?[0-9\s)(+-]+$', 'i'),
            'map_to': 'source',
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
        'to': {
            'alias_of': 'targets',
        },
        'from': {
            'alias_of': 'from_phone',
        },
        'sid': {
            'alias_of': 'sid',
        },
        'token': {
            'alias_of': 'token',
        },
        'unicode': {
            # Unicode characters
            'name': _('Unicode Characters'),
            'type': 'bool',
            'default': True,
        },
        'region': {
            'name': _('Region Name'),
            'type': 'choice:string',
            'values': EXOTEL_REGIONS,
            'default': ExotelRegion.US,
            'map_to': 'region_name',
        },
        'priority': {
            'name': _('Priority'),
            'type': 'choice:int',
            'values': EXOTEL_PRIORITIES,
            'default': ExotelPriority.NORMAL,
        },
    })

    def __init__(self, sid, token, source, targets=None, unicode=None,
                 priority=None, region_name=None, **kwargs):
        """
        Initialize Exotel Object
        """
        super().__init__(**kwargs)

        # Account SID
        self.sid = validate_regex(sid)
        if not self.sid:
            msg = 'An invalid Exotel SID ' \
                  '({}) was specified.'.format(sid)
            self.logger.warning(msg)
            raise TypeError(msg)

        # API Token (associated with account)
        self.token = validate_regex(token)
        if not self.token:
            msg = 'An invalid Exotel API Token ' \
                  '({}) was specified.'.format(token)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Used for URL generation afterwards only
        self.invalid_targets = list()

        # Store our region
        try:
            self.region_name = self.template_args['region']['default'] \
                if region_name is None else region_name.lower()

            if self.region_name not in EXOTEL_REGIONS:
                # allow the outer except to handle this common response
                raise
        except:
            # Invalid region specified
            msg = 'The Exotel region specified ({}) is invalid.' \
                  .format(region_name)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Define whether or not we should set the unicode flag
        self.unicode = self.template_args['unicode']['default'] \
            if unicode is None else bool(unicode)

        #
        # Priority
        #
        if priority is None:
            # Default
            self.priority = self.template_args['priority']['default']

        else:
            # Input is a string; attempt to get the lookup from our
            # priority mapping
            self.priority = priority.lower().strip()

            # This little bit of black magic allows us to match against
            # low, lo, l (for low);
            # normal, norma, norm, nor, no, n (for normal)
            # ... etc
            result = next((key for key in EXOTEL_PRIORITY_MAP.keys()
                          if key.startswith(self.priority)), None) \
                if priority else None

            # Now test to see if we got a match
            if not result:
                msg = 'An invalid Exotel priority ' \
                      '({}) was specified.'.format(priority)
                self.logger.warning(msg)
                raise TypeError(msg)

            # store our successfully looked up priority
            self.priority = EXOTEL_PRIORITY_MAP[result]

        # The Source Phone #
        self.source = source

        result = is_phone_no(source, min_len=9)
        if not result:
            msg = 'The Account (From) Phone # specified ' \
                  '({}) is invalid.'.format(source)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store our parsed value
        self.source = result['full']

        # Parse our targets
        self.targets = list()

        for target in parse_phone_no(targets):
            # Validate targets and drop bad ones:
            result = is_phone_no(target, min_len=9)
            if not result:
                self.logger.warning(
                    'Dropped invalid phone # '
                    '({}) specified.'.format(target),
                )
                self.invalid_targets.append(target)
                continue

            # store valid phone number
            self.targets.append(result['full'])

        if len(self.targets) == 0 and not self.invalid_targets:
            # No sources specified, use our own phone no
            self.targets.append(self.source)

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Exotel Notification
        """

        if not self.targets:
            # There were no endpoints to notify
            self.logger.warning('There were no Exotel targets to notify.')
            return False

        # error tracking (used for function return)
        has_error = False

        # Prepare our headers
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        # Our authentication
        auth = (self.sid, self.token)

        # Prepare our payload
        payload = {
            'From': self.source,
            'Body': body,
            'EncodingType': ExotelEncoding.UNICODE
            if self.unicode else ExotelEncoding.TEXT,
            'priority': self.priority,
            'StatusCallback': None,

            # The to gets populated in the loop below
            'To': None,
        }

        # Create a copy of the targets list
        targets = list(self.targets)

        # Prepare our notify_url
        notify_url = EXOTEL_API_LOOKUP[self.region_name].format(sid=self.sid)

        while len(targets):
            # Get our target to notify
            target = targets.pop(0)

            # Prepare our user
            payload['To'] = target

            # Some Debug Logging
            self.logger.debug('Exotel POST URL: {} (cert_verify={})'.format(
                notify_url, self.verify_certificate))
            self.logger.debug('Exotel Payload: {}' .format(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()

            try:
                r = requests.post(
                    notify_url,
                    auth=auth,
                    data=payload,
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )

                if r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = \
                        NotifyExotel.http_response_code_lookup(
                            r.status_code)

                    self.logger.warning(
                        'Failed to send Exotel notification to {}: '
                        '{}{}error={}.'.format(
                            target,
                            status_str,
                            ', ' if status_str else '',
                            r.status_code))

                    self.logger.debug(
                        'Response Details:\r\n{}'.format(r.content))

                    # Mark our failure
                    has_error = True
                    continue

                else:
                    self.logger.info(
                        'Sent Exotel notification to %s.' % target)

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occurred sending Exotel:%s '
                    'notification.' % target
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
            'unicode': 'yes' if self.unicode else 'no',
            'region': self.region_name,
            'priority': self.priority,
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return '{schema}://{sid}:{token}@{source}/{targets}/?{params}'.format(
            schema=self.secure_protocol,
            sid=self.pprint(
                self.sid, privacy, mode=PrivacyMode.Secret, safe=''),
            token=self.pprint(self.token, privacy, safe=''),
            source=NotifyExotel.quote(self.source, safe=''),
            targets='/'.join(
                [NotifyExotel.quote(x, safe='') for x in chain(
                    self.targets, self.invalid_targets)]),
            params=NotifyExotel.urlencode(params))

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

        # Get our entries; split_path() looks after unquoting content for us
        # by default
        results['targets'] = NotifyExotel.split_path(results['fullpath'])

        # The hostname is our source number
        results['source'] = NotifyExotel.unquote(results['host'])

        # Get our account_sid and token from the user/pass config
        results['sid'] = NotifyExotel.unquote(results['user'])
        results['token'] = NotifyExotel.unquote(results['password'])

        # Get region
        if 'region' in results['qsd'] and len(results['qsd']['region']):
            results['region_name'] = \
                NotifyExotel.unquote(results['qsd']['region'])

        # API Token
        if 'token' in results['qsd'] and len(results['qsd']['token']):
            # Extract the Token from an argument
            results['token'] = \
                NotifyExotel.unquote(results['qsd']['token'])

        # API SID
        if 'sid' in results['qsd'] and len(results['qsd']['sid']):
            # Extract the API SID from an argument
            results['sid'] = \
                NotifyExotel.unquote(results['qsd']['sid'])

        # Support the 'from'  and 'source' variable so that we can support
        # targets this way too.
        # The 'from' makes it easier to use yaml configuration
        if 'from' in results['qsd'] and len(results['qsd']['from']):
            results['source'] = \
                NotifyExotel.unquote(results['qsd']['from'])
        if 'source' in results['qsd'] and len(results['qsd']['source']):
            results['source'] = \
                NotifyExotel.unquote(results['qsd']['source'])

        # Support the 'to' variable so that we can support rooms this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyExotel.parse_phone_no(results['qsd']['to'])

        # Get priority
        if 'priority' in results['qsd'] and len(results['qsd']['priority']):
            results['priority'] = \
                NotifyExotel.unquote(results['qsd']['priority'])

        return results
