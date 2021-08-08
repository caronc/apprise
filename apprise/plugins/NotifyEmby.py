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

# For this plugin to work correct, the Emby server must be set up to allow
# for remote connections.

# Emby Docker configuration: https://hub.docker.com/r/emby/embyserver/
# Authentication: https://github.com/MediaBrowser/Emby/wiki/Authentication
# Notifications: https://github.com/MediaBrowser/Emby/wiki/Remote-control
import requests
import hashlib
from json import dumps
from json import loads

from .NotifyBase import NotifyBase
from ..URLBase import PrivacyMode
from ..utils import parse_bool
from ..common import NotifyType
from .. import __version__ as VERSION
from ..AppriseLocale import gettext_lazy as _


class NotifyEmby(NotifyBase):
    """
    A wrapper for Emby Notifications
    """
    # The default descriptive name associated with the Notification
    service_name = 'Emby'

    # The services URL
    service_url = 'https://emby.media/'

    # The default protocol
    protocol = 'emby'

    # The default secure protocol
    secure_protocol = 'embys'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_emby'

    # By default Emby requires you to provide it a device id
    # The following was just a random uuid4 generated one.  There
    # is no real reason to change this, but hey; that's what open
    # source is for right?
    emby_device_id = '48df9504-6843-49be-9f2d-a685e25a0bc8'

    # The Emby message timeout; basically it is how long should our message be
    # displayed for.  The value is in milli-seconds
    emby_message_timeout_ms = 60000

    # Define object templates
    templates = (
        '{schema}://{host}',
        '{schema}://{host}:{port}',
        '{schema}://{user}:{password}@{host}',
        '{schema}://{user}:{password}@{host}:{port}',
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
            'default': 8096
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

    template_args = dict(NotifyBase.template_args, **{
        'modal': {
            'name': _('Modal'),
            'type': 'bool',
            'default': False,
        },
    })

    def __init__(self, modal=False, **kwargs):
        """
        Initialize Emby Object

        """
        super(NotifyEmby, self).__init__(**kwargs)

        if self.secure:
            self.schema = 'https'

        else:
            self.schema = 'http'

        # Our access token does not get created until we first
        # authenticate with our Emby server. The same goes for the
        # user id below.
        self.access_token = None
        self.user_id = None

        # Whether or not our popup dialog is a timed notification
        # or a modal type box (requires an Okay acknowledgement)
        self.modal = modal

        if not self.port:
            # Assign default port if one isn't otherwise specified:
            self.port = self.template_tokens['port']['default']

        if not self.user:
            # User was not specified
            msg = 'No Emby username was specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        return

    def login(self, **kwargs):
        """
        Creates our authentication token and prepares our header

        """

        if self.is_authenticated:
            # Log out first before we log back in
            self.logout()

        # Prepare our login url
        url = '%s://%s' % (self.schema, self.host)
        if self.port:
            url += ':%d' % self.port

        url += '/Users/AuthenticateByName'

        # Initialize our payload
        payload = {
            'Username': self.user
        }

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
            'X-Emby-Authorization': self.emby_auth_header,
        }

        if self.password:
            # Source: https://github.com/MediaBrowser/Emby/wiki/Authentication
            # We require the following during our authentication
            #    pw - password in plain text
            #    password - password in Sha1
            #    passwordMd5 - password in MD5
            payload['pw'] = self.password

            password_md5 = hashlib.md5()
            password_md5.update(self.password.encode('utf-8'))
            payload['passwordMd5'] = password_md5.hexdigest()

            password_sha1 = hashlib.sha1()
            password_sha1.update(self.password.encode('utf-8'))
            payload['password'] = password_sha1.hexdigest()

        else:
            # Backwards compatibility
            payload['password'] = ''
            payload['passwordMd5'] = ''

            # April 1st, 2018 and newer requirement:
            payload['pw'] = ''

        self.logger.debug(
            'Emby login() POST URL: %s (cert_verify=%r)' % (
                url, self.verify_certificate))

        try:
            r = requests.post(
                url,
                headers=headers,
                data=dumps(payload),
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )

            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyEmby.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to authenticate Emby user {} details: '
                    '{}{}error={}.'.format(
                        self.user,
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return False

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred authenticating a user with Emby '
                'at %s.' % self.host)
            self.logger.debug('Socket Exception: %s' % str(e))

            # Return; we're done
            return False

        # Load our results
        try:
            results = loads(r.content)

        except (AttributeError, TypeError, ValueError):
            # ValueError = r.content is Unparsable
            # TypeError = r.content is None
            # AttributeError = r is None

            # This is a problem; abort
            return False

        # Acquire our Access Token
        self.access_token = results.get('AccessToken')

        # Acquire our UserId. It can be in one (or both) of the
        # following locations in the response:
        #   {
        #      'User': {
        #         ...
        #         'Id': 'the_user_id_can_be_here',
        #         ...
        #       },
        #      'Id': 'the_user_id_can_be_found_here_too',
        #   }
        #
        # The below just safely covers both grounds.
        self.user_id = results.get('Id')
        if not self.user_id:
            if 'User' in results:
                self.user_id = results['User'].get('Id')

        # No user was found matching the specified
        return self.is_authenticated

    def sessions(self, user_controlled=True):
        """
        Acquire our Session Identifiers and store them in a dictionary
        indexed by the session id itself.

        """
        # A single session might look like this:
        # {
        #    u'AdditionalUsers': [],
        #    u'ApplicationVersion': u'3.3.1.0',
        #    u'Client': u'Emby Mobile',
        #    u'DeviceId': u'00c901e90ae814c00f81c75ae06a1c8a4381f45b',
        #    u'DeviceName': u'Firefox',
        #    u'Id': u'e37151ea06d7eb636639fded5a80f223',
        #    u'LastActivityDate': u'2018-03-04T21:29:02.5590200Z',
        #    u'PlayState': {
        #       u'CanSeek': False,
        #       u'IsMuted': False,
        #       u'IsPaused': False,
        #       u'RepeatMode': u'RepeatNone',
        #    },
        #    u'PlayableMediaTypes': [u'Audio', u'Video'],
        #    u'RemoteEndPoint': u'172.17.0.1',
        #    u'ServerId': u'4470e977ea704a08b264628c24127d43',
        #    u'SupportedCommands': [
        #       u'MoveUp',
        #       u'MoveDown',
        #       u'MoveLeft',
        #       u'MoveRight',
        #       u'PageUp',
        #       u'PageDown',
        #       u'PreviousLetter',
        #       u'NextLetter',
        #       u'ToggleOsd',
        #       u'ToggleContextMenu',
        #       u'Select',
        #       u'Back',
        #       u'SendKey',
        #       u'SendString',
        #       u'GoHome',
        #       u'GoToSettings',
        #       u'VolumeUp',
        #       u'VolumeDown',
        #       u'Mute',
        #       u'Unmute',
        #       u'ToggleMute',
        #       u'SetVolume',
        #       u'SetAudioStreamIndex',
        #       u'SetSubtitleStreamIndex',
        #       u'DisplayContent',
        #       u'GoToSearch',
        #       u'DisplayMessage',
        #       u'SetRepeatMode',
        #       u'ChannelUp',
        #       u'ChannelDown',
        #       u'PlayMediaSource',
        #    ],
        #    u'SupportsRemoteControl': True,
        #    u'UserId': u'6f98d12cb10f48209ee282787daf7af6',
        #    u'UserName': u'l2g'
        #    }

        # Prepare a dict() object to control our sessions; the keys are
        # the sessions while the details associated with the session
        # are stored inside.
        sessions = dict()

        if not self.is_authenticated and not self.login():
            # Authenticate if we aren't already
            return sessions

        # Prepare our login url
        url = '%s://%s' % (self.schema, self.host)
        if self.port:
            url += ':%d' % self.port

        url += '/Sessions'

        if user_controlled is True:
            # Only return sessions that can be managed by the current Emby
            # user.
            url += '?ControllableByUserId=%s' % self.user_id

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
            'X-Emby-Authorization': self.emby_auth_header,
            'X-MediaBrowser-Token': self.access_token,
        }

        self.logger.debug(
            'Emby session() GET URL: %s (cert_verify=%r)' % (
                url, self.verify_certificate))

        try:
            r = requests.get(
                url,
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )

            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyEmby.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to acquire Emby session for user {}: '
                    '{}{}error={}.'.format(
                        self.user,
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return sessions

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred querying Emby '
                'for session information at %s.' % self.host)
            self.logger.debug('Socket Exception: %s' % str(e))

            # Return; we're done
            return sessions

        # Load our results
        try:
            results = loads(r.content)

        except (AttributeError, TypeError, ValueError):
            # ValueError = r.content is Unparsable
            # TypeError = r.content is None
            # AttributeError = r is None

            # We need to abort at this point
            return sessions

        for entry in results:
            session = entry.get('Id')
            if session:
                sessions[session] = entry

        return sessions

    def logout(self, **kwargs):
        """
        Logs out of an already-authenticated session

        """
        if not self.is_authenticated:
            # We're not authenticated; there is nothing to do
            return True

        # Prepare our login url
        url = '%s://%s' % (self.schema, self.host)
        if self.port:
            url += ':%d' % self.port

        url += '/Sessions/Logout'

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
            'X-Emby-Authorization': self.emby_auth_header,
            'X-MediaBrowser-Token': self.access_token,
        }

        self.logger.debug(
            'Emby logout() POST URL: %s (cert_verify=%r)' % (
                url, self.verify_certificate))
        try:
            r = requests.post(
                url,
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )

            if r.status_code not in (
                    # We're already logged out
                    requests.codes.unauthorized,
                    # The below show up if we were 'just' logged out
                    requests.codes.ok,
                    requests.codes.no_content):

                # We had a problem
                status_str = \
                    NotifyEmby.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to logoff Emby user {}: '
                    '{}{}error={}.'.format(
                        self.user,
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return False

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred querying Emby '
                'to logoff user %s at %s.' % (self.user, self.host))
            self.logger.debug('Socket Exception: %s' % str(e))

            # Return; we're done
            return False

        # We logged our successfully if we reached here

        # Reset our variables
        self.access_token = None
        self.user_id = None
        return True

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Emby Notification
        """
        if not self.is_authenticated and not self.login():
            # Authenticate if we aren't already
            return False

        # Acquire our list of sessions
        sessions = self.sessions().keys()
        if not sessions:
            self.logger.warning('There were no Emby sessions to notify.')
            # We don't need to fail; there really is no one to notify
            return True

        url = '%s://%s' % (self.schema, self.host)
        if self.port:
            url += ':%d' % self.port

        # Append our remaining path
        url += '/Sessions/%s/Message'

        # Prepare Emby Object
        payload = {
            'Header': title,
            'Text': body,
        }

        if not self.modal:
            payload['TimeoutMs'] = self.emby_message_timeout_ms

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
            'X-Emby-Authorization': self.emby_auth_header,
            'X-MediaBrowser-Token': self.access_token,
        }

        # Track whether or not we had a failure or not.
        has_error = False

        for session in sessions:
            # Update our session
            session_url = url % session

            self.logger.debug('Emby POST URL: %s (cert_verify=%r)' % (
                session_url, self.verify_certificate,
            ))
            self.logger.debug('Emby Payload: %s' % str(payload))

            # Always call throttle before the requests are made
            self.throttle()

            try:
                r = requests.post(
                    session_url,
                    data=dumps(payload),
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )
                if r.status_code not in (
                        requests.codes.ok,
                        requests.codes.no_content):
                    # We had a problem
                    status_str = \
                        NotifyEmby.http_response_code_lookup(r.status_code)

                    self.logger.warning(
                        'Failed to send Emby notification: '
                        '{}{}error={}.'.format(
                            status_str,
                            ', ' if status_str else '',
                            r.status_code))

                    self.logger.debug(
                        'Response Details:\r\n{}'.format(r.content))

                    # Mark our failure
                    has_error = True
                    continue

                else:
                    self.logger.info('Sent Emby notification.')

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occurred sending Emby '
                    'notification to %s.' % self.host)
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
            'modal': 'yes' if self.modal else 'no',
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Determine Authentication
        auth = ''
        if self.user and self.password:
            auth = '{user}:{password}@'.format(
                user=NotifyEmby.quote(self.user, safe=''),
                password=self.pprint(
                    self.password, privacy, mode=PrivacyMode.Secret, safe=''),
            )
        else:  # self.user is set
            auth = '{user}@'.format(
                user=NotifyEmby.quote(self.user, safe=''),
            )

        return '{schema}://{auth}{hostname}{port}/?{params}'.format(
            schema=self.secure_protocol if self.secure else self.protocol,
            auth=auth,
            hostname=self.host,
            port='' if self.port is None
                 or self.port == self.template_tokens['port']['default']
                 else ':{}'.format(self.port),
            params=NotifyEmby.urlencode(params),
        )

    @property
    def is_authenticated(self):
        """
        Returns True if we're authenticated and False if not.

        """
        return True if self.access_token and self.user_id else False

    @property
    def emby_auth_header(self):
        """
        Generates the X-Emby-Authorization header response based on whether
        we're authenticated or not.

        """
        # Specific to Emby
        header_args = [
            ('MediaBrowser Client', self.app_id),
            ('Device', self.app_id),
            ('DeviceId', self.emby_device_id),
            ('Version', str(VERSION)),
        ]

        if self.user_id:
            # Append UserId variable if we're authenticated
            header_args.append(('UserId', self.user))

        return ', '.join(['%s="%s"' % (k, v) for k, v in header_args])

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to re-instantiate this object.

        """
        results = NotifyBase.parse_url(url)
        if not results:
            # We're done early
            return results

        # Modal type popup (default False)
        results['modal'] = parse_bool(results['qsd'].get('modal', False))

        return results

    def __del__(self):
        """
        Deconstructor
        """
        try:
            self.logout()

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
            # ticket system as unresolved and has provided work-arounds
            #   - https://github.com/kennethreitz/requests/issues/3578
            pass

        except ImportError:  # pragma: no cover
            # The actual exception is `ModuleNotFoundError` however ImportError
            # grants us backwards compatiblity with versions of Python older
            # than v3.6

            # Python code that makes early calls to sys.exit() can cause
            # the __del__() code to run. However in some newer versions of
            # Python, this causes the `sys` library to no longer be
            # available. The stack overflow also goes on to suggest that
            # it's not wise to use the __del__() as a deconstructor
            # which is the case here.

            # https://stackoverflow.com/questions/67218341/\
            #       modulenotfounderror-import-of-time-halted-none-in-sys-\
            #           modules-occured-when-obj?noredirect=1&lq=1
            #
            #
            # Also see: https://stackoverflow.com/questions\
            #       /1481488/what-is-the-del-method-and-how-do-i-call-it

            # At this time it seems clean to try to log out (if we can)
            # but not throw any unessisary exceptions (like this one) to
            # the end user if we don't have to.
            pass
