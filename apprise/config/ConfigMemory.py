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

from .ConfigBase import ConfigBase
from ..AppriseLocale import gettext_lazy as _


class ConfigMemory(ConfigBase):
    """
    For information that was loaded from memory and does not
    persist anywhere.
    """

    # The default descriptive name associated with the service
    service_name = _('Memory')

    # The default protocol
    protocol = 'memory'

    def __init__(self, content, **kwargs):
        """
        Initialize Memory Object

        Memory objects just store the raw configuration in memory.  There is
        no external reference point. It's always considered cached.
        """
        super().__init__(**kwargs)

        # Store our raw config into memory
        self.content = content

        if self.config_format is None:
            # Detect our format if possible
            self.config_format = \
                ConfigMemory.detect_config_format(self.content)

        return

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        return 'memory://'

    def read(self, **kwargs):
        """
        Simply return content stored into memory
        """

        return self.content

    @staticmethod
    def parse_url(url):
        """
        Memory objects have no parseable URL

        """
        # These URLs can not be parsed
        return None
