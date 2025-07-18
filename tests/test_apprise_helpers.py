# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2025, Chris Caron <lead2gold@gmail.com>
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
import logging
import os
import sys

import helpers

logging.disable(logging.CRITICAL)

# Ensure we don't create .pyc files for these tests
sys.dont_write_bytecode = True


def test_environ_temporary_change():
    """helpers: environ() testing"""
    # This is a helper function; but it does enough that we want to verify
    # our usage of it works correctly; yes... we're testing a test

    e_key1 = "APPRISE_TEMP1"
    e_key2 = "APPRISE_TEMP2"
    e_key3 = "APPRISE_TEMP3"

    e_val1 = "ABCD"
    e_val2 = "DEFG"
    e_val3 = "HIJK"

    os.environ[e_key1] = e_val1
    os.environ[e_key2] = e_val2
    os.environ[e_key3] = e_val3

    # Ensure our environment variable stuck
    assert e_key1 in os.environ
    assert e_val1 in os.environ[e_key1]
    assert e_key2 in os.environ
    assert e_val2 in os.environ[e_key2]
    assert e_key3 in os.environ
    assert e_val3 in os.environ[e_key3]

    with helpers.environ(e_key1, e_key3):
        # Eliminates Environment Variable 1 and 3
        assert e_key1 not in os.environ
        assert e_key2 in os.environ
        assert e_val2 in os.environ[e_key2]
        assert e_key3 not in os.environ

    # after with is over, environment is restored to normal
    assert e_key1 in os.environ
    assert e_val1 in os.environ[e_key1]
    assert e_key2 in os.environ
    assert e_val2 in os.environ[e_key2]
    assert e_key3 in os.environ
    assert e_val3 in os.environ[e_key3]

    d_key = "APPRISE_NOT_SET"
    n_key = "APPRISE_NEW_KEY"
    n_val = "NEW_VAL"

    # Verify that our temporary variables (defined above) are not pre-existing
    # environemnt variables as we'll be setting them below
    assert n_key not in os.environ
    assert d_key not in os.environ

    # makes it easier to pass in the arguments
    updates = {
        e_key1: e_val3,
        e_key2: e_val1,
        n_key: n_val,
    }
    with helpers.environ(d_key, e_key3, **updates):
        # Attempt to eliminate an undefined key (silently ignored)
        # Eliminates Environment Variable 3
        # Environment Variable 1 takes on the value of Env 3
        # Environment Variable 2 takes on the value of Env 1
        # Set a brand new variable that previously didn't exist
        assert e_key1 in os.environ
        assert e_val3 in os.environ[e_key1]
        assert e_key2 in os.environ
        assert e_val1 in os.environ[e_key2]
        assert e_key3 not in os.environ

        # Can't delete a variable that doesn't exist; so we're in the same
        # state here.
        assert d_key not in os.environ

        # Our temporary variables will be found now
        assert n_key in os.environ
        assert n_val in os.environ[n_key]

    # after with is over, environment is restored to normal
    assert e_key1 in os.environ
    assert e_val1 in os.environ[e_key1]
    assert e_key2 in os.environ
    assert e_val2 in os.environ[e_key2]
    assert e_key3 in os.environ
    assert e_val3 in os.environ[e_key3]

    # Even our temporary variables are now missing
    assert n_key not in os.environ
    assert d_key not in os.environ
