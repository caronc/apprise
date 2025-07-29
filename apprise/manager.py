# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2025, Chris Caron <lead2gold@gmail.com>
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

import contextlib
import hashlib
import inspect
import os
from os.path import abspath, dirname, join
import re
import sys
import threading
import time

from .logger import logger
from .utils.disk import path_decode
from .utils.module import import_module
from .utils.parse import parse_list
from .utils.singleton import Singleton


class PluginManager(metaclass=Singleton):
    """Designed to be a singleton object to maintain all initialized loading of
    modules in memory."""

    # Description (used for logging)
    name = "Singleton Plugin"

    # Memory Space
    _id = "undefined"

    # Our Module Python path name
    module_name_prefix = f"apprise.{_id}"

    # The module path to scan
    module_path = join(abspath(dirname(__file__)), _id)

    # For filtering our result when scanning a module
    module_filter_re = re.compile(r"^(?P<name>((?!_)[A-Za-z0-9]+))$")

    # thread safe loading
    _lock = threading.Lock()

    def __init__(self, *args, **kwargs):
        """Over-ride our class instantiation to provide a singleton."""

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

        # Track loaded module paths to prevent from loading them again
        self._loaded = set()

    def unload_modules(self, disable_native=False):
        """Reset our object and unload all modules."""

        with self._lock:
            if self._custom_module_map:
                # Handle Custom Module Assignments
                for meta in self._custom_module_map.values():
                    if meta["name"] not in self._module_map:
                        # Nothing to remove
                        continue

                    # For the purpose of tidying up un-used modules in memory
                    loaded = [
                        m
                        for m in sys.modules
                        if m.startswith(self._module_map[meta["name"]]["path"])
                    ]

                    for module_path in loaded:
                        del sys.modules[module_path]

            # Reset disabled plugins (if any)
            for schema in self._disabled:
                self._schema_map[schema].enabled = True
            self._disabled.clear()

            # Reset our variables
            self._schema_map = {}
            self._custom_module_map = {}
            if disable_native:
                self._module_map = {}

            else:
                self._module_map = None
                self._loaded = set()

            # Reset our path cache
            self._paths_previously_scanned = set()

    def load_modules(self, path=None, name=None, force=False):
        """Load our modules into memory."""

        # Default value
        module_name_prefix = self.module_name_prefix if name is None else name
        module_path = self.module_path if path is None else path

        with self._lock:
            if not force and module_path in self._loaded:
                # We're done
                return

            # Our base reference
            module_count = len(self._module_map) if self._module_map else 0
            schema_count = len(self._schema_map) if self._schema_map else 0

            if not self:
                # Initialize our maps
                self._module_map = {}
                self._schema_map = {}
                self._custom_module_map = {}

            # Used for the detection of additional Notify Services objects
            # The .py extension is optional as we support loading directories
            # too
            module_re = re.compile(
                r"^(?P<name>(?!base|_)[a-z0-9_]+)(\.py)?$", re.I
            )

            t_start = time.time()
            for f in os.listdir(module_path):
                tl_start = time.time()
                match = module_re.match(f)
                if not match:
                    # keep going
                    continue

                # Store our notification/plugin name:
                module_name = match.group("name")
                module_pyname = f"{module_name_prefix}.{module_name}"

                if module_name in self._module_map:
                    logger.warning(
                        "%s(s) (%s) already loaded; ignoring %s",
                        self.name,
                        module_name,
                        os.path.join(module_path, f),
                    )
                    continue

                try:
                    module = __import__(
                        module_pyname,
                        globals(),
                        locals(),
                        fromlist=[module_name],
                    )

                except ImportError:
                    # No problem, we can try again another way...
                    module = import_module(
                        os.path.join(module_path, f), module_pyname
                    )
                    if not module:
                        # logging found in import_module and not needed here
                        continue

                module_class = None
                for m_class in [
                    obj
                    for obj in dir(module)
                    if self.module_filter_re.match(obj)
                ]:
                    # Get our plugin
                    plugin = getattr(module, m_class)
                    if not hasattr(plugin, "app_id"):
                        # Filter out non-notification modules
                        logger.trace(
                            "(%s.%s) import failed; no app_id defined in %s",
                            self.name,
                            m_class,
                            os.path.join(module_path, f),
                        )
                        continue

                    # Add our plugin name to our module map
                    self._module_map[module_name] = {
                        "plugin": {plugin},
                        "module": module,
                        "path": f"{module_name_prefix}.{module_name}",
                        "native": True,
                    }

                    fn = getattr(plugin, "schemas", None)
                    schemas = set() if not callable(fn) else fn(plugin)

                    # map our schema to our plugin
                    for schema in schemas:
                        if schema in self._schema_map:
                            logger.error(
                                f"{self.name} schema ({schema}) mismatch"
                                " detected -"
                                f" {self._schema_map[schema]} already maps to"
                                f" {plugin}"
                            )
                            continue

                        # Assign plugin
                        self._schema_map[schema] = plugin

                    # Store our class
                    module_class = m_class
                    break

                if not module_class:
                    # Not a library we can load as it doesn't follow the simple
                    # rule that the class must bear the same name as the
                    # notification file itself.
                    logger.trace(
                        "%s (%s) import failed; no filename/Class "
                        "match found in %s",
                        self.name,
                        module_name,
                        os.path.join(module_path, f),
                    )
                    continue

                logger.trace(
                    f"{self.name} {module_name} loaded in"
                    f" {time.time() - tl_start:.6f}s"
                )

            # Track the directory loaded so we never load it again
            self._loaded.add(module_path)

            logger.debug(
                f"{self.name} {len(self._module_map) - module_count}(s) and"
                f" {len(self._schema_map) - schema_count} Schema(s) loaded in"
                f" {time.time() - t_start:.4f}s"
            )

    def module_detection(self, paths, cache=True):
        """Leverage the @notify decorator and load all objects found matching
        this."""
        # A simple restriction that we don't allow periods in the filename at
        # all so it can't be hidden (Linux OS's) and it won't conflict with
        # Python path naming.  This also prevents us from loading any python
        # file that starts with an underscore or dash
        # We allow for __init__.py as well
        module_re = re.compile(
            r"^(?P<name>[_a-z0-9][a-z0-9._-]+)?(\.py)?$", re.I
        )

        # Validate if we're a loadable Python file or not
        valid_python_file_re = re.compile(r".+\.py(o|c)?$", re.IGNORECASE)

        if isinstance(paths, str):
            paths = [
                paths,
            ]

        if not paths or not isinstance(paths, (tuple, list)):
            # We're done
            return

        def _import_module(path):
            # Since our plugin name can conflict (as a module) with another
            # we want to generate random strings to avoid steping on
            # another's namespace
            if not (path and valid_python_file_re.match(path)):
                # Ignore file/module type
                logger.trace("Plugin Scan: Skipping %s", path)
                return

            t_start = time.time()
            module_name = hashlib.sha1(path.encode("utf-8")).hexdigest()
            module_pyname = "{prefix}.{name}".format(
                prefix="apprise.custom.module", name=module_name
            )

            if module_pyname in self._custom_module_map:
                # First clear out existing entries
                for schema in self._custom_module_map[module_pyname]["notify"]:

                    # Remove any mapped modules to this file
                    del self._schema_map[schema]

                # Reset
                del self._custom_module_map[module_pyname]

            # Load our module
            module = import_module(path, module_pyname)
            if not module:
                # No problem, we can't use this object
                logger.warning("Failed to load custom module: %s", _path)
                return

            # Print our loaded modules if any
            if module_pyname in self._custom_module_map:
                logger.debug(
                    "Custom module %s - %d schema(s) (name=%s) "
                    "loaded in %.6fs",
                    _path,
                    len(self._custom_module_map[module_pyname]["notify"]),
                    module_name,
                    (time.time() - t_start),
                )

                # Add our plugin name to our module map
                self._module_map[module_name] = {
                    "plugin": set(),
                    "module": module,
                    "path": module_pyname,
                    "native": False,
                }

                for schema, _meta in self._custom_module_map[module_pyname][
                    "notify"
                ].items():

                    # For mapping purposes; map our element in our main list
                    self._module_map[module_name]["plugin"].add(
                        self._schema_map[schema]
                    )

                    # Log our success
                    logger.info("Loaded custom notification: %s://", schema)
            else:
                # The code reaches here if we successfully loaded the Python
                # module but no hooks/triggers were found. So we can safely
                # just remove/ignore this entry
                del sys.modules[module_pyname]
                return

            # end of _import_module()
            return

        for _path in paths:
            path = path_decode(_path)
            if (
                cache and path in self._paths_previously_scanned
            ) or not os.path.exists(path):
                # We're done as we've already scanned this
                continue

            # Store our path as a way of hashing it has been handled
            self._paths_previously_scanned.add(path)

            if os.path.isdir(path) and not os.path.isfile(
                os.path.join(path, "__init__.py")
            ):

                logger.debug("Scanning for custom plugins in: %s", path)
                for entry in os.listdir(path):
                    re_match = module_re.match(entry)
                    if not re_match:
                        # keep going
                        logger.trace("Plugin Scan: Ignoring %s", entry)
                        continue

                    new_path = os.path.join(path, entry)
                    if os.path.isdir(new_path):
                        # Update our path
                        new_path = os.path.join(path, entry, "__init__.py")
                        if not os.path.isfile(new_path):
                            logger.trace(
                                "Plugin Scan: Ignoring %s",
                                os.path.join(path, entry),
                            )
                            continue

                    if not cache or (
                        cache
                        and new_path not in self._paths_previously_scanned
                    ):
                        # Load our module
                        _import_module(new_path)

                        # Add our subdir path
                        self._paths_previously_scanned.add(new_path)
            else:
                if os.path.isdir(path):
                    # This logic is safe to apply because we already
                    # validated the directories state above; update our
                    # path
                    path = os.path.join(path, "__init__.py")
                    if cache and path in self._paths_previously_scanned:
                        continue

                    self._paths_previously_scanned.add(path)

                # directly load as is
                re_match = module_re.match(os.path.basename(path))
                # must be a match and must have a .py extension
                if not re_match or not re_match.group(1):
                    # keep going
                    logger.trace("Plugin Scan: Ignoring %s", path)
                    continue

                # Load our module
                _import_module(path)

        return None

    def add(self, plugin, schemas=None, url=None, send_func=None):
        """Ability to manually add Notification services to our stack."""

        if not self:
            # Lazy load
            self.load_modules()

        # Acquire a list of schemas
        p_schemas = parse_list(plugin.secure_protocol, plugin.protocol)
        if isinstance(schemas, str):
            schemas = [
                schemas,
            ]

        elif schemas is None:
            # Default
            schemas = p_schemas

        if not schemas or not isinstance(schemas, (set, tuple, list)):
            # We're done
            logger.error(
                "The schemas provided (type %s) is unsupported; "
                "loaded from %s.",
                type(schemas),
                send_func.__name__ if send_func else plugin.__class__.__name__,
            )
            return False

        # Convert our schemas into a set
        schemas = {s.lower() for s in schemas} | set(p_schemas)

        # Valdation
        conflict = [s for s in schemas if s in self]
        if conflict:
            # we're already handling this schema
            logger.warning(
                "The schema(s) (%s) are already defined and could not be "
                "loaded from %s%s.",
                ", ".join(conflict),
                "custom notify function " if send_func else "",
                send_func.__name__ if send_func else plugin.__class__.__name__,
            )
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
                    "name": module_name.split(".")[-1],
                    # The path to the module loaded
                    "path": path,
                    # Initialize our template
                    "notify": {},
                }

            for schema in schemas:
                self._custom_module_map[module_name]["notify"][schema] = {
                    # The name of the send function the @notify decorator
                    # wrapped
                    "fn_name": fn_name,
                    # The URL that was provided in the @notify decorator call
                    # associated with the 'on='
                    "url": url,
                }

        else:
            module_name = hashlib.sha1(
                "".join(schemas).encode("utf-8")
            ).hexdigest()
            module_pyname = "{prefix}.{name}".format(
                prefix="apprise.adhoc.module", name=module_name
            )

            # Add our plugin name to our module map
            self._module_map[module_name] = {
                "plugin": {plugin},
                "module": None,
                "path": module_pyname,
                "native": False,
            }

        for schema in schemas:
            # Assign our mapping
            self._schema_map[schema] = plugin

        return True

    def remove(self, *schemas):
        """Removes a loaded element (if defined)"""
        if not self:
            # Lazy load
            self.load_modules()

        for schema in schemas:
            with contextlib.suppress(KeyError):
                del self[schema]

    def plugins(self, include_disabled=True):
        """Return all of our loaded plugins."""
        if not self:
            # Lazy load
            self.load_modules()

        for module in self._module_map.values():
            for plugin in module["plugin"]:
                if not include_disabled and not plugin.enabled:
                    continue
                yield plugin

    def schemas(self, include_disabled=True):
        """Return all of our loaded schemas.

        if include_disabled == True, then even disabled notifications are
        returned
        """
        if not self:
            # Lazy load
            self.load_modules()

        # Return our list
        return (
            list(self._schema_map.keys())
            if include_disabled
            else [s for s in self._schema_map if self._schema_map[s].enabled]
        )

    def disable(self, *schemas):
        """Disables the modules associated with the specified schemas."""
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
        """Disables the modules associated with the specified schemas."""
        if not self:
            # Lazy load
            self.load_modules()

        # convert to set for faster indexing
        schemas = set(schemas)

        for plugin in self.plugins():
            # Get our plugin's schema list
            p_schemas = set(
                parse_list(plugin.secure_protocol, plugin.protocol)
            )

            if not schemas & p_schemas:
                if plugin.enabled:
                    # Disable it (only if previously enabled); this prevents us
                    # from adjusting schemas that were disabled due to missing
                    # libraries or other environment reasons
                    plugin.enabled = False
                    self._disabled |= p_schemas
                continue

            # If we reach here, our schema was flagged to be enabled
            if p_schemas & self._disabled:
                # Previously disabled; no worries, let's clear this up
                self._disabled -= p_schemas
                plugin.enabled = True

    def __contains__(self, schema):
        """Checks if a schema exists."""
        if not self:
            # Lazy load
            self.load_modules()

        return schema in self._schema_map

    def __delitem__(self, schema):
        if not self:
            # Lazy load
            self.load_modules()

        # Get our plugin (otherwise we throw a KeyError) which is
        # intended on del action that doesn't align
        plugin = self._schema_map[schema]

        # Our list of all schema entries
        p_schemas = {schema}

        for key in list(self._module_map.keys()):
            if plugin in self._module_map[key]["plugin"]:
                # Remove our plugin
                self._module_map[key]["plugin"].remove(plugin)

                # Custom Plugin Entry; Clean up cross reference
                module_pyname = self._module_map[key]["path"]
                if (
                    not self._module_map[key]["native"]
                    and module_pyname in self._custom_module_map
                ):

                    del self._custom_module_map[module_pyname]["notify"][
                        schema
                    ]

                    if not self._custom_module_map[module_pyname]["notify"]:
                        #
                        # Last custom loaded element
                        #

                        # Free up custom object entry
                        del self._custom_module_map[module_pyname]

                if not self._module_map[key]["plugin"]:
                    #
                    # Last element
                    #
                    if self._module_map[key]["native"]:
                        # Get our plugin's schema list
                        p_schemas = {
                            s
                            for s in parse_list(
                                plugin.secure_protocol, plugin.protocol
                            )
                            if s in self._schema_map
                        }

                    # free system memory
                    if self._module_map[key]["module"]:
                        del sys.modules[self._module_map[key]["path"]]

                    # free last remaining pointer in module map
                    del self._module_map[key]

        for schema in p_schemas:
            # Final Tidy
            del self._schema_map[schema]

    def __setitem__(self, schema, plugin):
        """Support fast assigning of Plugin/Notification Objects."""
        if not self:
            # Lazy load
            self.load_modules()

        # Set default values if not otherwise set
        if not plugin.service_name:
            # Assign service name if one doesn't exist
            plugin.service_name = f"{schema}://"

        p_schemas = set(parse_list(plugin.secure_protocol, plugin.protocol))
        if not p_schemas:
            # Assign our protocol
            plugin.secure_protocol = schema
            p_schemas.add(schema)

        elif schema not in p_schemas:
            # Add our others (if defined)
            plugin.secure_protocol = {
                schema,
                *parse_list(plugin.secure_protocol),
            }
            p_schemas.add(schema)

        if not self.add(plugin, schemas=p_schemas):
            raise KeyError("Conflicting Assignment")

    def __getitem__(self, schema):
        """Returns the indexed plugin identified by the schema specified."""
        if not self:
            # Lazy load
            self.load_modules()

        return self._schema_map[schema]

    def __iter__(self):
        """Returns an iterator so we can iterate over our loaded modules."""
        if not self:
            # Lazy load
            self.load_modules()

        return iter(self._module_map.values())

    def __len__(self):
        """Returns the number of modules/plugins loaded."""
        if not self:
            # Lazy load
            self.load_modules()

        return len(self._module_map)

    def __bool__(self):
        """Determines if object has loaded or not."""
        return bool(self._loaded and self._module_map is not None)
