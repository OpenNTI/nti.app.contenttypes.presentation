#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division

logger = __import__('logging').getLogger(__name__)

import itertools

from zope import interface

from pyramid.threadlocal import get_current_request

from nti.app.authentication import get_remote_user

from nti.app.contenttypes.presentation.utils import is_item_visible

from nti.app.contenttypes.presentation.utils.course import get_presentation_asset_courses

from nti.appserver.pyramid_authorization import has_permission

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contentsearch.interfaces import ISearchHitPredicate

from nti.contentsearch.predicates import DefaultSearchHitPredicate

from nti.contenttypes.presentation.interfaces import IVisible
from nti.contenttypes.presentation.interfaces import INTIMedia
from nti.contenttypes.presentation.interfaces import INTILessonOverview

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.publishing.interfaces import IPublishable

from nti.site.site import get_component_hierarchy_names

from nti.traversal.traversal import find_interface


@interface.implementer(ISearchHitPredicate)
class _LessonsSearchHitPredicate(DefaultSearchHitPredicate):
    """
    A `ISearchHitPredicate` that only allows `IPresentationAsset`
    items through that are in lessons that are accessible (readable and
    published).
    """

    __name__ = u'LessonsPresentationAsset'

    def _get_target_refs(self, target_ntiid):
        """
        For a target_ntiid and interface, get all references.
        """
        catalog = get_library_catalog()
        sites = get_component_hierarchy_names()
        refs = tuple(catalog.search_objects(target=target_ntiid,
                                            sites=sites))
        return refs

    def _iter_lessons(self, item):
        """
        For the given item, get all containing lessons.
        """
        catalog = get_library_catalog()
        # We can only reliably get lessons via refs (in a few cases).
        refs = self._get_target_refs(item.ntiid)
        all_items = refs + (item,)
        for item in all_items:
            for container in catalog.get_containers(item):
                if container is not None:
                    container = find_object_with_ntiid(container)
                if container is not None:
                    lesson = find_interface(container,
                                            INTILessonOverview,
                                            strict=False)
                    if lesson is not None:
                        yield lesson

    def _is_published(self, lesson):
        return not IPublishable.providedBy(lesson) or lesson.is_published()

    def allow(self, item, unused_score, unused_query=None):
        # If no lessons, we're allowed.
        result = True
        request = get_current_request()
        for lesson in self._iter_lessons(item):
            # If we have any lessons, we default to False
            result = False

            # Just need a single available/readable lesson to allow.
            if         (self._is_published(lesson) \
                   and has_permission(ACT_READ, lesson, request)) \
                or has_permission(ACT_CONTENT_EDIT, lesson, request):
                return True
        return result


@interface.implementer(ISearchHitPredicate)
class _TranscriptSearchHitPredicate(_LessonsSearchHitPredicate):

    __name__ = u'TranscriptLessonsPresentationAsset'

    def _iter_lessons(self, item):
        #: Look for our media lessons first, falling back to ourselves.
        #: Only the media lessons are probably in the container catalog.
        media = find_interface(item, INTIMedia, strict=False)
        media_iter = super(_TranscriptSearchHitPredicate, self)._iter_lessons(media)
        transcript_iter = super(_TranscriptSearchHitPredicate, self)._iter_lessons(item)
        return itertools.chain(media_iter, transcript_iter)


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
