#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from .. import MessageFactory as _

import os
import hashlib
from urllib import unquote
from urlparse import urlparse

from pyramid import httpexceptions as hexc

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

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contentfile import to_external_href

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware.interfaces import ICourseRootFolder

from nti.appserver.pyramid_authorization import has_permission

from nti.common.maps import CaseInsensitiveDict

from nti.common.random import generate_random_hex_string

from nti.coremetadata.interfaces import IPublishable

from nti.contentfile.model import ContentBlobFile
from nti.contentfile.model import ContentBlobImage

from nti.contentfolder.model import ContentFolder

from nti.contentlibrary.indexed_data import get_registry
from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation import iface_of_asset
from nti.contenttypes.presentation.interfaces import WillRemovePresentationAssetEvent

from nti.dataserver import authorization as nauth

from nti.ntiids.ntiids import find_object_with_ntiid
from nti.ntiids.ntiids import is_valid_ntiid_string as is_valid_ntiid

from nti.site.utils import unregisterUtility
from nti.site.site import get_component_hierarchy_names

from nti.traversal.traversal import find_interface

from . import ASSETS_FOLDER

def hexdigest(data, hasher=None):
	hasher = hashlib.sha256() if hasher is None else hasher
	hasher.update(data)
	result = hasher.hexdigest()
	return result

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
	contentType = getattr(source, 'contentType', None)
	if contentType:
		factory = ContentBlobFile
	else:
		contentType, _, _ = getImageInfo(source)
		source.seek(0)  # reset
		factory = ContentBlobImage if contentType else ContentBlobFile
	contentType = contentType or u'application/octet-stream'

	result = factory()
	result.name = filename
	result.filename = filename
	result.data = source.read()
	result.contentType = contentType
	return result

def db_connection(registry=None):
	registry = get_registry(registry)
	result = IConnection(registry, None)
	return result

def add_2_connection(item, registry=None, connection=None):
	connection = db_connection(registry) if connection is None else connection
	if connection is not None and getattr(item, '_p_jar', None) is None:
		connection.add(item)
	result = getattr(item, '_p_jar', None) is not None
	return result

def intid_register(item, registry=None, connection=None):
	if add_2_connection(item, registry, connection):
		lifecycleevent.added(item)
		return True
	return False

def get_render_link(item):
	try:
		result = to_external_href(item)  # adds @@view
	except Exception:
		pass  # Nope
	return result

def get_file_from_link(link):
	result = None
	try:
		if link.endswith('view') or link.endswith('download'):
			path = urlparse(link).path
			path = os.path.split(path)[0]
		else:
			path = link
		ntiid = unquote(os.path.split(path)[1] or u'')  # last part of path
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

class AbstractChildMoveView(AbstractAuthenticatedView,
							ModeledContentUploadRequestUtilsMixin):
	"""
	Move a given object between two parents in a course. The source
	and target NTIIDs must exist beneath the given context (no
	nodes are allowed to move between roots).

	Body elements:

	ObjectNTIID
		The NTIID of the object being moved.

	ParentNTIID
		The NTIID of the new parent node of the object being moved.

	Index
		(Optional) The index at which to insert the node in our parent.

	OldParentNTIID
		(Optional) The NTIID of the old parent of our moved
		node.
	"""

	# The notify event on move.
	notify_type = None

	def _get_children_ntiids(self, parent_ntiid=None):
		"""
		Subclasses should implement this to allow
		validation of movements within this context.
		"""
		return ()

	def _get_context_ntiid(self):
		"""
		Subclasses should implement this to define the
		contextual ntiid.
		"""
		return getattr(self.context, 'ntiid', None)

	def _remove_from_parent(self, parent, obj):
		"""
		Define how to remove an item from a parent.
		"""
		raise NotImplementedError()

	def _add_to_parent(self, parent, ntiid, index):
		"""
		Define how to add an item to a parent at an index.
		"""
		raise NotImplementedError()

	def __call__(self):
		values = CaseInsensitiveDict(self.readInput())
		index = values.get('Index')
		ntiid = values.get('ObjectNTIID')
		new_parent_ntiid = values.get('ParentNTIID')
		old_parent_ntiid = values.get('OldParentNTIID')
		context_ntiid = self._get_context_ntiid()

		obj = find_object_with_ntiid(ntiid)
		if obj is None:
			raise hexc.HTTPUnprocessableEntity(_('Object no longer exists.'))

		children_ntiids = self._get_children_ntiids(context_ntiid)
		if 		new_parent_ntiid not in children_ntiids \
			or (old_parent_ntiid
				and old_parent_ntiid not in children_ntiids):
			raise hexc.HTTPUnprocessableEntity(_('Cannot move between root objects.'))

		if new_parent_ntiid == context_ntiid:
			new_parent = self.context
		else:
			new_parent = find_object_with_ntiid(new_parent_ntiid)

		if new_parent is None:
			# Really shouldn't happen if we validate this object is in our outline.
			raise hexc.HTTPUnprocessableEntity(_('New parent does not exist.'))

		if index is not None and index < 0:
			raise hexc.HTTPBadRequest(_('Invalid index.'))

		self._add_to_parent(new_parent, obj, index)

		# Make sure they don't move the object within the same node and
		# attempt to delete from that node.
		if old_parent_ntiid and old_parent_ntiid != new_parent_ntiid:
			old_parent = find_object_with_ntiid(old_parent_ntiid)
			if old_parent is None:
				raise hexc.HTTPUnprocessableEntity(_('Old node parent no longer exists.'))
			self._remove_from_parent(old_parent, obj)

		if self.notify_type:
			notify(self.notify_type(new_parent, self.remoteUser.username, index))
		logger.info('Moved item (%s) at index (%s) (to=%s) (from=%s)',
					ntiid, index, new_parent_ntiid, old_parent_ntiid)
		return hexc.HTTPOk()

class PublishVisibilityMixin(object):

	def _is_visible(self, item):
		"""
		Define whether this possibly publishable object is visible to the
		remote user.
		"""
		return 		not IPublishable.providedBy(item) \
				or 	item.is_published() \
				or	has_permission(nauth.ACT_CONTENT_EDIT, item, self.request)
