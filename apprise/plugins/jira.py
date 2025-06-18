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

# Knowing this, you can build your Jira URL as follows:
#  jira://{apikey}/
#  jira://{apikey}/@{user}
#  jira://{apikey}/*{schedule}
#  jira://{apikey}/^{escalation}
#  jira://{apikey}/#{team}
#
# You can mix and match what you want to notify freely
#  jira://{apikey}/@{user}/#{team}/*{schedule}/^{escalation}
#
# If no target prefix is specified, then it is assumed to be a user.
#
# API Documentation: \
#     https://developer.atlassian.com/cloud/jira/ \
#           service-desk-ops/rest/v1/api-group-integration-events/

import requests
from json import dumps, loads
import hashlib

from .base import NotifyBase
from ..common import NotifyType, NOTIFY_TYPES
from ..common import PersistentStoreMode
from ..utils.parse import validate_regex, is_uuid, parse_list, parse_bool
from ..locale import gettext_lazy as _


class JiraCategory(NotifyBase):
    """
    We define the different category types that we can notify
    """
    USER = 'user'
    SCHEDULE = 'schedule'
    ESCALATION = 'escalation'
    TEAM = 'team'


JIRA_CATEGORIES = (
    JiraCategory.USER,
    JiraCategory.SCHEDULE,
    JiraCategory.ESCALATION,
    JiraCategory.TEAM,
)


class JiraAlertAction:
    """
    Defines the supported actions
    """
    # Use mapping (specify :key=arg to over-ride)
    MAP = 'map'

    # Create new alert (default)
    NEW = 'new'

    # Close Alert
    CLOSE = 'close'

    # Delete Alert
    DELETE = 'delete'

    # Acknowledge Alert
    ACKNOWLEDGE = 'acknowledge'

    # Add note to alert
    NOTE = 'note'


JIRA_ACTIONS = (
    JiraAlertAction.MAP,
    JiraAlertAction.NEW,
    JiraAlertAction.CLOSE,
    JiraAlertAction.DELETE,
    JiraAlertAction.ACKNOWLEDGE,
    JiraAlertAction.NOTE,
)

# Map all support Apprise Categories to Jira Categories
JIRA_ALERT_MAP = {
    NotifyType.INFO: JiraAlertAction.CLOSE,
    NotifyType.SUCCESS: JiraAlertAction.CLOSE,
    NotifyType.WARNING: JiraAlertAction.NEW,
    NotifyType.FAILURE: JiraAlertAction.NEW,
}


# Regions
class JiraRegion:
    US = 'us'
    EU = 'eu'


# Jira APIs (OpsGenie port - so keep us/en support for easy transition)
JIRA_API_LOOKUP = {
    JiraRegion.US: 'https://api.atlassian.com/jsm/ops/integration/v2/alerts',
    JiraRegion.EU: 'https://api.atlassian.com/jsm/ops/integration/v2/alerts',
}

# A List of our regions we can use for verification
JIRA_REGIONS = (
    JiraRegion.US,
    JiraRegion.EU,
)


# Priorities
class JiraPriority:
    LOW = 1
    MODERATE = 2
    NORMAL = 3
    HIGH = 4
    EMERGENCY = 5


JIRA_PRIORITIES = {
    # Note: This also acts as a reverse lookup mapping
    JiraPriority.LOW: 'low',
    JiraPriority.MODERATE: 'moderate',
    JiraPriority.NORMAL: 'normal',
    JiraPriority.HIGH: 'high',
    JiraPriority.EMERGENCY: 'emergency',
}

JIRA_PRIORITY_MAP = {
    # Maps against string 'low'
    'l': JiraPriority.LOW,
    # Maps against string 'moderate'
    'm': JiraPriority.MODERATE,
    # Maps against string 'normal'
    'n': JiraPriority.NORMAL,
    # Maps against string 'high'
    'h': JiraPriority.HIGH,
    # Maps against string 'emergency'
    'e': JiraPriority.EMERGENCY,

    # Entries to additionally support (so more like Jira's API)
    '1': JiraPriority.LOW,
    '2': JiraPriority.MODERATE,
    '3': JiraPriority.NORMAL,
    '4': JiraPriority.HIGH,
    '5': JiraPriority.EMERGENCY,
    # Support p-prefix
    'p1': JiraPriority.LOW,
    'p2': JiraPriority.MODERATE,
    'p3': JiraPriority.NORMAL,
    'p4': JiraPriority.HIGH,
    'p5': JiraPriority.EMERGENCY,
}


class NotifyJira(NotifyBase):
    """
    A wrapper for Jira Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Jira'

    # The services URL
    service_url = 'https://atlassian.com/'

    # All notification requests are secure
    secure_protocol = 'jira'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_jira'

    # The maximum length of the body
    body_maxlen = 15000

    # Our default is to no not use persistent storage beyond in-memory
    # reference
    storage_mode = PersistentStoreMode.AUTO

    # If we don't have the specified min length, then we don't bother using
    # the body directive
    jira_body_minlen = 130

    # The default region to use if one isn't otherwise specified
    jira_default_region = JiraRegion.US

    # The maximum allowable targets within a notification
    default_batch_size = 50

    # Defines our default message mapping
    jira_message_map = {
        # Add a note to existing alert
        NotifyType.INFO: JiraAlertAction.NOTE,
        # Close existing alert
        NotifyType.SUCCESS: JiraAlertAction.CLOSE,
        # Create notice
        NotifyType.WARNING: JiraAlertAction.NEW,
        # Create notice
        NotifyType.FAILURE: JiraAlertAction.NEW,
    }

    # Define object templates
    templates = (
        '{schema}://{apikey}',
        '{schema}://{user}@{apikey}',
        '{schema}://{apikey}/{targets}',
        '{schema}://{user}@{apikey}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'apikey': {
            'name': _('API Key'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'user': {
            'name': _('Username'),
            'type': 'string',
        },
        'target_escalation': {
            'name': _('Target Escalation'),
            'prefix': '^',
            'type': 'string',
            'map_to': 'targets',
        },
        'target_schedule': {
            'name': _('Target Schedule'),
            'type': 'string',
            'prefix': '*',
            'map_to': 'targets',
        },
        'target_user': {
            'name': _('Target User'),
            'type': 'string',
            'prefix': '@',
            'map_to': 'targets',
        },
        'target_team': {
            'name': _('Target Team'),
            'type': 'string',
            'prefix': '#',
            'map_to': 'targets',
        },
        'targets': {
            'name': _('Targets '),
            'type': 'list:string',
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'region': {
            'name': _('Region Name'),
            'type': 'choice:string',
            'values': JIRA_REGIONS,
            'default': JiraRegion.US,
            'map_to': 'region_name',
        },
        'batch': {
            'name': _('Batch Mode'),
            'type': 'bool',
            'default': False,
        },
        'priority': {
            'name': _('Priority'),
            'type': 'choice:int',
            'values': JIRA_PRIORITIES,
            'default': JiraPriority.NORMAL,
        },
        'entity': {
            'name': _('Entity'),
            'type': 'string',
        },
        'alias': {
            'name': _('Alias'),
            'type': 'string',
        },
        'tags': {
            'name': _('Tags'),
            'type': 'string',
        },
        'to': {
            'alias_of': 'targets',
        },
        'action': {
            'name': _('Action'),
            'type': 'choice:string',
            'values': JIRA_ACTIONS,
            'default': JIRA_ACTIONS[0],
        }
    })

    # Map of key-value pairs to use as custom properties of the alert.
    template_kwargs = {
        'details': {
            'name': _('Details'),
            'prefix': '+',
        },
        'mapping': {
            'name': _('Action Mapping'),
            'prefix': ':',
        },
    }

    def __init__(self, apikey, targets, region_name=None, details=None,
                 priority=None, alias=None, entity=None, batch=False,
                 tags=None, action=None, mapping=None, **kwargs):
        """
        Initialize Jira Object
        """
        super().__init__(**kwargs)

        # API Key (associated with project)
        self.apikey = validate_regex(apikey)
        if not self.apikey:
            msg = 'An invalid Jira API Key ' \
                  '({}) was specified.'.format(apikey)
            self.logger.warning(msg)
            raise TypeError(msg)

        # The Priority of the message
        self.priority = NotifyJira.template_args['priority']['default'] \
            if not priority else \
            next((
                v for k, v in JIRA_PRIORITY_MAP.items()
                if str(priority).lower().startswith(k)),
                NotifyJira.template_args['priority']['default'])

        # Store our region
        try:
            self.region_name = self.jira_default_region \
                if region_name is None else region_name.lower()

            if self.region_name not in JIRA_REGIONS:
                # allow the outer except to handle this common response
                raise
        except:
            # Invalid region specified
            msg = 'The Jira region specified ({}) is invalid.' \
                  .format(region_name)
            self.logger.warning(msg)
            raise TypeError(msg)

        if action and isinstance(action, str):
            self.action = next(
                (a for a in JIRA_ACTIONS if a.startswith(action)), None)
            if self.action not in JIRA_ACTIONS:
                msg = 'The Jira action specified ({}) is invalid.'\
                    .format(action)
                self.logger.warning(msg)
                raise TypeError(msg)
        else:
            self.action = self.template_args['action']['default']

        # Store our mappings
        self.mapping = self.jira_message_map.copy()
        if mapping and isinstance(mapping, dict):
            for _k, _v in mapping.items():
                # Get our mapping
                k = next((t for t in NOTIFY_TYPES if t.startswith(_k)), None)
                if not k:
                    msg = 'The Jira mapping key specified ({}) ' \
                        'is invalid.'.format(_k)
                    self.logger.warning(msg)
                    raise TypeError(msg)

                _v_lower = _v.lower()
                v = next((v for v in JIRA_ACTIONS[1:]
                          if v.startswith(_v_lower)), None)
                if not v:
                    msg = 'The Jira mapping value (assigned to {}) ' \
                          'specified ({}) is invalid.'.format(k, _v)
                    self.logger.warning(msg)
                    raise TypeError(msg)

                # Update our mapping
                self.mapping[k] = v

        self.details = {}
        if details:
            # Store our extra details
            self.details.update(details)

        # Prepare Batch Mode Flag
        self.batch_size = self.default_batch_size if batch else 1

        # Assign our tags (if defined)
        self.__tags = parse_list(tags)

        # Assign our entity (if defined)
        self.entity = entity

        # Assign our alias (if defined)
        self.alias = alias

        # Initialize our Targets
        self.targets = []

        # Sort our targets
        for _target in parse_list(targets):
            target = _target.strip()
            if len(target) < 2:
                self.logger.debug('Ignoring Jira Entry: %s' % target)
                continue

            if target.startswith(NotifyJira.template_tokens
                                 ['target_team']['prefix']):

                self.targets.append(
                    {'type': JiraCategory.TEAM, 'id': target[1:]}
                    if is_uuid(target[1:]) else
                    {'type': JiraCategory.TEAM, 'name': target[1:]})

            elif target.startswith(NotifyJira.template_tokens
                                   ['target_schedule']['prefix']):

                self.targets.append(
                    {'type': JiraCategory.SCHEDULE, 'id': target[1:]}
                    if is_uuid(target[1:]) else
                    {'type': JiraCategory.SCHEDULE, 'name': target[1:]})

            elif target.startswith(NotifyJira.template_tokens
                                   ['target_escalation']['prefix']):

                self.targets.append(
                    {'type': JiraCategory.ESCALATION, 'id': target[1:]}
                    if is_uuid(target[1:]) else
                    {'type': JiraCategory.ESCALATION, 'name': target[1:]})

            elif target.startswith(NotifyJira.template_tokens
                                   ['target_user']['prefix']):

                self.targets.append(
                    {'type': JiraCategory.USER, 'id': target[1:]}
                    if is_uuid(target[1:]) else
                    {'type': JiraCategory.USER, 'username': target[1:]})

            else:
                # Ambiguious entry; treat it as a user but not before
                # displaying a warning to the end user first:
                self.logger.debug(
                    'Treating ambigious Jira target %s as a user', target)
                self.targets.append(
                    {'type': JiraCategory.USER, 'id': target}
                    if is_uuid(target) else
                    {'type': JiraCategory.USER, 'username': target})

    def _fetch(self, method, url, payload, params=None):
        """
        Performs server retrieval/update and returns JSON Response
        """
        headers = {
            'User-Agent': self.app_id,
            'Accepts': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': 'GenieKey {}'.format(self.apikey),
        }

        # Some Debug Logging
        self.logger.debug(
            'Jira POST URL: {} (cert_verify={})'.format(
                url, self.verify_certificate))
        self.logger.debug('Jira Payload: {}' .format(payload))

        # Initialize our response object
        content = {}

        # Always call throttle before any remote server i/o is made
        self.throttle()
        try:
            r = method(
                url,
                data=dumps(payload),
                params=params,
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )

            # A Response might look like:
            # {
            #     "result": "Request will be processed",
            #     "took": 0.302,
            #     "requestId": "43a29c5c-3dbf-4fa4-9c26-f4f71023e120"
            # }

            try:
                # Update our response object
                content = loads(r.content)

            except (AttributeError, TypeError, ValueError):
                # ValueError = r.content is Unparsable
                # TypeError = r.content is None
                # AttributeError = r is None
                content = {}

            if r.status_code not in (
                    requests.codes.accepted, requests.codes.ok):
                status_str = \
                    NotifyBase.http_response_code_lookup(
                        r.status_code)

                self.logger.warning(
                    'Failed to send Jira notification:'
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))

                return (False, content.get('requestId'))

            # If we reach here; the message was sent
            self.logger.info('Sent Jira notification')
            self.logger.debug(
                'Response Details:\r\n{}'.format(r.content))

            return (True, content.get('requestId'))

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred sending Jira '
                'notification.')
            self.logger.debug('Socket Exception: %s' % str(e))

        return (False, content.get('requestId'))

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Jira Notification
        """

        # Get our Jira Action
        action = JIRA_ALERT_MAP[notify_type] \
            if self.action == JiraAlertAction.MAP else self.action

        # Prepare our URL as it's based on our hostname
        notify_url = JIRA_API_LOOKUP[self.region_name]

        # Initialize our has_error flag
        has_error = False

        # Default method is to post
        method = requests.post

        # For indexing in persistent store
        key = hashlib.sha1(
            (self.entity if self.entity else (
                self.alias if self.alias else (
                    title if title else self.app_id)))
            .encode('utf-8')).hexdigest()[0:10]

        # Get our Jira Request IDs
        request_ids = self.store.get(key, [])
        if not isinstance(request_ids, list):
            request_ids = []

        if action == JiraAlertAction.NEW:
            # Create a copy ouf our details object
            details = self.details.copy()
            if 'type' not in details:
                details['type'] = notify_type

            # Use body if title not set
            title_body = body if not title else title

            # Prepare our payload
            payload = {
                'source': self.app_desc,
                'message': title_body,
                'description': body,
                'details': details,
                'priority': 'P{}'.format(self.priority),
            }

            # Use our body directive if we exceed the minimum message
            # limitation
            if len(payload['message']) > self.jira_body_minlen:
                payload['message'] = '{}...'.format(
                    title_body[:self.jira_body_minlen - 3])

            if self.__tags:
                payload['tags'] = self.__tags

            if self.entity:
                payload['entity'] = self.entity

            if self.alias:
                payload['alias'] = self.alias

            if self.user:
                payload['user'] = self.user

            # reset our request IDs - we will re-populate them
            request_ids = []

            length = len(self.targets) if self.targets else 1
            for index in range(0, length, self.batch_size):
                if self.targets:
                    # If there were no targets identified, then we simply
                    # just iterate once without the responders set
                    payload['responders'] = \
                        self.targets[index:index + self.batch_size]

                # Perform our post
                success, request_id = self._fetch(
                    method, notify_url, payload)

                if success and request_id:
                    # Save our response
                    request_ids.append(request_id)

                else:
                    has_error = True

            # Store our entries for a maximum of 60 days
            self.store.set(key, request_ids, expires=60 * 60 * 24 * 60)

        elif request_ids:
            # Prepare our payload
            payload = {
                'source': self.app_desc,
                'note': body,
            }

            if self.user:
                payload['user'] = self.user

            # Prepare our Identifier type
            params = {
                'identifierType': 'id',
            }

            for request_id in request_ids:
                if action == JiraAlertAction.DELETE:
                    # Update our URL
                    url = f'{notify_url}/{request_id}'
                    method = requests.delete

                elif action == JiraAlertAction.ACKNOWLEDGE:
                    url = f'{notify_url}/{request_id}/acknowledge'

                elif action == JiraAlertAction.CLOSE:
                    url = f'{notify_url}/{request_id}/close'

                else:  # action == JiraAlertAction.CLOSE:
                    url = f'{notify_url}/{request_id}/notes'

                # Perform our post
                success, _ = self._fetch(method, url, payload, params)

                if not success:
                    has_error = True

            if not has_error and action == JiraAlertAction.DELETE:
                # Remove cached entry
                self.store.clear(key)

        else:
            self.logger.info(
                'No Jira notification sent due to (nothing to %s) '
                'condition', self.action)

        return not has_error

    @property
    def url_identifier(self):
        """
        Returns all of the identifiers that make this URL unique from
        another simliar one. Targets or end points should never be identified
        here.
        """
        return (self.secure_protocol, self.region_name, self.apikey)

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'action': self.action,
            'region': self.region_name,
            'priority':
                JIRA_PRIORITIES[self.template_args['priority']['default']]
                if self.priority not in JIRA_PRIORITIES
                else JIRA_PRIORITIES[self.priority],
            'batch': 'yes' if self.batch_size > 1 else 'no',
        }

        # Assign our entity value (if defined)
        if self.entity:
            params['entity'] = self.entity

        # Assign our alias value (if defined)
        if self.alias:
            params['alias'] = self.alias

        # Assign our tags (if specifed)
        if self.__tags:
            params['tags'] = ','.join(self.__tags)

        # Append our details into our parameters
        params.update({'+{}'.format(k): v for k, v in self.details.items()})

        # Append our assignment extra's into our parameters
        params.update(
            {':{}'.format(k): v for k, v in self.mapping.items()})

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # A map allows us to map our target types so they can be correctly
        # placed back into your URL below. Hence map the 'user' -> '@'
        __map = {
            JiraCategory.USER:
                NotifyJira.template_tokens['target_user']['prefix'],
            JiraCategory.SCHEDULE:
                NotifyJira.template_tokens['target_schedule']['prefix'],
            JiraCategory.ESCALATION:
                NotifyJira.template_tokens['target_escalation']['prefix'],
            JiraCategory.TEAM:
                NotifyJira.template_tokens['target_team']['prefix'],
        }

        return '{schema}://{user}{apikey}/{targets}/?{params}'.format(
            schema=self.secure_protocol,
            user='{}@'.format(self.user) if self.user else '',
            apikey=self.pprint(self.apikey, privacy, safe=''),
            targets='/'.join(
                [NotifyJira.quote('{}{}'.format(
                    __map[x['type']],
                    x.get('id', x.get('name', x.get('username')))))
                    for x in self.targets]),
            params=NotifyJira.urlencode(params))

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """
        #
        # Factor batch into calculation
        #
        targets = len(self.targets)
        if self.batch_size > 1:
            targets = int(targets / self.batch_size) + \
                (1 if targets % self.batch_size else 0)

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

        # The API Key is stored in the hostname
        results['apikey'] = NotifyJira.unquote(results['host'])

        # Get our Targets
        results['targets'] = NotifyJira.split_path(results['fullpath'])

        # Add our Meta Detail keys
        results['details'] = {NotifyBase.unquote(x): NotifyBase.unquote(y)
                              for x, y in results['qsd+'].items()}

        # Set our priority
        if 'priority' in results['qsd'] and len(results['qsd']['priority']):
            results['priority'] = \
                NotifyJira.unquote(results['qsd']['priority'])

        # Get Batch Boolean (if set)
        results['batch'] = \
            parse_bool(
                results['qsd'].get(
                    'batch',
                    NotifyJira.template_args['batch']['default']))

        if 'apikey' in results['qsd'] and len(results['qsd']['apikey']):
            results['apikey'] = \
                NotifyJira.unquote(results['qsd']['apikey'])

        if 'tags' in results['qsd'] and len(results['qsd']['tags']):
            # Extract our tags
            results['tags'] = \
                parse_list(NotifyJira.unquote(results['qsd']['tags']))

        if 'region' in results['qsd'] and len(results['qsd']['region']):
            # Extract our region
            results['region_name'] = \
                NotifyJira.unquote(results['qsd']['region'])

        if 'entity' in results['qsd'] and len(results['qsd']['entity']):
            # Extract optional entity field
            results['entity'] = \
                NotifyJira.unquote(results['qsd']['entity'])

        if 'alias' in results['qsd'] and len(results['qsd']['alias']):
            # Extract optional alias field
            results['alias'] = \
                NotifyJira.unquote(results['qsd']['alias'])

        # Handle 'to' email address
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'].append(results['qsd']['to'])

        # Store our action (if defined)
        if 'action' in results['qsd'] and len(results['qsd']['action']):
            results['action'] = \
                NotifyJira.unquote(results['qsd']['action'])

        # store any custom mapping defined
        results['mapping'] = \
            {NotifyJira.unquote(x): NotifyJira.unquote(y)
             for x, y in results['qsd:'].items()}

        return results
