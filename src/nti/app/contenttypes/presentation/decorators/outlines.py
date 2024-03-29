#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from six.moves import urllib_parse

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.location.interfaces import ILocation

from nti.app.contenttypes.presentation.decorators import LEGACY_UAS_20
from nti.app.contenttypes.presentation.decorators import VIEW_LESSON_PROGRESS
from nti.app.contenttypes.presentation.decorators import VIEW_ORDERED_CONTENTS
from nti.app.contenttypes.presentation.decorators import VIEW_OVERVIEW_CONTENT
from nti.app.contenttypes.presentation.decorators import VIEW_OVERVIEW_SUMMARY
from nti.app.contenttypes.presentation.decorators import VIEW_LESSON_PROGRESS_STATS

from nti.app.contenttypes.presentation.decorators import is_legacy_uas
from nti.app.contenttypes.presentation.decorators import get_omit_published
from nti.app.contenttypes.presentation.decorators import can_view_publishable

from nti.app.contenttypes.presentation.decorators import _AbstractMoveLinkDecorator

from nti.app.products.courseware.decorators import BaseRecursiveAuditLogLinkDecorator

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.appserver.pyramid_authorization import has_permission

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IContentUnitHrefMapper

from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseOutlineContentNode

from nti.contenttypes.courses.utils import get_course_hierarchy

from nti.contenttypes.presentation.interfaces import INTILessonOverview

from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.externalization.singleton import Singleton

from nti.links import render_link

from nti.links.links import Link

from . import _AbstractPublicationConstraintsDecorator

LINKS = StandardExternalFields.LINKS

logger = __import__('logging').getLogger(__name__)


def _lesson_overview_links(context, request):
    lesson = INTILessonOverview(context, None)
    if lesson is not None and can_view_publishable(lesson, request):
        result = []
        omit_unpublished = get_omit_published(request)
        for name in (VIEW_OVERVIEW_CONTENT, VIEW_OVERVIEW_SUMMARY):
            link = Link(context,
                        rel=name,
                        elements=('@@' + name,),
                        params={'omit_unpublished': omit_unpublished})
            result.append(link)
        return tuple(result)
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
        return getattr(self.request, 'acl_decoration', True)

    def _predicate(self, context, unused_result):
        return self._acl_decoration \
           and has_permission(ACT_CONTENT_EDIT, context, self.request)

    def _do_decorate_external(self, context, result):
        context_course = context.__parent__
        possible_courses = get_course_hierarchy(context_course)
        if len(possible_courses) > 1:
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
        return getattr(self.request, 'acl_decoration', True)

    def _predicate(self, context, unused_result):
        return self._acl_decoration \
           and self._is_authenticated \
           and has_permission(ACT_CONTENT_EDIT, context, self.request)

    def _do_decorate_external(self, context, result):
        links = result.setdefault(LINKS, [])
        link = Link(context, rel=VIEW_ORDERED_CONTENTS,
                    elements=('@@contents',))
        interface.alsoProvides(link, ILocation)
        link.__name__ = ''
        link.__parent__ = context
        links.append(link)


@component.adapter(ICourseOutlineContentNode)
@interface.implementer(IExternalMappingDecorator)
class _CourseOutlineContentNodeLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

    @Lazy
    def _acl_decoration(self):
        return getattr(self.request, 'acl_decoration', True)

    def _predicate(self, unused_context, unused_result):
        return self._acl_decoration

    def _legacy_decorate_external(self, context, result):
        # We want to decorate the old legacy content driven overviews
        # with proper links. These objects do not have LessonOverviewNTIIDs.
        if context.LessonOverviewNTIID is None:
            ntiid = context.ContentNTIID
            library = component.queryUtility(IContentPackageLibrary)
            paths = library.pathToNTIID(ntiid) if library else ()
            if paths:
                href = IContentUnitHrefMapper(paths[-1].key).href
                href = urllib_parse.urljoin(href, context.src)
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

    def _predicate(self, unused_context, unused_result):
        return is_legacy_uas(self.request, LEGACY_UAS_20)

    def _overview_decorate_external(self, context, result):
        try:
            overview_links = _lesson_overview_links(context, self.request)
            link = overview_links[0] if overview_links else None
            if link is not None:
                href = render_link(link)['href']
                url = urllib_parse.urljoin(self.request.host_url, href)
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


@component.adapter(ICourseOutlineContentNode)
@interface.implementer(IExternalMappingDecorator)
class _CourseOutlineNodeProgressLinkDecorator(Singleton):
    """
    Return a link on the content node in which the client can retrieve
    progress information for a user.
    """

    def decorateExternalObject(self, original, external):
        links = external.setdefault(LINKS, [])
        for rel in (VIEW_LESSON_PROGRESS, VIEW_LESSON_PROGRESS_STATS):
            link = Link(original, rel=rel, elements=('@@%s' % rel,))
            interface.alsoProvides(link, ILocation)
            link.__name__ = ''
            link.__parent__ = original
            links.append(link)


@component.adapter(ICourseOutlineNode)
@interface.implementer(IExternalMappingDecorator)
class _CourseOutlineNodePublicationConstraintsDecorator(_AbstractPublicationConstraintsDecorator):

    def _lesson(self, context):
        return INTILessonOverview(context, None)
