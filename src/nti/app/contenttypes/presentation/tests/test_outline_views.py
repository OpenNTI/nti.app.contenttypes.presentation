#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

import fudge

from hamcrest import is_
from hamcrest import none
from hamcrest import has_key
from hamcrest import is_not
from hamcrest import contains
from hamcrest import not_none
from hamcrest import has_item
from hamcrest import has_items
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import contains_string
does_not = is_not

from datetime import datetime
from calendar import timegm as _calendar_timegm

from urlparse import urlparse

from nti.app.publishing import VIEW_PUBLISH
from nti.app.publishing import VIEW_UNPUBLISH

from nti.app.products.courseware.tests import InstructedCourseApplicationTestLayer

from nti.app.testing.decorators import WithSharedApplicationMockDS
from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.dataserver.tests import mock_dataserver

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.app.contenttypes.presentation import VIEW_CONTENTS
from nti.app.contenttypes.presentation import VIEW_NODE_MOVE
from nti.app.contenttypes.presentation import VIEW_ORDERED_CONTENTS
from nti.app.contenttypes.presentation import VIEW_OVERVIEW_CONTENT
from nti.app.contenttypes.presentation import VIEW_OVERVIEW_SUMMARY

from nti.app.contenttypes.presentation.tests import INVALID_TITLE_LENGTH

INVALID_TITLE = 'x' * INVALID_TITLE_LENGTH

STUDENT = 'ichigo'

class TestOutlineViews(ApplicationLayerTest):

	layer = InstructedCourseApplicationTestLayer

	default_origin = b'http://janux.ou.edu'

	course_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323_SubInstances_995'
	course_href = '/dataserver2/Objects/%s' + course_ntiid

	def _do_enroll(self):
		admin_environ = self._make_extra_environ(username=self.default_username)
		enroll_url = '/dataserver2/CourseAdmin/UserCourseEnroll'
		data = {'username':STUDENT, 'ntiid': self.course_ntiid, 'scope':'ForCredit'}
		return self.testapp.post_json(enroll_url, data, status=201, extra_environ=admin_environ)

	@WithSharedApplicationMockDS(testapp=True, users=(STUDENT,))
	@fudge.patch( 'nti.app.products.courseware.utils.PreviewCourseAccessPredicate._is_preview' )
	def test_links(self, mock_preview):
		mock_preview.is_callable().returns( True )
		res = self._do_enroll()
		course_ext = res.json_body['CourseInstance']
		course_href = course_ext.get( 'href' )
		self.forbid_link_with_rel(course_ext, 'MediaByOutlineNode')
		ichigo_environ = self._make_extra_environ(username=STUDENT)

		# Now verify our link shows up outside of preview mode.
		mock_preview.is_callable().returns( False )
		res = self.testapp.get( course_href, extra_environ=ichigo_environ )
		course_ext = res.json_body
		self.require_link_href_with_rel(course_ext, 'MediaByOutlineNode')

	@WithSharedApplicationMockDS(testapp=True, users=(STUDENT,))
	def test_media_by_outline(self):
		res = self._do_enroll()

		# request media by outline
		course_ext = res.json_body['CourseInstance']
		course_href = course_ext.get( 'href' )
		ichigo_environ = self._make_extra_environ(username=STUDENT)
		res = self.testapp.get( course_href, extra_environ=ichigo_environ )
		course_ext = res.json_body
		media_href = self.require_link_href_with_rel(course_ext, 'MediaByOutlineNode')
		res = self.testapp.get(media_href, extra_environ=ichigo_environ)

		data = res.json_body
		assert_that(data, has_entry('ItemCount', is_(63)))
		assert_that(data, has_entry('Items', has_length(63)))
		assert_that(data, has_entry('Containers', has_length(24)))
		assert_that(data, has_entry('ContainerOrder', has_length(53)))

		lesson = 'tag:nextthought.com,2011-10:OU-HTML-CS1323_F_2015_Intro_to_Computer_Programming.lec:01.01_LESSON'
		children = [ "tag:nextthought.com,2011-10:OU-NTIVideo-CS1323_F_2015_Intro_to_Computer_Programming.ntivideo.video_01.01.01_Welcome",
				"tag:nextthought.com,2011-10:OU-NTIVideo-CS1323_F_2015_Intro_to_Computer_Programming.ntivideo.video_01.01.01_Code",
				"tag:nextthought.com,2011-10:OU-NTIVideo-CS1323_F_2015_Intro_to_Computer_Programming.ntivideo.video_01.01.01_Obama",
				"tag:nextthought.com,2011-10:OU-NTIVideo-CS1323_F_2015_Intro_to_Computer_Programming.ntivideo.video_01.01.01_Java",
				"tag:nextthought.com,2011-10:OU-NTIVideo-CS1323_F_2015_Intro_to_Computer_Programming.ntivideo.video_01.01.01_Academic_Integrity"]

		assert_that( data.get('Containers').get( lesson ), is_( children ))

class TestOutlineEditViews(ApplicationLayerTest):

	layer = InstructedCourseApplicationTestLayer

	default_origin = b'http://janux.ou.edu'
	course_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323_SubInstances_995'
	unit_mime_type = "application/vnd.nextthought.courses.courseoutlinenode"
	content_mime_type = "application/vnd.nextthought.courses.courseoutlinecontentnode"
	content_ntiid_type = 'NTICourseOutlineNode'
	outline_obj_url = '/dataserver2/%2B%2Betc%2B%2Bhostsites/platform.ou.edu/%2B%2Betc%2B%2Bsite/Courses/Fall2015/CS%201323/SubInstances/995/Outline'
	move_url = '%s/%s' % ( outline_obj_url, VIEW_NODE_MOVE )

	def _get_outline_json(self):
		res = self.testapp.get( self.outline_obj_url, extra_environ=self.editor_environ )
		return res.json_body

	@property
	def outline_url(self):
		res = self._get_outline_json()
		return self.require_link_href_with_rel( res, VIEW_CONTENTS )

	@property
	def outline_ordered_contents_url(self):
		res = self._get_outline_json()
		return self.require_link_href_with_rel( res, VIEW_ORDERED_CONTENTS )

	@property
	def outline_ntiid(self):
		res = self.testapp.get(self.outline_obj_url, extra_environ=self.editor_environ)
		res = res.json_body
		outline_ntiid = res.get( 'NTIID' )
		return outline_ntiid

	def setUp(self):
		# This instructor is also a content editor for this course.
		self.instructor_username = 'tryt3968'
		self.editor_environ = self._make_extra_environ( username=self.instructor_username )

	def _get_move_json(self, obj_ntiid, new_parent_ntiid, index=None, old_parent_ntiid=None):
		result = { 'ObjectNTIID': obj_ntiid,
					'ParentNTIID': new_parent_ntiid }
		if index is not None:
			result['Index'] = index
		if old_parent_ntiid is not None:
			result['OldParentNTIID'] = old_parent_ntiid
		return result

	def _get_delete_url_suffix(self, index, ntiid):
		# For outlines, the index is ignored. Validate that.
		return '/ntiid/%s?index=%s' % (ntiid, -1)

	def _create_student_environ(self):
		student_environ = self._make_extra_environ(username=STUDENT)
		try:
			with mock_dataserver.mock_db_trans(self.ds):
				self._create_user(STUDENT)
		except KeyError:
			pass
		else:
			# Enroll student
			enroll_url = '/dataserver2/CourseAdmin/UserCourseEnroll'
			data = {'username':STUDENT, 'ntiid': self.course_ntiid, 'scope':'ForCredit'}
			self.testapp.post_json(enroll_url, data, status=201)
		return student_environ

	def _get_outline_url(self, get_unpublished=True):
		url = self.outline_url
		if get_unpublished:
			parsed = urlparse( url )
			parsed = parsed._replace( query="omit_unpublished=False" )
			url = parsed.geturl()
		return url

	def _get_outline_ntiids(self, environ, expected_size, get_unpublished=True):
		"""
		Get the outline ntiids, validating size. By default, instructors
		will get unpublished nodes as well.
		"""
		url = self._get_outline_url( get_unpublished )
		res = self.testapp.get( url, extra_environ=environ )
		res = res.json_body
		unit_ntiids = [x.get('NTIID') for x in res]
		assert_that(unit_ntiids, has_length(expected_size))
		assert_that(set(unit_ntiids), has_length(expected_size))
		return unit_ntiids

	def _publish_obj( self, ntiid, start=None, end=None, unpublish=False ):
		"""
		Publish an object, optionally with start and end dates.
		"""
		data = None
		start = start and _calendar_timegm( start.timetuple() )
		end = end and _calendar_timegm( end.timetuple() )
		rel = 'unpublish' if unpublish else 'publish'

		if start or end:
			data = { 'publishBeginning': start,
					'publishEnding': end }
		url = '/dataserver2/Objects/%s' % ntiid
		res = self.testapp.get( url, extra_environ=self.editor_environ )
		res = res.json_body
		url = self.require_link_href_with_rel( res, rel )
		if data:
			self.testapp.post_json( url, data, extra_environ=self.editor_environ )
		else:
			self.testapp.post_json( url, extra_environ=self.editor_environ )

	def _check_lesson_ext_state(self, link, environ):
		res = self.testapp.get(link, extra_environ=environ)
		res = res.json_body
		assert_that( res, has_item( 'PublicationState' ) )

	def _check_ext_state(self, ntiid, is_lesson_visible=True, has_lesson=False,
						published=True, start=None, end=None, environ=None):
		"""
		Validate a node's external state. A node's contents are not visible
		if the content available dates are out-of-bounds. Validate pub/unpub
		links. Validate publish beginning/end times.
		"""
		environ = environ if environ else self.editor_environ
		res = self.testapp.get(self._get_outline_url(), extra_environ=environ)
		res = res.json_body
		def _find_item( items ):
			for item in items:
				if item.get( 'NTIID' ) == ntiid:
					return item
				for child in item.get( 'contents', () ):
					if child.get( 'NTIID' ) == ntiid:
						return child

		obj = _find_item( res )
		assert_that( obj, not_none() )
		if has_lesson and not is_lesson_visible:
			# Based on content available dates, items do not expose contents.
			assert_that( obj, does_not( has_items( 'contents', 'ContentNTIID' )))
			self.forbid_link_with_rel( obj, VIEW_OVERVIEW_CONTENT )
			self.forbid_link_with_rel( obj, VIEW_OVERVIEW_SUMMARY )
		elif has_lesson:
			# Content node with published/visible lesson contents.
			assert_that( obj, has_entries( 'contents', not_none(),
										'ContentNTIID', not_none() ))
			overview_link = self.require_link_href_with_rel( obj, VIEW_OVERVIEW_CONTENT )
			self.require_link_href_with_rel( obj, VIEW_OVERVIEW_SUMMARY )
			self._check_lesson_ext_state( overview_link, environ )
		else:
			# Unit with contents
			assert_that( obj, has_entries( 'contents', not_none() ))

		publish_matcher = not_none if published else none
		assert_that( obj.get( 'PublicationState' ), publish_matcher() )

		if environ is self.editor_environ:
			# Edit links are always available for editors.
			self.require_link_href_with_rel( obj, 'edit' )
			self.require_link_href_with_rel( obj, VIEW_PUBLISH )
			self.require_link_href_with_rel( obj, VIEW_UNPUBLISH )
			self.require_link_href_with_rel( obj, VIEW_ORDERED_CONTENTS )

		def _to_date( val ):
			return val and datetime.strptime( val, '%Y-%m-%dT%H:%M:%SZ' )

		start = start and start.replace( microsecond=0 )
		end = end and end.replace( microsecond=0 )

		assert_that( _to_date( obj.get('publishBeginning')), is_(start))
		assert_that( _to_date( obj.get('publishEnding')), is_(end))

	def _reset_obj_state(self, ntiid, child_locked=False):
		with mock_dataserver.mock_db_trans(self.ds, site_name='janux.ou.edu'):
			obj = find_object_with_ntiid(ntiid)
			assert_that(obj, not_none())
			obj.child_order_locked = child_locked

	def _check_obj_state(self, ntiid, is_published=False, is_locked=True, is_child_locked=False):
		"""
		Check our server state, specifically, whether an object is locked,
		published, and registered. If given a lesson, validate lesson props.
		"""
		with mock_dataserver.mock_db_trans(self.ds, site_name='janux.ou.edu'):
			obj = find_object_with_ntiid(ntiid)
			assert_that(obj, not_none())
			assert_that(obj.locked, is_(is_locked))
			assert_that(obj.isPublished(), is_(is_published))
			assert_that(obj.child_order_locked, is_(is_child_locked))

			if INTILessonOverview.providedBy( obj ):
				# Lessons have same titles as content nodes.
				assert_that( obj.title, is_( obj.__parent__.title ))
				# Lineage and asset-container
				assert_that( obj.__parent__, not_none())
				entry = find_object_with_ntiid(self.course_ntiid)
				course = ICourseInstance(entry)
				# Our asset container is only valid for the outline course
				# (which may or may not be shared with subinstances).
				course = ICourseInstance( course.Outline )
				container = IPresentationAssetContainer(course)
				assert_that(container, has_key(obj.ntiid))

	@WithSharedApplicationMockDS(testapp=True, users=True)
	def test_permissions(self):
		"""
		Test non-editors cannot edit/publish nodes.
		"""
		student_environ = self._create_student_environ()
		unit_ntiids = self._get_outline_ntiids(student_environ, 8)

		# Try editing
		unit_data = {'title': 'should not work', 'mime_type': self.unit_mime_type}
		self.testapp.post_json(self._get_outline_url(), unit_data,
							   extra_environ=student_environ, status=403)

		# Try moving
		outline_ntiid = self.outline_ntiid
		move_data = self._get_move_json(unit_ntiids[-1], outline_ntiid, 0)
		self.testapp.post_json(self.move_url, move_data,
							  extra_environ=student_environ, status=403)

		# Deleting
		to_delete = unit_ntiids[-1]
		index = unit_ntiids.index( to_delete )
		delete_suffix = self._get_delete_url_suffix( index, to_delete )
		self.testapp.delete(self.outline_ordered_contents_url + delete_suffix,
							extra_environ=student_environ, status=403)

		# No pub/unpub links
		res = self.testapp.get(self._get_outline_url(), extra_environ=student_environ)
		res = res.json_body
		for item in res:
			self.forbid_link_with_rel( item, VIEW_PUBLISH )
			self.forbid_link_with_rel( item, VIEW_UNPUBLISH )
			self.forbid_link_with_rel( item, 'edit' )

	@WithSharedApplicationMockDS(testapp=True, users=True)
	def test_unit_node_edits(self):
		"""
		Test we can insert/move units at/to various indexes.
		"""
		# TODO Revert layer changes?
		node_count = self._test_unit_node_inserts()
		self._test_moving_nodes( node_count )
		node_count = self._test_deleting_nodes( node_count )
		self._test_content_nodes()
		self._test_moving_content_nodes()

	def _test_content_nodes(self):
		"""
		Create content nodes (via append or insert) with their lessons and fields.
		"""
		instructor_environ = self.editor_environ
		student_environ = self._create_student_environ()
		def _get_first_unit_node( _environ=instructor_environ ):
			res = self.testapp.get(self._get_outline_url(), extra_environ=_environ)
			res = res.json_body
			return res[0]

		def _first_node_size( expected_size=3, _environ=instructor_environ ):
			res = _get_first_unit_node( _environ )
			child_ntiids = [x.get('NTIID') for x in res.get('contents')]
			assert_that(child_ntiids, has_length( expected_size ))
			return child_ntiids

		res = _get_first_unit_node()
		first_unit_ntiid = res.get('NTIID')
		_first_node_size()
		_first_node_size( _environ=student_environ )
		self._check_obj_state( first_unit_ntiid, is_published=True, is_locked=False )

		# Append content node; validate fields
		new_content_title = 'new content node title'
		unit_url = '/dataserver2/NTIIDs/%s/contents' % first_unit_ntiid
		content_data = {'title': new_content_title, 'MimeType': self.content_mime_type}
		res = self.testapp.post_json(unit_url, content_data,
									 extra_environ=instructor_environ)
		res = res.json_body
		content_href = res.get( 'href' )
		content_node_ntiid = res.get('NTIID')
		lesson_ntiid = res.get('ContentNTIID')
		assert_that(res.get('Creator'), is_(self.instructor_username))
		assert_that(res.get('MimeType'), is_(self.content_mime_type))
		assert_that(res.get('title'), is_(new_content_title))
		assert_that(lesson_ntiid, is_not(content_node_ntiid))
		assert_that(content_node_ntiid, contains_string('NTICourseOutlineNode'))
		assert_that(lesson_ntiid, contains_string('NTILessonOverview'))
		self.require_link_href_with_rel(res, VIEW_PUBLISH)
		self.require_link_href_with_rel(res, VIEW_UNPUBLISH)

		# Must publish for students to see
		_first_node_size( 4 )
		_first_node_size( 3, student_environ )
		self._check_obj_state( content_node_ntiid )
		self._publish_obj( content_node_ntiid )
		self._check_obj_state( content_node_ntiid, is_published=True )
		self._check_obj_state( lesson_ntiid )
		self._check_ext_state( content_node_ntiid,  has_lesson=True )
		# Parent is child order locked.
		self._check_obj_state( first_unit_ntiid, is_published=True,
							is_locked=False, is_child_locked=True )

		_first_node_size( 4, student_environ )
		child_ntiids = _first_node_size( 4 )
		assert_that(child_ntiids[-1], is_(content_node_ntiid))

		# Editting content node title changes lesson title.
		content_data = {'title':'new content title2'}
		self.testapp.put_json(content_href, content_data,
							extra_environ=instructor_environ)
		self._check_obj_state( content_node_ntiid, is_published=True )
		self._check_obj_state( lesson_ntiid )

		# Insert at index 0 with dates
		new_content_title2 = 'new content node title2'
		unit_url = '/dataserver2/NTIIDs/%s/contents/index/0' % first_unit_ntiid
		content_data = {'title': new_content_title2,
						'MimeType': self.content_mime_type }
		res = self.testapp.post_json(unit_url, content_data,
									 extra_environ=instructor_environ)
		res = res.json_body
		content_node_ntiid2 = res.get('NTIID')
		lesson_ntiid2 = res.get('ContentNTIID')
		self.require_link_href_with_rel(res, VIEW_PUBLISH)
		self.require_link_href_with_rel(res, VIEW_UNPUBLISH)
		self._check_obj_state(content_node_ntiid2)
		self._check_obj_state(lesson_ntiid2)
		# Parent is child order locked.
		self._check_obj_state( first_unit_ntiid, is_published=True,
							is_locked=False, is_child_locked=True )

		# Must publish for students to see
		_first_node_size( 5 )
		_first_node_size( 4, student_environ )
		self._check_obj_state( content_node_ntiid2 )

		content_beginning = datetime.utcnow().replace( year=2200 )
		content_ending = datetime.utcnow().replace( year=2213 )
		self._publish_obj( content_node_ntiid2, start=content_beginning, end=content_ending )
		# Based on dates, node is still not published
		self._check_obj_state( content_node_ntiid2 )
		self._check_obj_state( lesson_ntiid2 )
		self._check_ext_state( content_node_ntiid2,
							published=False, has_lesson=True,
							start=content_beginning, end=content_ending )

		# Unpublish, dates are gone
		self._publish_obj( content_node_ntiid2, unpublish=True )
		self._check_obj_state( content_node_ntiid2 )
		self._check_ext_state( content_node_ntiid2,
							published=False, has_lesson=True )

		# Random access on unpublished item; instructor can see, student cannot not.
		get_url = '/dataserver2/Objects/%s' % content_node_ntiid2
		self.testapp.get( get_url, extra_environ=instructor_environ )
		self.testapp.get( get_url, extra_environ=student_environ, status=403 )

		# Re-add dates and explicitly publish, dates are gone
		self._publish_obj( content_node_ntiid2, start=content_beginning, end=content_ending )
		self._publish_obj( content_node_ntiid2 )
		self._check_obj_state( content_node_ntiid2, is_published=True )
		self._check_obj_state( lesson_ntiid2 )
		self._check_ext_state( content_node_ntiid2,
							published=True, has_lesson=True )

		_first_node_size( 5 )
		child_ntiids = _first_node_size( 5, student_environ )
		assert_that(child_ntiids[0], is_(content_node_ntiid2))
		assert_that(child_ntiids[-1], is_(content_node_ntiid))

		# Now publish the lesson with dates; student cannot see.
		self._publish_obj( lesson_ntiid2, start=content_beginning )
		self._check_obj_state( content_node_ntiid2, is_published=True )
		self._check_obj_state( lesson_ntiid2 )
		self._check_ext_state( content_node_ntiid2, is_lesson_visible=False,
							published=True, has_lesson=True,
							environ=student_environ )

		# Now explicit publish lesson
		self._publish_obj( lesson_ntiid2 )
		self._check_obj_state( content_node_ntiid2, is_published=True )
		self._check_obj_state( lesson_ntiid2, is_published=True )
		self._check_ext_state( content_node_ntiid2,
							published=True, has_lesson=True )
		self._check_ext_state( content_node_ntiid2,
							published=True, has_lesson=True,
							environ=student_environ )

		# Publish with end date boundary in past (unpublished).
		last_year_content_ending = datetime.utcnow().replace( year=2014 )
		self._publish_obj( lesson_ntiid2, end=last_year_content_ending )
		self._check_obj_state( content_node_ntiid2, is_published=True )
		self._check_obj_state( lesson_ntiid2 )
		self._check_ext_state( content_node_ntiid2,
							published=True, has_lesson=True )
		self._check_ext_state( content_node_ntiid2, is_lesson_visible=False,
							published=True, has_lesson=True,
							environ=student_environ )

		# Publish with end date boundary in future (published).
		self._publish_obj( lesson_ntiid2, end=content_ending )
		self._check_obj_state( lesson_ntiid2, is_published=True )
		self._check_ext_state( content_node_ntiid2,
							published=True, has_lesson=True )
		self._check_ext_state( content_node_ntiid2,
							published=True, has_lesson=True,
							environ=student_environ )

		# Unpublish lesson
		self._publish_obj( lesson_ntiid2, unpublish=True )
		self._check_obj_state( content_node_ntiid2, is_published=True )
		self._check_obj_state( lesson_ntiid2 )
		self._check_ext_state( content_node_ntiid2,
							published=True, has_lesson=True )
		self._check_ext_state( content_node_ntiid2, is_lesson_visible=False,
							published=True, has_lesson=True,
							environ=student_environ )

	def _test_moving_content_nodes(self):
		"""
		Move nodes between unit nodes.
		"""
		instructor_environ = self.editor_environ
		def _get_unit_node(index):
			res = self.testapp.get(self._get_outline_url(), extra_environ=instructor_environ)
			res = res.json_body
			return res[index]

		res = _get_unit_node(0)
		src_unit_ntiid = res.get('NTIID')
		original_src_child_ntiids = [x.get('NTIID') for x in res.get('contents')]
		moved_ntiid = original_src_child_ntiids[0]

		res = _get_unit_node(1)
		target_unit_ntiid = res.get('NTIID')
		original_target_child_ntiids = [x.get('NTIID') for x in res.get('contents')]

		self._reset_obj_state( target_unit_ntiid )
		self._reset_obj_state( src_unit_ntiid )
		self._check_obj_state( target_unit_ntiid, is_locked=False, is_published=True )
		self._check_obj_state( src_unit_ntiid, is_locked=False, is_published=True )

		# Move to our target
		move_data = self._get_move_json(moved_ntiid, target_unit_ntiid, 0, src_unit_ntiid)
		self.testapp.post_json(self.move_url, move_data,
							  extra_environ=instructor_environ)

		# Removed from old
		res = _get_unit_node(0)
		src_child_ntiids = [x.get('NTIID') for x in res.get('contents')]
		assert_that( src_child_ntiids, is_not(has_item(moved_ntiid)))
		assert_that( src_child_ntiids, has_length(len(original_src_child_ntiids) - 1))

		res = _get_unit_node(1)
		target_child_ntiids = [x.get('NTIID') for x in res.get('contents')]
		assert_that( target_child_ntiids[0], is_(moved_ntiid) )

		self._check_obj_state( target_unit_ntiid, is_locked=False,
							is_child_locked=True, is_published=True )
		self._check_obj_state( src_unit_ntiid, is_locked=False,
							is_child_locked=True, is_published=True )

		# Move back
		move_data = self._get_move_json(moved_ntiid, src_unit_ntiid, 0, target_unit_ntiid)
		self.testapp.post_json(self.move_url, move_data,
							  extra_environ=instructor_environ)

		res = _get_unit_node(0)
		src_child_ntiids = [x.get('NTIID') for x in res.get('contents')]
		assert_that(src_child_ntiids[0], is_(moved_ntiid))
		assert_that(src_child_ntiids, contains(*original_src_child_ntiids))

		res = _get_unit_node(1)
		target_child_ntiids2 = [x.get('NTIID') for x in res.get('contents')]
		assert_that(target_child_ntiids2, contains(*original_target_child_ntiids))

		self._check_obj_state( target_unit_ntiid, is_locked=False,
							is_child_locked=True, is_published=True )
		self._check_obj_state( src_unit_ntiid, is_locked=False,
							is_child_locked=True, is_published=True )

	def _test_unit_node_inserts(self):
		"""
		Test inserting/appending unit nodes to an outline, with fields.
		"""
		# Base case
		node_count = 8
		instructor_environ = self.editor_environ
		outline_ntiid = self.outline_ntiid
		student_environ = self._create_student_environ()
		self._get_outline_ntiids(student_environ, node_count)
		unit_ntiids = self._get_outline_ntiids(instructor_environ, node_count)
		first_unit_ntiid = unit_ntiids[0]
		last_unit_ntiid = unit_ntiids[-1]

		self._reset_obj_state( outline_ntiid )
		self._check_obj_state( outline_ntiid, is_locked=False )

		# Append unit node
		new_unit_title = 'new unit title'
		unit_data = {'title': new_unit_title, 'MimeType': self.unit_mime_type}
		res = self.testapp.post_json(self.outline_ordered_contents_url, unit_data,
									 extra_environ=instructor_environ)

		res = res.json_body
		new_ntiid = res.get('NTIID')
		assert_that(res.get('Creator'), is_(self.instructor_username))
		assert_that(res.get('MimeType'), is_(self.unit_mime_type))
		assert_that(res.get('title'), is_(new_unit_title))
		# New ntiid is of correct type and contains our username
		assert_that(new_ntiid, contains_string(self.content_ntiid_type))
		assert_that(new_ntiid, contains_string('tryt3968'))
		self.require_link_href_with_rel(res, VIEW_PUBLISH)
		self.require_link_href_with_rel(res, VIEW_UNPUBLISH)

		# Before publishing, our outline is unchanged for students
		self._get_outline_ntiids( student_environ, node_count )
		self._get_outline_ntiids( instructor_environ, node_count, get_unpublished=False )
		self._get_outline_ntiids( instructor_environ, node_count + 1 )
		self._check_obj_state( new_ntiid )
		self._publish_obj( new_ntiid )
		node_count += 1
		self._check_obj_state( new_ntiid, is_published=True )
		self._check_ext_state( new_ntiid, is_lesson_visible=True )

		# Test our outline; new ntiid is at end
		unit_ntiids = self._get_outline_ntiids( student_environ, node_count )
		assert_that(unit_ntiids[0], is_(first_unit_ntiid))
		assert_that(unit_ntiids[-2], is_(last_unit_ntiid))
		assert_that(unit_ntiids[-1], is_(new_ntiid))
		self._check_obj_state( outline_ntiid, is_locked=False,
							is_child_locked=True )

		# Insert at index 0
		at_index_url = self.outline_ordered_contents_url + '/index/0'
		new_unit_title2 = 'new unit title2'
		unit_data2 = {'title': new_unit_title2,
					'MimeType': self.unit_mime_type}
		res = self.testapp.post_json(at_index_url, unit_data2,
									 extra_environ=instructor_environ)
		res = res.json_body
		new_ntiid2 = res.get('NTIID')
		self.require_link_href_with_rel(res, VIEW_PUBLISH)
		self.require_link_href_with_rel(res, VIEW_UNPUBLISH)

		self._get_outline_ntiids( student_environ, node_count )
		self._get_outline_ntiids( instructor_environ, node_count, get_unpublished=False )
		self._get_outline_ntiids( instructor_environ, node_count + 1 )
		self._check_obj_state( new_ntiid2 )

		content_beginning = datetime.utcnow().replace( year=2013 )
		content_ending = datetime.utcnow().replace( year=2213 )
		self._publish_obj( new_ntiid2, start=content_beginning, end=content_ending )
		node_count += 1
		self._check_obj_state( new_ntiid2, is_published=True )
		self._check_ext_state( new_ntiid2, is_lesson_visible=False,
							start=content_beginning, end=content_ending )

		unit_ntiids = self._get_outline_ntiids( student_environ, node_count )
		assert_that(unit_ntiids[0], is_(new_ntiid2))
		assert_that(unit_ntiids[1], is_(first_unit_ntiid))
		assert_that(unit_ntiids[-2], is_(last_unit_ntiid))
		assert_that(unit_ntiids[-1], is_(new_ntiid))

		# Insert at last index
		at_index_url = self.outline_ordered_contents_url + '/index/9'
		new_unit_title3 = 'new unit title3'
		unit_data3 = {'title': new_unit_title3,
					'MimeType': self.unit_mime_type}
		res = self.testapp.post_json(at_index_url, unit_data3,
									 extra_environ=instructor_environ)
		new_ntiid3 = res.json_body.get('NTIID')

		self._check_obj_state(new_ntiid3)
		content_beginning = datetime.utcnow().replace( year=2000 )
		self._publish_obj( new_ntiid3, start=content_beginning )
		node_count += 1
		self._check_obj_state( new_ntiid3, is_published=True )
		self._check_ext_state( new_ntiid3, start=content_beginning )

		unit_ntiids = self._get_outline_ntiids( student_environ, node_count )
		assert_that(unit_ntiids[0], is_(new_ntiid2))
		assert_that(unit_ntiids[1], is_(first_unit_ntiid))
		assert_that(unit_ntiids[-3], is_(last_unit_ntiid))
		assert_that(unit_ntiids[-2], is_(new_ntiid3))
		assert_that(unit_ntiids[-1], is_(new_ntiid))

		self._check_obj_state( outline_ntiid, is_locked=False,
							is_child_locked=True )

		# Invalid
		invalid_data = {'title': INVALID_TITLE,
					'MimeType': self.unit_mime_type}
		self.testapp.post_json(at_index_url, invalid_data,
								extra_environ=instructor_environ,
								status=422)

		return node_count

	def _test_moving_nodes(self, node_count):
		instructor_environ = self.editor_environ
		unit_ntiids = self._get_outline_ntiids(instructor_environ, node_count)
		first_ntiid = unit_ntiids[0]
		last_ntiid = unit_ntiids[-1]
		outline_ntiid = self.outline_ntiid

		self._reset_obj_state( outline_ntiid )
		self._check_obj_state( outline_ntiid, is_locked=False )

		# Move last object to index 0
		move_data = self._get_move_json(last_ntiid, outline_ntiid, 0)
		move_res = self.testapp.post_json(self.move_url, move_data,
							  extra_environ=instructor_environ)
		move_res = move_res.json_body.get( 'Items' )

		unit_ntiids = self._get_outline_ntiids(instructor_environ, node_count)
		assert_that( unit_ntiids[0], is_(last_ntiid))
		assert_that( unit_ntiids[1], is_(first_ntiid))
		assert_that( move_res, has_length( node_count ))
		self._check_obj_state( outline_ntiid, is_locked=False, is_child_locked=True )

		# Same move is no-op
		move_res = self.testapp.post_json(self.move_url, move_data,
							  extra_environ=instructor_environ)
		move_res = move_res.json_body.get( 'Items' )

		unit_ntiids = self._get_outline_ntiids(instructor_environ, node_count)
		assert_that( unit_ntiids[0], is_(last_ntiid))
		assert_that( unit_ntiids[1], is_(first_ntiid))
		assert_that( move_res, has_length( node_count ))

		# Move original first object to last index
		last_index = len( unit_ntiids ) - 1
		move_data = self._get_move_json(first_ntiid, outline_ntiid, last_index)
		move_res = self.testapp.post_json(self.move_url, move_data,
							  extra_environ=instructor_environ)
		move_res = move_res.json_body.get( 'Items' )
		move_ntiids = [x.get( 'NTIID' ) for x in move_res]

		unit_ntiids = self._get_outline_ntiids(instructor_environ, node_count)
		assert_that( unit_ntiids[0], is_(last_ntiid))
		assert_that( unit_ntiids[-1], is_(first_ntiid))
		assert_that( move_res, has_length( node_count ))
		assert_that( move_ntiids, is_( unit_ntiids ))
		self._check_obj_state( outline_ntiid, is_locked=False, is_child_locked=True )

	def _test_deleting_nodes(self, node_count):
		instructor_environ = self.editor_environ
		unit_ntiids = self._get_outline_ntiids(instructor_environ, node_count)
		first_ntiid = unit_ntiids[0]
		last_ntiid = unit_ntiids[-1]
		outline_ntiid = self.outline_ntiid

		self._reset_obj_state( outline_ntiid )
		self._check_obj_state( outline_ntiid, is_locked=False )

		# One
		delete_suffix = self._get_delete_url_suffix( 0, first_ntiid )
		self.testapp.delete(self.outline_ordered_contents_url + delete_suffix,
							extra_environ=instructor_environ)
		node_count -= 1
		unit_ntiids = self._get_outline_ntiids(instructor_environ, node_count)
		assert_that(unit_ntiids, is_not(has_item(first_ntiid)))
		self._check_obj_state( outline_ntiid, is_locked=False, is_child_locked=True )

		# Two
		index = unit_ntiids.index( last_ntiid )
		delete_suffix = self._get_delete_url_suffix( index, last_ntiid )
		self.testapp.delete(self.outline_ordered_contents_url + delete_suffix,
							extra_environ=instructor_environ)
		# Multiple calls are fine
		self.testapp.delete(self.outline_ordered_contents_url + delete_suffix,
							extra_environ=instructor_environ)

		node_count -= 1
		unit_ntiids = self._get_outline_ntiids(instructor_environ, node_count)
		assert_that(unit_ntiids, is_not(has_item(last_ntiid)))
		self._check_obj_state( outline_ntiid, is_locked=False, is_child_locked=True )
		return node_count

	@WithSharedApplicationMockDS(testapp=True, users=True)
	def test_outline_decorator(self):
		url = '/dataserver2/%2B%2Betc%2B%2Bhostsites/platform.ou.edu/%2B%2Betc%2B%2Bsite/Courses/Fall2015/CS%201323/SubInstances/995'
		res = self.testapp.get( url, extra_environ=self.editor_environ )
		res = res.json_body.get( 'Outline' )
		self.require_link_href_with_rel(res, VIEW_NODE_MOVE)
		assert_that( res, has_entries( 'IsCourseOutlineShared', is_( True ),
									'CourseOutlineSharedEntries', has_length( 3 )))
