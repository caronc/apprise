# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 Chris Caron <lead2gold@gmail.com>
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
        super(ConfigMemory, self).__init__(**kwargs)

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
