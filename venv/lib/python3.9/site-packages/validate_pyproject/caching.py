# This module is intentionally kept minimal,
# so that it can be imported without triggering imports outside stdlib.
import hashlib
import io
import logging
import os
from pathlib import Path
from typing import Callable, Optional, Union

PathLike = Union[str, "os.PathLike[str]"]
_logger = logging.getLogger(__name__)


def as_file(
    fn: Callable[[str], io.StringIO],
    arg: str,
    cache_dir: Optional[PathLike] = None,
) -> Union[io.StringIO, io.BufferedReader]:
    """
    Cache the result of calling ``fn(arg)`` into a file inside ``cache_dir``.
    The file name is derived from ``arg``.
    If no ``cache_dir`` is provided, it is equivalent to calling ``fn(arg)``.
    The return value can be used as a context.
    """
    cache_path = path_for(arg, cache_dir)
    if not cache_path:
        return fn(arg)

    if cache_path.exists():
        _logger.debug(f"Using cached {arg} from {cache_path}")
    else:
        with fn(arg) as f:
            cache_path.write_text(f.getvalue(), encoding="utf-8")
            _logger.debug(f"Caching {arg} into {cache_path}")

    return open(cache_path, "rb")


def path_for(arbitrary_id: str, cache: Optional[PathLike] = None) -> Optional[Path]:
    cache_dir = cache or os.getenv("VALIDATE_PYPROJECT_CACHE_REMOTE")
    if not cache_dir:
        return None

    escaped = "".join(c if c.isalnum() else "-" for c in arbitrary_id)
    sha1 = hashlib.sha1(arbitrary_id.encode())  # noqa: S324
    # ^-- Non-crypto context and appending `escaped` should minimise collisions
    return Path(os.path.expanduser(cache_dir), f"{sha1.hexdigest()}-{escaped}")
    # ^-- Intentionally uses `os.path` instead of `pathlib` to avoid exception
