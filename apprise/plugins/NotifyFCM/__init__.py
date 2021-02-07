# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Chris Caron <lead2gold@gmail.com>
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
# Visit your console page: https://console.firebase.google.com
# 1. Create a project if you haven't already.  If you did the
#    {project} ID will be listed as name-XXXXX.
# 2. Click on your project from here to open it up.
# 3. Access your Web API Key by clicking on:
#     - The (gear-next-to-project-name) > Project Settings > Cloud Messaging

# Visit the following site to get you're Project information:
#    - https://console.cloud.google.com/project/_/settings/general/
#
# Docs: https://firebase.google.com/docs/cloud-messaging/send-message

# Legacy Docs:
# https://firebase.google.com/docs/cloud-messaging/http-server-ref\
#       #send-downstream
#
# If you Generate a new private key, it will provide a .json file
# You will need this in order to send an apprise messag
import six
import requests
from json import dumps
from .oauth import GoogleOAuth
from ..NotifyBase import NotifyBase
from ...common import NotifyType
from ...utils import validate_regex
from ...utils import parse_list
from ...AppriseAttachment import AppriseAttachment
from ...AppriseLocale import gettext_lazy as _

# Our lookup map
FCM_HTTP_ERROR_MAP = {
    400: 'A bad request was made to the server.',
    401: 'The provided API Key was not valid.',
    404: 'The token could not be registered.',
}


class FCMMode(object):
    """
    Define the Firebase Cloud Messaging Modes
    """
    # The legacy way of sending a message
    Legacy = "legacy"

    # The new API
    OAuth2 = "oauth2"


# FCM Modes
FCM_MODES = (
    # Legacy API
    FCMMode.Legacy,
    # HTTP v1 URL
    FCMMode.OAuth2,
)


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
    notify_oauth2_url = \
        "https://fcm.googleapis.com/v1/projects/{project}/messages:send"

    notify_legacy_url = "https://fcm.googleapis.com/fcm/send"

    # There is no reason we should exceed 5KB when reading in a JSON file.
    # If it is more than this, then it is not accepted.
    max_fcm_keyfile_size = 5000

    # The maximum length of the body
    body_maxlen = 1024

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Define object templates
    templates = (
        # OAuth2
        '{schema}://{project}/{targets}?keyfile={keyfile}',
        # Legacy Mode
        '{schema}://{apikey}/{targets}',
    )

    # Define our template
    template_tokens = dict(NotifyBase.template_tokens, **{
        'apikey': {
            'name': _('API Key'),
            'type': 'string',
            'private': True,
        },
        'keyfile': {
            'name': _('OAuth2 KeyFile'),
            'type': 'string',
            'private': True,
        },
        'mode': {
            'name': _('Mode'),
            'type': 'choice:string',
            'values': FCM_MODES,
            'default': FCMMode.Legacy,
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

    def __init__(self, project, apikey, targets=None, mode=None, keyfile=None,
                 **kwargs):
        """
        Initialize Firebase Cloud Messaging

        """
        super(NotifyFCM, self).__init__(**kwargs)

        if mode is None:
            # Detect our mode
            self.mode = FCMMode.OAuth2 if keyfile else FCMMode.Legacy

        else:
            # Setup our mode
            self.mode = NotifyFCM.template_tokens['mode']['default'] \
                if not isinstance(mode, six.string_types) else mode.lower()
            if self.mode and self.mode not in FCM_MODES:
                msg = 'The mode specified ({}) is invalid.'.format(mode)
                self.logger.warning(msg)
                raise TypeError(msg)

        # Used for Legacy Mode; this is the Web API Key retrieved from the
        # User Panel
        self.apikey = None

        # Path to our Keyfile
        self.keyfile = None

        # Our Project ID is required to verify against the keyfile
        # specified
        self.project = None

        # Initialize our Google OAuth module we can work with
        self.oauth = GoogleOAuth(
            user_agent=self.app_id, timeout=self.request_timeout,
            verify_certificate=self.verify_certificate)

        if self.mode == FCMMode.OAuth2:
            # The project ID associated with the account
            self.project = validate_regex(project)
            if not self.project:
                msg = 'An invalid FCM Project ID ' \
                      '({}) was specified.'.format(project)
                self.logger.warning(msg)
                raise TypeError(msg)

            if not keyfile:
                msg = 'No FCM JSON KeyFile was specified.'
                self.logger.warning(msg)
                raise TypeError(msg)

            # Our keyfile object is just an AppriseAttachment object
            self.keyfile = AppriseAttachment(asset=self.asset)
            # Add our definition to our template
            self.keyfile.add(keyfile)
            # Enforce maximum file size
            self.keyfile[0].max_file_size = self.max_fcm_keyfile_size

        else:  # Legacy Mode

            # The apikey associated with the account
            self.apikey = validate_regex(apikey)
            if not self.apikey:
                msg = 'An invalid FCM API key ' \
                      '({}) was specified.'.format(apikey)
                self.logger.warning(msg)
                raise TypeError(msg)

        # Acquire Device IDs to notify
        self.targets = parse_list(targets)
        return

    @property
    def access_token(self):
        """
        Generates a access_token based on the keyfile provided
        """
        keyfile = self.keyfile[0]
        if not keyfile:
            # We could not access the keyfile
            self.logger.error(
                'Could not access FCM keyfile {}.'.format(
                    keyfile.url(privacy=True)))
            return None

        if not self.oauth.load(keyfile.path):
            self.logger.error(
                'FCM keyfile {} could not be loaded.'.format(
                    keyfile.url(privacy=True)))
            return None

        # Verify our project id against the one provided in our keyfile
        if self.project != self.oauth.project_id:
            self.logger.error(
                'FCM keyfile {} identifies itself for a different project'
                .format(keyfile.url(privacy=True)))
            return None

        # Return our generated key; the below returns None if a token could
        # not be acquired
        return self.oauth.access_token

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform FCM Notification
        """

        if not self.targets:
            # There is no one to email; we're done
            self.logger.warning('There are no FCM devices or topics to notify')
            return False

        if self.mode == FCMMode.OAuth2:
            access_token = self.access_token
            if not access_token:
                # Error message is generated in access_tokengen() so no reason
                # to additionally write anything here
                return False

            headers = {
                'User-Agent': self.app_id,
                'Content-Type': 'application/json',
                "Authorization": "Bearer {}".format(access_token),
            }

            # Prepare our notify URL
            notify_url = self.notify_oauth2_url

        else:  # FCMMode.Legacy
            headers = {
                'User-Agent': self.app_id,
                'Content-Type': 'application/json',
                "Authorization": "key={}".format(self.apikey),
            }

            # Prepare our notify URL
            notify_url = self.notify_legacy_url

        has_error = False
        # Create a copy of the targets list
        targets = list(self.targets)
        while len(targets):
            recipient = targets.pop(0)

            if self.mode == FCMMode.OAuth2:
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

            else:  # FCMMode.Legacy
                payload = {
                    'notification': {
                        'notification': {
                            'title': title,
                            'body': body,
                        }
                    }
                }
                if recipient[0] == '#':
                    payload['to'] = '/topics/{}'.format(recipient)
                    self.logger.debug(
                        "FCM recipient %s parsed as a topic",
                        recipient[1:])

                else:
                    payload['to'] = recipient
                    self.logger.debug(
                        "FCM recipient %s parsed as a device token",
                        recipient)

            self.logger.debug(
                'FCM %s POST URL: %s (cert_verify=%r)',
                self.mode, notify_url, self.verify_certificate,
            )
            self.logger.debug('FCM %s Payload: %s', self.mode, str(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.post(
                    notify_url.format(project=self.project),
                    data=dumps(payload),
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )
                if r.status_code not in (
                        requests.codes.ok, requests.codes.no_content):
                    # We had a problem
                    status_str = \
                        NotifyBase.http_response_code_lookup(
                            r.status_code, FCM_HTTP_ERROR_MAP)

                    self.logger.warning(
                        'Failed to send {} FCM notification: '
                        '{}{}error={}.'.format(
                            self.mode,
                            status_str,
                            ', ' if status_str else '',
                            r.status_code))

                    self.logger.debug(
                        'Response Details:\r\n%s', r.content)

                    has_error = True

                else:
                    self.logger.info('Sent %s FCM notification.', self.mode)

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

        # Define any URL parameters
        params = {
            'mode': self.mode,
        }

        if self.keyfile:
            # Include our keyfile if specified
            params['keyfile'] = NotifyFCM.quote(
                self.keyfile[0].url(privacy=privacy), safe='')

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        reference = NotifyFCM.quote(self.project) \
            if self.mode == FCMMode.OAuth2 \
            else self.pprint(self.apikey, privacy, safe='')

        return '{schema}://{reference}/{targets}?{params}'.format(
            schema=self.secure_protocol,
            reference=reference,
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

        # The apikey/project is stored in the hostname
        results['apikey'] = NotifyFCM.unquote(results['host'])
        results['project'] = results['apikey']

        # Get our Device IDs
        results['targets'] = NotifyFCM.split_path(results['fullpath'])

        # Get our mode
        results['mode'] = results['qsd'].get('mode')

        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyFCM.parse_list(results['qsd']['to'])

        # Our Project ID
        if 'project' in results['qsd'] and results['qsd']['project']:
            results['project'] = \
                NotifyFCM.unquote(results['qsd']['project'])

        # Our Web API Key
        if 'apikey' in results['qsd'] and results['qsd']['apikey']:
            results['apikey'] = \
                NotifyFCM.unquote(results['qsd']['apikey'])

        # Our Keyfile (JSON)
        if 'keyfile' in results['qsd'] and results['qsd']['keyfile']:
            results['keyfile'] = \
                NotifyFCM.unquote(results['qsd']['keyfile'])

        return results
