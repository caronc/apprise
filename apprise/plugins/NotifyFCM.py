# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 Chris Caron <lead2gold@gmail.com>
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

# For this plugin to work correct, the FCM server must be set up to allow
# for remote connections.

# Firebase Cloud Messaging
# Docs: https://firebase.google.com/docs/cloud-messaging/send-message

import requests
from json import dumps

from .NotifyBase import NotifyBase
from ..common import NotifyType
from ..utils import validate_regex
from ..utils import parse_list
from ..AppriseLocale import gettext_lazy as _


class NotifyFCM(NotifyBase):
    """
    A wrapper for Google's Firebase Cloud Messaging Notifications
    """
    # The default descriptive name associated with the Notification
    service_name = 'Firebase Cloud Messaging'

    # The services URL
    service_url = 'https://firebase.google.com'

    # The default protocol
    secure_protocol = 'fcm'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_fcm'

    # Project Notification
    # https://firebase.google.com/docs/cloud-messaging/send-message
    notify_url = \
        "https://fcm.googleapis.com/v1/projects/{project}/messages:send"

    # The maximum length of the body
    body_maxlen = 160

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Define object templates
    templates = (
        '{schema}://{project}@{apikey}/{targets}',
    )

    # Define our template
    template_tokens = dict(NotifyBase.template_tokens, **{
        'apikey': {
            'name': _('API Key'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'project': {
            'name': _('Project ID'),
            'type': 'string',
            'required': True,
        },
        'target_device': {
            'name': _('Target Device'),
            'type': 'string',
            'map_to': 'targets',
        },
        'target_topic': {
            'name': _('Target Topic'),
            'type': 'string',
            'prefix': '#',
            'map_to': 'targets',
        },
        'targets': {
            'name': _('Targets'),
            'type': 'list:string',
        },
    })

    template_args = dict(NotifyBase.template_args, **{
        'to': {
            'alias_of': 'targets',
        },
    })

    def __init__(self, project, apikey, targets=None, **kwargs):
        """
        Initialize Firebase Cloud Messaging

        """
        super(NotifyFCM, self).__init__(**kwargs)

        # The apikey associated with the account
        self.apikey = validate_regex(apikey)
        if not self.apikey:
            msg = 'An invalid FCM API key ' \
                  '({}) was specified.'.format(apikey)
            self.logger.warning(msg)
            raise TypeError(msg)

        # The project ID associated with the account
        self.project = validate_regex(project)
        if not self.project:
            msg = 'An invalid FCM Project ID ' \
                  '({}) was specified.'.format(project)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Acquire Device IDs to notify
        self.targets = parse_list(targets)
        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform FCM Notification
        """

        if not self.targets:
            # There is no one to email; we're done
            self.logger.warning('There are no devices or topics to notify')
            return False

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
            "Authorization": "Bearer {}".format(self.apikey),
        }

        has_error = False
        # Create a copy of the targets list
        targets = list(self.targets)
        while len(targets):
            recipient = targets.pop(0)

            payload = {
                'message': {
                    'token': None,
                    'notification': {
                        'title': title,
                        'body': body,
                    }
                }
            }

            if recipient[0] == '#':
                payload['message']['topic'] = recipient[1:]
                self.logger.debug(
                    "FCM recipient %s parsed as a topic",
                    recipient[1:])

            else:
                payload['message']['token'] = recipient
                self.logger.debug(
                    "FCM recipient %s parsed as a device token",
                    recipient)

            self.logger.debug('FCM POST URL: %s (cert_verify=%r)' % (
                self.notify_url, self.verify_certificate,
            ))
            self.logger.debug('FCM Payload: %s' % str(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.post(
                    self.notify_url.format(project=self.project),
                    data=dumps(payload),
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )
                if r.status_code not in (
                        requests.codes.ok, requests.codes.no_content):
                    # We had a problem
                    status_str = \
                        NotifyFCM.http_response_code_lookup(
                            r.status_code)

                    self.logger.warning(
                        'Failed to send FCM notification: '
                        '{}{}error={}.'.format(
                            status_str,
                            ', ' if status_str else '',
                            r.status_code))

                    self.logger.debug(
                        'Response Details:\r\n%s', r.content)

                    has_error = True

                else:
                    self.logger.info('Sent FCM notification.')

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occurred sending FCM '
                    'notification.'
                )
                self.logger.debug('Socket Exception: %s', str(e))

                has_error = True

        return not has_error

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Our URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        return '{schema}://{project}@{apikey}/{targets}?{params}'.format(
            schema=self.secure_protocol,
            project=NotifyFCM.quote(self.project),
            apikey=self.pprint(self.apikey, privacy, safe=''),
            targets='/'.join(
                [NotifyFCM.quote(x) for x in self.targets]),
            params=NotifyFCM.urlencode(params),
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

        # The project identifier associated with the account
        results['project'] = NotifyFCM.unquote(results['user'])

        # The apikey is stored in the hostname
        results['apikey'] = NotifyFCM.unquote(results['host'])

        # Get our Device IDs
        results['targets'] = NotifyFCM.split_path(results['fullpath'])

        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyFCM.parse_list(results['qsd']['to'])

        return results
