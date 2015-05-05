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

from nti.assessment.interfaces import IQuestionSet
from nti.assessment.interfaces import IQAssignment

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation.interfaces import INTIAudio
from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTIAudioRef
from nti.contenttypes.presentation.interfaces import INTIVideoRef
from nti.contenttypes.presentation.interfaces import INTIQuestionRef
from nti.contenttypes.presentation.interfaces import INTIAssignmentRef
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup

from nti.traversal.traversal import find_interface

@interface.implementer(ICourseInstance)
@component.adapter(INTICourseOverviewGroup)
def _course_overview_group_to_course(group):
	return find_interface(group, ICourseInstance, strict=False)

@interface.implementer(INTILessonOverview)
@component.adapter(INTICourseOverviewGroup)
def _lesson_overview_to_course(group):
	return find_interface(group, ICourseInstance, strict=False)

@component.adapter(INTIAudioRef)
@interface.implementer(INTIAudio)
def _audioref_to_audio(context):
	result = component.queryUtility(INTIAudio, name=context.ntiid)
	return result

@component.adapter(INTIVideoRef)
@interface.implementer(INTIVideo)
def _videoref_to_video(context):
	result = component.queryUtility(INTIVideo, name=context.ntiid)
	return result

@component.adapter(INTIQuestionRef)
@interface.implementer(IQuestionSet)
def _questionsetref_to_questionset(context):
	result = component.queryUtility(IQuestionSet, name=context.target)
	return result

@interface.implementer(IQAssignment)
@component.adapter(INTIAssignmentRef)
def _assignmentref_to_assignment(context):
	result = component.queryUtility(IQAssignment, name=context.target)
	return result
