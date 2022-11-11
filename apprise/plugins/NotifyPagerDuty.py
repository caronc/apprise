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


class PagerDutySeverity:
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

PAGERDUTY_SEVERITIES = (
    PagerDutySeverity.INFO,
    PagerDutySeverity.WARNING,
    PagerDutySeverity.CRITICAL,
    PagerDutySeverity.ERROR,
)


# Priorities
class PagerDutyRegion:
    US = 'us'
    EU = 'eu'


# SparkPost APIs
PAGERDUTY_API_LOOKUP = {
    PagerDutyRegion.US: 'https://events.pagerduty.com/v2/enqueue',
    PagerDutyRegion.EU: 'https://events.eu.pagerduty.com/v2/enqueue',
}

# A List of our regions we can use for verification
PAGERDUTY_REGIONS = (
    PagerDutyRegion.US,
    PagerDutyRegion.EU,
)


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

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_pagerduty'

    # We don't support titles for Pager Duty notifications
    title_maxlen = 0

    # Allows the user to specify the NotifyImageSize object; this is supported
    # through the webhook
    image_size = NotifyImageSize.XY_128

    # Our event action type
    event_action = 'trigger'

    # The default region to use if one isn't otherwise specified
    default_region = PagerDutyRegion.US

    # Define object templates
    templates = (
        '{schema}://{integrationkey}@{apikey}',
        '{schema}://{integrationkey}@{apikey}/{source}',
        '{schema}://{integrationkey}@{apikey}/{source}/{component}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'apikey': {
            'name': _('API Key'),
            'type': 'string',
            'private': True,
            'required': True
        },
        # Optional but triggers V2 API
        'integrationkey': {
            'name': _('Routing Key'),
            'type': 'string',
            'private': True,
            'required': True
        },
        'source': {
            # Optional Source Identifier (preferably a FQDN)
            'name': _('Source'),
            'type': 'string',
            'default': 'Apprise',
        },
        'component': {
            # Optional Component Identifier
            'name': _('Component'),
            'type': 'string',
            'default': 'Notification',
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'group': {
            'name': _('Group'),
            'type': 'string',
        },
        'class': {
            'name': _('Class'),
            'type': 'string',
            'map_to': 'class_id',
        },
        'click': {
            'name': _('Click'),
            'type': 'string',
        },
        'region': {
            'name': _('Region Name'),
            'type': 'choice:string',
            'values': PAGERDUTY_REGIONS,
            'default': PagerDutyRegion.US,
            'map_to': 'region_name',
        },
        # The severity is automatically determined, however you can optionally
        # over-ride its value and force it to be what you want
        'severity': {
            'name': _('Severity'),
            'type': 'choice:string',
            'values': PAGERDUTY_SEVERITIES,
            'map_to': 'severity',
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
                 include_image=True, click=None, details=None,
                 region_name=None, severity=None, **kwargs):
        """
        Initialize Pager Duty Object
        """
        super().__init__(**kwargs)

        # Long-Lived Access token (generated from User Profile)
        self.apikey = validate_regex(apikey)
        if not self.apikey:
            msg = 'An invalid Pager Duty API Key ' \
                  '({}) was specified.'.format(apikey)
            self.logger.warning(msg)
            raise TypeError(msg)

        self.integration_key = validate_regex(integrationkey)
        if not self.integration_key:
            msg = 'An invalid Pager Duty Routing Key ' \
                  '({}) was specified.'.format(integrationkey)
            self.logger.warning(msg)
            raise TypeError(msg)

        # An Optional Source
        self.source = self.template_tokens['source']['default']
        if source:
            self.source = validate_regex(source)
            if not self.source:
                msg = 'An invalid Pager Duty Notification Source ' \
                      '({}) was specified.'.format(source)
                self.logger.warning(msg)
                raise TypeError(msg)
        else:
            self.component = self.template_tokens['source']['default']

        # An Optional Component
        self.component = self.template_tokens['component']['default']
        if component:
            self.component = validate_regex(component)
            if not self.component:
                msg = 'An invalid Pager Duty Notification Component ' \
                      '({}) was specified.'.format(component)
                self.logger.warning(msg)
                raise TypeError(msg)
        else:
            self.component = self.template_tokens['component']['default']

        # Store our region
        try:
            self.region_name = self.default_region \
                if region_name is None else region_name.lower()

            if self.region_name not in PAGERDUTY_REGIONS:
                # allow the outer except to handle this common response
                raise
        except:
            # Invalid region specified
            msg = 'The PagerDuty region specified ({}) is invalid.' \
                  .format(region_name)
            self.logger.warning(msg)
            raise TypeError(msg)

        # The severity (if specified)
        self.severity = \
            None if severity is None else next((
                s for s in PAGERDUTY_SEVERITIES
                if str(s).lower().startswith(severity)), False)

        if self.severity is False:
            # Invalid severity specified
            msg = 'The PagerDuty severity specified ({}) is invalid.' \
                  .format(severity)
            self.logger.warning(msg)
            raise TypeError(msg)

        # A clickthrough option for notifications
        self.click = click

        # Store Class ID if specified
        self.class_id = class_id

        # Store Group if specified
        self.group = group

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
            'routing_key': self.integration_key,

            # Prepare our payload
            'payload': {
                'summary': body,

                # Set our severity
                'severity': PAGERDUTY_SEVERITY_MAP[notify_type]
                if not self.severity else self.severity,

                # Our Alerting Source/Component
                'source': self.source,
                'component': self.component,
            },
            'client': self.app_id,
            # Our Event Action
            'event_action': self.event_action,
        }

        if self.group:
            payload['payload']['group'] = self.group

        if self.class_id:
            payload['payload']['class'] = self.class_id

        if self.click:
            payload['links'] = [{
                "href": self.click,
            }]

        # Acquire our image url if configured to do so
        image_url = None if not self.include_image else \
            self.image_url(notify_type)

        if image_url:
            payload['images'] = [{
                'src': image_url,
                'alt': notify_type,
            }]

        if self.details:
            payload['payload']['custom_details'] = {}
            # Apply any provided custom details
            for k, v in self.details.items():
                payload['payload']['custom_details'][k] = v

        # Prepare our URL based on region
        notify_url = PAGERDUTY_API_LOOKUP[self.region_name]

        self.logger.debug('Pager Duty POST URL: %s (cert_verify=%r)' % (
            notify_url, self.verify_certificate,
        ))
        self.logger.debug('Pager Duty Payload: %s' % str(payload))

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
        params = {
            'region': self.region_name,
            'image': 'yes' if self.include_image else 'no',
        }
        if self.class_id:
            params['class'] = self.class_id

        if self.group:
            params['group'] = self.group

        if self.click is not None:
            params['click'] = self.click

        if self.severity:
            params['severity'] = self.severity

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

        if 'click' in results['qsd'] and len(results['qsd']['click']):
            results['click'] = NotifyPagerDuty.unquote(results['qsd']['click'])

        if 'group' in results['qsd'] and len(results['qsd']['group']):
            results['group'] = \
                NotifyPagerDuty.unquote(results['qsd']['group'])

        if 'class' in results['qsd'] and len(results['qsd']['class']):
            results['class_id'] = \
                NotifyPagerDuty.unquote(results['qsd']['class'])

        if 'severity' in results['qsd'] and len(results['qsd']['severity']):
            results['severity'] = \
                NotifyPagerDuty.unquote(results['qsd']['severity'])

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

        if 'region' in results['qsd'] and len(results['qsd']['region']):
            # Extract from name to associate with from address
            results['region_name'] = \
                NotifyPagerDuty.unquote(results['qsd']['region'])

        # Include images with our message
        results['include_image'] = \
            parse_bool(results['qsd'].get('image', True))

        return results
