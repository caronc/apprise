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

# Great sources
# - https://github.com/matrix-org/matrix-python-sdk
# - https://github.com/matrix-org/synapse/blob/master/docs/reverse_proxy.rst
#
import re
import requests
import uuid
from markdown import markdown
from json import dumps
from json import loads
from time import time

from .base import NotifyBase
from ..url import PrivacyMode
from ..exception import AppriseException
from ..common import NotifyType
from ..common import NotifyImageSize
from ..common import NotifyFormat
from ..common import PersistentStoreMode
from ..utils.parse import (
    parse_bool, parse_list, is_hostname, validate_regex)
from ..locale import gettext_lazy as _

# Define default path
MATRIX_V1_WEBHOOK_PATH = '/api/v1/matrix/hook'
MATRIX_V2_API_PATH = '/_matrix/client/r0'
MATRIX_V3_API_PATH = '/_matrix/client/v3'
MATRIX_V3_MEDIA_PATH = '/_matrix/media/v3'
MATRIX_V2_MEDIA_PATH = '/_matrix/media/r0'


class MatrixDiscoveryException(AppriseException):
    """
    Apprise Matrix Exception Class
    """


# Extend HTTP Error Messages
MATRIX_HTTP_ERROR_MAP = {
    403: 'Unauthorized - Invalid Token.',
    429: 'Rate limit imposed; wait 2s and try again',
}

# Matrix Room Syntax
IS_ROOM_ALIAS = re.compile(
    r'^\s*(#|%23)?(?P<room>[a-z0-9-]+)((:|%3A)'
    r'(?P<home_server>[a-z0-9.-]+))?\s*$', re.I)

# Room ID MUST start with an exclamation to avoid ambiguity
IS_ROOM_ID = re.compile(
    r'^\s*(!|&#33;|%21)(?P<room>[a-z0-9-]+)((:|%3A)'
    r'(?P<home_server>[a-z0-9.-]+))?\s*$', re.I)


class MatrixMessageType:
    """
    The Matrix Message types
    """
    TEXT = "text"
    NOTICE = "notice"


# matrix message types are placed into this list for validation purposes
MATRIX_MESSAGE_TYPES = (
    MatrixMessageType.TEXT,
    MatrixMessageType.NOTICE,
)


class MatrixVersion:
    # Version 2
    V2 = "2"

    # Version 3
    V3 = "3"


# webhook modes are placed into this list for validation purposes
MATRIX_VERSIONS = (
    MatrixVersion.V2,
    MatrixVersion.V3,
)


class MatrixWebhookMode:
    # Webhook Mode is disabled
    DISABLED = "off"

    # The default webhook mode is to just be set to Matrix
    MATRIX = "matrix"

    # Support the slack webhook plugin
    SLACK = "slack"

    # Support the t2bot webhook plugin
    T2BOT = "t2bot"


# webhook modes are placed into this list for validation purposes
MATRIX_WEBHOOK_MODES = (
    MatrixWebhookMode.DISABLED,
    MatrixWebhookMode.MATRIX,
    MatrixWebhookMode.SLACK,
    MatrixWebhookMode.T2BOT,
)


class NotifyMatrix(NotifyBase):
    """
    A wrapper for Matrix Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Matrix'

    # The services URL
    service_url = 'https://matrix.org/'

    # The default protocol
    protocol = 'matrix'

    # The default secure protocol
    secure_protocol = 'matrixs'

    # Support Attachments
    attachment_support = True

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_matrix'

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_32

    # The maximum allowable characters allowed in the body per message
    # https://spec.matrix.org/v1.6/client-server-api/#size-limits
    # The complete event MUST NOT be larger than 65536 bytes, when formatted
    # with the federation event format, including any signatures, and encoded
    # as Canonical JSON.
    #
    # To gracefully allow for some overhead' we'll define a max body length
    # of just slighty lower then the limit of the full message itself.
    body_maxlen = 65000

    # Throttle a wee-bit to avoid thrashing
    request_rate_per_sec = 0.5

    # How many retry attempts we'll make in the event the server asks us to
    # throttle back.
    default_retries = 2

    # The number of micro seconds to wait if we get a 429 error code and
    # the server doesn't remind us how long we shoul wait for
    default_wait_ms = 1000

    # Our default is to no not use persistent storage beyond in-memory
    # reference
    storage_mode = PersistentStoreMode.AUTO

    # Keep our cache for 20 days
    default_cache_expiry_sec = 60 * 60 * 24 * 20

    # Used for server discovery
    discovery_base_key = '__discovery_base'
    discovery_identity_key = '__discovery_identity'

    # Defines how long we cache our discovery for
    discovery_cache_length_sec = 86400

    # Define object templates
    templates = (
        # Targets are ignored when using t2bot mode; only a token is required
        '{schema}://{token}',
        '{schema}://{user}@{token}',

        # Matrix Server
        '{schema}://{user}:{password}@{host}/{targets}',
        '{schema}://{user}:{password}@{host}:{port}/{targets}',
        '{schema}://{token}@{host}/{targets}',
        '{schema}://{token}@{host}:{port}/{targets}',

        # Webhook mode
        '{schema}://{user}:{token}@{host}/{targets}',
        '{schema}://{user}:{token}@{host}:{port}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'host': {
            'name': _('Hostname'),
            'type': 'string',
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
        'token': {
            'name': _('Access Token'),
            'private': True,
            'map_to': 'password',
        },
        'target_user': {
            'name': _('Target User'),
            'type': 'string',
            'prefix': '@',
            'map_to': 'targets',
        },
        'target_room_id': {
            'name': _('Target Room ID'),
            'type': 'string',
            'prefix': '!',
            'map_to': 'targets',
        },
        'target_room_alias': {
            'name': _('Target Room Alias'),
            'type': 'string',
            'prefix': '!',
            'map_to': 'targets',
        },
        'targets': {
            'name': _('Targets'),
            'type': 'list:string',
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'image': {
            'name': _('Include Image'),
            'type': 'bool',
            'default': False,
            'map_to': 'include_image',
        },
        'discovery': {
            'name': _('Server Discovery'),
            'type': 'bool',
            'default': True,
        },
        'mode': {
            'name': _('Webhook Mode'),
            'type': 'choice:string',
            'values': MATRIX_WEBHOOK_MODES,
            'default': MatrixWebhookMode.DISABLED,
        },
        'version': {
            'name': _('Matrix API Verion'),
            'type': 'choice:string',
            'values': MATRIX_VERSIONS,
            'default': MatrixVersion.V3,
        },
        'msgtype': {
            'name': _('Message Type'),
            'type': 'choice:string',
            'values': MATRIX_MESSAGE_TYPES,
            'default': MatrixMessageType.TEXT,
        },
        'to': {
            'alias_of': 'targets',
        },
        'token': {
            'alias_of': 'token',
        },
    })

    def __init__(self, targets=None, mode=None, msgtype=None, version=None,
                 include_image=None, discovery=None, **kwargs):
        """
        Initialize Matrix Object
        """
        super().__init__(**kwargs)

        # Prepare a list of rooms to connect and notify
        self.rooms = parse_list(targets)

        # our home server gets populated after a login/registration
        self.home_server = None

        # our user_id gets populated after a login/registration
        self.user_id = None

        # This gets initialized after a login/registration
        self.access_token = None

        # This gets incremented for each request made against the v3 API
        self.transaction_id = 0

        # Place an image inline with the message body
        self.include_image = self.template_args['image']['default'] \
            if include_image is None else include_image

        # Prepare Delegate Server Lookup Check
        self.discovery = self.template_args['discovery']['default'] \
            if discovery is None else discovery

        # Setup our mode
        self.mode = self.template_args['mode']['default'] \
            if not isinstance(mode, str) else mode.lower()
        if self.mode and self.mode not in MATRIX_WEBHOOK_MODES:
            msg = 'The mode specified ({}) is invalid.'.format(mode)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Setup our version
        self.version = self.template_args['version']['default'] \
            if not isinstance(version, str) else version
        if self.version not in MATRIX_VERSIONS:
            msg = 'The version specified ({}) is invalid.'.format(version)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Setup our message type
        self.msgtype = self.template_args['msgtype']['default'] \
            if not isinstance(msgtype, str) else msgtype.lower()
        if self.msgtype and self.msgtype not in MATRIX_MESSAGE_TYPES:
            msg = 'The msgtype specified ({}) is invalid.'.format(msgtype)
            self.logger.warning(msg)
            raise TypeError(msg)

        if self.mode == MatrixWebhookMode.T2BOT:
            # t2bot configuration requires that a webhook id is specified
            self.access_token = validate_regex(
                self.password, r'^[a-z0-9]{64}$', 'i')
            if not self.access_token:
                msg = 'An invalid T2Bot/Matrix Webhook ID ' \
                      '({}) was specified.'.format(self.password)
                self.logger.warning(msg)
                raise TypeError(msg)

        elif not is_hostname(self.host):
            msg = 'An invalid Matrix Hostname ({}) was specified'\
                  .format(self.host)
            self.logger.warning(msg)
            raise TypeError(msg)

        else:
            # Verify port if specified
            if self.port is not None and not (
                    isinstance(self.port, int)
                    and self.port >= self.template_tokens['port']['min']
                    and self.port <= self.template_tokens['port']['max']):
                msg = 'An invalid Matrix Port ({}) was specified'\
                      .format(self.port)
                self.logger.warning(msg)
                raise TypeError(msg)

        if self.mode != MatrixWebhookMode.DISABLED:
            # Discovery only works when we're not using webhooks
            self.discovery = False

        #
        # Initialize from cache if present
        #
        if self.mode != MatrixWebhookMode.T2BOT:
            # our home server gets populated after a login/registration
            self.home_server = self.store.get('home_server')

            # our user_id gets populated after a login/registration
            self.user_id = self.store.get('user_id')

            # This gets initialized after a login/registration
            self.access_token = self.store.get('access_token')

        # This gets incremented for each request made against the v3 API
        self.transaction_id = 0 if not self.access_token \
            else self.store.get('transaction_id', 0)

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Matrix Notification
        """

        # Call the _send_ function applicable to whatever mode we're in
        # - calls _send_webhook_notification if the mode variable is set
        # - calls _send_server_notification if the mode variable is not set
        return getattr(self, '_send_{}_notification'.format(
            'webhook' if self.mode != MatrixWebhookMode.DISABLED
            else 'server'))(
                body=body, title=title, notify_type=notify_type, **kwargs)

    def _send_webhook_notification(self, body, title='',
                                   notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Matrix Notification as a webhook
        """

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
        }

        if self.mode != MatrixWebhookMode.T2BOT:
            # Acquire our access token from our URL
            access_token = self.password if self.password else self.user

            default_port = 443 if self.secure else 80

            # Prepare our URL
            url = '{schema}://{hostname}:{port}{webhook_path}/{token}'.format(
                schema='https' if self.secure else 'http',
                hostname=self.host,
                port='' if self.port is None
                or self.port == default_port else self.port,
                webhook_path=MATRIX_V1_WEBHOOK_PATH,
                token=access_token,
            )

        else:
            #
            # t2bot Setup
            #

            # Prepare our URL
            url = 'https://webhooks.t2bot.io/api/v1/matrix/hook/' \
                '{token}'.format(token=self.access_token)

        # Retrieve our payload
        payload = getattr(self, '_{}_webhook_payload'.format(self.mode))(
            body=body, title=title, notify_type=notify_type, **kwargs)

        self.logger.debug('Matrix POST URL: %s (cert_verify=%r)' % (
            url, self.verify_certificate,
        ))
        self.logger.debug('Matrix Payload: %s' % str(payload))

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
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyMatrix.http_response_code_lookup(
                        r.status_code, MATRIX_HTTP_ERROR_MAP)

                self.logger.warning(
                    'Failed to send Matrix notification: '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return False

            else:
                self.logger.info('Sent Matrix notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred sending Matrix notification.'
            )
            self.logger.debug('Socket Exception: %s' % str(e))
            # Return; we're done
            return False

        return True

    def _slack_webhook_payload(self, body, title='',
                               notify_type=NotifyType.INFO, **kwargs):
        """
        Format the payload for a Slack based message

        """

        if not hasattr(self, '_re_slack_formatting_rules'):
            # Prepare some one-time slack formatting variables

            self._re_slack_formatting_map = {
                # New lines must become the string version
                r'\r\*\n': '\\n',
                # Escape other special characters
                r'&': '&amp;',
                r'<': '&lt;',
                r'>': '&gt;',
            }

            # Iterate over above list and store content accordingly
            self._re_slack_formatting_rules = re.compile(
                r'(' + '|'.join(self._re_slack_formatting_map.keys()) + r')',
                re.IGNORECASE,
            )

        # Perform Formatting
        title = self._re_slack_formatting_rules.sub(  # pragma: no branch
            lambda x: self._re_slack_formatting_map[x.group()], title,
        )

        body = self._re_slack_formatting_rules.sub(  # pragma: no branch
            lambda x: self._re_slack_formatting_map[x.group()], body,
        )

        # prepare JSON Object
        payload = {
            'username': self.user if self.user else self.app_id,
            # Use Markdown language
            'mrkdwn': (self.notify_format == NotifyFormat.MARKDOWN),
            'attachments': [{
                'title': title,
                'text': body,
                'color': self.color(notify_type),
                'ts': time(),
                'footer': self.app_id,
            }],
        }

        return payload

    def _matrix_webhook_payload(self, body, title='',
                                notify_type=NotifyType.INFO, **kwargs):
        """
        Format the payload for a Matrix based message

        """

        payload = {
            'displayName':
                self.user if self.user else self.app_id,
            'format': 'plain' if self.notify_format == NotifyFormat.TEXT
            else 'html',
            'text': '',
        }

        if self.notify_format == NotifyFormat.HTML:
            payload['text'] = '{title}{body}'.format(
                title='' if not title else '<h1>{}</h1>'.format(
                    NotifyMatrix.escape_html(title)),
                body=body)

        elif self.notify_format == NotifyFormat.MARKDOWN:
            payload['text'] = '{title}{body}'.format(
                title='' if not title else '<h1>{}</h1>'.format(
                    NotifyMatrix.escape_html(title)),
                body=markdown(body))

        else:  # NotifyFormat.TEXT
            payload['text'] = \
                body if not title else '{}\r\n{}'.format(title, body)

        return payload

    def _t2bot_webhook_payload(self, body, title='',
                               notify_type=NotifyType.INFO, **kwargs):
        """
        Format the payload for a T2Bot Matrix based messages

        """

        # Retrieve our payload
        payload = self._matrix_webhook_payload(
            body=body, title=title, notify_type=notify_type, **kwargs)

        # Acquire our image url if we're configured to do so
        image_url = None if not self.include_image else \
            self.image_url(notify_type)

        if image_url:
            # t2bot can take an avatarUrl Entry
            payload['avatarUrl'] = image_url

        return payload

    def _send_server_notification(self, body, title='',
                                  notify_type=NotifyType.INFO, attach=None,
                                  **kwargs):
        """
        Perform Direct Matrix Server Notification (no webhook)
        """

        if self.access_token is None and self.password and not self.user:
            self.access_token = self.password
            self.transaction_id = uuid.uuid4()

        if self.access_token is None:
            # We need to register
            if not self._login():
                if not self._register():
                    return False

        if len(self.rooms) == 0:
            # Attempt to retrieve a list of already joined channels
            self.rooms = self._joined_rooms()

            if len(self.rooms) == 0:
                # Nothing to notify
                self.logger.warning(
                    'There were no Matrix rooms specified to notify.')
                return False

        # Create a copy of our rooms to join and message
        rooms = list(self.rooms)

        # Initiaize our error tracking
        has_error = False

        attachments = None
        if attach and self.attachment_support:
            attachments = self._send_attachments(attach)
            if attachments is False:
                # take an early exit
                return False

        while len(rooms) > 0:

            # Get our room
            room = rooms.pop(0)

            # Get our room_id from our response
            room_id = self._room_join(room)
            if not room_id:
                # Notify our user about our failure
                self.logger.warning(
                    'Could not join Matrix room {}.'.format((room)))

                # Mark our failure
                has_error = True
                continue

            # Acquire our image url if we're configured to do so
            image_url = None if not self.include_image else \
                self.image_url(notify_type)

            # Build our path
            if self.version == MatrixVersion.V3:
                path = '/rooms/{}/send/m.room.message/{}'.format(
                    NotifyMatrix.quote(room_id),
                    self.transaction_id,
                )

            else:
                path = '/rooms/{}/send/m.room.message'.format(
                    NotifyMatrix.quote(room_id))

            if self.version == MatrixVersion.V2:
                #
                # Attachments don't work beyond V2 at this time
                #
                if image_url:
                    # Define our payload
                    image_payload = {
                        'msgtype': 'm.image',
                        'url': image_url,
                        'body': '{}'.format(
                            notify_type if not title else title),
                    }

                    # Post our content
                    postokay, response = self._fetch(
                        path, payload=image_payload)
                    if not postokay:
                        # Mark our failure
                        has_error = True
                        continue

                if attachments:
                    for attachment in attachments:
                        attachment['room_id'] = room_id
                        attachment['type'] = 'm.room.message'

                        postokay, response = self._fetch(
                            path, payload=attachment)
                        if not postokay:
                            # Mark our failure
                            has_error = True
                            continue

            # Define our payload
            payload = {
                'msgtype': 'm.{}'.format(self.msgtype),
                'body': '{title}{body}'.format(
                    title='' if not title else '# {}\r\n'.format(title),
                    body=body),
            }

            # Update our payload advance formatting for the services that
            # support them.
            if self.notify_format == NotifyFormat.HTML:
                payload.update({
                    'format': 'org.matrix.custom.html',
                    'formatted_body': '{title}{body}'.format(
                        title='' if not title else '<h1>{}</h1>'.format(title),
                        body=body,
                    )
                })

            elif self.notify_format == NotifyFormat.MARKDOWN:
                payload.update({
                    'format': 'org.matrix.custom.html',
                    'formatted_body': '{title}{body}'.format(
                        title='' if not title else '<h1>{}</h1>'.format(
                            NotifyMatrix.escape_html(title, whitespace=False)),
                        body=markdown(body),
                    )
                })

            # Post our content
            method = 'PUT' if self.version == MatrixVersion.V3 else 'POST'
            postokay, response = self._fetch(
                path, payload=payload, method=method)

            # Increment the transaction ID to avoid future messages being
            # recognized as retransmissions and ignored
            if self.version == MatrixVersion.V3 \
               and self.access_token != self.password:
                self.transaction_id += 1
                self.store.set(
                    'transaction_id', self.transaction_id,
                    expires=self.default_cache_expiry_sec)

            if not postokay:
                # Notify our user
                self.logger.warning(
                    'Could not send notification Matrix room {}.'.format(room))

                # Mark our failure
                has_error = True
                continue

        return not has_error

    def _send_attachments(self, attach):
        """
        Posts all of the provided attachments
        """

        payloads = []
        if self.version != MatrixVersion.V2:
            self.logger.warning(
                'Add ?v=2 to Apprise URL to support Attachments')
            return next((False for a in attach if not a), [])

        for attachment in attach:
            if not attachment:
                # invalid attachment (bad file)
                return False

            if not re.match(r'^image/', attachment.mimetype, re.I):
                # unsuppored at this time
                continue

            postokay, response = \
                self._fetch('/upload', attachment=attachment)
            if not (postokay and isinstance(response, dict)):
                # Failed to perform upload
                return False

            # If we get here, we'll have a response that looks like:
            # {
            #     "content_uri": "mxc://example.com/a-unique-key"
            # }

            # FUTURE if self.version == MatrixVersion.V3:
            # FUTURE     # Prepare our payload
            # FUTURE     payloads.append({
            # FUTURE         "body": attachment.name,
            # FUTURE         "info": {
            # FUTURE             "mimetype": attachment.mimetype,
            # FUTURE             "size": len(attachment),
            # FUTURE         },
            # FUTURE         "msgtype": "m.image",
            # FUTURE         "url": response.get('content_uri'),
            # FUTURE     })

            # FUTURE else:
            # FUTURE     # Prepare our payload
            # FUTURE     payloads.append({
            # FUTURE         "info": {
            # FUTURE             "mimetype": attachment.mimetype,
            # FUTURE         },
            # FUTURE         "msgtype": "m.image",
            # FUTURE         "body": "tta.webp",
            # FUTURE         "url": response.get('content_uri'),
            # FUTURE     })

            # Prepare our payload
            payloads.append({
                "info": {
                    "mimetype": attachment.mimetype,
                },
                "msgtype": "m.image",
                "body": "tta.webp",
                "url": response.get('content_uri'),
            })

        return payloads

    def _register(self):
        """
        Register with the service if possible.
        """

        # Prepare our Registration Payload. This will only work if registration
        # is enabled for the public
        payload = {
            'kind': 'user',
            'auth': {'type': 'm.login.dummy'},
        }

        # parameters
        params = {
            'kind': 'user',
        }

        # If a user is not specified, one will be randomly generated for you.
        # If you do not specify a password, you will be unable to login to the
        # account if you forget the access_token.
        if self.user:
            payload['username'] = self.user

        if self.password:
            payload['password'] = self.password

        # Register
        postokay, response = \
            self._fetch('/register', payload=payload, params=params)
        if not (postokay and isinstance(response, dict)):
            # Failed to register
            return False

        # Pull the response details
        self.access_token = response.get('access_token')
        self.home_server = response.get('home_server')
        self.user_id = response.get('user_id')

        self.store.set(
            'access_token', self.access_token,
            expires=self.default_cache_expiry_sec)
        self.store.set(
            'home_server', self.home_server,
            expires=self.default_cache_expiry_sec)
        self.store.set(
            'user_id', self.user_id,
            expires=self.default_cache_expiry_sec)

        if self.access_token is not None:
            # Store our token into our store
            self.logger.debug(
                'Registered successfully with Matrix server.')
            return True

        return False

    def _login(self):
        """
        Acquires the matrix token required for making future requests. If we
        fail we return False, otherwise we return True
        """

        if self.access_token:
            # Login not required; silently skip-over
            return True

        if (self.user and self.password):
            # Prepare our Authentication Payload
            if self.version == MatrixVersion.V3:
                payload = {
                    'type': 'm.login.password',
                    'identifier': {
                        'type': 'm.id.user',
                        'user': self.user,
                    },
                    'password': self.password,
                }

            else:
                payload = {
                    'type': 'm.login.password',
                    'user': self.user,
                    'password': self.password,
                }

        else:
            # It's not possible to register since we need these 2 values to
            # make the action possible.
            self.logger.warning(
                'Failed to login to Matrix server: '
                'token or user/pass combo is missing.')
            return False

        # Build our URL
        postokay, response = self._fetch('/login', payload=payload)
        if not (postokay and isinstance(response, dict)):
            # Failed to login
            return False

        # Pull the response details
        self.access_token = response.get('access_token')
        self.home_server = response.get('home_server')
        self.user_id = response.get('user_id')

        if not self.access_token:
            return False

        self.logger.debug(
            'Authenticated successfully with Matrix server.')

        # Store our token into our store
        self.store.set(
            'access_token', self.access_token,
            expires=self.default_cache_expiry_sec)
        self.store.set(
            'home_server', self.home_server,
            expires=self.default_cache_expiry_sec)
        self.store.set(
            'user_id', self.user_id,
            expires=self.default_cache_expiry_sec)

        return True

    def _logout(self):
        """
        Relinquishes token from remote server
        """

        if not self.access_token:
            # Login not required; silently skip-over
            return True

        # Prepare our Registration Payload
        payload = {}

        # Expire our token
        postokay, response = self._fetch('/logout', payload=payload)
        if not postokay:
            # If we get here, the token was declared as having already
            # been expired.  The response looks like this:
            # {
            #    u'errcode': u'M_UNKNOWN_TOKEN',
            #    u'error': u'Access Token unknown or expired',
            # }
            #
            # In this case it's okay to safely return True because
            # we're logged out in this case.
            if response.get('errcode') != u'M_UNKNOWN_TOKEN':
                return False

        # else: The response object looks like this if we were successful:
        #  {}

        # Pull the response details
        self.access_token = None
        self.home_server = None
        self.user_id = None

        # clear our tokens
        self.store.clear(
            'access_token', 'home_server', 'user_id', 'transaction_id')

        self.logger.debug(
            'Unauthenticated successfully with Matrix server.')

        return True

    def _room_join(self, room):
        """
        Joins a matrix room if we're not already in it. Otherwise it attempts
        to create it if it doesn't exist and always returns
        the room_id if it was successful, otherwise it returns None

        """

        if not self.access_token:
            # We can't join a room if we're not logged in
            return None

        if not isinstance(room, str):
            # Not a supported string
            return None

        # Prepare our Join Payload
        payload = {}

        # Check if it's a room id...
        result = IS_ROOM_ID.match(room)
        if result:
            # We detected ourselves the home_server
            home_server = result.group('home_server') \
                if result.group('home_server') else self.home_server

            # It was a room ID; simple mapping:
            room_id = "!{}:{}".format(
                result.group('room'),
                home_server,
            )

            # Check our cache for speed:
            try:
                # We're done as we've already joined the channel
                return self.store[room_id]['id']

            except KeyError:
                # No worries, we'll try to acquire the info
                pass

            # Build our URL
            path = '/join/{}'.format(NotifyMatrix.quote(room_id))

            # Make our query
            postokay, _ = self._fetch(path, payload=payload)
            if postokay:
                # Cache our entry for fast access later
                self.store.set(room_id, {
                    'id': room_id,
                    'home_server': home_server,
                })

            return room_id if postokay else None

        # Try to see if it's an alias then...
        result = IS_ROOM_ALIAS.match(room)
        if not result:
            # There is nothing else it could be
            self.logger.warning(
                'Ignoring illegally formed room {} '
                'from Matrix server list.'.format(room))
            return None

        # If we reach here, we're dealing with a channel alias
        home_server = self.home_server \
            if not result.group('home_server') \
            else result.group('home_server')

        # tidy our room (alias) identifier
        room = '#{}:{}'.format(result.group('room'), home_server)

        # Check our cache for speed:
        try:
            # We're done as we've already joined the channel
            return self.store[room]['id']

        except KeyError:
            # No worries, we'll try to acquire the info
            pass

        # If we reach here, we need to join the channel

        # Build our URL
        path = '/join/{}'.format(NotifyMatrix.quote(room))

        # Attempt to join the channel
        postokay, response = self._fetch(path, payload=payload)
        if postokay:
            # Cache our entry for fast access later
            self.store.set(room, {
                'id': response.get('room_id'),
                'home_server': home_server,
            })

            return response.get('room_id')

        # Try to create the channel
        return self._room_create(room)

    def _room_create(self, room):
        """
        Creates a matrix room and return it's room_id if successful
        otherwise None is returned.
        """
        if not self.access_token:
            # We can't create a room if we're not logged in
            return None

        if not isinstance(room, str):
            # Not a supported string
            return None

        # Build our room if we have to:
        result = IS_ROOM_ALIAS.match(room)
        if not result:
            # Illegally formed room
            return None

        # Our home_server
        home_server = result.group('home_server') \
            if result.group('home_server') else self.home_server

        # update our room details
        room = '#{}:{}'.format(result.group('room'), home_server)

        # Prepare our Create Payload
        payload = {
            'room_alias_name': result.group('room'),
            # Set our channel name
            'name': '#{} - {}'.format(result.group('room'), self.app_desc),
            # hide the room by default; let the user open it up if they wish
            # to others.
            'visibility': 'private',
            'preset': 'trusted_private_chat',
        }

        postokay, response = self._fetch('/createRoom', payload=payload)
        if not postokay:
            # Failed to create channel
            # Typical responses:
            #   - {u'errcode': u'M_ROOM_IN_USE',
            #      u'error': u'Room alias already taken'}
            #   - {u'errcode': u'M_UNKNOWN',
            #      u'error': u'Internal server error'}
            if (response and response.get('errcode') == 'M_ROOM_IN_USE'):
                return self._room_id(room)
            return None

        # Cache our entry for fast access later
        self.store.set(response.get('room_alias'), {
            'id': response.get('room_id'),
            'home_server': home_server,
        })

        return response.get('room_id')

    def _joined_rooms(self):
        """
        Returns a list of the current rooms the logged in user
        is a part of.
        """

        if not self.access_token:
            # No list is possible
            return list()

        postokay, response = self._fetch(
            '/joined_rooms', payload=None, method='GET')
        if not postokay:
            # Failed to retrieve listings
            return list()

        # Return our list of rooms
        return response.get('joined_rooms', list())

    def _room_id(self, room):
        """Get room id from its alias.
        Args:
            room (str): The room alias name.

        Returns:
            returns the room id if it can, otherwise it returns None
        """

        if not self.access_token:
            # We can't get a room id if we're not logged in
            return None

        if not isinstance(room, str):
            # Not a supported string
            return None

        # Build our room if we have to:
        result = IS_ROOM_ALIAS.match(room)
        if not result:
            # Illegally formed room
            return None

        # Our home_server
        home_server = result.group('home_server') \
            if result.group('home_server') else self.home_server

        # update our room details
        room = '#{}:{}'.format(result.group('room'), home_server)

        # Make our request
        postokay, response = self._fetch(
            "/directory/room/{}".format(
                NotifyMatrix.quote(room)), payload=None, method='GET')

        if postokay:
            return response.get("room_id")

        return None

    def _fetch(self, path, payload=None, params={}, attachment=None,
               method='POST', url_override=None):
        """
        Wrapper to request.post() to manage it's response better and make
        the send() function cleaner and easier to maintain.

        This function returns True if the _post was successful and False
        if it wasn't.

        this function returns the status code if url_override is used
        """

        # Define our headers
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        if self.access_token is not None:
            headers["Authorization"] = 'Bearer %s' % self.access_token

        # Server Discovery / Well-known URI
        if url_override:
            url = url_override

        else:
            try:
                url = self.base_url

            except MatrixDiscoveryException:
                # Discovery failed; we're done
                return (False, {})

        # Default return status code
        status_code = requests.codes.internal_server_error

        if path == '/upload':
            # FUTURE if self.version == MatrixVersion.V3:
            # FUTURE     url += MATRIX_V3_MEDIA_PATH + path

            # FUTURE else:
            # FUTURE     url += MATRIX_V2_MEDIA_PATH + path
            url += MATRIX_V2_MEDIA_PATH + path

            params.update({'filename': attachment.name})
            with open(attachment.path, 'rb') as fp:
                payload = fp.read()

            # Update our content type
            headers['Content-Type'] = attachment.mimetype

        elif not url_override:
            if self.version == MatrixVersion.V3:
                url += MATRIX_V3_API_PATH + path

            else:
                url += MATRIX_V2_API_PATH + path

        # Our response object
        response = {}

        # fetch function
        fn = requests.post if method == 'POST' else (
            requests.put if method == 'PUT' else requests.get)

        # Define how many attempts we'll make if we get caught in a throttle
        # event
        retries = self.default_retries if self.default_retries > 0 else 1
        while retries > 0:

            # Decrement our throttle retry count
            retries -= 1

            self.logger.debug('Matrix %s URL: %s (cert_verify=%r)' % (
                'POST' if method == 'POST' else (
                    requests.put if method == 'PUT' else 'GET'),
                url, self.verify_certificate,
            ))
            self.logger.debug('Matrix Payload: %s' % str(payload))

            # Initialize our response object
            r = None

            try:
                r = fn(
                    url,
                    data=dumps(payload) if not attachment else payload,
                    params=None if not params else params,
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )

                # Store status code
                status_code = r.status_code

                self.logger.debug(
                    'Matrix Response: code=%d, %s' % (
                        r.status_code, str(r.content)))
                response = loads(r.content)

                if r.status_code == requests.codes.too_many_requests:
                    wait = self.default_wait_ms / 1000
                    try:
                        wait = response['retry_after_ms'] / 1000

                    except KeyError:
                        try:
                            errordata = response['error']
                            wait = errordata['retry_after_ms'] / 1000
                        except KeyError:
                            pass

                    self.logger.warning(
                        'Matrix server requested we throttle back {}ms; '
                        'retries left {}.'.format(wait, retries))
                    self.logger.debug(
                        'Response Details:\r\n{}'.format(r.content))

                    # Throttle for specified wait
                    self.throttle(wait=wait)

                    # Try again
                    continue

                elif r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = \
                        NotifyMatrix.http_response_code_lookup(
                            r.status_code, MATRIX_HTTP_ERROR_MAP)

                    self.logger.warning(
                        'Failed to handshake with Matrix server: '
                        '{}{}error={}.'.format(
                            status_str,
                            ', ' if status_str else '',
                            r.status_code))

                    self.logger.debug(
                        'Response Details:\r\n{}'.format(r.content))

                    # Return; we're done
                    return (
                        False if not url_override else status_code, response)

            except (AttributeError, TypeError, ValueError):
                # This gets thrown if we can't parse our JSON Response
                #  - ValueError = r.content is Unparsable
                #  - TypeError = r.content is None
                #  - AttributeError = r is None
                self.logger.warning('Invalid response from Matrix server.')
                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))
                return (False if not url_override else status_code, {})

            except (requests.TooManyRedirects, requests.RequestException) as e:
                self.logger.warning(
                    'A Connection error occurred while registering with Matrix'
                    ' server.')
                self.logger.debug('Socket Exception: %s', str(e))
                # Return; we're done
                return (False if not url_override else status_code, response)

            except (OSError, IOError) as e:
                self.logger.warning(
                    'An I/O error occurred while reading {}.'.format(
                        attachment.name if attachment else 'unknown file'))
                self.logger.debug('I/O Exception: %s', str(e))
                return (False if not url_override else status_code, {})

            return (True if not url_override else status_code, response)

        # If we get here, we ran out of retries
        return (False if not url_override else status_code, {})

    def __del__(self):
        """
        Ensure we relinquish our token
        """
        if self.mode == MatrixWebhookMode.T2BOT:
            # nothing to do
            return

        if self.store.mode != PersistentStoreMode.MEMORY:
            # We no longer have to log out as we have persistant storage to
            # re-use our credentials with
            return

        if self.access_token is not None \
           and self.access_token == self.password and not self.user:
            return

        try:
            self._logout()

        except LookupError:  # pragma: no cover
            # Python v3.5 call to requests can sometimes throw the exception
            #   "/usr/lib64/python3.7/socket.py", line 748, in getaddrinfo
            #   LookupError: unknown encoding: idna
            #
            # This occurs every time when running unit-tests against Apprise:
            # LANG=C.UTF-8 PYTHONPATH=$(pwd) py.test-3.7
            #
            # There has been an open issue on this since Jan 2017.
            #   - https://bugs.python.org/issue29288
            #
            # A ~similar~ issue can be identified here in the requests
            # ticket system as unresolved and has provided workarounds
            #   - https://github.com/kennethreitz/requests/issues/3578
            pass

        except ImportError:  # pragma: no cover
            # The actual exception is `ModuleNotFoundError` however ImportError
            # grants us backwards compatibility with versions of Python older
            # than v3.6

            # Python code that makes early calls to sys.exit() can cause
            # the __del__() code to run. However, in some newer versions of
            # Python, this causes the `sys` library to no longer be
            # available. The stack overflow also goes on to suggest that
            # it's not wise to use the __del__() as a destructor
            # which is the case here.

            # https://stackoverflow.com/questions/67218341/\
            #       modulenotfounderror-import-of-time-halted-none-in-sys-\
            #           modules-occured-when-obj?noredirect=1&lq=1
            #
            #
            # Also see: https://stackoverflow.com/questions\
            #       /1481488/what-is-the-del-method-and-how-do-i-call-it

            # At this time it seems clean to try to log out (if we can)
            # but not throw any unnecessary exceptions (like this one) to
            # the end user if we don't have to.
            pass

    @property
    def url_identifier(self):
        """
        Returns all of the identifiers that make this URL unique from
        another simliar one. Targets or end points should never be identified
        here.
        """
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.host if self.mode != MatrixWebhookMode.T2BOT
            else self.access_token,
            self.port if self.port else (443 if self.secure else 80),
            self.user if self.mode != MatrixWebhookMode.T2BOT else None,
            self.password if self.mode != MatrixWebhookMode.T2BOT else None,
        )

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'image': 'yes' if self.include_image else 'no',
            'mode': self.mode,
            'version': self.version,
            'msgtype': self.msgtype,
            'discovery': 'yes' if self.discovery else 'no',
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        auth = ''
        if self.mode != MatrixWebhookMode.T2BOT:
            # Determine Authentication
            if self.user and self.password:
                auth = '{user}:{password}@'.format(
                    user=NotifyMatrix.quote(self.user, safe=''),
                    password=self.pprint(
                        self.password, privacy, mode=PrivacyMode.Secret,
                        safe=''),
                )

            elif self.user or self.password:
                auth = '{value}@'.format(
                    value=NotifyMatrix.quote(
                        self.user if self.user else self.password, safe=''),
                )

        default_port = 443 if self.secure else 80

        return '{schema}://{auth}{hostname}{port}/{rooms}?{params}'.format(
            schema=self.secure_protocol if self.secure else self.protocol,
            auth=auth,
            hostname=NotifyMatrix.quote(self.host, safe='')
            if self.mode != MatrixWebhookMode.T2BOT
            else self.pprint(self.access_token, privacy, safe=''),
            port='' if self.port is None
            or self.port == default_port else ':{}'.format(self.port),
            rooms=NotifyMatrix.quote('/'.join(self.rooms)),
            params=NotifyMatrix.urlencode(params),
        )

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """
        targets = len(self.rooms)
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

        if not results.get('host'):
            return None

        # Get our rooms
        results['targets'] = NotifyMatrix.split_path(results['fullpath'])

        # Support the 'to' variable so that we can support rooms this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += NotifyMatrix.parse_list(results['qsd']['to'])

        # Boolean to include an image or not
        results['include_image'] = parse_bool(results['qsd'].get(
            'image', NotifyMatrix.template_args['image']['default']))

        # Boolean to perform a server discovery
        results['discovery'] = parse_bool(results['qsd'].get(
            'discovery', NotifyMatrix.template_args['discovery']['default']))

        # Get our mode
        results['mode'] = results['qsd'].get('mode')

        # t2bot detection... look for just a hostname, and/or just a user/host
        # if we match this; we can go ahead and set the mode (but only if
        # it was otherwise not set)
        if results['mode'] is None \
                and not results['password'] \
                and not results['targets']:

            # Default mode to t2bot
            results['mode'] = MatrixWebhookMode.T2BOT

        if results['mode'] and \
                results['mode'].lower() == MatrixWebhookMode.T2BOT:
            # unquote our hostname and pass it in as the password/token
            results['password'] = NotifyMatrix.unquote(results['host'])

        # Support the message type keyword
        if 'msgtype' in results['qsd'] and len(results['qsd']['msgtype']):
            results['msgtype'] = \
                NotifyMatrix.unquote(results['qsd']['msgtype'])

        # Support the use of the token= keyword
        if 'token' in results['qsd'] and len(results['qsd']['token']):
            results['password'] = NotifyMatrix.unquote(results['qsd']['token'])

        elif not results['password'] and results['user']:
            # swap
            results['password'] = results['user']
            results['user'] = None

        # Support the use of the version= or v= keyword
        if 'version' in results['qsd'] and len(results['qsd']['version']):
            results['version'] = \
                NotifyMatrix.unquote(results['qsd']['version'])

        elif 'v' in results['qsd'] and len(results['qsd']['v']):
            results['version'] = NotifyMatrix.unquote(results['qsd']['v'])

        return results

    @staticmethod
    def parse_native_url(url):
        """
        Support https://webhooks.t2bot.io/api/v1/matrix/hook/WEBHOOK_TOKEN/
        """

        result = re.match(
            r'^https?://webhooks\.t2bot\.io/api/v[0-9]+/matrix/hook/'
            r'(?P<webhook_token>[A-Z0-9_-]+)/?'
            r'(?P<params>\?.+)?$', url, re.I)

        if result:
            mode = 'mode={}'.format(MatrixWebhookMode.T2BOT)

            return NotifyMatrix.parse_url(
                '{schema}://{webhook_token}/{params}'.format(
                    schema=NotifyMatrix.secure_protocol,
                    webhook_token=result.group('webhook_token'),
                    params='?{}'.format(mode) if not result.group('params')
                    else '{}&{}'.format(result.group('params'), mode)))

        return None

    def server_discovery(self):
        """
        Home Server Discovery as documented here:
           https://spec.matrix.org/v1.11/client-server-api/#well-known-uri
        """

        if not (self.discovery and self.secure):
            # Nothing further to do with insecure server setups
            return ''

        # Get our content from cache
        base_url, identity_url = (
            self.store.get(self.discovery_base_key),
            self.store.get(self.discovery_identity_key),
        )

        if not (base_url is None and identity_url is None):
            # We can use our cached value and return early
            return base_url

        # 1. Extract the server name from the user’s Matrix ID by splitting
        # the Matrix ID at the first colon.
        verify_url = f'https://{self.host}/.well-known/matrix/client'
        code, wk_response = self._fetch(
            None, method='GET', url_override=verify_url)

        # Output may look as follows:
        # {
        #     "m.homeserver": {
        #         "base_url": "https://matrix.example.com"
        #     },
        #     "m.identity_server": {
        #         "base_url": "https://nuxref.com"
        #     }
        # }

        if code == requests.codes.not_found:
            # This is an acceptable response; we're done
            self.logger.debug(
                'Matrix Well-Known Base URI not found at %s', verify_url)

            # Set our keys out for fast recall later on
            self.store.set(
                self.discovery_base_key, '',
                expires=self.discovery_cache_length_sec)
            self.store.set(
                self.discovery_identity_key, '',
                expires=self.discovery_cache_length_sec)
            return ''

        elif code != requests.codes.ok:
            # We're done early as we couldn't load the results
            msg = 'Matrix Well-Known Base URI Discovery Failed'
            self.logger.warning(
                '%s - %s returned error code: %d', msg, verify_url, code)
            raise MatrixDiscoveryException(msg, error_code=code)

        if not wk_response:
            # This is an acceptable response; we simply do nothing
            self.logger.debug(
                'Matrix Well-Known Base URI not defined %s', verify_url)

            # Set our keys out for fast recall later on
            self.store.set(
                self.discovery_base_key, '',
                expires=self.discovery_cache_length_sec)
            self.store.set(
                self.discovery_identity_key, '',
                expires=self.discovery_cache_length_sec)
            return ''

        #
        # Parse our m.homeserver information
        #
        try:
            base_url = wk_response['m.homeserver']['base_url'].rstrip('/')
            results = NotifyBase.parse_url(base_url, verify_host=True)

        except (AttributeError, TypeError, KeyError):
            # AttributeError: result wasn't a string (rstrip failed)
            # TypeError     : wk_response wasn't a dictionary
            # KeyError      : wk_response not to standards
            results = None

        if not results:
            msg = 'Matrix Well-Known Base URI Discovery Failed'
            self.logger.warning(
                '%s - m.homeserver payload is missing or invalid: %s',
                msg, str(wk_response))
            raise MatrixDiscoveryException(msg)

        #
        # Our .well-known extraction was successful; now we need to verify
        # that the version information resolves.
        #
        verify_url = f'{base_url}/_matrix/client/versions'
        # Post our content
        code, response = self._fetch(
            None, method='GET', url_override=verify_url)
        if code != requests.codes.ok:
            # We're done early as we couldn't load the results
            msg = 'Matrix Well-Known Base URI Discovery Verification Failed'
            self.logger.warning(
                '%s - %s returned error code: %d', msg, verify_url, code)
            raise MatrixDiscoveryException(msg, error_code=code)

        #
        # Phase 2: Handle m.identity_server IF defined
        #
        if 'm.identity_server' in wk_response:
            try:
                identity_url = \
                    wk_response['m.identity_server']['base_url'].rstrip('/')
                results = NotifyBase.parse_url(identity_url, verify_host=True)

            except (AttributeError, TypeError, KeyError):
                # AttributeError: result wasn't a string (rstrip failed)
                # TypeError     : wk_response wasn't a dictionary
                # KeyError      : wk_response not to standards
                results = None

            if not results:
                msg = 'Matrix Well-Known Identity URI Discovery Failed'
                self.logger.warning(
                    '%s - m.identity_server payload is missing or invalid: %s',
                    msg, str(wk_response))
                raise MatrixDiscoveryException(msg)

            #
            #  Verify identity server found
            #
            verify_url = f'{identity_url}/_matrix/identity/v2'

            # Post our content
            code, response = self._fetch(
                None, method='GET', url_override=verify_url)
            if code != requests.codes.ok:
                # We're done early as we couldn't load the results
                msg = 'Matrix Well-Known Identity URI Discovery Failed'
                self.logger.warning(
                    '%s - %s returned error code: %d', msg, verify_url, code)
                raise MatrixDiscoveryException(msg, error_code=code)

            # Update our cache
            self.store.set(
                self.discovery_identity_key, identity_url,
                # Add 2 seconds to prevent this key from expiring before base
                expires=self.discovery_cache_length_sec + 2)
        else:
            # No identity server
            self.store.set(
                self.discovery_identity_key, '',
                # Add 2 seconds to prevent this key from expiring before base
                expires=self.discovery_cache_length_sec + 2)

        # Update our cache
        self.store.set(
            self.discovery_base_key, base_url,
            expires=self.discovery_cache_length_sec)

        return base_url

    @property
    def base_url(self):
        """
        Returns the base_url if known
        """
        try:
            base_url = self.server_discovery()
            if base_url:
                # We can use our cached value and return early
                return base_url

        except MatrixDiscoveryException:
            self.store.clear(
                self.discovery_base_key, self.discovery_identity_key)
            raise

        # If we get hear, we need to build our URL dynamically based on what
        # was provided to us during the plugins initialization
        default_port = 443 if self.secure else 80

        return '{schema}://{hostname}{port}'.format(
            schema='https' if self.secure else 'http',
            hostname=self.host,
            port='' if self.port is None
            or self.port == default_port else f':{self.port}')

    @property
    def identity_url(self):
        """
        Returns the identity_url if known
        """
        base_url = self.base_url
        identity_url = self.store.get(self.discovery_identity_key)
        return base_url if not identity_url else identity_url
