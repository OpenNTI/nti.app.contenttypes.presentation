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

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.completion.interfaces import ICompletableItemCompletionPolicy
from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicyContainer


from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef

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
        return progress is not None and progress.HasProgress


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
        return progress is not None and progress.HasProgress


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
