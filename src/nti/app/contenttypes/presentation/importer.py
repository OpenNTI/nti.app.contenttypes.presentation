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

from plone.namedfile.interfaces import INamed as IPloneNamed

from nti.app.contenttypes.presentation.synchronizer import clear_course_assets
from nti.app.contenttypes.presentation.synchronizer import clear_namespace_last_modified
from nti.app.contenttypes.presentation.synchronizer import remove_and_unindex_course_assets
from nti.app.contenttypes.presentation.synchronizer import synchronize_course_lesson_overview

from nti.app.products.courseware.resources.utils import get_course_filer
from nti.app.products.courseware.resources.utils import is_internal_file_link
from nti.app.products.courseware.resources.utils import get_file_from_external_link

from nti.app.products.courseware.utils.importer import transfer_resources_from_filer

from nti.contenttypes.courses.importer import BaseSectionImporter

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseSectionImporter

from nti.contenttypes.courses.utils import get_course_subinstances

from nti.contenttypes.presentation import iface_of_asset

from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import IItemAssetContainer

from nti.externalization.oids import to_external_ntiid_oid

from nti.ntiids.ntiids import is_valid_ntiid_string

from nti.site.hostpolicy import get_host_site

from nti.site.interfaces import IHostPolicyFolder

from nti.site.site import get_component_hierarchy_names

from nti.traversal.traversal import find_interface

@interface.implementer(ICourseSectionImporter)
class LessonOverviewsImporter(BaseSectionImporter):

	def _post_process_asset(self, asset, source_filer, target_filer):
		# save asset resources
		provided = iface_of_asset(asset)
		transfer_resources_from_filer(provided, asset, source_filer, target_filer)
		# check 'children'
		if IItemAssetContainer.providedBy(asset):
			asset_items = asset.Items if asset.Items is not None else ()
			for item in asset_items:
				self._post_process_asset(item, source_filer, target_filer)
		# check related work target
		if INTIRelatedWorkRef.providedBy(asset) and not asset.target:
			href = asset.href
			if IPloneNamed.providedBy(href):
				asset.target = to_external_ntiid_oid(href)
			elif is_valid_ntiid_string(href):
				asset.target = href
			elif is_internal_file_link(href):
				ext = get_file_from_external_link(href)
				asset.target = to_external_ntiid_oid(ext)

	def _get_course_site(self, course):
		site_name = find_interface(course, IHostPolicyFolder, strict=False).__name__
		site = get_host_site(site_name)
		return site

	def _do_import(self, context, source_filer):
		course = ICourseInstance(context)
		entry = ICourseCatalogEntry(course)
		site = self._get_course_site(course)
		target_filer = get_course_filer(course)
		named_sites = get_component_hierarchy_names()
		if source_filer.is_bucket("Lessons"):
			bucket = source_filer.get("Lessons")
			with current_site(site):
				registry = site.getSiteManager()
				# clear assets - not merging
				clear_course_assets(course)  
				clear_namespace_last_modified(course)
				remove_and_unindex_course_assets(namespace=entry.ntiid,
										  		 registry=registry,
										  		 course=course,
										 		 sites=named_sites,
										 		 force=True)  # not merging
				# load assets
				lessons = synchronize_course_lesson_overview(course, buckets=(bucket,))
				for lesson in lessons or ():
					self._post_process_asset(lesson, source_filer, target_filer)
				return lessons
		return ()

	def process(self, context, filer):
		result = []
		course = ICourseInstance(context)
		result.extend(self._do_import(context, filer))
		for sub_instance in get_course_subinstances(course):
			if sub_instance.Outline is not course.Outline:
				result.extend(self._do_import(sub_instance, filer))
		return tuple(result)
