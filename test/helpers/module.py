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
from importlib import import_module, reload
import sys


def reload_plugin(name, replace_in=None):
    """
    Reload built-in plugin module, e.g. `NotifyGnome`.

    Reloading plugin modules is needed when testing module-level code of
    notification plugins.

    See also https://stackoverflow.com/questions/31363311.
    """

    module_name = f"apprise.plugins.{name}"

    reload(sys.modules['apprise.common'])
    reload(sys.modules['apprise.attachment'])
    reload(sys.modules['apprise.config'])
    if module_name in sys.modules:
        reload(sys.modules[module_name])
    reload(sys.modules['apprise.plugins'])
    reload(sys.modules['apprise.Apprise'])
    reload(sys.modules['apprise.utils'])
    reload(sys.modules['apprise'])

    # Fix reference to new plugin class in given module.
    # Needed for updating the module-level import reference like
    # `from apprise.plugins.NotifyMacOSX import NotifyMacOSX`.
    if replace_in is not None:
        mod = import_module(module_name)
        setattr(replace_in, name, getattr(mod, name))
