#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Adapters for application-level events.

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from nti.contenttypes.completion.completion import CompletedItem

from nti.contenttypes.completion.interfaces import ICompletableItemProvider
from nti.contenttypes.completion.interfaces import ICompletableItemCompletionPolicy
from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicyContainer

from nti.contenttypes.completion.utils import is_item_required

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseOutlineContentNode

from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import IConcreteAsset
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef

from nti.coremetadata.interfaces import IUser

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.publishing.interfaces import IPublishable


logger = __import__('logging').getLogger(__name__)


@component.adapter(INTIRelatedWorkRef)
@interface.implementer(ICompletableItemCompletionPolicy)
class DefaultRelatedWorkRefCompletionPolicy(object):
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


@component.adapter(INTIVideo)
@interface.implementer(ICompletableItemCompletionPolicy)
class DefaultVideoCompletionPolicy(object):
    """
    A simple completion policy that cares about some portion of progress
    being made on videos.
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


@component.adapter(IUser, ICourseInstance)
@interface.implementer(ICompletableItemProvider)
class _AssetItemProvider(object):
    """
    Return the :class:`ICompletableItem` items for this user/course. This will
    be the set of items in available/published lessons.
    """

    def __init__(self, user, course):
        self.user = user
        self.course = course

    def _is_published(self, obj):
        return not IPublishable.providedBy(obj) or obj.is_published()

    def _is_item_required(self, item):
        return  self._is_published(item) \
            and is_item_required(item, self.course)

    def _get_items_for_node(self, node, accum):
        lesson = find_object_with_ntiid(node.LessonOverviewNTIID)
        if lesson is not None and self._is_published(lesson):
            for group in lesson or ():
                for item in group or ():
                    item = IConcreteAsset(item, item)
                    if self._is_item_required(item):
                        accum.add(item)
                    target = getattr(item, 'target', '')
                    target = find_object_with_ntiid(target)
                    if self._is_item_required(target):
                        accum.add(item)

    def iter_items(self):
        result = set()
        def _recur(node):
            if ICourseOutlineContentNode.providedBy(node):
                self._get_items_for_node(node, result)
            for child_node in node.values():
                _recur(child_node)

        _recur(self.course.Outline)
        return result
