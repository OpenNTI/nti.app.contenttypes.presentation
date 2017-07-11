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

from nti.app.contenttypes.presentation.processors.asset import handle_asset

from nti.app.contenttypes.presentation.processors.mixins import BaseAssetProcessor

from nti.app.contenttypes.presentation.processors.mixins import canonicalize
from nti.app.contenttypes.presentation.processors.mixins import get_context_registry

from nti.app.externalization.error import raise_json_error

from nti.assessment.interfaces import IQInquiry
from nti.assessment.interfaces import IQAssessment

from nti.contenttypes.courses.discussions.utils import resolve_discussion_course_bundle

from nti.contenttypes.presentation.discussion import is_nti_course_bundle

from nti.contenttypes.presentation.interfaces import IAssetRef
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


def handle_assessment_ref(item, context, creator=None, request=None):
    handle_asset(item, context, creator, request)
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
    handle_asset(item, context, creator, request)
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
    handle_asset(group, context, creator, request)
    registry = get_context_registry(context)
    # transform to refs
    for idx, item in enumerate(group.Items or ()):
        group.Items[idx] = IAssetRef(item, item)
    # have unique copies of group items
    canonicalize(group.Items, creator,
                 registry=registry,
                 base=group.ntiid)
    # process group items
    for item in group or ():
        item.__parent__ = group  # take ownership
        proc = IPresentationAssetProcessor(item)
        proc.handle(item, context, creator, request)


@component.adapter(IGroupOverViewable)
@interface.implementer(IPresentationAssetProcessor)
class GroupOverViewableProcessor(BaseAssetProcessor):

    def handle(self, item, context, creator=None, request=None):
        item = self.asset if item is None else item
        return handle_asset(item, context, creator, request)


@component.adapter(INTIAssessmentRef)
@interface.implementer(IPresentationAssetProcessor)
class AssessmentRefProcessor(BaseAssetProcessor):

    def handle(self, item, context, creator=None, request=None):
        item = self.asset if item is None else item
        return handle_assessment_ref(item, context, creator, request)


@component.adapter(INTIDiscussionRef)
@interface.implementer(IPresentationAssetProcessor)
class DiscussionRefProcessor(BaseAssetProcessor):

    def handle(self, item, context, creator=None, request=None):
        item = self.asset if item is None else item
        return handle_discussion_ref(item, context, creator, request)


@component.adapter(INTICourseOverviewGroup)
@interface.implementer(IPresentationAssetProcessor)
class CourseOverviewGroupProcessor(BaseAssetProcessor):

    def handle(self, item, context, creator=None, request=None):
        item = self.asset if item is None else item
        return handle_overview_group(item, context, creator, request)
