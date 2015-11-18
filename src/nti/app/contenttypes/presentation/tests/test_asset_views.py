#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_in
from hamcrest import is_not
from hamcrest import has_key
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import greater_than
from hamcrest import has_property

from nti.schema.testing import validly_provides

import os
from itertools import chain

import simplejson

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.contenttypes.presentation.utils import prepare_json_text

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.recorder.interfaces import ITransactionRecordHistory

from nti.app.testing.decorators import WithSharedApplicationMockDS
from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.dataserver.tests import mock_dataserver

from nti.app.products.courseware.tests import InstructedCourseApplicationTestLayer

class TestAssetViews(ApplicationLayerTest):

	layer = InstructedCourseApplicationTestLayer

	default_origin = b'http://janux.ou.edu'

	course_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'
	course_url = '/dataserver2/%2B%2Betc%2B%2Bhostsites/platform.ou.edu/%2B%2Betc%2B%2Bsite/Courses/Fall2015/CS%201323'
	assets_url = course_url + '/assets'

	def _load_resource(self, name):
		path = os.path.join(os.path.dirname(__file__), name)
		with open(path, "r") as fp:
			source = simplejson.loads(prepare_json_text(fp.read()))
		return source

	def _check_containers(self, course, pacakges=True, items=()):
		for item in items or ():
			ntiid = item.ntiid
			container = IPresentationAssetContainer(course)
			assert_that(container, has_key(ntiid))

			if pacakges:
				packs = course.ContentPackageBundle.ContentPackages
				container = IPresentationAssetContainer(packs[0])
				assert_that(container, has_key(ntiid))

	@WithSharedApplicationMockDS(testapp=True, users=True)
	def test_ntivideo(self):
		source = self._load_resource('ntivideo.json')
		source.pop('NTIID', None)
		
		# post
		res = self.testapp.post_json(self.assets_url, source, status=201)
		assert_that(res.json_body, has_entry('ntiid', is_not(none())))
		assert_that(res.json_body, has_entry('href', is_not(none())))
		with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
			ntiid = res.json_body['ntiid']
			href = res.json_body['href']
			obj = find_object_with_ntiid(ntiid)
			assert_that(obj, is_not(none()))
			assert_that(obj, validly_provides(INTIVideo))
			assert_that(obj, has_property('description', is_('Human')))
			
			entry = find_object_with_ntiid(self.course_ntiid)
			course = ICourseInstance(entry)
			self._check_containers(course, (obj,))

			catalog = get_library_catalog()
			containers = catalog.get_containers(obj)
			assert_that(containers, has_length(greater_than(1)))
		
		# put
		source = self._load_resource('ntivideo.json')
		source['description'] = 'Human/Quincy'
		res = self.testapp.put_json(href, source, status=200)
		with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
			ntiid = res.json_body['ntiid']
			obj = find_object_with_ntiid(ntiid)
			assert_that(obj, has_property('description', is_('Human/Quincy')))

	@WithSharedApplicationMockDS(testapp=True, users=True)
	def test_slidedeck(self):
		source = self._load_resource('ntislidedeck.json')
		res = self.testapp.post_json(self.assets_url, source, status=201)
		assert_that(res.json_body, has_entry('ntiid', is_not(none())))
		with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
			ntiid = res.json_body['ntiid']
			href = res.json_body['href']
			obj = find_object_with_ntiid(ntiid)
			assert_that(obj, is_not(none()))
			assert_that(obj, has_property('locked', is_(True)))
			assert_that(obj, validly_provides(INTISlideDeck))
			assert_that(obj, has_property('title', is_('Install Software on a Macintosh')))
			
			entry = find_object_with_ntiid(self.course_ntiid)
			course = ICourseInstance(entry)

			items = chain(obj.Slides, obj.Videos, (obj,))
			self._check_containers(course, items)
			
		# put
		source = self._load_resource('ntislidedeck.json')
		source['title'] = 'Install Software on a MAC'
		res = self.testapp.put_json(href, source, status=200)
		with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
			ntiid = res.json_body['ntiid']
			obj = find_object_with_ntiid(ntiid)
			assert_that(obj, has_property('locked', is_(True)))
			assert_that(obj, has_property('title', is_('Install Software on a MAC')))
			history  = ITransactionRecordHistory(obj)
			assert_that(history, has_length(1))

	@WithSharedApplicationMockDS(testapp=True, users=True)
	def test_post_overview_group(self):
		source = self._load_resource('nticourseoverviewgroup.json')
		res = self.testapp.post_json(self.assets_url, source, status=201)
		assert_that(res.json_body, has_entry('ntiid', is_not(none())))
		with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
			ntiid = res.json_body['ntiid']
			obj = find_object_with_ntiid(ntiid)
			assert_that(obj, is_not(none()))
			assert_that(obj, validly_provides(INTICourseOverviewGroup))
			assert_that(obj, has_property('Items', has_length(2)))

			entry = find_object_with_ntiid(self.course_ntiid)
			course = ICourseInstance(entry)
			self._check_containers(course, False, obj.Items)

	@WithSharedApplicationMockDS(testapp=True, users=True)
	def test_post_lesson(self):
		source = self._load_resource('ntilessonoverview.json')
		source.pop('NTIID', None)
		res = self.testapp.post_json(self.assets_url, source, status=201)
		assert_that(res.json_body, has_entry('ntiid', is_not(none())))
		with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
			ntiid = res.json_body['ntiid']
			obj = find_object_with_ntiid(ntiid)
			assert_that(obj, is_not(none()))
			assert_that(obj, validly_provides(INTILessonOverview))
			assert_that(obj, has_property('Items', has_length(1)))

			entry = find_object_with_ntiid(self.course_ntiid)
			course = ICourseInstance(entry)
			self._check_containers(course, False, obj.Items)

			catalog = get_library_catalog()
			containers = catalog.get_containers(obj.Items[0])
			assert_that(ntiid, is_in(containers))
