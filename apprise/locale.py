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


from __future__ import annotations

from collections.abc import Callable, Iterator
import contextlib
import contextvars
import ctypes
import locale
import os
from os.path import abspath, dirname, join
import re
from typing import Optional, Union

from .logger import logger

# This gets toggled to True if we succeed
GETTEXT_LOADED = False

try:
    # Initialize gettext
    import gettext

    # Toggle our flag
    GETTEXT_LOADED = True

except ImportError:
    # gettext isn't available; no problem; Use the library features without
    # multi-language support.
    pass


# The translation function used for lazy strings inside lang_at().
ACTIVE_GETTEXT = contextvars.ContextVar("apprise_active_gettext", default=None)


class AppriseLocale:
    """Load and switch between gettext languages as needed."""

    # Define our translation domain
    _domain = "apprise"

    # The path to our translations
    _locale_dir = abspath(join(dirname(__file__), "i18n"))

    # Locale regular expression
    #
    # Matches a locale such as en_CA.UTF-8 or ca_ES.UTF-8@valencia:
    # - A 2 or 3 letter language with an optional region (en_CA or en-CA).
    # - An optional codeset (.UTF-8) and modifier (@euro), both discarded.
    # - A codeset may hold dots and underscores (C.ANSI_X3.4-1968).
    _local_re = re.compile(
        r"^\s*((?P<ansii>C|POSIX)|(?P<lang>([a-z]{2,3}))"
        r"([_-](?P<country>[a-z0-9]{2,8}))?([_-][a-z0-9]{2,8})*)"
        r"(\.(?P<enc>[a-z0-9._-]+))?"
        r"(@(?P<modifier>[a-z0-9_-]+))?\s*$",
        re.IGNORECASE,
    )

    # The environment variables that name a language, in the order gettext
    # itself consults them. LANGUAGE is the GNU extension and wins; LC_ALL
    # over-rides every category; LC_MESSAGES is the category that governs
    # translated text; LANG is the fallback for all of them.
    _env_variables = ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG")

    # The same list without LANGUAGE. These name a locale rather than a
    # language, and the first one set decides whether text is translated at
    # all.
    _locale_variables = ("LC_ALL", "LC_MESSAGES", "LANG")

    # Define our default encoding
    _default_encoding = "utf-8"

    # The function to assign `_` by default
    _fn = "gettext"

    # The language we should fall back to if all else fails
    _default_language = "en"

    def __init__(self, language: Optional[str] = None) -> None:
        """Use the requested language or detect it from the operating system.

        The configured default language is used when detection fails.
        """

        # Cache previously loaded translations
        self._gtobjs = {}

        # Get our language
        self.lang = AppriseLocale.detect_language(language)

        # Our mapping to our _fn
        self.__fn_map = None

        if GETTEXT_LOADED is False:
            # We're done
            return

        # Add language
        self.add(self.lang)

    def add(
        self,
        lang: Optional[str] = None,
        set_default: bool = True,
    ) -> bool:
        """Add a language to our list."""
        lang = lang if lang else self._default_language
        if lang not in self._gtobjs:
            # Try the regional catalog before its base language.
            languages = AppriseLocale.language_candidates(lang)
            if not languages:
                logger.warning(
                    "The language specified (%s) is not supported.", lang
                )
                return False

            # Load our gettext object and install our language
            try:
                self._gtobjs[lang] = gettext.translation(
                    self._domain,
                    localedir=self._locale_dir,
                    languages=languages,
                    fallback=False,
                )

                # Keep the selected gettext function without installing it.
                self.__fn_map = getattr(self._gtobjs[lang], self._fn)

            except FileNotFoundError:
                # The translation directory does not exist
                logger.debug(
                    "Could not load translation path: %s",
                    join(self._locale_dir, lang),
                )

                # Fallback (handle case where self.lang does not exist)
                if self.lang not in self._gtobjs:
                    self._gtobjs[self.lang] = gettext
                    self.__fn_map = getattr(self._gtobjs[self.lang], self._fn)

                return False

            logger.trace(
                "Loaded language %s (searched: %s)",
                lang,
                ", ".join(languages),
            )

        if set_default:
            logger.debug("Language set to %s", lang)
            self.lang = lang

        return True

    @contextlib.contextmanager
    def lang_at(
        self,
        lang: Optional[str],
        mapto: str = _fn,
    ) -> Iterator[Optional[Callable[[str], str]]]:
        """Temporarily use a language and yield its translation function.

        For example::

            with at.lang_at('fr'):
                # Strings use French within this block.
        """

        if GETTEXT_LOADED is False:
            # Do nothing
            yield None

            # No translation support is available.
            return

        # Normalize the requested language.
        lang = AppriseLocale.detect_language(lang, detect_fallback=False)
        if not lang or (
            lang not in self._gtobjs and not self.add(lang, set_default=False)
        ):
            # Nothing usable was asked for, or no catalog exists for it; fall
            # back to the language we were already set up with
            fn = getattr(self._gtobjs[self.lang], mapto)

        else:
            fn = getattr(self._gtobjs[lang], mapto)

        # Use this translation for lazy strings within the context.
        token = ACTIVE_GETTEXT.set(fn if mapto == self._fn else None)
        try:
            # Provide the selected translation function.
            yield fn

        finally:
            # Restore the translation used by the surrounding context.
            ACTIVE_GETTEXT.reset(token)

        return

    @property
    def gettext(self) -> Callable[[str], str]:
        """Return the current language gettext() function.

        Useful for assigning to `_`
        """
        return self._gtobjs[self.lang].gettext

    @staticmethod
    def normalize_language(lang: Optional[str]) -> Optional[str]:
        """Normalize a language code, or return None when it is invalid.

        Matching is case insensitive. A hyphen or an underscore separates a
        region, so ``en-CA``, ``en_CA``, and ``EN-ca`` all become ``en_CA``.
        A codeset or modifier is dropped, so ``en_CA.UTF-8@euro`` becomes
        ``en_CA``. Only the first value of a preference list is used.
        """
        if not isinstance(lang, str):
            return None

        # Use the first language in a preference list. A comma separates an
        # Accept-Language list and a colon separates a LANGUAGE= one.
        entry = re.split(r"[,:]", lang, maxsplit=1)[0]

        # Ignore a quality value such as ;q=0.9.
        entry = entry.split(";")[0]

        result = AppriseLocale._local_re.match(entry)
        if not result or not result.group("lang"):
            # The value is not a supported language format.
            return None

        # Language codes are lower case, regions are upper case (en_CA)
        language = result.group("lang").lower()
        country = result.group("country")

        # Drop unsupported regions or script names such as Hans in zh-Hans.
        if not country or not re.match(r"^[a-z]{2}$", country, re.I):
            return language

        return f"{language}_{country.upper()}"

    @staticmethod
    def is_ansii_locale(value: Optional[str]) -> bool:
        """Return True when ``value`` names the C (or POSIX) locale."""
        if not isinstance(value, str):
            return False

        # C, POSIX, and C.UTF-8 all mean the same thing here
        result = AppriseLocale._local_re.match(value)
        return bool(result and result.group("ansii"))

    @staticmethod
    def language_candidates(lang: Optional[str]) -> list[str]:
        """Return matching catalogs in preference order.

        For example, ``en_CA`` searches ``en_CA`` and then ``en``. Invalid
        values return an empty list.
        """
        language = AppriseLocale.normalize_language(lang)
        if not language:
            # No catalog can match an invalid value.
            return []

        # Retry a regional language without its region.
        return (
            [language, language.split("_")[0]]
            if "_" in language
            else [language]
        )

    @staticmethod
    def detect_language(
        lang: Optional[str] = None,
        detect_fallback: bool = True,
    ) -> Optional[str]:
        """Return a normalized language from the input or the system."""
        # Preserve valid regions; return None for invalid values.
        if not isinstance(lang, str):
            if detect_fallback is False:
                # no detection enabled; we're done
                return None

            # Posix lookup
            lookup = os.environ.get

            # The locale in charge of translated text. Asking for C (or
            # POSIX) is asking for no translation at all, and it silences
            # LANGUAGE too, so detection stops there.
            #
            # This follows GNU gettext, which documents LANGUAGE as being
            # ignored under the C locale. Python's own gettext.find() skips
            # that rule and lets LANGUAGE through; we do not, because
            # LC_ALL=C is how a script asks for untranslated output.
            localename = next(
                (
                    value
                    for value in (
                        lookup(variable)
                        for variable in AppriseLocale._locale_variables
                    )
                    if value
                ),
                None,
            )
            if localename and AppriseLocale.is_ansii_locale(localename):
                logger.debug(
                    "The %s locale asks for no translation; using %s",
                    localename,
                    AppriseLocale._default_language,
                )
                return AppriseLocale._default_language

            localename = None
            for variable in AppriseLocale._env_variables:
                localename = lookup(variable, None)
                if localename:
                    # Normalization applies the same rules and drops any
                    # encoding suffix such as .UTF-8 on its own.
                    language = AppriseLocale.normalize_language(localename)
                    if language:
                        return language

            # Windows handling
            if hasattr(ctypes, "windll"):
                windll = ctypes.windll.kernel32
                try:
                    lang = locale.windows_locale[
                        windll.GetUserDefaultUILanguage()
                    ]

                    # Our detected windows language
                    return AppriseLocale.normalize_language(lang)

                except (TypeError, KeyError):
                    # Fallback to posix detection
                    pass

            # Built in locale library check
            try:
                # Acquire our locale
                lang = locale.getlocale()[0]
                # Compatibility for Python >= 3.12
                if lang == "C":
                    lang = AppriseLocale._default_language

            except (ValueError, TypeError) as e:
                # An invalid environment locale can make getlocale() fail.
                # Warn the user so they can correct their locale variables.
                logger.warning(f"Language detection failure / {e!s}")
                return None

        return AppriseLocale.normalize_language(lang)

    def __getstate__(self) -> dict:
        """Return state that can be pickled."""
        state = self.__dict__.copy()

        # Remove the unpicklable entries.
        del state["_gtobjs"]
        del state["_AppriseLocale__fn_map"]
        return state

    def __setstate__(self, state: dict) -> None:
        """Restore pickled state and reload its language."""
        self.__dict__.update(state)
        # Our mapping to our _fn
        self.__fn_map = None
        self._gtobjs = {}
        self.add(state["lang"], set_default=True)


#
# Prepare our default LOCALE Singleton
#
LOCALE = AppriseLocale()


class LazyTranslation:
    """Translate text only when it is converted to a string."""

    def __init__(self, text: str, *args, **kwargs) -> None:
        """Store our text."""
        self.text = text

        super().__init__(*args, **kwargs)

    def __str__(self) -> str:
        if GETTEXT_LOADED is False:
            return self.text

        # A lang_at() context overrides the configured language.
        fn = ACTIVE_GETTEXT.get()
        return fn(self.text) if fn else LOCALE.gettext(self.text)


# Lazy translation handling
def gettext_lazy(text: str) -> LazyTranslation:
    """Return text that is translated when converted to a string."""

    return LazyTranslation(text=text)


# Identify our Translatable content
Translatable = Union[str, LazyTranslation]
