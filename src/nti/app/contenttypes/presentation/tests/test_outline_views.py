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
from hamcrest import contains_string

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

class TestOutlineEditViews(ApplicationLayerTest):

	layer = InstructedCourseApplicationTestLayer

	default_origin = b'http://janux.ou.edu'
	course_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323_SubInstances_995'
	unit_mime_type = "application/vnd.nextthought.courses.courseoutlinenode"
	content_mime_type = "application/vnd.nextthought.courses.courseoutlinecontentnode"
	content_ntiid_type = 'NTICourseOutlineNode'
	outline_url = '/dataserver2/%2B%2Betc%2B%2Bhostsites/platform.ou.edu/%2B%2Betc%2B%2Bsite/Courses/Fall2015/CS%201323/SubInstances/995/Outline/contents'

	def setUp(self):
		# TODO Admin; need to test instructor
		self.instructor_username = 'sjohnson@nextthought.com'
		self.instructor_environ = self._make_extra_environ(username=self.instructor_username)

	def _get_outline_ntiids(self, environ, expected_size):
		res = self.testapp.get( self.outline_url, extra_environ=environ )
		res = res.json_body
		unit_ntiids = [x.get( 'NTIID' ) for x in res]
		assert_that( unit_ntiids, has_length( expected_size ))
		assert_that( set(unit_ntiids), has_length( expected_size ))
		return unit_ntiids

	@WithSharedApplicationMockDS(testapp=True, users=True)
	def test_permissions(self):
		student = "ichigo"
		with mock_dataserver.mock_db_trans(self.ds):
			self._create_user(student)

		# Enroll student
		ichigo_environ = self._make_extra_environ(username=student)
		enroll_url = '/dataserver2/CourseAdmin/UserCourseEnroll'
		data = {'username':student, 'ntiid': self.course_ntiid, 'scope':'ForCredit'}
		self.testapp.post_json(enroll_url, data, status=201)
		unit_ntiids = self._get_outline_ntiids( ichigo_environ, 8 )

		# Try editing
		unit_data = {'title': 'should not work', 'mime_type': self.unit_mime_type}
		self.testapp.post_json(self.outline_url, unit_data,
								extra_environ=ichigo_environ, status=403)

		# Try moving
		at_index_url = self.outline_url + '/index/0'
		unit_data = {'ntiid': unit_ntiids[-1]}
		self.testapp.put_json(at_index_url, unit_data,
							extra_environ=ichigo_environ, status=403)

	@WithSharedApplicationMockDS(testapp=True, users=True)
	def test_unit_node_edits(self):
		"""
		Test we can insert/move units at/to various indexes.
		"""
		# TODO delete
		# multi-type
		# move between nodes
		# TODO Revert layer changes ?
		# TODO test state: locked, published
		self._test_unit_node_inserts()
		self._test_moving_nodes()

	def _test_unit_node_inserts(self):
		# Base case
		instructor_environ = self.instructor_environ
		unit_ntiids = self._get_outline_ntiids( instructor_environ, 8 )
		first_unit_ntiid = unit_ntiids[0]
		last_unit_ntiid = unit_ntiids[-1]

		# Append unit node
		new_unit_title = 'new unit title'
		unit_data = {'title': new_unit_title, 'MimeType': self.unit_mime_type}
		res = self.testapp.post_json(self.outline_url, unit_data,
									extra_environ=instructor_environ)

		res = res.json_body
		new_ntiid = res.get( 'NTIID' )
		assert_that( res.get( 'Creator' ), is_( self.instructor_username ))
		assert_that( res.get( 'MimeType' ), is_( self.unit_mime_type ))
		assert_that( res.get( 'title' ), is_( new_unit_title ))
		# New ntiid is of correct type and contains our username
		assert_that( new_ntiid, contains_string( self.content_ntiid_type ))
		assert_that( new_ntiid, contains_string( 'sjohnson' ))

		# Test our outline; new ntiid is at end
		unit_ntiids = self._get_outline_ntiids( instructor_environ, 9 )
		assert_that( unit_ntiids[0], is_( first_unit_ntiid ))
		assert_that( unit_ntiids[-2], is_( last_unit_ntiid ))
		assert_that( unit_ntiids[-1], is_( new_ntiid ))

		# Insert at index 0
		at_index_url = self.outline_url + '/index/0'
		new_unit_title2 = 'new unit title2'
		content_beginning = '2013-08-13T06:00:00Z'
		content_ending = '2013-12-13T06:00:00Z'
		unit_data2 = {'title': new_unit_title2,
					'MimeType': self.unit_mime_type,
					'ContentsAvailableBeginning': content_beginning,
					'ContentsAvailableEnding': content_ending }
		res = self.testapp.post_json(at_index_url, unit_data2,
									extra_environ=instructor_environ)
		res = res.json_body
		new_ntiid2 = res.get( 'NTIID' )
		assert_that( res.get( 'ContentsAvailableBeginning' ), is_( content_beginning ))
		assert_that( res.get( 'ContentsAvailableEnding' ), is_( content_ending ))

		unit_ntiids = self._get_outline_ntiids( instructor_environ, 10 )
		assert_that( unit_ntiids[0], is_( new_ntiid2 ))
		assert_that( unit_ntiids[1], is_( first_unit_ntiid ))
		assert_that( unit_ntiids[-2], is_( last_unit_ntiid ))
		assert_that( unit_ntiids[-1], is_( new_ntiid ))

		# Insert at last index
		at_index_url = self.outline_url + '/index/9'
		new_unit_title3 = 'new unit title3'
		unit_data3 = {'title': new_unit_title3, 'MimeType': self.unit_mime_type}
		res = self.testapp.post_json(at_index_url, unit_data3,
									extra_environ=instructor_environ)
		new_ntiid3 = res.json_body.get( 'NTIID' )

		unit_ntiids = self._get_outline_ntiids( instructor_environ, 11 )
		assert_that( unit_ntiids[0], is_( new_ntiid2 ))
		assert_that( unit_ntiids[1], is_( first_unit_ntiid ))
		assert_that( unit_ntiids[-3], is_( last_unit_ntiid ))
		assert_that( unit_ntiids[-2], is_( new_ntiid3 ))
		assert_that( unit_ntiids[-1], is_( new_ntiid ))

	def _test_moving_nodes(self):
		instructor_environ = self.instructor_environ
		unit_ntiids = self._get_outline_ntiids( instructor_environ, 11 )
		first_ntiid = unit_ntiids[0]
		last_ntiid = unit_ntiids[-1]

		# Move last object to index 0
		at_index_url = self.outline_url + '/index/0'
		ntiid_data = {'ntiid': last_ntiid}
		self.testapp.put_json(at_index_url, ntiid_data,
								extra_environ=instructor_environ)

		unit_ntiids = self._get_outline_ntiids( instructor_environ, 11 )
		assert_that( unit_ntiids[0], is_( last_ntiid ))
		assert_that( unit_ntiids[1], is_( first_ntiid ))

		# Same move is no-op
		self.testapp.put_json(at_index_url, ntiid_data,
								extra_environ=instructor_environ)

		unit_ntiids = self._get_outline_ntiids( instructor_environ, 11 )
		assert_that( unit_ntiids[0], is_( last_ntiid ))
		assert_that( unit_ntiids[1], is_( first_ntiid ))

		# Move original first object to last index
		at_index_url = self.outline_url + '/index/10'
		ntiid_data = {'ntiid': first_ntiid}
		self.testapp.put_json(at_index_url, ntiid_data,
								extra_environ=instructor_environ)

		unit_ntiids = self._get_outline_ntiids( instructor_environ, 11 )
		assert_that( unit_ntiids[0], is_( last_ntiid ))
		assert_that( unit_ntiids[-1], is_( first_ntiid ))

