# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2023, Chris Caron <lead2gold@gmail.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import os
import re
import sys
import time
import hashlib
import inspect
from .utils import import_module
from os.path import dirname
from os.path import abspath
from os.path import join
from importlib import reload

from .logger import logger


class Singleton(type):
    """
    Our Singleton MetaClass
    """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        """
        instantiate our singleton meta entry
        """
        if cls not in cls._instances:
            # we have not every built an instance before.  Build one now.
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class NotificationManager(metaclass=Singleton):
    """
    Designed to be a singleton object to maintain all initialized notifications
    in memory.
    """

    # Our Module Python path name
    module_name_prefix = 'apprise.plugins'

    # The module path to scan
    module_path = join(abspath(dirname(__file__)), 'plugins')

    def __init__(self, *args, **kwargs):
        """
        Over-ride our class instantiation to provide a singleton
        """

        self._module_map = None
        self._schema_map = None

        # This contains a mapping of all plugins dynamicaly loaded at runtime
        # from external modules such as the @notify decorator
        #
        # The elements here will be additionally added to the _schema_map if
        # there is no conflict otherwise.
        # The structure looks like the following:
        # Module path, e.g. /usr/share/apprise/plugins/my_notify_hook.py
        # {
        #   'path': path,
        #
        #   'notify': {
        #     'schema': {
        #       'name': 'Custom schema name',
        #       'fn_name': 'name_of_function_decorator_was_found_on',
        #       'url': 'schema://any/additional/info/found/on/url'
        #       'plugin': <CustomNotifyWrapperPlugin>
        #    },
        #     'schema2': {
        #       'name': 'Custom schema name',
        #       'fn_name': 'name_of_function_decorator_was_found_on',
        #       'url': 'schema://any/additional/info/found/on/url'
        #       'plugin': <CustomNotifyWrapperPlugin>
        #    }
        #  }
        # Note: that the <CustomNotifyWrapperPlugin> inherits from
        #       NotifyBase
        self._custom_module_map = {}

        # Track manually disabled modules (by their schema)
        self._disabled = set()

        # Hash of all paths previously scanned so we don't waste
        # effort/overhead doing it again
        self._paths_previously_scanned = set()

    def unload_modules(self, disable_native=False):
        """
        Reset our object and unload all modules
        """
        if self._custom_module_map and self._custom_module_map:
            # Handle Custom Module Assignments
            for module_path in list(sys.modules.keys()):
                for module_name, meta in self._custom_module_map.items():
                    if module_path.startswith(meta['path']):
                        del sys.modules[module_path]

        # Reset our variables
        self._module_map = None if not disable_native else {}
        self._schema_map = {}
        self._custom_module_map = {}

        # Reset our internal tracking flags
        self._paths_previously_scanned = set()
        self._disabled = set()

    def load_modules(self, path=None, name=None):
        """
        Load our modules into memory
        """

        # Default value
        module_name_prefix = self.module_name_prefix if name is None else name
        module_path = self.module_path if path is None else path

        if not self:
            # Initialize our maps
            self._module_map = {}
            self._schema_map = {}
            self._custom_module_map = {}

        # Used for the detection of additional Notify Services objects
        # The .py extension is optional as we support loading directories too
        module_re = re.compile(r'^(?P<name>Notify[a-z0-9]+)(\.py)?$', re.I)

        t_start = time.time()
        for f in os.listdir(module_path):
            tl_start = time.time()
            match = module_re.match(f)
            if not match:
                # keep going
                continue

            elif match.group('name') == 'NotifyBase':
                # keep going
                continue

            # Store our notification/plugin name:
            module_name = match.group('name')
            module_pyname = '{}.{}'.format(module_name_prefix, module_name)

            try:
                module = __import__(
                    module_pyname,
                    globals(), locals(),
                    fromlist=[module_name])

            except ImportError:
                # No problem, we can't use this object
                continue

            if not hasattr(module, module_name):
                # Not a library we can load as it doesn't follow the simple
                # rule that the class must bear the same name as the
                # notification file itself.
                continue

            # Get our plugin
            plugin = getattr(module, module_name)
            if not hasattr(plugin, 'app_id'):
                # Filter out non-notification modules
                continue

            elif module_name in self._module_map:
                # we're already handling this object
                continue

            # Add our plugin name to our module map
            self._module_map[module_name] = {
                'plugin': set([plugin]),
                'module': module,
                'path': '{}.{}'.format(module_name_prefix, module_name),
                'native': True,
            }

            fn = getattr(plugin, 'schemas', None)
            schemas = set([]) if not callable(fn) else fn(plugin)

            # map our schema to our plugin
            for schema in schemas:
                if schema in self._schema_map:
                    logger.error(
                        "Notification schema ({}) mismatch detected - {} to {}"
                        .format(schema, self._schema_map, plugin))
                    continue

                # Assign plugin
                self._schema_map[schema] = plugin

            logger.trace(
                'Plugin {} loaded in {:.6f}s'.format(
                    module_name, (time.time() - tl_start)))
        logger.debug(
            '{} Plugin(s) and {} Schema(s) loaded in {:.4f}s'.format(
                len(self._module_map), len(self._schema_map),
                (time.time() - t_start)))

    def module_detection(self, paths, cache=True):
        """
        Leverage the @notify decorator and load all objects found matching
        this.
        """
        # A simple restriction that we don't allow periods in the filename at
        # all so it can't be hidden (Linux OS's) and it won't conflict with
        # Python path naming.  This also prevents us from loading any python
        # file that starts with an underscore or dash
        # We allow for __init__.py as well
        module_re = re.compile(
            r'^(?P<name>[_a-z0-9][a-z0-9._-]+)?(\.py)?$', re.I)

        # Validate if we're a loadable Python file or not
        valid_python_file_re = re.compile(r'.+\.py(o|c)?$', re.IGNORECASE)

        if isinstance(paths, str):
            paths = [paths, ]

        if not paths or not isinstance(paths, (tuple, list)):
            # We're done
            return

        def _import_module(path):
            # Since our plugin name can conflict (as a module) with another
            # we want to generate random strings to avoid steping on
            # another's namespace
            if not (path and valid_python_file_re.match(path)):
                # Ignore file/module type
                logger.trace('Plugin Scan: Skipping %s', path)
                return

            t_start = time.time()
            module_name = hashlib.sha1(path.encode('utf-8')).hexdigest()
            module_pyname = "{prefix}.{name}".format(
                prefix='apprise.custom.module', name=module_name)

            if module_pyname in self._custom_module_map:
                # First clear out existing entries
                for schema in \
                        self._custom_module_map[module_pyname]['notify']\
                        .keys():

                    # Remove any mapped modules to this file
                    del self._schema_map[schema]

                # Reset
                del self._custom_module_map[module_pyname]

            # Load our module
            module = import_module(path, module_pyname)
            if not module:
                # No problem, we can't use this object
                logger.warning('Failed to load custom module: %s', _path)
                return

            # Print our loaded modules if any
            if module_pyname in self._custom_module_map:
                logger.debug(
                    'Custom module %s - %d schema(s) (name=%s) '
                    'loaded in {:.6f}s',
                    _path, module_name,
                    len(self._custom_module_map[module_pyname]['notify']),
                    (time.time() - t_start))

                # Add our plugin name to our module map
                self._module_map[module_name] = {
                    'plugin': set(),
                    'module': module,
                    'path': module_pyname,
                    'native': False,
                }

                for schema, meta in\
                        self._custom_module_map[module_pyname]['notify']\
                        .items():

                    # For mapping purposes; map our element in our main list
                    self._module_map[module_name]['plugin'].add(
                        self._schema_map[schema])

                    # Log our success
                    logger.info('Loaded custom notification: %s://', schema)
            else:
                # The code reaches here if we successfully loaded the Python
                # module but no hooks/triggers were found. So we can safely
                # just remove/ignore this entry
                del sys.modules[module_pyname]
                return

            # end of _import_module()
            return

        for _path in paths:
            path = os.path.abspath(os.path.expanduser(_path))
            if (cache and path in self._paths_previously_scanned) \
                    or not os.path.exists(path):
                # We're done as we've already scanned this
                continue

            # Store our path as a way of hashing it has been handled
            self._paths_previously_scanned.add(path)

            if os.path.isdir(path) and not \
                    os.path.isfile(os.path.join(path, '__init__.py')):

                logger.debug('Scanning for custom plugins in: %s', path)
                for entry in os.listdir(path):
                    re_match = module_re.match(entry)
                    if not re_match:
                        # keep going
                        logger.trace('Plugin Scan: Ignoring %s', entry)
                        continue

                    new_path = os.path.join(path, entry)
                    if os.path.isdir(new_path):
                        # Update our path
                        new_path = os.path.join(path, entry, '__init__.py')
                        if not os.path.isfile(new_path):
                            logger.trace(
                                'Plugin Scan: Ignoring %s',
                                os.path.join(path, entry))
                            continue

                    if not cache or \
                            (cache and
                             new_path not in self._paths_previously_scanned):
                        # Load our module
                        _import_module(new_path)

                        # Add our subdir path
                        self._paths_previously_scanned.add(new_path)
            else:
                if os.path.isdir(path):
                    # This logic is safe to apply because we already validated
                    # the directories state above; update our path
                    path = os.path.join(path, '__init__.py')
                    if cache and path in self._paths_previously_scanned:
                        continue

                    self._paths_previously_scanned.add(path)

                # directly load as is
                re_match = module_re.match(os.path.basename(path))
                # must be a match and must have a .py extension
                if not re_match or not re_match.group(1):
                    # keep going
                    logger.trace('Plugin Scan: Ignoring %s', path)
                    continue

                # Load our module
                _import_module(path)

            return None

    def add(self, schema, plugin, url=None, send_func=None):
        """
        Ability to manually add Notification services to our stack
        """

        if not self:
            # Lazy load
            self.load_modules()

        if schema in self:
            # we're already handling this schema
            logger.warning(
                'The schema (%s) is already defined and could not be '
                'loaded from %s%s.',
                schema,
                'custom notify function ' if send_func else '',
                send_func.__name__ if send_func else plugin.__class__.__name__)
            return False

        if send_func:
            # Acquire the function name
            fn_name = send_func.__name__

            # Acquire the python filename path
            path = inspect.getfile(send_func)

            # Acquire our path to our module
            module_name = str(send_func.__module__)

            if module_name not in self._custom_module_map:
                # Support non-dynamic includes as well...
                self._custom_module_map[module_name] = {
                    # Name can be useful for indexing back into the
                    # _module_map object; this is the key to do it with:
                    'name': module_name.split('.')[-1],

                    # The path to the module loaded
                    'path': path,

                    # Initialize our template
                    'notify': {},
                }

            self._custom_module_map[module_name]['notify'][schema] = {
                # The name of the send function the @notify decorator wrapped
                'fn_name': fn_name,
                # The URL that was provided in the @notify decorator call
                # associated with the 'on='
                'url': url,
            }

        # Assign our mapping
        self._schema_map[schema] = plugin

        return True

    def reload(self, module_name):
        """
        Reloads our module
        """
        if not self:
            # Lazy load
            self.load_modules()

        module_pyname = '{}.{}'.format(self.module_name_prefix, module_name)
        if module_name in self._module_map and module_pyname in sys.modules:
            path = self._module_map[module_name]['path'] + '.'
            for module_path in list(sys.modules.keys()):
                if module_path.startswith(path):
                    del sys.modules[module_path]

            reload(sys.modules[module_pyname])

            # Store our new values from the reload
            module = sys.modules[module_pyname]
            plugin = getattr(module, module_name)

            # Update our Schema Map
            for schema in self.schemas():
                if self._schema_map[schema] \
                        == self._module_map[module_name]['plugin']:
                    # Update Plugin
                    self._schema_map[schema] = plugin

            # Update Module Map
            self._module_map[module_name]['module'] = module
            self._module_map[module_name]['plugin'].add(plugin)

    def remove(self, *schemas):
        """
        Removes a loaded element (if defined)
        """
        if not self:
            # Nothing to do
            return

        for schema in schemas:
            if self and schema in self:
                del self._schema_map[schema]

    def plugins(self):
        """
        Return all of our loaded plugins
        """
        if not self:
            # Lazy load
            self.load_modules()

        for module in self._module_map.values():
            for plugin in module['plugin']:
                yield plugin

    def schemas(self):
        """
        Return all of our loaded schemas
        """
        if not self:
            # Lazy load
            self.load_modules()

        return list(self._schema_map.keys())

    def disable(self, *schemas):
        """
        Disables the modules associated with the specified schemas
        """
        if not self:
            # Lazy load
            self.load_modules()

        for schema in schemas:
            if schema not in self._schema_map:
                continue

            if not self._schema_map[schema].enabled:
                continue

            # Disable
            self._schema_map[schema].enabled = False
            self._disabled.add(schema)

    def enable_only(self, *schemas):
        """
        Disables the modules associated with the specified schemas
        """
        if not self:
            # Lazy load
            self.load_modules()

        # convert to set for faster indexing
        schemas = set(schemas)

        # Track plugins added since they share 1 or more schemas
        _enabled = set()

        for schema in self._schema_map:

            if schema not in schemas:
                if self._schema_map[schema].enabled and \
                        self._schema_map[schema] not in _enabled:
                    # Disable
                    self._schema_map[schema].enabled = False
                    self._disabled.add(schema)
                continue

            if schema in self._disabled:
                self._disabled.remove(schema)
                self._schema_map[schema].enabled = True
                _enabled.add(self._schema_map[schema])

    def __contains__(self, schema):
        """
        Checks if a schema exists
        """
        if not self:
            # Lazy load
            self.load_modules()

        return schema in self._schema_map

    def __delitem__(self, schema):
        if not self:
            # Lazy load
            self.load_modules()

        for key in list(self._module_map.keys()):
            if key not in self._module_map:
                continue

            if self._schema_map[schema] in self._module_map[key]['plugin']:
                self._module_map[key]['plugin']\
                    .remove(self._schema_map[schema])

                # Custom Plugin Entry; Clean up cross reference
                module_pyname = self._module_map[key]['path']
                if not self._module_map[key]['native'] and \
                        module_pyname in self._custom_module_map:

                    del self.\
                        _custom_module_map[module_pyname]['notify'][schema]

                    if not self._custom_module_map[module_pyname]['notify']:
                        #
                        # Last custom loaded element
                        #

                        # Free up custom object entry
                        del self._custom_module_map[module_pyname]

                if not self._module_map[key]['plugin']:
                    #
                    # Last element
                    #

                    # free system memory
                    del sys.modules[self._module_map[key]['path']]

                    # free last remaining pointer in module map
                    del self._module_map[key]

        del self._schema_map[schema]

    def __setitem__(self, schema, plugin):
        """
        Support fast assigning of Plugin/Notification Objects
        """
        if not self:
            # Lazy load
            self.load_modules()

        # Set default values if not otherwise set
        if not plugin.service_name:
            # Assign service name if one doesn't exist
            plugin.service_name = f'{schema}://'

        # Assignment
        self._schema_map[schema] = plugin

        module_name = hashlib.sha1(schema.encode('utf-8')).hexdigest()
        module_pyname = "{prefix}.{name}".format(
            prefix='apprise.adhoc.module', name=module_name)

        # Add our plugin name to our module map
        self._module_map[module_name] = {
            'plugin': set([plugin]),
            'module': None,
            'path': '{}.{}'.format(module_pyname, module_name),
            'native': False,
        }

    def __getitem__(self, schema):
        """
        Returns the indexed plugin identified by the schema specified
        """
        if not self:
            # Lazy load
            self.load_modules()

        return self._schema_map[schema]

    def __iter__(self):
        """
        Returns an iterator so we can iterate over our loaded modules
        """
        if self._module_map is None:
            # Lazy load
            self.load_modules()

        return iter(self._module_map.values())

    def __len__(self):
        """
        Returns the number of modules/plugins loaded
        """
        if not self:
            # Lazy load
            self.load_modules()

        return len(self._module_map)

    def __bool__(self):
        """
        Determines if object has loaded or not
        """
        return True if self._module_map is not None else False
