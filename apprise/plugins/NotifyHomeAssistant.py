# -*- coding: utf-8 -*-
#
# Apprise - Push Notification Library.
# Copyright (C) 2023  Chris Caron <lead2gold@gmail.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor,
# Boston, MA  02110-1301, USA.

# You must generate a "Long-Lived Access Token". This can be done from your
# Home Assistant Profile page.

import requests
from json import dumps

from uuid import uuid4

from .NotifyBase import NotifyBase
from ..URLBase import PrivacyMode
from ..common import NotifyType
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _


class NotifyHomeAssistant(NotifyBase):
    """
    A wrapper for Home Assistant Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'HomeAssistant'

    # The services URL
    service_url = 'https://www.home-assistant.io/'

    # Insecure Protocol Access
    protocol = 'hassio'

    # Secure Protocol
    secure_protocol = 'hassios'

    # Default to Home Assistant Default Insecure port of 8123 instead of 80
    default_insecure_port = 8123

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_homeassistant'

    # Define object templates
    templates = (
        '{schema}://{host}/{accesstoken}',
        '{schema}://{host}:{port}/{accesstoken}',
        '{schema}://{user}@{host}/{accesstoken}',
        '{schema}://{user}@{host}:{port}/{accesstoken}',
        '{schema}://{user}:{password}@{host}/{accesstoken}',
        '{schema}://{user}:{password}@{host}:{port}/{accesstoken}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'host': {
            'name': _('Hostname'),
            'type': 'string',
            'required': True,
        },
        'port': {
            'name': _('Port'),
            'type': 'int',
            'min': 1,
            'max': 65535,
        },
        'user': {
            'name': _('Username'),
            'type': 'string',
        },
        'password': {
            'name': _('Password'),
            'type': 'string',
            'private': True,
        },
        'accesstoken': {
            'name': _('Long-Lived Access Token'),
            'type': 'string',
            'private': True,
            'required': True,
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'nid': {
            # Optional Unique Notification ID
            'name': _('Notification ID'),
            'type': 'string',
            'regex': (r'^[a-z0-9_-]+$', 'i'),
        },
    })

    def __init__(self, accesstoken, nid=None, **kwargs):
        """
        Initialize Home Assistant Object
        """
        super().__init__(**kwargs)

        self.fullpath = kwargs.get('fullpath', '')

        if not (self.secure or self.port):
            # Use default insecure port
            self.port = self.default_insecure_port

        # Long-Lived Access token (generated from User Profile)
        self.accesstoken = validate_regex(accesstoken)
        if not self.accesstoken:
            msg = 'An invalid Home Assistant Long-Lived Access Token ' \
                  '({}) was specified.'.format(accesstoken)
            self.logger.warning(msg)
            raise TypeError(msg)

        # An Optional Notification Identifier
        self.nid = None
        if nid:
            self.nid = validate_regex(
                nid, *self.template_args['nid']['regex'])
            if not self.nid:
                msg = 'An invalid Home Assistant Notification Identifier ' \
                      '({}) was specified.'.format(nid)
                self.logger.warning(msg)
                raise TypeError(msg)

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Sends Message
        """

        # Prepare our persistent_notification.create payload
        payload = {
            'title': title,
            'message': body,
            # Use a unique ID so we don't over-write the last message
            # we posted. Otherwise use the notification id specified
            'notification_id': self.nid if self.nid else str(uuid4()),
        }

        # Prepare our headers
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
            'Authorization': 'Bearer {}'.format(self.accesstoken),
        }

        auth = None
        if self.user:
            auth = (self.user, self.password)

        # Set our schema
        schema = 'https' if self.secure else 'http'

        url = '{}://{}'.format(schema, self.host)
        if isinstance(self.port, int):
            url += ':%d' % self.port

        url += '' if not self.fullpath else '/' + self.fullpath.strip('/')
        url += '/api/services/persistent_notification/create'

        self.logger.debug('Home Assistant POST URL: %s (cert_verify=%r)' % (
            url, self.verify_certificate,
        ))
        self.logger.debug('Home Assistant Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                url,
                data=dumps(payload),
                headers=headers,
                auth=auth,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyHomeAssistant.http_response_code_lookup(
                        r.status_code)

                self.logger.warning(
                    'Failed to send Home Assistant notification: '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return False

            else:
                self.logger.info('Sent Home Assistant notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred sending Home Assistant '
                'notification to %s.' % self.host)
            self.logger.debug('Socket Exception: %s' % str(e))

            # Return; we're done
            return False

        return True

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {}
        if self.nid:
            params['nid'] = self.nid

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Determine Authentication
        auth = ''
        if self.user and self.password:
            auth = '{user}:{password}@'.format(
                user=NotifyHomeAssistant.quote(self.user, safe=''),
                password=self.pprint(
                    self.password, privacy, mode=PrivacyMode.Secret, safe=''),
            )
        elif self.user:
            auth = '{user}@'.format(
                user=NotifyHomeAssistant.quote(self.user, safe=''),
            )

        default_port = 443 if self.secure else self.default_insecure_port

        url = '{schema}://{auth}{hostname}{port}{fullpath}' \
              '{accesstoken}/?{params}'

        return url.format(
            schema=self.secure_protocol if self.secure else self.protocol,
            auth=auth,
            # never encode hostname since we're expecting it to be a valid one
            hostname=self.host,
            port='' if not self.port or self.port == default_port
            else ':{}'.format(self.port),
            fullpath='/' if not self.fullpath else '/{}/'.format(
                NotifyHomeAssistant.quote(self.fullpath.strip('/'), safe='/')),
            accesstoken=self.pprint(self.accesstoken, privacy, safe=''),
            params=NotifyHomeAssistant.urlencode(params),
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

        # Get our Long-Lived Access Token
        if 'accesstoken' in results['qsd'] and \
                len(results['qsd']['accesstoken']):
            results['accesstoken'] = \
                NotifyHomeAssistant.unquote(results['qsd']['accesstoken'])

        else:
            # Acquire our full path
            fullpath = NotifyHomeAssistant.split_path(results['fullpath'])

            # Otherwise pop the last element from our path to be it
            results['accesstoken'] = fullpath.pop() if fullpath else None

            # Re-assemble our full path
            results['fullpath'] = '/'.join(fullpath)

        # Allow the specification of a unique notification_id so that
        # it will always replace the last one sent.
        if 'nid' in results['qsd'] and len(results['qsd']['nid']):
            results['nid'] = \
                NotifyHomeAssistant.unquote(results['qsd']['nid'])

        return results
