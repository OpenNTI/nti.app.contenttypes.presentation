#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os

from plone.namedfile.file import getImageInfo

from slugify import slugify_filename

from nti.common.random import generate_random_hex_string

from nti.contentfile.model import ContentBlobFile
from nti.contentfile.model import ContentBlobImage

from .. import VIEW_NODE_CONTENTS
from .. import VIEW_OVERVIEW_CONTENT
from .. import VIEW_OVERVIEW_SUMMARY

def slugify(text, container):
    separator = '_'
    newtext = slugify_filename(text)
    text_noe, ext = os.path.splitext(newtext)
    while True:
        s = generate_random_hex_string(6)
        newtext = "%s%s%s%s" % (text_noe, separator, s, ext)
        if newtext not in container:
            break
    return newtext

def get_namedfile(source, filename=None):
    content_type, _, _ = getImageInfo(source)
    source.seek(0)  # reset
    if content_type:  # it's an image
        result = ContentBlobImage()
        result.data = source.read() # set content type
    else:
        result = ContentBlobFile()
        result.data = source.read()
        result.contentType = source.contentType
    result.name = filename
    result.filename = filename
    return result
