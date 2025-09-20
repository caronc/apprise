import json
import logging
import typing
import urllib.parse
from typing import Generator, Optional, Tuple

from . import caching, errors, http
from .types import Schema

if typing.TYPE_CHECKING:
    import sys

    if sys.version_info < (3, 11):
        from typing_extensions import Self
    else:
        from typing import Self


__all__ = ["RemotePlugin", "load_store"]


_logger = logging.getLogger(__name__)


def load_from_uri(
    tool_uri: str, cache_dir: Optional[caching.PathLike] = None
) -> Tuple[str, Schema]:
    tool_info = urllib.parse.urlparse(tool_uri)
    if tool_info.netloc:
        url = f"{tool_info.scheme}://{tool_info.netloc}{tool_info.path}"
        download = caching.as_file(http.open_url, url, cache_dir)
        with download as f:
            contents = json.load(f)
    else:
        with open(tool_info.path, "rb") as f:
            contents = json.load(f)
    return tool_info.fragment, contents


class RemotePlugin:
    def __init__(self, *, tool: str, schema: Schema, fragment: str = ""):
        self.tool = tool
        self.schema = schema
        self.fragment = fragment
        self.id = self.schema["$id"]
        self.help_text = f"{tool} <external>"

    @classmethod
    def from_url(cls, tool: str, url: str) -> "Self":
        fragment, schema = load_from_uri(url)
        return cls(tool=tool, schema=schema, fragment=fragment)

    @classmethod
    def from_str(cls, tool_url: str) -> "Self":
        tool, _, url = tool_url.partition("=")
        if not url:
            raise errors.URLMissingTool(tool)
        return cls.from_url(tool, url)


def load_store(pyproject_url: str) -> Generator[RemotePlugin, None, None]:
    """
    Takes a URL / Path and loads the tool table, assuming it is a set of ref's.
    Currently ignores "inline" sections. This is the format that SchemaStore
    (https://json.schemastore.org/pyproject.json) is in.
    """

    fragment, contents = load_from_uri(pyproject_url)
    if fragment:
        _logger.error(
            f"Must not be called with a fragment, got {fragment!r}"
        )  # pragma: no cover
    table = contents["properties"]["tool"]["properties"]
    for tool, info in table.items():
        if tool in {"setuptools", "distutils"}:
            pass  # built-in
        elif "$ref" in info:
            _logger.info(f"Loading {tool} from store: {pyproject_url}")
            rp = RemotePlugin.from_url(tool, info["$ref"])
            yield rp
            for values in rp.schema["properties"].values():
                url = values.get("$ref", "")
                if url.startswith(("https://", "https://")):
                    yield RemotePlugin.from_url("", url)
        else:
            _logger.warning(f"{tool!r} does not contain $ref")  # pragma: no cover


if typing.TYPE_CHECKING:
    from .plugins import PluginProtocol

    _: PluginProtocol = typing.cast("RemotePlugin", None)
