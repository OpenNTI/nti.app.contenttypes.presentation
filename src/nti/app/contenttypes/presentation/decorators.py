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

from nti.contenttypes.courses.interfaces import IN_CLASS
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseOutlineContentNode

from nti.contenttypes.presentation.interfaces import EVERYONE
from nti.contenttypes.presentation.interfaces import IVisible
from nti.contenttypes.presentation.interfaces import INTIDiscussionRef
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup
from nti.contenttypes.presentation.interfaces import IPresentationVisibility

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.links.links import Link

from nti.ntiids.ntiids import get_parts
from nti.ntiids.ntiids import make_provider_safe

from .utils import get_visibility_for_scope

from . import VIEW_OVERVIEW_CONTENT

LINKS = StandardExternalFields.LINKS
ITEMS = StandardExternalFields.ITEMS
IN_CLASS_PROVIDER = make_provider_safe(IN_CLASS)

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
			lesson = component.getUtility(INTILessonOverview, name=ntiid) if ntiid else None
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
@interface.implementer(IExternalMappingDecorator)
class _NTICourseOverviewGroupDecorator(AbstractAuthenticatedRequestAwareDecorator):
	
	_record = None
	
	def record(self, context):
		if self._record is None:
			course = ICourseInstance(context)
			record = get_any_enrollment(course, self.remoteUser)
			self._record = record
		return self._record

	def _do_decorate_external(self, context, result):		
		idx = 0
		items = result[ITEMS]
		adapted = IPresentationVisibility(self.remoteUser, None)
		user_visibility = adapted.visibility() if adapted is not None else None
		for item in context.Items:
			## filter items that cannot be visible for the user
			if 	IVisible.providedBy(item) and item.visibility != EVERYONE and \
				user_visibility != item.visibility:
				record = self.record(context)
				scope = record.Scope if record is not None else None
				if get_visibility_for_scope(scope) != item.visibility:
					del items[idx]
					continue
			elif INTIDiscussionRef.providedBy(item): 
				parts = get_parts(item.target)
				nttype = parts.nttype
				## check legacy discussions ref
				if nttype in (NTIID_TYPE_COURSE_TOPIC, NTIID_TYPE_COURSE_SECTION_TOPIC):
					record = self.record(context)
					scope = record.Scope if record is not None else None
					
					
			idx += 1
