#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os

from zope import interface

from zope.component.hooks import site as current_site

from nti.app.contenttypes.presentation.utils.asset import check_related_work_target

from nti.app.contenttypes.presentation.synchronizer import clear_course_assets
from nti.app.contenttypes.presentation.synchronizer import clear_namespace_last_modified
from nti.app.contenttypes.presentation.synchronizer import remove_and_unindex_course_assets
from nti.app.contenttypes.presentation.synchronizer import synchronize_course_lesson_overview

from nti.app.products.courseware.resources.utils import get_course_filer

from nti.app.products.courseware.utils.importer import transfer_resources_from_filer

from nti.cabinet.filer import transfer_to_native_file

from nti.contentlibrary.interfaces import IFilesystemBucket

from nti.contenttypes.courses.common import get_course_site

from nti.contenttypes.courses.importer import BaseSectionImporter

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseSectionImporter

from nti.contenttypes.courses.utils import get_parent_course
from nti.contenttypes.courses.utils import get_course_subinstances

from nti.contenttypes.presentation import iface_of_asset

from nti.contenttypes.presentation.interfaces import IItemAssetContainer

from nti.site.hostpolicy import get_host_site

from nti.site.site import get_component_hierarchy_names

@interface.implementer(ICourseSectionImporter)
class LessonOverviewsImporter(BaseSectionImporter):

	__LESSONS__ = 'Lessons'

	def _post_process_asset(self, asset, source_filer, target_filer):
		# save asset resources
		provided = iface_of_asset(asset)
		transfer_resources_from_filer(provided, asset, source_filer, target_filer)
		# check 'children'
		if IItemAssetContainer.providedBy(asset):
			asset_items = asset.Items if asset.Items is not None else ()
			for item in asset_items:
				self._post_process_asset(item, source_filer, target_filer)
		check_related_work_target(asset)

	def _get_course_site(self, course):
		site_name = get_course_site(course)
		site = get_host_site(site_name)
		return site

	def _do_import(self, context, source_filer, save_sources=True):
		course = ICourseInstance(context)
		entry = ICourseCatalogEntry(course)
		site = self._get_course_site(course)
		target_filer = get_course_filer(course)
		named_sites = get_component_hierarchy_names()

		if source_filer.is_bucket(self.__LESSONS__):
			bucket = source_filer.get(self.__LESSONS__)
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

			# save sources in main course Lessos folder
			parent = get_parent_course(course)
			root = parent.root
			if save_sources and IFilesystemBucket.providedBy(root):
				out_path = os.path.join(root.absolute_path, self.__LESSONS__)
				self.makedirs(out_path) # create
				for path in source_filer.list(self.__LESSONS__):
					if not source_filer.is_bucket(path):
						source = source_filer.get(path)
						name = source_filer.key_name(path)
						new_path = os.path.join(out_path, name)
						transfer_to_native_file(source, new_path)
			return lessons

		return ()

	def process(self, context, filer, writeout=True):
		result = []
		course = ICourseInstance(context)
		result.extend(self._do_import(context, filer, writeout))
		for sub_instance in get_course_subinstances(course):
			if sub_instance.Outline is not course.Outline:
				result.extend(self._do_import(sub_instance, filer, writeout))
		return tuple(result)
