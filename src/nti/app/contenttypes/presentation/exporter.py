#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import re
from StringIO import StringIO

import simplejson

from zope import interface

from nti.app.products.courseware.utils.exporter import save_resources_to_filer

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSectionExporter

from nti.contenttypes.courses.utils import get_course_subinstances

from nti.contenttypes.presentation import iface_of_asset

from nti.contenttypes.presentation.interfaces import IItemAssetContainer

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import StandardExternalFields

from nti.ntiids.ntiids import find_object_with_ntiid

ITEMS = StandardExternalFields.ITEMS

def _outline_nodes(outline, seen):
	result = []
	def _recur(node):
		ntiid = node.LessonOverviewNTIID
		if ntiid and ntiid not in seen:
			seen.add(ntiid)
			lesson = find_object_with_ntiid(ntiid)
			if lesson is not None:
				result.append((node, lesson))
		# parse children
		for child in node.values():
			_recur(child)
	if outline is not None:
		_recur(outline)
	return result

def safe_filename(s):
	return re.sub(r'[/<>:"\\|?*]+', '_', s) if s else s

@interface.implementer(ICourseSectionExporter)
class LessonOverviewsExporer(object):

	def _process_asset_resources(self, asset, ext_obj, filer):
		# save asset resources
		provided = iface_of_asset(asset)
		save_resources_to_filer(provided, asset, filer, ext_obj)
		# check 'children'
		if IItemAssetContainer.providedBy(asset):
			ext_items = ext_obj.get(ITEMS) or ()
			asset_items = asset.Items if asset.Items is not None else ()
			for item, item_ext in zip(asset_items, ext_items):
				self._process_asset_resources(item, item_ext, filer)

	def _do_export(self, context, filer, seen):
		course = ICourseInstance(context)
		nodes = _outline_nodes(course.Outline, seen)
		for node, lesson in nodes:
			ext_obj = to_external_object(lesson, name="exporter", decorate=False)
			# process internal resources 
			self._process_asset_resources(lesson, ext_obj, filer)
			# save to json
			source = StringIO()
			simplejson.dump(ext_obj, source, indent=4)
			source.seek(0)
			# save to filer
			name = safe_filename(node.src or lesson.ntiid)
			name = name + '.json' if not name.endswith('.json') else name
			filer.save(name, source, overwrite=True, contentType=u"text/x-json")

	def export(self, context, filer):
		seen = set()
		course = ICourseInstance(context)
		self._do_export(context, filer, seen)
		for sub_instance in get_course_subinstances(course):
			if sub_instance.Outline is not course.Outline:
				self._do_export(sub_instance, filer, seen)
