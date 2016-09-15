#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import time
import simplejson

from zope import component
from zope import lifecycleevent

from zope.authentication.interfaces import IUnauthenticatedPrincipal

from zope.component.hooks import getSite

from zope.intid.interfaces import IIntIds

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contenttypes.presentation import MessageFactory as _

from nti.app.contenttypes.presentation.views import VIEW_NODE_MOVE
from nti.app.contenttypes.presentation.views import VIEW_NODE_CONTENTS
from nti.app.contenttypes.presentation.views import VIEW_OVERVIEW_CONTENT
from nti.app.contenttypes.presentation.views import VIEW_OVERVIEW_SUMMARY

from nti.app.contenttypes.presentation.utils import is_item_visible
from nti.app.contenttypes.presentation.utils import create_lesson_4_node
from nti.app.contenttypes.presentation.utils import get_enrollment_record
from nti.app.contenttypes.presentation.utils import remove_presentation_asset
from nti.app.contenttypes.presentation.utils import get_participation_principal
from nti.app.contenttypes.presentation.utils import get_enrollment_record as get_any_enrollment_record

from nti.app.contenttypes.presentation.views.view_mixins import PublishVisibilityMixin

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware import VIEW_RECURSIVE_AUDIT_LOG
from nti.app.products.courseware import VIEW_RECURSIVE_TX_HISTORY

from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment

from nti.app.products.courseware.views.course_views import CourseOutlineContentsView

from nti.app.products.courseware.views.view_mixins import NTIIDPathMixin
from nti.app.products.courseware.views.view_mixins import IndexedRequestMixin
from nti.app.products.courseware.views.view_mixins import AbstractChildMoveView
from nti.app.products.courseware.views.view_mixins import AbstractRecursiveTransactionHistoryView

from nti.appserver.ugd_edit_views import UGDPutView
from nti.appserver.ugd_query_views import RecursiveUGDView

from nti.appserver.pyramid_authorization import has_permission

from nti.assessment.interfaces import IQSurvey
from nti.assessment.interfaces import IQAssignment

from nti.common.maps import CaseInsensitiveDict

from nti.common.string import is_true

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import NTI_COURSE_OUTLINE_NODE

from nti.contenttypes.courses.interfaces import iface_of_node
from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseOutlineContentNode
from nti.contenttypes.courses.interfaces import CourseOutlineNodeMovedEvent
from nti.contenttypes.courses.interfaces import IAnonymouslyAccessibleCourseInstance
from nti.contenttypes.courses.interfaces import get_course_assessment_predicate_for_user

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance

from nti.contenttypes.courses.interfaces import ES_ALL

from nti.contenttypes.presentation import AUDIO_MIMETYES
from nti.contenttypes.presentation import VIDEO_MIMETYES
from nti.contenttypes.presentation import TIMELINE_MIMETYES
from nti.contenttypes.presentation import VIDEO_REF_MIMETYES
from nti.contenttypes.presentation import AUDIO_REF_MIMETYES
from nti.contenttypes.presentation import AUDIO_ROLL_MIMETYES
from nti.contenttypes.presentation import SLIDE_DECK_MIMETYES
from nti.contenttypes.presentation import VIDEO_ROLL_MIMETYES
from nti.contenttypes.presentation import TIMELINE_REF_MIMETYES
from nti.contenttypes.presentation import SLIDE_DECK_REF_MIMETYES
from nti.contenttypes.presentation import DISCUSSION_REF_MIMETYES
from nti.contenttypes.presentation import ASSIGNMENT_REF_MIMETYES
from nti.contenttypes.presentation import QUESTIONSET_REF_MIMETYES
from nti.contenttypes.presentation import RELATED_WORK_REF_MIMETYES

from nti.contenttypes.presentation import NTI_LESSON_OVERVIEW

from nti.contenttypes.presentation.interfaces import IPointer
from nti.contenttypes.presentation.interfaces import IVisible
from nti.contenttypes.presentation.interfaces import IMediaRef
from nti.contenttypes.presentation.interfaces import INTIMedia
from nti.contenttypes.presentation.interfaces import INTIMediaRoll
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTISurveyRef
from nti.contenttypes.presentation.interfaces import IConcreteAsset
from nti.contenttypes.presentation.interfaces import INTIDocketAsset
from nti.contenttypes.presentation.interfaces import INTISlideDeckRef
from nti.contenttypes.presentation.interfaces import INTIAssessmentRef
from nti.contenttypes.presentation.interfaces import INTIAssignmentRef
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
from nti.ntiids.ntiids import find_object_with_ntiid

from nti.property.property import Lazy

from nti.site.interfaces import IHostPolicyFolder

from nti.site.site import get_component_hierarchy_names

from nti.site.utils import registerUtility
from nti.site.utils import unregisterUtility

from nti.traversal.traversal import find_interface

from nti.zodb.containers import time_to_64bit_int

CLASS = StandardExternalFields.CLASS
ITEMS = StandardExternalFields.ITEMS
TOTAL = StandardExternalFields.TOTAL
MIMETYPE = StandardExternalFields.MIMETYPE
ITEM_COUNT = StandardExternalFields.ITEM_COUNT
LAST_MODIFIED = StandardExternalFields.LAST_MODIFIED

class OutlineLessonOverviewMixin(object):

	def _get_lesson(self):
		context = self.request.context
		lesson = INTILessonOverview(context, None)
		if lesson is None:
			raise hexc.HTTPUnprocessableEntity(_("Cannot find lesson overview."))
		return lesson

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
			external = to_external_object(lesson)
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
class OutlineLessonOverviewSummaryView(RecursiveUGDView, OutlineLessonOverviewMixin):

	_DEFAULT_BATCH_START = 0
	_DEFAULT_BATCH_SIZE = None

	def _set_user_and_ntiid(self, request, the_user, the_ntiid):
		if request.context is not None:
			self.user = the_user or self.remoteUser
			self.ntiid = the_ntiid or request.context.ntiid

	def _key_ntiid(self, item):
		if IPointer.providedBy(item):
			return item.target
		return item.ntiid

	def _count_ntiids(self, item):
		result = (item.ntiid,)
		if IPointer.providedBy(item):
			ref = IConcreteAsset(item, item)
			if INTIDocketAsset.providedBy(ref):
				result = (ref.target, ref.ntiid)
			else:
				result = (item.target,)
		return result

	def _do_count(self, item):
		# With older content, we're not sure where the UGD
		# may hang; so summarize per item.
		count = 0
		for ntiid in self._count_ntiids(item):
			self.ntiid = ntiid
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
			for lesson_group in lesson or ():
				for item in lesson_group or ():
					ugd_count = self._do_count(item)
					ntiid = self._key_ntiid(item)
					result[ntiid] = item_results = {}
					item_results[CLASS] = 'OverviewItemSummary'
					item_results[MIMETYPE] = mime_type
					item_results[ITEM_COUNT] = ugd_count
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

	@Lazy
	def _site_name(self):
		folder = find_interface(self.context, IHostPolicyFolder, strict=False)
		result = folder.__name__ if folder is not None else getSite().__name__
		return result

	@Lazy
	def _registry(self):
		folder = find_interface(self.context, IHostPolicyFolder, strict=False)
		result = folder.getSiteManager() if folder is not None else None
		return result if result is not None else component.getSiteManager()

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
									  self.remoteUser.username,
									  current_time)
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
		registry = self._registry
		registerUtility(registry,
						component=obj,
						name=obj.ntiid,
						provided=self.iface_of_obj(obj))

	def _make_lesson_node(self, node):
		registry = self._registry
		ntiid = make_ntiid(nttype=NTI_LESSON_OVERVIEW, base=node.ntiid)
		result = create_lesson_4_node(node, ntiid=ntiid, registry=registry,
									  sites=self._site_name)
		return result

	def _get_new_node(self):
		# TODO: We could support auto-publishing based on type here.
		creator = self.remoteUser
		new_node = self.readCreateUpdateContentObject(creator)
		self._set_node_ntiid(new_node)
		self._register_obj(new_node)
		new_node.locked = True
		return new_node

	def __call__(self):
		index = self._get_index()
		new_node = self._get_new_node()
		self.context.insert(index, new_node)
		self.context.child_order_locked = True

		# After insert, create our lesson. This makes sure lineage
		# is hooked up correctly when we do so.
		if ICourseOutlineContentNode.providedBy(new_node):
			new_lesson = self._make_lesson_node(new_node)
			new_lesson.locked = True

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
		super(OutlineNodeMoveView, self).__call__()
		result = to_external_object(self.context)
		if ITEMS not in result:
			result[ITEMS] = self.externalize_node_contents(self.context)
		return result

class OutlineNodeDeleteMixin(AbstractAuthenticatedView, NTIIDPathMixin):

	@Lazy
	def _registry(self):
		folder = find_interface(self.context, IHostPolicyFolder, strict=False)
		result = folder.getSiteManager() if folder is not None else None
		return result if result is not None else component.getSiteManager()

	def _remove_lesson(self, ntiid):
		lesson = component.queryUtility(INTILessonOverview, name=ntiid)
		if lesson is not None:
			remove_presentation_asset(lesson, registry=self._registry)

	def _delete_lesson(self, context):
		if context.LessonOverviewNTIID:
			self._remove_lesson(context.LessonOverviewNTIID)
			return True
		return False

	def _delete_node(self, parent, ntiid):
		try:
			node = parent[ntiid]
			unregisterUtility(name=ntiid,
							  registry=self._registry,
							  provided=iface_of_node(node))
			del parent[ntiid]
		except KeyError:
			# Already deleted.
			return False
		else:
			logger.info('Deleted entity in outline %s', ntiid)
			parent.child_order_locked = True
			return True

@view_config(route_name='objects.generic.traversal',
			 context=ICourseOutlineNode,
			 request_method='DELETE',
			 permission=nauth.ACT_CONTENT_EDIT,
			 renderer='rest',
			 name=VIEW_NODE_CONTENTS)
class OutlineNodeDeleteContentsView(OutlineNodeDeleteMixin):
	"""
	Delete the given ntiid in our context. We may be given an `index`
	param, which we will ignore.
	"""

	def __call__(self):
		ntiid = self._get_ntiid()
		# 12.2015 - We currently do not delete the underlying lesson
		# and assets tied to this node. Potentially, we could allow
		# the user to recover/undo these deleted lesson nodes, or
		# through administrative action.
		# if self.context.LessonOverviewNTIID:
		# 	self._remove_lesson(self.context.LessonOverviewNTIID)
		# TODO: Do we want to permanently delete nodes, or delete placeholder
		# mark them (to undo and save transaction history)?
		self._delete_node(self.context, ntiid)
		return hexc.HTTPOk()

@view_config(route_name='objects.generic.traversal',
			 context=ICourseOutlineNode,
			 request_method='DELETE',
			 permission=nauth.ACT_CONTENT_EDIT,
			 renderer='rest')
class OutlineNodeDeleteView(OutlineNodeDeleteMixin):

	def __call__(self):
		self._delete_lesson(self.context)
		self._delete_node(self.context.__parent__, self.context.ntiid)
		return hexc.HTTPNoContent()

@view_config(route_name='objects.generic.traversal',
			 context=ICourseOutlineNode,
			 request_method='PUT',
			 permission=nauth.ACT_CONTENT_EDIT,
			 renderer='rest')
class OutlineNodeFieldPutView(UGDPutView, OutlineLessonOverviewMixin):

	def readInput(self, value=None):
		result = UGDPutView.readInput(self, value=value)
		result.pop('ntiid', None)
		result.pop('NTIID', None)
		return result

	def _update_lesson(self):
		"""
		For content nodes, sync our title with our lesson
		"""
		input_dict = self.readInput()
		new_title = input_dict.get('title')
		if new_title:
			lesson = self._get_lesson()
			if lesson is not None:
				lesson.title = new_title

	def __call__(self):
		result = UGDPutView.__call__(self)
		if ICourseOutlineContentNode.providedBy(self.context):
			self._update_lesson()
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

# Misc Views

def _get_group_accept_types(accept_types):
	"""
	Map the given mimetypes to types found in overview groups.
	"""
	if not accept_types:
		return None
	result = set()
	for accept_type in accept_types:
		if accept_type in AUDIO_MIMETYES:
			result.update(AUDIO_MIMETYES)
			result.update(AUDIO_REF_MIMETYES)
			result.update(AUDIO_ROLL_MIMETYES)
		elif accept_type in VIDEO_MIMETYES:
			result.update(VIDEO_MIMETYES)
			result.update(VIDEO_REF_MIMETYES)
			result.update(VIDEO_ROLL_MIMETYES)
		elif accept_type in RELATED_WORK_REF_MIMETYES:
			result.update(RELATED_WORK_REF_MIMETYES)
		elif accept_type in VIDEO_ROLL_MIMETYES:
			result.update(VIDEO_ROLL_MIMETYES)
		elif accept_type in AUDIO_ROLL_MIMETYES:
			result.update(AUDIO_ROLL_MIMETYES)
		elif accept_type in TIMELINE_MIMETYES:
			result.update(TIMELINE_MIMETYES)
			result.update(TIMELINE_REF_MIMETYES)
		elif accept_type in SLIDE_DECK_MIMETYES:
			result.update(SLIDE_DECK_MIMETYES)
			result.update(SLIDE_DECK_REF_MIMETYES)
		elif accept_type in DISCUSSION_REF_MIMETYES:
			result.update(DISCUSSION_REF_MIMETYES)
		elif accept_type in QUESTIONSET_REF_MIMETYES:
			result.update(QUESTIONSET_REF_MIMETYES)
		elif accept_type in ASSIGNMENT_REF_MIMETYES:
			result.update(ASSIGNMENT_REF_MIMETYES)
	return result

class _MimeFilter(object):

	def __init__(self, accept_types):
		self.accept_types = _get_group_accept_types(accept_types)

	def include(self, obj):
		result = True
		if self.accept_types:
			mime_type = 	getattr(obj, 'mime_type', None) \
						or	getattr(obj, 'MimeType', None) \
						or	getattr(obj, 'mimeType', None)
			result = mime_type in self.accept_types
		return result

@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_config(context=ICourseInstanceEnrollment)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   permission=nauth.ACT_READ,
			   request_method='GET',
			   name='AssetByOutlineNode')
class AssetByOutlineNodeView(AbstractAuthenticatedView):
	"""
	Return a mapping of asset ntiids, filtered by comma separated
	`mimetypes`, to their containers. We also
	return the ContainerOrder (via ContentNTIIDs found depth-first
	in the tree) and the items found in the outline.

	Currently we do not handle discussions.

	# FIXME: Needs to handle legacy slide deck behavior.
	# Pull slidedecks for course, iterate through, grabbing videos
	# that are slide videos.
	"""

	@Lazy
	def course(self):
		return ICourseInstance(self.request.context)

	@Lazy
	def _is_editor(self):
		return has_permission(ACT_CONTENT_EDIT, self.course)

	@Lazy
	def record(self):
		return get_any_enrollment_record(self.course, self.remoteUser)

	def _allow_assessmentref(self, iface, item):
		if self._is_editor:
			return True
		assg = iface(item, None)
		if assg is None:
			return False
		# Instructor
		if self.record.Scope == ES_ALL:
			return True
		course = self.record.CourseInstance
		predicate = get_course_assessment_predicate_for_user(self.remoteUser, course)
		result = predicate is not None and predicate(assg)
		return result

	def _allow_assignmentref(self, item):
		result = self._allow_assessmentref(IQAssignment, item)
		return result

	def _allow_surveyref(self, item):
		result = self._allow_assessmentref(IQSurvey, item)
		return result

	def _include_assessment(self, item):
		result = True
		if	INTIAssignmentRef.providedBy(item):
			result = self._allow_assignmentref(item)
		elif INTISurveyRef.providedBy(item):
			result = self._allow_surveyref(item)
		return result

	def _get_all_items(self, item):
		"""
		Expand our overview group item into all items needed.
		"""
		if INTIMediaRoll.providedBy(item):
			result = tuple(item.items)
		elif INTISlideDeck.providedBy(item):
			result = list(item.items)
			result.append(item)
		else:
			result = (item,)
		return result

	def _get_return_item(self, item):
		"""
		Convert refs to objects the clients expect.
		"""
		if INTIAssessmentRef.providedBy(item):
			result = find_object_with_ntiid(item.target)
		elif IMediaRef.providedBy(item):
			result = INTIMedia(item)
		else:
			result = IConcreteAsset(item, item)
		return result

	def _is_published(self, obj):
		return not IPublishable.providedBy(obj) or obj.is_published()

	def _is_visible(self, item, course, record):
		return 		not IVisible.providedBy(item) \
				or  is_item_visible(item, self.remoteUser,
									context=course, record=record)

	def _include(self, item, course, record):
		return		self.mime_filter.include(item) \
				and self._is_visible(item, course, record) \
				and self._include_assessment(item)

	def _do_call(self, course, record):
		result = LocatedExternalDict()
		result.__name__ = self.request.view_name
		result.__parent__ = self.request.context

		result[ITEMS] = items = {}
		result['Containers'] = containers = {}
		result['ContainerOrder'] = container_order = []

		def add_item(item, container_id):
			# Only add if it passes filter and is visible.
			if not self._is_visible(item, course, record):
				return
			item = self._get_return_item(item)
			items[item.ntiid] = item
			containers.setdefault(container_id, [])
			containers[container_id].append(item.ntiid)

		def _recur(node):
			if ICourseOutlineContentNode.providedBy(node):
				if node.src and node.ContentNTIID:
					container_order.append(node.ContentNTIID)
				lesson = INTILessonOverview(node, None)
				# Only want to return items if the lesson is
				# published or we're an editor.
				if lesson is not None and (self._is_editor or self._is_published(lesson)):
					container_id = node.ContentNTIID or node.LessonOverviewNTIID
					for group in lesson or ():
						for item in group or ():
							if self._include(item, course, record):
								# Expand and add
								all_items = self._get_all_items(item)
								for item in all_items:
									add_item(item, container_id)

			for child in node.values():
				_recur(child)

		outline = course.Outline
		if outline is not None:
			_recur(outline)

		last_mod = None
		if items:
			try:
				last_mod = max(x.lastModified for x in items.values() if getattr(x, 'lastModified', 0))
			except ValueError:
				# QQuestionSet with no 'lastModified'
				pass
		result.lastModified = result[LAST_MODIFIED] = last_mod
		result[TOTAL] = result[ITEM_COUNT] = len(items)
		return result

	@Lazy
	def _mime_filter_params(self):
		result =	self.params.get('mimetypes') \
				or	self.params.get('mime_types') \
				or	self.params.get('types')
		if result:
			result = result.split(',')
		return result

	@Lazy
	def mime_filter(self):
		return _MimeFilter(self._mime_filter_params)

	@Lazy
	def params(self):
		return CaseInsensitiveDict(self.request.params)

	def _allow_anonymous_access(self, course):
		# Or do we short-circuit this by allowing anyone with READ
		# access on course. We could also bake this into a mixin.
		prin = get_participation_principal()
		return  prin is not None \
			and IUnauthenticatedPrincipal.providedBy(prin) \
			and IAnonymouslyAccessibleCourseInstance.providedBy(course) \

	def _predicate(self, course, record):
		return 		record is not None \
				or	has_permission(ACT_CONTENT_EDIT, course, self.request) \
				or  self._allow_anonymous_access(course)

	def __call__(self):
		course = self.course
		record = get_enrollment_record(course, self.remoteUser) if self.remoteUser else None
		if not self._predicate(course, record):
			raise hexc.HTTPForbidden(_("Must be enrolled in a course."))

		self.request.acl_decoration = False  # avoid acl decoration
		result = self._do_call(course, record)
		return result

@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_config(context=ICourseInstanceEnrollment)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   permission=nauth.ACT_READ,
			   request_method='GET',
			   name='MediaByOutlineNode')  # See decorators
class MediaByOutlineNodeView(AssetByOutlineNodeView):
	"""
	Legacy view to fetch media by outline node.
	"""

	@Lazy
	def course(self):
		return ICourseInstance(self.request.context)

	@Lazy
	def _is_editor(self):
		return has_permission(ACT_CONTENT_EDIT, self.course)

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

	def _do_legacy(self, course):
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

	def _get_node_ntiids(self, nodes):
		"""
		Gather the set of ntiids to look up in our container index. Some API
		created items are indexed by lesson overview (versus content) so
		return those as well. Make sure we capture the map of lessons to
		content so we can return items by ContentNTIID for clients.
		"""
		ntiids = set()
		namespaces = set()
		lesson_to_content_map = {}
		for node in nodes:
			namespaces.add(node.src)
			ntiids.add(node.ContentNTIID)
			# Authored items are namespaced underneath the lesson.
			lesson = find_object_with_ntiid(node.LessonOverviewNTIID)
			namespaces.add(to_external_ntiid_oid(lesson))
			if node.ContentNTIID != node.LessonOverviewNTIID:
				ntiids.add(node.LessonOverviewNTIID)
				lesson_to_content_map[node.LessonOverviewNTIID] = node.ContentNTIID
		ntiids.discard(None)
		namespaces.discard(None)
		return namespaces, ntiids, lesson_to_content_map

	def _do_current(self, course, record):
		result = LocatedExternalDict()
		result.__name__ = self.request.view_name
		result.__parent__ = self.request.context

		lastModified = 0
		catalog = get_library_catalog()
		intids = component.getUtility(IIntIds)

		items = result[ITEMS] = {}
		containers = result['Containers'] = {}
		containers_seen = {}

		nodes = self._outline_nodes(course)
		namespaces, ntiids, lesson_to_content_map = self._get_node_ntiids(nodes)

		result['ContainerOrder'] = [node.ContentNTIID for node in nodes]

		def _add_item_to_container(container_ntiid, item):
			# We only want to map to our ContentNTIID here, for clients.
			if container_ntiid in lesson_to_content_map:
				container_ntiid = lesson_to_content_map.get(container_ntiid)
			containers_seen.setdefault(container_ntiid, set())
			seen = containers_seen[container_ntiid]
			# Avoid dupes but retain order.
			if item.ntiid not in seen:
				seen.add(item.ntiid)
				containers.setdefault(container_ntiid, [])
				containers[container_ntiid].append(item.ntiid)

		def add_item(item):
			# Check visibility
			ref_obj = item
			if IVisible.providedBy(item):
				if not is_item_visible(item, self.remoteUser,
									   context=course, record=record):
					return
				else:
					item = INTIMedia(item, None)

			# We need to check both our media obj and our ref here.
			# API created objects are indexed with ref objects, where
			# sync'd objects are indexed with media objects.
			for media_obj in (item, ref_obj):
				# Check if ref was valid
				uid = intids.queryId(media_obj) if media_obj is not None else None
				if uid is None:
					return

				# Set content containers
				for ntiid in catalog.get_containers(uid):
					if ntiid in ntiids:
						_add_item_to_container(ntiid, item)
			items[item.ntiid] = to_external_object(item)
			return max(item.lastModified, ref_obj.lastModified)

		sites = get_component_hierarchy_names()
		for group in catalog.search_objects(namespace=namespaces,
											provided=INTICourseOverviewGroup,
											sites=sites):
			for item in group or ():
				# ignore non media items
				if 	(	 not IMediaRef.providedBy(item)
					 and not INTIMedia.providedBy(item)
					 and not INTIMediaRoll.providedBy(item)
					 and not INTISlideDeck.providedBy(item)
					 and not INTISlideDeckRef.providedBy(item)):
					continue

				# check containing node/lesson is published
				unpublished = False
				for provided in (ICourseOutlineNode, INTILessonOverview):
					obj = find_interface(item, provided, strict=False)
					if obj is None or not obj.isPublished():
						unpublished = True
						break
				# No need to keep checking the group if unpublished and not editor.
				if not self._is_editor and unpublished:
					break

				# check for valid slide decks
				if INTISlideDeckRef.providedBy(item):
					item = INTISlideDeck(item, None)
					if item is None:
						continue

				if INTIMediaRoll.providedBy(item):
					item_last_mod = 0
					# For media rolls, we want to expand to preserve bwc.
					for roll_item in item.items:
						roll_last_mod = add_item(roll_item)
						if roll_last_mod:
							item_last_mod = max(roll_last_mod, item_last_mod)
				else:
					item_last_mod = add_item(item)

				if item_last_mod:
					lastModified = max(lastModified, item_last_mod)

		for item in catalog.search_objects(container_ntiids=ntiids,
										   provided=INTISlideDeck,
										   container_all_of=False,
										   sites=sites):
			uid = intids.getId(item)
			for ntiid in catalog.get_containers(uid):
				if ntiid in ntiids:
					_add_item_to_container(ntiid, item)
			items[item.ntiid] = to_external_object(item)
			lastModified = max(lastModified, item.lastModified)

		result.lastModified = result[LAST_MODIFIED] = lastModified
		result[TOTAL] = result[ITEM_COUNT] = len(items)
		return result

	def __call__(self):
		course = ICourseInstance(self.request.context)
		record = get_enrollment_record(course, self.remoteUser) if self.remoteUser else None
		if not self._predicate(course, record):
			raise hexc.HTTPForbidden(_("Must be enrolled in a course."))

		self.request.acl_decoration = False  # avoid acl decoration

		if ILegacyCourseInstance.providedBy(course):
			result = self._do_legacy(course)
		else:
			result = self._do_current(course, record)
		return result

@view_config(name=VIEW_RECURSIVE_AUDIT_LOG)
@view_config(name=VIEW_RECURSIVE_TX_HISTORY)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='GET',
			   permission=nauth.ACT_CONTENT_EDIT,
			   context=ICourseOutlineNode)
class RecursiveCourseTransactionHistoryView(AbstractRecursiveTransactionHistoryView):
	"""
	A batched view to get all edits that have occurred in this outline node, recursively.
	"""

	def _get_items(self):
		return self._get_node_items(self.context)

# Sync Lock/Unlock outline and lessons

@view_config(route_name='objects.generic.traversal',
			 context=ICourseOutline,
			 request_method='POST',
			 permission=nauth.ACT_CONTENT_EDIT,
			 renderer='rest',
			 name='SyncLock')
class SyncLockOutlineView(AbstractAuthenticatedView,
						  ModeledContentUploadRequestUtilsMixin):
	"""
	Locks all nodes and lesson overviews pointed by the outline.
	"""

	def readInput(self, value=None):
		result = ModeledContentUploadRequestUtilsMixin.readInput(self, value=value)
		return CaseInsensitiveDict(result)

	def _get_nodes(self, outline):
		result = []
		def _recur(node):
			if not ICourseOutline.providedBy(node):
				result.append(node)
			for child in node.values():
				_recur(child)
		_recur(outline)
		return result

	def _do_op(self, node, do_lessons=True):
		node.lock()
		lifecycleevent.modified(node)
		if do_lessons:
			lesson = INTILessonOverview(node, None)
			if lesson is not None:
				lesson.lock()
				lifecycleevent.modified(lesson)

	def _do_call(self, outline, do_lessons=True):
		for node in self._get_nodes(outline):
			self._do_op(node, do_lessons)

	def __call__(self):
		values = self.readInput()
		do_lessons = is_true(values.get('lesson') or values.get('lessons'))
		self._do_call(self.context, do_lessons)
		return hexc.HTTPNoContent()

@view_config(route_name='objects.generic.traversal',
			 context=ICourseOutline,
			 request_method='POST',
			 permission=nauth.ACT_CONTENT_EDIT,
			 renderer='rest',
			 name='SyncUnlock')
class SyncUnlockOutlineView(SyncLockOutlineView):
	"""
	Unlocks all nodes and lesson overviews pointed by the outline.
	"""

	def _do_op(self, node, do_lessons=True):
		node.lock()
		lifecycleevent.modified(node)
		if do_lessons:
			lesson = INTILessonOverview(node, None)
			if lesson is not None:
				lesson.unlock()
				lesson.childOrderUnlock()
				lifecycleevent.modified(lesson)
