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

from zope.intid import IIntIds

from pyramid.view import view_config
from pyramid.view import view_defaults
from pyramid import httpexceptions as hexc

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment

from nti.app.products.courseware.views.course_views import CourseOutlineContentsView

from nti.appserver.ugd_edit_views import UGDPutView
from nti.appserver.ugd_query_views import RecursiveUGDView

from nti.appserver.pyramid_authorization import has_permission

from nti.common.time import time_to_64bit_int
from nti.common.maps import CaseInsensitiveDict

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import iface_of_node
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
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup

from nti.coremetadata.interfaces import IPublishable

from nti.dataserver import authorization as nauth
from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.externalization.oids import to_external_ntiid_oid
from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.externalization import to_external_object

from nti.mimetype.mimetype import MIME_BASE

from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import get_provider
from nti.ntiids.ntiids import get_specific
from nti.ntiids.ntiids import make_specific_safe

from nti.site.site import get_component_hierarchy_names

from nti.site.utils import registerUtility

from nti.traversal.traversal import find_interface

from ..utils import is_item_visible
from ..utils import component_registry
from ..utils import create_lesson_4_node
from ..utils import get_enrollment_record
from ..utils import remove_presentation_asset

from .view_mixins import IndexedRequestMixin
from .view_mixins import AbstractChildMoveView
from .view_mixins import PublishVisibilityMixin

from . import VIEW_NODE_MOVE
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
				raise hexc.HTTPServerError(
						_("Outline does not have a valid lesson overview."))

			lesson = component.getUtility(INTILessonOverview, name=ntiid)
			if lesson is None:
				raise hexc.HTTPUnprocessableEntity(_("Cannot find lesson overview."))
			return lesson
		except AttributeError:
			raise hexc.HTTPServerError(
						_("Outline does not have a lesson overview attribute."))

	def _can_edit_lesson(self, lesson=None):
		lesson = self._get_lesson() if lesson is None else lesson
		result = has_permission(ACT_CONTENT_EDIT, lesson, self.request)
		return result

@view_config(route_name='objects.generic.traversal',
			 context=ICourseOutlineContentNode,
			 request_method='GET',
			 permission=nauth.ACT_READ,
			 renderer='rest',
			 name=VIEW_OVERVIEW_CONTENT)
class OutlineLessonOverviewView(AbstractAuthenticatedView,
								OutlineLessonOverviewMixin,
								PublishVisibilityMixin):

	def __call__(self):
		lesson = self._get_lesson()
		if self._is_visible(lesson):
			self.request.acl_decoration = self._can_edit_lesson(lesson)
			external = to_external_object( lesson )
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

	_DEFAULT_BATCH_START = 0
	_DEFAULT_BATCH_SIZE = None

	def _set_user_and_ntiid(self, request, the_user, the_ntiid):
		if request.context is not None:
			self.user = the_user or self.remoteUser
			self.ntiid = the_ntiid or request.context.ntiid

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

		lastModified = 0
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
				lastModified = max(lastModified, item.lastModified)

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
			lastModified = max(lastModified, item.lastModified)

		# make json ready
		for k, v in list(containers.items()):
			containers[k] = list(v)
		result[LAST_MODIFIED] = lastModified
		result['Total'] = result['ItemCount'] = len(items)
		return result

	def __call__(self):
		course = ICourseInstance(self.request.context)
		record = get_enrollment_record(course, self.remoteUser)
		if record is None:
			raise hexc.HTTPForbidden(_("Must be enrolled in a course."))

		self.request.acl_decoration = False  # avoid acl decoration

		if ILegacyCourseInstance.providedBy(course):
			result = self._do_legacy(course, record)
		else:
			result = self._do_current(course, record)
		return result

@view_config(route_name='objects.generic.traversal',
			 context=ICourseOutlineNode,
			 request_method='POST',
			 permission=nauth.ACT_CONTENT_EDIT,
			 renderer='rest',
			 name=VIEW_NODE_CONTENTS)
class OutlineNodeInsertView(AbstractAuthenticatedView,
							ModeledContentUploadRequestUtilsMixin,
							IndexedRequestMixin):
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
		return iface_of_node(obj)

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
		registry = component.getSiteManager()
		ntiid = make_ntiid(nttype=NTI_LESSON_OVERVIEW, base=node.ntiid)
		result = create_lesson_4_node(node, ntiid=ntiid, registry=registry)
		return result

	def _get_new_node(self):
		# TODO: We could support auto-publishing based on type here.
		creator = self.remoteUser
		new_node = self.readCreateUpdateContentObject(creator)
		self._set_node_ntiid(new_node)
		if ICourseOutlineContentNode.providedBy(new_node):
			new_lesson = self._make_lesson_node(new_node)
			new_lesson.locked = True  # locked
		self._register_obj(new_node)
		new_node.locked = True
		return new_node

	def __call__(self):
		index = self._get_index()
		new_node = self._get_new_node()
		self.context.insert( index, new_node )

		logger.info('Created new outline node (%s)', new_node.ntiid)
		self.request.response.status_int = 201
		return new_node

@view_config(route_name='objects.generic.traversal',
			 context=ICourseOutline,
			 request_method='POST',
			 permission=nauth.ACT_CONTENT_EDIT,
			 renderer='rest',
			 name=VIEW_NODE_MOVE)
class OutlineNodeMoveView(AbstractChildMoveView,
						CourseOutlineContentsView,
						ModeledContentUploadRequestUtilsMixin):
	"""
	Move the given object between outline nodes in a course
	outline. The source, target NTIIDs must exist in the outline (no
	nodes are allowed to move between courses).
	"""

	notify_type = CourseOutlineNodeMovedEvent

	def _get_context_ntiid(self):
		# Our outline gets an OID NTIID on externalization.
		return to_external_ntiid_oid(self.context)

	def _remove_from_parent(self, parent, obj):
		try:
			del parent[obj.ntiid]
			return True
		except KeyError:
			return False

	def _get_children_ntiids(self, outline_ntiid):
		result = set()
		result.add(outline_ntiid)
		def _recur(node):
			val = getattr(node, 'ntiid', None)
			if val:
				result.add(val)
			for child in node.values():
				_recur(child)

		_recur(self.context)
		return result

	def __call__(self):
		super( OutlineNodeMoveView, self ).__call__()
		result = self._to_external()
		return result

@view_config(route_name='objects.generic.traversal',
			 context=ICourseOutlineNode,
			 request_method='DELETE',
			 permission=nauth.ACT_CONTENT_EDIT,
			 renderer='rest',
			 name=VIEW_NODE_CONTENTS)
class OutlineNodeDeleteView(AbstractAuthenticatedView,
							ModeledContentUploadRequestUtilsMixin):
	"""
	Delete the given ntiid in our context.
	"""

	def _remove_lesson(self, ntiid):
		lesson = component.queryUtility(INTILessonOverview, name=ntiid)
		if lesson is not None:
			registry = component_registry(lesson, provided=INTILessonOverview, name=ntiid)
			remove_presentation_asset(lesson, registry=registry)

	def __call__(self):
		values = CaseInsensitiveDict(self.readInput())
		old_keys = list(self.context.keys())
		ntiid = values.get('ntiid')

		if ntiid not in old_keys:
			raise hexc.HTTPConflict(_('NTIID no longer present'))

		# 12.2015 - We currently do not delete the underlying lesson
		# and assets tied to this node. Potentially, we could allow
		# the user to recover/undo these deleted lesson nodes, or
		# through administrative action.
		# if self.context.LessonOverviewNTIID:
		# 	self._remove_lesson(self.context.LessonOverviewNTIID)

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
class OutlineNodeGetView(AbstractAuthenticatedView, PublishVisibilityMixin):

	def __call__(self):
		if self._is_visible(self.context):
			return self.context
		raise hexc.HTTPForbidden()
