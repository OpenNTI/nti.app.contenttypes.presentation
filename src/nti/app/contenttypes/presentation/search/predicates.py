#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from pyramid.threadlocal import get_current_request

from zope import interface

from nti.app.authentication import get_remote_user

from nti.app.contenttypes.presentation.utils import is_item_visible

from nti.app.contenttypes.presentation.utils.course import get_presentation_asset_courses

from nti.appserver.pyramid_authorization import has_permission

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contentsearch.interfaces import ISearchHitPredicate

from nti.contentsearch.predicates import DefaultSearchHitPredicate

from nti.contenttypes.presentation.interfaces import IVisible
from nti.contenttypes.presentation.interfaces import INTILessonOverview

from nti.dataserver.authorization import ACT_READ

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.publishing.interfaces import IPublishable

from nti.traversal.traversal import find_interface


@interface.implementer(ISearchHitPredicate)
class _LessonsSearchHitPredicate(DefaultSearchHitPredicate):
    """
    A `ISearchHitPredicate` that only allows `IPresentationAsset`
    items through that are in lessons that are accessible (readable and
    published).
    """

    __name__ = u'LessonsPresentationAsset'

    def _get_lessons_for_item(self, item):
        """
        For the given item, get all containing lessons.
        """
        results = set()
        catalog = get_library_catalog()
        for container in catalog.get_containers(item):
            if container is not None:
                container = find_object_with_ntiid(container)
            if container is not None:
                lesson = find_interface(container,
                                        INTILessonOverview,
                                        strict=False)
                if lesson is not None:
                    results.add(lesson)
        return results

    def _is_published(self, lesson):
        return not IPublishable.providedBy(lesson) or lesson.is_published()

    def allow(self, item, unused_score, unused_query=None):
        lessons = self._get_lessons_for_item(item)
        if not lessons:
            # If no lesson, we're allowed.
            return True

        request = get_current_request()
        for lesson in lessons:
            # Just need a single available/readable lesson to allow.
            if      self._is_published(lesson) \
                and has_permission(ACT_READ, lesson, request):
                return True
        # We have lessons, but no access.
        return False


@interface.implementer(ISearchHitPredicate)
class _AssetVisibleSearchPredicate(DefaultSearchHitPredicate):
    """
    A `ISearchHitPredicate` that only allows `IPresentationAsset`
    items through that are in lessons that are visible.
    """

    __name__ = u'PresentationAssetVisible'

    def allow(self, item, unused_score, unused_query=None):
        user = get_remote_user()
        if IVisible.providedBy(item):
            courses = get_presentation_asset_courses(item)
            for course in courses or ():
                if is_item_visible(item, user, context=course):
                    return True
            return False
        return True
