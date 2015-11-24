#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os

from zope import lifecycleevent

from ZODB.interfaces import IConnection

from plone.namedfile.file import getImageInfo

from slugify import slugify_filename

from nti.app.products.courseware.interfaces import ICourseRootFolder

from nti.common.random import generate_random_hex_string

from nti.contentfile.model import ContentBlobFile
from nti.contentfile.model import ContentBlobImage

from nti.contentfolder.model import ContentFolder

from nti.contentlibrary.indexed_data import get_registry

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.links import Link
from nti.links.externalization import render_link

from nti.traversal.traversal import find_interface

from . import ASSETS_FOLDER

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
		result.data = source.read()  # set content type
	else:
		result = ContentBlobFile()
		result.data = source.read()
		result.contentType = source.contentType
	result.name = filename
	result.filename = filename
	return result

def db_connection(registry=None):
	registry = get_registry(registry)
	result = IConnection(registry, None)
	return result

def intid_register(item, registry=None, connection=None):
	connection = db_connection(registry) if connection is None else connection
	if connection is not None:
		connection.add(item)
		lifecycleevent.added(item)
		return True
	return False

def get_render_link(item):
	try:
		link = Link(item)
		href = render_link(link)['href']
		result = href + '/@@view'
	except (KeyError, ValueError, AssertionError):
		pass  # Nope
	return result

def get_assets_folder(context, strict=True):
	course = ICourseInstance(context, None)
	if course is None:
		course = find_interface(context, ICourseInstance, strict=strict)
	root = ICourseRootFolder(course, None)
	if root is not None:
		if ASSETS_FOLDER not in root:
			result = ContentFolder(name=ASSETS_FOLDER)
			root[ASSETS_FOLDER] = result
		else:
			result = root[ASSETS_FOLDER]
		return result
	return None
