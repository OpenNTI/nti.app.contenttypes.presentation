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

from nti.contentlibrary.indexed_data import get_catalog

from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup

from nti.app.contenttypes.presentation.subscribers import _removed_registered
from nti.app.contenttypes.presentation.subscribers import _index_overview_items
from nti.app.contenttypes.presentation.subscribers import _load_and_register_lesson_overview_json

from nti.app.contenttypes.presentation.tests import PersistentComponents

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans
import nti.dataserver.tests.mock_dataserver as mock_dataserver

def _remove_from_registry(container_ntiids=None, provided=None, registry=None):
	result = []
	catalog = get_catalog()
	intids = component.queryUtility(IIntIds)
	for utility in catalog.search_objects(intids=intids, provided=provided,
										  container_ntiids=container_ntiids ):
		try:
			ntiid = utility.ntiid
			if ntiid:
				result.append(utility)
				_removed_registered(provided,
									name=ntiid,
									intids=intids,
									catalog=catalog,
									registry=registry)
		except AttributeError:
			pass
	return result

class TestSubscribers(ApplicationLayerTest):

	@WithMockDSTrans
	def test_lessong_overview(self):
		path = os.path.join(os.path.dirname(__file__), 'lesson_overview.json')
		with open(path, "r") as fp:
			source = fp.read()

		registry = PersistentComponents()
		mock_dataserver.current_transaction.add(registry)

		result, removed = _load_and_register_lesson_overview_json(source, registry=registry)
		assert_that(result, is_not(none()))
		assert_that(removed, has_length(0))

		_index_overview_items((result,), container_ntiids='xxx')

		result = _remove_from_registry(container_ntiids='xxx', 
									   provided=INTICourseOverviewGroup,
									   registry=registry)
		assert_that(result, has_length(4))

		result = _remove_from_registry(container_ntiids='xxx', 
									   provided=INTILessonOverview,
									   registry=registry)
		assert_that(result, has_length(1))
