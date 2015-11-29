#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from urlparse import urljoin

from zope import component
from zope import interface

from zope.location.interfaces import ILocation

from pyramid.interfaces import IRequest

from nti.app.contentlibrary.utils import get_item_content_units

from nti.app.products.courseware.interfaces import NTIID_TYPE_COURSE_TOPIC
from nti.app.products.courseware.interfaces import NTIID_TYPE_COURSE_SECTION_TOPIC

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.appserver.pyramid_authorization import has_permission

from nti.assessment.interfaces import IQAssignment

from nti.common.property import Lazy

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IContentUnitHrefMapper

from nti.contenttypes.courses.interfaces import OPEN
from nti.contenttypes.courses.interfaces import ES_ALL
from nti.contenttypes.courses.interfaces import IN_CLASS
from nti.contenttypes.courses.interfaces import ES_CREDIT
from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ENROLLMENT_LINEAGE_MAP

from nti.contenttypes.courses.interfaces import get_course_assessment_predicate_for_user

from nti.contenttypes.presentation.interfaces import IVisible
from nti.contenttypes.presentation.interfaces import IMediaRef
from nti.contenttypes.presentation.interfaces import INTIMedia
from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTIMediaRoll
from nti.contenttypes.presentation.interfaces import INTIQuestionRef
from nti.contenttypes.presentation.interfaces import INTIAssignmentRef
from nti.contenttypes.presentation.interfaces import INTIDiscussionRef
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTIQuestionSetRef
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup

from nti.dataserver.authorization import ACT_UPDATE
from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalObjectDecorator
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.externalization.externalization import to_external_object

from nti.links.links import Link

from nti.ntiids.ntiids import get_type
from nti.ntiids.ntiids import get_specific
from nti.ntiids.ntiids import make_provider_safe

from ..utils import is_item_visible
from ..utils import resolve_discussion_course_bundle
from ..utils import get_enrollment_record as get_any_enrollment_record

from . import LEGACY_UAS_40
from . import ORDERED_CONTENTS

from . import is_legacy_uas

NTIID = StandardExternalFields.NTIID
LINKS = StandardExternalFields.LINKS
ITEMS = StandardExternalFields.ITEMS
CLASS = StandardExternalFields.CLASS
MIMETYPE = StandardExternalFields.MIMETYPE
IN_CLASS_SAFE = make_provider_safe(IN_CLASS)

@component.adapter(IPresentationAsset)
@interface.implementer(IExternalMappingDecorator)
class _PresentationAssetEditLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

	@Lazy
	def _acl_decoration(self):
		result = getattr(self.request, 'acl_decoration', True)
		return result

	def _has_edit_link(self, result):
		_links = result.get(LINKS)
		for link in _links or ():
			if getattr(link, 'rel', None) == 'edit':
				return True
		return False

	def _predicate(self, context, result):
		return 		self._acl_decoration \
				and self._is_authenticated \
				and	not self._has_edit_link(result) \
				and has_permission(ACT_UPDATE, context, self.request)

	def _do_decorate_external(self, context, result):
		_links = result.setdefault(LINKS, [])
		link = Link(context, rel='edit')
		interface.alsoProvides(link, ILocation)
		link.__name__ = ''
		link.__parent__ = context
		_links.append(link)

@component.adapter(INTILessonOverview)
@component.adapter(INTICourseOverviewGroup)
@interface.implementer(IExternalMappingDecorator)
class _NTIAssetOrderedContentsLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

	@Lazy
	def _acl_decoration(self):
		result = getattr(self.request, 'acl_decoration', True)
		return result

	def _predicate(self, context, result):
		return 		self._acl_decoration \
				and self._is_authenticated \
				and has_permission(ACT_CONTENT_EDIT, context, self.request)

	def _do_decorate_external(self, context, result):
		links = result.setdefault(LINKS, [])
		link = Link(context, rel=ORDERED_CONTENTS, elements=('contents',))
		interface.alsoProvides(link, ILocation)
		link.__name__ = ''
		link.__parent__ = context
		links.append(link)

@interface.implementer(IExternalObjectDecorator)
class _VisibleMixinDecorator(AbstractAuthenticatedRequestAwareDecorator):

	_record = None

	def record(self, context):
		if self._record is None:
			self._record = get_any_enrollment_record(context, self.remoteUser)
		return self._record

	def _handle_media_ref(self, items, item, idx):
		source = INTIMedia(item, None)
		if source is not None:
			items[idx] = to_external_object(source, name="render")
			return True
		return False

	def _allow_visible(self, context, item):
		record = self.record(context)
		result = is_item_visible(item, user=self.remoteUser,
								 context=context, record=record)
		return result

	def _decorate_external_impl(self, context, result):
		pass

	def _do_decorate_external(self, context, result):
		try:
			__traceback_info__ = context
			self._decorate_external_impl(context, result)
		except Exception:
			logger.exception("Error while decorating asset")

@component.adapter(INTIMediaRoll)
class _NTIMediaRollDecorator(_VisibleMixinDecorator):

	def _decorate_external_impl(self, context, result):
		removal = set()
		items = result[ITEMS]
		# loop through sources
		for idx, item in enumerate(context):
			if IVisible.providedBy(item) and not self._allow_visible(context, item):
				removal.add(idx)
			elif IMediaRef.providedBy(item):
				self._handle_media_ref(items, item, idx)
		# remove disallowed items
		if removal:
			result[ITEMS] = [x for idx, x in enumerate(items) if idx not in removal]

@component.adapter(INTICourseOverviewGroup)
class _NTICourseOverviewGroupDecorator(_VisibleMixinDecorator):

	def _is_legacy_discussion(self, item):
		nttype = get_type(item.target)
		return nttype in (NTIID_TYPE_COURSE_TOPIC, NTIID_TYPE_COURSE_SECTION_TOPIC)

	def _filter_legacy_discussions(self, context, indexes, removal):
		items = context.Items
		record = self.record(context)
		scope = record.Scope if record is not None else None
		scope = ES_CREDIT if scope == ES_ALL else scope  # map to credit
		m_scope = ENROLLMENT_LINEAGE_MAP.get(scope or u'')
		if not m_scope:
			removal.update(indexes)
		else:
			scopes = {}
			has_credit = False
			for idx in indexes:
				item = items[idx]
				specific = get_specific(item.target)
				scopes[idx] = ES_PUBLIC if OPEN in specific else None
				scopes[idx] = ES_CREDIT if IN_CLASS_SAFE in specific else scopes[idx]
				has_credit = has_credit or scopes[idx] == ES_CREDIT

			m_scope = m_scope[0]  # pick first
			for idx in indexes:
				item = items[idx]
				scope = scopes[idx]
				if not scope:
					removal.add(idx)
				elif m_scope == ES_PUBLIC and scope != ES_PUBLIC:
					removal.add(idx)
				elif m_scope == ES_CREDIT and scope == ES_PUBLIC and has_credit:
					removal.add(idx)

	def _allow_discussion_course_bundle(self, context, item, ext_item):
		record = self.record(context)
		topic = resolve_discussion_course_bundle(user=self.remoteUser,
												 item=item,
												 context=context,
												 record=record)
		if topic is None:
			return False

		# replace the target to the topic NTIID
		ext_item[NTIID] = ext_item['target'] = topic.NTIID
		return True

	def allow_assignmentref(self, context, item):
		record = self.record(context)
		assg = IQAssignment(item, None)
		if assg is None or record is None:
			return False
		if record.Scope == ES_ALL:  # instructor
			return True
		course = record.CourseInstance
		predicate = get_course_assessment_predicate_for_user(self.remoteUser, course)
		result = predicate is not None and predicate(assg)
		return result

	def _decorate_external_impl(self, context, result):
		idx = 0
		removal = set()
		discussions = []
		items = result[ITEMS]
		# loop through sources
		for idx, item in enumerate(context):
			if IVisible.providedBy(item) and not self._allow_visible(context, item):
				removal.add(idx)
			elif INTIDiscussionRef.providedBy(item):
				if item.isCourseBundle():
					ext_item = items[idx]
					if not self._allow_discussion_course_bundle(context, item, ext_item):
						removal.add(idx)
				elif self._is_legacy_discussion(item):
					discussions.append(idx)
			elif IMediaRef.providedBy(item):
				self._handle_media_ref(items, item, idx)
			elif INTIAssignmentRef.providedBy(item) and \
				not self.allow_assignmentref(context, item):
				removal.add(idx)

		# filter legacy discussions
		if discussions:
			self._filter_legacy_discussions(context, discussions, removal)

		# remove disallowed items
		if removal:
			result[ITEMS] = [x for idx, x in enumerate(items) if idx not in removal]

@interface.implementer(IExternalMappingDecorator)
@component.adapter(INTIRelatedWorkRef, IRequest)
@component.adapter(INTITimeline, IRequest)
class _NTIAbsoluteURLDecorator(AbstractAuthenticatedRequestAwareDecorator):

	@Lazy
	def is_legacy_ipad(self):
		result = is_legacy_uas(self.request, LEGACY_UAS_40)
		return result

	def _predicate(self, context, result):
		result = self._is_authenticated
		return result

	def _do_decorate_external(self, context, result):
		package = None
		library = component.queryUtility(IContentPackageLibrary)
		if library is not None:
			units = get_item_content_units(context)
			# FIXME: pick first content unit avaiable; clients
			# should try to give us context
			paths = library.pathToNTIID(units[0].ntiid) if units else None
			package = paths[0] if paths else None
		if package is not None:
			location = IContentUnitHrefMapper(package.key.bucket).href  # parent
			for name in ('href', 'icon'):
				value = getattr(context, name, None)
				if value and not value.startswith('/') and '://' not in value:
					value = urljoin(location, value)
					if self.is_legacy_ipad:  # for legacy ipad
						value = urljoin(self.request.host_url, value)
					result[name] = value

@interface.implementer(IExternalMappingDecorator)
class _IPADLegacyReferenceDecorator(AbstractAuthenticatedRequestAwareDecorator):

	def _predicate(self, context, result):
		result = is_legacy_uas(self.request, LEGACY_UAS_40)
		return result

	def _do_decorate_external(self, context, result_map):
		if INTIAssignmentRef.providedBy(context):
			result_map[CLASS] = 'Assignment'
			result_map[MIMETYPE] = 'application/vnd.nextthought.assessment.assignment'
		elif INTIQuestionSetRef.providedBy(context):
			result_map[CLASS] = 'QuestionSet'
			result_map[MIMETYPE] = 'application/vnd.nextthought.naquestionset'
		elif INTIQuestionRef.providedBy(context):
			result_map[CLASS] = 'Question'
			result_map[MIMETYPE] = 'application/vnd.nextthought.naquestion'
		elif INTIDiscussionRef.providedBy(context):
			result_map[MIMETYPE] = 'application/vnd.nextthought.discussion'
