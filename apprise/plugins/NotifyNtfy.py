# MIT License

# Copyright (c) 2022 Joey Espinosa <@particledecay>

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Examples:
#   ntfys://my-topic
#   ntfy://ntfy.local.domain/my-topic
#   ntfys://ntfy.local.domain:8080/my-topic
#   ntfy://ntfy.local.domain/?priority=max
import re
import requests
import six
from json import loads

from .NotifyBase import NotifyBase
from ..common import NotifyType
from ..AppriseLocale import gettext_lazy as _
from ..utils import parse_list
from ..utils import is_hostname
from ..utils import is_ipaddr
from ..URLBase import PrivacyMode


class NtfyMode(object):
    """
    Define Ntfy Notification Modes
    """
    # App posts upstream to the developer API on Ntfy's website
    CLOUD = "cloud"

    # Running a dedicated private Ntfy Server
    PRIVATE = "private"


NTFY_MODES = (
    NtfyMode.CLOUD,
    NtfyMode.PRIVATE,
)


class NtfyPriority(object):
    """
    Ntfy Priority Definitions
    """
    MAX = 'max'
    HIGH = 'high'
    DEFAULT = 'default'
    LOW = 'low'
    MIN = 'min'

    VALUES = (
        (MAX, 5),
        (HIGH, 4),
        (DEFAULT, 3),
        (LOW, 2),
        (MIN, 1),
    )

    @classmethod
    def get_priority(cls, value):
        priorities = [p[0] for p in NtfyPriority.VALUES if p[1] == value]
        if priorities:
            return priorities[0]
        named_priorities = [p[0] for p in NtfyPriority.VALUES if p[0] == value]
        if named_priorities:
            return named_priorities[0]
        return


NTFY_PRIORITIES = (
    NtfyPriority.MAX,
    NtfyPriority.HIGH,
    NtfyPriority.DEFAULT,
    NtfyPriority.LOW,
    NtfyPriority.MIN,
)


class NotifyNtfy(NotifyBase):
    """
    A wrapper for Ntfy Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'ntfy'

    # The services URL
    service_url = 'https://ntfy.sh/'

    # Insecure protocol (for those self hosted requests)
    protocol = 'ntfy'

    # The default protocol
    secure_protocol = 'ntfys'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_ntfy'

    # Default upstream/cloud host if none is defined
    cloud_notify_url = 'https://ntfy.sh'

    # Message time to live (if remote client isn't around to receive it)
    time_to_live = 2419200

    # Define object templates
    templates = (
        '{schema}://{topic}',
        '{schema}://{host}/{targets}',
        '{schema}://{host}:{port}/{targets}',
        '{schema}://{user}@{host}/{targets}',
        '{schema}://{user}@{host}:{port}/{targets}',
        '{schema}://{user}:{password}@{host}/{targets}',
        '{schema}://{user}:{password}@{host}:{port}/{targets}',
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
        'topic': {
            'name': _('Topic'),
            'type': 'string',
            'map_to': 'targets',
        },
        'targets': {
            'name': _('Targets'),
            'type': 'list:string',
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'attach': {
            'name': _('Attach'),
            'type': 'string',
        },
        'click': {
            'name': _('Click'),
            'type': 'string',
        },
        'delay': {
            'name': _('Delay'),
            'type': 'string',
        },
        'email': {
            'name': _('Email'),
            'type': 'string',
        },
        'priority': {
            'name': _('Priority'),
            'type': 'choice:string',
            'values': NTFY_PRIORITIES,
            'default': NtfyPriority.DEFAULT,
        },
        'tags': {
            'name': _('Tags'),
            'type': 'string',
        },
        'mode': {
            'name': _('Mode'),
            'type': 'choice:string',
            'values': NTFY_MODES,
            'default': NtfyMode.PRIVATE,
        },
        'to': {
            'alias_of': 'targets',
        },
    })

    def __init__(self, targets=None, attach=None, click=None, delay=None,
                 email=None, priority=None, tags=None, mode=None, **kwargs):
        """
        Initialize Ntfy Object
        """
        super(NotifyNtfy, self).__init__(**kwargs)

        # Prepare our mode
        self.mode = mode.strip().lower() \
            if isinstance(mode, six.string_types) \
            else self.template_args['mode']['default']

        if self.mode not in NTFY_MODES:
            msg = 'An invalid Ntfy Mode ({}) was specified.'.format(mode)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Build list of topics
        self.topics = parse_list(targets)

        # Attach a file (URL supported)
        self.attach = attach

        # A clickthrough option for notifications
        self.click = click

        # Time delay for notifications (various string formats)
        self.delay = delay

        # An email to forward notifications to
        self.email = email

        # The priority of the message
        if priority not in NTFY_PRIORITIES:
            self.priority = self.template_args['priority']['default']

        else:
            self.priority = priority

        # Any optional tags to attach to the notification
        self.__tags = parse_list(tags)

        if not self.topics:
            self.logger.warning(
                'No Ntfy topics were identified to be notified')
        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Ntfy Notification
        """

        # error tracking (used for function return)
        has_error = False

        if not len(self.topics):
            # We have nothing to notify; we're done
            self.logger.warning('There are no Ntfy topics to notify')
            return False

        # Prepare our headers
        headers = {
            'User-Agent': self.app_id,
        }

        priority = NtfyPriority.get_priority(self.priority)
        if priority != NtfyPriority.DEFAULT:
            headers['X-Priority'] = priority

        if title:
            headers['X-Title'] = title

        if self.attach is not None:
            headers['X-Attach'] = self.attach

        if self.click is not None:
            headers['X-Click'] = self.click

        if self.delay is not None:
            headers['X-Delay'] = self.delay

        if self.email is not None:
            headers['X-Email'] = self.email

        if self.__tags:
            headers['X-Tags'] = ",".join(self.__tags)

        # Prepare our payload
        payload = body

        auth = None
        if self.mode == NtfyMode.CLOUD:
            # Cloud Service
            template_url = self.cloud_notify_url

        else:  # NotifyNtfy.PRVATE
            # Allow more settings to be applied now
            if self.user:
                auth = (self.user, self.password)

            # Prepare our Ntfy Template URL
            schema = 'https' if self.secure else 'http'

            template_url = '%s://%s' % (schema, self.host)
            if isinstance(self.port, int):
                template_url += ':%d' % self.port

        template_url += '/{topic}'

        # Create a copy of the subreddits list
        topics = list(self.topics)
        while len(topics) > 0:
            # Retrieve our topic
            topic = topics.pop()

            # Create our Posting URL per topic provided
            url = template_url.format(topic=topic)
            self.logger.debug('Ntfy POST URL: %s (cert_verify=%r)' % (
                url, self.verify_certificate,
            ))
            self.logger.debug('Ntfy Payload: %s' % str(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()

            try:
                r = requests.post(
                    url,
                    data=payload,
                    headers=headers,
                    auth=auth,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )

                if r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = \
                        NotifyBase.http_response_code_lookup(r.status_code)

                    # set up our status code to use
                    status_code = r.status_code

                    try:
                        # Update our status response if we can
                        json_response = loads(r.content)
                        status_code = json_response.get('code', status_code)
                        status_str = json_response.get('error', status_str)

                    except (AttributeError, TypeError, ValueError):
                        # ValueError = r.content is Unparsable
                        # TypeError = r.content is None
                        # AttributeError = r is None

                        # We could not parse JSON response.
                        # We will just use the status we already have.
                        pass

                    self.logger.warning(
                        "Failed to send Ntfy notification to topic '{}': "
                        '{}{}error={}.'.format(
                            topic,
                            status_str,
                            ', ' if status_str else '',
                            status_code))

                    self.logger.debug(
                        'Response Details:\r\n{}'.format(r.content))

                    # Mark our failure
                    has_error = True

                else:
                    self.logger.info(
                        "Sent Ntfy notification to '{}'.".format(url))

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occurred sending Ntfy:%s ' % (
                        url) + 'notification.'
                )
                self.logger.debug('Socket Exception: %s' % str(e))

                # Mark our failure
                has_error = True

        return not has_error

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        default_port = 443 if self.secure else 80

        params = {
            'priority': self.priority
            if self.priority
            else NTFY_PRIORITIES.DEFAULT,
            'mode': self.mode,
        }

        if self.attach is not None:
            params['attach'] = self.attach

        if self.click is not None:
            params['click'] = self.click

        if self.delay is not None:
            params['delay'] = self.delay

        if self.email is not None:
            params['email'] = self.email

        if self.__tags:
            params['tags'] = ','.join(self.__tags)

        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Determine Authentication
        auth = ''
        if self.user and self.password:
            auth = '{user}:{password}@'.format(
                user=NotifyNtfy.quote(self.user, safe=''),
                password=self.pprint(
                    self.password, privacy, mode=PrivacyMode.Secret, safe=''),
            )
        elif self.user:
            auth = '{user}@'.format(
                user=NotifyNtfy.quote(self.user, safe=''),
            )

        if self.mode == NtfyMode.PRIVATE:
            return '{schema}://{auth}{host}{port}/{targets}?{params}'.format(
                schema=self.secure_protocol if self.secure else self.protocol,
                auth=auth,
                host=self.host,
                port='' if self.port is None or self.port == default_port
                else ':{}'.format(self.port),
                targets='/'.join(
                    [NotifyNtfy.quote(x, safe='') for x in self.topics]),
                params=NotifyNtfy.urlencode(params)
            )

        else:  # Cloud mode
            return '{schema}://{targets}?{params}'.format(
                schema=self.secure_protocol,
                targets='/'.join(
                    [NotifyNtfy.quote(x, safe='') for x in self.topics]),
                params=NotifyNtfy.urlencode(params)
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

        if 'priority' in results['qsd'] and len(results['qsd']['priority']):
            try:
                results['priority'] = \
                    NtfyPriority.get_priority(results['qsd']['priority'])
            except KeyError:  # no priority was set
                pass

        if 'attach' in results['qsd'] and len(results['qsd']['attach']):
            results['attach'] = NotifyNtfy.unquote(results['qsd']['attach'])

        if 'click' in results['qsd'] and len(results['qsd']['click']):
            results['click'] = NotifyNtfy.unquote(results['qsd']['click'])

        if 'delay' in results['qsd'] and len(results['qsd']['delay']):
            results['delay'] = NotifyNtfy.unquote(results['qsd']['delay'])

        if 'email' in results['qsd'] and len(results['qsd']['email']):
            results['email'] = NotifyNtfy.unquote(results['qsd']['email'])

        if 'tags' in results['qsd'] and len(results['qsd']['tags']):
            results['tags'] = \
                parse_list(NotifyNtfy.unquote(results['qsd']['tags']))

        # Acquire our targets/topics
        results['targets'] = NotifyNtfy.split_path(results['fullpath'])

        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyNtfy.parse_list(results['qsd']['to'])

        # Mode override
        if 'mode' in results['qsd'] and results['qsd']['mode']:
            results['mode'] = NotifyNtfy.unquote(
                results['qsd']['mode'].strip().lower())

        else:
            # We can try to detect the mode based on the validity of the
            # hostname.
            #
            # This isn't a surfire way to do things though; it's best to
            # specify the mode= flag
            results['mode'] = NtfyMode.PRIVATE \
                if ((is_hostname(results['host']) or
                    is_ipaddr(results['host'])) and results['targets']) \
                else NtfyMode.CLOUD

        if results['mode'] == NtfyMode.CLOUD:
            # Store first entry as it can be a topic too in this case
            # But only if we also rule it out not being the words
            # ntfy.sh itself, something that starts wiht an non-alpha numeric
            # character:
            if not re.search(
                    r'(ntfy\.sh|[^A-Za-z0-9][A-Za-z0-9_-]*)', results['host']):
                # Add it to the front of the list for consistency
                results['targets'].insert(0, results['host'])

        elif results['mode'] == NtfyMode.PRIVATE and \
                not (is_hostname(results['host'] or
                     is_ipaddr(results['host']))):
            # Invalid Host for NtfyMode.PRIVATE
            return None

        return results

    @staticmethod
    def parse_native_url(url):
        """
        Support https://ntfy.sh/topic
        """

        # Quick lookup for users who want to just paste
        # the ntfy.sh url directly into Apprise
        result = re.match(
            r'^https?://ntfy\.sh/'
            r'(?P<topics>[^?]+)'
            r'(?P<params>\?.+)?$', url, re.I)

        if result:
            mode = 'mode=%s' % NtfyMode.CLOUD
            return NotifyNtfy.parse_url(
                '{schema}://{topics}{params}'.format(
                    schema=NotifyNtfy.secure_protocol,
                    topics=result.group('topics'),
                    params='?%s' % mode
                    if not result.group('params')
                    else result.group('params') + '&%s' % mode))

        return None
