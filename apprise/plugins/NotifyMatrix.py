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

# Great sources
# - https://github.com/matrix-org/matrix-python-sdk
# - https://github.com/matrix-org/synapse/blob/master/docs/reverse_proxy.rst
#
import re
import six
import requests
from json import dumps
from json import loads

from .NotifyBase import NotifyBase
from ..common import NotifyType
from ..common import NotifyImageSize
from ..utils import parse_bool

# Define default path
MATRIX_V2_API_PATH = '/_matrix/client/r0'

# Extend HTTP Error Messages
MATRIX_HTTP_ERROR_MAP = {
    403: 'Unauthorized - Invalid Token.',
    429: 'Rate limit imposed; wait 2s and try again',
}

# Used to break apart list of potential tags by their delimiter
# into a usable list.
LIST_DELIM = re.compile(r'[ \t\r\n,\\/]+')

# Matrix Room Syntax
IS_ROOM_ALIAS = re.compile(
    r'^\s*(#|%23)?(?P<room>[a-z0-9-]+)((:|%3A)'
    r'(?P<home_server>[a-z0-9.-]+))?\s*$', re.I)

# Room ID MUST start with an exclamation to avoid ambiguity
IS_ROOM_ID = re.compile(
    r'^\s*(!|&#33;|%21)(?P<room>[a-z0-9-]+)((:|%3A)'
    r'(?P<home_server>[a-z0-9.-]+))?\s*$', re.I)


class NotifyMatrix(NotifyBase):
    """
    A wrapper for Matrix Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Matrix'

    # The services URL
    service_url = 'https://matrix.org/'

    # The default protocol
    protocol = 'matrix'

    # The default secure protocol
    secure_protocol = 'matrixs'

    # Define the default secure port to use
    default_secure_port = 8448

    # Define the default insecure port to use
    default_insecure_port = 8008

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_matrix'

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_32

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 1000

    # Throttle a wee-bit to avoid thrashing
    request_rate_per_sec = 0.5

    # How many retry attempts we'll make in the event the server asks us to
    # throttle back.
    default_retries = 2

    # The number of micro seconds to wait if we get a 429 error code and
    # the server doesn't remind us how long we shoul wait for
    default_wait_ms = 1000

    def __init__(self, rooms=None, thumbnail=True, **kwargs):
        """
        Initialize Matrix Object
        """
        super(NotifyMatrix, self).__init__(**kwargs)

        # Prepare a list of rooms to connect and notify
        if isinstance(rooms, six.string_types):
            self.rooms = [x for x in filter(bool, LIST_DELIM.split(
                rooms,
            ))]

        elif isinstance(rooms, (set, tuple, list)):
            self.rooms = rooms

        else:
            self.rooms = []

        # our home server gets populated after a login/registration
        self.home_server = None

        # our user_id gets populated after a login/registration
        self.user_id = None

        # This gets initialized after a login/registration
        self.access_token = None

        # Place a thumbnail image inline with the message body
        self.thumbnail = thumbnail

        # maintain a lookup of room alias's we already paired with their id
        # to speed up future requests
        self._room_cache = {}

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Matrix Notification
        """

        if self.access_token is None:
            # We need to register
            if not self._login():
                if not self._register():
                    return False

        if len(self.rooms) == 0:
            # Attempt to retrieve a list of already joined channels
            self.rooms = self._joined_rooms()

            if len(self.rooms) == 0:
                # Nothing to notify
                self.logger.warning(
                    'There were no Matrix rooms specified to notify.')
                return False

        # Create a copy of our rooms to join and message
        rooms = list(self.rooms)

        # Initiaize our error tracking
        has_error = False

        while len(rooms) > 0:

            # Get our room
            room = rooms.pop(0)

            # Get our room_id from our response
            room_id = self._room_join(room)
            if not room_id:
                # Notify our user about our failure
                self.logger.warning(
                    'Could not join Matrix room {}.'.format((room)))

                # Mark our failure
                has_error = True
                continue

            # We have our data cached at this point we can freely use it
            msg = '{title}{body}'.format(
                title='' if not title else '{}\r\n'.format(title),
                body=body)

            image_url = self.image_url(notify_type)
            if self.thumbnail and image_url:
                # Define our payload
                image_payload = {
                    'msgtype': 'm.image',
                    'url': image_url,
                    'body': '{}'.format(notify_type if not title else title),
                }
                # Build our path
                path = '/rooms/{}/send/m.room.message'.format(
                    NotifyBase.quote(room_id))

                # Post our content
                postokay, response = self._fetch(path, payload=image_payload)
                if not postokay:
                    # Mark our failure
                    has_error = True
                    continue

            # Define our payload
            payload = {
                'msgtype': 'm.text',
                'body': msg,
            }

            # Build our path
            path = '/rooms/{}/send/m.room.message'.format(
                NotifyBase.quote(room_id))

            # Post our content
            postokay, response = self._fetch(path, payload=payload)
            if not postokay:
                # Notify our user
                self.logger.warning(
                    'Could not send notification Matrix room {}.'.format(room))

                # Mark our failure
                has_error = True
                continue

        return not has_error

    def _register(self):
        """
        Register with the service if possible.
        """

        # Prepare our Registration Payload. This will only work if registration
        # is enabled for the public
        payload = {
            'kind': 'user',
            'auth': {'type': 'm.login.dummy'},
        }

        # parameters
        params = {
            'kind': 'user',
        }

        # If a user is not specified, one will be randomly generated for you.
        # If you do not specify a password, you will be unable to login to the
        # account if you forget the access_token.
        if self.user:
            payload['username'] = self.user

        if self.password:
            payload['password'] = self.password

        # Register
        postokay, response = \
            self._fetch('/register', payload=payload, params=params)
        if not postokay:
            # Failed to register
            return False

        # Pull the response details
        self.access_token = response.get('access_token')
        self.home_server = response.get('home_server')
        self.user_id = response.get('user_id')

        if self.access_token is not None:
            self.logger.debug(
                'Registered successfully with Matrix server.')
            return True

        return False

    def _login(self):
        """
        Acquires the matrix token required for making future requests. If we
        fail we return False, otherwise we return True
        """

        if self.access_token:
            # Login not required; silently skip-over
            return True

        if not (self.user and self.password):
            # It's not possible to register since we need these 2 values to
            # make the action possible.
            self.logger.warning(
                'Failed to login to Matrix server: '
                'user/pass combo is missing.')
            return False

        # Prepare our Registration Payload
        payload = {
            'type': 'm.login.password',
            'user': self.user,
            'password': self.password,
        }

        # Build our URL
        postokay, response = self._fetch('/login', payload=payload)
        if not postokay:
            # Failed to login
            return False

        # Pull the response details
        self.access_token = response.get('access_token')
        self.home_server = response.get('home_server')
        self.user_id = response.get('user_id')

        if not self.access_token:
            return False

        self.logger.debug(
            'Authenticated successfully with Matrix server.')
        return True

    def _logout(self):
        """
        Relinquishes token from remote server
        """

        if not self.access_token:
            # Login not required; silently skip-over
            return True

        # Prepare our Registration Payload
        payload = {}

        # Expire our token
        postokay, response = self._fetch('/logout', payload=payload)
        if not postokay:
            # If we get here, the token was declared as having already
            # been expired.  The response looks like this:
            # {
            #    u'errcode': u'M_UNKNOWN_TOKEN',
            #    u'error': u'Access Token unknown or expired',
            # }
            #
            # In this case it's okay to safely return True because
            # we're logged out in this case.
            if response.get('errcode') != u'M_UNKNOWN_TOKEN':
                return False

        # else: The response object looks like this if we were successful:
        #  {}

        # Pull the response details
        self.access_token = None
        self.home_server = None
        self.user_id = None

        # Clear our room cache
        self._room_cache = {}

        self.logger.debug(
            'Unauthenticated successfully with Matrix server.')

        return True

    def _room_join(self, room):
        """
        Joins a matrix room if we're not already in it. Otherwise it attempts
        to create it if it doesn't exist and always returns
        the room_id if it was successful, otherwise it returns None

        """

        if not self.access_token:
            # We can't join a room if we're not logged in
            return None

        if not isinstance(room, six.string_types):
            # Not a supported string
            return None

        # Prepare our Join Payload
        payload = {}

        # Not in cache, next step is to check if it's a room id...
        result = IS_ROOM_ID.match(room)
        if result:
            # We detected ourselves the home_server
            home_server = result.group('home_server') \
                if result.group('home_server') else self.home_server

            # It was a room ID; simple mapping:
            room_id = "!{}:{}".format(
                result.group('room'),
                home_server,
            )

            # Build our URL
            path = '/join/{}'.format(NotifyBase.quote(room_id))

            # Make our query
            postokay, _ = self._fetch(path, payload=payload)
            return room_id if postokay else None

        # Try to see if it's an alias then...
        result = IS_ROOM_ALIAS.match(room)
        if not result:
            # There is nothing else it could be
            self.logger.warning(
                'Ignoring illegally formed room {} '
                'from Matrix server list.'.format(room))
            return None

        # If we reach here, we're dealing with a channel alias
        home_server = self.home_server \
            if not result.group('home_server') \
            else result.group('home_server')

        # tidy our room (alias) identifier
        room = '#{}:{}'.format(result.group('room'), home_server)

        # Check our cache for speed:
        if room in self._room_cache:
            # We're done as we've already joined the channel
            return self._room_cache[room]['id']

        # If we reach here, we need to join the channel

        # Build our URL
        path = '/join/{}'.format(NotifyBase.quote(room))

        # Attempt to join the channel
        postokay, response = self._fetch(path, payload=payload)
        if postokay:
            # Cache our entry for fast access later
            self._room_cache[room] = {
                'id': response.get('room_id'),
                'home_server': home_server,
            }
            return self._room_cache[room]['id']

        # Try to create the channel
        return self._room_create(room)

    def _room_create(self, room):
        """
        Creates a matrix room and return it's room_id if successful
        otherwise None is returned.
        """
        if not self.access_token:
            # We can't create a room if we're not logged in
            return None

        if not isinstance(room, six.string_types):
            # Not a supported string
            return None

        # Build our room if we have to:
        result = IS_ROOM_ALIAS.match(room)
        if not result:
            # Illegally formed room
            return None

        # Our home_server
        home_server = result.group('home_server') \
            if result.group('home_server') else self.home_server

        # update our room details
        room = '#{}:{}'.format(result.group('room'), home_server)

        # Prepare our Create Payload
        payload = {
            'room_alias_name': result.group('room'),
            # Set our channel name
            'name': '#{} - {}'.format(result.group('room'), self.app_desc),
            # hide the room by default; let the user open it up if they wish
            # to others.
            'visibility': 'private',
            'preset': 'trusted_private_chat',
        }

        postokay, response = self._fetch('/createRoom', payload=payload)
        if not postokay:
            # Failed to create channel
            # Typical responses:
            #   - {u'errcode': u'M_ROOM_IN_USE',
            #      u'error': u'Room alias already taken'}
            #   - {u'errcode': u'M_UNKNOWN',
            #      u'error': u'Internal server error'}
            if (response and response.get('errcode') == 'M_ROOM_IN_USE'):
                return self._room_id(room)
            return None

        # Cache our entry for fast access later
        self._room_cache[response.get('room_alias')] = {
            'id': response.get('room_id'),
            'home_server': home_server,
        }

        return response.get('room_id')

    def _joined_rooms(self):
        """
        Returns a list of the current rooms the logged in user
        is a part of.
        """

        if not self.access_token:
            # No list is possible
            return list()

        postokay, response = self._fetch(
            '/joined_rooms', payload=None, fn=requests.get)
        if not postokay:
            # Failed to retrieve listings
            return list()

        # Return our list of rooms
        return response.get('joined_rooms', list())

    def _room_id(self, room):
        """Get room id from its alias.
        Args:
            room (str): The room alias name.

        Returns:
            returns the room id if it can, otherwise it returns None
        """

        if not self.access_token:
            # We can't get a room id if we're not logged in
            return None

        if not isinstance(room, six.string_types):
            # Not a supported string
            return None

        # Build our room if we have to:
        result = IS_ROOM_ALIAS.match(room)
        if not result:
            # Illegally formed room
            return None

        # Our home_server
        home_server = result.group('home_server') \
            if result.group('home_server') else self.home_server

        # update our room details
        room = '#{}:{}'.format(result.group('room'), home_server)

        # Make our request
        postokay, response = self._fetch(
            "/directory/room/{}".format(
                self.quote(room)), payload=None, fn=requests.get)

        if postokay:
            return response.get("room_id")

        return None

    def _fetch(self, path, payload=None, params=None, fn=requests.post):
        """
        Wrapper to request.post() to manage it's response better and make
        the send() function cleaner and easier to maintain.

        This function returns True if the _post was successful and False
        if it wasn't.
        """

        # Define our headers
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
        }

        if self.access_token is not None:
            headers["Authorization"] = 'Bearer %s' % self.access_token

        default_port = self.default_secure_port \
            if self.secure else self.default_insecure_port

        url = \
            '{schema}://{hostname}:{port}{matrix_api}{path}'.format(
                schema='https' if self.secure else 'http',
                hostname=self.host,
                port=default_port if self.port is None else self.port,
                matrix_api=MATRIX_V2_API_PATH,
                path=path)

        # Our response object
        response = {}

        # Define how many attempts we'll make if we get caught in a throttle
        # event
        retries = self.default_retries if self.default_retries > 0 else 1
        while retries > 0:

            # Decrement our throttle retry count
            retries -= 1

            self.logger.debug('Matrix POST URL: %s (cert_verify=%r)' % (
                url, self.verify_certificate,
            ))
            self.logger.debug('Matrix Payload: %s' % str(payload))

            try:
                r = requests.post(
                    url,
                    data=dumps(payload),
                    params=params,
                    headers=headers,
                    verify=self.verify_certificate,
                )

                response = loads(r.content)

                if r.status_code == 429:
                    wait = self.default_wait_ms / 1000
                    try:
                        wait = response['retry_after_ms'] / 1000

                    except KeyError:
                        try:
                            errordata = response['error']
                            wait = errordata['retry_after_ms'] / 1000
                        except KeyError:
                            pass

                    self.logger.warning(
                        'Matrix server requested we throttle back {}ms; '
                        'retries left {}.'.format(wait, retries))
                    self.logger.debug(
                        'Response Details:\r\n{}'.format(r.content))

                    # Throttle for specified wait
                    self.throttle(wait=wait)

                    # Try again
                    continue

                elif r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = \
                        NotifyBase.http_response_code_lookup(
                            r.status_code, MATRIX_HTTP_ERROR_MAP)

                    self.logger.warning(
                        'Failed to handshake with Matrix server: '
                        '{}{}error={}.'.format(
                            status_str,
                            ', ' if status_str else '',
                            r.status_code))

                    self.logger.debug(
                        'Response Details:\r\n{}'.format(r.content))

                    # Return; we're done
                    return (False, response)

            except ValueError:
                # This gets thrown if we can't parse our JSON Response
                self.logger.warning('Invalid response from Matrix server.')
                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))
                return (False, {})

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occured while registering with Matrix'
                    ' server.')
                self.logger.debug('Socket Exception: %s' % str(e))
                # Return; we're done
                return (False, response)

            return (True, response)

        # If we get here, we ran out of retries
        return (False, {})

    def __del__(self):
        """
        Ensure we relinquish our token
        """
        self._logout()

    def url(self):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any arguments set
        args = {
            'format': self.notify_format,
            'overflow': self.overflow_mode,
        }

        # Determine Authentication method
        auth = ''
        if self.user and self.password:
            auth = '{user}:{password}@'.format(
                user=self.quote(self.user, safe=''),
                password=self.quote(self.password, safe=''),
            )

        elif self.user:
            auth = '{user}@'.format(
                user=self.quote(self.user, safe=''),
            )

        default_port = self.default_secure_port \
            if self.secure else self.default_insecure_port

        return '{schema}://{auth}{hostname}{port}/{rooms}?{args}'.format(
            schema=self.secure_protocol if self.secure else self.protocol,
            auth=auth,
            hostname=self.host,
            port='' if self.port is None or self.port == default_port
                 else ':{}'.format(self.port),
            rooms=self.quote('/'.join(self.rooms)),
            args=self.urlencode(args),
        )

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to substantiate this object.

        """
        results = NotifyBase.parse_url(url)

        if not results:
            # We're done early as we couldn't load the results
            return results

        # Get our rooms
        results['rooms'] = [
            NotifyBase.unquote(x) for x in filter(bool, NotifyBase.split_path(
                results['fullpath']))][0:]

        # Use Thumbnail
        results['thumbnail'] = \
            parse_bool(results['qsd'].get('thumbnail', False))

        return results
