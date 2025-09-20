import sys

try:  # pragma: no cover
    if sys.version_info[:2] >= (3, 11):
        from tomllib import TOMLDecodeError, loads
    else:
        from tomli import TOMLDecodeError, loads
except ImportError:  # pragma: no cover
    try:
        from toml import (  # type: ignore[no-redef,import-untyped]
            TomlDecodeError as TOMLDecodeError,
        )
        from toml import loads  # type: ignore[no-redef]
    except ImportError as ex:
        raise ImportError("Please install `tomli` (TOML parser)") from ex


__all__ = [
    "TOMLDecodeError",
    "loads",
]
