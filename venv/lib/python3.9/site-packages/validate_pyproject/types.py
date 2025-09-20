from typing import Callable, Mapping, NewType, TypeVar

T = TypeVar("T", bound=Mapping)

Schema = NewType("Schema", Mapping)
"""JSON Schema represented as a Python dict"""

ValidationFn = Callable[[T], T]
"""Custom validation function.
It should receive as input a mapping corresponding to the whole
``pyproject.toml`` file and raise a :exc:`fastjsonschema.JsonSchemaValueException`
if it is not valid.
"""

FormatValidationFn = Callable[[str], bool]
"""Should return ``True`` when the input string satisfies the format"""

Plugin = Callable[[str], Schema]
"""A plugin is something that receives the name of a `tool` sub-table
(as defined  in PEPPEP621) and returns a :obj:`Schema`.

For example ``plugin("setuptools")`` should return the JSON schema for the
``[tool.setuptools]`` table of a ``pyproject.toml`` file.
"""
