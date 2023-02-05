# -*- coding: utf-8 -*-
# BSD 3-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2023, Chris Caron <lead2gold@gmail.com>
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
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
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

import ctypes
import locale
import contextlib
from os.path import join
from os.path import dirname
from os.path import abspath
from .logger import logger

# Define our translation domain
DOMAIN = 'apprise'
LOCALE_DIR = abspath(join(dirname(__file__), 'i18n'))

# This gets toggled to True if we succeed
GETTEXT_LOADED = False

try:
    # Initialize gettext
    import gettext

    # install() creates a _() in our builtins
    gettext.install(DOMAIN, localedir=LOCALE_DIR)

    # Toggle our flag
    GETTEXT_LOADED = True

except ImportError:
    # gettext isn't available; no problem, just fall back to using
    # the library features without multi-language support.
    import builtins
    builtins.__dict__['_'] = lambda x: x  # pragma: no branch


class LazyTranslation:
    """
    Doesn't translate anything until str() or unicode() references
    are made.

    """
    def __init__(self, text, *args, **kwargs):
        """
        Store our text
        """
        self.text = text

        super().__init__(*args, **kwargs)

    def __str__(self):
        return gettext.gettext(self.text)


# Lazy translation handling
def gettext_lazy(text):
    """
    A dummy function that can be referenced
    """
    return LazyTranslation(text=text)


class AppriseLocale:
    """
    A wrapper class to gettext so that we can manipulate multiple lanaguages
    on the fly if required.

    """

    def __init__(self, language=None):
        """
        Initializes our object, if a language is specified, then we
        initialize ourselves to that, otherwise we use whatever we detect
        from the local operating system. If all else fails, we resort to the
        defined default_language.

        """

        # Cache previously loaded translations
        self._gtobjs = {}

        # Get our language
        self.lang = AppriseLocale.detect_language(language)

        if GETTEXT_LOADED is False:
            # We're done
            return

        if self.lang:
            # Load our gettext object and install our language
            try:
                self._gtobjs[self.lang] = gettext.translation(
                    DOMAIN, localedir=LOCALE_DIR, languages=[self.lang])

                # Install our language
                self._gtobjs[self.lang].install()

            except IOError:
                # This occurs if we can't access/load our translations
                pass

    @contextlib.contextmanager
    def lang_at(self, lang):
        """
        The syntax works as:
            with at.lang_at('fr'):
                # apprise works as though the french language has been
                # defined. afterwards, the language falls back to whatever
                # it was.
        """

        if GETTEXT_LOADED is False:
            # yield
            yield

            # we're done
            return

        # Tidy the language
        lang = AppriseLocale.detect_language(lang, detect_fallback=False)

        # Now attempt to load it
        try:
            if lang in self._gtobjs:
                if lang != self.lang:
                    # Install our language only if we aren't using it
                    # already
                    self._gtobjs[lang].install()

            else:
                self._gtobjs[lang] = gettext.translation(
                    DOMAIN, localedir=LOCALE_DIR, languages=[self.lang])

                # Install our language
                self._gtobjs[lang].install()

            # Yield
            yield

        except (IOError, KeyError):
            # This occurs if we can't access/load our translations
            # Yield reguardless
            yield

        finally:
            # Fall back to our previous language
            if lang != self.lang and lang in self._gtobjs:
                # Install our language
                self._gtobjs[self.lang].install()

        return

    @staticmethod
    def detect_language(lang=None, detect_fallback=True):
        """
        returns the language (if it's retrievable)
        """
        # We want to only use the 2 character version of this language
        # hence en_CA becomes en, en_US becomes en.
        if not isinstance(lang, str):
            if detect_fallback is False:
                # no detection enabled; we're done
                return None

            if hasattr(ctypes, 'windll'):
                windll = ctypes.windll.kernel32
                try:
                    lang = locale.windows_locale[
                        windll.GetUserDefaultUILanguage()]

                    # Our detected windows language
                    return lang[0:2].lower()

                except (TypeError, KeyError):
                    # Fallback to posix detection
                    pass

            try:
                # Detect language
                lang = locale.getdefaultlocale()[0]

            except ValueError as e:
                # This occurs when an invalid locale was parsed from the
                # environment variable. While we still return None in this
                # case, we want to better notify the end user of this. Users
                # receiving this error should check their environment
                # variables.
                logger.warning(
                    'Language detection failure / {}'.format(str(e)))
                return None

            except TypeError:
                # None is returned if the default can't be determined
                # we're done in this case
                return None

        return None if not lang else lang[0:2].lower()
