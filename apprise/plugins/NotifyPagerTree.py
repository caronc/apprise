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

import requests
from json import dumps

from uuid import uuid4

from .NotifyBase import NotifyBase
from ..URLBase import PrivacyMode
from ..common import NotifyType
from ..common import NotifyFormat
from ..utils import parse_list
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _

# Actions
class PagerTreeAction:
    CREATE = 'create'
    ACKNOWLEDGE = 'acknowledge'
    RESOLVE = 'resolve'

PAGERTREE_ACTIONS = {
    PagerTreeAction.CREATE: 'create',
    PagerTreeAction.ACKNOWLEDGE: 'acknowledge',
    PagerTreeAction.RESOLVE: 'resolve',
}

# Urgencies
class PagerTreeUrgency:
    SILENT = "silent"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

PAGERTREE_URGENCIES = {
    # Note: This also acts as a reverse lookup mapping
    PagerTreeUrgency.SILENT: 'silent',
    PagerTreeUrgency.LOW: 'low',
    PagerTreeUrgency.MEDIUM: 'medium',
    PagerTreeUrgency.HIGH: 'high',
    PagerTreeUrgency.CRITICAL: 'critical',
}
# Extend HTTP Error Messages
PAGERTREE_HTTP_ERROR_MAP = {
    402: 'Payment Required - Please subscribe or upgrade',
    403: 'Forbidden - Blocked',
    404: 'Not Found - Invalid Integration ID',
    405: 'Method Not Allowed - Integration Disabled',
    429: 'Too Many Requests - Rate Limit Exceeded',
}


class NotifyPagerTree(NotifyBase):
    """
    A wrapper for PagerTree Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'PagerTree'

    # The services URL
    service_url = 'https://pagertree.com/'

    # All PagerTree requests are secure
    secure_protocol = 'pagertree'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_pagertree'

    # PagerTree uses the http protocol with JSON requests
    notify_url = 'https://api.pagertree.com/integration/{}'

    # Define object templates
    templates = (
        '{schema}://{integration_id}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'integration_id': {
            'name': _('Integration ID'),
            'type': 'string',
            'private': True,
            'required': True,
        }
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'action': {
            'name': _('Action'),
            'type': 'choice:string',
            'values': PAGERTREE_ACTIONS,
            'default': PagerTreeAction.CREATE,
        },
        'thirdparty_id': {
            'name': _('Third Party ID'),
            'type': 'string',
            'default': None,
        },
        'urgency': {
            'name': _('Urgency'),
            'type': 'choice:string',
            'values': PAGERTREE_URGENCIES,
            'default': None,
        },
        'tags': {
            'name': _('Tags'),
            'type': 'string',
        },
    })

    # Define any kwargs we're using
    template_kwargs = {
        'headers': {
            'name': _('HTTP Header'),
            'prefix': '+',
        },
        'payload_extras': {
            'name': _('Payload Extras'),
            'prefix': ':',
        },
        'meta_extras': {
            'name': _('Meta Extras'),
            'prefix': '-',
        },
    }

    def __init__(self, integration_id, action=None, thirdparty_id=None, 
                urgency=None, tags=None, meta=None, headers=None, payload_extras=None, 
                meta_extras=None, **kwargs):
        """
        Initialize PagerTree Object
        """
        super().__init__(**kwargs)

        # Integration ID (associated with account)
        self.integration_id = validate_regex(integration_id)
        if not self.integration_id:
            msg = 'An invalid PagerTree Integration ID ' \
                  '({}) was specified.'.format(integration_id)
            self.logger.warning(msg)
            raise TypeError(msg)

        self.headers = {}
        if headers:
            # Store our extra headers
            self.headers.update(headers)

        self.payload_extras = {}
        if payload_extras:
            # Store our extra payload entries
            self.payload_extras.update(payload_extras)

        self.meta_extras = {}
        if meta_extras:
            # Store our extra payload entries
            self.meta_extras.update(meta_extras)

        # thirdparty_id (optional, in case they want to pass the acknowledge or resolve action)
        self.thirdparty_id = validate_regex(thirdparty_id) if thirdparty_id is not None else str(uuid4())


        # Setup our action
        self.action = NotifyPagerTree.template_args['action']['default'] if action not in PAGERTREE_ACTIONS else PAGERTREE_ACTIONS[action]

        # Setup our urgency
        self.urgency = None if urgency not in PAGERTREE_URGENCIES else PAGERTREE_URGENCIES[urgency]

        # Any optional tags to attach to the notification
        self.__tags = parse_list(tags)

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform PagerTree Notification
        """

        # Prepare our headers
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
        }

        # Apply any/all header over-rides defined
        headers.update(self.headers)

        # prepare JSON Object
        payload = {
            'event_type': self.action,
            'title': title if title else self.app_desc,
            'description': body,
        }

        if self.thirdparty_id is not None:
            payload['id'] = self.thirdparty_id

        if self.urgency is not None:
            payload['urgency'] = self.urgency

        if self.__tags is not None:
            payload['tags'] = self.__tags

        if self.meta_extras is not None:
            payload['meta'] = self.meta_extras

        # Apply any/all payload over-rides defined
        payload.update(self.payload_extras)

        # Prepare our URL based on integration_id
        notify_url = self.notify_url.format(self.integration_id)

        self.logger.debug('PagerTree POST URL: %s (cert_verify=%r)' % (
            notify_url, self.verify_certificate,
        ))
        self.logger.debug('PagerTree Payload: %s' % str(payload))

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
            if r.status_code not in (
                    requests.codes.ok, requests.codes.created,
                    requests.codes.accepted):
                # We had a problem
                status_str = \
                    NotifyPagerTree.http_response_code_lookup(
                        r.status_code)

                self.logger.warning(
                    'Failed to send PagerTree notification: '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return False

            else:
                self.logger.info('Sent PagerTree notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred sending PagerTree '
                'notification to %s.' % self.host)
            self.logger.debug('Socket Exception: %s' % str(e))

            # Return; we're done
            return False

        return True

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        # Append our headers into our parameters
        params.update({'+{}'.format(k): v for k, v in self.headers.items()})

        # Append our meta extras into our parameters
        params.update({'-{}'.format(k): v for k, v in self.meta_extras.items()})

        # Append our payload extras into our parameters
        params.update({':{}'.format(k): v for k, v in self.payload_extras.items()})

        return '{schema}://{integration_id}'.format(
            schema=self.secure_protocol,
            # never encode hostname since we're expecting it to be a valid one
            integration_id=self.pprint(self.integration_id, privacy, safe=''),
            params=NotifyPagerTree.urlencode(params),
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

        # Add our headers that the user can potentially over-ride if they wish
        # to to our returned result set and tidy entries by unquoting them
        results['headers'] = {NotifyPagerTree.unquote(x): NotifyPagerTree.unquote(y)
                              for x, y in results['qsd+'].items()}

        # store any additional payload extra's defined
        results['payload_extras'] = {NotifyPagerTree.unquote(x): NotifyPagerTree.unquote(y)
                              for x, y in results['qsd:'].items()}

        # store any additional meta extra's defined
        results['meta_extras'] = {NotifyPagerTree.unquote(x): NotifyPagerTree.unquote(y)
                              for x, y in results['qsd-'].items()}

        # Integration ID
        if 'integration_id' in results['qsd'] and \
                len(results['qsd']['integration_id']):
            results['integration_id'] = \
                NotifyPagerTree.unquote(results['qsd']['integration_id'])
        else:
            results['integration_id'] = \
                NotifyPagerTree.unquote(results['host'])

        # Set our thirdparty_id
        if 'thirdparty_id' in results['qsd'] and len(results['qsd']['thirdparty_id']):
            results['thirdparty_id'] = \
                NotifyPagerTree.unquote(results['qsd']['thirdparty_id'])

        # Set our urgency
        if 'action' in results['qsd'] and len(results['qsd']['action']):
            results['action'] = \
                NotifyPagerTree.unquote(results['qsd']['action'])

        # Set our urgency
        if 'urgency' in results['qsd'] and len(results['qsd']['urgency']):
            results['urgency'] = \
                NotifyPagerTree.unquote(results['qsd']['urgency'])

        # Set our tags
        if 'tags' in results['qsd'] and len(results['qsd']['tags']):
            results['tags'] = \
                parse_list(NotifyPagerTree.unquote(results['qsd']['tags']))

        return results
