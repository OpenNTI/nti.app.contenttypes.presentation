#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that

import unittest

from nti.app.contenttypes.presentation.utils import VISIBILITY_SCOPE_MAP
from nti.app.contenttypes.presentation.utils import get_visibility_for_scope

from nti.app.contenttypes.presentation.tests import SharedConfiguringTestLayer

from nti.contenttypes.courses.interfaces import ES_ALL
from nti.contenttypes.courses.interfaces import ES_CREDIT
from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ES_PURCHASED
from nti.contenttypes.courses.interfaces import ES_CREDIT_DEGREE
from nti.contenttypes.courses.interfaces import ES_CREDIT_NONDEGREE

from nti.contenttypes.presentation.interfaces import PUBLIC
from nti.contenttypes.presentation.interfaces import CREDIT
from nti.contenttypes.presentation.interfaces import EVERYONE
from nti.contenttypes.presentation.interfaces import PURCHASED

class TestUtils(unittest.TestCase):

	layer = SharedConfiguringTestLayer

	def test_visibility_map(self):
		assert_that(VISIBILITY_SCOPE_MAP, has_length(6))
		assert_that(VISIBILITY_SCOPE_MAP, has_entry(ES_ALL, is_(EVERYONE)))
		assert_that(VISIBILITY_SCOPE_MAP, has_entry(ES_CREDIT, is_(CREDIT)))
		assert_that(VISIBILITY_SCOPE_MAP, has_entry(ES_PUBLIC, is_(PUBLIC)))
		assert_that(VISIBILITY_SCOPE_MAP, has_entry(ES_PURCHASED, is_(PURCHASED)))
		assert_that(VISIBILITY_SCOPE_MAP, has_entry(ES_CREDIT_DEGREE, is_(CREDIT)))
		assert_that(VISIBILITY_SCOPE_MAP, has_entry(ES_CREDIT_NONDEGREE, is_(CREDIT)))
		assert_that(get_visibility_for_scope(ES_ALL), is_(EVERYONE))
