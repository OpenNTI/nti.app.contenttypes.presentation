#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import assert_that

import unittest

from nti.app.contenttypes.presentation.index import PresentationAssetCatalog

from nti.app.contenttypes.presentation.tests import SharedConfiguringTestLayer

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

class TestIndex(unittest.TestCase):

	layer = SharedConfiguringTestLayer

	@WithMockDSTrans
	def test_last_modified(self):
		catalog = PresentationAssetCatalog()
		assert_that(catalog.get_last_modified('key'), is_(0))

		catalog.set_last_modified('key', 100)
		assert_that(catalog.get_last_modified('key'), is_(100))

	@WithMockDSTrans
	def test_catalog(self):
		catalog = PresentationAssetCatalog()
		catalog.index(1, container='x')
		assert_that(list(catalog.get_references(container='x')), is_([1]))
		catalog.index(1, container='y')
		assert_that(list(catalog.get_references(container='x')), is_([1]))
		assert_that(list(catalog.get_references(container='y')), is_([1]))

		catalog.unindex(1)
		assert_that(list(catalog.get_references(container='x')), is_([]))
		assert_that(list(catalog.get_references(container='y')), is_([]))

		catalog.unindex(10)
		assert_that(list(catalog.get_references(container='x')), is_([]))

		catalog.index(10, container='x')
		catalog.index(11, container='x')
		assert_that(list(catalog.get_references(container='x')), is_([10, 11]))
		
		catalog.unindex(10)
		assert_that(list(catalog.get_references(container='x')), is_([11]))
		
		catalog.index(100, container='x', kind='p')
		assert_that(list(catalog.get_references(container='x', kind='p')), is_([100]))
		assert_that(list(catalog.get_references(container='x', kind='x')), is_([]))
		assert_that(list(catalog.get_references(container='r', kind='p')), is_([]))
		assert_that(list(catalog.get_references(kind='p')), is_([100]))
