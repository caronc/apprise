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

# To use this plugin, sign up with Hampager (you need to be a licensed
# ham radio operator
#  http://www.hampager.de/
#
# You're done at this point, you only need to know your user/pass that
# you signed up with.

#  The following URLs would be accepted by Apprise:
#   - dapnet://{user}:{password}@{callsign}
#   - dapnet://{user}:{password}@{callsign1}/{callsign2}

# Optional parameters:
#   - priority (NORMAL or EMERGENCY). Default: NORMAL
#   - txgroups --> comma-separated list of DAPNET transmitter
#                           groups. Default: 'dl-all'
#                           https://hampager.de/#/transmitters/groups

from json import dumps

# The API reference used to build this plugin was documented here:
#  https://hampager.de/dokuwiki/doku.php#dapnet_api
#
import requests
from requests.auth import HTTPBasicAuth

from .base import NotifyBase
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..common import NotifyType
from ..utils.parse import (
    is_call_sign, parse_call_sign, parse_list, parse_bool)


class DapnetPriority:
    NORMAL = 0
    EMERGENCY = 1


DAPNET_PRIORITIES = {
    DapnetPriority.NORMAL: 'normal',
    DapnetPriority.EMERGENCY: 'emergency',
}


DAPNET_PRIORITY_MAP = {
    # Maps against string 'normal'
    'n': DapnetPriority.NORMAL,
    # Maps against string 'emergency'
    'e': DapnetPriority.EMERGENCY,

    # Entries to additionally support (so more like Dapnet's API)
    '0': DapnetPriority.NORMAL,
    '1': DapnetPriority.EMERGENCY,
}


class NotifyDapnet(NotifyBase):
    """
    A wrapper for DAPNET / Hampager Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Dapnet'

    # The services URL
    service_url = 'https://hampager.de/'

    # The default secure protocol
    secure_protocol = 'dapnet'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_dapnet'

    # Dapnet uses the http protocol with JSON requests
    notify_url = 'http://www.hampager.de:8080/calls'

    # The maximum length of the body
    body_maxlen = 80

    # A title can not be used for Dapnet Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # The maximum amount of emails that can reside within a single transmission
    default_batch_size = 50

    # Define object templates
    templates = ('{schema}://{user}:{password}@{targets}',)

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
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
            'target_callsign': {
                'name': _('Target Callsign'),
                'type': 'string',
                'regex': (
                    r'^[a-z0-9]{2,5}(-[a-z0-9]{1,2})?$', 'i',
                ),
                'map_to': 'targets',
            },
            'targets': {
                'name': _('Targets'),
                'type': 'list:string',
                'required': True,
            },
        }
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            'to': {
                'name': _('Target Callsign'),
                'type': 'string',
                'map_to': 'targets',
            },
            'priority': {
                'name': _('Priority'),
                'type': 'choice:int',
                'values': DAPNET_PRIORITIES,
                'default': DapnetPriority.NORMAL,
            },
            'txgroups': {
                'name': _('Transmitter Groups'),
                'type': 'string',
                'default': 'dl-all',
                'private': True,
            },
            'batch': {
                'name': _('Batch Mode'),
                'type': 'bool',
                'default': False,
            },
        }
    )

    def __init__(self, targets=None, priority=None, txgroups=None,
                 batch=False, **kwargs):
        """
        Initialize Dapnet Object
        """
        super().__init__(**kwargs)

        # Parse our targets
        self.targets = list()

        # The Priority of the message
        self.priority = int(
            NotifyDapnet.template_args['priority']['default']
            if priority is None else
            next((
                v for k, v in DAPNET_PRIORITY_MAP.items()
                if str(priority).lower().startswith(k)),
                NotifyDapnet.template_args['priority']['default']))

        if not (self.user and self.password):
            msg = 'A Dapnet user/pass was not provided.'
            self.logger.warning(msg)
            raise TypeError(msg)

        # Get the transmitter group
        self.txgroups = parse_list(
            NotifyDapnet.template_args['txgroups']['default']
            if not txgroups else txgroups)

        # Prepare Batch Mode Flag
        self.batch = batch

        for target in parse_call_sign(targets):
            # Validate targets and drop bad ones:
            result = is_call_sign(target)
            if not result:
                self.logger.warning(
                    'Dropping invalid Amateur radio call sign ({}).'.format(
                        target),
                )
                continue

            # Store callsign without SSID and ignore duplicates
            if result['callsign'] not in self.targets:
                self.targets.append(result['callsign'])

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Dapnet Notification
        """

        if not self.targets:
            # There is no one to email; we're done
            self.logger.warning(
                'There are no Amateur radio callsigns to notify')
            return False

        # Send in batches if identified to do so
        batch_size = 1 if not self.batch else self.default_batch_size

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json; charset=utf-8',
        }

        # error tracking (used for function return)
        has_error = False

        # Create a copy of the targets list
        targets = list(self.targets)

        for index in range(0, len(targets), batch_size):

            # prepare JSON payload
            payload = {
                'text': body,
                'callSignNames': targets[index:index + batch_size],
                'transmitterGroupNames': self.txgroups,
                'emergency': (self.priority == DapnetPriority.EMERGENCY),
            }

            self.logger.debug('DAPNET POST URL: %s' % self.notify_url)
            self.logger.debug('DAPNET Payload: %s' % dumps(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.post(
                    self.notify_url,
                    data=dumps(payload),
                    headers=headers,
                    auth=HTTPBasicAuth(
                        username=self.user, password=self.password),
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )
                if r.status_code != requests.codes.created:
                    # We had a problem

                    self.logger.warning(
                        'Failed to send DAPNET notification {} to {}: '
                        'error={}.'.format(
                            payload['text'],
                            ' to {}'.format(self.targets),
                            r.status_code
                        )
                    )

                    self.logger.debug(
                        'Response Details:\r\n{}'.format(r.content))

                    # Mark our failure
                    has_error = True

                else:
                    self.logger.info(
                        'Sent \'{}\' DAPNET notification {}'.format(
                            payload['text'], 'to {}'.format(self.targets)
                        )
                    )

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occurred sending DAPNET '
                    'notification to {}'.format(self.targets)
                )
                self.logger.debug('Socket Exception: %s' % str(e))

                # Mark our failure
                has_error = True

        return not has_error

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'priority':
                DAPNET_PRIORITIES[self.template_args['priority']['default']]
                if self.priority not in DAPNET_PRIORITIES
                else DAPNET_PRIORITIES[self.priority],
            'batch': 'yes' if self.batch else 'no',
            'txgroups': ','.join(self.txgroups),
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Setup Authentication
        auth = '{user}:{password}@'.format(
            user=NotifyDapnet.quote(self.user, safe=""),
            password=self.pprint(
                self.password, privacy, mode=PrivacyMode.Secret, safe=''
            ),
        )

        return '{schema}://{auth}{targets}?{params}'.format(
            schema=self.secure_protocol,
            auth=auth,
            targets='/'.join([self.pprint(x, privacy, safe='')
                              for x in self.targets]),
            params=NotifyDapnet.urlencode(params),
        )

    @property
    def url_identifier(self):
        """
        Returns all of the identifiers that make this URL unique from
        another simliar one. Targets or end points should never be identified
        here.
        """
        return (self.secure_protocol, self.user, self.password)

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """
        #
        # Factor batch into calculation
        #
        batch_size = 1 if not self.batch else self.default_batch_size
        targets = len(self.targets)
        if batch_size > 1:
            targets = int(targets / batch_size) + \
                (1 if targets % batch_size else 0)

        return targets

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

        # All elements are targets
        results['targets'] = [NotifyDapnet.unquote(results['host'])]

        # All entries after the hostname are additional targets
        results['targets'].extend(NotifyDapnet.split_path(results['fullpath']))

        # Support the 'to' variable so that we can support rooms this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyDapnet.parse_list(results['qsd']['to'])

        # Set our priority
        if 'priority' in results['qsd'] and len(results['qsd']['priority']):
            results['priority'] = \
                NotifyDapnet.unquote(results['qsd']['priority'])

        # Check for one or multiple transmitter groups (comma separated)
        # and split them up, when necessary
        if 'txgroups' in results['qsd']:
            results['txgroups'] = \
                [x.lower() for x in
                 NotifyDapnet.parse_list(results['qsd']['txgroups'])]

        # Get Batch Mode Flag
        results['batch'] = \
            parse_bool(results['qsd'].get(
                'batch', NotifyDapnet.template_args['batch']['default']))

        return results
