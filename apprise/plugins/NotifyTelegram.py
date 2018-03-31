# -*- coding: utf-8 -*-
#
# Telegram Notify Wrapper
#
# Copyright (C) 2017-2018 Chris Caron <lead2gold@gmail.com>
#
# This file is part of apprise.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.

# To use this plugin, you need to first access https://api.telegram.org
# You need to create a bot and acquire it's Token Identifier (bot_token)
#
# Basically you need to create a chat with a user called the 'BotFather'
# and type: /newbot
#
# Then follow through the wizard, it will provide you an api key
# that looks like this:123456789:alphanumeri_characters
#
# For each chat_id a bot joins will have a chat_id associated with it.
# You will need this value as well to send the notification.
#
# Log into the webpage version of the site if you like by accessing:
#    https://web.telegram.org
#
# You can't check out to see if your entry is working using:
#    https://api.telegram.org/botAPI_KEY/getMe
#
#    Pay attention to the word 'bot' that must be present infront of your
#    api key that the BotFather gave you.
#
#  For example, a url might look like this:
#    https://api.telegram.org/bot123456789:alphanumeri_characters/getMe
#
# Development API Reference::
#  - https://core.telegram.org/bots/api
import requests
import re

from os.path import basename

from json import loads
from json import dumps

from .NotifyBase import NotifyBase
from .NotifyBase import HTTP_ERROR_MAP
from ..common import NotifyImageSize
from ..utils import compat_is_basestring
from ..utils import parse_bool

TELEGRAM_IMAGE_XY = NotifyImageSize.XY_256

# Token required as part of the API request
# allow the word 'bot' infront
VALIDATE_BOT_TOKEN = re.compile(
    r'^(bot)?(?P<key>[0-9]+:[a-z0-9_-]+)/*$',
    re.IGNORECASE,
)

# Chat ID is required
# If the Chat ID is positive, then it's addressed to a single person
# If the Chat ID is negative, then it's targeting a group
IS_CHAT_ID_RE = re.compile(
    r'^(@*(?P<idno>-?[0-9]{1,32})|(?P<name>[a-z_-][a-z0-9_-]+))$',
    re.IGNORECASE,
)

# Used to break path apart into list of chat identifiers
CHAT_ID_LIST_DELIM = re.compile(r'[ \t\r\n,#\\/]+')


class NotifyTelegram(NotifyBase):
    """
    A wrapper for Telegram Notifications
    """

    # The default secure protocol
    secure_protocol = 'tgram'

    # Telegram uses the http protocol with JSON requests
    notify_url = 'https://api.telegram.org/bot'

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_256

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 4096

    def __init__(self, bot_token, chat_ids, detect_bot_owner=True,
                 include_image=True, **kwargs):
        """
        Initialize Telegram Object
        """
        super(NotifyTelegram, self).__init__(**kwargs)

        try:
            self.bot_token = bot_token.strip()

        except AttributeError:
            # Token was None
            self.logger.warning('No Bot Token was specified.')
            raise TypeError('No Bot Token was specified.')

        result = VALIDATE_BOT_TOKEN.match(self.bot_token)
        if not result:
            raise TypeError(
                'The Bot Token specified (%s) is invalid.' % bot_token,
            )

        # Store our Bot Token
        self.bot_token = result.group('key')

        if compat_is_basestring(chat_ids):
            self.chat_ids = [x for x in filter(bool, CHAT_ID_LIST_DELIM.split(
                chat_ids,
            ))]

        elif isinstance(chat_ids, (set, tuple, list)):
            self.chat_ids = list(chat_ids)

        else:
            self.chat_ids = list()

        if self.user:
            # Treat this as a channel too
            self.chat_ids.append(self.user)

        if len(self.chat_ids) == 0 and detect_bot_owner:
            _id = self.detect_bot_owner()
            if _id:
                # Store our id
                self.chat_ids = [str(_id)]

        if len(self.chat_ids) == 0:
            self.logger.warning('No chat_id(s) were specified.')
            raise TypeError('No chat_id(s) were specified.')

        # Track whether or not we want to send an image with our notification
        # or not.
        self.include_image = include_image

    def send_image(self, chat_id, notify_type):
        """
        Sends a sticker based on the specified notify type

        """

        # The URL; we do not set headers because the api doesn't seem to like
        # when we set one.
        url = '%s%s/%s' % (
            self.notify_url,
            self.bot_token,
            'sendPhoto'
        )

        path = self.image_path(notify_type)
        if not path:
            # No image to send
            self.logger.debug(
                'Telegram Image does not exist for %s' % (
                    notify_type))
            return None

        files = {'photo': (basename(path), open(path), 'rb')}

        payload = {
            'chat_id': chat_id,
        }

        self.logger.debug(
            'Telegram Image POST URL: %s (cert_verify=%r)' % (
                url, self.verify_certificate))

        try:
            r = requests.post(
                url,
                files=files,
                data=payload,
                verify=self.verify_certificate,
            )

            if r.status_code != requests.codes.ok:
                # We had a problem
                try:
                    self.logger.warning(
                        'Failed to post Telegram Image: '
                        '%s (error=%s).' % (
                            HTTP_ERROR_MAP[r.status_code],
                            r.status_code))

                except KeyError:
                    self.logger.warning(
                        'Failed to detect Telegram Image. (error=%s).' % (
                            r.status_code))

                # self.logger.debug('Response Details: %s' % r.raw.read())
                return False

        except requests.RequestException as e:
            self.logger.warning(
                'A connection error occured posting Telegram Image.')
            self.logger.debug('Socket Exception: %s' % str(e))
            return False

        return True

    def detect_bot_owner(self):
        """
        Takes a bot and attempts to detect it's chat id from that

        """

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
        }

        url = '%s%s/%s' % (
            self.notify_url,
            self.bot_token,
            'getUpdates'
        )

        self.logger.debug(
            'Telegram User Detection POST URL: %s (cert_verify=%r)' % (
                url, self.verify_certificate))

        try:
            r = requests.post(
                url,
                headers=headers,
                verify=self.verify_certificate,
            )

            if r.status_code != requests.codes.ok:
                # We had a problem

                try:
                    # Try to get the error message if we can:
                    error_msg = loads(r.content)['description']

                except:
                    error_msg = None

                try:
                    if error_msg:
                        self.logger.warning(
                            'Failed to detect Telegram user: (%s) %s.' % (
                                r.status_code, error_msg))

                    else:
                        self.logger.warning(
                            'Failed to detect Telegram user: '
                            '%s (error=%s).' % (
                                HTTP_ERROR_MAP[r.status_code],
                                r.status_code))

                except KeyError:
                    self.logger.warning(
                        'Failed to detect Telegram user. (error=%s).' % (
                            r.status_code))

                # self.logger.debug('Response Details: %s' % r.raw.read())
                return 0

        except requests.RequestException as e:
            self.logger.warning(
                'A connection error occured detecting Telegram User.')
            self.logger.debug('Socket Exception: %s' % str(e))
            return 0

        # A Response might look something like this:
        # {
        #    "ok":true,
        #    "result":[{
        #      "update_id":645421321,
        #      "message":{
        #        "message_id":1,
        #        "from":{
        #          "id":532389719,
        #          "is_bot":false,
        #          "first_name":"Chris",
        #          "language_code":"en-US"
        #        },
        #      "chat":{
        #        "id":532389719,
        #        "first_name":"Chris",
        #        "type":"private"
        #      },
        #      "date":1519694394,
        #      "text":"/start",
        #      "entities":[{"offset":0,"length":6,"type":"bot_command"}]}}]

        # Load our response and attempt to fetch our userid
        response = loads(r.content)
        if 'ok' in response and response['ok'] is True:
            start = re.compile('^\s*\/start', re.I)
            for _msg in iter(response['result']):
                # Find /start
                if not start.search(_msg['message']['text']):
                    continue

                _id = _msg['message']['from'].get('id', 0)
                _user = _msg['message']['from'].get('first_name')
                self.logger.info('Detected telegram user %s (userid=%d)' % (
                    _user, _id))
                # Return our detected userid
                return _id

            self.logger.warning(
                'Could not detect bot owner. Is it running (/start)?')

        return 0

    def notify(self, title, body, notify_type, **kwargs):
        """
        Perform Telegram Notification
        """

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
        }

        # error tracking (used for function return)
        has_error = False

        url = '%s%s/%s' % (
            self.notify_url,
            self.bot_token,
            'sendMessage'
        )

        payload = {}

        # HTML Spaces (&nbsp;) and tabs (&emsp;) aren't supported
        # See https://core.telegram.org/bots/api#html-style
        title = re.sub('&nbsp;?', ' ', title, re.I)
        body = re.sub('&nbsp;?', ' ', body, re.I)
        # Tabs become 3 spaces
        title = re.sub('&emsp;?', '   ', title, re.I)
        body = re.sub('&emsp;?', '   ', body, re.I)

        # HTML
        title = NotifyBase.escape_html(title, whitespace=False)
        body = NotifyBase.escape_html(body, whitespace=False)

        payload['parse_mode'] = 'HTML'

        payload['text'] = '<b>%s</b>\r\n%s' % (
            title,
            body,
        )

        # Create a copy of the chat_ids list
        chat_ids = list(self.chat_ids)
        while len(chat_ids):
            chat_id = chat_ids.pop(0)
            chat_id = IS_CHAT_ID_RE.match(chat_id)
            if not chat_id:
                self.logger.warning(
                    "The specified chat_id '%s' is invalid; skipping." % (
                        chat_id,
                    )
                )
                has_error = True
                continue

            if chat_id.group('name') is not None:
                # Name
                payload['chat_id'] = '@%s' % chat_id.group('name')

            else:
                # ID
                payload['chat_id'] = int(chat_id.group('idno'))

            if self.include_image is True:
                # Send an image
                if self.send_image(
                        payload['chat_id'], notify_type) is not None:
                    # We sent a post (whether we were successful or not)
                    # we still hit the remote server... just throttle
                    # before our next hit server query
                    self.throttle()

            self.logger.debug('Telegram POST URL: %s (cert_verify=%r)' % (
                url, self.verify_certificate,
            ))
            self.logger.debug('Telegram Payload: %s' % str(payload))

            try:
                r = requests.post(
                    url,
                    data=dumps(payload),
                    headers=headers,
                    verify=self.verify_certificate,
                )

                if r.status_code != requests.codes.ok:
                    # We had a problem

                    try:
                        # Try to get the error message if we can:
                        error_msg = loads(r.content)['description']

                    except:
                        error_msg = None

                    try:
                        if error_msg:
                            self.logger.warning(
                                'Failed to send Telegram:%s '
                                'notification: (%s) %s.' % (
                                    payload['chat_id'],
                                    r.status_code, error_msg))

                        else:
                            self.logger.warning(
                                'Failed to send Telegram:%s '
                                'notification: %s (error=%s).' % (
                                    payload['chat_id'],
                                    HTTP_ERROR_MAP[r.status_code],
                                    r.status_code))

                    except KeyError:
                        self.logger.warning(
                            'Failed to send Telegram:%s '
                            'notification (error=%s).' % (
                                payload['chat_id'], r.status_code))

                    # self.logger.debug('Response Details: %s' % r.raw.read())

                    # Flag our error
                    has_error = True

                else:
                    self.logger.info('Sent Telegram notification.')

            except requests.RequestException as e:
                self.logger.warning(
                    'A connection error occured sending Telegram:%s ' % (
                        payload['chat_id']) + 'notification.'
                )
                self.logger.debug('Socket Exception: %s' % str(e))
                has_error = True

            finally:
                if len(chat_ids):
                    # Prevent thrashing requests
                    self.throttle()

        return not has_error

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to substantiate this object.

        """
        # This is a dirty hack; but it's the only work around to
        # tgram:// messages since the bot_token has a colon in it.
        # It invalidates an normal URL.

        # This hack searches for this bogus URL and corrects it
        # so we can properly load it further down. The other
        # alternative is to ask users to actually change the colon
        # into a slash (which will work too), but it's more likely
        # to cause confusion... So this is the next best thing
        try:
            tgram = re.match(
                r'(?P<protocol>%s://)(bot)?(?P<prefix>([a-z0-9_-]+)'
                r'(:[a-z0-9_-]+)?@)?(?P<btoken_a>[0-9]+):+'
                r'(?P<remaining>.*)$' % NotifyTelegram.secure_protocol,
                url, re.I)

        except (TypeError, AttributeError):
            # url is bad; force tgram to be None
            tgram = None

        if not tgram:
            # Content is simply not parseable
            return None

        if tgram.group('prefix'):
            # Try again
            results = NotifyBase.parse_url(
                '%s%s%s/%s' % (
                    tgram.group('protocol'),
                    tgram.group('prefix'),
                    tgram.group('btoken_a'),
                    tgram.group('remaining'),
                ),
            )

        else:
            # Try again
            results = NotifyBase.parse_url(
                '%s%s/%s' % (
                    tgram.group('protocol'),
                    tgram.group('btoken_a'),
                    tgram.group('remaining'),
                ),
            )

        # The first token is stored in the hostname
        bot_token_a = results['host']

        # Now fetch the remaining tokens
        bot_token_b = [x for x in filter(
            bool, NotifyBase.split_path(results['fullpath']))][0]

        bot_token = '%s:%s' % (bot_token_a, bot_token_b)

        chat_ids = ','.join(
            [x for x in filter(
                bool, NotifyBase.split_path(results['fullpath']))][1:])

        # Store our bot token
        results['bot_token'] = bot_token

        # Store our chat ids
        results['chat_ids'] = chat_ids

        # Include images with our message
        results['include_image'] = \
            parse_bool(results['qsd'].get('image', False))

        return results
