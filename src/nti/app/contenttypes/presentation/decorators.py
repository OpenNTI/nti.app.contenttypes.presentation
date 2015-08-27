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

from nti.app.assessment.interfaces import get_course_assignment_predicate_for_user

from nti.app.contentlibrary.utils import get_item_content_units

from nti.app.products.courseware.interfaces import NTIID_TYPE_COURSE_TOPIC
from nti.app.products.courseware.interfaces import NTIID_TYPE_COURSE_SECTION_TOPIC

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

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

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseOutlineContentNode

from nti.contenttypes.presentation.interfaces import IVisible
from nti.contenttypes.presentation.interfaces import IMediaRef
from nti.contenttypes.presentation.interfaces import INTIMedia
from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTIAssignmentRef
from nti.contenttypes.presentation.interfaces import INTIDiscussionRef
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalObjectDecorator
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.externalization.externalization import to_external_object

from nti.links.links import Link
from nti.links.externalization import render_link

from nti.ntiids.ntiids import get_type
from nti.ntiids.ntiids import get_specific
from nti.ntiids.ntiids import make_provider_safe

from .utils import is_item_visible
from .utils import get_enrollment_record
from .utils import resolve_discussion_course_bundle

from . import VIEW_OVERVIEW_CONTENT
from . import VIEW_OVERVIEW_SUMMARY

NTIID = StandardExternalFields.NTIID
LINKS = StandardExternalFields.LINKS
ITEMS = StandardExternalFields.ITEMS
IN_CLASS_SAFE = make_provider_safe(IN_CLASS)

def _lesson_overview_links(context):
	try:
		name = context.LessonOverviewNTIID
		lesson = component.queryUtility(INTILessonOverview, name=name) if name else None
		if lesson is not None:
			overview_link = Link(context, rel=VIEW_OVERVIEW_CONTENT,
								 elements=(VIEW_OVERVIEW_CONTENT,))
			summary_link = Link(context, rel=VIEW_OVERVIEW_SUMMARY,
								elements=(VIEW_OVERVIEW_SUMMARY,))
			return (overview_link, summary_link)
	except AttributeError:
		pass
	return None

@component.adapter(ICourseOutlineContentNode)
@interface.implementer(IExternalMappingDecorator)
class _CourseOutlineContentNodeLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

	def _predicate(self, context, result):
		return True

	def _legacy_decorate_external(self, context, result):
		if context.src:
			library = component.queryUtility(IContentPackageLibrary)
			paths = library.pathToNTIID(context.ContentNTIID) if library else ()
			if paths:
				href = IContentUnitHrefMapper(paths[-1].key).href
				href = urljoin(href, context.src)
				# set link for overview
				links = result.setdefault(LINKS, [])
				link = Link(href, rel=VIEW_OVERVIEW_CONTENT,
							ignore_properties_of_target=True)
				interface.alsoProvides(link, ILocation)
				link.__name__ = ''
				link.__parent__ = context
				links.append(link)
				return True
		return False

	def _overview_decorate_external(self, context, result):
		overview_links = _lesson_overview_links(context)
		if overview_links:
			links = result.setdefault(LINKS, [])
			links.extend(overview_links)
			return True
		return False

	def _do_decorate_external(self, context, result):
		if not self._overview_decorate_external(context, result):
			self._legacy_decorate_external(context, result)

@component.adapter(INTICourseOverviewGroup)
@interface.implementer(IExternalObjectDecorator)
class _NTICourseOverviewGroupDecorator(AbstractAuthenticatedRequestAwareDecorator):

	_record = None

	def record(self, context):
		if self._record is None:
			self._record = get_enrollment_record(context, self.remoteUser)
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
		ext_item[NTIID] = ext_item['target'] = topic.NTIID  # replace the target to the topic NTIID
		return True

	def allow_assignmentref(self, context, item):
		record = self.record(context)
		assg = IQAssignment(item, None)
		if assg is None or record is None:
			return False
		if record.Scope == ES_ALL: # instructor
			return True
		course = record.CourseInstance
		predicate = get_course_assignment_predicate_for_user(self.remoteUser, course)
		result = predicate is None and predicate(assg)
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

	def _do_decorate_external(self, context, result):
		try:
			__traceback_info__ = context
			self._decorate_external_impl(context, result)
		except Exception:
			logger.exception("Error while decorating course overview group")

def is_legacy_uas(request, legacy_uas):
	ua = request.environ.get('HTTP_USER_AGENT', '')
	if not ua:
		return False

	for lua in legacy_uas:
		if ua.startswith(lua):
			return True
	return False

@component.adapter(ICourseOutlineContentNode)
@interface.implementer(IExternalMappingDecorator)
class _IpadCourseOutlineContentNodeSrcDecorator(AbstractAuthenticatedRequestAwareDecorator):

	LEGACY_UAS = ("NTIFoundation DataLoader NextThought/1.0",
				  "NTIFoundation DataLoader NextThought/1.1.0",
				  "NTIFoundation DataLoader NextThought/1.1.1",
				  "NTIFoundation DataLoader NextThought/1.2.")

	def _predicate(self, context, result):
		result = is_legacy_uas(self.request, self.LEGACY_UAS)
		return result

	def _overview_decorate_external(self, context, result):
		try:
			overview_links = _lesson_overview_links(context)
			link = overview_links[0] if overview_links else None
			if link is not None:
				href = render_link(link)['href']
				url = urljoin(self.request.host_url, href)
				result['src'] = url
				return True
		except (KeyError, ValueError, AssertionError):
			pass
		return False

	def _do_decorate_external(self, context, result):
		self._overview_decorate_external(context, result)

@interface.implementer(IExternalMappingDecorator)
@component.adapter(INTIRelatedWorkRef, IRequest)
@component.adapter(INTITimeline, IRequest)
class _NTIAbsoluteURLDecorator(AbstractAuthenticatedRequestAwareDecorator):

	LEGACY_UAS = ("NTIFoundation DataLoader NextThought/1.0",
				  "NTIFoundation DataLoader NextThought/1.1.0",
				  "NTIFoundation DataLoader NextThought/1.1.1",
				  "NTIFoundation DataLoader NextThought/1.2.",
				  "NTIFoundation DataLoader NextThought/1.3.0",
				  "NTIFoundation DataLoader NextThought/1.3.1")

	@Lazy
	def is_legacy_ipad(self):
		result = is_legacy_uas(self.request, self.LEGACY_UAS)
		return result

	def _predicate(self, context, result):
		result = bool(self._is_authenticated)
		return result

	def _do_decorate_external(self, context, result):
		package = None
		library = component.queryUtility(IContentPackageLibrary)
		if library is not None:
			units = get_item_content_units(context)
			# pick first content unit avaiable; clients
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
class _MediaByOutlineNodeDecorator(AbstractAuthenticatedRequestAwareDecorator):

	def _predicate(self, context, result):
		course = ICourseInstance(context, None)
		record = get_enrollment_record(context, self.remoteUser) if not course else None
		return record is not None
	
	def _do_decorate_external(self, context, result_map):
		course = ICourseInstance(context, context)
		links = result_map.setdefault( LINKS, [] )
		for rel in ('MediaByOutlineNode',):
			# Prefer to canonicalize these through to the course, if possible
			link = Link( course,
						 rel=rel,
						 elements=(rel,),
						 # We'd get the wrong type/ntiid values if we
						 # didn't ignore them.
						 ignore_properties_of_target=True)
			links.append(link)
