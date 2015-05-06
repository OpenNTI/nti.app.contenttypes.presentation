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

from nti.app.products.courseware.utils import get_any_enrollment
from nti.app.products.courseware.interfaces import NTIID_TYPE_COURSE_TOPIC
from nti.app.products.courseware.interfaces import NTIID_TYPE_COURSE_SECTION_TOPIC

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

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
from nti.contenttypes.courses.discussions.utils import get_discussion_key
from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussions

from nti.contenttypes.presentation.interfaces import EVERYONE
from nti.contenttypes.presentation.interfaces import IVisible
from nti.contenttypes.presentation.interfaces import IMediaRef
from nti.contenttypes.presentation.interfaces import INTIMedia
from nti.contenttypes.presentation.interfaces import INTIDiscussionRef
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup
from nti.contenttypes.presentation.interfaces import IPresentationVisibility

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalObjectDecorator
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.externalization.externalization import to_external_object

from nti.links.links import Link

from nti.ntiids.ntiids import get_parts
from nti.ntiids.ntiids import make_provider_safe

from .utils import get_visibility_for_scope

from . import VIEW_OVERVIEW_CONTENT

LINKS = StandardExternalFields.LINKS
ITEMS = StandardExternalFields.ITEMS
IN_CLASS_SAFE = make_provider_safe(IN_CLASS)

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
				href = IContentUnitHrefMapper( paths[-1].key ).href
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
		try:
			ntiid = context.LessonOverviewNTIID
			lesson = component.queryUtility(INTILessonOverview, name=ntiid) if ntiid else None
			if lesson is not None:
				links = result.setdefault(LINKS, [])
				link = Link(context, rel=VIEW_OVERVIEW_CONTENT,
							elements=(VIEW_OVERVIEW_CONTENT,) )
				links.append(link)
				return True
		except AttributeError:
			pass
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
			course = ICourseInstance(context)
			record = get_any_enrollment(course, self.remoteUser)
			self._record = record
		return self._record

	def _handle_media_ref(self, items, item, idx):
		source = INTIMedia(item, None)
		if source is not None:
			items[idx] = to_external_object(source, name="render")
			return True
		return False
		
	def _allow_visible(self, context, user_visibility, item):
		if item.visibility != EVERYONE and user_visibility != item.visibility:
			record = self.record(context)
			scope = record.Scope if record is not None else None
			if get_visibility_for_scope(scope) != item.visibility:
				return False
		return True
	
	def _allow_legacy_discussion(self, context, item):
		parts = get_parts(item.target)
		nttype = parts.nttype
		specific = parts.specific
		## Check if [legacy] discussion NTIID is of either
		## Topic:EnrolledCourseRoot or Topic:EnrolledCourseSection type.
		## If so only return the reference if [mapped] enrollment scope 
		## is in the specific NTIID string
		if nttype in (NTIID_TYPE_COURSE_TOPIC, NTIID_TYPE_COURSE_SECTION_TOPIC):
			record = self.record(context)
			scope = record.Scope if record is not None else None
			m_scope = ENROLLMENT_LINEAGE_MAP.get(scope or u'')
			m_scope = m_scope[0] if m_scope else None # pick first
			if	(not m_scope) or \
				(m_scope == ES_PUBLIC and OPEN not in specific) or \
				(m_scope == ES_CREDIT and IN_CLASS_SAFE not in specific):
				return False
		return True
	
	def _allow_discussion_course_bundle(self, context, item):
		## get enrollment record
		record = self.record(context)
		scope = record.Scope if record is not None else None
		
		## get course discussion
		key = get_discussion_key(item)
		course = record.CourseInstance if record is not None else None
		discussions = ICourseDiscussions(course, None)
		discussion = discussions.get(key) if discussions else  None
		scopes = discussion.scopes if discussion is None else ()
		
		if	(not scope) or \
			(not scopes) or \
			(ES_ALL not in scopes and scope not in scopes):
			return False
		else:
			pass
		return True
	
	def _decorate_external_impl(self, context, result):
		idx = 0
		items = result[ITEMS]

		## get user presentation visibility
		adapted = IPresentationVisibility(self.remoteUser, None)
		user_visibility = adapted.visibility() if adapted is not None else None
		
		## loop through sources
		for item in context: # should resolve weak refs
			## filter items that cannot be visible for the user
			if 	IVisible.providedBy(item) and \
				not self._allow_visible(context, user_visibility, item):
				del items[idx]
				continue
			elif INTIDiscussionRef.providedBy(item): 
				if item.isCourseBundle():
					if not self._allow_discussion_course_bundle(context, item):
						del items[idx]
						continue
				elif not self._allow_legacy_discussion(context, item):
					del items[idx]
					continue
			elif IMediaRef.providedBy(item):
				self._handle_media_ref(items, item, idx)
	
			idx += 1

	def _do_decorate_external(self, context, result):
		try:
			__traceback_info__ = context
			self._decorate_external_impl(context, result)
		except Exception:
			logger.exception("Error while decorating course overview group")
