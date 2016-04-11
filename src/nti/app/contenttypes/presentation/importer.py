#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from zope.component.hooks import site as current_site

from nti.app.contenttypes.presentation.synchronizer import clear_course_assets
from nti.app.contenttypes.presentation.synchronizer import remove_and_unindex_course_assets
from nti.app.contenttypes.presentation.synchronizer import synchronize_course_lesson_overview

from nti.app.products.courseware.utils.importer import transfer_resources_from_filer

from nti.contenttypes.courses.importer import BaseSectionImporter

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseSectionImporter

from nti.contenttypes.courses.utils import get_course_subinstances

from nti.contenttypes.presentation import iface_of_asset

from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef

from nti.site.hostpolicy import get_host_site

from nti.site.interfaces import IHostPolicyFolder

from nti.site.site import get_component_hierarchy_names

from nti.traversal.traversal import find_interface

@interface.implementer(ICourseSectionImporter)
class LessonOverviewsImporter(BaseSectionImporter):

	def _post_process_asset(self, asset, ext_obj, filer):
		# save asset resources
		provided = iface_of_asset(asset)
		transfer_resources_from_filer(provided, asset, filer, ext_obj)
		# check related work
		if 		INTIRelatedWorkRef.providedBy(asset):
			ext_obj['target'] = None # don't leak internal OIDs

	def _get_course_site(self, course):
		site_name = find_interface(course, IHostPolicyFolder, strict=False).__name__
		site = get_host_site(site_name)
		return site

	def _do_import(self, context, source_filer):
		course = ICourseInstance(context)
		entry = ICourseCatalogEntry(course)
		site = self._get_course_site(course)
		named_sites = get_component_hierarchy_names()
		if source_filer.is_bucket("Lessons"):
			bucket = source_filer.get("Lessons")
			with current_site(site):
				registry = site.getSiteManager()
				# clear assets
				clear_course_assets(course) # not merging
				remove_and_unindex_course_assets(namespace=entry.ntiid,
										  		 registry=registry, 
										  		 course=course,
										 		 sites=named_sites, 
										 		 force=True) # not merging
				# load assets
				synchronize_course_lesson_overview(course, buckets=(bucket,))

	def process(self, context, filer):
		course = ICourseInstance(context)
		self._do_import(context, filer)
		for sub_instance in get_course_subinstances(course):
			if sub_instance.Outline is not course.Outline:
				self._do_import(sub_instance, filer)
