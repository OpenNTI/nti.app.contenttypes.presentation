#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Adapters for application-level events.

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from pyramid.threadlocal import get_current_request

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from nti.app.contenttypes.presentation.utils import is_item_visible

from nti.app.contenttypes.presentation.utils.course import is_video_included

from nti.contenttypes.completion.completion import CompletedItem

from nti.contenttypes.completion.interfaces import ICompletables
from nti.contenttypes.completion.interfaces import ICompletableItem
from nti.contenttypes.completion.interfaces import ICompletableItemProvider
from nti.contenttypes.completion.interfaces import IRequiredCompletableItemProvider
from nti.contenttypes.completion.interfaces import ICompletableItemCompletionPolicy
from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicyContainer

from nti.contenttypes.completion.policies import AbstractCompletableItemCompletionPolicy
from nti.contenttypes.completion.policies import CompletableItemAggregateCompletionPolicy

from nti.contenttypes.completion.utils import is_item_required

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseOutlineContentNode

from nti.contenttypes.courses.utils import get_parent_course
from nti.contenttypes.courses.utils import get_enrollment_record

from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import IConcreteAsset
from nti.contenttypes.presentation.interfaces import INTIAssignmentRef
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import IPresentationAsset

from nti.externalization.persistence import NoPickle

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.publishing.interfaces import IPublishable
from nti.publishing.interfaces import ICalendarPublishable


logger = __import__('logging').getLogger(__name__)


@NoPickle
@component.adapter(INTIRelatedWorkRef)
@interface.implementer(ICompletableItemCompletionPolicy)
class DefaultRelatedWorkRefCompletionPolicy(AbstractCompletableItemCompletionPolicy):
    """
    A simple completion policy that only cares about some progress on related
    work refs.
    """

    def __init__(self, obj):
        self.asset = obj

    def is_complete(self, progress):
        result = None
        if progress is not None and progress.HasProgress:
            result = CompletedItem(Item=progress.Item,
                                   Principal=progress.User,
                                   CompletedDate=progress.LastModified)
        return result


@NoPickle
@component.adapter(INTIVideo)
@interface.implementer(ICompletableItemCompletionPolicy)
class DefaultVideoCompletionPolicy(CompletableItemAggregateCompletionPolicy):
    """
    By default, videos are not complete unless 95% watched.
    """

    percentage = 0.95

    def __init__(self, obj):
        self.asset = obj


def _asset_completion_policy(asset, course):
    """
    Fetch the :class:`ICompletableItemCompletionPolicy` for this asset, course.
    """
    # First see if we have a specific policy set on our context.
    context_policies = ICompletionContextCompletionPolicyContainer(course)
    try:
        result = context_policies[asset.ntiid]
    except KeyError:
        # Ok, fetch the default
        result = ICompletableItemCompletionPolicy(asset)
    return result


@component.adapter(INTIRelatedWorkRef, ICourseInstance)
@interface.implementer(ICompletableItemCompletionPolicy)
def _related_work_ref_completion_policy(asset, course):
    return _asset_completion_policy(asset, course)


@component.adapter(INTIVideo, ICourseInstance)
@interface.implementer(ICompletableItemCompletionPolicy)
def _video_completion_policy(asset, course):
    return _asset_completion_policy(asset, course)


@component.adapter(INTILessonOverview)
@interface.implementer(ICompletableItemProvider)
class _LessonAssetItemProvider(object):
    """
    Return the :class:`ICompletableItem` items for this user/lesson. This will
    be the set of items in available/published lessons. This provider will not
    return any assignments.
    """

    def __init__(self, context):
        self.context = context
        self._scope_to_items = dict()

    @Lazy
    def course(self):
        return ICourseInstance(self.context)

    def _is_scheduled(self, obj):
        return  ICalendarPublishable.providedBy(obj) \
            and (obj.publishBeginning or obj.publishEnding)

    def _is_available(self, obj, user):
        """
        An object is considered part of completion if it is either published
        or scheduled to be published.
        """
        return not IPublishable.providedBy(obj) \
            or obj.is_published(principal=user) \
            or self._is_scheduled(obj)

    def _is_visible(self, obj, user, record):
        return is_item_visible(obj, user, context=self.course, record=record)

    def _include_item(self, item, user):
        return  ICompletableItem.providedBy(item) \
            and self._is_available(item, user) \

    @Lazy
    def _courses(self):
        course = self.course
        return [course, get_parent_course(course)] if ICourseSubInstance.providedBy(course) else [course]

    def _accum_item(self, item, accum, user, record):
        item = IConcreteAsset(item, item)
        if     INTIAssignmentRef.providedBy(item) \
            or not self._is_visible(item, user, record):
            # Do not pull in target if we are an assignment ref (different
            # provider) or we are not visible.
            return

        if INTIVideo.providedBy(item) and not is_video_included(item, self._courses):
            # If video is created by child course, it shouldn't show in the parent and other child courses.
            return

        target = getattr(item, 'target', '')
        target = find_object_with_ntiid(target)
        if ICompletableItem.providedBy(target):
            # If the target is a completable item, prefer it over the ref.
            if self._include_item(target, user) and self._is_visible(target, user, record):
                accum.add(target)
        elif self._include_item(item, user):
            accum.add(item)
        children = getattr(item, 'Items', None)
        for child in children or ():
            self._accum_item(child, accum, user, record)

    def _get_items_for_lesson(self, lesson, accum, user, record):
        if lesson is not None and self._is_available(lesson, user):
            for group in lesson or ():
                for item in group or ():
                    self._accum_item(item, accum, user, record)

    def _get_items(self, user, record):
        """
        Subclasses may override.
        """
        result = set()
        self._get_items_for_lesson(self.context, result, user, record)
        return result

    def iter_items(self, user):
        record = get_enrollment_record(self.course, user)
        scope = record.Scope if record is not None else 'ALL'
        result = self._scope_to_items.get(scope)
        if result is None:
            result = self._get_items(user, record)
            self._scope_to_items[scope] = result
        return result


@component.adapter(INTILessonOverview)
@interface.implementer(IRequiredCompletableItemProvider)
class _LessonAssetRequiredItemProvider(_LessonAssetItemProvider):
    """
    Return the set of required :class:`ICompletableItem` items for this
    user/course. This will be the set of items in available/published lessons.
    This provider will not return any assignments.
    """

    def _include_item(self, item, user):
        result = super(_LessonAssetRequiredItemProvider, self)._include_item(item, user)
        return result and is_item_required(item, self.course)


@component.adapter(ICourseInstance)
@interface.implementer(ICompletableItemProvider)
class _CourseAssetItemProvider(_LessonAssetItemProvider):
    """
    Return the :class:`ICompletableItem` items for this user/course. This will
    be the set of items in available/published lessons. This provider will not
    return any assignments.
    """

    REQUEST_CACHE_KEY = 'course_completable_items_by_scope'

    def _get_items_for_node(self, node, accum, user, record):
        lesson = find_object_with_ntiid(node.LessonOverviewNTIID)
        return self._get_items_for_lesson(lesson, accum, user, record)

    def _get_items(self, user, record):
        result = set()
        def _recur(node):
            if ICourseOutlineContentNode.providedBy(node):
                self._get_items_for_node(node, result, user, record)
            for child_node in node.values():
                _recur(child_node)
        # pylint: disable=no-member
        _recur(self.course.Outline)
        return result

    def iter_items(self, user):
        request = get_current_request()
        course_scope_items = getattr(request, self.REQUEST_CACHE_KEY, {})
        entry_ntiid = ICourseCatalogEntry(self.course).ntiid
        course_scopes = course_scope_items.setdefault(entry_ntiid, {})
        record = get_enrollment_record(self.course, user)
        scope = record.Scope if record is not None else 'ALL'
        if scope in course_scopes:
            result = course_scopes[scope]
        else:
            result = super(_CourseAssetItemProvider, self).iter_items(user)
            course_scopes[scope] = result
        setattr(request, self.REQUEST_CACHE_KEY, course_scope_items)
        return result


@component.adapter(ICourseInstance)
@interface.implementer(IRequiredCompletableItemProvider)
class _CourseAssetRequiredItemProvider(_CourseAssetItemProvider):
    """
    Return the set of required :class:`ICompletableItem` items for this
    user/course. This will be the set of items in available/published lessons.
    This provider will not return any assignments.
    """

    def iter_items(self, user):
        result = super(_CourseAssetRequiredItemProvider, self).iter_items(user)
        return [x for x in result if is_item_required(x, self.course)]


@interface.implementer(ICompletables)
class AssetCompletables(object):

    __slots__ = ()

    def __init__(self, *args):
        pass

    def iter_objects(self):
        for unused_name, item in component.getUtilitiesFor(IPresentationAsset):
            if ICompletableItem.providedBy(item):
                yield item
