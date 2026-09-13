# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2026, Chris Caron <lead2gold@gmail.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
"""Support ``${NAME}`` variables in YAML configuration URLs.

Declared variables are replaced with safe placeholders while the URL is
parsed. Their values are then applied to the parsed fields.
"""

from __future__ import annotations

import os
import re
import secrets
from typing import Any, Optional

from ..exception import AppriseTemplateError

# Prefix used to look a variable up in the environment.  A variable
# named "target" is read from APPRISE_TEMPLATE_TARGET.
TEMPLATE_ENV_PREFIX = "APPRISE_TEMPLATE_"

# Longest variable name we accept
TEMPLATE_NAME_MAXLEN = 32

# Longest value a variable may resolve to
MAX_TEMPLATE_VALUE_LEN = 1024

# Longest URL we will build once every value has been filled in
MAX_RESOLVED_URL_LEN = 8192

# One definition of what a name may look like, so the bound above is the
# only place the limit is written down.
TEMPLATE_NAME_PATTERN = r"[A-Za-z0-9_]{1," + str(TEMPLATE_NAME_MAXLEN) + r"}"

# Match ${NAME}. The fixed-length name pattern avoids costly backtracking.
TEMPLATE_VAR_RE = re.compile(r"\$\{(?P<name>" + TEMPLATE_NAME_PATTERN + r")\}")

# A standalone check for a variable name on its own.
#
# "\Z" rather than "$": a "$" also matches just before a trailing newline,
# which would let "token\n" pass as a name and carry a line break into a
# log entry.
TEMPLATE_NAME_RE = re.compile(r"\A" + TEMPLATE_NAME_PATTERN + r"\Z")

# Characters a value may never contain.  These would let a value break
# out of a log line or an HTTP header.
INVALID_VALUE_RE = re.compile(r"[\x00-\x1f\x7f\u2028\u2029]")

# Placeholders are built as a<random-prefix>t<index>z.
PLACEHOLDER_VAR = "t"

# How many times to try for a placeholder prefix that does not already
# appear in the configuration before giving up
PLACEHOLDER_ATTEMPTS = 8


def normalize_name(name: str) -> str:
    """Return the form of a variable name used for lookups.

    Names are matched without regard to case, so TARGET, Target and
    target all refer to the same variable.
    """
    return name.lower()


def validate_value(name: str, value: Any) -> str:
    """Check a supplied value and return it as a string.

    Accepts strings and plain numbers or booleans, which are converted
    to text.  Anything else, along with an over-long value or one
    holding control characters, is rejected.
    """

    if isinstance(value, bool):
        # Handled before the number check below; in Python a bool is
        # also an int, and "True" reads better than "1" here.
        value = "yes" if value else "no"

    elif isinstance(value, (int, float)):
        value = str(value)

    if not isinstance(value, str):
        raise AppriseTemplateError(
            "Template variable '{}' must be text.".format(name),
            variable=name,
        )

    if len(value) > MAX_TEMPLATE_VALUE_LEN:
        raise AppriseTemplateError(
            "Template variable '{}' exceeds {} characters.".format(
                name, MAX_TEMPLATE_VALUE_LEN
            ),
            variable=name,
        )

    if INVALID_VALUE_RE.search(value):
        raise AppriseTemplateError(
            "Template variable '{}' contains a control character.".format(
                name
            ),
            variable=name,
        )

    return value


class TemplateVariable:
    """One variable declared in a ``template:`` section."""

    __slots__ = ("default", "name")

    def __init__(self, name: str, default: Optional[str] = None):
        """Store the normalized name and its optional fallback value."""
        # Names are normalized by TemplateSchema before reaching this class.
        self.name = name

        # None marks a required value; an empty string is a valid default.
        self.default = default

    @property
    def required(self) -> bool:
        """A variable with no default must always be supplied."""
        return self.default is None

    def __repr__(self) -> str:
        """Show the variable name and whether a value is required."""
        return "<TemplateVariable {} required={}>".format(
            self.name, self.required
        )


class TemplateSchema:
    """Every variable a configuration declares."""

    __slots__ = ("variables",)

    def __init__(self, variables: Optional[dict] = None):
        """Create a schema from an optional normalized variable mapping."""
        # Use a new mapping when no declarations were provided.
        self.variables = variables if variables is not None else {}

    @staticmethod
    def parse(entries: Any) -> TemplateSchema:
        """Read a ``template:`` section into a schema.

        Two layouts are accepted and mean the same thing:

        - a list of ``- name`` or ``- name: default`` entries
        - a mapping of ``name: default`` entries

        In both cases a variable written without a value is mandatory
        and must be supplied before the URL using it can load.
        """

        variables = {}

        if isinstance(entries, dict):
            # name: default
            items = list(entries.items())

        elif isinstance(entries, (list, tuple)):
            items = []
            for entry in entries:
                if isinstance(entry, str):
                    # A bare "- name"; mandatory
                    items.append((entry, None))

                elif isinstance(entry, dict):
                    items.extend(entry.items())

                else:
                    raise AppriseTemplateError(
                        "Invalid template declaration entry."
                    )

        else:
            raise AppriseTemplateError(
                "The template section must be a list or a mapping."
            )

        for name, default in items:
            if not isinstance(name, str) or not TEMPLATE_NAME_RE.match(name):
                raise AppriseTemplateError(
                    "Invalid template variable name {!r}.".format(name)
                )

            key = normalize_name(name)
            if key in variables:
                raise AppriseTemplateError(
                    "Template variable '{}' is declared more than"
                    " once.".format(key),
                    variable=key,
                )

            if default is not None:
                default = validate_value(key, default)

            variables[key] = TemplateVariable(key, default)

        return TemplateSchema(variables)

    @property
    def names(self) -> tuple:
        """Return all declared names in their stored order."""
        return tuple(self.variables)

    @property
    def required(self) -> tuple:
        """Return names that have no default value."""
        return tuple(k for k, v in self.variables.items() if v.required)

    def __contains__(self, name: str) -> bool:
        """Match a declared name without regard to case."""
        return normalize_name(name) in self.variables

    def __bool__(self) -> bool:
        """Report whether the schema declares at least one variable."""
        return bool(self.variables)


class TemplatePlaceholderMap:
    """Swap declared variables for parse-safe placeholders and back.

    A placeholder is a short run of letters and digits, which is legal
    anywhere in a URL.  Swapping it in lets the URL parse normally
    even though the real value is not known yet.
    """

    def __init__(self, schema: TemplateSchema, content: str = ""):
        """Create a placeholder map that avoids text already in the file."""
        # The schema decides which ${NAME} markers belong to this template.
        self.schema = schema

        # Map each generated placeholder back to its variable name.
        self.placeholders = {}

        # Reuse one placeholder whenever the same name appears again.
        self._vars = {}

        # Avoid placeholders that already appear in the configuration.
        self.nonce = None
        for _ in range(PLACEHOLDER_ATTEMPTS):
            nonce = secrets.token_hex(8)
            if "a{}".format(nonce) not in content:
                self.nonce = nonce
                break

        if self.nonce is None:
            raise AppriseTemplateError(
                "Could not prepare template variable placeholders."
            )

    def _placeholder(self, name: str) -> str:
        """Return one reusable placeholder for a variable name."""
        if name not in self._vars:
            token = "a{}{}{}z".format(
                self.nonce, PLACEHOLDER_VAR, len(self._vars)
            )
            self._vars[name] = token
            self.placeholders[token] = name

        return self._vars[name]

    def encode(self, text: Any) -> Any:
        """Replace declared variables.

        Undeclared markers remain unchanged.
        """

        if not isinstance(text, str) or "${" not in text:
            return text

        def replace(match):
            name = normalize_name(match.group("name"))
            if name not in self.schema.variables:
                # Not ours; hand back exactly what was matched
                return match.group(0)

            return self._placeholder(name)

        # One pass only.  re.sub never looks at what it just wrote, so
        # a value can not be expanded a second time.
        return TEMPLATE_VAR_RE.sub(replace, text)

    def encode_obj(self, obj: Any, memo: Optional[dict] = None) -> Any:
        """Replace variables in YAML values without changing setting names."""
        return self._walk(obj, self.encode, memo)

    def _walk(
        self,
        obj: Any,
        fn,
        memo: Optional[dict] = None,
    ) -> Any:
        """Rebuild a nested value, running ``fn`` over each string."""

        if isinstance(obj, str):
            # Leaf strings are the only values that can hold placeholders.
            return fn(obj)

        if not isinstance(obj, (list, tuple, set, dict)):
            # Numbers, flags, None, and custom scalars pass through unchanged.
            return obj

        if memo is None:
            # One memo preserves aliases and identifies recursive structures.
            memo = {}

        marker = id(obj)
        if marker in memo:
            if memo[marker] is None:
                # Reject YAML loops instead of following them forever.
                raise AppriseTemplateError(
                    "Looping structure found in configuration."
                )
            return memo[marker]

        memo[marker] = None

        if isinstance(obj, dict):
            # Mapping keys are deliberately preserved; only values are walked.
            result = {k: self._walk(v, fn, memo) for k, v in obj.items()}

        elif isinstance(obj, set):
            # Preserve the collection type while rebuilding its members.
            result = {self._walk(v, fn, memo) for v in obj}

        else:
            # Lists and tuples share traversal but keep their original type.
            built = [self._walk(v, fn, memo) for v in obj]
            result = tuple(built) if isinstance(obj, tuple) else built

        memo[marker] = result
        return result

    @property
    def pattern(self) -> re.Pattern:
        """A regex matching any placeholder this map handed out."""
        if not hasattr(self, "_pattern"):
            # The random nonce limits matches to this configuration instance.
            self._pattern = re.compile(
                r"a{}{}\d+z".format(re.escape(self.nonce), PLACEHOLDER_VAR)
            )
        return self._pattern

    def used(self, obj: Any) -> set:
        """Return the variable names a parsed entry still needs."""

        found = set()

        def collect(text):
            # The pattern only ever matches placeholders this map handed
            # out, so every hit is one it knows.
            for token in self.pattern.finditer(text):
                found.add(self.placeholders[token.group(0)])
            return text

        self._walk(obj, collect)
        return found

    def keys_contain_placeholder(self, obj: Any, memo=None) -> Optional[str]:
        """Return a variable used as a setting name, if any."""

        if memo is None:
            # Object identities stop aliases and loops from being revisited.
            memo = set()

        if not isinstance(obj, dict):
            if isinstance(obj, (list, tuple, set)):
                for item in obj:
                    name = self.keys_contain_placeholder(item, memo)
                    if name:
                        return name
            return None

        marker = id(obj)
        if marker in memo:
            return None
        memo.add(marker)

        for key, value in obj.items():
            # A placeholder in a key would let a caller choose a setting name.
            if isinstance(key, str):
                match = self.pattern.search(key)
                if match:
                    return self.placeholders[match.group(0)]

            name = self.keys_contain_placeholder(value, memo)
            if name:
                return name

        return None

    def display(self, text: Any) -> Any:
        """Put ``${NAME}`` back in place of a placeholder."""

        if not isinstance(text, str):
            return text

        def replace(match):
            return "${{{}}}".format(self.placeholders[match.group(0)].upper())

        return self.pattern.sub(replace, text)

    def substitute(self, obj: Any, values: dict) -> Any:
        """Drop the real values in where the placeholders sit."""

        def value_for(token):
            return values[self.placeholders[token.group(0)]]

        def replace_one(match):
            return value_for(match)

        def replace(text):
            # Only the original text is scanned.  A value that happens
            # to look like a placeholder is left alone.
            return self.pattern.sub(replace_one, text)

        if isinstance(obj, dict):
            # Substitute every parsed field without filtering its characters.
            # The configuration author chooses the URL position and accepts
            # that position's normal service-specific meaning.
            result = {
                key: self._walk(item, replace) for key, item in obj.items()
            }

            # A marker owning the whole authority may use the familiar
            # user@host form without reparsing any other URL content.
            host_token = self.pattern.fullmatch(obj.get("host") or "")
            if host_token and not obj.get("user") and not obj.get("password"):
                authority = value_for(host_token)
                if "@" in authority:
                    credentials, hostname = authority.rsplit("@", 1)
                    if credentials and hostname:
                        if ":" in credentials:
                            result["user"], result["password"] = (
                                credentials.split(":", 1)
                            )
                        else:
                            result["user"] = credentials
                        result["host"] = hostname

            # The matching whole-user form accepts user or user:pass.
            user_token = self.pattern.fullmatch(obj.get("user") or "")
            if user_token and not obj.get("password"):
                credentials = value_for(user_token)
                if ":" in credentials:
                    result["user"], result["password"] = credentials.split(
                        ":", 1
                    )

            return result

        return self._walk(obj, replace)


def resolve_values(
    schema: TemplateSchema,
    overrides: Optional[dict] = None,
    environ: Optional[dict] = None,
    names: Optional[set] = None,
) -> dict:
    """Resolve requested variables by precedence.

    Each variable is looked for in this order:

    - a value handed in directly for this call
    - the ``APPRISE_TEMPLATE_<NAME>`` environment variable
    - the default written in the configuration

    Use ``names`` to resolve only one entry's variables, or ``environ={}`` to
    disable environment lookups. Missing required values raise an error.
    """

    if environ is None:
        # Read the process environment unless the caller supplied an override.
        environ = os.environ

    # Names handed in are matched without regard to case
    supplied = {}
    for key, value in (overrides or {}).items():
        if not isinstance(key, str) or not TEMPLATE_NAME_RE.match(key):
            raise AppriseTemplateError(
                "Invalid template variable name {!r}.".format(key)
            )

        name = normalize_name(key)
        if name not in schema.variables:
            # One mapping can serve several configurations. This entry simply
            # ignores names it does not use.
            continue

        supplied[name] = validate_value(name, value)

    results = {}
    for name, variable in schema.variables.items():
        # An entry resolves only the names it actually contains.
        if names is not None and name not in names:
            continue

        if name in supplied:
            # Call-specific input has the highest priority.
            results[name] = supplied[name]
            continue

        value = environ.get(TEMPLATE_ENV_PREFIX + name.upper())
        if value:
            # Environment values provide deployment-wide defaults.
            results[name] = validate_value(name, value)
            continue

        if variable.default is not None:
            # The declaration default is the final available source.
            results[name] = variable.default
            continue

        raise AppriseTemplateError(
            "No value available for template variable '{}'.".format(name),
            variable=name,
        )

    return results
