import warnings
from functools import wraps
from inspect import cleandoc
from typing import Any

from ..pre_compile import pre_compile


def _deprecated(orig: Any, repl: Any) -> Any:
    msg = f"""
    `{orig.__module__}:{orig.__name__}` is deprecated and will be removed in future
    versions of `validate-pyproject`.

    Please use `{repl.__module__}:{repl.__name__}` instead.
    """

    @wraps(orig)
    def _wrapper(*args: Any, **kwargs: Any) -> Any:
        warnings.warn(cleandoc(msg), category=DeprecationWarning, stacklevel=2)
        return repl(*args, **kwargs)

    return _wrapper


def vendorify(*args: Any, **kwargs: Any) -> Any:
    return _deprecated(vendorify, pre_compile)(*args, **kwargs)
