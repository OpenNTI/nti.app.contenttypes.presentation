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

from zope.container.contained import Contained

from zope.interface.interfaces import IMethod

from zope.intid.interfaces import IIntIds

from zope.location.location import LocationProxy

from nti.app.contenttypes.presentation.interfaces import ICoursePresentationAssets

from nti.app.contenttypes.presentation.utils import is_item_visible

from nti.appserver._adapters import _AbstractExternalFieldTraverser

from nti.appserver.interfaces import IExternalFieldTraversable

from nti.assessment.interfaces import IQPoll
from nti.assessment.interfaces import IQSurvey
from nti.assessment.interfaces import IQInquiry
from nti.assessment.interfaces import IQuestion
from nti.assessment.interfaces import IQEvaluation
from nti.assessment.interfaces import IQuestionSet
from nti.assessment.interfaces import IQAssignment

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.presentation import interface_of_asset

from nti.contenttypes.calendar.interfaces import ICalendarEvent

from nti.contenttypes.courses.common import get_course_packages

from nti.contenttypes.courses.utils import get_parent_course

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseOutlineNode

from nti.contenttypes.presentation import ALL_PRESENTATION_ASSETS_INTERFACES

from nti.contenttypes.presentation.interfaces import IAssetRef
from nti.contenttypes.presentation.interfaces import INTIAudio
from nti.contenttypes.presentation.interfaces import INTIMedia
from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTIPollRef
from nti.contenttypes.presentation.interfaces import INTIAudioRef
from nti.contenttypes.presentation.interfaces import INTIMediaRef
from nti.contenttypes.presentation.interfaces import INTIVideoRef
from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTISurveyRef
from nti.contenttypes.presentation.interfaces import IConcreteAsset
from nti.contenttypes.presentation.interfaces import INTIInquiryRef
from nti.contenttypes.presentation.interfaces import INTIQuestionRef
from nti.contenttypes.presentation.interfaces import INTITimelineRef
from nti.contenttypes.presentation.interfaces import INTISlideDeckRef
from nti.contenttypes.presentation.interfaces import INTIAssessmentRef
from nti.contenttypes.presentation.interfaces import INTIAssignmentRef
from nti.contenttypes.presentation.interfaces import INTIDiscussionRef
from nti.contenttypes.presentation.interfaces import IGroupOverViewable
from nti.contenttypes.presentation.interfaces import INTIQuestionSetRef
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import INTICalendarEventRef
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRefPointer
from nti.contenttypes.presentation.interfaces import IUserAssetVisibilityUtility
from nti.contenttypes.presentation.interfaces import ILessonPublicationConstraint

from nti.dataserver.interfaces import IUser

from nti.externalization.persistence import NoPickle

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.namedfile.constraints import FileConstraints

from nti.schema.jsonschema import TAG_HIDDEN_IN_UI

from nti.site.interfaces import IHostPolicyFolder

from nti.site.site import get_component_hierarchy_names

from nti.traversal.traversal import find_interface

logger = __import__('logging').getLogger(__name__)


@interface.implementer(ICourseInstance)
@component.adapter(INTICourseOverviewGroup)
def _course_overview_group_to_course(group):
    return find_interface(group, ICourseInstance, strict=False)


@component.adapter(INTILessonOverview)
@interface.implementer(ICourseInstance)
def _lesson_overview_to_course(item):
    return find_interface(item, ICourseInstance, strict=False)


@component.adapter(IGroupOverViewable)
@interface.implementer(ICourseInstance)
def _group_overviewable_to_course(item):
    return find_interface(item, ICourseInstance, strict=False)


@interface.implementer(ICourseInstance)
@component.adapter(ILessonPublicationConstraint)
def _publication_constraint_to_course(item):
    return find_interface(item, ICourseInstance, strict=False)


@interface.implementer(INTILessonOverview)
@component.adapter(ILessonPublicationConstraint)
def _publication_constraint_to_lesson(item):
    return find_interface(item, INTILessonOverview, strict=False)


@component.adapter(INTIAudioRef)
@interface.implementer(INTIAudio)
def _audioref_to_audio(context):
    name = context.target or context.ntiid
    return component.queryUtility(INTIAudio, name=name)


@component.adapter(INTIVideoRef)
@interface.implementer(INTIVideo)
def _videoref_to_video(context):
    name = context.target or context.ntiid
    return component.queryUtility(INTIVideo, name=name)


@component.adapter(INTIMediaRef)
@interface.implementer(INTIMedia)
def _mediaref_to_media(context):
    name = context.target or context.ntiid
    return component.queryUtility(INTIMedia, name=name)


@interface.implementer(IQuestion)
@component.adapter(INTIQuestionRef)
def _questionref_to_question(context):
    return component.queryUtility(IQuestion, name=context.target or '')


@interface.implementer(IQuestionSet)
@component.adapter(INTIQuestionSetRef)
def _questionsetref_to_questionset(context):
    return component.queryUtility(IQuestionSet, name=context.target or '')


@interface.implementer(IQAssignment)
@component.adapter(INTIAssignmentRef)
def _assignmentref_to_assignment(context):
    return component.queryUtility(IQAssignment, name=context.target or '')


@interface.implementer(IQSurvey)
@component.adapter(INTISurveyRef)
def _surveyref_to_survey(context):
    return component.queryUtility(IQSurvey, name=context.target or '')


@interface.implementer(IQPoll)
@component.adapter(INTIPollRef)
def _pollref_to_poll(context):
    return component.queryUtility(IQPoll, name=context.target or '')


@interface.implementer(IQInquiry)
@component.adapter(INTIInquiryRef)
def _inquiryref_to_inquiry(context):
    return component.queryUtility(IQInquiry, name=context.target or '')


@interface.implementer(IQEvaluation)
@component.adapter(INTIAssessmentRef)
def _evaluationref_to_evaluation(context):
    return component.queryUtility(IQEvaluation, name=context.target or '')


@component.adapter(INTISlideDeckRef)
@interface.implementer(INTISlideDeck)
def _slideckref_to_slidedeck(context):
    return component.queryUtility(INTISlideDeck, name=context.target or '')


@interface.implementer(INTITimeline)
@component.adapter(INTITimelineRef)
def _timelineref_to_timeline(context):
    return component.queryUtility(INTITimeline, name=context.target or '')


@interface.implementer(INTIRelatedWorkRef)
@component.adapter(INTIRelatedWorkRefPointer)
def _relatedworkrefpointer_to_relatedworkref(context):
    return component.queryUtility(INTIRelatedWorkRef, name=context.target or '')


@interface.implementer(ICalendarEvent)
@component.adapter(INTICalendarEventRef)
def _calendareventref_to_calendarref(context):
    return find_object_with_ntiid(context.target or '')


@component.adapter(IAssetRef)
@interface.implementer(IConcreteAsset)
def _reference_to_concrete(context):
    return component.queryUtility(IPresentationAsset, name=context.target or '')


@component.adapter(ICourseOutlineNode)
@interface.implementer(INTILessonOverview)
def _outlinenode_to_lesson(context):
    ntiid = context.LessonOverviewNTIID
    return component.queryUtility(INTILessonOverview, name=ntiid or '')


@component.adapter(IPresentationAsset)
@interface.implementer(IHostPolicyFolder)
def _asset_to_policy_folder(context):
    return find_interface(context, IHostPolicyFolder, strict=False)


@component.adapter(IPresentationAsset)
@interface.implementer(IExternalFieldTraversable)
class _PresentationAssetExternalFieldTraverser(_AbstractExternalFieldTraverser):

    def __init__(self, context, request=None):
        _AbstractExternalFieldTraverser.__init__(self, context, request=request)
        allowed_fields = set()
        asset_iface = interface_of_asset(context)
        for k, v in asset_iface.namesAndDescriptions(all=True):
            # pylint: disable=unused-variable
            __traceback_info__ = k, v
            if IMethod.providedBy(v):
                continue
            # v could be a schema field or an interface.Attribute
            if v.queryTaggedValue(TAG_HIDDEN_IN_UI):
                continue
            allowed_fields.add(k)
        self._allowed_fields = allowed_fields


# constraints


@component.adapter(INTIDiscussionRef)
class _DiscussionRefFileConstraints(FileConstraints):
    max_files = 1
    max_file_size = 10485760  # 10 MB


@component.adapter(INTIRelatedWorkRef)
class _RelatedWorkRefFileConstraints(FileConstraints):
    max_file_size = 104857600  # 100 MB


@component.adapter(INTIMedia)
class _MediaFileConstraints(FileConstraints):
    max_file_size = 104857600  # 100 MB


# course


@component.adapter(IUser, ICourseInstance)
@interface.implementer(IUserAssetVisibilityUtility)
class _UserAssetVisibilityUtility(object):

    def __init__(self, user, course):
        self.user = user
        self.course = course

    def is_item_visible(self, item, user=None, course=None):
        """
        :return: a bool if the item is visible to the user.
        """
        user = user if user is not None else self.user
        course = course if course is not None else self.course
        return is_item_visible(item, user, course)


@NoPickle
@component.adapter(ICourseInstance)
@interface.implementer(ICoursePresentationAssets)
class CoursePresentationAssets(Contained):

    __name__ = 'assets'
    __parent__ = None

    def __init__(self, course):
        self.__parent__ = course

    @property
    def course(self):
        return self.__parent__

    def pkg_containers(self, pacakge):
        result = []
        def recur(unit):
            for child in unit.children or ():
                recur(child)
            result.append(unit.ntiid)
        recur(pacakge)
        return result

    def course_containers(self, course):
        result = set()
        courses = {course, get_parent_course(course)}
        courses.discard(None)
        for _course in courses:
            entry = ICourseCatalogEntry(_course)
            for package in get_course_packages(_course):
                result.update(self.pkg_containers(package))
            result.add(entry.ntiid)
        return result

    def intids(self, provided=ALL_PRESENTATION_ASSETS_INTERFACES):
        catalog = get_library_catalog()
        container_ntiids = self.course_containers(self.course)
        return catalog.get_references(container_all_of=False,
                                      container_ntiids=container_ntiids,
                                      sites=get_component_hierarchy_names(),
                                      provided=provided)
        

    def items(self, provided=ALL_PRESENTATION_ASSETS_INTERFACES):
        catalog = get_library_catalog()
        intids = component.getUtility(IIntIds)
        container_ntiids = self.course_containers(self.course)
        return catalog.search_objects(intids=intids,
                                      container_all_of=False,
                                      container_ntiids=container_ntiids,
                                      sites=get_component_hierarchy_names(),
                                      provided=provided)

    def __getitem__(self, ntiid):
        catalog = get_library_catalog()
        intids = component.getUtility(IIntIds)
        container_ntiids = self.course_containers(self.course)
        res = catalog.search_objects(intids=intids,
                                     ntiid=ntiid,
                                     container_all_of=False,
                                     container_ntiids=container_ntiids,
                                     sites=get_component_hierarchy_names(),
                                     provided=ALL_PRESENTATION_ASSETS_INTERFACES)
        try:
            # TODO We probably want to LocationProxy this with
            # self as the parent. Consider the case where our context (__parent__) is
            # a subinstnace, but we've just looked up a presentation item
            # whose parent is our parent course instance.
            return next(res.items())[1]
        except StopIteration:
            return KeyError(ntiid)
