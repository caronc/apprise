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
import re

from .parse import is_hostname, parse_url


def cwe312_word(word, force=False, advanced=True, threshold=5):
    """This function was written to help mask secure/private information that
    may or may not be found within Apprise. The idea is to provide a
    presentable word response that the user who prepared it would understand,
    yet not reveal any private information for any potential intruder.

    For more detail see CWE-312 @
       https://cwe.mitre.org/data/definitions/312.html

    The `force` is an optional argument used to keep the string formatting
    consistent and in one place. If set, the content passed in is presumed
    to be containing secret information and will be updated accordingly.

    If advanced is set to `True` then content is additionally checked for
    upper/lower/ascii/numerical variances. If an obscurity threshold is
    reached, then content is considered secret
    """

    class Variance:
        """A Simple List of Possible Character Variances."""

        # An Upper Case Character (ABCDEF... etc)
        ALPHA_UPPER = "+"
        # An Lower Case Character (abcdef... etc)
        ALPHA_LOWER = "-"
        # A Special Character ($%^;... etc)
        SPECIAL = "s"
        # A Numerical Character (1234... etc)
        NUMERIC = "n"

    if not (isinstance(word, str) and word.strip()):
        # not a password if it's not something we even support
        return word

    # Formatting
    word = word.strip()
    if force:
        # We're forcing the representation to be a secret
        # We do this for consistency
        return f"{word[0:1]}...{word[-1:]}"

    elif len(word) > 1 and not is_hostname(
        word, ipv4=True, ipv6=True, underscore=False
    ):
        # Verify if it is a hostname or not
        return f"{word[0:1]}...{word[-1:]}"

    elif len(word) >= 16:
        # an IP will be 15 characters so we don't want to use a smaller
        # value then 16 (e.g 101.102.103.104)
        # we can assume very long words are passwords otherwise
        return f"{word[0:1]}...{word[-1:]}"

    if advanced:
        #
        # Mark word a secret based on it's obscurity
        #

        # Our variances will increase depending on these variables:
        last_variance = None
        obscurity = 0

        for c in word:
            # Detect our variance
            if c.isdigit():
                variance = Variance.NUMERIC
            elif c.isalpha() and c.isupper():
                variance = Variance.ALPHA_UPPER
            elif c.isalpha() and c.islower():
                variance = Variance.ALPHA_LOWER
            else:
                variance = Variance.SPECIAL

            if last_variance != variance or variance == Variance.SPECIAL:
                obscurity += 1

                if obscurity >= threshold:
                    return f"{word[0:1]}...{word[-1:]}"

            last_variance = variance

    # Otherwise we're good; return our word
    return word


def cwe312_url(url):
    """This function was written to help mask secure/private information that
    may or may not be found on an Apprise URL. The idea is to not disrupt the
    structure of the previous URL too much, yet still protect the users private
    information from being logged directly to screen.

    For more detail see CWE-312 @
    https://cwe.mitre.org/data/definitions/312.html

    For example, consider the URL: http://user:password@localhost/

    When passed into this function, the return value would be:
    http://user:****@localhost/

    Since apprise allows you to put private information everywhere in it's
    custom URLs, it uses this function to manipulate the content before
    returning to any kind of logger.

    The idea is that the URL can still be interpreted by the person who
    constructed them, but not to an intruder.
    """
    # Parse our URL
    results = parse_url(url)
    if not results:
        # Nothing was returned (invalid data was fed in); return our
        # information as it was fed to us (without changing it)
        return url

    # Update our URL with values
    results["password"] = cwe312_word(results["password"], force=True)
    if not results["schema"].startswith("http"):
        results["user"] = cwe312_word(results["user"])
        results["host"] = cwe312_word(results["host"])

    else:
        results["host"] = cwe312_word(results["host"], advanced=False)
        results["user"] = cwe312_word(results["user"], advanced=False)

    # Apply our full path scan in all cases
    results["fullpath"] = (
        "/"
        + "/".join([
            cwe312_word(x)
            for x in re.split(r"[\\/]+", results["fullpath"].lstrip("/"))
        ])
        if results["fullpath"]
        else ""
    )

    #
    # Now re-assemble our URL for display purposes
    #

    # Determine Authentication
    auth = ""
    if results["user"] and results["password"]:
        auth = "{user}:{password}@".format(
            user=results["user"],
            password=results["password"],
        )
    elif results["user"]:
        auth = "{user}@".format(
            user=results["user"],
        )

    params = ""
    if results["qsd"]:
        params = "?{}".format(
            "&".join([
                "{}={}".format(
                    k,
                    cwe312_word(
                        v,
                        force=(
                            k
                            in (
                                "password",
                                "secret",
                                "pass",
                                "token",
                                "key",
                                "id",
                                "apikey",
                                "to",
                            )
                        ),
                    ),
                )
                for k, v in results["qsd"].items()
            ])
        )

    return "{schema}://{auth}{hostname}{port}{fullpath}{params}".format(
        schema=results["schema"],
        auth=auth,
        # never encode hostname since we're expecting it to be a valid one
        hostname=results["host"],
        port="" if not results["port"] else ":{}".format(results["port"]),
        fullpath=results["fullpath"] if results["fullpath"] else "",
        params=params,
    )
