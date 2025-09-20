# The code in this module is based on a similar code from `ini2toml` (originally
# published under the MPL-2.0 license)
# https://github.com/abravalheri/ini2toml/blob/49897590a9254646434b7341225932e54f9626a3/LICENSE.txt

# ruff: noqa: C408
# Unnecessary `dict` call (rewrite as a literal)

import argparse
import io
import json
import logging
import sys
from contextlib import contextmanager
from itertools import chain
from textwrap import dedent, wrap
from typing import (
    Callable,
    Dict,
    Generator,
    Iterator,
    List,
    NamedTuple,
    Sequence,
    Tuple,
    Type,
    TypeVar,
)

from . import __version__
from . import _tomllib as tomllib
from .api import Validator
from .errors import ValidationError
from .plugins import PluginProtocol, PluginWrapper
from .plugins import list_from_entry_points as list_plugins_from_entry_points
from .remote import RemotePlugin, load_store

_logger = logging.getLogger(__package__)
T = TypeVar("T", bound=NamedTuple)

_REGULAR_EXCEPTIONS = (ValidationError, tomllib.TOMLDecodeError)


@contextmanager
def critical_logging() -> Generator[None, None, None]:
    """Make sure the logging level is set even before parsing the CLI args"""
    try:
        yield
    except Exception:  # pragma: no cover
        if "-vv" in sys.argv or "--very-verbose" in sys.argv:
            setup_logging(logging.DEBUG)
        raise


_STDIN = argparse.FileType("r")("-")

META: Dict[str, dict] = {
    "version": dict(
        flags=("-V", "--version"),
        action="version",
        version=f"{__package__} {__version__}",
    ),
    "input_file": dict(
        dest="input_file",
        nargs="*",
        # default=[_STDIN],  # postponed to facilitate testing
        type=argparse.FileType("r"),
        help="TOML file to be verified (`stdin` by default)",
    ),
    "enable": dict(
        flags=("-E", "--enable-plugins"),
        nargs="+",
        default=(),
        dest="enable",
        metavar="PLUGINS",
        help="Enable ONLY the given plugins (ALL plugins are enabled by default).",
    ),
    "disable": dict(
        flags=("-D", "--disable-plugins"),
        nargs="+",
        dest="disable",
        default=(),
        metavar="PLUGINS",
        help="Enable ALL plugins, EXCEPT the ones given.",
    ),
    "verbose": dict(
        flags=("-v", "--verbose"),
        dest="loglevel",
        action="store_const",
        const=logging.INFO,
        help="set logging level to INFO",
    ),
    "very_verbose": dict(
        flags=("-vv", "--very-verbose"),
        dest="loglevel",
        action="store_const",
        const=logging.DEBUG,
        help="set logging level to DEBUG",
    ),
    "dump_json": dict(
        flags=("--dump-json",),
        action="store_true",
        help="Print the JSON equivalent to the given TOML",
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


class CliParams(NamedTuple):
    input_file: List[io.TextIOBase]
    plugins: List[PluginWrapper]
    tool: List[str]
    store: str
    loglevel: int = logging.WARNING
    dump_json: bool = False


def __meta__(plugins: Sequence[PluginProtocol]) -> Dict[str, dict]:
    """'Hyper parameters' to instruct :mod:`argparse` how to create the CLI"""
    meta = {k: v.copy() for k, v in META.items()}
    meta["enable"]["choices"] = {p.tool for p in plugins}
    meta["input_file"]["default"] = [_STDIN]  # lazily defined to facilitate testing
    return meta


@critical_logging()
def parse_args(
    args: Sequence[str],
    plugins: Sequence[PluginProtocol],
    description: str = "Validate a given TOML file",
    get_parser_spec: Callable[[Sequence[PluginProtocol]], Dict[str, dict]] = __meta__,
    params_class: Type[T] = CliParams,  # type: ignore[assignment]
) -> T:
    """Parse command line parameters

    Args:
      args: command line parameters as list of strings (for example  ``["--help"]``).

    Returns: command line parameters namespace
    """
    epilog = ""
    if plugins:
        epilog = f"The following plugins are available:\n\n{plugins_help(plugins)}"

    parser = argparse.ArgumentParser(
        description=description, epilog=epilog, formatter_class=Formatter
    )
    for cli_opts in get_parser_spec(plugins).values():
        parser.add_argument(*cli_opts.pop("flags", ()), **cli_opts)

    parser.set_defaults(loglevel=logging.WARNING)
    params = vars(parser.parse_args(args))
    enabled = params.pop("enable", ())
    disabled = params.pop("disable", ())
    params["tool"] = params["tool"] or []
    params["store"] = params["store"] or ""
    params["plugins"] = select_plugins(plugins, enabled, disabled)
    return params_class(**params)  # type: ignore[call-overload, no-any-return]


Plugins = TypeVar("Plugins", bound=PluginProtocol)


def select_plugins(
    plugins: Sequence[Plugins],
    enabled: Sequence[str] = (),
    disabled: Sequence[str] = (),
) -> List[Plugins]:
    available = list(plugins)
    if enabled:
        available = [p for p in available if p.tool in enabled]
    if disabled:
        available = [p for p in available if p.tool not in disabled]
    return available


def setup_logging(loglevel: int) -> None:
    """Setup basic logging

    Args:
      loglevel: minimum loglevel for emitting messages
    """
    logformat = "[%(levelname)s] %(message)s"
    logging.basicConfig(level=loglevel, stream=sys.stderr, format=logformat)


@contextmanager
def exceptions2exit() -> Generator[None, None, None]:
    try:
        yield
    except _ExceptionGroup as group:
        for prefix, ex in group:
            print(prefix)
            _logger.error(str(ex) + "\n")
        raise SystemExit(1) from None
    except _REGULAR_EXCEPTIONS as ex:
        _logger.error(str(ex))
        raise SystemExit(1) from None
    except Exception as ex:  # pragma: no cover
        _logger.error(f"{ex.__class__.__name__}: {ex}\n")
        _logger.debug("Please check the following information:", exc_info=True)
        raise SystemExit(1) from None


def run(args: Sequence[str] = ()) -> int:
    """Wrapper allowing :obj:`Translator` to be called in a CLI fashion.

    Instead of returning the value from :func:`Translator.translate`, it prints the
    result to the given ``output_file`` or ``stdout``.

    Args:
      args (List[str]): command line parameters as list of strings
          (for example  ``["--verbose", "setup.cfg"]``).
    """
    args = args or sys.argv[1:]
    plugins = list_plugins_from_entry_points()
    params: CliParams = parse_args(args, plugins)
    setup_logging(params.loglevel)
    tool_plugins = [RemotePlugin.from_str(t) for t in params.tool]
    if params.store:
        tool_plugins.extend(load_store(params.store))
    validator = Validator(params.plugins, extra_plugins=tool_plugins)

    exceptions = _ExceptionGroup()
    for file in params.input_file:
        try:
            _run_on_file(validator, params, file)
        except _REGULAR_EXCEPTIONS as ex:
            exceptions.add(f"Invalid {_format_file(file)}", ex)

    exceptions.raise_if_any()

    return 0


def _run_on_file(validator: Validator, params: CliParams, file: io.TextIOBase) -> None:
    if file in (sys.stdin, _STDIN):
        print("Expecting input via `stdin`...", file=sys.stderr, flush=True)

    toml_equivalent = tomllib.loads(file.read())
    validator(toml_equivalent)
    if params.dump_json:
        print(json.dumps(toml_equivalent, indent=2))
    else:
        print(f"Valid {_format_file(file)}")


main = exceptions2exit()(run)


class Formatter(argparse.RawTextHelpFormatter):
    # Since the stdlib does not specify what is the signature we need to implement in
    # order to create our own formatter, we are left no choice other then overwrite a
    # "private" method considered to be an implementation detail.

    def _split_lines(self, text: str, width: int) -> List[str]:
        return list(chain.from_iterable(wrap(x, width) for x in text.splitlines()))


def plugins_help(plugins: Sequence[PluginProtocol]) -> str:
    return "\n".join(_format_plugin_help(p) for p in plugins)


def _flatten_str(text: str) -> str:
    text = " ".join(x.strip() for x in dedent(text).splitlines()).strip()
    text = text.rstrip(".,;").strip()
    return (text[0].lower() + text[1:]).strip()


def _format_plugin_help(plugin: PluginProtocol) -> str:
    help_text = plugin.help_text
    help_text = f": {_flatten_str(help_text)}" if help_text else ""
    return f"* {plugin.tool!r}{help_text}"


def _format_file(file: io.TextIOBase) -> str:
    if hasattr(file, "name") and file.name:
        return f"file: {file.name}"
    return "file"  # pragma: no cover


class _ExceptionGroup(Exception):
    _members: List[Tuple[str, Exception]]

    def __init__(self) -> None:
        self._members = []
        super().__init__()

    def add(self, prefix: str, ex: Exception) -> None:
        self._members.append((prefix, ex))

    def __iter__(self) -> Iterator[Tuple[str, Exception]]:
        return iter(self._members)

    def raise_if_any(self) -> None:
        number = len(self._members)
        if number == 1:
            print(self._members[0][0])
            raise self._members[0][1]
        if number > 0:
            raise self
