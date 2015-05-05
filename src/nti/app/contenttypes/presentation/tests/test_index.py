#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import assert_that

from nti.app.contenttypes.presentation.index import PresentationAssetCatalog

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

class TestIndex(ApplicationLayerTest):

	@WithMockDSTrans
	def test_last_modified(self):
		catalog = PresentationAssetCatalog()
		assert_that(catalog.get_last_modified('key'), is_(0))

		catalog.set_last_modified('key', 100)
		assert_that(catalog.get_last_modified('key'), is_(100))

	@WithMockDSTrans
	def test_catalog(self):
		catalog = PresentationAssetCatalog()
		catalog.index(1, containers='x')
		assert_that(list(catalog.get_references(containers='x')), is_([1]))
		catalog.index(1, containers='y')
		assert_that(list(catalog.get_references(containers='x')), is_([1]))
		assert_that(list(catalog.get_references(containers='y')), is_([1]))

		catalog.unindex(1)
		assert_that(list(catalog.get_references(containers='x')), is_([]))
		assert_that(list(catalog.get_references(containers='y')), is_([]))

		catalog.unindex(10)
		assert_that(list(catalog.get_references(containers='x')), is_([]))

		catalog.index(10, containers='x')
		catalog.index(11, containers='x')
		assert_that(list(catalog.get_references(containers='x')), is_([10, 11]))
		
		catalog.unindex(10)
		assert_that(list(catalog.get_references(containers='x')), is_([11]))
		
		catalog.index(100, containers='x', provided='p')
		assert_that(list(catalog.get_references(containers='x', provided='p')), is_([100]))
		assert_that(list(catalog.get_references(containers='x', provided='x')), is_([]))
		assert_that(list(catalog.get_references(containers='r', provided='p')), is_([]))
		assert_that(list(catalog.get_references(provided='p')), is_([100]))
