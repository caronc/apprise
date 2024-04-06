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

# Great sources
# - https://github.com/matrix-org/matrix-python-sdk
# - https://github.com/matrix-org/synapse/blob/master/docs/reverse_proxy.rst
#
# Examples:
#   ntfys://my-topic
#   ntfy://ntfy.local.domain/my-topic
#   ntfys://ntfy.local.domain:8080/my-topic
#   ntfy://ntfy.local.domain/?priority=max
import re
import requests
from json import loads
from json import dumps
from os.path import basename

from .NotifyBase import NotifyBase
from ..common import NotifyFormat
from ..common import NotifyType
from ..common import NotifyImageSize
from ..AppriseLocale import gettext_lazy as _
from ..utils import parse_list
from ..utils import parse_bool
from ..utils import is_hostname
from ..utils import is_ipaddr
from ..utils import validate_regex
from ..URLBase import PrivacyMode
from ..attachment.AttachBase import AttachBase


class NtfyMode:
    """
    Define ntfy Notification Modes
    """
    # App posts upstream to the developer API on ntfy's website
    CLOUD = "cloud"

    # Running a dedicated private ntfy Server
    PRIVATE = "private"


NTFY_MODES = (
    NtfyMode.CLOUD,
    NtfyMode.PRIVATE,
)

# A Simple regular expression used to auto detect Auth mode if it isn't
# otherwise specified:
NTFY_AUTH_DETECT_RE = re.compile('tk_[^ \t]+', re.IGNORECASE)


class NtfyAuth:
    """
    Define ntfy Authentication Modes
    """
    # Basic auth (user and password provided)
    BASIC = "basic"

    # Auth Token based
    TOKEN = "token"


NTFY_AUTH = (
    NtfyAuth.BASIC,
    NtfyAuth.TOKEN,
)


class NtfyPriority:
    """
    Ntfy Priority Definitions
    """
    MAX = 'max'
    HIGH = 'high'
    NORMAL = 'default'
    LOW = 'low'
    MIN = 'min'


NTFY_PRIORITIES = (
    NtfyPriority.MAX,
    NtfyPriority.HIGH,
    NtfyPriority.NORMAL,
    NtfyPriority.LOW,
    NtfyPriority.MIN,
)

NTFY_PRIORITY_MAP = {
    # Maps against string 'low' but maps to Moderate to avoid
    # conflicting with actual ntfy mappings
    'l': NtfyPriority.LOW,
    # Maps against string 'moderate'
    'mo': NtfyPriority.LOW,
    # Maps against string 'normal'
    'n': NtfyPriority.NORMAL,
    # Maps against string 'high'
    'h': NtfyPriority.HIGH,
    # Maps against string 'emergency'
    'e': NtfyPriority.MAX,

    # Entries to additionally support (so more like Ntfy's API)
    # Maps against string 'min'
    'mi': NtfyPriority.MIN,
    # Maps against string 'max'
    'ma': NtfyPriority.MAX,
    # Maps against string 'default'
    'd': NtfyPriority.NORMAL,

    # support 1-5 values as well
    '1': NtfyPriority.MIN,
    # Maps against string 'moderate'
    '2': NtfyPriority.LOW,
    # Maps against string 'normal'
    '3': NtfyPriority.NORMAL,
    # Maps against string 'high'
    '4': NtfyPriority.HIGH,
    # Maps against string 'emergency'
    '5': NtfyPriority.MAX,
}


class NotifyNtfy(NotifyBase):
    """
    A wrapper for ntfy Notifications
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

    # Support attachments
    attachment_support = True

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_256

    # Message time to live (if remote client isn't around to receive it)
    time_to_live = 2419200

    # if our hostname matches the following we automatically enforce
    # cloud mode
    __auto_cloud_host = re.compile(r'ntfy\.sh', re.IGNORECASE)

    # Define object templates
    templates = (
        '{schema}://{topic}',
        '{schema}://{host}/{targets}',
        '{schema}://{host}:{port}/{targets}',
        '{schema}://{user}@{host}/{targets}',
        '{schema}://{user}@{host}:{port}/{targets}',
        '{schema}://{user}:{password}@{host}/{targets}',
        '{schema}://{user}:{password}@{host}:{port}/{targets}',
        '{schema}://{token}@{host}/{targets}',
        '{schema}://{token}@{host}:{port}/{targets}',
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
            'name': _('Token'),
            'type': 'string',
            'private': True,
        },
        'topic': {
            'name': _('Topic'),
            'type': 'string',
            'map_to': 'targets',
            'regex': (r'^[a-z0-9_-]{1,64}$', 'i')
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
        'image': {
            'name': _('Include Image'),
            'type': 'bool',
            'default': True,
            'map_to': 'include_image',
        },
        'avatar_url': {
            'name': _('Avatar URL'),
            'type': 'string',
        },
        'filename': {
            'name': _('Attach Filename'),
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
            'default': NtfyPriority.NORMAL,
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
        'token': {
            'alias_of': 'token',
        },
        'auth': {
            'name': _('Authentication Type'),
            'type': 'choice:string',
            'values': NTFY_AUTH,
            'default': NtfyAuth.BASIC,
        },
        'to': {
            'alias_of': 'targets',
        },
    })

    def __init__(self, targets=None, attach=None, filename=None, click=None,
                 delay=None, email=None, priority=None, tags=None, mode=None,
                 include_image=True, avatar_url=None, auth=None, token=None,
                 **kwargs):
        """
        Initialize ntfy Object
        """
        super().__init__(**kwargs)

        # Prepare our mode
        self.mode = mode.strip().lower() \
            if isinstance(mode, str) \
            else self.template_args['mode']['default']

        if self.mode not in NTFY_MODES:
            msg = 'An invalid ntfy Mode ({}) was specified.'.format(mode)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Show image associated with notification
        self.include_image = include_image

        # Prepare our authentication type
        self.auth = auth.strip().lower() \
            if isinstance(auth, str) \
            else self.template_args['auth']['default']

        if self.auth not in NTFY_AUTH:
            msg = 'An invalid ntfy Authentication type ({}) was specified.' \
                .format(auth)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Attach a file (URL supported)
        self.attach = attach

        # Our filename (if defined)
        self.filename = filename

        # A clickthrough option for notifications
        self.click = click

        # Time delay for notifications (various string formats)
        self.delay = delay

        # An email to forward notifications to
        self.email = email

        # Save our token
        self.token = token

        # The Priority of the message
        self.priority = NotifyNtfy.template_args['priority']['default'] \
            if not priority else \
            next((
                v for k, v in NTFY_PRIORITY_MAP.items()
                if str(priority).lower().startswith(k)),
                NotifyNtfy.template_args['priority']['default'])

        # Any optional tags to attach to the notification
        self.__tags = parse_list(tags)

        # Avatar URL
        # This allows a user to provide an over-ride to the otherwise
        # dynamically generated avatar url images
        self.avatar_url = avatar_url

        # Build list of topics
        topics = parse_list(targets)
        self.topics = []
        for _topic in topics:
            topic = validate_regex(
                _topic, *self.template_tokens['topic']['regex'])
            if not topic:
                self.logger.warning(
                    'A specified ntfy topic ({}) is invalid and will be '
                    'ignored'.format(_topic))
                continue
            self.topics.append(topic)
        return

    def send(self, body, title='', notify_type=NotifyType.INFO, attach=None,
             **kwargs):
        """
        Perform ntfy Notification
        """

        # error tracking (used for function return)
        has_error = False

        if not len(self.topics):
            # We have nothing to notify; we're done
            self.logger.warning('There are no ntfy topics to notify')
            return False

        # Acquire image_url
        image_url = self.image_url(notify_type)

        if self.include_image and (image_url or self.avatar_url):
            image_url = \
                self.avatar_url if self.avatar_url else image_url
        else:
            image_url = None

        # Create a copy of the topics
        topics = list(self.topics)
        while len(topics) > 0:
            # Retrieve our topic
            topic = topics.pop()

            if attach and self.attachment_support:
                # We need to upload our payload first so that we can source it
                # in remaining messages
                for no, attachment in enumerate(attach):

                    # First message only includes the text (if defined)
                    _body = body if not no and body else None
                    _title = title if not no and title else None

                    # Perform some simple error checking
                    if not attachment:
                        # We could not access the attachment
                        self.logger.error(
                            'Could not access attachment {}.'.format(
                                attachment.url(privacy=True)))
                        return False

                    self.logger.debug(
                        'Preparing ntfy attachment {}'.format(
                            attachment.url(privacy=True)))

                    okay, response = self._send(
                        topic, body=_body, title=_title, image_url=image_url,
                        attach=attachment)
                    if not okay:
                        # We can't post our attachment; abort immediately
                        return False
            else:
                # Send our Notification Message
                okay, response = self._send(
                    topic, body=body, title=title, image_url=image_url)
                if not okay:
                    # Mark our failure, but contiue to move on
                    has_error = True

        return not has_error

    def _send(self, topic, body=None, title=None, attach=None, image_url=None,
              **kwargs):
        """
        Wrapper to the requests (post) object
        """

        # Prepare our headers
        headers = {
            'User-Agent': self.app_id,
        }

        # See https://ntfy.sh/docs/publish/#publish-as-json
        data = {}

        # Posting Parameters
        params = {}

        auth = None
        if self.mode == NtfyMode.CLOUD:
            # Cloud Service
            notify_url = self.cloud_notify_url

        else:  # NotifyNtfy.PRVATE
            # Allow more settings to be applied now
            if self.auth == NtfyAuth.BASIC and self.user:
                auth = (self.user, self.password)

            elif self.auth == NtfyAuth.TOKEN:
                if not self.token:
                    self.logger.warning('No Ntfy Token was specified')
                    return False, None

                # Set Token
                headers['Authorization'] = f'Bearer {self.token}'

            # Prepare our ntfy Template URL
            schema = 'https' if self.secure else 'http'

            notify_url = '%s://%s' % (schema, self.host)
            if isinstance(self.port, int):
                notify_url += ':%d' % self.port

        if not attach:
            headers['Content-Type'] = 'application/json'

            data['topic'] = topic
            virt_payload = data

            if self.attach:
                virt_payload['attach'] = self.attach

                if self.filename:
                    virt_payload['filename'] = self.filename

        else:
            # Point our payload to our parameters
            virt_payload = params
            notify_url += '/{topic}'.format(topic=topic)

            # Prepare our Header
            virt_payload['filename'] = attach.name

            with open(attach.path, 'rb') as fp:
                data = fp.read()

        if image_url:
            headers['X-Icon'] = image_url

        if title:
            virt_payload['title'] = title

        if body:
            virt_payload['message'] = body

        if self.notify_format == NotifyFormat.MARKDOWN:
            # Support Markdown
            headers['X-Markdown'] = 'yes'

        if self.priority != NtfyPriority.NORMAL:
            headers['X-Priority'] = self.priority

        if self.delay is not None:
            headers['X-Delay'] = self.delay

        if self.click is not None:
            headers['X-Click'] = self.click

        if self.email is not None:
            headers['X-Email'] = self.email

        if self.__tags:
            headers['X-Tags'] = ",".join(self.__tags)

        self.logger.debug('ntfy POST URL: %s (cert_verify=%r)' % (
            notify_url, self.verify_certificate,
        ))
        self.logger.debug('ntfy Payload: %s' % str(virt_payload))
        self.logger.debug('ntfy Headers: %s' % str(headers))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        # Default response type
        response = None

        if not attach:
            data = dumps(data)

        try:
            r = requests.post(
                notify_url,
                params=params if params else None,
                data=data,
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
                    response = loads(r.content)
                    status_str = response.get('error', status_str)
                    status_code = \
                        int(response.get('code', status_code))

                except (AttributeError, TypeError, ValueError):
                    # ValueError = r.content is Unparsable
                    # TypeError = r.content is None
                    # AttributeError = r is None

                    # We could not parse JSON response.
                    # We will just use the status we already have.
                    pass

                self.logger.warning(
                    "Failed to send ntfy notification to topic '{}': "
                    '{}{}error={}.'.format(
                        topic,
                        status_str,
                        ', ' if status_str else '',
                        status_code))

                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))

                return False, response

            # otherwise we were successful
            self.logger.info(
                "Sent ntfy notification to '{}'.".format(notify_url))

            return True, response

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred sending ntfy:%s ' % (
                    notify_url) + 'notification.'
            )
            self.logger.debug('Socket Exception: %s' % str(e))

        except (OSError, IOError) as e:
            self.logger.warning(
                'An I/O error occurred while handling {}.'.format(
                    attach.name if isinstance(attach, AttachBase)
                    else virt_payload))
            self.logger.debug('I/O Exception: %s' % str(e))

        return False, response

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        default_port = 443 if self.secure else 80

        params = {
            'priority': self.priority,
            'mode': self.mode,
            'image': 'yes' if self.include_image else 'no',
            'auth': self.auth,
        }

        if self.avatar_url:
            params['avatar_url'] = self.avatar_url

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
        if self.auth == NtfyAuth.BASIC:
            if self.user and self.password:
                auth = '{user}:{password}@'.format(
                    user=NotifyNtfy.quote(self.user, safe=''),
                    password=self.pprint(
                        self.password, privacy, mode=PrivacyMode.Secret,
                        safe=''),
                )
            elif self.user:
                auth = '{user}@'.format(
                    user=NotifyNtfy.quote(self.user, safe=''),
                )

        elif self.token:  # NtfyAuth.TOKEN also
            auth = '{token}@'.format(
                token=self.pprint(self.token, privacy, safe=''),
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

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """
        return 1 if not self.topics else len(self.topics)

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

        # Set our priority
        if 'priority' in results['qsd'] and len(results['qsd']['priority']):
            results['priority'] = \
                NotifyNtfy.unquote(results['qsd']['priority'])

        if 'attach' in results['qsd'] and len(results['qsd']['attach']):
            results['attach'] = NotifyNtfy.unquote(results['qsd']['attach'])
            _results = NotifyBase.parse_url(results['attach'])
            if _results:
                results['filename'] = \
                    None if _results['fullpath'] \
                    else basename(_results['fullpath'])

            if 'filename' in results['qsd'] and \
                    len(results['qsd']['filename']):
                results['filename'] = \
                    basename(NotifyNtfy.unquote(results['qsd']['filename']))

        if 'click' in results['qsd'] and len(results['qsd']['click']):
            results['click'] = NotifyNtfy.unquote(results['qsd']['click'])

        if 'delay' in results['qsd'] and len(results['qsd']['delay']):
            results['delay'] = NotifyNtfy.unquote(results['qsd']['delay'])

        if 'email' in results['qsd'] and len(results['qsd']['email']):
            results['email'] = NotifyNtfy.unquote(results['qsd']['email'])

        if 'tags' in results['qsd'] and len(results['qsd']['tags']):
            results['tags'] = \
                parse_list(NotifyNtfy.unquote(results['qsd']['tags']))

        # Boolean to include an image or not
        results['include_image'] = parse_bool(results['qsd'].get(
            'image', NotifyNtfy.template_args['image']['default']))

        # Extract avatar url if it was specified
        if 'avatar_url' in results['qsd']:
            results['avatar_url'] = \
                NotifyNtfy.unquote(results['qsd']['avatar_url'])

        # Acquire our targets/topics
        results['targets'] = NotifyNtfy.split_path(results['fullpath'])

        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyNtfy.parse_list(results['qsd']['to'])

        # Token Specified
        if 'token' in results['qsd'] and len(results['qsd']['token']):
            # Token presumed to be the one in use
            results['auth'] = NtfyAuth.TOKEN
            results['token'] = NotifyNtfy.unquote(results['qsd']['token'])

        # Auth override
        if 'auth' in results['qsd'] and results['qsd']['auth']:
            results['auth'] = NotifyNtfy.unquote(
                results['qsd']['auth'].strip().lower())

        if not results.get('auth') and results['user'] \
                and not results['password']:
            # We can try to detect the authentication type on the formatting of
            # the username. Look for tk_.*
            #
            # This isn't a surfire way to do things though; it's best to
            # specify the auth= flag
            results['auth'] = NtfyAuth.TOKEN \
                if NTFY_AUTH_DETECT_RE.match(results['user']) \
                else NtfyAuth.BASIC

        if results.get('auth') == NtfyAuth.TOKEN and not results.get('token'):
            if results['user'] and not results['password']:
                # Make sure we properly set our token
                results['token'] = NotifyNtfy.unquote(results['user'])

            elif results['password']:
                # Make sure we properly set our token
                results['token'] = NotifyNtfy.unquote(results['password'])

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
                if ((is_hostname(results['host'])
                    or is_ipaddr(results['host'])) and results['targets']) \
                else NtfyMode.CLOUD

        if results['mode'] == NtfyMode.CLOUD:
            # Store first entry as it can be a topic too in this case
            # But only if we also rule it out not being the words
            # ntfy.sh itself, something that starts wiht an non-alpha numeric
            # character:
            if not NotifyNtfy.__auto_cloud_host.search(results['host']):
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
            r'^(http|ntfy)s?://ntfy\.sh'
            r'(?P<topics>/[^?]+)?'
            r'(?P<params>\?.+)?$', url, re.I)

        if result:
            mode = 'mode=%s' % NtfyMode.CLOUD
            return NotifyNtfy.parse_url(
                '{schema}://{topics}{params}'.format(
                    schema=NotifyNtfy.secure_protocol,
                    topics=result.group('topics')
                    if result.group('topics') else '',
                    params='?%s' % mode
                    if not result.group('params')
                    else result.group('params') + '&%s' % mode))

        return None
