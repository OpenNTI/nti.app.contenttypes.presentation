#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
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

from nti.app.contenttypes.presentation.interfaces import ILessonPublicationConstraintChecker

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

from nti.coremetadata.interfaces import ICalendarPublishablePredicate

from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import ISystemUserPrincipal

from nti.dataserver.users.users import User

from nti.metadata.predicates import BasePrincipalObjects

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


@component.adapter(IAssignmentCompletionConstraint)
@interface.implementer(ILessonPublicationConstraintChecker)
class AssignmentCompletionConstraintChecker(object):

    constraint = None

    def __init__(self, constraint=None):
        self.constraint = constraint

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
            assignment = component.queryUtility(
                IQAssignment, name=assignment_ntiid)
            if assignment is None:
                continue
            if not has_submitted_assigment(course, user, assignment):
                return False
        return True


@component.adapter(ISurveyCompletionConstraint)
@interface.implementer(ILessonPublicationConstraintChecker)
class SurveyCompletionConstraintChecker(object):

    constraint = None

    def __init__(self, constraint=None):
        self.constraint = constraint

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
            due_date = get_available_for_submission_ending(survey, course) or now
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
