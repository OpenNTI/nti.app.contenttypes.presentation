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

from nti.app.assessment.common import get_user
from nti.app.assessment.common import get_available_for_submission_ending

from nti.app.assessment.interfaces import IUsersCourseInquiry
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
class LessonPublicationConstraintChecker(object):

    constraint = None

    def __init__(self, constraint=None):
        self.constraint = constraint

    def satisfied_time(self, user, constraint=None):
        user = get_user(user)
        constraint = self.constraint if constraint is None else constraint
        course = ICourseInstance(constraint, None) # lineage
        # By default, unless we have relevant completed constraints,
        # we return 0.
        completed_time = 0
        # Don't run through this for instructors or editors.
        if not (   is_course_instructor_or_editor(course, user)
                or has_permission(ACT_CONTENT_EDIT, course)):
            # check all item constraints
            for item in self.get_constraint_items(constraint) or ():
                if completed_time != 0:
                    ct_item = self.check_time_constraint_item(item, user, constraint)
                    completed_time = max(ct_item, completed_time)
                else:
                    # Make sure to assign completed_time the first trip
                    # through the loop
                    completed_time = self.check_time_constraint_item(item, user, constraint)
                if completed_time is None:
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
            submission = histories.get(item_ntiid, None)
            if submission is not None:
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

    def is_published(self, lesson, principal=None, *args, **kwargs):
        constraints = constraints_for_lesson(lesson, False)
        if constraints is not None:
            for constraint in constraints.Items:
                checker = ILessonPublicationConstraintChecker(constraint, None)
                if      checker is not None \
                    and not checker.is_satisfied(principal, constraint):
                    return False
        return True
