#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import assert_that

from nti.app.contenttypes.presentation.utils.course import ProxyEnrollmentRecord

from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecord

from nti.dataserver.tests import mock_dataserver

from nti.testing.matchers import verifiably_provides

class TestCourse(mock_dataserver.DataserverLayerTest):
	
	def test_proxy(self):
		p = ProxyEnrollmentRecord()
		assert_that(p, verifiably_provides(ICourseInstanceEnrollmentRecord))
