#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from datetime import datetime

from zope import component
from zope import interface

from nti.app.assessment.common.utils import get_user
from nti.app.assessment.common.utils import get_available_for_submission_ending

from nti.app.assessment.interfaces import IUsersCourseInquiry
from nti.app.assessment.interfaces import IUsersCourseAssignmentHistory

from nti.appserver.pyramid_authorization import has_permission

from nti.assessment.interfaces import IQSurvey

from nti.contenttypes.presentation.interfaces import ILessonPublicationConstraintChecker

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.courses.utils import is_course_instructor_or_editor

from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import ISurveyCompletionConstraint
from nti.contenttypes.presentation.interfaces import IAssignmentCompletionConstraint

from nti.contenttypes.presentation.lesson import constraints_for_lesson

from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.publishing.interfaces import ICalendarPublishablePredicate

logger = __import__('logging').getLogger(__name__)


@interface.implementer(ILessonPublicationConstraintChecker)
class LessonPublicationConstraintChecker(object):

    constraint = None

    def __init__(self, constraint=None):
        self.constraint = constraint

    def satisfied_time(self, user, constraint=None):
        user = get_user(user)
        constraint = self.constraint if constraint is None else constraint
        course = ICourseInstance(constraint, None) # lineage
        completed_time = 0
        # Don't run through this for instructors or editors.
        if not (   is_course_instructor_or_editor(course, user)
                or has_permission(ACT_CONTENT_EDIT, course)):
            # pylint: disable=no-member
            for item in self.get_constraint_items(constraint) or ():
                item_time = self.check_time_constraint_item(item, user, constraint)
                if item_time is None:
                    # Constraint failed, bail.
                    return None
                completed_time = max(item_time, completed_time)
        # So we have 3 possible cases: Returning 0 if there are no
        # assignments on this constraint for some reason or if the user
        # is an instructor or course editor or admin, returning
        # the satisfied time if all assignments have been submitted,
        # and returning None if some assignments have not yet been
        # submitted.
        #
        # The time at which this constraint is satisfied is the most
        # recent time at which all assignments have been submitted
        # initially by the student, according to createdTime of
        # each submission.
        return completed_time

    def is_satisfied(self, principal=None, constraint=None):
        return self.satisfied_time(principal, constraint) is not None


@component.adapter(IAssignmentCompletionConstraint)
class AssignmentCompletionConstraintChecker(LessonPublicationConstraintChecker):

    def get_constraint_items(self, constraint=None):
        constraint = self.constraint if constraint is None else constraint
        return constraint.assignments

    def check_time_constraint_item(self, item_ntiid, user, constraint=None):
        # for each assignment in the constraint, we want to use the time
        # that it was first completed.
        user = get_user(user)
        completed_time = None
        constraint = self.constraint if constraint is None else constraint
        course = ICourseInstance(constraint, None) # lineage
        histories = component.queryMultiAdapter((course, user),
                                                IUsersCourseAssignmentHistory)
        if histories is not None:
            submission_container = histories.get(item_ntiid, None)
            if submission_container:
                # First submission created time
                submission = submission_container.values()[0]
                completed_time = submission.createdTime
        return completed_time


@component.adapter(ISurveyCompletionConstraint)
class SurveyCompletionConstraintChecker(LessonPublicationConstraintChecker):

    def get_constraint_items(self, constraint=None):
        constraint = self.constraint if constraint is None else constraint
        return constraint.surveys

    def check_time_constraint_item(self, item_ntiid, user, constraint=None):
        # for each survey in the constraint, we want to use the time
        # that it was first completed.
        user = get_user(user)
        completed_time = None
        constraint = self.constraint if constraint is None else constraint
        course = ICourseInstance(constraint, None) # lineage
        histories = component.queryMultiAdapter((course, user),
                                                IUsersCourseInquiry)
        if histories is not None:
            current_time = datetime.utcnow()
            survey = component.queryUtility(IQSurvey, name=item_ntiid)
            submission = histories.get(item_ntiid, None)
            due_date = get_available_for_submission_ending(survey, course)
            due_date = due_date or current_time
            if submission is not None and due_date >= current_time:
                completed_time = submission.createdTime
        return completed_time


@component.adapter(INTILessonOverview)
@interface.implementer(ICalendarPublishablePredicate)
class LessonPublishablePredicate(object):

    __slots__ = ()

    def __init__(self, *args):
        pass

    # pylint: disable=keyword-arg-before-vararg
    def is_published(self, lesson, principal=None, *unused_args, **unused_kwargs):
        constraints = constraints_for_lesson(lesson, False)
        if constraints is not None:
            for constraint in constraints.Items:
                # pylint: disable=too-many-function-args
                checker = ILessonPublicationConstraintChecker(constraint, None)
                if      checker is not None \
                    and not checker.is_satisfied(principal, constraint):
                    return False
        return True
