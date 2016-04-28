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

from pyramid.threadlocal import get_current_request

from nti.app.contenttypes.presentation.decorators import LEGACY_UAS_20
from nti.app.contenttypes.presentation.decorators import VIEW_ORDERED_CONTENTS
from nti.app.contenttypes.presentation.decorators import VIEW_OVERVIEW_CONTENT
from nti.app.contenttypes.presentation.decorators import VIEW_OVERVIEW_SUMMARY

from nti.app.contenttypes.presentation.decorators import is_legacy_uas
from nti.app.contenttypes.presentation.decorators import _AbstractMoveLinkDecorator

from nti.app.products.courseware.decorators import BaseRecursiveAuditLogLinkDecorator

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.appserver.pyramid_authorization import has_permission

from nti.common.property import Lazy
from nti.common.string import TRUE_VALUES

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IContentUnitHrefMapper

from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseOutlineContentNode

from nti.contenttypes.courses.utils import get_course_hierarchy

from nti.contenttypes.presentation.interfaces import INTILessonOverview

from nti.coremetadata.interfaces import IPublishable

from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.links.externalization import render_link

from nti.links.links import Link

from nti.ntiids.ntiids import TYPE_OID
from nti.ntiids.ntiids import is_ntiid_of_type

LINKS = StandardExternalFields.LINKS

def _is_visible(item, request, show_unpublished=True):
	return 	not IPublishable.providedBy(item) \
			or 	item.is_published() \
			or	(show_unpublished and has_permission(ACT_CONTENT_EDIT, item, request))

def _is_true(v):
	return v and str(v).lower() in TRUE_VALUES

def _lesson_overview_links(context, request):
	omit_unpublished = False

	try:
		omit_unpublished = _is_true(request.params.get('omit_unpublished', False))
	except ValueError:
		pass

	name = context.LessonOverviewNTIID
	lesson = component.queryUtility(INTILessonOverview, name=name) if name else None
	if lesson is not None and _is_visible(lesson, request, not omit_unpublished):
		overview_link = Link(context, rel=VIEW_OVERVIEW_CONTENT,
							 elements=(VIEW_OVERVIEW_CONTENT,))
		summary_link = Link(context, rel=VIEW_OVERVIEW_SUMMARY,
							elements=(VIEW_OVERVIEW_SUMMARY,))
		return (overview_link, summary_link)
	return None

@component.adapter(ICourseOutline)
@interface.implementer(IExternalMappingDecorator)
class _CourseOutlineSharedDecorator(AbstractAuthenticatedRequestAwareDecorator):
	"""
	For course outline editors, display contextual information
	if an outline is shared across multiple courses.
	"""
	@Lazy
	def _acl_decoration(self):
		request = get_current_request()
		result = getattr(request, 'acl_decoration', True)
		return result

	def _predicate(self, context, result):
		return 		self._acl_decoration \
				and has_permission(ACT_CONTENT_EDIT, context, self.request)

	def _do_decorate_external(self, context, result):
		context_course = context.__parent__
		possible_courses = get_course_hierarchy(context_course)

		if len( possible_courses ) > 1:
			matches = []
			is_shared = False
			our_outline = context_course.Outline
			for course in possible_courses:
				if context_course == course:
					continue

				if course.Outline == our_outline:
					is_shared = True
					catalog = ICourseCatalogEntry(course, None)
					if catalog is not None:
						matches.append(catalog.ntiid)
			result['IsCourseOutlineShared'] = is_shared
			result['CourseOutlineSharedEntries'] = matches

@component.adapter(ICourseOutline)
@interface.implementer(IExternalMappingDecorator)
class _CourseOutlineMoveLinkDecorator(_AbstractMoveLinkDecorator):
	pass

@component.adapter(ICourseOutlineNode)
@interface.implementer(IExternalMappingDecorator)
class _CourseOutlineEditLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

	@Lazy
	def _acl_decoration(self):
		result = getattr(self.request, 'acl_decoration', True)
		return result

	def _predicate(self, context, result):
		return		self._acl_decoration \
				and self._is_authenticated \
				and has_permission(ACT_CONTENT_EDIT, context, self.request)

	def _do_decorate_external(self, context, result):
		links = result.setdefault(LINKS, [])
		link = Link(context, rel=VIEW_ORDERED_CONTENTS, elements=('contents',))
		interface.alsoProvides(link, ILocation)
		link.__name__ = ''
		link.__parent__ = context
		links.append(link)

@component.adapter(ICourseOutlineContentNode)
@interface.implementer(IExternalMappingDecorator)
class _CourseOutlineContentNodeLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

	@Lazy
	def _acl_decoration(self):
		result = getattr(self.request, 'acl_decoration', True)
		return result

	def _predicate(self, context, result):
		return self._acl_decoration

	def _legacy_decorate_external(self, context, result):
		# We want to decorate the old legacy content driven overviews
		# with proper links. These objects do not have LessonOverviewNTIIDs.
		if context.LessonOverviewNTIID is None:
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
		overview_links = _lesson_overview_links(context, self.request)
		if overview_links:
			links = result.setdefault(LINKS, [])
			links.extend(overview_links)
			return True
		return False

	def _do_decorate_external(self, context, result):
		if not self._overview_decorate_external(context, result):
			self._legacy_decorate_external(context, result)

@component.adapter(ICourseOutlineContentNode)
@interface.implementer(IExternalMappingDecorator)
class _IpadCourseOutlineContentNodeSrcDecorator(AbstractAuthenticatedRequestAwareDecorator):

	def _predicate(self, context, result):
		result = is_legacy_uas(self.request, LEGACY_UAS_20)
		return result

	def _overview_decorate_external(self, context, result):
		try:
			overview_links = _lesson_overview_links(context, self.request)
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

@component.adapter(ICourseOutlineNode)
@interface.implementer(IExternalMappingDecorator)
class OutlineNodeRecursiveAuditLogLinkDecorator(BaseRecursiveAuditLogLinkDecorator):
	pass
