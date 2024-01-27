# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2024, Chris Caron <lead2gold@gmail.com>
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

import os
import sys
from unittest import mock

import ctypes
import pytest

from apprise import AppriseLocale
from apprise.utils import environ
from importlib import reload

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)


def test_apprise_trans():
    """
    API: Test apprise locale object
    """
    lazytrans = AppriseLocale.LazyTranslation('Token')
    assert str(lazytrans) == 'Token'


@pytest.mark.skipif(
    'gettext' not in sys.modules, reason="Requires gettext")
def test_apprise_trans_gettext_init():
    """
    API: Handle gettext
    """
    # Toggle
    AppriseLocale.GETTEXT_LOADED = False

    # Objects can still be created
    al = AppriseLocale.AppriseLocale()

    with al.lang_at('en') as _:
        # functions still behave as normal
        assert _ is None

    # Restore the object
    AppriseLocale.GETTEXT_LOADED = True


@pytest.mark.skipif(
    'gettext' not in sys.modules, reason="Requires gettext")
@mock.patch('gettext.translation')
@mock.patch('locale.getlocale')
def test_apprise_trans_gettext_translations(
        mock_getlocale, mock_gettext_trans):
    """
    API: Apprise() Gettext translations

    """

    # Set- our gettext.locale() return value
    mock_getlocale.return_value = ('en_US', 'UTF-8')

    mock_gettext_trans.side_effect = FileNotFoundError()

    # This throws internally but we handle it gracefully
    al = AppriseLocale.AppriseLocale()

    with al.lang_at('en'):
        # functions still behave as normal
        pass

    # This throws internally but we handle it gracefully
    AppriseLocale.AppriseLocale(language="fr")


@pytest.mark.skipif(
    hasattr(ctypes, 'windll'), reason="Unique Nux test cases")
@pytest.mark.skipif(
    'gettext' not in sys.modules, reason="Requires gettext")
@mock.patch('locale.getlocale')
def test_apprise_trans_gettext_lang_at(mock_getlocale):
    """
    API: Apprise() Gettext lang_at

    """

    # Set- our gettext.locale() return value
    mock_getlocale.return_value = ('en_CA', 'UTF-8')

    # This throws internally but we handle it gracefully
    al = AppriseLocale.AppriseLocale()

    # Edge Cases
    assert al.add('en', set_default=False) is True
    assert al.add('en', set_default=True) is True

    with al.lang_at('en'):
        # functions still behave as normal
        pass

    # This throws internally but we handle it gracefully
    AppriseLocale.AppriseLocale(language="fr")

    with al.lang_at('en') as _:
        # functions still behave as normal
        assert callable(_)

    with al.lang_at('es') as _:
        # functions still behave as normal
        assert callable(_)

    with al.lang_at('fr') as _:
        # functions still behave as normal
        assert callable(_)

    # Test our initialization when our fallback is a language we do
    # not have. This is only done to test edge cases when for whatever
    # reason the person who set up apprise does not have the languages
    # installed.
    fallback = AppriseLocale.AppriseLocale._default_language
    mock_getlocale.return_value = None

    with environ('LANGUAGE', 'LC_ALL', 'LC_CTYPE', 'LANG'):
        # Our default language
        AppriseLocale.AppriseLocale._default_language = 'zz'

        # We will detect the zz since there were no environment variables to
        # help us otherwise
        assert AppriseLocale.AppriseLocale.detect_language() is None
        al = AppriseLocale.AppriseLocale()

        # No Language could be set becuause no locale directory exists for this
        assert al.lang is None

        with al.lang_at(None) as _:
            # functions still behave as normal
            assert callable(_)

        with al.lang_at('en') as _:
            # functions still behave as normal
            assert callable(_)

        with al.lang_at('es') as _:
            # functions still behave as normal
            assert callable(_)

        with al.lang_at('fr') as _:
            # functions still behave as normal
            assert callable(_)

        # We can still perform simple lookups; they access a dummy wrapper:
        assert al.gettext('test') == 'test'

    with environ('LANGUAGE', 'LC_CTYPE', LC_ALL='C.UTF-8', LANG="en_CA"):
        # the UTF-8 entry is skipped over
        AppriseLocale.AppriseLocale._default_language = 'fr'

        # We will detect the english language (found in the LANG= environment
        # variable which over-rides the _default
        assert AppriseLocale.AppriseLocale.detect_language() == "en"
        al = AppriseLocale.AppriseLocale()
        assert al.lang == "en"
        assert al.gettext('test') == 'test'

        # Test case with set_default set to False (so we're still set to 'fr')
        assert al.add('zy', set_default=False) is False
        assert al.gettext('test') == 'test'

        al.add('ab', set_default=True)
        assert al.gettext('test') == 'test'

        assert al.add('zy', set_default=False) is False
    AppriseLocale.AppriseLocale._default_language = fallback


@pytest.mark.skipif(
    'gettext' not in sys.modules, reason="Requires gettext")
def test_apprise_trans_add():
    """
    API: Apprise() Gettext add

    """

    # This throws internally but we handle it gracefully
    al = AppriseLocale.AppriseLocale()
    with environ('LANGUAGE', 'LC_ALL', 'LC_CTYPE', 'LANG'):
        # English is the default/fallback type
        assert al.add('en') is True

    al = AppriseLocale.AppriseLocale()
    with environ('LANGUAGE', 'LC_ALL', 'LC_CTYPE', LANG='C.UTF-8'):
        # Test English Environment
        assert al.add('en') is True

    al = AppriseLocale.AppriseLocale()
    with environ('LANGUAGE', 'LC_ALL', 'LC_CTYPE', LANG='en_CA.UTF-8'):
        # Test English Environment
        assert al.add('en') is True

        # Double add (copy of above) to access logic that prevents adding it
        # again
        assert al.add('en') is True

    # Invalid Language
    assert al.add('bad') is False


@pytest.mark.skipif(
    not hasattr(ctypes, 'windll'), reason="Unique Windows test cases")
@pytest.mark.skipif(
    'gettext' not in sys.modules, reason="Requires gettext")
@mock.patch('locale.getlocale')
def test_apprise_trans_windows_users_win(mock_getlocale):
    """
    API: Apprise() Windows Locale Testing (Win version)

    """

    # Set- our gettext.locale() return value
    mock_getlocale.return_value = ('fr_CA', 'UTF-8')

    with mock.patch(
            'ctypes.windll.kernel32.GetUserDefaultUILanguage') as ui_lang:

        # 4105 = en_CA
        ui_lang.return_value = 4105

        with environ('LANGUAGE', 'LC_ALL', 'LC_CTYPE', 'LANG'):
            # Our default language
            AppriseLocale.AppriseLocale._default_language = 'zz'

            # We will pick up the windll module and detect english
            assert AppriseLocale.AppriseLocale.detect_language() == 'en'

        # The below accesses the windows fallback code
        with environ('LANGUAGE', 'LC_ALL', 'LC_CTYPE', LANG="es_AR"):
            # Environment Variable Trumps
            assert AppriseLocale.AppriseLocale.detect_language() == 'es'

        # No environment variable, then the Windows environment is used
        with environ('LANGUAGE', 'LC_ALL', 'LC_CTYPE', 'LANG'):
            # Windows Environment
            assert AppriseLocale.AppriseLocale.detect_language() == 'en'

        assert AppriseLocale.AppriseLocale\
            .detect_language(detect_fallback=False) is None

        # 0 = IndexError
        ui_lang.return_value = 0
        with environ('LANGUAGE', 'LANG', 'LC_ALL', 'LC_CTYPE'):
            # We fall back to posix locale
            assert AppriseLocale.AppriseLocale.detect_language() == 'fr'


@pytest.mark.skipif(
    hasattr(ctypes, 'windll'), reason="Unique Nux test cases")
@pytest.mark.skipif(
    'gettext' not in sys.modules, reason="Requires gettext")
@mock.patch('locale.getlocale')
def test_apprise_trans_windows_users_nux(mock_getlocale):
    """
    API: Apprise() Windows Locale Testing (Nux version)

    """

    # Set- our gettext.locale() return value
    mock_getlocale.return_value = ('fr_CA', 'UTF-8')

    # Emulate a windows environment
    windll = mock.Mock()
    setattr(ctypes, 'windll', windll)

    # 4105 = en_CA
    windll.kernel32.GetUserDefaultUILanguage.return_value = 4105

    with environ('LANGUAGE', 'LC_ALL', 'LC_CTYPE', 'LANG'):
        # Our default language
        AppriseLocale.AppriseLocale._default_language = 'zz'

        # We will pick up the windll module and detect english
        assert AppriseLocale.AppriseLocale.detect_language() == 'en'

    # The below accesses the windows fallback code
    with environ('LANGUAGE', 'LC_ALL', 'LC_CTYPE', LANG="es_AR"):
        # Environment Variable Trumps
        assert AppriseLocale.AppriseLocale.detect_language() == 'es'

    # No environment variable, then the Windows environment is used
    with environ('LANGUAGE', 'LC_ALL', 'LC_CTYPE', 'LANG'):
        # Windows Environment
        assert AppriseLocale.AppriseLocale.detect_language() == 'en'

    assert AppriseLocale.AppriseLocale\
        .detect_language(detect_fallback=False) is None

    # 0 = IndexError
    windll.kernel32.GetUserDefaultUILanguage.return_value = 0
    with environ('LANGUAGE', 'LANG', 'LC_ALL', 'LC_CTYPE'):
        # We fall back to posix locale
        assert AppriseLocale.AppriseLocale.detect_language() == 'fr'

    delattr(ctypes, 'windll')


@pytest.mark.skipif(sys.platform == "win32", reason="Unique Nux test cases")
@mock.patch('locale.getlocale')
def test_detect_language_using_env(mock_getlocale):
    """
    Test the reading of information from an environment variable
    """

    # Set- our gettext.locale() return value
    mock_getlocale.return_value = ('en_CA', 'UTF-8')

    # The below accesses the windows fallback code and fail
    # then it will resort to the environment variables.
    with environ('LANG', 'LANGUAGE', 'LC_ALL', 'LC_CTYPE'):
        # Language can now be detected in this case
        assert isinstance(
            AppriseLocale.AppriseLocale.detect_language(), str)

    # Detect French language.
    with environ('LANGUAGE', 'LC_ALL', LC_CTYPE="garbage", LANG="fr_CA"):
        assert AppriseLocale.AppriseLocale.detect_language() == 'fr'

    # The following unsets all environment variables and sets LC_CTYPE
    # This was causing Python 2.7 to internally parse UTF-8 as an invalid
    # locale and throw an uncaught ValueError; Python v2 support has been
    # dropped, but just to ensure this issue does not come back, we keep
    # this test:
    with environ(*list(os.environ.keys()), LC_CTYPE="UTF-8"):
        assert isinstance(AppriseLocale.AppriseLocale.detect_language(), str)

    # Test with absolutely no environment variables what-so-ever
    with environ(*list(os.environ.keys())):
        assert isinstance(AppriseLocale.AppriseLocale.detect_language(), str)

    # Handle case where getlocale() can't be detected
    mock_getlocale.return_value = None
    with environ('LC_ALL', 'LC_CTYPE', 'LANG', 'LANGUAGE'):
        assert AppriseLocale.AppriseLocale.detect_language() is None

    mock_getlocale.return_value = (None, None)
    with environ('LC_ALL', 'LC_CTYPE', 'LANG', 'LANGUAGE'):
        assert AppriseLocale.AppriseLocale.detect_language() is None

    # if detect_language and windows env fail us, then we don't
    # set up a default language on first load
    AppriseLocale.AppriseLocale()


@pytest.mark.skipif(
    'gettext' not in sys.modules, reason="Requires gettext")
def test_apprise_trans_gettext_missing(tmpdir):
    """
    Verify we can still operate without the gettext library
    """

    # remove gettext from our system enviroment
    del sys.modules["gettext"]

    # Make our new path to a fake gettext (used to over-ride real one)
    # have it fail right out of the gate
    gettext_dir = tmpdir.mkdir("gettext")
    gettext_dir.join("__init__.py").write("")
    gettext_dir.join("gettext.py").write("""raise ImportError()""")

    # Update our path to point path to head
    sys.path.insert(0, str(gettext_dir))

    # reload our module (forcing the import error when it tries to load gettext
    reload(sys.modules['apprise.AppriseLocale'])
    from apprise import AppriseLocale
    assert AppriseLocale.GETTEXT_LOADED is False

    # Now roll our changes back
    sys.path.pop(0)

    # Reload again (reverting back)
    reload(sys.modules['apprise.AppriseLocale'])
    from apprise import AppriseLocale
    assert AppriseLocale.GETTEXT_LOADED is True
