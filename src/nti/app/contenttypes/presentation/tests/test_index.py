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
