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

from zope.container.contained import Contained

from zope.security.interfaces import IPrincipal

from nti.app.products.courseware.utils import get_any_enrollment
from nti.app.products.courseware.utils import is_course_instructor

from nti.contenttypes.courses.interfaces import ES_ALL
from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecord

from nti.coremetadata.mixins import CreatedAndModifiedTimeMixin

from nti.ntiids.ntiids import find_object_with_ntiid

from .. import get_catalog

@interface.implementer(ICourseInstanceEnrollmentRecord)
class ProxyEnrollmentRecord(CreatedAndModifiedTimeMixin, Contained):
	Scope = None
	Principal = None
	CourseInstance = None

	def __init__(self, course=None, principal=None, scope=None):
		self.Scope = scope
		self.Principal = principal
		self.CourseInstance = course

def get_enrollment_record(context, user):
	course = ICourseInstance(context, None)
	if is_course_instructor(course, user):
		# create a fake enrollment record w/ all scopes to signal an instructor
		result = ProxyEnrollmentRecord(course, IPrincipal(user), ES_ALL)
	else:
		result = get_any_enrollment(course, user) if course is not None else None
	return result

def get_courses(ntiids=()):
	result = []
	catalog = component.getUtility(ICourseCatalog)
	for ntiid in ntiids or ():
		course = None
		context = find_object_with_ntiid(ntiid)
		if ICourseCatalogEntry.providedBy(context):
			course = ICourseInstance(context, None)
		elif ICourseInstance.providedBy(context):
			course = context
		elif context is None:
			try:
				entry = catalog.getCatalogEntry(ntiid)
				course = ICourseInstance(entry, None)
			except KeyError:
				pass
		if course is not None:
			result.append(course)
	return result

def get_presentation_asset_courses(item, sort=False):
	catalog = get_catalog()
	entries = catalog.get_containers(item)
	result = get_courses(entries) if entries else ()
	return result
