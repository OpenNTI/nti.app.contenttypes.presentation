#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from nti.app.products.courseware.utils.exporter import save_resources_to_filer

from nti.common.file import safe_filename

from nti.contenttypes.courses.exporter import BaseSectionExporter

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSectionExporter

from nti.contenttypes.courses.utils import get_course_subinstances

from nti.contenttypes.presentation import iface_of_asset

from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import IItemAssetContainer

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import StandardInternalFields

from nti.ntiids.ntiids import TYPE_OID
from nti.ntiids.ntiids import is_ntiid_of_type
from nti.ntiids.ntiids import is_valid_ntiid_string
from nti.ntiids.ntiids import find_object_with_ntiid

OID = StandardExternalFields.OID
ITEMS = StandardExternalFields.ITEMS
NTIID = StandardExternalFields.NTIID
CONTAINER_ID = StandardExternalFields.CONTAINER_ID
INTERNAL_CONTAINER_ID = StandardInternalFields.CONTAINER_ID

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
	return tuple(result)

@interface.implementer(ICourseSectionExporter)
class LessonOverviewsExporter(BaseSectionExporter):

	def _post_process_asset(self, asset, ext_obj, filer):
		ext_obj.pop(OID, None)
		ext_obj.pop(CONTAINER_ID, None)
		
		# save asset resources
		provided = iface_of_asset(asset)
		save_resources_to_filer(provided, asset, filer, ext_obj)

		# check 'children'
		if IItemAssetContainer.providedBy(asset):
			if INTISlideDeck.providedBy(asset):
				for name in ('Videos', 'Slides'):
					ext_items = ext_obj.get(name) or ()
					deck_items = getattr(asset, name, None) or ()
					for item, item_ext in zip(deck_items, ext_items):
						self._post_process_asset(item, item_ext, filer)
			else:
				ext_items = ext_obj.get(ITEMS) or ()
				asset_items = asset.Items if asset.Items is not None else ()
				for item, item_ext in zip(asset_items, ext_items):
					self._post_process_asset(item, item_ext, filer)
		
		# don't leak internal OIDs
		for name in (NTIID, NTIID.lower(), INTERNAL_CONTAINER_ID, 'target'):
			value = ext_obj.get(name)
			if 		value \
				and	is_valid_ntiid_string(value) \
				and is_ntiid_of_type(value, TYPE_OID):
				ext_obj.pop(name, None)

	def _do_export(self, context, filer, seen):
		course = ICourseInstance(context)
		nodes = _outline_nodes(course.Outline, seen)
		for node, lesson in nodes:
			ext_obj = to_external_object(lesson, name="exporter", decorate=False)
			# process internal resources
			self._post_process_asset(lesson, ext_obj, filer)
			# save to json
			source = self.dump(ext_obj)
			# save to filer
			name = safe_filename(node.src or lesson.ntiid)
			name = name + '.json' if not name.endswith('.json') else name
			filer.save(name, source, overwrite=True,
					   bucket="Lessons", contentType=u"application/x-json")

	def export(self, context, filer):
		seen = set()
		course = ICourseInstance(context)
		self._do_export(context, filer, seen)
		for sub_instance in get_course_subinstances(course):
			if sub_instance.Outline is not course.Outline:
				self._do_export(sub_instance, filer, seen)
