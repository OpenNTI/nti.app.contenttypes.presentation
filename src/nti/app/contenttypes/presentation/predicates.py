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

from nti.app.assessment.common import has_submitted_assigment
from nti.app.assessment.common import get_available_for_submission_ending

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation import ALL_PRESENTATION_ASSETS_INTERFACES

from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import ILessonPublicationConstraints

from nti.assessment.interfaces import IQAssignment

from nti.coremetadata.interfaces import ICalendarPublishablePredicate

from nti.dataserver.interfaces import ISystemUserPrincipal

from nti.dataserver.users.users import User

from nti.metadata.predicates import BasePrincipalObjects

from nti.site.hostpolicy import get_all_host_sites

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

@component.adapter(INTILessonOverview)
@interface.implementer(ICalendarPublishablePredicate)
class LessonPublishablePredicate(object):

	__slots__ = ()

	def is_published(self, lesson, principal=None, *args, **kwargs):
		constraints = ILessonPublicationConstraints(lesson).Items
		user = User.get_user(principal.id) if principal is not None else None
		if not user:
			return False
		for constraint in constraints:
			if not self.is_satisfied(constraint, lesson, user):
				return False
		return True

	def is_satisfied(self, constraint, lesson, user):
		now = datetime.utcnow()
		course = ICourseInstance(lesson, None)
		if course is None:
			return False
		for assignment_ntiid in constraint.assignments:
			assignment = component.queryUtility(IQAssignment, name=assignment_ntiid)
			if assignment is None:
				continue
			due_date = get_available_for_submission_ending(assignment, course)
			if now > due_date:
				return False
			if has_submitted_assigment(course, user, assignment):
				return False
		return True
