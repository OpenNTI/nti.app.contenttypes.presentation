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

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.appserver.pyramid_authorization import has_permission

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IContentUnitHrefMapper

from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import ICourseOutlineContentNode

from nti.contenttypes.courses.utils import get_parent_course
from nti.contenttypes.courses.utils import get_course_subinstances

from nti.contenttypes.presentation.interfaces import INTILessonOverview

from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.externalization.singleton import SingletonDecorator

from nti.links.links import Link
from nti.links.externalization import render_link

from nti.ntiids.ntiids import is_valid_ntiid_string

from . import LEGACY_UAS_20
from . import ORDERED_CONTENTS
from . import VIEW_OVERVIEW_CONTENT
from . import VIEW_OVERVIEW_SUMMARY
from . import _AbstractMoveLinkDecorator

from . import is_legacy_uas

LINKS = StandardExternalFields.LINKS

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

@component.adapter(ICourseOutline)
@interface.implementer(IExternalMappingDecorator)
class _CourseOutlineSharedDecorator(object):
	"""
	For course outline editors, display contextual information
	if an outline is shared across multiple courses.
	"""
	__metaclass__ = SingletonDecorator

	def _predicate(self, context, result):
		return has_permission(ACT_CONTENT_EDIT, context, self.request)

	def _possible_courses(self, course):
		if ICourseSubInstance.providedBy(course):
			course = get_parent_course(course)
		return get_course_subinstances(course)

	def decorateExternalMapping(self, context, result):
		course = context.__parent__
		possible_courses = self._possible_courses(course)
		if possible_courses:
			matches = []
			is_shared = False
			our_outline = course.Outline
			for course in possible_courses:
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

	def _predicate(self, context, result):
		return 		self._is_authenticated \
				and has_permission(ACT_CONTENT_EDIT, context, self.request)

	def _do_decorate_external(self, context, result):
		links = result.setdefault(LINKS, [])
		link = Link(context, rel=ORDERED_CONTENTS, elements=('contents',))
		interface.alsoProvides(link, ILocation)
		link.__name__ = ''
		link.__parent__ = context
		links.append(link)

@component.adapter(ICourseOutlineContentNode)
@interface.implementer(IExternalMappingDecorator)
class _CourseOutlineContentNodeLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

	def _predicate(self, context, result):
		return True

	def _legacy_decorate_external(self, context, result):
		if context.src and not is_valid_ntiid_string(context.src):
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
		else:
			ntiid = getattr(context, 'LessonOverviewNTIID', None)
			if ntiid:
				result['LessonOverviewNTIID'] = ntiid

@component.adapter(ICourseOutlineContentNode)
@interface.implementer(IExternalMappingDecorator)
class _IpadCourseOutlineContentNodeSrcDecorator(AbstractAuthenticatedRequestAwareDecorator):

	def _predicate(self, context, result):
		result = is_legacy_uas(self.request, LEGACY_UAS_20)
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
