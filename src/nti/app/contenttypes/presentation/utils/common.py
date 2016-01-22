#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance

from nti.contenttypes.courses.utils import get_course_subinstances

from nti.ntiids.ntiids import find_object_with_ntiid

def yield_sync_courses(ntiids=()):
	catalog = component.getUtility(ICourseCatalog)
	if not ntiids:
		for entry in catalog.iterCatalogEntries():
			course = ICourseInstance(entry, None)
			if 		course is None \
				or	ILegacyCourseInstance.providedBy(course) \
				or	ICourseSubInstance.providedBy(course):
				continue
			yield course
			for subinstance in get_course_subinstances(course):
				yield subinstance
	else:
		for ntiid in ntiids:
			obj = find_object_with_ntiid(ntiid)
			course = ICourseInstance(obj, None)
			if course is None or ILegacyCourseInstance.providedBy(course):
				logger.error("Could not find course with NTIID %s", ntiid)
			else:
				yield course
