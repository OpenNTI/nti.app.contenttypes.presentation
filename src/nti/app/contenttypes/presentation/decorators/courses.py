#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from zope.location.interfaces import ILocation

from nti.app.contenttypes.presentation import VIEW_COURSE_CONTENT_LIBRARY_SUMMARY

from nti.app.contenttypes.presentation.decorators import VIEW_ASSETS
from nti.app.contenttypes.presentation.decorators import PreviewCourseAccessPredicateDecorator

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.appserver.pyramid_authorization import has_permission

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussion

from nti.contenttypes.courses.discussions.utils import is_nti_course_bundle
from nti.contenttypes.courses.discussions.utils import resolve_discussion_course_bundle

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.courses.utils import is_course_editor

from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.links.links import Link

LINKS = StandardExternalFields.LINKS

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IExternalMappingDecorator)
class _CourseAssetsLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

    def _predicate(self, context, unused_result):
        return   self._is_authenticated \
            and (	is_course_editor(context, self.remoteUser)
                 or has_permission(ACT_CONTENT_EDIT, context, self.request))

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        for rel in (VIEW_ASSETS, VIEW_COURSE_CONTENT_LIBRARY_SUMMARY):
            link = Link(context, rel=rel, elements=('@@' + rel,))
            interface.alsoProvides(link, ILocation)
            link.__name__ = ''
            link.__parent__ = context
            _links.append(link)


@interface.implementer(IExternalMappingDecorator)
class _ByOutlineNodeDecorator(PreviewCourseAccessPredicateDecorator,
                              AbstractAuthenticatedRequestAwareDecorator):

    # We used to check enrollment/instructor access here, for visibility
    # concerns. Since we allow anon access now, we simply provide the link.

    def _do_decorate_external(self, context, result_map):
        course = ICourseInstance(context, context)
        links = result_map.setdefault(LINKS, [])
        for rel in ('MediaByOutlineNode', 'AssetByOutlineNode'):
            link = Link(course, rel=rel, elements=('@@%s' % rel,))
            links.append(link)


@component.adapter(ICourseDiscussion)
@interface.implementer(IExternalMappingDecorator)
class _CourseDiscussionDecorator(AbstractAuthenticatedRequestAwareDecorator):

    def _do_decorate_external(self, context, result_map):
        if is_nti_course_bundle(context):
            course = ICourseInstance(context, None)
            resolved = resolve_discussion_course_bundle(self.remoteUser,
														context,
														course)
            if resolved is not None:
                _, topic = resolved
                result_map['Topic'] = topic.NTIID
