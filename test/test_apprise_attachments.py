# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 Chris Caron <lead2gold@gmail.com>
# All rights reserved.
#
# This code is licensed under the MIT License.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files(the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and / or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions :
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import sys
import pytest
from os.path import getsize
from os.path import join
from os.path import dirname
from apprise.AppriseAttachment import AppriseAttachment
from apprise.AppriseAsset import AppriseAsset
from apprise.attachment.AttachBase import AttachBase
from apprise.common import ATTACHMENT_SCHEMA_MAP
from apprise.attachment import __load_matrix
from apprise.common import ContentLocation

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

TEST_VAR_DIR = join(dirname(__file__), 'var')


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
    path = join(TEST_VAR_DIR, 'apprise-test.gif')
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
        'file://{}?name=newfilename.gif?cache=120'.format(path),
        AppriseAttachment.instantiate(
            'file://{}?name=anotherfilename.gif'.format(path), cache=100),
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
    assert attachment.name == 'anotherfilename.gif'
    assert attachment.mimetype == 'image/gif'

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

    assert aa.add(AppriseAttachment.instantiate(
        'file://{}?name=andanother.png&cache=Yes'.format(path)))
    assert aa.add(AppriseAttachment.instantiate(
        'file://{}?name=andanother.png&cache=No'.format(path)))
    AppriseAttachment.instantiate(
        'file://{}?name=andanother.png&cache=600'.format(path))
    assert aa.add(AppriseAttachment.instantiate(
        'file://{}?name=andanother.png&cache=600'.format(path)))

    assert len(aa) == 3
    assert aa[0].cache is True
    assert aa[1].cache is False
    assert aa[2].cache == 600

    # Negative cache are not allowed
    assert not aa.add(AppriseAttachment.instantiate(
        'file://{}?name=andanother.png&cache=-600'.format(path)))

    # Invalid cache value
    assert not aa.add(AppriseAttachment.instantiate(
        'file://{}?name=andanother.png'.format(path), cache='invalid'))

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
        'garbage://',
    )

    # Add our attachments
    assert aa.add(attachments) is False

    # length remains unchanged
    assert len(aa) == 0

    # if instantiating attachments from the class, it will throw a TypeError
    # if attachments couldn't be loaded
    with pytest.raises(TypeError):
        AppriseAttachment('garbage://')

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
    aa = AppriseAttachment('file://non-existant-file.png')
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


def test_apprise_attachment_instantiate():
    """
    API: AppriseAttachment.instantiate()

    """
    assert AppriseAttachment.instantiate(
        'file://?', suppress_exceptions=True) is None

    assert AppriseAttachment.instantiate(
        'invalid://?', suppress_exceptions=True) is None

    class BadAttachType(AttachBase):
        def __init__(self, **kwargs):
            super(BadAttachType, self).__init__(**kwargs)

            # We fail whenever we're initialized
            raise TypeError()

    # Store our bad attachment type in our schema map
    ATTACHMENT_SCHEMA_MAP['bad'] = BadAttachType

    with pytest.raises(TypeError):
        AppriseAttachment.instantiate(
            'bad://path', suppress_exceptions=False)

    # Same call but exceptions suppressed
    assert AppriseAttachment.instantiate(
        'bad://path', suppress_exceptions=True) is None


def test_apprise_attachment_matrix_load():
    """
    API: AppriseAttachment() matrix initialization

    """

    import apprise

    class AttachmentDummy(AttachBase):
        """
        A dummy wrapper for testing the different options in the load_matrix
        function
        """

        # The default descriptive name associated with the Notification
        service_name = 'dummy'

        # protocol as tuple
        protocol = ('uh', 'oh')

        # secure protocol as tuple
        secure_protocol = ('no', 'yes')

    class AttachmentDummy2(AttachBase):
        """
        A dummy wrapper for testing the different options in the load_matrix
        function
        """

        # The default descriptive name associated with the Notification
        service_name = 'dummy2'

        # secure protocol as tuple
        secure_protocol = ('true', 'false')

    class AttachmentDummy3(AttachBase):
        """
        A dummy wrapper for testing the different options in the load_matrix
        function
        """

        # The default descriptive name associated with the Notification
        service_name = 'dummy3'

        # secure protocol as string
        secure_protocol = 'true'

    class AttachmentDummy4(AttachBase):
        """
        A dummy wrapper for testing the different options in the load_matrix
        function
        """

        # The default descriptive name associated with the Notification
        service_name = 'dummy4'

        # protocol as string
        protocol = 'true'

    # Generate ourselves a fake entry
    apprise.attachment.AttachmentDummy = AttachmentDummy
    apprise.attachment.AttachmentDummy2 = AttachmentDummy2
    apprise.attachment.AttachmentDummy3 = AttachmentDummy3
    apprise.attachment.AttachmentDummy4 = AttachmentDummy4

    __load_matrix()

    # Call it again so we detect our entries already loaded
    __load_matrix()


def test_attachment_matrix_dynamic_importing(tmpdir):
    """
    API: Apprise() Attachment Matrix Importing

    """

    # Make our new path valid
    suite = tmpdir.mkdir("apprise_attach_test_suite")
    suite.join("__init__.py").write('')

    module_name = 'badattach'

    # Update our path to point to our new test suite
    sys.path.insert(0, str(suite))

    # Create a base area to work within
    base = suite.mkdir(module_name)
    base.join("__init__.py").write('')

    # Test no app_id
    base.join('AttachBadFile1.py').write(
        """
class AttachBadFile1:
    pass""")

    # No class of the same name
    base.join('AttachBadFile2.py').write(
        """
class BadClassName:
    pass""")

    # Exception thrown
    base.join('AttachBadFile3.py').write("""raise ImportError()""")

    # Utilizes a schema:// already occupied (as string)
    base.join('AttachGoober.py').write(
        """
from apprise import AttachBase
class AttachGoober(AttachBase):
    # This class tests the fact we have a new class name, but we're
    # trying to over-ride items previously used

    # The default simple (insecure) protocol
    protocol = 'http'

    # The default secure protocol
    secure_protocol = 'https'""")

    # Utilizes a schema:// already occupied (as tuple)
    base.join('AttachBugger.py').write("""
from apprise import AttachBase
class AttachBugger(AttachBase):
    # This class tests the fact we have a new class name, but we're
    # trying to over-ride items previously used

    # The default simple (insecure) protocol
    protocol = ('http', 'bugger-test' )

    # The default secure protocol
    secure_protocol = ('https', 'bugger-tests')""")

    __load_matrix(path=str(base), name=module_name)
