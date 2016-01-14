# #!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os
from itertools import chain

from zope import component
from zope import interface

from zope.container.contained import Contained

from zope.security.interfaces import IPrincipal

from nti.contentlibrary.interfaces import IContentUnit
from nti.contentlibrary.indexed_data import get_catalog

from nti.contenttypes.courses.interfaces import ES_ALL
from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecord

from nti.contenttypes.courses.utils import is_course_editor
from nti.contenttypes.courses.utils import get_parent_course 
from nti.contenttypes.courses.utils import get_any_enrollment
from nti.contenttypes.courses.utils import get_course_packages
from nti.contenttypes.courses.utils import is_course_instructor

from nti.coremetadata.mixins import CreatedAndModifiedTimeMixin

from nti.ntiids.ntiids import find_object_with_ntiid

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
	course = ICourseInstance(context, None)  # e.g. course in lineage
	if course is None:
		return None

	main_course = get_parent_course(course)

	# give priority to course in lineage before checking the rest
	for instance in chain((course, main_course), main_course.SubInstances.values()):
		if is_course_instructor(instance, user) or is_course_editor(instance, user):
			# create a fake enrollment record w/ all scopes to signal an instructor
			return ProxyEnrollmentRecord(course, IPrincipal(user), ES_ALL)

	result = get_any_enrollment(course, user) if course is not None else None
	return result

def get_courses_for_pacakge(ntiid):
	result = []
	catalog = component.getUtility(ICourseCatalog)
	for entry in catalog.iterCatalogEntries():
		course = ICourseInstance(entry, None)
		packs = get_course_packages(course)	
		for pack in packs or ():
			if pack.ntiid == ntiid:
				result.append(course)
	return result

def get_containers(ntiids=()):
	result = []
	for ntiid in ntiids or ():
		context = find_object_with_ntiid(ntiid)
		if ICourseCatalogEntry.providedBy(context):
			context = ICourseInstance(context, None)
		if context is not None:
			result.append(context)
	return result

def get_courses(ntiids=()):
	result = set()
	for ntiid in ntiids or ():
		course = None
		context = find_object_with_ntiid(ntiid)
		if ICourseCatalogEntry.providedBy(context):
			course = ICourseInstance(context, None)
		elif ICourseInstance.providedBy(context):
			course = context
		elif not IContentUnit.providedBy(context): # ignore content units
			course = ICourseInstance(context, None)
		if course is not None:
			result.add(course)
	return result

def get_presentation_asset_courses(item, sort=False):
	catalog = get_catalog()
	entries = catalog.get_containers(item)
	result = get_courses(entries) if entries else ()
	return result

def get_presentation_asset_containers(item):
	catalog = get_catalog()
	entries = catalog.get_containers(item)
	result = get_containers(entries) if entries else ()
	return result

def get_entry_by_relative_path_parts(*parts):
	original = os.path.sep.join(parts)
	transformed = os.path.sep.join([x.replace('_', ' ') for x in parts])
	catalog = component.getUtility(ICourseCatalog)
	for entry in catalog.iterCatalogEntries():
		relative_path = getattr(entry, 'relative_path', None)
		if relative_path == original or relative_path == transformed:
			return entry
	return None

def get_course_by_relative_path_parts(*parts):
	result = ICourseInstance(get_entry_by_relative_path_parts(*parts), None)
	return result
