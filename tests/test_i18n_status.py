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


# Disable logging for a cleaner testing output
import builtins
import importlib.util
import logging
import os
import sys

import pytest

logging.disable(logging.CRITICAL)

# Our translation report lives beside the packaging tooling rather than
# inside the apprise package, so it is loaded by path
SCRIPT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "packaging",
    "i18n_status.py",
)

_spec = importlib.util.spec_from_file_location("i18n_status", SCRIPT)
i18n_status = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(i18n_status)


HEADER = """\
msgid ""
msgstr ""
"Project-Id-Version: apprise 1.0.0\\n"
"Language: {language}\\n"
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=utf-8\\n"
"Content-Transfer-Encoding: 8bit\\n"
"""


def write_catalog(root, language, entries, header=True):
    """Write a catalog for ``language`` under ``root`` and return its path."""
    path = os.path.join(str(root), language, "LC_MESSAGES")
    os.makedirs(path, exist_ok=True)
    target = os.path.join(path, "apprise.po")
    with open(target, "w", encoding="utf-8") as fp:
        if header:
            fp.write(HEADER.format(language=language))

        fp.write("\n" + entries)

    return target


def test_read_catalog(tmpdir):
    """Every shape our catalogs can take is read back correctly."""

    path = write_catalog(
        tmpdir,
        "xx",
        """
#: apprise/url.py:1
msgid "Token"
msgstr "Jeton"

#: apprise/url.py:2
#, fuzzy
msgid "Password"
msgstr "Guessed"

#. A translator note
#: apprise/url.py:3
msgid "A very long string that a tool decided to wrap onto another line"
msgstr ""
"Une chaine tres longue "
"qu un outil a decide de couper"

msgid "Quoted \\"value\\" with a \\\\ and a \\ttab"
msgstr "Traduit"

msgid "A literal \\\\n stays as it was written"
msgstr "Traduit"

msgctxt "menu"
msgid "Open"
msgstr "Ouvrir"

msgid "One file"
msgid_plural "Many files"
msgstr[0] "Un fichier"
msgstr[1] "Des fichiers"

#~ msgid "Removed"
#~ msgstr "Retire"

msgid Lost its quoting
msgstr "Ignored"

""",
    )

    translations, fuzzy = i18n_status.read_catalog(path)

    # A plain entry, and one a tool only guessed at
    assert translations["Token"] == "Jeton"
    assert fuzzy == {"Password"}

    # A wrapped translation is joined back together
    assert (
        translations[
            "A very long string that a tool decided to wrap onto another line"
        ]
        == "Une chaine tres longue qu un outil a decide de couper"
    )

    # Escapes are resolved on both sides
    assert 'Quoted "value" with a \\ and a \ttab' in translations

    # An escaped backslash is not re-read as the start of the next escape
    assert translations["A literal \\n stays as it was written"] == "Traduit"

    # A context or plural entry is left out rather than read wrongly
    assert "Open" not in translations
    assert "One file" not in translations

    # So is anything the template no longer has
    assert "Removed" not in translations

    # A hand broken entry is stepped over rather than crashing the report
    assert "Lost its quoting" not in translations


def test_reference_from_source():
    """Our strings are read from the Apprise source, not from a file."""

    msgids, origin = i18n_status.reference()
    assert origin == "source"

    # A label only the source knows about proves nothing on disk was used
    assert "Verify SSL" in msgids
    assert len(msgids) > 400


def test_reference_from_template(tmpdir, monkeypatch):
    """The template is the fallback when Babel is unavailable."""

    monkeypatch.setattr(i18n_status, "extract", lambda: None)
    monkeypatch.setattr(
        i18n_status, "POT_FILE", os.path.join(str(tmpdir), "apprise.pot")
    )

    # With no template either, there is nothing to measure against
    assert i18n_status.reference() == ([], "")

    with open(i18n_status.POT_FILE, "w", encoding="utf-8") as fp:
        fp.write(HEADER.format(language="en"))
        fp.write('\nmsgid "Token"\nmsgstr ""\n')

    assert i18n_status.reference() == (["Token"], "template")


def test_reference_without_babel(monkeypatch):
    """No Babel means no strings can be read out of the source."""

    # Hide Babel the way an environment without it would
    real_import = builtins.__import__

    def deny(name, *args, **kwargs):
        if name.startswith("babel"):
            raise ImportError(name)

        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", deny)
    assert i18n_status.extract() is None


def run(monkeypatch, capsys, *args):
    """Run the report with ``args`` and return its (code, output)."""
    monkeypatch.setattr(sys, "argv", ["i18n_status.py", *args])
    code = i18n_status.main()
    return (code, capsys.readouterr())


def test_status_complete(tmpdir, monkeypatch, capsys):
    """A fully translated language is reported as complete."""

    monkeypatch.setattr(i18n_status, "I18N_DIR", str(tmpdir))
    monkeypatch.setattr(i18n_status, "extract", lambda: ["Token"])
    write_catalog(tmpdir, "fr", 'msgid "Token"\nmsgstr "Jeton"\n')

    code, out = run(monkeypatch, capsys)
    assert code == 0
    assert "fr" in out.out
    assert "complete" in out.out
    assert "Every language is fully translated" in out.out

    # Nothing is left to do, so --strict is happy too
    assert run(monkeypatch, capsys, "--strict")[0] == 0


def test_status_gaps(tmpdir, monkeypatch, capsys):
    """Untranslated and fuzzy strings are each listed as a bullet."""

    monkeypatch.setattr(i18n_status, "I18N_DIR", str(tmpdir))
    monkeypatch.setattr(
        i18n_status, "extract", lambda: ["Token", "Secret", "Password"]
    )
    write_catalog(
        tmpdir,
        "fr",
        """
msgid "Token"
msgstr "Jeton"

msgid "Secret"
msgstr ""

#, fuzzy
msgid "Password"
msgstr "Guessed"
""",
    )

    code, out = run(monkeypatch, capsys)
    assert code == 0
    assert "needs help" in out.out
    assert "  - Secret" in out.out
    assert "  - Password (marked fuzzy; please confirm it)" in out.out
    assert "tox -e i18n" in out.out

    # The summary on its own leaves the bullets out
    code, out = run(monkeypatch, capsys, "--quiet")
    assert code == 0
    assert "needs help" in out.out
    assert "  - Secret" not in out.out

    # Anything left over is an error when we are asked to be strict
    assert run(monkeypatch, capsys, "--strict", "-l", "fr")[0] == 1


def test_status_missing_everywhere(tmpdir, monkeypatch, capsys):
    """A string no catalog has yet is still reported against the source."""

    monkeypatch.setattr(i18n_status, "I18N_DIR", str(tmpdir))
    monkeypatch.setattr(
        i18n_status, "POT_FILE", os.path.join(str(tmpdir), "apprise.pot")
    )

    # Two languages agree with each other and both fall short of the source
    for language in ("de", "fr"):
        write_catalog(tmpdir, language, 'msgid "Token"\nmsgstr "Token"\n')

    monkeypatch.setattr(
        i18n_status, "extract", lambda: ["Token", "Brand New Label"]
    )

    code, out = run(monkeypatch, capsys, "--strict")
    assert code == 1
    assert "1/2" in out.out
    assert out.out.count("  - Brand New Label") == 2

    # Falling back to a template that is behind the source is announced
    monkeypatch.setattr(i18n_status, "extract", lambda: None)
    with open(i18n_status.POT_FILE, "w", encoding="utf-8") as fp:
        fp.write(HEADER.format(language="en"))
        fp.write('\nmsgid "Token"\nmsgstr ""\n')

    code, out = run(monkeypatch, capsys)
    assert code == 0
    assert "Measured against apprise/i18n/apprise.pot" in out.out


def test_status_strict_needs_source(tmpdir, monkeypatch, capsys):
    """Strict mode refuses to certify against a file that can be stale."""

    monkeypatch.setattr(i18n_status, "I18N_DIR", str(tmpdir))
    monkeypatch.setattr(i18n_status, "extract", lambda: None)
    monkeypatch.setattr(
        i18n_status, "POT_FILE", os.path.join(str(tmpdir), "apprise.pot")
    )
    write_catalog(tmpdir, "fr", 'msgid "Token"\nmsgstr "Jeton"\n')
    with open(i18n_status.POT_FILE, "w", encoding="utf-8") as fp:
        fp.write(HEADER.format(language="en"))
        fp.write('\nmsgid "Token"\nmsgstr ""\n')

    # The template says everything is translated, and it may well be behind
    # the source, so strict mode will not sign off on it
    code, out = run(monkeypatch, capsys, "--strict")
    assert code == 1
    assert "Babel is required" in out.err

    # Without --strict the same run reports on the template instead
    code, out = run(monkeypatch, capsys)
    assert code == 0
    assert "Measured against apprise/i18n/apprise.pot" in out.out


def test_status_unknown_language(tmpdir, monkeypatch, capsys):
    """A name with no catalog behind it is refused."""

    monkeypatch.setattr(i18n_status, "I18N_DIR", str(tmpdir))
    write_catalog(tmpdir, "fr", 'msgid "Token"\nmsgstr "Jeton"\n')

    # A directory without a catalog inside it is not a language
    os.makedirs(os.path.join(str(tmpdir), "__pycache__"), exist_ok=True)

    code, out = run(monkeypatch, capsys, "-l", "__pycache__")
    assert code == 1
    assert "No translation exists for: __pycache__" in out.err


def test_status_no_catalogs(tmpdir, monkeypatch, capsys):
    """Nothing to report on is an error rather than a traceback."""

    monkeypatch.setattr(i18n_status, "I18N_DIR", str(tmpdir))

    code, out = run(monkeypatch, capsys)
    assert code == 1
    assert "No translations were found" in out.err


def test_status_no_strings(tmpdir, monkeypatch, capsys):
    """A catalog holding nothing but a header tells us to rebuild."""

    monkeypatch.setattr(i18n_status, "I18N_DIR", str(tmpdir))
    monkeypatch.setattr(i18n_status, "extract", lambda: None)
    monkeypatch.setattr(
        i18n_status, "POT_FILE", os.path.join(str(tmpdir), "apprise.pot")
    )
    write_catalog(tmpdir, "fr", "")

    code, out = run(monkeypatch, capsys)
    assert code == 1
    assert "No translatable strings were found" in out.err


def test_languages_found():
    """Our own catalogs are discovered from the repository."""

    # Apprise ships these; a missing one means a catalog was lost
    found = i18n_status.languages()
    assert "en" in found
    assert "fr" in found

    # Every entry we report on has a catalog behind it
    for language in found:
        assert os.path.isfile(
            os.path.join(i18n_status.I18N_DIR, language, i18n_status.CATALOG)
        )


def test_catalog_state():
    """A catalog with nothing outstanding reports itself as complete."""

    catalog = i18n_status.Catalog("fr")
    assert catalog.complete

    # Either list is enough to need a person
    catalog.missing.append("Token")
    assert not catalog.complete

    catalog.missing.clear()
    catalog.fuzzy.append("Token")
    assert not catalog.complete


def test_real_catalogs_complete():
    """Every language Apprise ships covers every string in the source."""

    # Read from the source so a catalog can not vouch for another one
    msgids = i18n_status.extract()
    if msgids is None:
        pytest.skip("Requires Babel to read our strings from the source")

    assert msgids

    for language in i18n_status.languages():
        catalog = i18n_status.inspect(language, msgids)
        assert catalog.complete, (
            f"{language} is missing {catalog.missing + catalog.fuzzy};"
            " run `tox -e i18n-status` for the full report"
        )


def test_status_entry_point(monkeypatch, capsys):
    """The report runs against our own catalogs without a failure."""

    # Our own translations are complete, so this is a clean run
    assert run(monkeypatch, capsys, "--quiet", "--strict")[0] == 0
