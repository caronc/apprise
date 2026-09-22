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


"""Static checks on how plugins use delivery tracking.

These read the plugin sources instead of running them, so a new plugin
that picks up one of the mistakes already found in the fleet is caught
the moment it is added:

- marking a target while a payload is still being built (a generator)
  or while the plugin is still being set up (``__init__``)
- a ``mark_delivered()`` placed after a ``continue`` where it can never
  run
- asking ``is_delivered()`` without ever marking anything, or the other
  way around
"""

# Disable logging for a cleaner testing output
import ast
import logging
import os

logging.disable(logging.CRITICAL)

# Where the plugins live
PLUGIN_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "apprise",
    "plugins",
)

# The two calls being looked for
TRACKERS = ("is_delivered", "mark_delivered")


def _plugins():
    """Yield (name, parsed module) for every plugin file."""
    for root, _dirs, files in os.walk(PLUGIN_DIR):
        for fname in sorted(files):
            if not fname.endswith(".py"):
                continue

            path = os.path.join(root, fname)
            with open(path, encoding="utf-8") as f:
                yield (
                    os.path.relpath(path, PLUGIN_DIR),
                    ast.parse(f.read(), filename=path),
                )


def _tracker(node):
    """Return the tracking call a statement makes, or None."""
    if not isinstance(node, ast.Call):
        return None

    func = node.func
    return (
        func.attr
        if isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == "self"
        and func.attr in TRACKERS
        else None
    )


def _scan():
    """Walk every plugin once and collect anything that looks wrong."""

    built = []
    unreachable = []
    lonely = []

    for name, tree in _plugins():
        used = set()

        for node in ast.walk(tree):
            called = _tracker(node)
            if called:
                used.add(called)

            # A mark that sits after a continue/break/return in the same
            # block can never run
            body = getattr(node, "body", None)
            if isinstance(body, list):
                stop = None
                for statement in body:
                    if stop and any(
                        _tracker(child) == "mark_delivered"
                        for child in ast.walk(statement)
                    ):
                        unreachable.append(
                            f"{name}:{statement.lineno} marks a target"
                            f" after the {stop[0]} on line {stop[1]}"
                        )

                    if isinstance(
                        statement, (ast.Continue, ast.Break, ast.Return)
                    ):
                        stop = (
                            type(statement).__name__.lower(),
                            statement.lineno,
                        )

            # Where the mark lives matters too
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                marks = [
                    child
                    for child in ast.walk(node)
                    if _tracker(child) == "mark_delivered"
                ]
                if not marks:
                    continue

                if node.name == "__init__":
                    built.append(
                        f"{name}:{marks[0].lineno} marks a target from"
                        " __init__(), before anything is sent"
                    )

                elif any(
                    isinstance(child, (ast.Yield, ast.YieldFrom))
                    for child in ast.walk(node)
                ):
                    built.append(
                        f"{name}:{marks[0].lineno} marks a target inside"
                        f" the generator {node.name}(), while the payload"
                        " is still being built"
                    )

        if used and used != set(TRACKERS):
            lonely.append(
                f"{name} uses {sorted(used)[0]}() on its own; a target is"
                " either never skipped or never recorded"
            )

    return built, unreachable, lonely


# Scanned once for the whole module
BUILT, UNREACHABLE, LONELY = _scan()


def test_targets_are_not_marked_while_a_payload_is_built():
    """Marking belongs in the loop that sends, nowhere else."""

    assert not BUILT, "\n".join(BUILT)


def test_marking_a_target_is_reachable():
    """A mark placed after a continue can never run."""

    assert not UNREACHABLE, "\n".join(UNREACHABLE)


def test_asking_and_marking_go_together():
    """A plugin that asks also marks, and one that marks also asks."""

    assert not LONELY, "\n".join(LONELY)
