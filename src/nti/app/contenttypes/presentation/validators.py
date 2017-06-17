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

from zope.i18n import translate

from nti.app.contenttypes.presentation import MessageFactory as _

from nti.app.contenttypes.presentation.interfaces import IItemRefValidator
from nti.app.contenttypes.presentation.interfaces import ILessonPublicationConstraintValidator

from nti.assessment.interfaces import IQPoll
from nti.assessment.interfaces import IQSurvey
from nti.assessment.interfaces import IQAssignment

from nti.contenttypes.presentation.interfaces import INTIAudio
from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTIPollRef
from nti.contenttypes.presentation.interfaces import INTIAudioRef
from nti.contenttypes.presentation.interfaces import INTIVideoRef
from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTISurveyRef
from nti.contenttypes.presentation.interfaces import INTITimelineRef
from nti.contenttypes.presentation.interfaces import INTISlideDeckRef
from nti.contenttypes.presentation.interfaces import INTIAssignmentRef
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRefPointer
from nti.contenttypes.presentation.interfaces import IAssignmentCompletionConstraint
from nti.contenttypes.presentation.interfaces import ISurveyCompletionConstraint


@interface.implementer(IItemRefValidator)
class _ItemRefValidator(object):

    provided = None
    item_type = None
    field_name = None

    def __init__(self, item):
        self.item = item

    def validate(self):
        reference = self.provided(self.item, None)
        name = getattr(self.item, self.field_name, None) or u''
        if reference is None:
            logger.error("Could not find %s %s", self.item_type, name)
        return bool(reference is not None)


@component.adapter(INTIAssignmentRef)
class _AssignmentRefValidator(_ItemRefValidator):
    field_name = 'target'
    item_type = 'Assignment'
    provided = IQAssignment


@component.adapter(INTIPollRef)
class _PollRefValidator(_ItemRefValidator):
    field_name = 'target'
    item_type = 'Poll'
    provided = IQPoll


@component.adapter(INTISurveyRef)
class _SurveyRefValidator(_ItemRefValidator):
    field_name = 'target'
    item_type = 'Survey'
    provided = IQSurvey


@component.adapter(INTIVideoRef)
class _VideoRefValidator(_ItemRefValidator):
    field_name = 'target'
    item_type = 'Video'
    provided = INTIVideo


@component.adapter(INTIAudioRef)
class _AudioRefValidator(_ItemRefValidator):
    field_name = 'target'
    item_type = 'Audio'
    provided = INTIAudio


@component.adapter(INTISlideDeckRef)
class _SlideDeckRefValidator(_ItemRefValidator):
    field_name = 'target'
    item_type = 'SlideDeck'
    provided = INTISlideDeck


@component.adapter(INTITimelineRef)
class _TimelineRefValidator(_ItemRefValidator):
    field_name = 'target'
    item_type = 'Timeline'
    provided = INTITimeline


@component.adapter(INTIRelatedWorkRefPointer)
class _RelatedWorkRefPointerValidator(_ItemRefValidator):
    field_name = 'target'
    item_type = 'RelatedWork'
    provided = INTIRelatedWorkRef


@component.adapter(IAssignmentCompletionConstraint)
@interface.implementer(ILessonPublicationConstraintValidator)
class _AssignmentCompletionConstraintValidator(object):

    constraint = None

    def __init__(self, constraint):
        self.constraint = constraint

    def validate(self, constraint=None):
        constraint = self.constraint if constraint is None else constraint
        assignments = constraint.assignments
        if not assignments:
            raise ValueError(_(u"Assignment list cannot be empty."))

        for ntiid in assignments:
            if component.queryUtility(IQAssignment, name=ntiid) is None:
                msg = translate(_(u"Assigment ${ntiid} does not exist.",
                                  mapping={'ntiid': ntiid}))
                raise ValueError(msg)


@component.adapter(ISurveyCompletionConstraint)
@interface.implementer(ILessonPublicationConstraintValidator)
class _SurveyCompletionConstraintValidator(object):

    constraint = None

    def __init__(self, constraint):
        self.constraint = constraint

    def validate(self, constraint=None):
        constraint = self.constraint if constraint is None else constraint
        surveys = constraint.surveys
        if not surveys:
            raise ValueError(_(u"Survey list cannot be empty."))

        for ntiid in surveys:
            if component.queryUtility(IQSurvey, name=ntiid) is None:
                msg = translate(_(u"Survey ${ntiid} does not exist.",
                                  mapping={'ntiid': ntiid}))
                raise ValueError(msg)
