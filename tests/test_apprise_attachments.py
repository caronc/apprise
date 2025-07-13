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

from inspect import cleandoc
import json

# Disable logging for a cleaner testing output
import logging
from os.path import dirname, getsize, join
from unittest import mock

import pytest
import requests

from apprise import Apprise, AppriseAsset, AttachmentManager
from apprise.apprise_attachment import AppriseAttachment
from apprise.attachment import AttachBase
from apprise.common import ContentLocation

logging.disable(logging.CRITICAL)

TEST_VAR_DIR = join(dirname(__file__), "var")

# Grant access to our Attachment Manager Singleton
A_MGR = AttachmentManager()


def test_apprise_attachment():
    """
    API: AppriseAttachment basic testing

    """

    # Create ourselves an attachment object
    aa = AppriseAttachment()

    # There are no attachents loaded
    assert len(aa) == 0

    # Object can be directly checked as a boolean; response is False
    # when there are no entries loaded
    assert not aa

    # An attachment object using a custom Apprise Asset object
    # Set a cache expiry of 5 minutes (300 seconds)
    aa = AppriseAttachment(asset=AppriseAsset(), cache=300)

    # still no attachments added
    assert len(aa) == 0

    # Add a file by it's path
    path = join(TEST_VAR_DIR, "apprise-test.gif")
    assert aa.add(path)

    # There is now 1 attachment
    assert len(aa) == 1

    # our attachment took on our cache value
    assert aa[0].cache == 300

    # we can test the object as a boolean and get a value of True now
    assert aa

    # Add another entry already in it's AttachBase format
    response = AppriseAttachment.instantiate(path, cache=True)
    assert isinstance(response, AttachBase)
    assert aa.add(response, asset=AppriseAsset())

    # There is now 2 attachments
    assert len(aa) == 2

    # Cache is initialized to True
    assert aa[1].cache is True

    # Reset our object
    aa = AppriseAttachment()

    # We can add by lists as well in a variety of formats
    attachments = (
        path,
        f"file://{path}?name=newfilename.gif?cache=120",
        AppriseAttachment.instantiate(
            f"file://{path}?name=anotherfilename.gif", cache=100
        ),
    )

    # Add them
    assert aa.add(attachments, cache=False)

    # There is now 3 attachments
    assert len(aa) == 3

    # Take on our fixed cache value of False.
    # The last entry will have our set value of 100
    assert aa[0].cache is False
    # Even though we set a value of 120, we take on the value of False because
    # it was forced on the instantiate call
    assert aa[1].cache is False
    assert aa[2].cache == 100

    # We can pop the last element off of the list as well
    attachment = aa.pop()
    assert isinstance(attachment, AttachBase)
    # we can test of the attachment is valid using a boolean check:
    assert attachment
    assert len(aa) == 2
    assert attachment.path == path
    assert attachment.name == "anotherfilename.gif"
    assert attachment.mimetype == "image/gif"

    # elements can also be directly indexed
    assert isinstance(aa[0], AttachBase)
    assert isinstance(aa[1], AttachBase)

    with pytest.raises(IndexError):
        aa[2]

    # We can iterate over attachments too:
    for count, a in enumerate(aa):
        assert isinstance(a, AttachBase)

        # we'll never iterate more then the number of entries in our object
        assert count < len(aa)

    # Get the file-size of our image
    expected_size = getsize(path) * len(aa)

    # verify that's what we get as a result
    assert aa.size() == expected_size

    # Attachments can also be loaded during the instantiation of the
    # AppriseAttachment object
    aa = AppriseAttachment(attachments)

    # There is now 3 attachments
    assert len(aa) == 3

    # Reset our object
    aa.clear()
    assert len(aa) == 0
    assert not aa

    assert aa.add(
        AppriseAttachment.instantiate(
            f"file://{path}?name=andanother.png&cache=Yes"
        )
    )
    assert aa.add(
        AppriseAttachment.instantiate(
            f"file://{path}?name=andanother.png&cache=No"
        )
    )
    AppriseAttachment.instantiate(
        f"file://{path}?name=andanother.png&cache=600"
    )
    assert aa.add(
        AppriseAttachment.instantiate(
            f"file://{path}?name=andanother.png&cache=600"
        )
    )

    assert len(aa) == 3
    assert aa[0].cache is True
    assert aa[1].cache is False
    assert aa[2].cache == 600

    # Negative cache are not allowed
    assert not aa.add(
        AppriseAttachment.instantiate(
            f"file://{path}?name=andanother.png&cache=-600"
        )
    )

    # Invalid cache value
    assert not aa.add(
        AppriseAttachment.instantiate(
            f"file://{path}?name=andanother.png", cache="invalid"
        )
    )

    # No length change
    assert len(aa) == 3

    # Reset our object
    aa.clear()

    # Garbage in produces garbage out
    assert aa.add(None) is False
    assert aa.add(object()) is False
    assert aa.add(42) is False

    # length remains unchanged
    assert len(aa) == 0

    # We can add by lists as well in a variety of formats
    attachments = (
        None,
        object(),
        42,
        "garbage://",
    )

    # Add our attachments
    assert aa.add(attachments) is False

    # length remains unchanged
    assert len(aa) == 0

    # if instantiating attachments from the class, it will throw a TypeError
    # if attachments couldn't be loaded
    with pytest.raises(TypeError):
        AppriseAttachment("garbage://")

    # Load our other attachment types
    aa = AppriseAttachment(location=ContentLocation.LOCAL)

    # Hosted type won't allow us to import files
    aa = AppriseAttachment(location=ContentLocation.HOSTED)
    assert len(aa) == 0

    # Add our attachments defined a the head of this function
    aa.add(attachments)

    # Our length is still zero because we can't import files in
    # a hosted environment
    assert len(aa) == 0

    # Inaccessible type prevents the adding of new stuff
    aa = AppriseAttachment(location=ContentLocation.INACCESSIBLE)
    assert len(aa) == 0

    # Add our attachments defined a the head of this function
    aa.add(attachments)

    # Our length is still zero
    assert len(aa) == 0

    with pytest.raises(TypeError):
        # Invalid location specified
        AppriseAttachment(location="invalid")

    # test cases when file simply doesn't exist
    aa = AppriseAttachment("file://non-existant-file.png")
    # Our length is still 1
    assert len(aa) == 1
    # Our object will still return a True
    assert aa

    # However our indexed entry will not
    assert not aa[0]

    # length will return 0
    assert len(aa[0]) == 0

    # Total length will also return 0
    assert aa.size() == 0


@mock.patch("requests.get")
def test_apprise_attachment_truncate(mock_get):
    """
    API: AppriseAttachment when truncation in place

    """

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_get.return_value = response

    # our Apprise Object
    ap_obj = Apprise()

    # Add ourselves an object set to truncate
    ap_obj.add("json://localhost/?method=GET&overflow=truncate")

    # Create ourselves an attachment object
    aa = AppriseAttachment()

    # There are no attachents loaded
    assert len(aa) == 0

    # Object can be directly checked as a boolean; response is False
    # when there are no entries loaded
    assert not aa

    # Add 2 attachments
    assert aa.add(join(TEST_VAR_DIR, "apprise-test.gif"))
    assert aa.add(join(TEST_VAR_DIR, "apprise-test.png"))

    assert mock_get.call_count == 0
    assert ap_obj.notify(body="body", title="title", attach=aa)

    assert mock_get.call_count == 1

    # Our first item was truncated, so only 1 attachment
    details = mock_get.call_args_list[0]
    dataset = json.loads(details[1]["data"])
    assert len(dataset["attachments"]) == 1

    # Reset our object
    mock_get.reset_mock()

    # our Apprise Object
    ap_obj = Apprise()

    # Add ourselves an object set to upstream
    ap_obj.add("json://localhost/?method=GET&overflow=upstream")

    # Create ourselves an attachment object
    aa = AppriseAttachment()

    # Add 2 attachments
    assert aa.add(join(TEST_VAR_DIR, "apprise-test.gif"))
    assert aa.add(join(TEST_VAR_DIR, "apprise-test.png"))

    assert mock_get.call_count == 0
    assert ap_obj.notify(body="body", title="title", attach=aa)

    assert mock_get.call_count == 1

    # Our item was not truncated, so all attachments
    details = mock_get.call_args_list[0]
    dataset = json.loads(details[1]["data"])
    assert len(dataset["attachments"]) == 2


def test_apprise_attachment_instantiate():
    """
    API: AppriseAttachment.instantiate()

    """
    assert (
        AppriseAttachment.instantiate("file://?", suppress_exceptions=True)
        is None
    )

    assert (
        AppriseAttachment.instantiate("invalid://?", suppress_exceptions=True)
        is None
    )

    class BadAttachType(AttachBase):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

            # We fail whenever we're initialized
            raise TypeError()

    # Store our bad attachment type in our schema map
    A_MGR["bad"] = BadAttachType

    with pytest.raises(TypeError):
        AppriseAttachment.instantiate("bad://path", suppress_exceptions=False)

    # Same call but exceptions suppressed
    assert (
        AppriseAttachment.instantiate("bad://path", suppress_exceptions=True)
        is None
    )


def test_attachment_matrix_dynamic_importing(tmpdir):
    """
    API: Apprise() Attachment Matrix Importing

    """

    # Make our new path valid
    suite = tmpdir.mkdir("apprise_attach_test_suite")
    suite.join("__init__.py").write("")

    module_name = "badattach"

    # Create a base area to work within
    base = suite.mkdir(module_name)
    base.join("__init__.py").write("")

    # Test no app_id
    base.join("AttachBadFile1.py").write(cleandoc("""
        class AttachBadFile1:
            pass
        """))

    # No class of the same name
    base.join("AttachBadFile2.py").write(cleandoc("""
        class BadClassName:
            pass
        """))

    # Exception thrown
    base.join("AttachBadFile3.py").write("""raise ImportError()""")

    # Utilizes a schema:// already occupied (as string)
    base.join("AttachGoober.py").write(cleandoc("""
        from apprise import AttachBase
        class AttachGoober(AttachBase):
            # This class tests the fact we have a new class name, but we're
            # trying to over-ride items previously used

            # The default simple (insecure) protocol
            protocol = 'http'

            # The default secure protocol
            secure_protocol = 'https'
        """))

    # Utilizes a schema:// already occupied (as tuple)
    base.join("AttachBugger.py").write(cleandoc("""
        from apprise import AttachBase
        class AttachBugger(AttachBase):
            # This class tests the fact we have a new class name, but we're
            # trying to over-ride items previously used

            # The default simple (insecure) protocol
            protocol = ('http', 'bugger-test' )

            # The default secure protocol
            secure_protocol = ('https', 'bugger-tests')
        """))

    A_MGR.load_modules(path=str(base), name=module_name)
