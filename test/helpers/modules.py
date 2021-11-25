# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Chris Caron <lead2gold@gmail.com>
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
import six
from shutil import rmtree
from tempfile import mkdtemp
from apprise.plugins import __reset_matrix as reset_matrix
from apprise.plugins import __load_matrix as load_matrix

try:
    # Python v3.4+
    from importlib import reload
except ImportError:
    try:
        # Python v3.0-v3.3
        from imp import reload
    except ImportError:
        # Python v2.7
        pass


class ModuleImportError(object):
    """
    A Simple class/context manager for managing what modules are loaded
    forcing them to cause an import error.

    Syntax:

        with ModuleImportError(modules_to_throw_import_errors):
            # do your stuff


    The class automatically reloads any modules you specify in the base input
    variable before and after the module manipulation; thus it handles the
    cleanup for you.
    """

    base = r"^(apprise|apprise.plugins(\..*))$"

    # Track our unloadd modules
    __prev_unloaded = {}

    def __init__(self, modules, base=None):
        """
        Initialize our base module finder
        """
        self.base_re = re.compile(self.base if not base else base)

        # Ensure we're dealing with a list
        self.modules = \
            [modules] if isinstance(modules, six.string_types) else modules

    def set_modules(self, modules=None, unavailable=True, reload_modules=True):
        """
        Sets the state of specified modules
        """

        if modules is not None:
            # Ensure we're dealing with a list
            modules = \
                [modules] if isinstance(modules, six.string_types) else modules

        else:
            modules = self.modules

        for module in modules:
            if module not in self.__prev_unloaded:
                self.__prev_unloaded[module] = {
                    # Path to ghost library path
                    'path': None,
                    # our modules we found in memory
                    'modules': {},
                }

            # Get a list of our modules to work with
            related = sorted(
                [m for m in sys.modules.keys()
                 if m.startswith('{}.'.format(module))])

            # unload each module:
            for name in related:
                if name not in self.__prev_unloaded[module]:
                    self.__prev_unloaded[module]['modules'][name] = \
                        sys.modules[name]
                del sys.modules[name]

            if module in sys.modules:
                self.__prev_unloaded[module]['modules'][module] = \
                    sys.modules[module]
                del sys.modules[module]

            if unavailable and self.__prev_unloaded[module]['path'] is None:
                # We'll now create a temporary location to store our temporary
                # failing module (forcing an ImportError)
                self.__prev_unloaded[module]['path'] = mkdtemp()

                # Empty File
                open(os.path.join(
                    self.__prev_unloaded[module]['path'], '__init__.py'),
                    'w').close()

                os.makedirs(os.path.join(
                    self.__prev_unloaded[module]['path'], module))

                with open(os.path.join(
                        self.__prev_unloaded[module]['path'],
                        module, '__init__.py'), 'w') as fp:
                    fp.write('raise ImportError()')

                # Update our python path to point to our new temporary object
                sys.path.insert(0, self.__prev_unloaded[module]['path'])

            elif not unavailable and module in self.__prev_unloaded:
                if self.__prev_unloaded[module]['path']:
                    rmtree(self.__prev_unloaded[module]['path'])
                    sys.path.remove(self.__prev_unloaded[module]['path'])

                # Restore our modules
                for name, module in \
                        self.__prev_unloaded[module]['modules'].items():
                    sys.modules[name] = module

                # Remove from history
                del self.__prev_unloaded[name]

        if self.base_re and reload_modules:
            # Our base project modules; we need them sorted from longest module
            # path to smallest:
            base_modules = sorted(
                [name for name in sys.modules.keys()
                 if self.base_re.match(name)], reverse=True)

            # The following libraries need to be reloaded to prevent
            #  TypeError: super(type, obj): obj must be an instance or subtype
            #  of type.
            #
            #  This is better explained in this StackOverflow post:
            #     https://stackoverflow.com/questions/31363311/\
            #       any-way-to-manually-fix-operation-of-\
            #          super-after-ipython-reload-avoiding-ty
            for module in base_modules:
                try:
                    reload(sys.modules[module])

                except ImportError:
                    # Don't keep modules that can not be re-loaded in memory
                    del sys.modules[module]

        # Reset our matrix
        reset_matrix()
        load_matrix()

    def __enter__(self):
        """
        A simple tool that will unload a module for testing purposes and reload
        Apprise.
        """
        self.set_modules(self.modules, unavailable=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Performs a cleanup of said modules
        """

        # Build our list of modules
        self.set_modules(self.modules, unavailable=False)
