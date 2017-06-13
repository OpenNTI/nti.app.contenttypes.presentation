#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from datetime import datetime

from zope import component
from zope import interface

from zope.component.hooks import site as current_site

from zope.interface.adapter import _lookupAll as zopeLookupAll  # Private func

from zope.security.interfaces import IPrincipal

from nti.app.assessment.common import has_submitted_inquiry
from nti.app.assessment.common import has_submitted_assigment
from nti.app.assessment.common import get_available_for_submission_ending

from nti.app.assessment.interfaces import IUsersCourseAssignmentHistory

from nti.contenttypes.presentation.interfaces import ILessonPublicationConstraintChecker

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.courses.utils import is_course_instructor_or_editor

from nti.contenttypes.presentation import ALL_PRESENTATION_ASSETS_INTERFACES

from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import ISurveyCompletionConstraint
from nti.contenttypes.presentation.interfaces import IAssignmentCompletionConstraint

from nti.contenttypes.presentation.lesson import constraints_for_lesson

from nti.appserver.pyramid_authorization import has_permission

from nti.assessment.interfaces import IQSurvey
from nti.assessment.interfaces import IQAssignment

from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import ISystemUserPrincipal

from nti.dataserver.metadata.predicates import BasePrincipalObjects

from nti.dataserver.users.users import User

from nti.publishing.interfaces import ICalendarPublishablePredicate

from nti.site.hostpolicy import get_all_host_sites


# metadata


def lookup_all_presentation_assets(site_registry):
    result = {}
    required = ()
    order = len(required)
    for registry in site_registry.utilities.ro:  # must keep order
        byorder = registry._adapters
        if order >= len(byorder):
            continue
        components = byorder[order]
        extendors = ALL_PRESENTATION_ASSETS_INTERFACES
        zopeLookupAll(components, required, extendors, result, 0, order)
        break  # break on first
    return result


@component.adapter(ISystemUserPrincipal)
class _PresentationAssetObjects(BasePrincipalObjects):

    def iter_objects(self):
        result = []
        for site in get_all_host_sites():
            with current_site(site):
                registry = site.getSiteManager()
                site_components = lookup_all_presentation_assets(registry)
                result.extend(site_components.values())
        return result


# lesson constraints


def get_user(user):
    if IPrincipal.providedBy(user):
        user = user.id
    if user is not None and not IUser.providedBy(user):
        user = User.get_user(str(user))
    return user


@interface.implementer(ILessonPublicationConstraintChecker)
@component.adapter(IAssignmentCompletionConstraint)
class AssignmentCompletionConstraintChecker(object):

    constraint = None

    def __init__(self, constraint=None):
        self.constraint = constraint

    def satisfied_time(self, user):
        user = get_user(user)
        course = ICourseInstance(self, None)

        # By default, unless we have relevant completed constraints,
        # we return 0.
        completed_time = 0

        # Don't run through this for instructors or editors.
        if not (is_course_instructor_or_editor(course, user)
                or has_permission(ACT_CONTENT_EDIT, course)):

            histories = component.queryMultiAdapter((course, user),
                                                    IUsersCourseAssignmentHistory)
            if histories:
                for assignment in self.constraint.assignments:
                    # for each assignment in the constraint, we want to use the time
                    # that it was first completed.
                    assignment_satisfied_time = 0
                    # note that these are assignment ntiids, not assignment
                    # objects
                    submission = histories.get(assignment, None)
                    if submission is not None:
                        assignment_satisfied_time = submission.createdTime
                        # We only want to update this for a submitted
                        # assignment
                        if completed_time != 0:
                            completed_time = max(
                                assignment_satisfied_time, completed_time)
                        else:
                            # Make sure to assign completed_time the first
                            # time through the loop
                            completed_time = assignment_satisfied_time
                    else:
                        # If an assignment for this constraint has not been
                        # submitted, we don't care about checking the others;
                        # we should just return None to indicate this constraint
                        # has not been satisfied.
                        completed_time = None
                        break

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

    def is_satisfied(self, constraint=None, principal=None):
        user = get_user(principal)
        if user is None:
            return False
        constraint = self.constraint if constraint is None else constraint
        course = ICourseInstance(constraint, None)
        if course is None:
            return False
        # allow editors and instructors
        if     is_course_instructor_or_editor(course, user) \
            or has_permission(ACT_CONTENT_EDIT, course):
            return True
        # check assignment constraints
        for assignment_ntiid in constraint.assignments or ():
            assignment = component.queryUtility(IQAssignment,
                                                name=assignment_ntiid)
            if assignment is None:
                continue
            if not has_submitted_assigment(course, user, assignment):
                return False
        return True


@interface.implementer(ILessonPublicationConstraintChecker)
@component.adapter(ISurveyCompletionConstraint)
class SurveyCompletionConstraintChecker(object):

    constraint = None

    def __init__(self, constraint=None):
        self.constraint = constraint

    def satisfied_time(self, user):
        user = User.get_user(user)
        course = ICourseInstance(self, None)

        # If we don't have any completed surveys for this constraint,
        # we return 0 so that caching doesn't need to reload the lesson
        # outline.
        completed_time = 0

        user = User.get_user(user)
        course = ICourseInstance(self, None)

        # By default, unless we have relevant completed constraints,
        # we return 0.
        completed_time = 0

        # Don't run through this for instructors or editors.

        if not (is_course_instructor_or_editor(course, user)
                or has_permission(ACT_CONTENT_EDIT, course)):

            histories = component.queryMultiAdapter((course, user),
                                                    IUsersCourseAssignmentHistory)
            if histories:
                for survey in self.constraint.surveys:
                    # for each survey in the constraint, we want to use the time
                    # that it was first completed.
                    survey_satisfied_time = 0
                    # note that these are survey ntiids, not survey objects
                    submission = histories.get(survey, None)
                    if submission is not None:
                        survey_satisfied_time = submission.createdTime
                        # We only want to update this for a submitted survey
                        if completed_time != 0:
                            completed_time = max(
                                survey_satisfied_time, completed_time)
                        else:
                            # Make sure to assign completed_time the first
                            # time through the loop
                            completed_time = survey_satisfied_time
                    else:
                        # If an survey for this constraint has not been
                        # submitted, we don't care about checking the others;
                        # we should just return None to indicate this constraint
                        # has not been satisfied.
                        completed_time = None
                        break

        # So we have 3 possible cases: Returning 0 if there are no
        # surveys on this constraint for some reason or if the user
        # is an instructor or course editor or admin, returning
        # the satisfied time if all surveys have been submitted,
        # and returning None if some surveys have not yet been
        # submitted.
        #
        # The time at which this constraint is satisfied is the most
        # recent time at which all surveys have been submitted
        # initially by the student, according to createdTime of
        # each submission.
        return completed_time

    def is_satisfied(self, constraint=None, principal=None):
        user = get_user(principal)
        if user is None:
            return False
        constraint = self.constraint if constraint is None else constraint
        course = ICourseInstance(constraint, None)
        if course is None:
            return False
        # always allow editors and instructors
        if     is_course_instructor_or_editor(course, user) \
                or has_permission(ACT_CONTENT_EDIT, course):
            return True
        now = datetime.utcnow()
        for survey_ntiid in constraint.surveys:
            survey = component.queryUtility(IQSurvey, name=survey_ntiid)
            if survey is None:
                continue
            due_date = get_available_for_submission_ending(survey, course) \
                or now
            if due_date >= now and not has_submitted_inquiry(course, user, survey):
                return False
        return True


@component.adapter(INTILessonOverview)
@interface.implementer(ICalendarPublishablePredicate)
class LessonPublishablePredicate(object):

    __slots__ = ()

    def __init__(self, *args):
        pass

    def is_published(self, lesson, principal=None, *args, **kwargs):
        constraints = constraints_for_lesson(lesson, False)
        if constraints is not None:
            for constraint in constraints.Items:
                checker = ILessonPublicationConstraintChecker(constraint, None)
                if      checker is not None \
                        and not checker.is_satisfied(constraint, principal):
                    return False
        return True
