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

from .base import NotifyBase
from ..common import NotifyType
from .. import exception
from ..utils import is_phone_no
from ..utils import parse_phone_no
from ..utils import parse_bool
from ..url import PrivacyMode
from ..locale import gettext_lazy as _


GROUP_REGEX = re.compile(
    r'^\s*((\@|\%40)?(group\.)|\@|\%40)(?P<group>[a-z0-9_=-]+)', re.I)


class NotifySignalAPI(NotifyBase):
    """
    A wrapper for SignalAPI Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Signal API'

    # The services URL
    service_url = 'https://bbernhard.github.io/signal-cli-rest-api/'

    # The default protocol
    protocol = 'signal'

    # The default protocol
    secure_protocol = 'signals'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_signal'

    # Support attachments
    attachment_support = True

    # The maximum targets to include when doing batch transfers
    default_batch_size = 10

    # We don't support titles for Signal notifications
    title_maxlen = 0

    # Define object templates
    templates = (
        '{schema}://{host}/{from_phone}',
        '{schema}://{host}:{port}/{from_phone}',
        '{schema}://{user}@{host}/{from_phone}',
        '{schema}://{user}@{host}:{port}/{from_phone}',
        '{schema}://{user}:{password}@{host}/{from_phone}',
        '{schema}://{user}:{password}@{host}:{port}/{from_phone}',
        '{schema}://{host}/{from_phone}/{targets}',
        '{schema}://{host}:{port}/{from_phone}/{targets}',
        '{schema}://{user}@{host}/{from_phone}/{targets}',
        '{schema}://{user}@{host}:{port}/{from_phone}/{targets}',
        '{schema}://{user}:{password}@{host}/{from_phone}/{targets}',
        '{schema}://{user}:{password}@{host}:{port}/{from_phone}/{targets}',
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
        'from_phone': {
            'name': _('From Phone No'),
            'type': 'string',
            'required': True,
            'regex': (r'^\+?[0-9\s)(+-]+$', 'i'),
            'map_to': 'source',
        },
        'target_phone': {
            'name': _('Target Phone No'),
            'type': 'string',
            'prefix': '+',
            'regex': (r'^[0-9\s)(+-]+$', 'i'),
            'map_to': 'targets',
        },
        'target_channel': {
            'name': _('Target Group ID'),
            'type': 'string',
            'prefix': '@',
            'regex': (r'^[a-z0-9_=-]+$', 'i'),
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
        'from': {
            'alias_of': 'from_phone',
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

    def __init__(self, source=None, targets=None, batch=False, status=False,
                 **kwargs):
        """
        Initialize SignalAPI Object
        """
        super().__init__(**kwargs)

        # Prepare Batch Mode Flag
        self.batch = batch

        # Set Status type
        self.status = status

        # Parse our targets
        self.targets = list()

        # Used for URL generation afterwards only
        self.invalid_targets = list()

        # Manage our Source Phone
        result = is_phone_no(source)
        if not result:
            msg = 'An invalid Signal API Source Phone No ' \
                  '({}) was provided.'.format(source)
            self.logger.warning(msg)
            raise TypeError(msg)

        self.source = '+{}'.format(result['full'])

        if targets:
            # Validate our targerts
            for target in parse_phone_no(targets):
                # Validate targets and drop bad ones:
                result = is_phone_no(target)
                if result:
                    # store valid phone number
                    self.targets.append('+{}'.format(result['full']))
                    continue

                result = GROUP_REGEX.match(target)
                if result:
                    # Just store group information
                    self.targets.append(
                        'group.{}'.format(result.group('group')))
                    continue

                self.logger.warning(
                    'Dropped invalid phone/group '
                    '({}) specified.'.format(target),
                )
                self.invalid_targets.append(target)
                continue

        else:
            # Send a message to ourselves
            self.targets.append(self.source)

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, attach=None,
             **kwargs):
        """
        Perform Signal API Notification
        """

        if len(self.targets) == 0:
            # There were no services to notify
            self.logger.warning(
                'There were no Signal API targets to notify.')
            return False

        # error tracking (used for function return)
        has_error = False

        attachments = []
        if attach and self.attachment_support:
            for attachment in attach:
                # Perform some simple error checking
                if not attachment:
                    # We could not access the attachment
                    self.logger.error(
                        'Could not access Signal API attachment {}.'.format(
                            attachment.url(privacy=True)))
                    return False

                try:
                    attachments.append(attachment.base64())

                except exception.AppriseException:
                    # We could not access the attachment
                    self.logger.error(
                        'Could not access Signal API attachment {}.'.format(
                            attachment.url(privacy=True)))
                    return False

                self.logger.debug(
                    'Appending Signal API attachment {}'.format(
                        attachment.url(privacy=True)))

        # Prepare our headers
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
        }

        # Format defined here:
        #   https://bbernhard.github.io/signal-cli-rest-api\
        #       /#/Messages/post_v2_send
        # Example:
        # {
        #   "base64_attachments": [
        #     "string"
        #   ],
        #   "message": "string",
        #   "number": "string",
        #   "recipients": [
        #     "string"
        #   ]
        # }
        # Prepare our payload
        payload = {
            'message': "{}{}".format(
                '' if not self.status else '{} '.format(
                    self.asset.ascii(notify_type)), body).rstrip(),
            "number": self.source,
            "recipients": []
        }

        if attachments:
            # Store our attachments
            payload['base64_attachments'] = attachments

        # Determine Authentication
        auth = None
        if self.user:
            auth = (self.user, self.password)

        # Set our schema
        schema = 'https' if self.secure else 'http'

        # Construct our URL
        notify_url = '%s://%s' % (schema, self.host)
        if isinstance(self.port, int):
            notify_url += ':%d' % self.port
        notify_url += '/v2/send'

        # Send in batches if identified to do so
        batch_size = 1 if not self.batch else self.default_batch_size

        for index in range(0, len(self.targets), batch_size):
            # Prepare our recipients
            payload['recipients'] = self.targets[index:index + batch_size]

            self.logger.debug('Signal API POST URL: %s (cert_verify=%r)' % (
                notify_url, self.verify_certificate,
            ))
            self.logger.debug('Signal API Payload: %s' % str(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.post(
                    notify_url,
                    auth=auth,
                    data=dumps(payload),
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )
                if r.status_code not in (
                        requests.codes.ok, requests.codes.created):
                    # We had a problem
                    status_str = \
                        NotifySignalAPI.http_response_code_lookup(
                            r.status_code)

                    self.logger.warning(
                        'Failed to send {} Signal API notification{}: '
                        '{}{}error={}.'.format(
                            len(self.targets[index:index + batch_size]),
                            ' to {}'.format(self.targets[index])
                            if batch_size == 1 else '(s)',
                            status_str,
                            ', ' if status_str else '',
                            r.status_code))

                    self.logger.debug(
                        'Response Details:\r\n{}'.format(r.content))

                    # Mark our failure
                    has_error = True
                    continue

                else:
                    self.logger.info(
                        'Sent {} Signal API notification{}.'
                        .format(
                            len(self.targets[index:index + batch_size]),
                            ' to {}'.format(self.targets[index])
                            if batch_size == 1 else '(s)',
                        ))

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occured sending {} Signal API '
                    'notification(s).'.format(
                        len(self.targets[index:index + batch_size])))
                self.logger.debug('Socket Exception: %s' % str(e))

                # Mark our failure
                has_error = True
                continue

        return not has_error

    @property
    def url_identifier(self):
        """
        Returns all of the identifiers that make this URL unique from
        another simliar one. Targets or end points should never be identified
        here.
        """
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.user, self.password, self.host, self.port, self.source,
        )

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
                user=NotifySignalAPI.quote(self.user, safe=''),
                password=self.pprint(
                    self.password, privacy, mode=PrivacyMode.Secret, safe=''),
            )
        elif self.user:
            auth = '{user}@'.format(
                user=NotifySignalAPI.quote(self.user, safe=''),
            )

        default_port = 443 if self.secure else 80

        # So we can strip out our own phone (if present); create a copy of our
        # targets
        if len(self.targets) == 1 and self.source in self.targets:
            targets = []

        elif len(self.targets) == 0:
            # invalid phone-no were specified
            targets = self.invalid_targets

        else:
            # append @ to non-phone number entries as they are groups
            # Remove group. prefix as well
            targets = \
                ['@{}'.format(x[6:]) if x[0] != '+'
                 else x for x in self.targets]

        return '{schema}://{auth}{hostname}{port}/{src}/{dst}?{params}'.format(
            schema=self.secure_protocol if self.secure else self.protocol,
            auth=auth,
            # never encode hostname since we're expecting it to be a valid one
            hostname=self.host,
            port='' if self.port is None or self.port == default_port
                 else ':{}'.format(self.port),
            src=self.source,
            dst='/'.join(
                [NotifySignalAPI.quote(x, safe='@+') for x in targets]),
            params=NotifySignalAPI.urlencode(params),
        )

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

        # Get our entries; split_path() looks after unquoting content for us
        # by default
        results['targets'] = \
            NotifySignalAPI.split_path(results['fullpath'])

        # The hostname is our authentication key
        results['apikey'] = NotifySignalAPI.unquote(results['host'])

        if 'from' in results['qsd'] and len(results['qsd']['from']):
            results['source'] = \
                NotifySignalAPI.unquote(results['qsd']['from'])

        elif results['targets']:
            # The from phone no is the first entry in the list otherwise
            results['source'] = results['targets'].pop(0)

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifySignalAPI.parse_phone_no(results['qsd']['to'])

        # Get Batch Mode Flag
        results['batch'] = \
            parse_bool(results['qsd'].get('batch', False))

        # Get status switch
        results['status'] = \
            parse_bool(results['qsd'].get('status', False))

        return results
