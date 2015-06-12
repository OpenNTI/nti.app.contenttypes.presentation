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

from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup

from nti.app.contenttypes.presentation.subscribers import _remove_from_registry
from nti.app.contenttypes.presentation.subscribers import _index_overview_items
from nti.app.contenttypes.presentation.subscribers import _load_and_register_lesson_overview_json

from nti.app.contenttypes.presentation.tests import PersistentComponents

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans
import nti.dataserver.tests.mock_dataserver as mock_dataserver

class TestSubscribers(ApplicationLayerTest):

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
