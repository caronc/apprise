"""
Retrieve JSON schemas for validating dicts representing a ``pyproject.toml`` file.
"""

import json
import logging
import sys
import typing
from enum import Enum
from functools import partial, reduce
from types import MappingProxyType, ModuleType
from typing import (
    Callable,
    Dict,
    Iterator,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    Union,
)

import fastjsonschema as FJS

from . import errors, formats
from .error_reporting import detailed_errors
from .extra_validations import EXTRA_VALIDATIONS
from .types import FormatValidationFn, Schema, ValidationFn

_logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:  # pragma: no cover
    from .plugins import PluginProtocol


if sys.version_info >= (3, 9):  # pragma: no cover
    from importlib.resources import files

    def read_text(package: Union[str, ModuleType], resource: str) -> str:
        """:meta private:"""
        return files(package).joinpath(resource).read_text(encoding="utf-8")

else:  # pragma: no cover
    from importlib.resources import read_text as read_text  # noqa: PLC0414


__all__ = ["Validator"]


T = TypeVar("T", bound=Mapping)
AllPlugins = Enum("AllPlugins", "ALL_PLUGINS")  #: :meta private:
ALL_PLUGINS = AllPlugins.ALL_PLUGINS

TOP_LEVEL_SCHEMA = "pyproject_toml"
PROJECT_TABLE_SCHEMA = "project_metadata"


def _get_public_functions(module: ModuleType) -> Mapping[str, FormatValidationFn]:
    return {
        fn.__name__.replace("_", "-"): fn
        for fn in module.__dict__.values()
        if callable(fn) and not fn.__name__.startswith("_")
    }


FORMAT_FUNCTIONS = MappingProxyType(_get_public_functions(formats))


def load(name: str, package: str = __package__, ext: str = ".schema.json") -> Schema:
    """Load the schema from a JSON Schema file.
    The returned dict-like object is immutable.

    :meta private: (low level detail)
    """
    return Schema(json.loads(read_text(package, f"{name}{ext}")))


def load_builtin_plugin(name: str) -> Schema:
    """:meta private: (low level detail)"""
    return load(name, f"{__package__}.plugins")


class SchemaRegistry(Mapping[str, Schema]):
    """Repository of parsed JSON Schemas used for validating a ``pyproject.toml``.

    During instantiation the schemas equivalent to PEP 517, PEP 518 and PEP 621
    will be combined with the schemas for the ``tool`` subtables provided by the
    plugins.

    Since this object work as a mapping between each schema ``$id`` and the schema
    itself, all schemas provided by plugins **MUST** have a top level ``$id``.

    :meta private: (low level detail)
    """

    def __init__(self, plugins: Sequence["PluginProtocol"] = ()):
        self._schemas: Dict[str, Tuple[str, str, Schema]] = {}
        # (which part of the TOML, who defines, schema)

        top_level = typing.cast("dict", load(TOP_LEVEL_SCHEMA))  # Make it mutable
        self._spec_version: str = top_level["$schema"]
        top_properties = top_level["properties"]
        tool_properties = top_properties["tool"].setdefault("properties", {})

        # Add PEP 621
        project_table_schema = load(PROJECT_TABLE_SCHEMA)
        self._ensure_compatibility(PROJECT_TABLE_SCHEMA, project_table_schema)
        sid = project_table_schema["$id"]
        top_level["project"] = {"$ref": sid}
        origin = f"{__name__} - project metadata"
        self._schemas = {sid: ("project", origin, project_table_schema)}

        # Add tools using Plugins
        for plugin in plugins:
            if plugin.tool:
                allow_overwrite: Optional[str] = None
                if plugin.tool in tool_properties:
                    _logger.warning(f"{plugin} overwrites `tool.{plugin.tool}` schema")
                    allow_overwrite = plugin.schema.get("$id")
                else:
                    _logger.info(f"{plugin} defines `tool.{plugin.tool}` schema")
                compatible = self._ensure_compatibility(
                    plugin.tool, plugin.schema, allow_overwrite
                )
                sid = compatible["$id"]
                sref = f"{sid}#{plugin.fragment}" if plugin.fragment else sid
                tool_properties[plugin.tool] = {"$ref": sref}
                self._schemas[sid] = (f"tool.{plugin.tool}", plugin.id, plugin.schema)
            else:
                _logger.info(f"{plugin} defines extra schema {plugin.id}")
                self._schemas[plugin.id] = (plugin.id, plugin.id, plugin.schema)

        self._main_id: str = top_level["$id"]
        main_schema = Schema(top_level)
        origin = f"{__name__} - build metadata"
        self._schemas[self._main_id] = ("<$ROOT>", origin, main_schema)

    @property
    def spec_version(self) -> str:
        """Version of the JSON Schema spec in use"""
        return self._spec_version

    @property
    def main(self) -> str:
        """Top level schema for validating a ``pyproject.toml`` file"""
        return self._main_id

    def _ensure_compatibility(
        self,
        reference: str,
        schema: Schema,
        allow_overwrite: Optional[str] = None,
    ) -> Schema:
        if "$id" not in schema or not schema["$id"]:
            raise errors.SchemaMissingId(reference or "<extra>")
        sid = schema["$id"]
        if sid in self._schemas and sid != allow_overwrite:
            raise errors.SchemaWithDuplicatedId(sid)
        version = schema.get("$schema")
        # Support schemas with missing trailing # (incorrect, but required before 0.15)
        if version and version.rstrip("#") != self.spec_version.rstrip("#"):
            raise errors.InvalidSchemaVersion(
                reference or sid, version, self.spec_version
            )
        return schema

    def __getitem__(self, key: str) -> Schema:
        return self._schemas[key][-1]

    def __iter__(self) -> Iterator[str]:
        return iter(self._schemas)

    def __len__(self) -> int:
        return len(self._schemas)


class RefHandler(Mapping[str, Callable[[str], Schema]]):
    """:mod:`fastjsonschema` allows passing a dict-like object to load external schema
    ``$ref``s. Such objects map the URI schema (e.g. ``http``, ``https``, ``ftp``)
    into a function that receives the schema URI and returns the schema (as parsed JSON)
    (otherwise :mod:`urllib` is used and the URI is assumed to be a valid URL).
    This class will ensure all the URIs are loaded from the local registry.

    :meta private: (low level detail)
    """

    def __init__(self, registry: Mapping[str, Schema]):
        self._uri_schemas = ["http", "https"]
        self._registry = registry

    def __contains__(self, key: object) -> bool:
        if isinstance(key, str):
            if key not in self._uri_schemas:
                self._uri_schemas.append(key)
            return True
        return False

    def __iter__(self) -> Iterator[str]:
        return iter(self._uri_schemas)

    def __len__(self) -> int:
        return len(self._uri_schemas)

    def __getitem__(self, key: str) -> Callable[[str], Schema]:
        """All the references should be retrieved from the registry"""
        return self._registry.__getitem__


class Validator:
    _plugins: Sequence["PluginProtocol"]

    def __init__(
        self,
        plugins: Union[Sequence["PluginProtocol"], AllPlugins] = ALL_PLUGINS,
        format_validators: Mapping[str, FormatValidationFn] = FORMAT_FUNCTIONS,
        extra_validations: Sequence[ValidationFn] = EXTRA_VALIDATIONS,
        *,
        extra_plugins: Sequence["PluginProtocol"] = (),
    ):
        self._code_cache: Optional[str] = None
        self._cache: Optional[ValidationFn] = None
        self._schema: Optional[Schema] = None

        # Let's make the following options readonly
        self._format_validators = MappingProxyType(format_validators)
        self._extra_validations = tuple(extra_validations)

        if plugins is ALL_PLUGINS:
            from .plugins import list_from_entry_points

            plugins = list_from_entry_points()

        self._plugins = (*plugins, *extra_plugins)

        self._schema_registry = SchemaRegistry(self._plugins)
        self.handlers = RefHandler(self._schema_registry)

    @property
    def registry(self) -> SchemaRegistry:
        return self._schema_registry

    @property
    def schema(self) -> Schema:
        """Top level ``pyproject.toml`` JSON Schema"""
        return Schema({"$ref": self._schema_registry.main})

    @property
    def extra_validations(self) -> Sequence[ValidationFn]:
        """List of extra validation functions that run after the JSON Schema check"""
        return self._extra_validations

    @property
    def formats(self) -> Mapping[str, FormatValidationFn]:
        """Mapping between JSON Schema formats and functions that validates them"""
        return self._format_validators

    @property
    def generated_code(self) -> str:
        if self._code_cache is None:
            fmts = dict(self.formats)
            self._code_cache = FJS.compile_to_code(
                self.schema, self.handlers, fmts, use_default=False
            )

        return self._code_cache

    def __getitem__(self, schema_id: str) -> Schema:
        """Retrieve a schema from registry"""
        return self._schema_registry[schema_id]

    def __call__(self, pyproject: T) -> T:
        """Checks a parsed ``pyproject.toml`` file (given as :obj:`typing.Mapping`)
        and raises an exception when it is not a valid.
        """
        if self._cache is None:
            compiled = FJS.compile(
                self.schema, self.handlers, dict(self.formats), use_default=False
            )
            fn = partial(compiled, custom_formats=self._format_validators)
            self._cache = typing.cast("ValidationFn", fn)

        with detailed_errors():
            self._cache(pyproject)
            return reduce(lambda acc, fn: fn(acc), self.extra_validations, pyproject)
