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
from zope import lifecycleevent

from zope.event import notify

from zope.intid import IIntIds

from ZODB.interfaces import IConnection

from pyramid.view import view_config
from pyramid.view import view_defaults
from pyramid import httpexceptions as hexc

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment

from nti.appserver.ugd_edit_views import UGDPutView
from nti.appserver.ugd_query_views import RecursiveUGDView

from nti.appserver.pyramid_authorization import has_permission

from nti.common.time import time_to_64bit_int
from nti.common.maps import CaseInsensitiveDict

from nti.contentlibrary.indexed_data import get_registry
from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import NTI_COURSE_OUTLINE_NODE

from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseOutlineCalendarNode
from nti.contenttypes.courses.interfaces import ICourseOutlineContentNode
from nti.contenttypes.courses.interfaces import CourseOutlineNodeMovedEvent

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance

from nti.contenttypes.presentation import NTI_LESSON_OVERVIEW

from nti.contenttypes.presentation.interfaces import IVisible
from nti.contenttypes.presentation.interfaces import IMediaRef
from nti.contenttypes.presentation.interfaces import INTIMedia
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup

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
from nti.ntiids.ntiids import find_object_with_ntiid

from nti.site.site import get_component_hierarchy_names

from nti.site.utils import registerUtility

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

def _db_connection(registry=None):
	registry = get_registry(registry)
	if registry == component.getGlobalSiteManager():
		result = None
	else:
		result = IConnection(registry, None)
	return result

def _intid_register(item, registry=None, intids=None, connection=None):
	registry = get_registry(registry)
	intids = component.getUtility(IIntIds) if intids is None else intids
	connection = _db_connection(registry) if connection is None else connection
	if connection is not None:
		connection.add(item)
		lifecycleevent.added(item)
		return True
	return False

class OutlineLessonOverviewMixin(object):

	def _get_lesson(self):
		context = self.request.context
		try:
			ntiid = context.LessonOverviewNTIID
			if not ntiid:
				raise hexc.HTTPServerError(
						_("Outline does not have a valid lesson overview."))

			lesson = component.getUtility(INTILessonOverview, name=ntiid)
			if lesson is None:
				raise hexc.HTTPUnprocessableEntity(_("Cannot find lesson overview."))
			return lesson
		except AttributeError:
			raise hexc.HTTPServerError(
						_("Outline does not have a lesson overview attribute."))

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
		if not IPublishable.providedBy(lesson) or lesson.is_published():
			external = to_external_object(lesson, name="render")
			external.lastModified = external[LAST_MODIFIED] = lesson.lastModified
		else:
			external = LocatedExternalDict()
			external.lastModified = external[LAST_MODIFIED] = 0
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

	def __init__(self, request, the_user=None, the_ntiid=None):
		super(OutlineLessonOverviewSummaryView, self).__init__(request, self.remoteUser)

	def _do_count(self, item):
		# With older content, we're not sure where the UGD
		# may hang; so summarize per item.
		count = 0
		for ntiid_field in ('ntiid', 'target_ntiid'):
			self.ntiid = getattr(item, ntiid_field, None)
			if self.ntiid:
				try:
					results = super(OutlineLessonOverviewSummaryView, self).__call__()
					container_ntiids = results.get(ITEMS, ())
					count += len(container_ntiids)
				except hexc.HTTPNotFound:
					pass  # Empty
		return count

	def __call__(self):
		lesson = self._get_lesson()
		result = LocatedExternalDict()
		result[CLASS] = 'OverviewGroupSummary'
		result[MIMETYPE] = MIME_BASE + ".courses.overviewgroupsummary"
		if not IPublishable.providedBy(lesson) or lesson.is_published():
			self.user = self.remoteUser
			mime_type = MIME_BASE + ".courses.overviewitemsummary"
			for lesson_group in lesson.items:
				for item in lesson_group.items:
					ugd_count = self._do_count(item)
					result[item.ntiid] = item_results = {}
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
		namespaces = {node.src for node in nodes}
		ntiids = {node.ContentNTIID for node in nodes}
		result['ContainerOrder'] = [node.ContentNTIID for node in nodes]

		sites = get_component_hierarchy_names()
		for group in catalog.search_objects(
								namespace=namespaces,
								provided=INTICourseOverviewGroup,
								sites=sites):

			for item in group.Items:
				# ignore non media items
				if 	(not IMediaRef.providedBy(item)
					 and not INTIMedia.providedBy(item)
					 and not INTISlideDeck.providedBy(item)):
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

		for item in catalog.search_objects(
								container_ntiids=ntiids,
								provided=INTISlideDeck,
								container_all_of=False,
								sites=sites):
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

		self.request.no_acl_decoration = True  # at all times

		if ILegacyCourseInstance.providedBy(course):
			result = self._do_legacy(course, record)
		else:
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

	def _get_catalog_entry(self, outline):
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
			entry = self._get_catalog_entry(parent)
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

	def iface_of_obj(self, obj):
		for iface in (ICourseOutlineContentNode,
					  ICourseOutlineCalendarNode,
					  ICourseOutlineNode,
					  ICourseOutline,
			   	   	  INTILessonOverview):  # order matters
			if iface.providedBy(obj):
				return iface
		return None

	def _set_node_ntiid(self, new_node):
		ntiid = self._create_node_ntiid()
		new_node.ntiid = ntiid

	def _register_obj(self, obj):
		registry = component.getSiteManager()
		registerUtility(registry,
						component=obj,
						name=obj.ntiid,
						provided=self.iface_of_obj(obj))

	def _make_lesson_node(self, node):
		lesson_ntiid = make_ntiid(nttype=NTI_LESSON_OVERVIEW, base=node.ntiid)
		new_lesson = NTILessonOverView()
		new_lesson.ntiid = lesson_ntiid
		new_lesson.__parent__ = node
		new_lesson.title = node.title
		new_lesson.creator = node.creator
		# XXX If there is no lesson set it to the overview
		if not node.ContentNTIID:
			node.ContentNTIID = lesson_ntiid
		# XXX: set src and lesson ntiid (see MediaByOutlineView)
		# at his point is very likely that LessonOverviewNTIID,
		# ContentNTIID and src are simply alias fields. All of them
		# are kept so long as we have manual sync and BWC
		node.LessonOverviewNTIID = node.src = lesson_ntiid
		return new_lesson

	def _get_new_node(self):
		# TODO: We could support auto-publishing based on type here.
		creator = self.remoteUser
		new_node = self.readCreateUpdateContentObject(creator)
		self._set_node_ntiid(new_node)
		if ICourseOutlineContentNode.providedBy(new_node):
			new_lesson = self._make_lesson_node(new_node)
			new_lesson.locked = True
			lifecycleevent.created(new_lesson)
			_intid_register(new_lesson)
			self._register_obj(new_lesson)
		self._register_obj(new_node)
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
		index = index if index is None else max(index, 0)
		new_node = self._get_new_node()
		old_keys = list(self.context.keys())
		children_size = len(old_keys)
		self.context.append(new_node)

		self.request.response.status_int = 201

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
class OutlineNodePutView(OutlineNodeInsertView):
	"""
	Put the given ntiid to the given context. We allow moves (copies)
	between nodes, if the object exists. We expect the client to then
	DELETE from the old node if moving.
	"""

	def __call__(self):
		index = self._get_index()
		if index is None:
			raise hexc.HTTPBadRequest('No index supplied')
		values = CaseInsensitiveDict(self.readInput())
		old_keys = list(self.context.keys())
		ntiid = values.get('ntiid')
		old_parent_ntiid = values.get('RemovedFromParent')

		if 		index >= len(old_keys) \
			or 	index < 0:
			raise hexc.HTTPConflict('Invalid index or ntiid (%s) (%s)' % (ntiid, index))

		if ntiid in old_keys:
			old_keys.remove(ntiid)
		else:
			# It's a move, append to our context.
			obj = find_object_with_ntiid(ntiid)
			if obj is None:
				raise hexc.HTTPUnprocessableEntity('Object no longer exists (%s)', ntiid)
			self.context.append(obj)

		# Make sure they don't move the object within the same node and
		# attempt to delete from that node.
		if old_parent_ntiid and old_parent_ntiid != self.context.ntiid:
			old_parent = find_object_with_ntiid(old_parent_ntiid)
			if old_parent is None:
				raise hexc.HTTPUnprocessableEntity('Node parent no longer exists (%s)',
													old_parent_ntiid)
			del old_parent[ntiid]

		principal = self.remoteUser.username
		self._reorder_for_ntiid(ntiid, index, old_keys)
		notify(CourseOutlineNodeMovedEvent(self.context, principal, index))
		logger.info('Moved node (%s) to index (%s) (from=%s)', ntiid, index, old_parent_ntiid)
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
		# TODO: Can we tell when to unregister nodes (no longer contained)
		# to avoid orphans?

		# TODO: Do we want to permanently delete nodes, or delete placeholder
		# mark them (to undo and save transaction history)?
		del self.context[ntiid]
		logger.info('Deleted entity in outline %s', ntiid)
		return hexc.HTTPOk()

@view_config(route_name='objects.generic.traversal',
			 context=ICourseOutlineNode,
			 request_method='PUT',
			 permission=nauth.ACT_CONTENT_EDIT,
			 renderer='rest')
class OutlineNodeFieldPutView(UGDPutView):

	def readInput(self, value=None):
		result = UGDPutView.readInput(self, value=value)
		result.pop('ntiid', None)
		result.pop('NTIID', None)
		return result

@view_config(route_name='objects.generic.traversal',
			 context=ICourseOutlineNode,
			 request_method='GET',
			 permission=nauth.ACT_READ,
			 renderer='rest')
class OutlineNodeGetView(AbstractAuthenticatedView):

	def _is_visible(self, item):
		return 		not IPublishable.providedBy(item) \
				or 	item.is_published() \
				or	has_permission(nauth.ACT_CONTENT_EDIT, item, self.request)

	def __call__(self):
		if self._is_visible(self.context):
			return self.context
		raise hexc.HTTPForbidden()
