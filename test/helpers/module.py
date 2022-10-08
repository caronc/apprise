# -*- coding: utf-8 -*-
#
# Copyright (C) 2022 Chris Caron <lead2gold@gmail.com>
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

import re
import os
import sys

from importlib import reload


def module_reload(filename):
    """

    set filename to plugin to be reloaded (for example NotifyGnome.py)

    The following libraries need to be reloaded to prevent
     TypeError: super(type, obj): obj must be an instance or subtype of type
     This is better explained in this StackOverflow post:
        https://stackoverflow.com/questions/31363311/\
          any-way-to-manually-fix-operation-of-\
             super-after-ipython-reload-avoiding-ty

    """

    module_name = 'apprise.plugins.{}'.format(
        re.match(r'^(.+)(\.py)?$', os.path.basename(filename), re.I).group(1))

    reload(sys.modules['apprise.common'])
    reload(sys.modules['apprise.attachment'])
    reload(sys.modules['apprise.config'])
    reload(sys.modules[module_name])
    reload(sys.modules['apprise.plugins'])
    reload(sys.modules['apprise.Apprise'])
    reload(sys.modules['apprise.utils'])
    reload(sys.modules['apprise'])
