# -*- coding: utf-8 -*-
#
# Apprise - Push Notification Library.
# Copyright (C) 2023  Chris Caron <lead2gold@gmail.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor,
# Boston, MA  02110-1301, USA.

# For this to work correctly you need to create a webhook. To do this just
# click on the little gear icon next to the channel you're part of. From
# here you'll be able to access the Webhooks menu and create a new one.
#
#  When you've completed, you'll get a URL that looks a little like this:
#  https://media.guilded.gg/webhooks/417429632418316298/\
#         JHZ7lQml277CDHmQKMHI8qBe7bk2ZwO5UKjCiOAF7711o33MyqU344Qpgv7YTpadV_js
#
#  Simplified, it looks like this:
#     https://media.guilded.gg/webhooks/WEBHOOK_ID/WEBHOOK_TOKEN
#
#  This plugin will simply work using the url of:
#     guilded://WEBHOOK_ID/WEBHOOK_TOKEN
#
# API Documentation on Webhooks:
#    - https://discord.com/developers/docs/resources/webhook
#

import re
from .NotifyDiscord import NotifyDiscord


class NotifyGuilded(NotifyDiscord):
    """
    A wrapper to Guilded Notifications

    """

    # The default descriptive name associated with the Notification
    service_name = 'Guilded'

    # The services URL
    service_url = 'https://guilded.gg/'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_guilded'

    # The default secure protocol
    secure_protocol = 'guilded'

    # Guilded Webhook
    notify_url = 'https://media.guilded.gg/webhooks'

    @staticmethod
    def parse_native_url(url):
        """
        Support https://media.guilded.gg/webhooks/WEBHOOK_ID/WEBHOOK_TOKEN
        """

        result = re.match(
            r'^https?://(media\.)?guilded\.gg/webhooks/'
            # a UUID, but we do we really need to be _that_ picky?
            r'(?P<webhook_id>[-0-9a-f]+)/'
            r'(?P<webhook_token>[A-Z0-9_-]+)/?'
            r'(?P<params>\?.+)?$', url, re.I)

        if result:
            return NotifyGuilded.parse_url(
                '{schema}://{webhook_id}/{webhook_token}/{params}'.format(
                    schema=NotifyGuilded.secure_protocol,
                    webhook_id=result.group('webhook_id'),
                    webhook_token=result.group('webhook_token'),
                    params='' if not result.group('params')
                    else result.group('params')))

        return None
