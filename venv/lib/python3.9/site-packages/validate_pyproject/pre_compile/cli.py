# ruff: noqa: C408
# Unnecessary `dict` call (rewrite as a literal)

import json
import logging
import sys
from functools import partial, wraps
from pathlib import Path
from types import MappingProxyType
from typing import Any, Dict, List, Mapping, NamedTuple, Sequence

from .. import cli
from ..plugins import PluginProtocol, PluginWrapper
from ..plugins import list_from_entry_points as list_plugins_from_entry_points
from ..remote import RemotePlugin, load_store
from . import pre_compile

if sys.platform == "win32":  # pragma: no cover
    from subprocess import list2cmdline as arg_join
else:  # pragma: no cover
    from shlex import join as arg_join


_logger = logging.getLogger(__package__)


def JSON_dict(name: str, value: str) -> Dict[str, Any]:
    try:
        return ensure_dict(name, json.loads(value))
    except json.JSONDecodeError as ex:
        raise ValueError(f"Invalid JSON: {value}") from ex


META: Dict[str, dict] = {
    "output_dir": dict(
        flags=("-O", "--output-dir"),
        default=".",
        type=Path,
        help="Path to the directory where the files for embedding will be generated "
        "(default: current working directory)",
    ),
    "main_file": dict(
        flags=("-M", "--main-file"),
        default="__init__.py",
        help="Name of the file that will contain the main `validate` function"
        "(default: `%(default)s`)",
    ),
    "replacements": dict(
        flags=("-R", "--replacements"),
        default="{}",
        type=wraps(JSON_dict)(partial(JSON_dict, "replacements")),
        help="JSON string (don't forget to quote) representing a map between strings "
        "that should be replaced in the generated files and their replacement, "
        "for example: \n"
        '-R \'{"from packaging import": "from .._vendor.packaging import"}\'',
    ),
    "tool": dict(
        flags=("-t", "--tool"),
        action="append",
        dest="tool",
        help="External tools file/url(s) to load, of the form name=URL#path",
    ),
    "store": dict(
        flags=("--store",),
        help="Load a pyproject.json file and read all the $ref's into tools "
        "(see https://json.schemastore.org/pyproject.json)",
    ),
}


def ensure_dict(name: str, value: Any) -> dict:
    if not isinstance(value, dict):
        msg = f"`{value.__class__.__name__}` given (value = {value!r})."
        raise ValueError(f"`{name}` should be a dict. {msg}")
    return value


class CliParams(NamedTuple):
    plugins: List[PluginWrapper]
    output_dir: Path = Path(".")
    main_file: str = "__init__.py"
    replacements: Mapping[str, str] = MappingProxyType({})
    loglevel: int = logging.WARNING
    tool: Sequence[str] = ()
    store: str = ""


def parser_spec(
    plugins: Sequence[PluginProtocol],
) -> Dict[str, dict]:
    common = ("version", "enable", "disable", "verbose", "very_verbose")
    cli_spec = cli.__meta__(plugins)
    meta = {k: v.copy() for k, v in META.items()}
    meta.update({k: cli_spec[k].copy() for k in common})
    return meta


def run(args: Sequence[str] = ()) -> int:
    args = args if args else sys.argv[1:]
    cmd = f"python -m {__package__} " + arg_join(args)
    plugins = list_plugins_from_entry_points()
    desc = 'Generate files for "pre-compiling" `validate-pyproject`'
    prms = cli.parse_args(args, plugins, desc, parser_spec, CliParams)
    cli.setup_logging(prms.loglevel)

    tool_plugins: List[PluginProtocol] = [RemotePlugin.from_str(t) for t in prms.tool]
    if prms.store:
        tool_plugins.extend(load_store(prms.store))

    pre_compile(
        prms.output_dir,
        prms.main_file,
        cmd,
        prms.plugins,
        prms.replacements,
        extra_plugins=tool_plugins,
    )
    return 0


main = cli.exceptions2exit()(run)


if __name__ == "__main__":
    main()
