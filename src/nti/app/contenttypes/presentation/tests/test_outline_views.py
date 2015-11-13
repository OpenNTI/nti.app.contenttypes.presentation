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

from nti.app.testing.decorators import WithSharedApplicationMockDS
from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.dataserver.tests import mock_dataserver

from nti.app.products.courseware.tests import InstructedCourseApplicationTestLayer

class TestOutlineViews(ApplicationLayerTest):

	layer = InstructedCourseApplicationTestLayer

	default_origin = b'http://janux.ou.edu'

	course_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323_SubInstances_995'
	course_href = '/dataserver2/Objects/%s' + course_ntiid

	@WithSharedApplicationMockDS(testapp=True, users=True)
	def test_media_by_outline(self):
		student = "ichigo"
		with mock_dataserver.mock_db_trans(self.ds):
			self._create_user(student)

		# enroll student
		enroll_url = '/dataserver2/CourseAdmin/UserCourseEnroll'
		data = {'username':student, 'ntiid': self.course_ntiid, 'scope':'ForCredit'}
		res = self.testapp.post_json(enroll_url, data, status=201)

		# request media by outline
		course_ref = res.json_body['CourseInstance']['href']
		media_ref = course_ref + '/@@MediaByOutlineNode'
		ichigo_environ = self._make_extra_environ(username=student)
		res = self.testapp.get(media_ref, extra_environ=ichigo_environ)

		data = res.json_body
		assert_that(data, has_entry('ItemCount', is_(51)))
		assert_that(data, has_entry('Items', has_length(51)))
		assert_that(data, has_entry('Containers', has_length(22)))
		assert_that(data, has_entry('ContainerOrder', has_length(42)))
