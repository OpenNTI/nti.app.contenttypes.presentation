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
does_not = is_not

import fudge

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

from nti.externalization.externalization import to_external_object

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.recorder.interfaces import ITransactionRecordHistory

from nti.app.testing.decorators import WithSharedApplicationMockDS
from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.dataserver.tests import mock_dataserver

from nti.app.products.courseware.tests import InstructedCourseApplicationTestLayer

from nti.app.contenttypes.presentation import VIEW_NODE_MOVE

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
	def test_all_assets(self):
		res = self.testapp.get(self.assets_url, status=200)
		assert_that(res.json_body, has_entry('Total', is_(5)))
		assert_that(res.json_body, has_entry('Items', has_length(5)))

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

			source = to_external_object(obj)

		# put
		source['description'] = 'Human/Quincy'
		res = self.testapp.put_json(href, source, status=200)
		with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
			obj = find_object_with_ntiid(ntiid)
			assert_that(obj, has_property('description', is_('Human/Quincy')))

		# delete
		res = self.testapp.delete(href, status=204)
		with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
			obj = find_object_with_ntiid(ntiid)
			assert_that(obj, is_(none()))

			entry = find_object_with_ntiid(self.course_ntiid)
			course = ICourseInstance(entry)
			container = IPresentationAssetContainer(course)
			assert_that(container, does_not(has_key(ntiid)))

	@WithSharedApplicationMockDS(testapp=True, users=True)
	def test_slidedeck(self):
		source = self._load_resource('ntislidedeck.json')

		# post
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

			source = to_external_object(obj)

		# put
		source['title'] = 'Install Software on a MAC'
		res = self.testapp.put_json(href, source, status=200)
		with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
			obj = find_object_with_ntiid(ntiid)
			assert_that(obj, has_property('locked', is_(True)))
			assert_that(obj, has_property('title', is_('Install Software on a MAC')))
			history  = ITransactionRecordHistory(obj)
			assert_that(history, has_length(2))

	@WithSharedApplicationMockDS(testapp=True, users=True)
	@fudge.patch('nti.app.contenttypes.presentation.views.asset_views.CourseOverviewGroupOrderedContentsView.readInput',
				 'nti.app.contenttypes.presentation.views.asset_views.get_assets_folder',
				 'nti.app.contenttypes.presentation.views.asset_views.get_render_link')
	def test_overview_group(self, mc_ri, mc_gaf, mc_lnk):
		source = self._load_resource('nticourseoverviewgroup.json')

		# post
		res = self.testapp.post_json(self.assets_url, source, status=201)
		assert_that(res.json_body, has_entry('ntiid', is_not(none())))
		with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
			ntiid = res.json_body['ntiid']
			href = res.json_body['href']
			obj = find_object_with_ntiid(ntiid)
			assert_that(obj, is_not(none()))
			assert_that(obj, validly_provides(INTICourseOverviewGroup))
			assert_that(obj, has_property('Items', has_length(2)))

			entry = find_object_with_ntiid(self.course_ntiid)
			course = ICourseInstance(entry)
			self._check_containers(course, False, obj.Items)

			source = to_external_object(obj)

		# put
		source['Items'] = [source['Items'][1]]
		res = self.testapp.put_json(href, source, status=200)
		with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
			obj = find_object_with_ntiid(ntiid)
			assert_that(obj, has_property('locked', is_(True)))
			assert_that(obj, has_property('Items', has_length(1)))
			history  = ITransactionRecordHistory(obj)
			assert_that(history, has_length(2))

		# contents
		source = self._load_resource('relatedwork.json')
		source.pop('ntiid', None)
		assert_that(source, has_entry('icon','http://bleach.com/aizen.jpg'))

		mc_ri.is_callable().with_args().returns(source)
		mc_gaf.is_callable().with_args().returns({})
		mc_lnk.is_callable().with_args().returns('http://bleach.org/ichigo.png')

		contents_url = href + '/@@contents'
		res = self.testapp.post(contents_url,
								upload_files=[('icon', 'ichigo.png', b'ichigo')],
								status=201)
		with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
			# check returned object
			assert_that(res.json_body, has_entry('icon', 'http://bleach.org/ichigo.png'))

			obj = find_object_with_ntiid(ntiid)
			rel_ntiid = res.json_body['ntiid']
			assert_that(obj, has_property('Items', has_length(2)))
			assert_that( obj.Items[-1].ntiid, is_( rel_ntiid ))
			history  = ITransactionRecordHistory(obj)
			assert_that(history, has_length(3))

			obj = find_object_with_ntiid(rel_ntiid)
			catalog = get_library_catalog()
			containers = catalog.get_containers(obj)
			assert_that(ntiid, is_in(containers))

		# Insert at index 0
		res = self.testapp.post_json(contents_url + '/index/0',
									upload_files=[('icon', 'ichigo.png', b'ichigo')],
									status=201)
		with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
			obj = find_object_with_ntiid(ntiid)
			rel_ntiid = res.json_body['ntiid']
			assert_that(obj, has_property('Items', has_length(3)))
			assert_that( obj.Items[0].ntiid, is_( rel_ntiid ))
			history  = ITransactionRecordHistory(obj)
			assert_that(history, has_length(4))

			obj = find_object_with_ntiid(rel_ntiid)
			catalog = get_library_catalog()
			containers = catalog.get_containers(obj)
			assert_that(ntiid, is_in(containers))

	@WithSharedApplicationMockDS(testapp=True, users=True)
	def test_lesson(self):
		source = self._load_resource('ntilessonoverview.json')
		source.pop('NTIID', None)

		# post
		res = self.testapp.post_json(self.assets_url, source, status=201)
		assert_that(res.json_body, has_entry('ntiid', is_not(none())))

		with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
			ntiid = res.json_body['ntiid']
			href = res.json_body['href']
			obj = find_object_with_ntiid(ntiid)
			assert_that(obj, is_not(none()))
			assert_that(obj, validly_provides(INTILessonOverview))
			assert_that(obj, has_property('Items', has_length(1)))
			group_ntiid = obj.Items[0].ntiid

			entry = find_object_with_ntiid(self.course_ntiid)
			course = ICourseInstance(entry)
			self._check_containers(course, False, obj.Items)

			catalog = get_library_catalog()
			containers = catalog.get_containers(obj.Items[0])
			assert_that(ntiid, is_in(containers))

			source = to_external_object(obj)

		# remove ntiid to fake a new group
		source['Items'][0].pop('ntiid', None)
		source['Items'][0].pop('NTIID', None)
		res = self.testapp.put_json(href, source, status=200)
		with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
			obj = find_object_with_ntiid(ntiid)
			old_group = find_object_with_ntiid(group_ntiid)
			assert_that(old_group, is_(none()))
			assert_that(obj, has_property('Items', has_length(1)))
			history  = ITransactionRecordHistory(obj)
			assert_that(history, has_length(2))

		# contents, insert group at end
		source = {'title':'mygroup'}
		contents_url = href + '/@@contents'
		res = self.testapp.post_json(contents_url, source, status=201)
		with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
			obj = find_object_with_ntiid(ntiid)
			group_ntiid = res.json_body['ntiid']
			assert_that(obj, has_property('Items', has_length(2)))
			assert_that( obj.Items[-1].ntiid, is_( group_ntiid ))
			history = ITransactionRecordHistory(obj)
			assert_that(history, has_length(3))

			obj = find_object_with_ntiid(group_ntiid)
			catalog = get_library_catalog()
			containers = catalog.get_containers(obj)
			assert_that(ntiid, is_in(containers))

		# Insert group at index 0
		res = self.testapp.post_json(contents_url + '/index/0', source, status=201)
		with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
			obj = find_object_with_ntiid(ntiid)
			group_ntiid = res.json_body['ntiid']
			assert_that(obj, has_property('Items', has_length(3)))
			assert_that( obj.Items[0].ntiid, is_( group_ntiid ))

			obj = find_object_with_ntiid(group_ntiid)
			catalog = get_library_catalog()
			containers = catalog.get_containers(obj)
			assert_that(ntiid, is_in(containers))

	def _get_move_json(self, obj_ntiid, new_parent_ntiid, index=None, old_parent_ntiid=None):
		result = { 'ObjectNTIID': obj_ntiid,
					'ParentNTIID': new_parent_ntiid }
		if index is not None:
			result['Index'] = index
		if old_parent_ntiid is not None:
			result['OldParentNTIID'] = old_parent_ntiid
		return result

	@WithSharedApplicationMockDS(testapp=True, users=True)
	def test_moves(self):
		source = self._load_resource('lesson_overview.json')
		# Remove all NTIIDs so things get registered.
		def _remove_ntiids( obj ):
			obj.pop( 'NTIID', None )
			for item in obj.get( 'Items', () ):
				_remove_ntiids( item )
		_remove_ntiids( source )
		res = self.testapp.post_json(self.assets_url, source, status=201)
		res = res.json_body

		move_link = self.require_link_href_with_rel( res, VIEW_NODE_MOVE )
		lesson_ntiid = res.get( 'NTIID' )
		lesson_url = '/dataserver2/Objects/%s' % lesson_ntiid
		groups = res.get( 'Items' )
		original_group_count = len( groups )
		first_group_ntiid = groups[0].get( 'NTIID' )
		last_group_ntiid = groups[-1].get( 'NTIID' )

		# Move our last item to first
		move_data = self._get_move_json(last_group_ntiid, lesson_ntiid, 0, lesson_ntiid)
		self.testapp.post_json( move_link, move_data )

		res = self.testapp.get( lesson_url )
		res = res.json_body
		groups = res.get( 'Items' )
		assert_that( groups, has_length( original_group_count ))
		assert_that( groups[0].get( 'NTIID' ), is_( last_group_ntiid ))
		assert_that( groups[1].get( 'NTIID' ), is_( first_group_ntiid ))
		assert_that( groups[-1].get( 'NTIID' ), is_not( first_group_ntiid ))

		# Move the item back to the end
		move_data = self._get_move_json(last_group_ntiid, lesson_ntiid)
		self.testapp.post_json( move_link, move_data )

		res = self.testapp.get( lesson_url )
		res = res.json_body
		groups = res.get( 'Items' )
		assert_that( groups, has_length( original_group_count ))
		assert_that( groups[0].get( 'NTIID' ), is_( first_group_ntiid ))
		assert_that( groups[-1].get( 'NTIID' ), is_( last_group_ntiid ))

		# Overview groups
		source_group_index = 0
		target_group_index = 3
		source_group = groups[ source_group_index ]
		source_group_ntiid = source_group.get( 'NTIID' )
		target_group = groups[ target_group_index ]
		target_group_ntiid = target_group.get( 'NTIID' )
		group_items = source_group.get( 'Items' )
		original_source_group_size = len( group_items )
		original_target_group_size = len( target_group.get( 'Items' ) )
		first_asset_ntiid = group_items[0].get( 'NTIID' )
		last_asset_ntiid = group_items[-1].get( 'NTIID' )

		# Move within an overview group
		move_data = self._get_move_json(first_asset_ntiid, source_group_ntiid)
		self.testapp.post_json( move_link, move_data )

		res = self.testapp.get( lesson_url )
		res = res.json_body
		groups = res.get( 'Items' )
		assert_that( len( groups ), is_( original_group_count ))
		new_source_group = groups[ source_group_index ]
		new_source_group_items = new_source_group.get( 'Items' )
		assert_that( new_source_group_items, has_length( original_source_group_size ))
		assert_that( new_source_group_items[-2].get( 'NTIID' ), is_( last_asset_ntiid ))
		assert_that( new_source_group_items[-1].get( 'NTIID' ), is_( first_asset_ntiid ))

		# Move between overview groups
		move_data = self._get_move_json(first_asset_ntiid, target_group_ntiid, 0, source_group_ntiid)
		self.testapp.post_json( move_link, move_data )

		res = self.testapp.get( lesson_url )
		res = res.json_body
		groups = res.get( 'Items' )
		assert_that( len( groups ), is_( original_group_count ))
		new_source_group = groups[ source_group_index ]
		new_target_group = groups[ target_group_index ]
		new_source_group_items = new_source_group.get( 'Items' )
		new_target_group_items = new_target_group.get( 'Items' )
		assert_that( new_source_group_items, has_length( original_source_group_size - 1 ))
		assert_that( new_target_group_items, has_length( original_target_group_size + 1 ))
		assert_that( new_source_group_items[-1].get( 'NTIID' ), is_not( first_asset_ntiid ))
		assert_that( new_target_group_items[0].get( 'NTIID' ), is_( first_asset_ntiid ))

		# Move back to original group
		move_data = self._get_move_json(first_asset_ntiid, source_group_ntiid, 0, target_group_ntiid )
		self.testapp.post_json( move_link, move_data )

		res = self.testapp.get( lesson_url )
		res = res.json_body
		groups = res.get( 'Items' )
		assert_that( len( groups ), is_( original_group_count ))
		new_source_group = groups[ source_group_index ]
		new_target_group = groups[ target_group_index ]
		new_source_group_items = new_source_group.get( 'Items' )
		new_target_group_items = new_target_group.get( 'Items' )
		assert_that( new_source_group_items, has_length( original_source_group_size ))
		assert_that( new_target_group_items, has_length( original_target_group_size ))
		assert_that( new_source_group_items[0].get( 'NTIID' ), is_( first_asset_ntiid ))
		assert_that( new_target_group_items[0].get( 'NTIID' ), is_not( first_asset_ntiid ))
