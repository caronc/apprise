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
