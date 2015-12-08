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

from nti.appserver.interfaces import IExternalFieldTraversable
from nti.appserver._adapters import _AbstractExternalFieldTraverser

from nti.assessment.interfaces import IQPoll
from nti.assessment.interfaces import IQSurvey
from nti.assessment.interfaces import IQInquiry
from nti.assessment.interfaces import IQuestion
from nti.assessment.interfaces import IQuestionSet
from nti.assessment.interfaces import IQAssignment

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation.interfaces import INTIAudio
from nti.contenttypes.presentation.interfaces import INTIMedia
from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTIPollRef
from nti.contenttypes.presentation.interfaces import INTIAudioRef
from nti.contenttypes.presentation.interfaces import INTIVideoRef
from nti.contenttypes.presentation.interfaces import INTIMediaRoll
from nti.contenttypes.presentation.interfaces import INTISurveyRef
from nti.contenttypes.presentation.interfaces import INTIInquiryRef
from nti.contenttypes.presentation.interfaces import INTIQuestionRef
from nti.contenttypes.presentation.interfaces import INTIMediaRollRef
from nti.contenttypes.presentation.interfaces import INTIAssignmentRef
from nti.contenttypes.presentation.interfaces import INTIQuestionSetRef
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup

from nti.namedfile.file import FileConstraints

from nti.schema.jsonschema import TAG_HIDDEN_IN_UI

from nti.traversal.traversal import find_interface

from . import iface_of_thing

@interface.implementer(ICourseInstance)
@component.adapter(INTICourseOverviewGroup)
def _course_overview_group_to_course(group):
	return find_interface(group, ICourseInstance, strict=False)

@component.adapter(INTILessonOverview)
@interface.implementer(ICourseInstance)
def _lesson_overview_to_course(item):
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

@component.adapter(INTIMediaRollRef)
@interface.implementer(INTIMediaRoll)
def _mediarollref_to_mediaroll(context):
	name = context.target or context.ntiid
	result = component.queryUtility(INTIMediaRoll, name=name)
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

@component.adapter(IPresentationAsset)
@interface.implementer(IExternalFieldTraversable)
class _PresentationAssetExternalFieldTraverser(_AbstractExternalFieldTraverser):

	def __init__(self, context, request=None):
		super(_PresentationAssetExternalFieldTraverser, self).__init__(context, request=request)
		allowed_fields = set()
		asset_iface = iface_of_thing(context)
		for k, v in asset_iface.namesAndDescriptions(all=True):
			__traceback_info__ = k, v
			if interface.interfaces.IMethod.providedBy(v):
				continue
			# v could be a schema field or an interface.Attribute
			if v.queryTaggedValue(TAG_HIDDEN_IN_UI):
				continue
			allowed_fields.add(k)
		self._allowed_fields = allowed_fields

# constraints

@component.adapter(INTIRelatedWorkRef)
class _RelatedWorkRefFileConstraints(FileConstraints):
	max_file_size = 52428800 # 50 MB

@component.adapter(INTIMedia)
class _MediaFileConstraints(FileConstraints):
	max_file_size = 209715200 # 200 MB
