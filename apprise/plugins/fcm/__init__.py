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
import requests
from json import dumps
from ..base import NotifyBase
from ...common import NotifyType
from ...utils import validate_regex
from ...utils import parse_list
from ...utils import parse_bool
from ...utils import dict_full_update
from ...common import NotifyImageSize
from ...apprise_attachment import AppriseAttachment
from ...locale import gettext_lazy as _
from .common import (FCMMode, FCM_MODES)
from .priority import (FCM_PRIORITIES, FCMPriorityManager)
from .color import FCMColorManager

# Default our global support flag
NOTIFY_FCM_SUPPORT_ENABLED = False

try:
    from .oauth import GoogleOAuth

    # We're good to go
    NOTIFY_FCM_SUPPORT_ENABLED = True

except ImportError:
    # cryptography is the dependency of the .oauth library

    # Create a dummy object for init() call to work
    class GoogleOAuth:
        pass


# Our lookup map
FCM_HTTP_ERROR_MAP = {
    400: 'A bad request was made to the server.',
    401: 'The provided API Key was not valid.',
    404: 'The token could not be registered.',
}


class NotifyFCM(NotifyBase):
    """
    A wrapper for Google's Firebase Cloud Messaging Notifications
    """

    # Set our global enabled flag
    enabled = NOTIFY_FCM_SUPPORT_ENABLED

    requirements = {
        # Define our required packaging in order to work
        'packages_required': 'cryptography'
    }

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

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_256

    # The maximum length of the body
    body_maxlen = 1024

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
        'project': {
            'name': _('Project ID'),
            'type': 'string',
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
            'required': True,
        },
    })

    template_args = dict(NotifyBase.template_args, **{
        'to': {
            'alias_of': 'targets',
        },
        'mode': {
            'name': _('Mode'),
            'type': 'choice:string',
            'values': FCM_MODES,
            'default': FCMMode.Legacy,
        },
        'priority': {
            'name': _('Mode'),
            'type': 'choice:string',
            'values': FCM_PRIORITIES,
        },
        'image_url': {
            'name': _('Custom Image URL'),
            'type': 'string',
        },
        'image': {
            'name': _('Include Image'),
            'type': 'bool',
            'default': False,
            'map_to': 'include_image',
        },
        # Color can either be yes, no, or a #rrggbb (
        # rrggbb without hashtag is accepted to)
        'color': {
            'name': _('Notification Color'),
            'type': 'string',
            'default': 'yes',
        },
    })

    # Define our data entry
    template_kwargs = {
        'data_kwargs': {
            'name': _('Data Entries'),
            'prefix': '+',
        },
    }

    def __init__(self, project, apikey, targets=None, mode=None, keyfile=None,
                 data_kwargs=None, image_url=None, include_image=False,
                 color=None, priority=None, **kwargs):
        """
        Initialize Firebase Cloud Messaging

        """
        super().__init__(**kwargs)

        if mode is None:
            # Detect our mode
            self.mode = FCMMode.OAuth2 if keyfile else FCMMode.Legacy

        else:
            # Setup our mode
            self.mode = NotifyFCM.template_tokens['mode']['default'] \
                if not isinstance(mode, str) else mode.lower()
            if self.mode and self.mode not in FCM_MODES:
                msg = 'The FCM mode specified ({}) is invalid.'.format(mode)
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

        # Our data Keyword/Arguments to include in our outbound payload
        self.data_kwargs = {}
        if isinstance(data_kwargs, dict):
            self.data_kwargs.update(data_kwargs)

        # Include the image as part of the payload
        self.include_image = include_image

        # A Custom Image URL
        # FCM allows you to provide a remote https?:// URL to an image_url
        # located on the internet that it will download and include in the
        # payload.
        #
        # self.image_url() is reserved as an internal function name; so we
        # jsut store it into a different variable for now
        self.image_src = image_url

        # Initialize our priority
        self.priority = FCMPriorityManager(self.mode, priority)

        # Initialize our color
        self.color = FCMColorManager(color, asset=self.asset)
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

        # Acquire image url
        image = self.image_url(notify_type) \
            if not self.image_src else self.image_src

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

                if self.color:
                    # Acquire our color
                    payload['message']['android'] = {
                        'notification': {'color': self.color.get(notify_type)}}

                if self.include_image and image:
                    payload['message']['notification']['image'] = image

                if self.data_kwargs:
                    payload['message']['data'] = self.data_kwargs

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

                if self.color:
                    # Acquire our color
                    payload['notification']['notification']['color'] = \
                        self.color.get(notify_type)

                if self.include_image and image:
                    payload['notification']['notification']['image'] = image

                if self.data_kwargs:
                    payload['data'] = self.data_kwargs

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

            # A more advanced dict.update() that recursively includes
            # sub-dictionaries as well
            dict_full_update(payload, self.priority.payload())

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

    @property
    def url_identifier(self):
        """
        Returns all of the identifiers that make this URL unique from
        another simliar one. Targets or end points should never be identified
        here.
        """
        return (self.secure_protocol, self.mode, self.apikey, self.project)

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'mode': self.mode,
            'image': 'yes' if self.include_image else 'no',
            'color': str(self.color),
        }

        if self.priority:
            # Store our priority if one was defined
            params['priority'] = str(self.priority)

        if self.keyfile:
            # Include our keyfile if specified
            params['keyfile'] = NotifyFCM.quote(
                self.keyfile[0].url(privacy=privacy), safe='')

        if self.image_src:
            # Include our image path as part of our URL payload
            params['image_url'] = self.image_src

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Add our data keyword/args into our URL response
        params.update(
            {'+{}'.format(k): v for k, v in self.data_kwargs.items()})

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

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """
        return len(self.targets)

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

        # Our Priority
        if 'priority' in results['qsd'] and results['qsd']['priority']:
            results['priority'] = \
                NotifyFCM.unquote(results['qsd']['priority'])

        # Our Color
        if 'color' in results['qsd'] and results['qsd']['color']:
            results['color'] = \
                NotifyFCM.unquote(results['qsd']['color'])

        # Boolean to include an image or not
        results['include_image'] = parse_bool(results['qsd'].get(
            'image', NotifyFCM.template_args['image']['default']))

        # Extract image_url if it was specified
        if 'image_url' in results['qsd']:
            results['image_url'] = \
                NotifyFCM.unquote(results['qsd']['image_url'])
            if 'image' not in results['qsd']:
                # Toggle default behaviour if a custom image was provided
                # but ONLY if the `image` boolean was not set
                results['include_image'] = True

        # Store our data keyword/args if specified
        results['data_kwargs'] = results['qsd+']

        return results
