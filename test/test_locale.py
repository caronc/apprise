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


@mock.patch('gettext.install')
def test_apprise_locale(mock_gettext_install):
    """
    API: Test apprise locale object
    """
    lazytrans = AppriseLocale.LazyTranslation('Token')
    assert str(lazytrans) == 'Token'


@mock.patch('gettext.install')
def test_gettext_init(mock_gettext_install):
    """
    API: Mock Gettext init
    """
    mock_gettext_install.side_effect = ImportError()
    # Test our fall back to not supporting translations
    reload(AppriseLocale)

    # Objects can still be created
    al = AppriseLocale.AppriseLocale()

    with al.lang_at('en'):
        # functions still behave as normal
        pass

    # restore the object
    mock_gettext_install.side_effect = None
    reload(AppriseLocale)


@mock.patch('gettext.translation')
def test_gettext_translations(mock_gettext_trans):
    """
    API: Apprise() Gettext translations

    """

    mock_gettext_trans.side_effect = IOError()

    # This throws internally but we handle it gracefully
    al = AppriseLocale.AppriseLocale()

    with al.lang_at('en'):
        # functions still behave as normal
        pass

    # This throws internally but we handle it gracefully
    AppriseLocale.AppriseLocale(language="fr")


@mock.patch('gettext.translation')
def test_gettext_installs(mock_gettext_trans):
    """
    API: Apprise() Gettext install

    """

    mock_lang = mock.Mock()
    mock_lang.install.return_value = True
    mock_gettext_trans.return_value = mock_lang

    # This throws internally but we handle it gracefully
    al = AppriseLocale.AppriseLocale()

    with al.lang_at('en'):
        # functions still behave as normal
        pass

    # This throws internally but we handle it gracefully
    AppriseLocale.AppriseLocale(language="fr")

    # Force a few different languages
    al._gtobjs['en'] = mock_lang
    al._gtobjs['es'] = mock_lang
    al.lang = 'en'

    with al.lang_at('en'):
        # functions still behave as normal
        pass

    with al.lang_at('es'):
        # functions still behave as normal
        pass

    with al.lang_at('fr'):
        # functions still behave as normal
        pass


def test_detect_language_windows_users():
    """
    API: Apprise() Detect language

    """

    if hasattr(ctypes, 'windll'):
        from ctypes import windll
    else:
        windll = mock.Mock()
        # 4105 = en_CA
        windll.kernel32.GetUserDefaultUILanguage.return_value = 4105
        setattr(ctypes, 'windll', windll)

    # The below accesses the windows fallback code
    with environ('LANG', 'LANGUAGE', 'LC_ALL', 'LC_CTYPE', LANG="en_CA"):
        assert AppriseLocale.AppriseLocale.detect_language() == 'en'

    assert AppriseLocale.AppriseLocale\
        .detect_language(detect_fallback=False) is None

    # 0 = IndexError
    windll.kernel32.GetUserDefaultUILanguage.return_value = 0
    setattr(ctypes, 'windll', windll)
    with environ('LANG', 'LC_ALL', 'LC_CTYPE', LANGUAGE="en_CA"):
        assert AppriseLocale.AppriseLocale.detect_language() == 'en'


@pytest.mark.skipif(sys.platform == "win32", reason="Does not work on Windows")
def test_detect_language_windows_users_croaks_please_review():
    """
    When enabling CI testing on Windows, those tests did not produce the
    correct results. They may want to be reviewed.
    """

    # The below accesses the windows fallback code and fail
    # then it will resort to the environment variables.
    with environ('LANG', 'LANGUAGE', 'LC_ALL', 'LC_CTYPE'):
        # Language can't be detected
        assert AppriseLocale.AppriseLocale.detect_language() is None

    # Detect French language.
    with environ('LANGUAGE', 'LC_ALL', 'LC_CTYPE', LANG="fr_CA"):
        assert AppriseLocale.AppriseLocale.detect_language() == 'fr'

    # The following unsets all environment variables and sets LC_CTYPE
    # This was causing Python 2.7 to internally parse UTF-8 as an invalid
    # locale and throw an uncaught ValueError; Python v2 support has been
    # dropped, but just to ensure this issue does not come back, we keep
    # this test:
    with environ(*list(os.environ.keys()), LC_CTYPE="UTF-8"):
        assert AppriseLocale.AppriseLocale.detect_language() is None

    # Test with absolutely no environment variables what-so-ever
    with environ(*list(os.environ.keys())):
        assert AppriseLocale.AppriseLocale.detect_language() is None


@pytest.mark.skipif(sys.platform == "win32", reason="Does not work on Windows")
@mock.patch('locale.getdefaultlocale')
def test_detect_language_defaultlocale(mock_getlocale):
    """
    API: Apprise() Default locale detection

    """
    # Handle case where getdefaultlocale() can't be detected
    mock_getlocale.return_value = None
    assert AppriseLocale.AppriseLocale.detect_language() is None

    # if detect_language and windows env fail us, then we don't
    # set up a default language on first load
    AppriseLocale.AppriseLocale()
