#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import none
from hamcrest import is_not
from hamcrest import has_length
from hamcrest import assert_that

import os

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
from nti.contenttypes.presentation.utils import create_timelime_from_external
from nti.contenttypes.presentation.utils import create_ntivideo_from_external
from nti.contenttypes.presentation.utils import create_relatedwork_from_external

from nti.app.contenttypes.presentation import get_catalog
from nti.app.contenttypes.presentation.subscribers import iface_of_thing
from nti.app.contenttypes.presentation.subscribers import _remove_from_registry
from nti.app.contenttypes.presentation.subscribers import _index_overview_items
from nti.app.contenttypes.presentation.subscribers import _load_and_register_json
from nti.app.contenttypes.presentation.subscribers import _load_and_register_slidedeck_json
from nti.app.contenttypes.presentation.subscribers import _load_and_register_lesson_overview_json

from nti.app.contenttypes.presentation.tests import PersistentComponents

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans
import nti.dataserver.tests.mock_dataserver as mock_dataserver

def _index_items(item_iface, namespace, *registered):
	catalog = get_catalog()
	intids = component.queryUtility(IIntIds)
	for item in registered:
		catalog.index(item, intids=intids, namespace=namespace, provided=item_iface)

class TestSubscribers(ApplicationLayerTest):

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
		
		result = _remove_from_registry(namespace='xxx', provided=iface, registry=registry)
		assert_that(result, has_length(count))

	@WithMockDSTrans
	def test_video_index(self):
		self._test_feed('video_index.json', INTIVideo, 94,
						create_ntivideo_from_external)

	@WithMockDSTrans
	def test_timeline_index(self):
		self._test_feed('timeline_index.json', INTITimeline, 11,
						create_timelime_from_external)

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
		
		result = _remove_from_registry(namespace='xxx', provided=INTISlideDeck, registry=registry)
		assert_that(result, has_length(57))
		
		result = _remove_from_registry(namespace='xxx', provided=INTISlideVideo, registry=registry)
		assert_that(result, has_length(57))
		
		result = _remove_from_registry(namespace='xxx', provided=INTISlide, registry=registry)
		assert_that(result, has_length(628))

	@WithMockDSTrans
	def test_lessong_overview(self):
		path = os.path.join(os.path.dirname(__file__), 'lesson_overview.json')
		with open(path, "r") as fp:
			source = fp.read()
			
		registry = PersistentComponents()
		mock_dataserver.current_transaction.add(registry)

		result = _load_and_register_lesson_overview_json(source, registry=registry)
		assert_that(result, is_not(none()))
		
		_index_overview_items((result,), containers='xxx')
		
		result = _remove_from_registry(containers='xxx', provided=INTICourseOverviewGroup, registry=registry)
		assert_that(result, has_length(4))
		
		result = _remove_from_registry(containers='xxx', provided=INTILessonOverview, registry=registry)
		assert_that(result, has_length(1))
