#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from zope.interface.interfaces import IMethod

from nti.appserver._adapters import _AbstractExternalFieldTraverser

from nti.appserver.interfaces import IExternalFieldTraversable

from nti.assessment.interfaces import IQPoll
from nti.assessment.interfaces import IQSurvey
from nti.assessment.interfaces import IQInquiry
from nti.assessment.interfaces import IQuestion
from nti.assessment.interfaces import IQuestionSet
from nti.assessment.interfaces import IQAssignment

from nti.contenttypes.presentation import iface_of_asset

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseOutlineNode

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
from nti.contenttypes.presentation.interfaces import INTIAssignmentRef
from nti.contenttypes.presentation.interfaces import INTIDiscussionRef
from nti.contenttypes.presentation.interfaces import IGroupOverViewable
from nti.contenttypes.presentation.interfaces import INTIQuestionSetRef
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRefPointer

from nti.namedfile.constraints import FileConstraints

from nti.schema.jsonschema import TAG_HIDDEN_IN_UI

from nti.traversal.traversal import find_interface

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

@component.adapter(INTIAudioRef)
@interface.implementer(INTIAudio)
def _audioref_to_audio(context):
	name = context.target or context.ntiid
	result = component.queryUtility(INTIAudio, name=name)
	return result

@component.adapter(INTIVideoRef)
@interface.implementer(INTIVideo)
def _videoref_to_video(context):
	name = context.target or context.ntiid
	result = component.queryUtility(INTIVideo, name=name)
	return result

@component.adapter(INTIMediaRef)
@interface.implementer(INTIMedia)
def _mediaref_to_media(context):
	name = context.target or context.ntiid
	result = component.queryUtility(INTIMedia, name=name)
	return result

@interface.implementer(IQuestion)
@component.adapter(INTIQuestionRef)
def _questionref_to_question(context):
	result = component.queryUtility(IQuestion, name=context.target)
	return result

@interface.implementer(IQuestionSet)
@component.adapter(INTIQuestionSetRef)
def _questionsetref_to_questionset(context):
	result = component.queryUtility(IQuestionSet, name=context.target)
	return result

@interface.implementer(IQAssignment)
@component.adapter(INTIAssignmentRef)
def _assignmentref_to_assignment(context):
	result = component.queryUtility(IQAssignment, name=context.target)
	return result

@interface.implementer(IQSurvey)
@component.adapter(INTISurveyRef)
def _surveyref_to_survey(context):
	result = component.queryUtility(IQSurvey, name=context.target)
	return result

@interface.implementer(IQPoll)
@component.adapter(INTIPollRef)
def _pollref_to_poll(context):
	result = component.queryUtility(IQPoll, name=context.target)
	return result

@interface.implementer(IQInquiry)
@component.adapter(INTIInquiryRef)
def _inquiryref_to_inquiry(context):
	result = component.queryUtility(IQInquiry, name=context.target)
	return result

@component.adapter(INTISlideDeckRef)
@interface.implementer(INTISlideDeck)
def _slideckref_to_slidedeck(context):
	result = component.queryUtility(INTISlideDeck, name=context.target)
	return result

@interface.implementer(INTITimeline)
@component.adapter(INTITimelineRef)
def _timelineref_to_timeline(context):
	result = component.queryUtility(INTITimeline, name=context.target)
	return result

@interface.implementer(INTIRelatedWorkRef)
@component.adapter(INTIRelatedWorkRefPointer)
def _relatedworkrefpointer_to_relatedworkref(context):
	result = component.queryUtility(INTIRelatedWorkRef, name=context.target)
	return result

@component.adapter(IAssetRef)
@interface.implementer(IConcreteAsset)
def _reference_to_concrete(context):
	result = component.queryUtility(IPresentationAsset, name=context.target)
	return result

@component.adapter(ICourseOutlineNode)
@interface.implementer(INTILessonOverview)
def _outlinenode_to_lesson(context):
	ntiid = getattr(context, 'LessonOverviewNTIID', None)
	result = component.queryUtility(INTILessonOverview, name=ntiid or u'')
	return result

@component.adapter(IPresentationAsset)
@interface.implementer(IExternalFieldTraversable)
class _PresentationAssetExternalFieldTraverser(_AbstractExternalFieldTraverser):

	def __init__(self, context, request=None):
		super(_PresentationAssetExternalFieldTraverser, self).__init__(context, request=request)
		allowed_fields = set()
		asset_iface = iface_of_asset(context)
		for k, v in asset_iface.namesAndDescriptions(all=True):
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
