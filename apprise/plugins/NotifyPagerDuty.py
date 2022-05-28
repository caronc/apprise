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

# API Refererence:
#   - https://developer.pagerduty.com/api-reference/\
#       368ae3d938c9e-send-an-event-to-pager-duty
#

import requests
from json import dumps

from .NotifyBase import NotifyBase
from ..URLBase import PrivacyMode
from ..common import NotifyType
from ..common import NotifyImageSize
from ..utils import validate_regex
from ..utils import parse_bool
from ..AppriseLocale import gettext_lazy as _


class PagerDutySeverity(object):
    """
    Defines the Pager Duty Severity Levels
    """
    INFO = 'info'

    WARNING = 'warning'

    ERROR = 'error'

    CRITICAL = 'critical'


# Map all support Apprise Categories with the Pager Duty ones
PAGERDUTY_SEVERITY_MAP = {
    NotifyType.INFO: PagerDutySeverity.INFO,
    NotifyType.SUCCESS: PagerDutySeverity.INFO,
    NotifyType.WARNING: PagerDutySeverity.WARNING,
    NotifyType.FAILURE: PagerDutySeverity.CRITICAL,
}


class NotifyPagerDuty(NotifyBase):
    """
    A wrapper for Pager Duty Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Pager Duty'

    # The services URL
    service_url = 'https://pagerduty.com/'

    # Secure Protocol
    secure_protocol = 'pagerduty'

    # The URL refererenced for remote Notifications
    notify_url = 'https://events.pagerduty.com/v2/enqueue'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_pagerduty'

    # We don't support titles for Pager Duty notifications
    title_maxlen = 0

    # Allows the user to specify the NotifyImageSize object; this is supported
    # through the webhook
    image_size = NotifyImageSize.XY_128

    # Our event action type
    event_action = 'trigger'

    # Define object templates
    templates = (
        '{schema}://{integration_key}@{apikey}',
        '{schema}://{integration_key}@{apikey}/{source}',
        '{schema}://{integration_key}@{apikey}/{source}/{component}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'apikey': {
            'name': _('API Key'),
            'type': 'string',
            'private': True,
            'regex': (r'^[a-z0-9_-]+$', 'i'),
            'required': True
        },
        # Optional but triggers V2 API
        'integrationkey': {
            'name': _('Routing Key'),
            'type': 'string',
            'private': True,
            'regex': (r'^[a-z0-9_-]+$', 'i'),
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'source': {
            # Optional Source Identifier (preferably a FQDN)
            'name': _('Source'),
            'type': 'string',
            'regex': (r'^[a-z0-9._-]+$', 'i'),
            'default': 'Apprise',
        },
        'component': {
            # Optional Component Identifier
            'name': _('Component'),
            'type': 'string',
            'regex': (r'^[a-z0-9._-]+$', 'i'),
            'default': 'Notification',
        },
        'group': {
            'name': _('Group'),
            'type': 'string',
        },
        'class': {
            'name': _('Class'),
            'type': 'string',
            'map_to': 'class_id',
        },
        'image': {
            'name': _('Include Image'),
            'type': 'bool',
            'default': True,
            'map_to': 'include_image',
        },
    })

    # Define any kwargs we're using
    template_kwargs = {
        'details': {
            'name': _('Custom Details'),
            'prefix': '+',
        },
    }

    def __init__(self, apikey, integrationkey=None, source=None,
                 component=None, group=None, class_id=None,
                 include_image=True, details=None, **kwargs):
        """
        Initialize Pager Duty Object
        """
        super(NotifyPagerDuty, self).__init__(**kwargs)

        self.fullpath = kwargs.get('fullpath', '')

        # Long-Lived Access token (generated from User Profile)
        self.apikey = validate_regex(
            apikey, *self.template_tokens['apikey']['regex'])
        if not self.apikey:
            msg = 'An invalid Pager Duty API Key ' \
                  '({}) was specified.'.format(apikey)
            self.logger.warning(msg)
            raise TypeError(msg)

        self.integration_key = validate_regex(
            integrationkey, *self.template_tokens['integrationkey']['regex'])
        if not self.integration_key:
            msg = 'An invalid Pager Duty Routing Key ' \
                  '({}) was specified.'.format(integrationkey)
            self.logger.warning(msg)
            raise TypeError(msg)

        # An Optional Source
        self.source = self.template_args['source']['default']
        if source:
            self.source = validate_regex(
                source, *self.template_args['source']['regex'])
            if not self.source:
                msg = 'An invalid Pager Duty Notification Source ' \
                      '({}) was specified.'.format(source)
                self.logger.warning(msg)
                raise TypeError(msg)
        else:
            self.component = self.template_args['source']['default']

        # An Optional Component
        self.component = self.template_args['component']['default']
        if component:
            self.component = validate_regex(
                component, *self.template_args['component']['regex'])
            if not self.component:
                msg = 'An invalid Pager Duty Notification Source ' \
                      '({}) was specified.'.format(component)
                self.logger.warning(msg)
                raise TypeError(msg)

        else:
            self.component = self.template_args['component']['default']

        # Store Class ID if specified
        self.class_id = class_id if class_id else None

        # Store Group if specified
        self.group = group if group else None

        self.details = {}
        if details:
            # Store our extra details
            self.details.update(details)

        # Display our Apprise Image
        self.include_image = include_image

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Send our PagerDuty Notification
        """

        # Prepare our headers
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
            'Authorization': 'Token token={}'.format(self.apikey),
        }

        # Prepare our persistent_notification.create payload
        payload = {
            # Define our integration key
            'integration_key': self.integration_key,

            # Prepare our payload
            'payload': {
                'summary': body,

                # Set our severity
                'severity': PAGERDUTY_SEVERITY_MAP[notify_type],

                # Our Event Action
                'event_action': self.event_action,

                # Our Alerting Source/Component
                'source': self.source,
                'component': self.component,
            }
        }

        if self.group:
            payload['payload']['group'] = self.group

        if self.class_id:
            payload['payload']['class'] = self.class_id

        # Acquire our image url if configured to do so
        image_url = None if not self.include_image else \
            self.image_url(notify_type)

        if image_url:
            payload['images'] = {
                'src': image_url,
                'alt': notify_type,
            }

        if self.details:
            payload['payload']['custom_details'] = {}
            # Apply any provided custom details
            for k, v in self.details.items():
                payload['payload']['custom_details'][k] = v

        self.logger.debug('Pager Duty POST URL: %s (cert_verify=%r)' % (
            self.notify_url, self.verify_certificate,
        ))
        self.logger.debug('Pager Duty Payload: %s' % str(payload))

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
            if r.status_code not in (
                    requests.codes.ok, requests.codes.created,
                    requests.codes.accepted):
                # We had a problem
                status_str = \
                    NotifyPagerDuty.http_response_code_lookup(
                        r.status_code)

                self.logger.warning(
                    'Failed to send Pager Duty notification: '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return False

            else:
                self.logger.info('Sent Pager Duty notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred sending Pager Duty '
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
        if self.class_id:
            params['class'] = self.class_id

        if self.group:
            params['group'] = self.group

        # Append our custom entries our parameters
        params.update({'+{}'.format(k): v for k, v in self.details.items()})

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        url = '{schema}://{integration_key}@{apikey}/' \
              '{source}/{component}?{params}'

        return url.format(
            schema=self.secure_protocol,
            # never encode hostname since we're expecting it to be a valid one
            integration_key=self.pprint(
                self.integration_key, privacy, mode=PrivacyMode.Secret,
                safe=''),
            apikey=self.pprint(
                self.apikey, privacy, mode=PrivacyMode.Secret, safe=''),
            source=self.pprint(
                self.source, privacy, safe=''),
            component=self.pprint(
                self.component, privacy, safe=''),
            params=NotifyPagerDuty.urlencode(params),
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

        # The 'apikey' makes it easier to use yaml configuration
        if 'apikey' in results['qsd'] and len(results['qsd']['apikey']):
            results['apikey'] = \
                NotifyPagerDuty.unquote(results['qsd']['apikey'])
        else:
            results['apikey'] = NotifyPagerDuty.unquote(results['host'])

        # The 'integrationkey' makes it easier to use yaml configuration
        if 'integrationkey' in results['qsd'] and \
                len(results['qsd']['integrationkey']):
            results['integrationkey'] = \
                NotifyPagerDuty.unquote(results['qsd']['integrationkey'])
        else:
            results['integrationkey'] = \
                NotifyPagerDuty.unquote(results['user'])

        if 'group' in results['qsd'] and len(results['qsd']['group']):
            results['group'] = \
                NotifyPagerDuty.unquote(results['qsd']['group'])

        if 'class' in results['qsd'] and len(results['qsd']['class']):
            results['class_id'] = \
                NotifyPagerDuty.unquote(results['qsd']['class'])

        # Acquire our full path
        fullpath = NotifyPagerDuty.split_path(results['fullpath'])

        # Get our source
        if 'source' in results['qsd'] and len(results['qsd']['source']):
            results['source'] = \
                NotifyPagerDuty.unquote(results['qsd']['source'])
        else:
            results['source'] = fullpath.pop(0) if fullpath else None

        # Get our component
        if 'component' in results['qsd'] and len(results['qsd']['component']):
            results['component'] = \
                NotifyPagerDuty.unquote(results['qsd']['component'])
        else:
            results['component'] = fullpath.pop(0) if fullpath else None

        # Add our custom details key/value pairs that the user can potentially
        # over-ride if they wish to to our returned result set and tidy
        # entries by unquoting them
        results['details'] = {
            NotifyPagerDuty.unquote(x): NotifyPagerDuty.unquote(y)
            for x, y in results['qsd+'].items()}

        # Include images with our message
        results['include_image'] = \
            parse_bool(results['qsd'].get('image', True))

        return results
