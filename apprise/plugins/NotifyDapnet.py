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
#   - transmittergroups --> comma-separated list of DAPNET transmitter
#                           groups. Default: 'dl-all'
#                           https://hampager.de/#/transmitters/groups

from json import dumps

# The API reference used to build this plugin was documented here:
#  https://hampager.de/dokuwiki/doku.php#dapnet_api
#
import requests
from requests.auth import HTTPBasicAuth

from .NotifyBase import NotifyBase
from ..AppriseLocale import gettext_lazy as _
from ..URLBase import PrivacyMode
from ..common import NotifyType
from ..utils import is_call_sign
from ..utils import parse_call_sign


class DapnetPriority(object):
    NORMAL = 0
    EMERGENCY = 1


DAPNET_PRIORITIES = (
    DapnetPriority.NORMAL,
    DapnetPriority.EMERGENCY,
)


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

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

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
                    r'^[a-z0-9]{1,3}[0-9][a-z0-9]{0,3}[-]{0,1}[a-z0-9]{1,2}$',
                    'i',
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
            'priority': {
                'name': _('Priority'),
                'type': 'choice:int',
                'values': DAPNET_PRIORITIES,
                'default': DapnetPriority.NORMAL,
            },
            'transmittergroups': {
                'name': _('Transmitter Groups'),
                'type': 'string',
                'default': ['dl-all'],
                'private': True,
            },
        }
    )

    def __init__(self, targets=None, priority=None,
                 transmittergroups=None, **kwargs):
        """
        Initialize Dapnet Object
        """
        super(NotifyDapnet, self).__init__(**kwargs)

        # Parse our targets
        self.targets = list()

        # get the emergency prio setting
        if priority not in DAPNET_PRIORITIES:
            self.priority = self.template_args['priority']['default']
        else:
            self.priority = priority

        if not (self.user and self.password):
            msg = 'A Dapnet user/pass was not provided.'
            self.logger.warning(msg)
            raise TypeError(msg)

        # Get the transmitter group
        self.transmittergroups = transmittergroups
        if not self.transmittergroups:
            msg = 'Transmitter Groups not specified; using default'
            self.logger.debug(msg)
            self.transmittergroups = ['dl-all']

        for target in parse_call_sign(targets):
            # Validate targets and drop bad ones:
            result = is_call_sign(target)
            if not result:
                self.logger.warning(
                    'Dropping invalid call sign ({}).'.format(target),
                )
                continue

            # store valid call sign if not yet present
            # duplicates are possible if the user has
            # provided call signs with SSIDs
            if result['callsign'] not in self.targets:
                self.targets.append(result['callsign'])

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Dapnet Notification
        """

        if len(self.targets) == 0:
            # There were no services to notify
            self.logger.warning('There were no Dapnet targets to notify.')
            return False

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json; charset=utf-8',
        }

        # error tracking (used for function return)
        has_error = False

        # prepare JSON payload

        # prepare the emergency mode
        emergency_mode = True \
            if self.priority == DapnetPriority.EMERGENCY else False

        # truncate the body (if necessary)
        _payload_body = body
        if len(_payload_body) > 80:
            self.logger.debug('Message exceeds max DAPNET msglen; truncating')
            _payload_body = _payload_body[:80]

        payload = {
            'text': _payload_body,
            'callSignNames': self.targets,
            'transmitterGroupNames': self.transmittergroups,
            'emergency': emergency_mode,
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
                auth=HTTPBasicAuth(username=self.user, password=self.password),
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

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Mark our failure
                has_error = True

            else:
                self.logger.info(
                    'Sent {} DAPNET notification {}'.format(
                        payload['text'], ' to {}'.format(self.targets)
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
        _map = {
            DapnetPriority.NORMAL: 'normal',
            DapnetPriority.EMERGENCY: 'emergency',
        }

        # Define any URL parameters
        params = {
            'priority': 'normal' if self.priority not in _map
            else _map[self.priority],
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
            targets='/'.join([NotifyDapnet.quote(x, safe='')
                              for x in self.targets]),
            params=NotifyDapnet.urlencode(params),
        )

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
                NotifyDapnet.parse_call_sign(results['qsd']['to'])

        # Check for priority
        if 'priority' in results['qsd'] and len(results['qsd']['priority']):
            _map = {
                # Letter Assignments
                'n': DapnetPriority.NORMAL,
                'e': DapnetPriority.EMERGENCY,
                'no': DapnetPriority.NORMAL,
                'em': DapnetPriority.EMERGENCY,
                # Numeric assignments
                '0': DapnetPriority.NORMAL,
                '1': DapnetPriority.EMERGENCY,
            }
            try:
                results['priority'] = \
                    _map[results['qsd']['priority'][0:2].lower()]

            except KeyError:
                # No priority was set
                pass

        # Check for one or multiple transmitter groups (comma separated)
        # and split them up, when necessary
        if 'transmittergroups' in results['qsd']:
            try:
                _tgroups = results['qsd']['transmittergroups'].lower()
                results['transmittergroups'] = \
                    [x.strip() for x in _tgroups.split(',')]
            except KeyError:
                pass

        return results
