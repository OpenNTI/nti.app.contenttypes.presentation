#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904
from hamcrest import is_
from hamcrest import is_not
from hamcrest import contains
from hamcrest import not_none
from hamcrest import has_item
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import contains_string

from nti.app.testing.decorators import WithSharedApplicationMockDS
from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.dataserver.tests import mock_dataserver

from nti.ntiids.ntiids import find_object_with_ntiid

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

	def _check_obj_state(self, ntiid, is_published=False, is_locked=True):
		"""
		Check our server state, specifically, whether an object is locked,
		published, and registered.
		"""
		with mock_dataserver.mock_db_trans(self.ds, site_name='janux.ou.edu'):
			obj = find_object_with_ntiid( ntiid )
			assert_that( obj, not_none() )
			assert_that( obj.locked, is_( is_locked ) )
			assert_that( obj.isPublished(), is_( is_published ) )

	@WithSharedApplicationMockDS(testapp=True, users=True)
	def test_permissions(self):
		"""
		Test non-editors cannot edit nodes.
		"""
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

		# Deleting
		unit_data = {'ntiid': unit_ntiids[-1]}
		self.testapp.delete_json(self.outline_url, unit_data,
							extra_environ=ichigo_environ, status=403)

	@WithSharedApplicationMockDS(testapp=True, users=True)
	def test_unit_node_edits(self):
		"""
		Test we can insert/move units at/to various indexes.
		"""
		# TODO Validate publish visibility/publishing.
		# TODO Revert layer changes ?
		self._test_unit_node_inserts()
		self._test_moving_nodes()
		self._test_deleting_nodes()
		self._test_content_nodes()
		self._test_moving_content_nodes()

	def _test_content_nodes(self):
		"""
		Create content nodes (via append or insert) with their lessons and fields.
		"""
		instructor_environ = self.instructor_environ
		def _get_first_unit_node():
			res = self.testapp.get( self.outline_url, extra_environ=instructor_environ )
			res = res.json_body
			return res[0]

		res = _get_first_unit_node()
		first_unit_ntiid = res.get( 'NTIID' )
		child_ntiids = [x.get( 'NTIID' ) for x in res.get( 'contents' )]
		assert_that( child_ntiids, has_length( 3 ))

		# Append content node; validate fields
		new_content_title = 'new content node title'
		unit_url = '/dataserver2/NTIIDs/%s/contents' % first_unit_ntiid
		content_data = {'title': new_content_title, 'MimeType': self.content_mime_type}
		res = self.testapp.post_json(unit_url, content_data,
									extra_environ=instructor_environ)
		res = res.json_body
		content_node_ntiid = res.get( 'NTIID' )
		lesson_ntiid = res.get( 'ContentNTIID' )
		assert_that( res.get( 'Creator' ), is_( self.instructor_username ))
		assert_that( res.get( 'MimeType' ), is_( self.content_mime_type ))
		assert_that( res.get( 'title' ), is_( new_content_title ))
		assert_that(lesson_ntiid, is_not( content_node_ntiid ))
		assert_that( content_node_ntiid, contains_string( 'NTICourseOutlineNode' ))
		assert_that( lesson_ntiid, contains_string( 'NTILessonOverview' ))
		self._check_obj_state( content_node_ntiid )
		self._check_obj_state( lesson_ntiid )

		res = _get_first_unit_node()
		child_ntiids = [x.get( 'NTIID' ) for x in res.get( 'contents' )]
		assert_that( child_ntiids, has_length( 4 ))
		assert_that( child_ntiids[-1], is_( content_node_ntiid ))

		# Insert at index 0 with dates
		new_content_title2 = 'new content node title2'
		unit_url = '/dataserver2/NTIIDs/%s/contents/index/0' % first_unit_ntiid
		content_beginning = '2013-08-13T06:00:00Z'
		content_ending = '2013-12-13T06:00:00Z'
		content_data = {'title': new_content_title2,
						'MimeType': self.content_mime_type,
						'ContentsAvailableBeginning': content_beginning,
						'ContentsAvailableEnding': content_ending }
		res = self.testapp.post_json(unit_url, content_data,
									extra_environ=instructor_environ)
		res = res.json_body
		content_node_ntiid2 = res.get( 'NTIID' )
		lesson_ntiid2 = res.get( 'ContentNTIID' )
		assert_that( res.get( 'ContentsAvailableBeginning' ), is_( content_beginning ))
		assert_that( res.get( 'ContentsAvailableEnding' ), is_( content_ending ))
		self._check_obj_state( content_node_ntiid2 )
		self._check_obj_state( lesson_ntiid2 )

		# TODO Shouldnt be visible outside contents dates.
		res = _get_first_unit_node()
		child_ntiids = [x.get( 'NTIID' ) for x in res.get( 'contents' )]
		assert_that( child_ntiids, has_length( 5 ))
		assert_that( child_ntiids[0], is_( content_node_ntiid2 ))
		assert_that( child_ntiids[-1], is_( content_node_ntiid ))

	def _test_moving_content_nodes(self):
		"""
		Move nodes between unit nodes.
		"""
		instructor_environ = self.instructor_environ
		def _get_unit_node( index ):
			res = self.testapp.get( self.outline_url, extra_environ=instructor_environ )
			res = res.json_body
			return res[index]

		res = _get_unit_node( 0 )
		src_unit_ntiid = res.get( 'NTIID' )
		original_src_child_ntiids = [x.get( 'NTIID' ) for x in res.get( 'contents' )]
		moved_ntiid = original_src_child_ntiids[0]

		res = _get_unit_node( 1 )
		target_unit_ntiid = res.get( 'NTIID' )
		original_target_child_ntiids = [x.get( 'NTIID' ) for x in res.get( 'contents' )]

		# Move to our target
		unit_url = '/dataserver2/NTIIDs/%s/contents/index/0' % target_unit_ntiid
		ntiid_data = {'ntiid': moved_ntiid}
		self.testapp.put_json(unit_url, ntiid_data,
								extra_environ=instructor_environ)

		# Still in old for now
		res = _get_unit_node( 0 )
		src_child_ntiids = [x.get( 'NTIID' ) for x in res.get( 'contents' )]
		assert_that( src_child_ntiids, has_item( moved_ntiid ))
		assert_that( src_child_ntiids, has_length( len( original_src_child_ntiids ) ))

		res = _get_unit_node( 1 )
		target_child_ntiids = [x.get( 'NTIID' ) for x in res.get( 'contents' )]
		assert_that( target_child_ntiids[0], is_( moved_ntiid ) )
		assert_that( target_child_ntiids, has_length( len( original_target_child_ntiids ) + 1 ))

		# Now client deletes from old
		unit_url = '/dataserver2/NTIIDs/%s/contents' % src_unit_ntiid
		unit_data = {'ntiid': moved_ntiid}
		self.testapp.delete_json(unit_url, unit_data,
								extra_environ=instructor_environ)

		res = _get_unit_node( 0 )
		src_child_ntiids = [x.get( 'NTIID' ) for x in res.get( 'contents' )]
		assert_that( src_child_ntiids, is_not( has_item( moved_ntiid )))
		assert_that( src_child_ntiids, has_length( len( original_src_child_ntiids ) - 1 ))

		# Nothing changes here
		res = _get_unit_node( 1 )
		target_child_ntiids2 = [x.get( 'NTIID' ) for x in res.get( 'contents' )]
		assert_that( target_child_ntiids2[0], is_( moved_ntiid ) )
		assert_that( target_child_ntiids2, contains( *target_child_ntiids ))
		self._check_obj_state( moved_ntiid )

	def _test_unit_node_inserts(self):
		"""
		Test inserting/appending unit nodes to an outline, with fields.
		"""
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
		self._check_obj_state( new_ntiid )

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
		self._check_obj_state( new_ntiid2 )

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
		self._check_obj_state( new_ntiid3 )

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

	def _test_deleting_nodes(self):
		instructor_environ = self.instructor_environ
		unit_ntiids = self._get_outline_ntiids( instructor_environ, 11 )
		first_ntiid = unit_ntiids[0]
		last_ntiid = unit_ntiids[-1]

		# One
		unit_data = {'ntiid': first_ntiid}
		self.testapp.delete_json(self.outline_url, unit_data,
							extra_environ=instructor_environ)
		unit_ntiids = self._get_outline_ntiids( instructor_environ, 10 )
		assert_that( unit_ntiids, is_not( has_item( first_ntiid )))

		# Two
		unit_data = {'ntiid': last_ntiid}
		self.testapp.delete_json(self.outline_url, unit_data,
							extra_environ=instructor_environ)
		unit_ntiids = self._get_outline_ntiids( instructor_environ, 9 )
		assert_that( unit_ntiids, is_not( has_item( last_ntiid )))
