#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import has_length
from hamcrest import assert_that

import os
import unittest

from zope.interface.registry import Components

from nti.contenttypes.presentation.interfaces import INTISlide
from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTISlideVideo
from nti.contenttypes.presentation.interfaces import INTIRelatedWork
from nti.contenttypes.presentation.interfaces import IGroupOverViewable
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup

from nti.contenttypes.presentation.utils import create_object_from_external
from nti.contenttypes.presentation.utils import create_ntivideo_from_external
from nti.contenttypes.presentation.utils import create_relatedwork_from_external

from nti.app.contenttypes.presentation.subscribers import _load_and_register_json
from nti.app.contenttypes.presentation.subscribers import _load_and_register_slidedeck_json
from nti.app.contenttypes.presentation.subscribers import _remove_from_registry_with_interface
from nti.app.contenttypes.presentation.subscribers import _load_and_register_lesson_overview_json

from nti.app.contenttypes.presentation.tests import SharedConfiguringTestLayer

class TestSubscribers(unittest.TestCase):

	layer = SharedConfiguringTestLayer

	def _set_item_pkg_ntiid(self, result):
		for item in result:
			item._parent_ntiid_ = 'xxx'

	def _test_feed(self, source, iface, count, object_creator=create_object_from_external):
		path = os.path.join(os.path.dirname(__file__), source)
		with open(path, "r") as fp:
			source = fp.read()
			
		registry = Components()
		result = _load_and_register_json(iface, source, registry=registry,
										 external_object_creator=object_creator)
		assert_that(result, has_length(count))
		assert_that(list(registry.registeredUtilities()), has_length(count))

		self._set_item_pkg_ntiid(result)
		
		result = _remove_from_registry_with_interface('xxx', iface, registry=registry)
		assert_that(result, has_length(count))

	def test_video_index(self):
		self._test_feed('video_index.json', INTIVideo, 94,
						create_ntivideo_from_external)

	def test_timeline_index(self):
		self._test_feed('timeline_index.json', INTITimeline, 11)

	def test_related_content_index(self):
		self._test_feed('related_content_index.json', INTIRelatedWork, 372,
						create_relatedwork_from_external)
	
	def test_slidedeck_index(self):
		path = os.path.join(os.path.dirname(__file__), 'slidedeck_index.json')
		with open(path, "r") as fp:
			source = fp.read()
			
		registry = Components()
		result = _load_and_register_slidedeck_json(source, registry=registry)
		assert_that(result, has_length(742))

		self._set_item_pkg_ntiid(result)
		
		result = _remove_from_registry_with_interface('xxx', INTISlideDeck, registry=registry)
		assert_that(result, has_length(57))
		
		result = _remove_from_registry_with_interface('xxx', INTISlideVideo, registry=registry)
		assert_that(result, has_length(57))
		
		result = _remove_from_registry_with_interface('xxx', INTISlide, registry=registry)
		assert_that(result, has_length(628))

	def test_lessong_overview(self):
		path = os.path.join(os.path.dirname(__file__), 'lesson_overview.json')
		with open(path, "r") as fp:
			source = fp.read()
			
		registry = Components()
		result = _load_and_register_lesson_overview_json(source, registry=registry)
		assert_that(result, has_length(11))

		self._set_item_pkg_ntiid(result)
		
		result = _remove_from_registry_with_interface('xxx', IGroupOverViewable, registry=registry)
		assert_that(result, has_length(6))
		
		result = _remove_from_registry_with_interface('xxx', INTICourseOverviewGroup, registry=registry)
		assert_that(result, has_length(4))
		
		result = _remove_from_registry_with_interface('xxx', INTILessonOverview, registry=registry)
		assert_that(result, has_length(1))
