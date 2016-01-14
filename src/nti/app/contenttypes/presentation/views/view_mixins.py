#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from .. import MessageFactory as _

import re
import os
import hashlib
from urllib import unquote
from urlparse import urlparse

from pyramid import httpexceptions as hexc

from zope.event import notify

from plone.namedfile.file import getImageInfo
from plone.namedfile.interfaces import INamed

from slugify import slugify_filename

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contentfile import to_external_href

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware.utils import get_assets_folder

from nti.appserver.pyramid_authorization import has_permission

from nti.common.maps import CaseInsensitiveDict
from nti.common.random import generate_random_hex_string

from nti.coremetadata.interfaces import IPublishable

from nti.contentfile.model import ContentBlobFile
from nti.contentfile.model import ContentBlobImage

from nti.dataserver import authorization as nauth

from nti.ntiids.ntiids import find_object_with_ntiid
from nti.ntiids.ntiids import is_valid_ntiid_string as is_valid_ntiid

get_assets_folder = get_assets_folder # re-export

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

def get_namedfile(source, name=None):
	contentType = getattr(source, 'contentType', None)
	if contentType:
		factory = ContentBlobFile
	else:
		contentType, _, _ = getImageInfo(source)
		source.seek(0)  # reset
		factory = ContentBlobImage if contentType else ContentBlobFile
	contentType = contentType or u'application/octet-stream'
	result = factory()
	result.name = name
	# for filename we want to use the filename as originally provided on the source, not
	# the sluggified internal name. This allows us to give it back in the
	# Content-Disposition header on download
	result.filename = getattr(source, 'filename', None) or getattr(source, 'name', name)
	result.data = source.read()
	result.contentType = contentType
	return result

def get_download_href(item):
	try:
		result = to_external_href(item, True)
		return result
	except Exception:
		pass  # Nope
	return None

def get_file_from_link(link):
	result = None
	try:
		if re.match('(.+)/(@@)?[view|download](\/.*)?', link):
			path = urlparse(link).path
			path = os.path.split(path)[0]
			if path.endswith('download') or path.endswith('view'):
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

	:raises HTTPUnprocessableEntity if the parents do not exist, if the item
		does not exist in the old parent, or if moving between outlines.
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

	def _get_object_to_move(self, ntiid, old_parent=None):
		obj = find_object_with_ntiid(ntiid)
		if obj is None:
			raise hexc.HTTPUnprocessableEntity(_('Object no longer exists.'))
		return obj

	def _get_old_parent(self, old_parent_ntiid):
		result = None
		if old_parent_ntiid:
			result = find_object_with_ntiid(old_parent_ntiid)
			if result is None:
				raise hexc.HTTPUnprocessableEntity(_('Old node parent no longer exists.'))
		return result

	def _get_new_parent(self, context_ntiid, new_parent_ntiid):
		if new_parent_ntiid == context_ntiid:
			new_parent = self.context
		else:
			new_parent = find_object_with_ntiid(new_parent_ntiid)

		if new_parent is None:
			# Really shouldn't happen if we validate this object is in our outline.
			raise hexc.HTTPUnprocessableEntity(_('New parent does not exist.'))
		return new_parent

	def __call__(self):
		values = CaseInsensitiveDict(self.readInput())
		index = values.get('Index')
		ntiid = values.get('ObjectNTIID')
		new_parent_ntiid = values.get('ParentNTIID')
		old_parent_ntiid = values.get('OldParentNTIID')
		context_ntiid = self._get_context_ntiid()

		new_parent = self._get_new_parent( context_ntiid, new_parent_ntiid )
		old_parent = self._get_old_parent( old_parent_ntiid )
		if old_parent is None:
			old_parent = new_parent
		obj = self._get_object_to_move( ntiid, old_parent )

		children_ntiids = self._get_children_ntiids(context_ntiid)
		if 		new_parent_ntiid not in children_ntiids \
			or (	old_parent_ntiid
				and old_parent_ntiid not in children_ntiids):
			raise hexc.HTTPUnprocessableEntity(_('Cannot move between root objects.'))

		if index is not None and index < 0:
			raise hexc.HTTPBadRequest(_('Invalid index.'))
		new_parent.insert(index, obj)

		# Make sure they don't move the object within the same node and
		# attempt to delete from that node.
		if old_parent_ntiid and old_parent_ntiid != new_parent_ntiid:
			did_remove = self._remove_from_parent(old_parent, obj)
			if not did_remove:
				raise hexc.HTTPUnprocessableEntity(_('Moved node does not exist in old parent.'))
			old_parent.child_order_locked = True

		if self.notify_type:
			notify(self.notify_type(obj, self.remoteUser.username, index))
		logger.info('Moved item (%s) at index (%s) (to=%s) (from=%s)',
					ntiid, index, new_parent_ntiid, old_parent_ntiid)
		new_parent.child_order_locked = True
		return self.context

class PublishVisibilityMixin(object):

	def _is_visible(self, item):
		"""
		Define whether this possibly publishable object is visible to the
		remote user.
		"""
		return 		not IPublishable.providedBy(item) \
				or 	item.is_published() \
				or	has_permission(nauth.ACT_CONTENT_EDIT, item, self.request)

class IndexedRequestMixin(object):

	def _get_index(self):
		"""
		If the user supplies an index, we expect it to exist on the
		path: '.../index/<index_number>'
		"""
		index = None
		if 		self.request.subpath \
			and self.request.subpath[0] == 'index':
			try:
				index = self.request.subpath[1]
				index = int(index)
			except (TypeError, IndexError):
				raise hexc.HTTPUnprocessableEntity(_('Invalid index %s' % index))
		index = index if index is None else max(index, 0)
		return index

class NTIIDPathMixin(object):

	def _get_ntiid(self):
		"""
		Looks for a user supplied ntiid in the context path: '.../ntiid/<ntiid>'.
		"""
		result = None
		if 		self.request.subpath \
			and self.request.subpath[0] == 'ntiid':
			try:
				result = self.request.subpath[1]
			except (TypeError, IndexError):
				pass
		if result is None or not is_valid_ntiid( result ):
			raise hexc.HTTPUnprocessableEntity(_('Invalid ntiid %s' % result))
		return result
