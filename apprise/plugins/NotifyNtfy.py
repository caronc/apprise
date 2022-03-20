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
import requests
import six
from json import loads

from .NotifyBase import NotifyBase
from ..common import NotifyType
from ..AppriseLocale import gettext_lazy as _
from ..utils import parse_list
from ..URLBase import PrivacyMode


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

    # Default host if none is defined
    default_host = 'ntfy.sh'

    # Message time to live (if remote client isn't around to receive it)
    time_to_live = 2419200

    # Define object templates
    templates = (
        '{schema}://{topic}',
        '{schema}://{host}/{topic}',
        '{schema}://{host}:{port}/{topic}',
        '{schema}://{user}@{host}/{topic}',
        '{schema}://{user}@{host}:{port}/{topic}',
        '{schema}://{user}:{password}@{host}/{topic}',
        '{schema}://{user}:{password}@{host}:{port}/{topic}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'topic': {
            'name': _('Topic'),
            'type': 'string',
            'required': True,
        },
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
    })

    def __init__(self, topic, attach=None, click=None, delay=None,
                 email=None, priority=None, tags=None, **kwargs):
        """
        Initialize Ntfy Object
        """
        super(NotifyNtfy, self).__init__(**kwargs)
        if not topic:
            msg = 'A topic name must be provided.'
            self.logger.warning(msg)
            raise TypeError(msg)

        self.topic = topic

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

        # prepare our fullpath
        self.fullpath = kwargs.get('fullpath')
        if not isinstance(self.fullpath, six.string_types):
            self.fullpath = '/'

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Ntfy Notification
        """

        # error tracking (used for function return)
        has_error = False

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
        if self.user:
            auth = (self.user, self.password)

        # Prepare our Ntfy URL
        schema = 'https' if self.secure else 'http'

        # Use default host if one is not defined
        host = self.default_host
        if self.host != self.default_host:
            host = self.host

        url = '%s://%s' % (schema, host)
        if isinstance(self.port, int):
            url += ':%d' % self.port

        url += self.fullpath

        self.logger.debug('ntfy POST URL: %s (cert_verify=%r)' % (
            url, self.verify_certificate,
        ))
        self.logger.debug('ntfy Payload: %s' % str(payload))

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
                        self.topic,
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

        host = self.host or self.default_host
        default_port = 443 if self.secure else 80

        params = {
            'priority': self.priority
            if self.priority
            else NTFY_PRIORITIES.DEFAULT,
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

        return '{schema}://{auth}{host}{port}{topic}/?{params}'.format(
            schema=self.secure_protocol if self.secure else self.protocol,
            auth=auth,
            host='' if self.host == self.default_host else self.host,
            port='' if self.port is None or self.port == default_port
                 else ':{}'.format(self.port),
            topic='{}{}'.format(
                  '' if host == self.default_host and self.port == default_port
                  else '/', self.topic),
            params=NotifyNtfy.urlencode(params)
        )

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to re-instantiate this object.
        """
        results = NotifyBase.parse_url(url)

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

        try:
            # Grab the topic from the URL
            results['topic'] = NotifyNtfy.split_path(results['fullpath'])[-1]

        except IndexError:  # Not enough paths, probably no host provided
            results['topic'] = results['host']
            results['host'] = NotifyNtfy.default_host
            results['fullpath'] = '/{}'.format(results['topic'])

        return results
