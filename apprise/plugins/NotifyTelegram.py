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
from ..common import NotifyType
from ..common import NotifyImageSize
from ..common import NotifyFormat
from ..utils import parse_bool
from ..utils import parse_list

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


class NotifyTelegram(NotifyBase):
    """
    A wrapper for Telegram Notifications
    """
    # The default descriptive name associated with the Notification
    service_name = 'Telegram'

    # The services URL
    service_url = 'https://telegram.org/'

    # The default secure protocol
    secure_protocol = 'tgram'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_telegram'

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
            err = 'No Bot Token was specified.'
            self.logger.warning(err)
            raise TypeError(err)

        result = VALIDATE_BOT_TOKEN.match(self.bot_token)
        if not result:
            err = 'The Bot Token specified (%s) is invalid.' % bot_token
            self.logger.warning(err)
            raise TypeError(err)

        # Store our Bot Token
        self.bot_token = result.group('key')

        # Parse our list
        self.chat_ids = parse_list(chat_ids)

        if self.user:
            # Treat this as a channel too
            self.chat_ids.append(self.user)

        if len(self.chat_ids) == 0 and detect_bot_owner:
            _id = self.detect_bot_owner()
            if _id:
                # Store our id
                self.chat_ids.append(str(_id))

        if len(self.chat_ids) == 0:
            err = 'No chat_id(s) were specified.'
            self.logger.warning(err)
            raise TypeError(err)

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
                'Telegram Image does not exist for %s' % (notify_type))
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
                status_str = \
                    NotifyBase.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send Telegram Image: '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

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
                status_str = \
                    NotifyBase.http_response_code_lookup(r.status_code)

                try:
                    # Try to get the error message if we can:
                    error_msg = loads(r.content)['description']

                except Exception:
                    error_msg = None

                if error_msg:
                    self.logger.warning(
                        'Failed to detect the Telegram user: (%s) %s.' % (
                            r.status_code, error_msg))

                else:
                    self.logger.warning(
                        'Failed to detect the Telegram user: '
                        '{}{}error={}.'.format(
                            status_str,
                            ', ' if status_str else '',
                            r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                return 0

        except requests.RequestException as e:
            self.logger.warning(
                'A connection error occured detecting the Telegram User.')
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
            start = re.compile(r'^\s*\/start', re.I)
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

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
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

        # Prepare Email Message
        if self.notify_format == NotifyFormat.MARKDOWN:
            payload['parse_mode'] = 'MARKDOWN'

        else:
            # Either TEXT or HTML; if TEXT we'll make it HTML
            payload['parse_mode'] = 'HTML'

            # HTML Spaces (&nbsp;) and tabs (&emsp;) aren't supported
            # See https://core.telegram.org/bots/api#html-style
            body = re.sub('&nbsp;?', ' ', body, re.I)

            # Tabs become 3 spaces
            body = re.sub('&emsp;?', '   ', body, re.I)

            if title:
                # HTML Spaces (&nbsp;) and tabs (&emsp;) aren't supported
                # See https://core.telegram.org/bots/api#html-style
                title = re.sub('&nbsp;?', ' ', title, re.I)

                # Tabs become 3 spaces
                title = re.sub('&emsp;?', '   ', title, re.I)

                # HTML
                title = NotifyBase.escape_html(title, whitespace=False)

            # HTML
            body = NotifyBase.escape_html(body, whitespace=False)

        if title and self.notify_format == NotifyFormat.TEXT:
            # Text HTML Formatting
            payload['text'] = '<b>%s</b>\r\n%s' % (
                title,
                body,
            )

        elif title:
            # Already HTML; trust developer has wrapped
            # the title appropriately
            payload['text'] = '%s\r\n%s' % (
                title,
                body,
            )

        else:
            # Assign the body
            payload['text'] = body

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

                # Flag our error
                has_error = True
                continue

            if chat_id.group('name') is not None:
                # Name
                payload['chat_id'] = '@%s' % chat_id.group('name')

            else:
                # ID
                payload['chat_id'] = int(chat_id.group('idno'))

            # Always call throttle before any remote server i/o is made;
            # Telegram throttles to occur before sending the image so that
            # content can arrive together.
            self.throttle()

            if self.include_image is True:
                # Send an image
                self.send_image(payload['chat_id'], notify_type)

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
                    status_str = \
                        NotifyBase.http_response_code_lookup(r.status_code)

                    try:
                        # Try to get the error message if we can:
                        error_msg = loads(r.content)['description']

                    except Exception:
                        error_msg = None

                    self.logger.warning(
                        'Failed to send Telegram notification to {}: '
                        '{}, error={}.'.format(
                            payload['chat_id'],
                            error_msg if error_msg else status_str,
                            r.status_code))

                    self.logger.debug(
                        'Response Details:\r\n{}'.format(r.content))

                    # Flag our error
                    has_error = True
                    continue

                else:
                    self.logger.info('Sent Telegram notification.')

            except requests.RequestException as e:
                self.logger.warning(
                    'A connection error occured sending Telegram:%s ' % (
                        payload['chat_id']) + 'notification.'
                )
                self.logger.debug('Socket Exception: %s' % str(e))

                # Flag our error
                has_error = True
                continue

        return not has_error

    def url(self):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any arguments set
        args = {
            'format': self.notify_format,
            'overflow': self.overflow_mode,
        }

        # No need to check the user token because the user automatically gets
        # appended into the list of chat ids
        return '{schema}://{bot_token}/{targets}/?{args}'.format(
            schema=self.secure_protocol,
            bot_token=self.quote(self.bot_token, safe=''),
            targets='/'.join(
                [self.quote('@{}'.format(x)) for x in self.chat_ids]),
            args=self.urlencode(args))

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to substantiate this object.

        """
        # This is a dirty hack; but it's the only work around to
        # tgram:// messages since the bot_token has a colon in it.
        # It invalidates an normal URL.

        # This hack searches for this bogus URL and corrects it so we can
        # properly load it further down. The other alternative is to ask users
        # to actually change the colon into a slash (which will work too), but
        # it's more likely to cause confusion... So this is the next best thing
        # we also check for %3A (incase the URL is encoded) as %3A == :
        try:
            tgram = re.match(
                r'(?P<protocol>{schema}://)(bot)?(?P<prefix>([a-z0-9_-]+)'
                r'(:[a-z0-9_-]+)?@)?(?P<btoken_a>[0-9]+)(:|%3A)+'
                r'(?P<remaining>.*)$'.format(
                    schema=NotifyTelegram.secure_protocol), url, re.I)

        except (TypeError, AttributeError):
            # url is bad; force tgram to be None
            tgram = None

        if not tgram:
            # Content is simply not parseable
            return None

        if tgram.group('prefix'):
            # Try again
            results = NotifyBase.parse_url('%s%s%s/%s' % (
                tgram.group('protocol'),
                tgram.group('prefix'),
                tgram.group('btoken_a'),
                tgram.group('remaining')))

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

        chat_ids = [x for x in filter(
            bool, NotifyBase.split_path(results['fullpath']))][1:]

        # Store our bot token
        results['bot_token'] = bot_token

        # Store our chat ids
        results['chat_ids'] = chat_ids

        # Include images with our message
        results['include_image'] = \
            parse_bool(results['qsd'].get('image', False))

        return results
