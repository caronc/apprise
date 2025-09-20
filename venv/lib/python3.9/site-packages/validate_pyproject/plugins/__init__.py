# The code in this module is mostly borrowed/adapted from PyScaffold and was originally
# published under the MIT license
# The original PyScaffold license can be found in 'NOTICE.txt'
"""
.. _entry point: https://setuptools.readthedocs.io/en/latest/userguide/entry_point.html
"""

import typing
from importlib.metadata import EntryPoint, entry_points
from itertools import chain
from string import Template
from textwrap import dedent
from typing import (
    Any,
    Callable,
    Generator,
    Iterable,
    List,
    NamedTuple,
    Optional,
    Protocol,
    Union,
)

from .. import __version__
from ..types import Plugin, Schema

_DEFAULT_MULTI_PRIORITY = 0
_DEFAULT_TOOL_PRIORITY = 1


class PluginProtocol(Protocol):
    @property
    def id(self) -> str: ...

    @property
    def tool(self) -> str: ...

    @property
    def schema(self) -> Schema: ...

    @property
    def help_text(self) -> str: ...

    @property
    def fragment(self) -> str: ...


class PluginWrapper:
    def __init__(self, tool: str, load_fn: Plugin):
        self._tool = tool
        self._load_fn = load_fn

    @property
    def id(self) -> str:
        return f"{self._load_fn.__module__}.{self._load_fn.__name__}"

    @property
    def tool(self) -> str:
        return self._tool

    @property
    def schema(self) -> Schema:
        return self._load_fn(self.tool)

    @property
    def fragment(self) -> str:
        return ""

    @property
    def priority(self) -> float:
        return getattr(self._load_fn, "priority", _DEFAULT_TOOL_PRIORITY)

    @property
    def help_text(self) -> str:
        tpl = self._load_fn.__doc__
        if not tpl:
            return ""
        return Template(tpl).safe_substitute(tool=self.tool, id=self.id)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.tool!r}, {self.id})"

    def __str__(self) -> str:
        return self.id


class StoredPlugin:
    def __init__(self, tool: str, schema: Schema, source: str, priority: float):
        self._tool, _, self._fragment = tool.partition("#")
        self._schema = schema
        self._source = source
        self._priority = priority

    @property
    def id(self) -> str:
        return self._schema["$id"]  # type: ignore[no-any-return]

    @property
    def tool(self) -> str:
        return self._tool

    @property
    def schema(self) -> Schema:
        return self._schema

    @property
    def fragment(self) -> str:
        return self._fragment

    @property
    def priority(self) -> float:
        return self._priority

    @property
    def help_text(self) -> str:
        return self.schema.get("description", "")

    def __str__(self) -> str:
        return self._source

    def __repr__(self) -> str:
        args = [repr(self.tool), self.id]
        if self.fragment:
            args.append(f"fragment={self.fragment!r}")
        return f"{self.__class__.__name__}({', '.join(args)}, <schema: {self.id}>)"


if typing.TYPE_CHECKING:
    _: PluginProtocol = typing.cast("PluginWrapper", None)


def iterate_entry_points(group: str) -> Iterable[EntryPoint]:
    """Produces an iterable yielding an EntryPoint object for each plugin registered
    via ``setuptools`` `entry point`_ mechanism.

    This method can be used in conjunction with :obj:`load_from_entry_point` to filter
    the plugins before actually loading them. The entry points are not
    deduplicated.
    """
    entries = entry_points()
    if hasattr(entries, "select"):  # pragma: no cover
        # The select method was introduced in importlib_metadata 3.9 (and Python 3.10)
        # and the previous dict interface was declared deprecated
        select = typing.cast(
            "Callable[..., Iterable[EntryPoint]]",
            getattr(entries, "select"),  # noqa: B009
        )  # typecheck gymnastics
        return select(group=group)
    # pragma: no cover
    # TODO: Once Python 3.10 becomes the oldest version supported, this fallback and
    #       conditional statement can be removed.
    return (plugin for plugin in entries.get(group, []))


def load_from_entry_point(entry_point: EntryPoint) -> PluginWrapper:
    """Carefully load the plugin, raising a meaningful message in case of errors"""
    try:
        fn = entry_point.load()
        return PluginWrapper(entry_point.name, fn)
    except Exception as ex:
        raise ErrorLoadingPlugin(entry_point=entry_point) from ex


def load_from_multi_entry_point(
    entry_point: EntryPoint,
) -> Generator[StoredPlugin, None, None]:
    """Carefully load the plugin, raising a meaningful message in case of errors"""
    try:
        fn = entry_point.load()
        output = fn()
        id_ = f"{fn.__module__}.{fn.__name__}"
    except Exception as ex:
        raise ErrorLoadingPlugin(entry_point=entry_point) from ex

    priority = output.get("priority", _DEFAULT_MULTI_PRIORITY)
    for tool, schema in output["tools"].items():
        yield StoredPlugin(tool, schema, f"{id_}:{tool}", priority)
    for i, schema in enumerate(output.get("schemas", [])):
        yield StoredPlugin("", schema, f"{id_}:{i}", priority)


class _SortablePlugin(NamedTuple):
    name: str
    plugin: Union[PluginWrapper, StoredPlugin]

    def key(self) -> str:
        return self.plugin.tool or self.plugin.id

    def __lt__(self, other: Any) -> bool:
        # **Major concern**:
        # Consistency and reproducibility on which entry-points have priority
        # for a given environment.
        # The plugin with higher priority overwrites the schema definition.
        # The exact order that they are listed itself is not important for now.
        # **Implementation detail**:
        # By default, "single tool plugins" have priority 1 and "multi plugins"
        # have priority 0.
        # The order that the plugins will be listed is inverse to the priority.
        # If 2 plugins have the same numerical priority, the one whose
        # entry-point name is "higher alphabetically" wins.
        return (self.plugin.priority, self.name, self.key()) < (
            other.plugin.priority,
            other.name,
            other.key(),
        )


def list_from_entry_points(
    filtering: Callable[[EntryPoint], bool] = lambda _: True,
) -> List[Union[PluginWrapper, StoredPlugin]]:
    """Produces a list of plugin objects for each plugin registered
    via ``setuptools`` `entry point`_ mechanism.

    Args:
        filtering: function returning a boolean deciding if the entry point should be
            loaded and included (or not) in the final list. A ``True`` return means the
            plugin should be included.
    """
    tool_eps = (
        _SortablePlugin(e.name, load_from_entry_point(e))
        for e in iterate_entry_points("validate_pyproject.tool_schema")
        if filtering(e)
    )
    multi_eps = (
        _SortablePlugin(e.name, p)
        for e in iterate_entry_points("validate_pyproject.multi_schema")
        for p in load_from_multi_entry_point(e)
        if filtering(e)
    )
    eps = chain(tool_eps, multi_eps)
    dedup = {e.key(): e.plugin for e in sorted(eps)}
    return list(dedup.values())


class ErrorLoadingPlugin(RuntimeError):
    _DESC = """There was an error loading '{plugin}'.
    Please make sure you have installed a version of the plugin that is compatible
    with {package} {version}. You can also try uninstalling it.
    """
    __doc__ = _DESC

    def __init__(self, plugin: str = "", entry_point: Optional[EntryPoint] = None):
        if entry_point and not plugin:
            plugin = getattr(entry_point, "module", entry_point.name)

        sub = {"package": __package__, "version": __version__, "plugin": plugin}
        msg = dedent(self._DESC).format(**sub).splitlines()
        super().__init__(f"{msg[0]}\n{' '.join(msg[1:])}")
