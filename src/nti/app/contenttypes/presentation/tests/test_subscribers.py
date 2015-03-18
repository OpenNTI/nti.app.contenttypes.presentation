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

from zope import component
from zope.intid import IIntIds

from nti.contenttypes.presentation.interfaces import INTISlide
from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTISlideVideo
from nti.contenttypes.presentation.interfaces import INTIRelatedWork
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup

from nti.contenttypes.presentation.utils import create_object_from_external
from nti.contenttypes.presentation.utils import create_ntivideo_from_external
from nti.contenttypes.presentation.utils import create_relatedwork_from_external

from nti.app.contenttypes.presentation.subscribers import index_item
from nti.app.contenttypes.presentation.subscribers import iface_of_thing
from nti.app.contenttypes.presentation.subscribers import _load_and_register_json
from nti.app.contenttypes.presentation.subscribers import _load_and_register_slidedeck_json
from nti.app.contenttypes.presentation.subscribers import _remove_from_registry_with_interface
from nti.app.contenttypes.presentation.subscribers import _load_and_register_lesson_overview_json

from nti.app.contenttypes.presentation.tests import PersistentComponents
from nti.app.contenttypes.presentation.tests import SharedConfiguringTestLayer

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans
import nti.dataserver.tests.mock_dataserver as mock_dataserver

def _index_items(item_iface, parents=(), *registered):
	intids = component.queryUtility(IIntIds)
	if intids is not None:
		for item in registered:
			docid = intids.getId(item)
			index_item(docid, item_iface, parents=parents)

class TestSubscribers(unittest.TestCase):

	layer = SharedConfiguringTestLayer

	def _test_feed(self, source, iface, count, object_creator=create_object_from_external):
		path = os.path.join(os.path.dirname(__file__), source)
		with open(path, "r") as fp:
			source = fp.read()
			
		registry = PersistentComponents()
		mock_dataserver.current_transaction.add(registry)

		result = _load_and_register_json(iface, source, registry=registry,
										 external_object_creator=object_creator)
		assert_that(result, has_length(count))
		assert_that(list(registry.registeredUtilities()), has_length(count))

		_index_items(iface, 'xxx', *result)
		
		result = _remove_from_registry_with_interface('xxx', iface, registry=registry)
		assert_that(result, has_length(count))

	@WithMockDSTrans
	def test_video_index(self):
		self._test_feed('video_index.json', INTIVideo, 94,
						create_ntivideo_from_external)

	@WithMockDSTrans
	def test_timeline_index(self):
		self._test_feed('timeline_index.json', INTITimeline, 11)

	@WithMockDSTrans
	def test_related_content_index(self):
		self._test_feed('related_content_index.json', INTIRelatedWork, 372,
						create_relatedwork_from_external)
	
	@WithMockDSTrans
	def test_slidedeck_index(self):
		path = os.path.join(os.path.dirname(__file__), 'slidedeck_index.json')
		with open(path, "r") as fp:
			source = fp.read()
			
		registry = PersistentComponents()
		mock_dataserver.current_transaction.add(registry)
		
		result = _load_and_register_slidedeck_json(source, registry=registry)
		assert_that(result, has_length(742))
		
		for item in result:
			iface = iface_of_thing(item)
			_index_items(iface, 'xxx', item)
		
		result = _remove_from_registry_with_interface('xxx', INTISlideDeck, registry=registry)
		assert_that(result, has_length(57))
		
		result = _remove_from_registry_with_interface('xxx', INTISlideVideo, registry=registry)
		assert_that(result, has_length(57))
		
		result = _remove_from_registry_with_interface('xxx', INTISlide, registry=registry)
		assert_that(result, has_length(628))

	@WithMockDSTrans
	def test_lessong_overview(self):
		path = os.path.join(os.path.dirname(__file__), 'lesson_overview.json')
		with open(path, "r") as fp:
			source = fp.read()
			
		registry = PersistentComponents()
		mock_dataserver.current_transaction.add(registry)

		result = _load_and_register_lesson_overview_json(source, registry=registry)
		assert_that(result, has_length(11))

		for item in result:
			iface = iface_of_thing(item)
			_index_items(iface, 'xxx', item)
		
		result = _remove_from_registry_with_interface('xxx', INTICourseOverviewGroup, registry=registry)
		assert_that(result, has_length(4))
		
		result = _remove_from_registry_with_interface('xxx', INTILessonOverview, registry=registry)
		assert_that(result, has_length(1))
