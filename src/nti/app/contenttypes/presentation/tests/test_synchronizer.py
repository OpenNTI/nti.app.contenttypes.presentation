#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import same_instance

from nti.testing.matchers import validly_provides

import os

from zope import component
from zope.intid import IIntIds

from nti.contentlibrary.indexed_data import get_catalog

from nti.contenttypes.presentation.group import NTICourseOverViewGroup

from nti.contenttypes.presentation.media import NTIVideo
from nti.contenttypes.presentation.media import NTIVideoRoll

from nti.contenttypes.presentation.interfaces import INTIVideoRef
from nti.contenttypes.presentation.interfaces import INTIVideoRoll
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup

from nti.app.contenttypes.presentation.synchronizer import _removed_registered
from nti.app.contenttypes.presentation.synchronizer import _index_overview_items
from nti.app.contenttypes.presentation.synchronizer import _load_and_register_lesson_overview_json

from nti.app.contenttypes.presentation.tests import PersistentComponents

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans
import nti.dataserver.tests.mock_dataserver as mock_dataserver

def _remove_from_registry(container_ntiids=None, provided=None, registry=None):
	result = []
	catalog = get_catalog()
	intids = component.queryUtility(IIntIds)
	for utility in catalog.search_objects(intids=intids, provided=provided,
										  container_ntiids=container_ntiids ):
		try:
			ntiid = utility.ntiid
			if ntiid:
				result.append(utility)
				_removed_registered(provided,
									name=ntiid,
									intids=intids,
									catalog=catalog,
									registry=registry)
		except AttributeError:
			pass
	return result

class TestSynchronizer(ApplicationLayerTest):

	@WithMockDSTrans
	def test_lesson_overview(self):
		path = os.path.join(os.path.dirname(__file__), 'lesson_overview.json')
		with open(path, "r") as fp:
			source = fp.read()

		registry = PersistentComponents()
		mock_dataserver.current_transaction.add(registry)

		result, removed = _load_and_register_lesson_overview_json(source, registry=registry)
		assert_that(result, is_not(none()))
		assert_that(removed, has_length(0))

		_index_overview_items((result,), container_ntiids='xxx')

		result = _remove_from_registry(container_ntiids='xxx',
									   provided=INTICourseOverviewGroup,
									   registry=registry)
		assert_that(result, has_length(4))

		result = _remove_from_registry(container_ntiids='xxx',
									   provided=INTILessonOverview,
									   registry=registry)
		assert_that(result, has_length(1))

	@WithMockDSTrans
	def test_sync_twice_lesson_overview(self):
		path = os.path.join(os.path.dirname(__file__), 'lesson_overview.json')
		with open(path, "r") as fp:
			source = fp.read()

		registry = PersistentComponents()
		mock_dataserver.current_transaction.add(registry)

		_, removed = _load_and_register_lesson_overview_json(source, registry=registry)
		assert_that(removed, has_length(0))
		_, removed = _load_and_register_lesson_overview_json(source, registry=registry)
		assert_that(removed, has_length(15))

	@WithMockDSTrans
	def test_lesson_sync_with_locks(self):
		"""
		Test lesson synchronization with locked children in the tree. Any
		locked child will keep the lesson from being synced from disk.
		"""
		path = os.path.join(os.path.dirname(__file__), 'lesson_overview.json')
		with open(path, "r") as fp:
			source = fp.read()

		registry = PersistentComponents()
		mock_dataserver.current_transaction.add(registry)
		original_overview, removed = _load_and_register_lesson_overview_json(source, registry=registry)
		assert_that(original_overview.items, has_length( 4 ))
		assert_that( removed, has_length( 0 ))

		def _get_lesson_video_group( my_overview ):
			return my_overview.items[-1]

		# 0. Sync gives us a roll by default.
		video_group = _get_lesson_video_group( original_overview )
		assert_that( video_group, has_length( 1 ) )
		roll_one = video_group[0]
		assert_that( roll_one, has_length( 2 ))
		assert_that( roll_one, validly_provides( INTIVideoRoll ))
		assert_that( roll_one[0], validly_provides( INTIVideoRef ))
		assert_that( roll_one[1], validly_provides( INTIVideoRef ))

		# 1. Insert new locked roll
		new_roll = NTIVideoRoll()
		new_roll.lock(False)
		video_group.append( new_roll )

		overview, removed = _load_and_register_lesson_overview_json(source, registry=registry)
		assert_that( overview.items, has_length( 4 ))
		assert_that( overview, same_instance( original_overview ))
		assert_that( removed, has_length( 0 ))
		video_group = _get_lesson_video_group( overview )
		assert_that( video_group, has_length( 2 ) )
		roll_one = video_group[0]
		roll_two = video_group[1]
		assert_that( roll_one, has_length( 2 ))
		for roll_item in roll_one.items:
			assert_that( roll_item, validly_provides( INTIVideoRef ))
		assert_that( roll_two, has_length( 0 ))

		# 2. New video in original roll, index zero.
		new_roll.unlock(False)
		new_video = NTIVideo()
		new_video.lock(False)
		new_video.title = new_video_title = 'my new video'
		roll_one.insert( 0, new_video )

		overview, removed = _load_and_register_lesson_overview_json(source, registry=registry)
		assert_that( overview.items, has_length( 4 ))
		assert_that( removed, has_length( 0 ))
		assert_that( overview, same_instance( original_overview ))
		video_group = _get_lesson_video_group( overview )
		assert_that( video_group, has_length( 2 ) )
		roll_one = video_group[0]
		roll_two = video_group[1]
		assert_that( roll_one, has_length( 3 ))
		assert_that( roll_one[0].title, is_( new_video_title ))
		assert_that( roll_two, has_length( 0 ))

		# 3. New roll at index zero. The original sync video roll
		# retains it's videos.
		new_video.unlock(False)
		new_roll2 = NTIVideoRoll()
		new_roll2.lock(False)
		video_group.insert( 0, new_roll2 )

		overview, removed = _load_and_register_lesson_overview_json(source, registry=registry)
		assert_that( overview.items, has_length( 4 ))
		assert_that( removed, has_length( 0 ))
		assert_that( overview, same_instance( original_overview ))
		video_group = _get_lesson_video_group( overview )
		assert_that( video_group, has_length( 3 ) )
		roll_zero = video_group[0]
		roll_one = video_group[1]
		roll_two = video_group[-1]
		assert_that( roll_zero, has_length( 0 ))
		assert_that( roll_one, has_length( 3 ))
		assert_that( roll_one[0].title, is_( new_video_title ))
		assert_that( roll_two, has_length( 0 ))

		# 4. User moves a video from one roll to another.
		new_roll2.unlock(False)
		moved_video = roll_one[-1]
		moved_video.lock(False)
		roll_zero.append( moved_video )
		roll_one.remove( moved_video )

		overview, removed = _load_and_register_lesson_overview_json(source, registry=registry)
		assert_that( overview.items, has_length( 4 ))
		assert_that( removed, has_length( 0 ))
		assert_that( overview, same_instance( original_overview ))
		video_group = _get_lesson_video_group( overview )
		assert_that( video_group, has_length( 3 ) )
		roll_zero = video_group[0]
		roll_one = video_group[1]
		roll_two = video_group[-1]
		assert_that( roll_zero, has_length( 1 ))
		assert_that( roll_one, has_length( 2 ))
		assert_that( roll_one[0].title, is_( new_video_title ))
		assert_that( roll_two, has_length( 0 ))

		# 5. Overview group added
		moved_video.unlock(False)
		new_group = NTICourseOverViewGroup()
		new_group.lock(False)
		overview.append( new_group )

		overview, removed = _load_and_register_lesson_overview_json(source, registry=registry)
		assert_that( overview.items, has_length( 5 ))
		assert_that( removed, has_length( 0 ))
		assert_that( overview, is_( original_overview ))

		# 6. Child order lock group.
		new_group.unlock(False)
		new_group.child_order_lock(False)
		overview, removed = _load_and_register_lesson_overview_json(source, registry=registry)
		assert_that( overview.items, has_length( 5 ))
		assert_that( removed, has_length( 0 ))
		assert_that( overview, is_( original_overview ))

		# 7. Child order lock lesson.
		new_group.child_order_unlock(False)
		original_overview.child_order_lock(False)
		overview, removed = _load_and_register_lesson_overview_json(source, registry=registry)
		assert_that( overview.items, has_length( 5 ))
		assert_that( removed, has_length( 0 ))
		assert_that( overview, is_( original_overview ))

		# 8. Unlock and wipe
		original_overview.child_order_unlock(False)
		overview, removed = _load_and_register_lesson_overview_json(source, registry=registry)
		assert_that( overview.items, has_length( 4 ))
		assert_that( removed, has_length( 15 ))
		assert_that( overview, is_not( same_instance( original_overview )))
