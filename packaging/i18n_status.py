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


"""Report the state of every Apprise translation catalog.

Run it from the repository root:

    python packaging/i18n_status.py

Every language Apprise ships is listed with the number of strings it still
needs.  Each of those strings is then printed as a bullet so anyone can pick
a language up and start filling the gaps in.
"""

from __future__ import annotations

import argparse
from os.path import abspath, basename, dirname, isfile, join
import re
import sys
from typing import Optional

# The package our translatable strings are extracted from
PACKAGE_DIR = abspath(join(dirname(__file__), "..", "apprise"))

# Where our translations live
I18N_DIR = join(PACKAGE_DIR, "i18n")

# Our translation template. It is a build artifact rather than something the
# repository keeps, so it is only a fallback for reading our strings.
POT_FILE = join(I18N_DIR, "apprise.pot")

# The catalog filename found inside each language directory
CATALOG = join("LC_MESSAGES", "apprise.po")

# Matches the start of a msgid or msgstr line, and a quoted continuation of
# either; a PO file is free to wrap long strings over several lines
RE_ENTRY = re.compile(r'^(?P<key>msgid|msgstr)\s+"(?P<value>.*)"$')
RE_CONTINUATION = re.compile(r'^"(?P<value>.*)"$')

# What a backslash stands for inside a PO string. Anything else following a
# backslash is simply the character itself.
PO_ESCAPES = {
    "\\": "\\",
    '"': '"',
    "n": "\n",
    "r": "\r",
    "t": "\t",
}

# A backslash and whatever it escapes
RE_ESCAPE = re.compile(r"\\(.)")

# A plural entry, which Apprise has none of.  Reading one as an ordinary
# entry would report it wrongly, so it is stepped over.
RE_UNSUPPORTED = re.compile(r"^(msgid_plural|msgstr\[)")


class Catalog:
    """One language and the state of each string in it."""

    __slots__ = ("fuzzy", "language", "missing", "translated")

    def __init__(self, language: str) -> None:
        """Prepare an empty report for ``language``."""
        # The 2 letter language code, which is also its directory name
        self.language = language

        # Strings that have a translation we can use
        self.translated = []

        # Strings with no translation at all
        self.missing = []

        # Strings a tool guessed at; they need a human to confirm them
        self.fuzzy = []

    @property
    def complete(self) -> bool:
        """True when nothing is left to translate or confirm."""
        # A catalog is only done once both lists are empty.
        return not self.missing and not self.fuzzy


def unescape(value: str) -> str:
    """Return ``value`` with its PO escaping removed."""
    # One left to right pass, so an escaped backslash is not mistaken for the
    # start of the escape that follows it.
    return RE_ESCAPE.sub(
        lambda result: PO_ESCAPES.get(result.group(1), result.group(1)),
        value,
    )


class Entry:
    """One entry as it is read out of a catalog."""

    __slots__ = ("fuzzy", "msgid", "msgstr", "skip")

    def __init__(self) -> None:
        """Start an empty entry."""
        # The English source text and the translation given for it
        self.msgid = ""
        self.msgstr = ""

        # Whether a tool guessed at this entry rather than a person writing it
        self.fuzzy = False

        # Whether this is an entry shape we do not report on at all
        self.skip = False


def read_catalog(path: str) -> tuple[dict[str, str], set[str]]:
    """Return the translations in ``path`` and the fuzzy msgids among them."""
    translations = {}
    fuzzy = set()

    # The entry being read, and which of its two halves we are collecting
    entry = Entry()
    key = None

    # Flags read ahead of the next msgid; they belong to that entry, not to
    # the one we may still be holding on to
    pending_fuzzy = False
    pending_skip = False

    def store() -> None:
        """Keep the entry we just finished reading."""
        nonlocal entry, key
        if entry.msgid and not entry.skip:
            translations[entry.msgid] = entry.msgstr
            if entry.fuzzy:
                fuzzy.add(entry.msgid)

        entry = Entry()
        key = None

    with open(path, encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if line.startswith("#~"):
                # An obsolete entry; it is no longer in the template
                continue

            if line.startswith("#,") and "fuzzy" in line:
                # The entry below this needs a human to look at it
                pending_fuzzy = True
                continue

            if line.startswith("#"):
                # A comment, such as the source file the string came from
                continue

            if line.startswith("msgctxt"):
                # A context belongs to the entry below this one
                pending_skip = True
                continue

            if RE_UNSUPPORTED.match(line):
                # A plural entry; Apprise has none, and reading one as an
                # ordinary entry would report it wrongly
                entry.skip = True
                continue

            result = RE_ENTRY.match(line)
            if result:
                if result.group("key") == "msgid":
                    # A new entry begins here, and it owns whatever we read
                    # ahead of it
                    store()
                    entry.fuzzy = pending_fuzzy
                    entry.skip = pending_skip
                    pending_fuzzy = pending_skip = False

                key = result.group("key")
                setattr(entry, key, unescape(result.group("value")))
                continue

            result = RE_CONTINUATION.match(line) if key else None
            if result:
                # A long string wrapped onto another line
                setattr(
                    entry,
                    key,
                    getattr(entry, key) + unescape(result.group("value")),
                )
                continue

            if not line:
                # A blank line closes the entry
                store()

    store()
    return (translations, fuzzy)


def languages() -> list[str]:
    """Return every language Apprise ships a catalog for."""
    # Each language is a directory holding an LC_MESSAGES/apprise.po file.
    from glob import glob

    return sorted(
        basename(dirname(dirname(path)))
        for path in glob(join(I18N_DIR, "*", CATALOG))
    )


def extract() -> Optional[list[str]]:
    """Return every translatable string found in the Apprise source.

    None comes back when Babel is not installed.  This is the only list that
    can not go stale, so it is preferred over anything on disk.
    """
    try:
        from babel.messages.extract import extract_from_dir

    except ImportError:
        # Babel ships with our development requirements, but the report is
        # still useful without it
        return None

    msgids = []
    seen = set()
    for _filename, _lineno, message, _comments, _context in extract_from_dir(
        PACKAGE_DIR, method_map=[("**.py", "python")]
    ):
        # A message is a string on its own, or a tuple when it has plural
        # forms; only the singular is what Apprise asks us to translate
        msgid = message[0] if isinstance(message, tuple) else message
        if msgid and msgid not in seen:
            seen.add(msgid)
            msgids.append(msgid)

    return msgids


def reference() -> tuple[list[str], str]:
    """Return every string Apprise can translate, and where it came from.

    The source is read directly when Babel is available.  The template is
    the fallback; it is built by ``tox -e i18n`` and is not kept in the
    repository, so it can be absent or out of date.
    """
    msgids = extract()
    if msgids is not None:
        return (msgids, "source")

    if isfile(POT_FILE):
        template, _ = read_catalog(POT_FILE)
        return (list(template), "template")

    return ([], "")


def inspect(language: str, msgids: list[str]) -> Catalog:
    """Measure ``language`` against the strings in ``msgids``."""
    catalog = Catalog(language)
    translations, fuzzy = read_catalog(join(I18N_DIR, language, CATALOG))
    for msgid in msgids:
        if msgid in fuzzy or not translations.get(msgid):
            # Nothing usable; a fuzzy entry is a guess, not a translation
            target = catalog.fuzzy if msgid in fuzzy else catalog.missing
            target.append(msgid)
            continue

        catalog.translated.append(msgid)

    return catalog


def main() -> int:
    """Print our report and return the exit code to finish with."""
    parser = argparse.ArgumentParser(
        description=(
            "Report which Apprise translations are complete and list the"
            " strings the rest are still waiting on."
        ),
    )
    parser.add_argument(
        "-l",
        "--language",
        action="append",
        metavar="CODE",
        help=("only report on this language; may be used more than once"),
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="print the summary only, leaving the missing strings out",
    )
    parser.add_argument(
        "-s",
        "--strict",
        action="store_true",
        help="exit with an error when anything is left to translate",
    )
    args = parser.parse_args()

    # Work out which languages we were asked about
    available = languages()
    requested = args.language if args.language else available
    unknown = [
        language
        for language in requested
        if not isfile(join(I18N_DIR, language, CATALOG))
    ]
    if unknown:
        print(
            "No translation exists for: " + ", ".join(unknown),
            file=sys.stderr,
        )
        return 1

    if not available:
        print(
            f"No translations were found under {I18N_DIR}.",
            file=sys.stderr,
        )
        return 1

    # Every string Apprise can translate, read from the source where we can
    msgids, origin = reference()
    if not msgids:
        print(
            "No translatable strings were found; install Babel, or run"
            " `tox -e i18n` to build the translation template.",
            file=sys.stderr,
        )
        return 1

    if origin != "source" and args.strict:
        # Nothing on disk can certify that a catalog is complete; only the
        # source can, and reading it needs Babel
        print(
            "Babel is required to check completeness against the source;"
            " install it, or drop --strict to report on"
            " apprise/i18n/apprise.pot instead.",
            file=sys.stderr,
        )
        return 1

    print(f"Apprise translations ({len(msgids)} strings per language)")
    if origin == "template":
        # The template is a file on disk and may predate the source
        print(
            "Measured against apprise/i18n/apprise.pot; install Babel, or"
            " run `tox -e i18n`, to measure against the source itself."
        )

    print("")

    catalogs = [inspect(language, msgids) for language in requested]

    # The summary first, so the overall state is visible at a glance
    for catalog in catalogs:
        done = len(catalog.translated)
        percent = 100.0 * done / len(msgids) if msgids else 100.0
        state = "complete" if catalog.complete else "needs help"
        print(
            f"  {catalog.language:<6} {done:>4}/{len(msgids)}"
            f" ({percent:5.1f}%)  {state}"
        )

    if not args.quiet:
        # Then the strings themselves, so they can be worked through
        for catalog in catalogs:
            if catalog.complete:
                continue

            path = join("apprise", "i18n", catalog.language, CATALOG)
            print("")
            print(f"{catalog.language} -- edit {path}")
            for msgid in catalog.missing:
                print(f"  - {msgid}")

            for msgid in catalog.fuzzy:
                print(f"  - {msgid} (marked fuzzy; please confirm it)")

    incomplete = [c.language for c in catalogs if not c.complete]
    print("")
    if not incomplete:
        print("Every language is fully translated.  Thank you!")

    else:
        print(
            "To help, edit the file listed above for your language and fill"
            " in each empty msgstr."
        )
        print("Then run these from the repository root:")
        print("")
        print("  tox -e i18n      # refresh the .pot and every .po file")
        print("  tox -e compile   # build the .mo files Apprise loads")
        print("  python packaging/i18n_status.py")

    return 1 if (args.strict and incomplete) else 0


if __name__ == "__main__":
    sys.exit(main())
