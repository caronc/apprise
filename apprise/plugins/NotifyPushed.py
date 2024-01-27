# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2024, Chris Caron <lead2gold@gmail.com>
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

import re
import requests
from json import dumps
from itertools import chain

from .NotifyBase import NotifyBase
from ..URLBase import PrivacyMode
from ..common import NotifyType
from ..utils import parse_list
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _

# Used to detect and parse channels
IS_CHANNEL = re.compile(r'^#?(?P<name>[A-Za-z0-9]+)$')

# Used to detect and parse a users push id
IS_USER_PUSHED_ID = re.compile(r'^@(?P<name>[A-Za-z0-9]+)$')


class NotifyPushed(NotifyBase):
    """
    A wrapper to Pushed Notifications

    """

    # The default descriptive name associated with the Notification
    service_name = 'Pushed'

    # The services URL
    service_url = 'https://pushed.co/'

    # The default secure protocol
    secure_protocol = 'pushed'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_pushed'

    # Pushed uses the http protocol with JSON requests
    notify_url = 'https://api.pushed.co/1/push'

    # A title can not be used for Pushed Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 160

    # Define object templates
    templates = (
        '{schema}://{app_key}/{app_secret}',
        '{schema}://{app_key}/{app_secret}@{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'app_key': {
            'name': _('Application Key'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'app_secret': {
            'name': _('Application Secret'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'target_user': {
            'name': _('Target User'),
            'prefix': '@',
            'type': 'string',
            'map_to': 'targets',
        },
        'target_channel': {
            'name': _('Target Channel'),
            'type': 'string',
            'prefix': '#',
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
    })

    def __init__(self, app_key, app_secret, targets=None, **kwargs):
        """
        Initialize Pushed Object

        """
        super().__init__(**kwargs)

        # Application Key (associated with project)
        self.app_key = validate_regex(app_key)
        if not self.app_key:
            msg = 'An invalid Pushed Application Key ' \
                  '({}) was specified.'.format(app_key)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Access Secret (associated with project)
        self.app_secret = validate_regex(app_secret)
        if not self.app_secret:
            msg = 'An invalid Pushed Application Secret ' \
                  '({}) was specified.'.format(app_secret)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Initialize channel list
        self.channels = list()

        # Initialize user list
        self.users = list()

        # Get our targets
        targets = parse_list(targets)
        if targets:
            # Validate recipients and drop bad ones:
            for target in targets:
                result = IS_CHANNEL.match(target)
                if result:
                    # store valid device
                    self.channels.append(result.group('name'))
                    continue

                result = IS_USER_PUSHED_ID.match(target)
                if result:
                    # store valid room
                    self.users.append(result.group('name'))
                    continue

                self.logger.warning(
                    'Dropped invalid channel/userid '
                    '(%s) specified.' % target,
                )

            if len(self.channels) + len(self.users) == 0:
                # We have no valid channels or users to notify after
                # explicitly identifying at least one.
                msg = 'No Pushed targets to notify.'
                self.logger.warning(msg)
                raise TypeError(msg)

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Pushed Notification
        """

        # Initiaize our error tracking
        has_error = False

        # prepare JSON Object
        payload = {
            'app_key': self.app_key,
            'app_secret': self.app_secret,
            'target_type': 'app',
            'content': body,
        }

        # So the logic is as follows:
        #  - if no user/channel was specified, then we just simply notify the
        #    app.
        #  - if there are user/channels specified, then we only alert them
        #    while respecting throttle limits (in the event there are a lot of
        #    entries.

        if len(self.channels) + len(self.users) == 0:
            # Just notify the app
            return self._send(
                payload=payload, notify_type=notify_type, **kwargs)

        # If our code reaches here, we want to target channels and users (by
        # their Pushed_ID instead...

        # Generate a copy of our original list
        channels = list(self.channels)
        users = list(self.users)

        # Copy our payload
        _payload = dict(payload)
        _payload['target_type'] = 'channel'

        while len(channels) > 0:
            # Get Channel
            _payload['target_alias'] = channels.pop(0)

            if not self._send(
                    payload=_payload, notify_type=notify_type, **kwargs):

                # toggle flag
                has_error = True

        # Copy our payload
        _payload = dict(payload)
        _payload['target_type'] = 'pushed_id'

        # Send all our defined User Pushed ID's
        while len(users):
            # Get User's Pushed ID
            _payload['pushed_id'] = users.pop(0)

            if not self._send(
                    payload=_payload, notify_type=notify_type, **kwargs):

                # toggle flag
                has_error = True

        return not has_error

    def _send(self, payload, notify_type, **kwargs):
        """
        A lower level call that directly pushes a payload to the Pushed
        Notification servers.  This should never be called directly; it is
        referenced automatically through the send() function.
        """

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json'
        }

        self.logger.debug('Pushed POST URL: %s (cert_verify=%r)' % (
            self.notify_url, self.verify_certificate,
        ))
        self.logger.debug('Pushed Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                self.notify_url,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )

            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyPushed.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send Pushed notification:'
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return False

            else:
                self.logger.info('Sent Pushed notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred sending Pushed notification.')
            self.logger.debug('Socket Exception: %s' % str(e))

            # Return; we're done
            return False

        return True

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Our URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        return '{schema}://{app_key}/{app_secret}/{targets}/?{params}'.format(
            schema=self.secure_protocol,
            app_key=self.pprint(self.app_key, privacy, safe=''),
            app_secret=self.pprint(
                self.app_secret, privacy, mode=PrivacyMode.Secret, safe=''),
            targets='/'.join(
                [NotifyPushed.quote(x) for x in chain(
                    # Channels are prefixed with a pound/hashtag symbol
                    ['#{}'.format(x) for x in self.channels],
                    # Users are prefixed with an @ symbol
                    ['@{}'.format(x) for x in self.users],
                )]),
            params=NotifyPushed.urlencode(params))

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """
        targets = len(self.channels) + len(self.users)
        return targets if targets > 0 else 1

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

        # The first token is stored in the hostname
        app_key = NotifyPushed.unquote(results['host'])

        entries = NotifyPushed.split_path(results['fullpath'])
        # Now fetch the remaining tokens
        try:
            app_secret = entries.pop(0)

        except IndexError:
            # Force some bad values that will get caught
            # in parsing later
            app_secret = None
            app_key = None

        # Get our recipients (based on remaining entries)
        results['targets'] = entries

        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyPushed.parse_list(results['qsd']['to'])

        results['app_key'] = app_key
        results['app_secret'] = app_secret

        return results
