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

import re
import requests
from json import dumps, loads
import base64
from itertools import chain

from .NotifyBase import NotifyBase
from ..common import NotifyType
from ..utils import is_phone_no
from ..utils import parse_phone_no
from ..utils import parse_bool
from ..URLBase import PrivacyMode
from ..AppriseLocale import gettext_lazy as _


GROUP_REGEX = re.compile(
    r'^\s*((\@|\%40)?(group\.)|\@|\%40)(?P<group>[a-z0-9_-]+)', re.I)


class NotifySMSEagle(NotifyBase):
    """
    A wrapper for SMSEagle Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'SMS Eagle'

    # The services URL
    service_url = 'https://smseagle.eu'

    # The default protocol
    protocol = 'smseagle'

    # The default protocol
    secure_protocol = 'smseagles'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_smseagle'

    # The path we send our notification to
    notify_path = '/jsonrpc/sms'

    # The maximum targets to include when doing batch transfers
    default_batch_size = 10

    # We don't support titles for SMSEagle notifications
    title_maxlen = 0

    # Define object templates
    templates = (
        '{schema}://{token}@{host}/{targets}',
        '{schema}://{token}@{host}:{port}/{targets}',
        '{schema}://{user}:{password}@{host}/{targets}',
        '{schema}://{user}:{password}@{host}:{port}/{targets}',
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
        'token': {
            'name': _('Access Token'),
            'type': 'string',
        },
        'password': {
            'name': _('Password'),
            'type': 'string',
            'private': True,
        },
        'target_phone': {
            'name': _('Target Phone No'),
            'type': 'string',
            'prefix': '+',
            'regex': (r'^[0-9\s)(+-]+$', 'i'),
            'map_to': 'targets',
        },
        'target_group': {
            'name': _('Target Group ID'),
            'type': 'string',
            'prefix': '@',
            'regex': (r'^[a-z0-9_-]+$', 'i'),
            'map_to': 'targets',
        },
        'targets': {
            'name': _('Targets'),
            'type': 'list:string',
        }
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'to': {
            'alias_of': 'targets',
        },
        'token': {
            'alias_of': 'token',
        },
        'batch': {
            'name': _('Batch Mode'),
            'type': 'bool',
            'default': False,
        },
        'status': {
            'name': _('Show Status'),
            'type': 'bool',
            'default': False,
        },
    })

    def __init__(self, token=None, targets=None, batch=False, status=False,
                 **kwargs):
        """
        Initialize SMSEagle Object
        """
        super(NotifySMSEagle, self).__init__(**kwargs)

        # Prepare Batch Mode Flag
        self.batch = batch

        # Set Status type
        self.status = status

        # Parse our targets
        self.target_phones = list()
        self.target_groups = list()

        # Used for URL generation afterwards only
        self.invalid_targets = list()

        # We always use a token if provided, otherwise we use the user/pass
        self.auth = {}
        if not self.password:
            # token value trumps the user; but they are in turn the same thing
            self.user = self.user if not token else token
            if self.user:
                # Update our user object
                self.auth = {
                    'access_token': self.user
                }

        elif self.user and self.password:
            self.auth = {
                'login': self.user,
                'pass': self.password,
            }

        # Validate our targerts
        for target in parse_phone_no(targets):
            # Validate targets and drop bad ones:
            result = is_phone_no(target)
            if result:
                # store valid phone number
                self.target_phones.append('+{}'.format(result['full']))
                continue

            result = GROUP_REGEX.match(target)
            if result:
                # Just store group information
                self.target_groups.append(result.group('group'))
                continue

            self.logger.warning(
                'Dropped invalid phone/group '
                '({}) specified.'.format(target),
            )
            self.invalid_targets.append(target)
            continue

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, attach=None,
             **kwargs):
        """
        Perform SMSEagle Notification
        """

        if not self.auth:
            # No authentication was provided
            self.logger.warning(
                'There was no authentication provided for the SMSEagle API.')
            return False

        if not self.target_groups and not self.target_phones:
            # There were no services to notify
            self.logger.warning(
                'There were no SMSEagle targets to notify.')
            return False

        # error tracking (used for function return)
        has_error = False

        attachments = []
        if attach:
            for attachment in attach:
                # Perform some simple error checking
                if not attachment:
                    # We could not access the attachment
                    self.logger.error(
                        'Could not access attachment {}.'.format(
                            attachment.url(privacy=True)))
                    return False

                if not re.match(r'^image/.*', attachment.mimetype, re.I):
                    # Only support images at this time
                    self.logger.warning(
                        'Ignoring unsupported SMSEagle attachment {}.'.format(
                            attachment.url(privacy=True)))
                    continue

                try:
                    with open(attachment.path, 'rb') as f:
                        # Prepare our Attachment in Base64
                        attachments.append({
                            'content_type': attachment.mimetype,
                            'content': base64.b64encode(
                                f.read()).decode('utf-8'),
                        })

                except (OSError, IOError) as e:
                    self.logger.warning(
                        'An I/O error occurred while reading {}.'.format(
                            attachment.name if attachment else 'attachment'))
                    self.logger.debug('I/O Exception: %s' % str(e))
                    return False

        # Prepare our headers
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
        }

        # Prepare our payload
        payload_template = {
            # The message to send
            "message": None,

            # 0 = normal priority, 1 = high priority
            "highpriority": 0,

            # Support unicode characters
            "unicode": 1,

            # sms or mms (if attachment)
            "messge_type": 'sms',

            # Response Types:
            #  simple: format response as simple object with one result field
            #  extended: format response as extended JSON object
            "responsetype": 'extended',

            # Message Simulation
            "test": 0,
        }

        # Apply our authentication
        payload_template.update(self.auth)

        # Set our schema
        schema = 'https' if self.secure else 'http'

        # Construct our URL
        notify_url = '%s://%s' % (schema, self.host)
        if isinstance(self.port, int):
            notify_url += ':%d' % self.port
        notify_url += self.notify_path

        # Send in batches if identified to do so
        batch_size = 1 if not self.batch else self.default_batch_size

        notify_by = {
            'phone': {
                'payload': {
                    "method": "sms.send_sms",
                    "to": None,
                },
                'target': 'to',
            },
            'group': {
                'payload': {
                    "method": "sms.send_togroup",
                    "groupname": None,
                },
                'target': 'to',
            },
        }
        for category in ('phone', 'group'):

            # Create a copy of our template
            payload = payload_template.copy()

            # Update our payload
            payload.update({
                # Our message to transmit
                'message': "{}{}".format(
                    '' if not self.status else '{} '.format(
                        self.asset.ascii(notify_type)), body),

                # Our special options
                **notify_by[category]['payload'],
            })

            if attachments:
                # Store our attachments
                payload['messge_type'] = 'mms'
                payload['attachments'] = attachments

            targets = getattr(self, 'target_{}s'.format(category))
            for index in range(0, len(targets), batch_size):
                # Prepare our recipients
                payload.update({
                    notify_by[category]['target']:
                    ','.join(targets[index:index + batch_size])})

                self.logger.debug('SMSEagle POST URL: %s (cert_verify=%r)' % (
                    notify_url, self.verify_certificate,
                ))
                self.logger.debug('SMSEagle Payload: %s' % str(payload))

                # Always call throttle before any remote server i/o is made
                self.throttle()
                try:
                    r = requests.post(
                        notify_url,
                        data=dumps(payload),
                        headers=headers,
                        verify=self.verify_certificate,
                        timeout=self.request_timeout,
                    )

                    try:
                        content = loads(r.content)

                        # Store our status
                        status_str = content['result']

                    except (AttributeError, TypeError, ValueError):
                        # ValueError = r.content is Unparsable
                        # TypeError = r.content is None
                        # AttributeError = r is None
                        content = {}

                    if content.get('status') != 'ok' or r.status_code not in (
                            requests.codes.ok, requests.codes.created):
                        # We had a problem
                        status_str = content.get('result') \
                            if content.get('result') else \
                                NotifySMSEagle.http_response_code_lookup(
                                    r.status_code)

                        self.logger.warning(
                            'Failed to send {} {} SMSEagle {} notification: '
                            '{}{}error={}.'.format(
                                len(targets[index:index + batch_size]),
                                'to {}'.format(targets[index])
                                if batch_size == 1 else '(s)',
                                category,
                                status_str,
                                ', ' if status_str else '',
                                r.status_code))

                        self.logger.debug(
                            'Response {} Details:\r\n{}'.format(
                                category.upper(), r.content))

                        # Mark our failure
                        has_error = True
                        continue

                    else:
                        self.logger.info(
                            'Sent {} SMSEagle {} notification{}.'
                            .format(
                                len(targets[index:index + batch_size]),
                                category,
                                ' to {}'.format(targets[index])
                                if batch_size == 1 else '(s)',
                            ))

                except requests.RequestException as e:
                    self.logger.warning(
                        'A Connection error occured sending {} SMSEagle '
                        '{} notification(s).'.format(
                            len(targets[index:index + batch_size]), category))
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
            'batch': 'yes' if self.batch else 'no',
            'status': 'yes' if self.status else 'no',
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Determine Authentication
        auth = ''
        if self.user and self.password:
            auth = '{user}:{password}@'.format(
                user=NotifySMSEagle.quote(self.user, safe=''),
                password=self.pprint(
                    self.password, privacy, mode=PrivacyMode.Secret, safe=''),
            )
        elif self.user:
            auth = '{token}@'.format(
                token=NotifySMSEagle.quote(self.user, safe=''),
            )

        default_port = 443 if self.secure else 80

        return '{schema}://{auth}{hostname}{port}/{targets}?{params}'.format(
            schema=self.secure_protocol if self.secure else self.protocol,
            auth=auth,
            # never encode hostname since we're expecting it to be a valid one
            hostname=self.host,
            port='' if self.port is None or self.port == default_port
                 else ':{}'.format(self.port),
            targets='/'.join(
                [NotifySMSEagle.quote(x) for x in chain(
                    # Phone # are already prefixed with a plus symbol
                    ['+{}'.format(x) for x in self.target_phones],
                    # Groups
                    ['@{}'.format(x) for x in self.target_groups],
                )]),
            params=NotifySMSEagle.urlencode(params),
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

        # Get our entries; split_path() looks after unquoting content for us
        # by default
        results['targets'] = \
            NotifySMSEagle.split_path(results['fullpath'])

        if 'token' in results['qsd'] and len(results['qsd']['token']):
            results['token'] = NotifySMSEagle.unquote(results['qsd']['token'])

        elif not results['password'] and results['user']:
            results['token'] = NotifySMSEagle.unquote(results['user'])

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifySMSEagle.parse_phone_no(results['qsd']['to'])

        # Get Batch Mode Flag
        results['batch'] = \
            parse_bool(results['qsd'].get('batch', False))

        # Get status switch
        results['status'] = \
            parse_bool(results['qsd'].get('status', False))

        return results
