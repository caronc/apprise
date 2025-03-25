# -*- coding: utf-8 -*-
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

# To use this service you will need a BulkSMS account
# You will need credits (new accounts start with a few)
#     https://www.bulksms.com/account/
#
# API is documented here:
#   - https://www.bulksms.com/developer/json/v1/#tag/Message
import re
import requests
import json
from itertools import chain
from .base import NotifyBase
from ..url import PrivacyMode
from ..common import NotifyType
from ..utils.parse import is_phone_no, parse_phone_no, parse_bool
from ..locale import gettext_lazy as _


IS_GROUP_RE = re.compile(
    r'^(@?(?P<group>[A-Z0-9_-]+))$',
    re.IGNORECASE,
)


class BulkSMSRoutingGroup(object):
    """
    The different categories of routing
    """
    ECONOMY = "ECONOMY"
    STANDARD = "STANDARD"
    PREMIUM = "PREMIUM"


# Used for verification purposes
BULKSMS_ROUTING_GROUPS = (
    BulkSMSRoutingGroup.ECONOMY,
    BulkSMSRoutingGroup.STANDARD,
    BulkSMSRoutingGroup.PREMIUM,
)


class BulkSMSEncoding(object):
    """
    The different categories of routing
    """
    TEXT = "TEXT"
    UNICODE = "UNICODE"
    BINARY = "BINARY"


class NotifyBulkSMS(NotifyBase):
    """
    A wrapper for BulkSMS Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'BulkSMS'

    # The services URL
    service_url = 'https://bulksms.com/'

    # All notification requests are secure
    secure_protocol = 'bulksms'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_bulksms'

    # BulkSMS uses the http protocol with JSON requests
    notify_url = 'https://api.bulksms.com/v1/messages'

    # The maximum length of the body
    body_maxlen = 160

    # The maximum amount of texts that can go out in one batch
    default_batch_size = 4000

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
            'name': _('User Name'),
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
        'target_group': {
            'name': _('Target Group'),
            'type': 'string',
            'prefix': '@',
            'regex': (r'^[A-Z0-9 _-]+$', 'i'),
            'map_to': 'targets',
        },
        'targets': {
            'name': _('Targets'),
            'type': 'list:string',
            'required': True,
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'to': {
            'alias_of': 'targets',
        },
        'from': {
            'name': _('From Phone No'),
            'type': 'string',
            'regex': (r'^\+?[0-9\s)(+-]+$', 'i'),
            'map_to': 'source',
        },
        'route': {
            'name': _('Route Group'),
            'type': 'choice:string',
            'values': BULKSMS_ROUTING_GROUPS,
            'default': BulkSMSRoutingGroup.STANDARD,
        },
        'unicode': {
            # Unicode characters
            'name': _('Unicode Characters'),
            'type': 'bool',
            'default': True,
        },
        'batch': {
            'name': _('Batch Mode'),
            'type': 'bool',
            'default': False,
        },
    })

    def __init__(self, source=None, targets=None, unicode=None, batch=None,
                 route=None, **kwargs):
        """
        Initialize BulkSMS Object
        """
        super(NotifyBulkSMS, self).__init__(**kwargs)

        self.source = None
        if source:
            result = is_phone_no(source)
            if not result:
                msg = 'The Account (From) Phone # specified ' \
                      '({}) is invalid.'.format(source)
                self.logger.warning(msg)
                raise TypeError(msg)

            # Tidy source
            self.source = '+{}'.format(result['full'])

        # Setup our route
        self.route = self.template_args['route']['default'] \
            if not isinstance(route, str) else route.upper()
        if self.route not in BULKSMS_ROUTING_GROUPS:
            msg = 'The route specified ({}) is invalid.'.format(route)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Define whether or not we should set the unicode flag
        self.unicode = self.template_args['unicode']['default'] \
            if unicode is None else bool(unicode)

        # Define whether or not we should operate in a batch mode
        self.batch = self.template_args['batch']['default'] \
            if batch is None else bool(batch)

        # Parse our targets
        self.targets = list()
        self.groups = list()

        for target in parse_phone_no(targets):
            # Parse each phone number we found
            result = is_phone_no(target)
            if result:
                self.targets.append('+{}'.format(result['full']))
                continue

            group_re = IS_GROUP_RE.match(target)
            if group_re and not target.isdigit():
                # If the target specified is all digits, it MUST have a @
                # in front of it to eliminate any ambiguity
                self.groups.append(group_re.group('group'))
                continue

            self.logger.warning(
                'Dropped invalid phone # and/or Group '
                '({}) specified.'.format(target),
            )

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform BulkSMS Notification
        """

        if not (self.password and self.user):
            self.logger.warning(
                'There were no valid login credentials provided')
            return False

        if not (self.targets or self.groups):
            # We have nothing to notify
            self.logger.warning('There are no BulkSMS targets to notify')
            return False

        # Send in batches if identified to do so
        batch_size = 1 if not self.batch else self.default_batch_size

        # error tracking (used for function return)
        has_error = False

        # Prepare our headers
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
        }

        # Prepare our payload
        payload = {
            # The To gets populated in the loop below
            'to': None,
            'body': body,
            'routingGroup': self.route,
            'encoding': BulkSMSEncoding.UNICODE
            if self.unicode else BulkSMSEncoding.TEXT,
            # Options are NONE, ALL and ERRORS
            'deliveryReports': "ERRORS"
        }

        if self.source:
            payload.update({
                'from': self.source,
            })

        # Authentication
        auth = (self.user, self.password)

        # Prepare our targets
        targets = list(self.targets) if batch_size == 1 else \
            [self.targets[index:index + batch_size]
             for index in range(0, len(self.targets), batch_size)]
        targets += [{"type": "GROUP", "name": g} for g in self.groups]

        while len(targets):
            # Get our target to notify
            target = targets.pop(0)

            # Prepare our user
            payload['to'] = target

            # Printable reference
            if isinstance(target, dict):
                p_target = target['name']

            elif isinstance(target, list):
                p_target = '{} targets'.format(len(target))

            else:
                p_target = target

            # Some Debug Logging
            self.logger.debug('BulkSMS POST URL: {} (cert_verify={})'.format(
                self.notify_url, self.verify_certificate))
            self.logger.debug('BulkSMS Payload: {}' .format(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.post(
                    self.notify_url,
                    data=json.dumps(payload),
                    headers=headers,
                    auth=auth,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )

                # The responsne might look like:
                # [
                #   {
                #       "id": "string",
                #       "type": "SENT",
                #       "from": "string",
                #       "to": "string",
                #       "body": null,
                #       "encoding": "TEXT",
                #       "protocolId": 0,
                #       "messageClass": 0,
                #       "numberOfParts": 0,
                #       "creditCost": 0,
                #       "submission": {...},
                #       "status": {...},
                #       "relatedSentMessageId": "string",
                #       "userSuppliedId": "string"
                #   }
                # ]

                if r.status_code not in (
                        requests.codes.created, requests.codes.ok):
                    # We had a problem
                    status_str = \
                        NotifyBase.http_response_code_lookup(r.status_code)

                    # set up our status code to use
                    status_code = r.status_code

                    self.logger.warning(
                        'Failed to send BulkSMS notification to {}: '
                        '{}{}error={}.'.format(
                            p_target,
                            status_str,
                            ', ' if status_str else '',
                            status_code))

                    self.logger.debug(
                        'Response Details:\r\n{}'.format(r.content))

                    # Mark our failure
                    has_error = True
                    continue

                else:
                    self.logger.info(
                        'Sent BulkSMS notification to {}.'.format(p_target))

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occurred sending BulkSMS: to %s ',
                    p_target)
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
            'batch': 'yes' if self.batch else 'no',
            'route': self.route,
        }

        if self.source:
            params['from'] = self.source

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return '{schema}://{user}:{password}@{targets}/?{params}'.format(
            schema=self.secure_protocol,
            user=self.pprint(self.user, privacy, safe=''),
            password=self.pprint(
                self.password, privacy, mode=PrivacyMode.Secret, safe=''),
            targets='/'.join(chain(
                [NotifyBulkSMS.quote('{}'.format(x), safe='+')
                 for x in self.targets],
                [NotifyBulkSMS.quote('@{}'.format(x), safe='@')
                 for x in self.groups])),
            params=NotifyBulkSMS.urlencode(params))

    @property
    def url_identifier(self):
        """
        Returns all of the identifiers that make this URL unique from
        another simliar one. Targets or end points should never be identified
        here.
        """
        return (
            self.secure_protocol,
            self.user if self.user else None,
            self.password if self.password else None,
        )

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """

        #
        # Factor batch into calculation
        #
        # Note: Groups always require a separate request (and can not be
        # included in batch calculations)
        batch_size = 1 if not self.batch else self.default_batch_size
        targets = len(self.targets)
        if batch_size > 1:
            targets = int(targets / batch_size) + \
                (1 if targets % batch_size else 0)

        return targets + len(self.groups)

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
        results['targets'] = [
            NotifyBulkSMS.unquote(results['host']),
            *NotifyBulkSMS.split_path(results['fullpath'])]

        # Support the 'from'  and 'source' variable so that we can support
        # targets this way too.
        # The 'from' makes it easier to use yaml configuration
        if 'from' in results['qsd'] and len(results['qsd']['from']):
            results['source'] = \
                NotifyBulkSMS.unquote(results['qsd']['from'])

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyBulkSMS.parse_phone_no(results['qsd']['to'])

        # Unicode Characters
        results['unicode'] = \
            parse_bool(results['qsd'].get(
                'unicode', NotifyBulkSMS.template_args['unicode']['default']))

        # Get Batch Mode Flag
        results['batch'] = \
            parse_bool(results['qsd'].get(
                'batch', NotifyBulkSMS.template_args['batch']['default']))

        # Allow one to define a route group
        if 'route' in results['qsd'] and len(results['qsd']['route']):
            results['route'] = \
                NotifyBulkSMS.unquote(results['qsd']['route'])

        return results
