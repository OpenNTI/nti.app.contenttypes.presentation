#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os
from urllib import unquote
from urlparse import urlparse

from zope import component
from zope import lifecycleevent

from zope.event import notify

from zope.location.location import locate
from zope.location.interfaces import ILocation

from zope.traversing.interfaces import IEtcNamespace

from ZODB.interfaces import IConnection

from plone.namedfile.file import getImageInfo
from plone.namedfile.interfaces import INamed

from slugify import slugify_filename

from nti.app.contentfile import to_external_href

from nti.app.products.courseware.interfaces import ICourseRootFolder

from nti.common.random import generate_random_hex_string

from nti.contentfile.model import ContentBlobFile
from nti.contentfile.model import ContentBlobImage

from nti.contentfolder.model import ContentFolder

from nti.contentlibrary.indexed_data import get_registry
from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation import iface_of_asset
from nti.contenttypes.presentation.interfaces import WillRemovePresentationAssetEvent

from nti.ntiids.ntiids import find_object_with_ntiid
from nti.ntiids.ntiids import is_valid_ntiid_string as is_valid_ntiid

from nti.site.utils import unregisterUtility
from nti.site.site import get_component_hierarchy_names

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
		result = to_external_href(item) # adds @@view
	except Exception:
		pass  # Nope
	return result

def get_file_from_link(link):
	result = None
	try:
		if '@@view' in link or '@@download' in link:
			path = urlparse(link).path
			path = os.path.split(path)[0]
		else:
			path = link
		ntiid = unquote(os.path.split(path)[1] or u'') # last part of path
		result = find_object_with_ntiid(ntiid) if is_valid_ntiid(ntiid) else None
		if INamed.providedBy(result):
			return result
	except Exception:
		pass  # Nope
	return None

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

def component_registry(context, provided, name=None):
	sites_names = list(get_component_hierarchy_names())
	sites_names.reverse()  # higher sites first
	name = name or getattr(context, 'ntiid', None)
	hostsites = component.getUtility(IEtcNamespace, name='hostsites')
	for site_name in sites_names:
		try:
			folder = hostsites[site_name]
			registry = folder.getSiteManager()
			if registry.queryUtility(provided, name=name) == context:
				return registry
		except KeyError:
			pass
	return get_registry()

def notify_removed(item):
	lifecycleevent.removed(item)
	if ILocation.providedBy(item):
		locate(item, None, None)

def remove_asset(item, registry=None, catalog=None):
	notify(WillRemovePresentationAssetEvent(item))
	# remove utility
	registry = get_registry(registry)
	unregisterUtility(registry, provided=iface_of_asset(item), name=item.ntiid)
	# unindex
	catalog = get_library_catalog() if catalog is None else catalog
	catalog.unindex(item)
	# broadcast removed
	notify_removed(item)
