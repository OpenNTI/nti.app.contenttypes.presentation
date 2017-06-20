#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from pyramid import httpexceptions as hexc

from pyramid.threadlocal import get_current_request

from nti.app.authentication import get_remote_user

from nti.app.contenttypes.presentation.interfaces import IPresentationAssetProcessor

from nti.app.contenttypes.presentation.processors.mixins import set_creator
from nti.app.contenttypes.presentation.processors.mixins import canonicalize
from nti.app.contenttypes.presentation.processors.mixins import add_to_container
from nti.app.contenttypes.presentation.processors.mixins import get_context_registry

from nti.app.externalization.error import raise_json_error

from nti.assessment.interfaces import IQInquiry
from nti.assessment.interfaces import IQAssessment

from nti.contenttypes.courses.discussions.utils import resolve_discussion_course_bundle

from nti.contenttypes.presentation.discussion import is_nti_course_bundle

from nti.contenttypes.presentation.interfaces import INTISurveyRef
from nti.contenttypes.presentation.interfaces import INTIInquiryRef
from nti.contenttypes.presentation.interfaces import INTIAssessmentRef
from nti.contenttypes.presentation.interfaces import INTIAssignmentRef
from nti.contenttypes.presentation.interfaces import INTIDiscussionRef
from nti.contenttypes.presentation.interfaces import IGroupOverViewable
from nti.contenttypes.presentation.interfaces import INTIQuestionSetRef
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup

from nti.dataserver.contenttypes.forums.interfaces import ITopic

from nti.ntiids.ntiids import find_object_with_ntiid


def handle_overviewable(item, context, creator=None, request=None):
    # set creator
    set_creator(item, creator)
    # add to course container
    add_to_container(context, item)
    return item


def handle_assessment_ref(item, context, creator=None, request=None):
    handle_overviewable(item, context, creator, request)
    # find the target
    if INTIInquiryRef.providedBy(item):
        reference = IQInquiry(item, None)
    else:
        reference = IQAssessment(item, None)
    if reference == None:
        request = request or get_current_request()
        raise_json_error(request,
                         hexc.HTTPUnprocessableEntity,
                         {
                             'message': _(u'No assessment/inquiry found for given ntiid.'),
                             'field': 'ntiid'
                         },
                         None)
    if INTIAssignmentRef.providedBy(item):
        item.label = reference.title if not item.label else item.label
        item.title = reference.title if not item.title else item.title
    elif INTIQuestionSetRef.providedBy(item) or INTISurveyRef.providedBy(item):
        draw = getattr(reference, 'draw', None)
        item.question_count = draw or len(reference)
        item.label = reference.title if not item.label else item.label
    item.containerId = reference.containerId
    return item


def handle_discussion_ref(item, context, creator=None, request=None):
    handle_overviewable(item, context, creator, request)
    if is_nti_course_bundle(item.target):
        item.id = item.target
        item.target = None
    if not item.isCourseBundle():
        target = find_object_with_ntiid(item.target or '')
        if target is None or not ITopic.providedBy(target):
            request = request or get_current_request()
            raise_json_error(request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u'No valid topic found for given ntiid.'),
                                 'field': 'ntiid'
                             },
                             None)
    else:
        remote_user = get_remote_user()
        resolved = resolve_discussion_course_bundle(remote_user,
                                                    item,
                                                    context=context)
        if resolved is not None:  # (discussion, topic)
            item.target = resolved[1].NTIID
    return item


def handle_overview_group(group, context, creator=None, request=None):
    # set creator
    set_creator(group, creator)
    # add to course container
    add_to_container(context, group)
    registry = get_context_registry(context)
    # have unique copies of group items
    canonicalize(group.Items, creator,
                 registry=registry,
                 base=group.ntiid)
    # process group items
    for item in group or ():
        proc = IPresentationAssetProcessor(item)
        proc.handle(item, context, creator, request)


@component.adapter(IGroupOverViewable)
@interface.implementer(IPresentationAssetProcessor)
class GroupOverViewableProcessor(object):

    def __init__(self, asset=None):
        self.asset = asset

    def handle(self, item, context, creator=None, request=None):
        item = self.asset if item is None else item
        return handle_overviewable(item, context, creator, request)


@component.adapter(INTIAssessmentRef)
@interface.implementer(IPresentationAssetProcessor)
class AssessmentRefProcessor(object):

    def __init__(self, asset=None):
        self.asset = asset

    def handle(self, item, context, creator=None, request=None):
        item = self.asset if item is None else item
        return handle_assessment_ref(item, context, creator, request)


@component.adapter(INTIDiscussionRef)
@interface.implementer(IPresentationAssetProcessor)
class DiscussionRefProcessor(object):

    def __init__(self, asset=None):
        self.asset = asset

    def handle(self, item, context, creator=None, request=None):
        item = self.asset if item is None else item
        return handle_discussion_ref(item, context, creator, request)


@component.adapter(INTICourseOverviewGroup)
@interface.implementer(IPresentationAssetProcessor)
class CourseOverviewGroupProcessor(object):

    def __init__(self, asset=None):
        self.asset = asset

    def handle(self, item, context, creator=None, request=None):
        item = self.asset if item is None else item
        return handle_overview_group(item, context, creator, request)
