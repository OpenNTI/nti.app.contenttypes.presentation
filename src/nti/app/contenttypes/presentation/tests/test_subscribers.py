#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import has_length
from hamcrest import assert_that

import os
import fudge
import unittest

from zope.interface.registry import Components

from nti.contenttypes.presentation.interfaces import INTISlide
from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTIRelatedWork

from nti.app.contenttypes.presentation.subscribers import _load_and_register_json
from nti.app.contenttypes.presentation.subscribers import _load_and_register_slidedeck_json
from nti.app.contenttypes.presentation.subscribers import _remove_from_registry_with_interface

from nti.app.contenttypes.presentation.tests import SharedConfiguringTestLayer

class TestSubscribers(unittest.TestCase):

	layer = SharedConfiguringTestLayer

	def _set_item_pkg_ntiid(self, result):
		for item in result:
			item.content_package_ntiid = 'xxx'

	def _test_feed(self, source, iface, count):
		path = os.path.join(os.path.dirname(__file__), source)
		with open(path, "r") as fp:
			source = fp.read()
			
		registry = Components()
		result = _load_and_register_json(iface, source, registry=registry)
		assert_that(result, has_length(count))
		assert_that(list(registry.registeredUtilities()), has_length(count))

		self._set_item_pkg_ntiid(result)
		
		package = fudge.Fake().has_attr(ntiid='xxx')
		result = _remove_from_registry_with_interface(package, iface, registry=registry)
		assert_that(result, has_length(count))

	def test_video_index(self):
		self._test_feed('video_index.json', INTIVideo, 94)

	def test_timeline_index(self):
		self._test_feed('timeline_index.json', INTITimeline, 11)

	def test_related_content_index(self):
		self._test_feed('related_content_index.json', INTIRelatedWork, 372)
	
	def test_slidedeck_index(self):
		path = os.path.join(os.path.dirname(__file__), 'slidedeck_index.json')
		with open(path, "r") as fp:
			source = fp.read()
			
		registry = Components()
		result = _load_and_register_slidedeck_json(source, registry=registry)
		assert_that(result, has_length(1079))

		self._set_item_pkg_ntiid(result)
		
		package = fudge.Fake().has_attr(ntiid='xxx')
		result = _remove_from_registry_with_interface(package, INTISlideDeck, registry=registry)
		assert_that(result, has_length(57))
		
		result = _remove_from_registry_with_interface(package, INTISlide, registry=registry)
		assert_that(result, has_length(234))
