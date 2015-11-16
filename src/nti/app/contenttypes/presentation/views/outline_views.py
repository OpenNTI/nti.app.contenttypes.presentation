#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from .. import MessageFactory as _

import time
import simplejson

from zope import component

from zope.event import notify

from zope.intid import IIntIds

from pyramid.view import view_config
from pyramid.view import view_defaults
from pyramid import httpexceptions as hexc

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment

from nti.appserver.ugd_edit_views import UGDPutView
from nti.appserver.ugd_query_views import RecursiveUGDView

from nti.common.maps import CaseInsensitiveDict

from nti.common.time import time_to_64bit_int

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import NTI_COURSE_OUTLINE_NODE

from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseOutlineContentNode
from nti.contenttypes.courses.interfaces import CourseOutlineNodeMovedEvent

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance

from nti.contenttypes.presentation import NTI_LESSON_OVERVIEW

from nti.contenttypes.presentation.interfaces import IVisible
from nti.contenttypes.presentation.interfaces import IMediaRef
from nti.contenttypes.presentation.interfaces import INTIMedia
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.contenttypes.presentation.lesson import NTILessonOverView

from nti.coremetadata.interfaces import IPublishable

from nti.dataserver import authorization as nauth

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.externalization.externalization import to_external_object

from nti.mimetype.mimetype import MIME_BASE

from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import get_provider
from nti.ntiids.ntiids import get_specific
from nti.ntiids.ntiids import make_specific_safe

from nti.site.site import get_component_hierarchy_names

from nti.traversal.traversal import find_interface

from ..utils import is_item_visible
from ..utils import get_enrollment_record

from . import VIEW_NODE_CONTENTS
from . import VIEW_OVERVIEW_CONTENT
from . import VIEW_OVERVIEW_SUMMARY

CLASS = StandardExternalFields.CLASS
ITEMS = StandardExternalFields.ITEMS
MIMETYPE = StandardExternalFields.MIMETYPE
LAST_MODIFIED = StandardExternalFields.LAST_MODIFIED

class OutlineLessonOverviewMixin(object):

	def _get_lesson(self):
		context = self.request.context
		try:
			ntiid = context.LessonOverviewNTIID
			if not ntiid:
				raise hexc.HTTPServerError("Outline does not have a valid lesson overview")

			lesson = component.getUtility(INTILessonOverview, name=ntiid)
			if lesson is None:
				raise hexc.HTTPUnprocessableEntity("Cannot find lesson overview")
			return lesson
		except AttributeError:
			raise hexc.HTTPServerError("Outline does not have a lesson overview attribute")

@view_config(route_name='objects.generic.traversal',
			 context=ICourseOutlineContentNode,
			 request_method='GET',
			 permission=nauth.ACT_READ,
			 renderer='rest',
			 name=VIEW_OVERVIEW_CONTENT)
class OutlineLessonOverviewView(AbstractAuthenticatedView,
								OutlineLessonOverviewMixin):

	def __call__(self):
		lesson = self._get_lesson()
		external = to_external_object(lesson, name="render")
		external.lastModified = external[LAST_MODIFIED] = lesson.lastModified
		return external

@view_config(route_name='objects.generic.traversal',
			 context=ICourseOutlineContentNode,
			 request_method='GET',
			 permission=nauth.ACT_READ,
			 renderer='rest',
			 name=VIEW_OVERVIEW_SUMMARY)
class OutlineLessonOverviewSummaryView(RecursiveUGDView,
									   OutlineLessonOverviewMixin):

	_DEFAULT_BATCH_SIZE = None
	_DEFAULT_BATCH_START = 0

	def _do_count(self, item):
		# With older content, we're not sure where the UGD
		# may hang; so summarize per item.
		count = 0
		for ntiid_field in ('ntiid', 'target_ntiid'):
			self.ntiid = getattr(item, ntiid_field, None)
			if self.ntiid:
				try:
					results = super(OutlineLessonOverviewSummaryView, self).__call__()
					container_ntiids = results.get('Items', ())
					count += len(container_ntiids)
				except hexc.HTTPNotFound:
					pass  # Empty
		return count

	def __call__(self):
		lesson = self._get_lesson()
		result = LocatedExternalDict()
		result[ CLASS ] = 'OverviewGroupSummary'
		self.user = self.remoteUser

		mime_type = MIME_BASE + ".courses.overviewitemsummary"
		for lesson_group in lesson.items:
			for item in lesson_group.items:
				ugd_count = self._do_count(item)
				result[ item.ntiid ] = item_results = {}
				item_results[CLASS] = 'OverviewItemSummary'
				item_results[MIMETYPE] = mime_type
				item_results['ItemCount'] = ugd_count
		return result

@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_config(context=ICourseInstanceEnrollment)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   permission=nauth.ACT_READ,
			   request_method='GET',
			   name='MediaByOutlineNode')  # See decorators
class MediaByOutlineNodeDecorator(AbstractAuthenticatedView):

	def _outline_nodes(self, course):
		result = []
		def _recur(node):
			if ICourseOutlineContentNode.providedBy(node):
				if node.src and node.ContentNTIID:
					result.append(node)
			for child in node.values():
				_recur(child)

		outline = course.Outline
		if outline is not None:
			_recur(outline)
		return result

	def _do_legacy(self, course, record):
		result = None
		index_filename = "video_index.json"
		bundle = course.ContentPackageBundle
		for package in bundle.ContentPackages:
			sibling_key = package.does_sibling_entry_exist(index_filename)
			if not sibling_key:
				continue
			else:
				index_text = package.read_contents_of_sibling_entry(index_filename)
				if isinstance(index_text, bytes):
					index_text = index_text.decode('utf-8')
				result = simplejson.loads(index_text)
				break

		result = LocatedExternalDict() if not result else result
		return result

	def _do_current(self, course, record):
		result = LocatedExternalDict()
		result.__name__ = self.request.view_name
		result.__parent__ = self.request.context
		catalog = get_library_catalog()
		intids = component.getUtility(IIntIds)

		items = result[ITEMS] = {}
		containers = result['Containers'] = {}

		nodes = self._outline_nodes(course)
		ntiids = {node.ContentNTIID for node in nodes}
		result['ContainerOrder'] = [node.ContentNTIID for node in nodes]

		for item in IPresentationAssetContainer(course).values():
			# ignore non media items
			if 	(not IMediaRef.providedBy(item)
				 and not INTIMedia.providedBy(item)
				 and not INTISlideDeck.providedBy(item)):
				continue

			# ignore unpublished items
			if not IPublishable.providedBy(item) or not item.is_published:
				continue

			# check visibility
			if IVisible.providedBy(item):
				if not is_item_visible(item, self.remoteUser, record=record):
					continue
				else:
					item = INTIMedia(item, None)

			# check if ref was valid
			uid = intids.queryId(item) if item is not None else None
			if uid is None:
				continue

			# set content containers
			for ntiid in catalog.get_containers(uid):
				if ntiid in ntiids:
					containers.setdefault(ntiid, set())
					containers[ntiid].add(item.ntiid)
			items[item.ntiid] = to_external_object(item)

		sites = get_component_hierarchy_names()
		for item in catalog.search_objects(
								container_ntiids=ntiids,
								provided=INTISlideDeck,
								container_all_of=False,
								sites=sites):
			if not IPublishable.providedBy(item) or not item.is_published:
				continue
			uid = intids.getId(item)
			for ntiid in catalog.get_containers(uid):
				if ntiid in ntiids:
					containers.setdefault(ntiid, set())
					containers[ntiid].add(item.ntiid)
			items[item.ntiid] = to_external_object(item)

		# make json ready
		for k, v in list(containers.items()):
			containers[k] = list(v)
		result['Total'] = result['ItemCount'] = len(items)
		return result

	def __call__(self):
		course = ICourseInstance(self.request.context)
		record = get_enrollment_record(course, self.remoteUser)
		if record is None:
			raise hexc.HTTPForbidden(_("Must be enrolled in a course."))

		if ILegacyCourseInstance.providedBy(course):
			result = self._do_legacy(course, record)
		else:
			self.request.no_acl_decoration = True
			result = self._do_current(course, record)
		return result

class _AbstractOutlineNodeIndexView(AbstractAuthenticatedView):

	def _get_index(self):
		"""
		If the user supplies an index, we expect it to exist on the
		path: '.../index/<index_number>'
		"""
		index = None
		if 		self.request.subpath \
			and self.request.subpath[0] == 'index' \
			and len(self.request.subpath) > 1:
			try:
				index = self.request.subpath[1]
				index = int(index)
			except (TypeError, IndexError):
				raise hexc.HTTPUnprocessableEntity('Invalid index %s' % index)
		return index

@view_config(route_name='objects.generic.traversal',
			 context=ICourseOutlineNode,
			 request_method='POST',
			 permission=nauth.ACT_CONTENT_EDIT,
			 renderer='rest',
			 name=VIEW_NODE_CONTENTS)
class OutlineNodeInsertView(_AbstractOutlineNodeIndexView,
							ModeledContentUploadRequestUtilsMixin):
	"""
	Creates an outline node at the given index path, if supplied.
	Otherwise, append to our context.

	We could generalize this and the index views for
	all IOrderedContainers.
	"""

	def _get_catalog_entry( self, outline ):
		course = find_interface(outline, ICourseInstance, strict=False)
		result = ICourseCatalogEntry(course, None)
		return result

	def _create_node_ntiid(self):
		"""
		Build an ntiid for our new node, making sure we don't conflict
		with other ntiids. To help ensure this (and to avoid collisions
		with deleted nodes), we use the creator and a timestamp.
		"""
		parent = self.context
		try:
			base = parent.ntiid
		except AttributeError:
			# Outline, use catalog entry
			entry = self._get_catalog_entry( parent )
			base = entry.ntiid if entry is not None else None
		provider = get_provider(base) or 'NTI'
		current_time = time_to_64bit_int(time.time())
		specific_base = '%s.%s.%s' % (get_specific(base),
									  self.remoteUser.username, current_time)
		idx = 0
		while True:
			specific = specific_base + ".%s" % idx
			specific = make_specific_safe(specific)
			ntiid = make_ntiid(nttype=NTI_COURSE_OUTLINE_NODE,
							   base=base,
							   provider=provider,
							   specific=specific)
			if ntiid not in parent:
				break
			idx += 1
		return ntiid

	def _set_node_ntiid(self, new_node):
		content_ntiid = getattr(new_node, 'ContentNTIID', None)
		ntiid = content_ntiid if content_ntiid else self._create_node_ntiid()
		new_node.ntiid = ntiid

	def _make_lesson_node(self, node):
		# TODO Create node, register, set.
		# TODO Carlos verify
		# Lesson field empty?
		lesson_ntiid = make_ntiid(nttype=NTI_LESSON_OVERVIEW, base=node.ntiid)
		new_lesson = NTILessonOverView()
		new_lesson.ntiid = lesson_ntiid
		new_lesson.__parent__ = node
		new_lesson.title = node.title
		new_lesson.creator = node.creator
		return new_lesson

	def readInput(self):
		result = super(OutlineNodeInsertView, self).readInput()
		if result.get( MIMETYPE ) == "application/vnd.nextthought.courses.courseoutlinecontentnode":
			# This ContentNTIID field is arbitrary; mainly, the
			# clients use the presence of this field to determine
			# if the node is 'clickable'. We add a placeholder until
			# we create our lesson.
			if 'ContentNTIID' not in result:
				result['ContentNTIID'] = self._create_node_ntiid()
		return result

	def _get_new_node(self):
		# We could support auto-publishing based on type here.
		creator = self.remoteUser
		new_node = self.readCreateUpdateContentObject(creator)
		self._set_node_ntiid(new_node)
		if ICourseOutlineContentNode.providedBy( new_node ):
			new_lesson = self._make_lesson_node( new_node )
			new_node.ContentNTIID = new_lesson.ntiid
			assert new_node.ContentNTIID != new_node.ntiid
		new_node.locked = True
		return new_node

	def _reorder_for_ntiid(self, ntiid, index, old_keys):
		"""
		For a given ntiid and index, insert the ntiid into
		the `index` slot, reordering the parent.
		"""
		new_keys = old_keys[:index]
		new_keys.append(ntiid)
		new_keys.extend(old_keys[index:])
		self.context.updateOrder(new_keys)

	def __call__(self):
		index = self._get_index()
		index = index if index is None else max(index,0)
		new_node = self._get_new_node()
		old_keys = list(self.context.keys())
		children_size = len(old_keys)
		self.context.append(new_node)

		if index is not None and index < children_size:
			self._reorder_for_ntiid(new_node.ntiid, index, old_keys)
		logger.info('Created new outline node (%s)', new_node.ntiid)
		return new_node

@view_config(route_name='objects.generic.traversal',
			 context=ICourseOutlineNode,
			 request_method='PUT',
			 permission=nauth.ACT_CONTENT_EDIT,
			 renderer='rest',
			 name=VIEW_NODE_CONTENTS)
class OutlineNodeMoveView(OutlineNodeInsertView):
	"""
	Move the given ntiid to the given index.
	"""

	def __call__(self):
		index = self._get_index()
		if index is None:
			raise hexc.HTTPBadRequest('No index supplied')
		values = CaseInsensitiveDict(self.readInput())
		old_keys = list(self.context.keys())
		ntiid = values.get('ntiid')

		# TODO This may be a move from another node. Can we
		# detect that easily?
		# TODO Delete API, can we tell when to unregister/clean-up
		# orphaned nodes.
		if 		ntiid not in old_keys \
			or 	index >= len(old_keys) \
			or 	index < 0:
			raise hexc.HTTPConflict('Invalid index or ntiid (%s) (%s)' % (ntiid, index))

		old_keys.remove(ntiid)
		principal = self.remoteUser.username
		self._reorder_for_ntiid(ntiid, index, old_keys)
		notify(CourseOutlineNodeMovedEvent(self.context, principal, index))
		logger.info('Moved node (%s) to index (%s)', ntiid, index)
		return hexc.HTTPOk()

@view_config(route_name='objects.generic.traversal',
			 context=ICourseOutlineNode,
			 request_method='DELETE',
			 permission=nauth.ACT_CONTENT_EDIT,
			 renderer='rest',
			 name=VIEW_NODE_CONTENTS)
class OutlineNodeDeleteView(OutlineNodeInsertView):
	"""
	Delete the given ntiid in our context.
	"""

	def __call__(self):
		values = CaseInsensitiveDict(self.readInput())
		old_keys = list(self.context.keys())
		ntiid = values.get('ntiid')

		if ntiid not in old_keys:
			raise hexc.HTTPConflict('Invalid ntiid (%s)' % ntiid)
		# TODO Do we want to permanently delete nodes, or delete placeholder
		# mark them (to undo and save transaction history)?
		del self.context[ntiid]
		logger.info( 'Deleted entity in outline %s', ntiid )
		return hexc.HTTPOk()

@view_config(route_name='objects.generic.traversal',
			 context=ICourseOutlineNode,
			 request_method='PUT',
			 permission=nauth.ACT_CONTENT_EDIT,
			 renderer='rest')
class OutlineNodePutView(UGDPutView):

	def readInput(self, value=None):
		result = UGDPutView.readInput(self, value=value)
		result.pop('ntiid', None)
		result.pop('NTIID', None)
		return result
