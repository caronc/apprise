from typing import Any

from ..pre_compile import cli
from . import _deprecated


def run(*args: Any, **kwargs: Any) -> Any:
    return _deprecated(run, cli.run)(*args, **kwargs)


def main(*args: Any, **kwargs: Any) -> Any:
    return _deprecated(run, cli.main)(*args, **kwargs)
