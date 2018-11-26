#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import has_key
from hamcrest import contains
from hamcrest import not_none
from hamcrest import has_item
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_property
from hamcrest import same_instance
from hamcrest import contains_inanyorder
from hamcrest import greater_than_or_equal_to
does_not = is_not

from nti.testing.matchers import validly_provides

import fudge

import os
from itertools import chain

import simplejson

from zope import component

from zope.intid.interfaces import IIntIds

from nti.app.contenttypes.presentation import VIEW_NODE_MOVE
from nti.app.contenttypes.presentation import VIEW_ORDERED_CONTENTS
from nti.app.contenttypes.presentation import VIEW_LESSON_REMOVE_REFS

from nti.app.contentfolder.resources import is_internal_file_link

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.calendar.interfaces import ICalendar

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance

from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTIVideoRef
from nti.contenttypes.presentation.interfaces import INTIVideoRoll
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTITimelineRef
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTICalendarEventRef
from nti.contenttypes.presentation.interfaces import INTICourseOverviewGroup
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.contenttypes.presentation.interfaces import TRX_ASSET_MOVE_TYPE
from nti.contenttypes.presentation.interfaces import TRX_OVERVIEW_GROUP_MOVE_TYPE

from nti.contenttypes.presentation.media import NTIVideoRoll

from nti.contenttypes.presentation.timeline import NTITimeLine

from nti.contenttypes.presentation.utils import prepare_json_text

from nti.externalization.externalization import to_external_object

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.recorder.interfaces import ITransactionRecordHistory

from nti.app.contenttypes.calendar.entity.model import UserCalendarEvent

from nti.app.contenttypes.presentation.tests import INVALID_TITLE_LENGTH

from nti.app.products.courseware.calendar.model import CourseCalendarEvent

from nti.app.products.courseware.tests import InstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver

from nti.ntiids.oids import to_external_ntiid_oid

INVALID_TITLE = 'x' * INVALID_TITLE_LENGTH


class TestAssetViews(ApplicationLayerTest):

    layer = InstructedCourseApplicationTestLayer

    default_origin = b'http://platform.ou.edu'

    course_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'
    course_url = '/dataserver2/%2B%2Betc%2B%2Bhostsites/platform.ou.edu/%2B%2Betc%2B%2Bsite/Courses/Fall2015/CS%201323'
    assets_url = course_url + '/assets'

    @property
    def intids(self):
        return component.getUtility(IIntIds)

    @property
    def _media_href(self):
        res = self.testapp.get(self.course_url)
        res = self.require_link_href_with_rel(
            res.json_body, 'MediaByOutlineNode')
        return res

    def _media_by_outline(self):
        return self.testapp.get(self._media_href).json_body

    def _load_resource(self, name):
        path = os.path.join(os.path.dirname(__file__), name)
        with open(path, "r") as fp:
            source = simplejson.loads(prepare_json_text(fp.read()))
        return source

    def _check_containers(self, course, packages=True, items=()):
        for item in items or ():
            ntiid = item.ntiid
            container = IPresentationAssetContainer(course)
            assert_that(container, has_key(ntiid))

            if packages:
                packs = course.ContentPackageBundle.ContentPackages
                container = IPresentationAssetContainer(packs[0])
                assert_that(container, has_key(ntiid))

    def _check_container_index(self, obj, container_ids=None, packages=False, course=True):
        """
        Validate the container index for the given object.
        """
        catalog = get_library_catalog()
        containers = catalog.get_containers(obj)

        # For convenience, we pop any subinstances in our containers. Stuff
        # sync'd from disk will have all subinstances (when the outline is
        # shared); API created items will not. TODO: Is this correct?
        for container_id in tuple(containers):
            container_obj = find_object_with_ntiid(container_id)
            container_course = ICourseInstance(container_obj, None)
            if ICourseSubInstance.providedBy(container_course):
                containers.discard(container_id)

        expected_containers = []
        if course:
            expected_containers.append(self.course_ntiid)

        package_ids = ()
        if packages:
            entry = find_object_with_ntiid(self.course_ntiid)
            course = ICourseInstance(entry)
            package_ids = [
                x.ntiid for x in course.ContentPackageBundle.ContentPackages
            ]
        if container_ids:
            expected_containers.extend(container_ids)
        expected_containers.extend(package_ids)
        assert_that(containers, contains_inanyorder(*expected_containers))

        # Validate intid (must have an intid to be indexed anyway).
        assert_that(self.intids.queryId(obj), not_none())

    def _test_transaction_history(self, obj, *args):
        # Call within a ds transaction
        history = ITransactionRecordHistory(obj)
        record_types = [x.type for x in history.records()]
        for record_type in args:
            assert_that(record_types, has_item(record_type))

    def _get_delete_url_suffix(self, index, ntiid):
        return '/ntiid/%s?index=%s' % (ntiid, index)

    def _get_non_perm_environ(self):
        with mock_dataserver.mock_db_trans(self.ds):
            username = 'quentin_coldwater'
            self._create_user(username)
        return self._make_extra_environ(username)

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_all_assets(self):
        res = self.testapp.get(self.assets_url, status=200)
        assert_that(res.json_body, has_entry('Total', is_(1894)))
        assert_that(res.json_body, has_entry('Items', has_length(1894)))

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
            assert_that(obj.__parent__, not_none())

            entry = find_object_with_ntiid(self.course_ntiid)
            course = ICourseInstance(entry)
            self._check_containers(course, items=(obj,), packages=False)
            self._check_container_index(obj, packages=False)

            source = to_external_object(obj)

        # Permissions
        non_perm_env = self._get_non_perm_environ()
        self.testapp.get(href, extra_environ=non_perm_env, status=403)

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
    def test_video_roll_container(self):
        roll_source = self._load_resource('video_roll.json')

        res = self.testapp.post_json(self.assets_url, roll_source, status=201)
        res = res.json_body
        video_roll_ntiid = res.get('ntiid')
        assert_that(video_roll_ntiid, not_none())
        assert_that(res, has_entry('href', not_none()))

        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            roll_obj = find_object_with_ntiid(video_roll_ntiid)
            assert_that(roll_obj, not_none())
            assert_that(roll_obj, validly_provides(INTIVideoRoll))
            # assert_that(roll_obj.__parent__, not_none())

            entry = find_object_with_ntiid(self.course_ntiid)
            course = ICourseInstance(entry)
            self._check_containers(course, packages=False, items=(roll_obj,))

            self._check_container_index(roll_obj)
            self._check_containers(course,
                                   packages=False,
                                   items=roll_obj.Items)

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_video_roll(self):
        content_video_ntiid = 'tag:nextthought.com,2011-10:OU-NTIVideo-CS1323_F_2015_Intro_to_Computer_Programming.ntivideo.video_01.01.01_Obama'
        # Use existing overview group to check containers.
        group_ntiid = 'tag:nextthought.com,2011-10:OU-NTICourseOverviewGroup-CS1323_F_2015_Intro_to_Computer_Programming.lec:01.01_LESSON.0'
        res = self.testapp.get('/dataserver2/Objects/%s' % group_ntiid)
        res = res.json_body
        group_ntiid = res.get('ntiid')
        group_href = res.get('href')
        assert_that(res.get('Items'), has_length(1))
        original_group_item_ntiid = res['Items'][0]['ntiid']
        contents_link = self.require_link_href_with_rel(res,
                                                        VIEW_ORDERED_CONTENTS)

        media_res = self._media_by_outline()
        container_ntiid = media_res.get('ContainerOrder')[0]
        container_ntiids = media_res.get('Containers').get(container_ntiid)

        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            group = find_object_with_ntiid(group_ntiid)
            lesson_ntiid = group.__parent__.ntiid
            assert_that(group.child_order_locked, is_(False))
            for item in group:
                self._check_container_index(item, container_ids=(group_ntiid,
                                                                 lesson_ntiid))

        # Permissions
        non_perm_env = self._get_non_perm_environ()
        self.testapp.get(group_href, extra_environ=non_perm_env, status=403)

        # Create base video and video roll
        video_source = self._load_resource('ntivideo.json')
        video_source.pop('NTIID', None)
        res = self.testapp.post_json(self.assets_url, video_source, status=201)
        res = res.json_body
        video_href = res.get('href')
        video_ntiid = res.get('ntiid')

        # Video does not exist in MediaByOutlineNode
        assert_that(container_ntiids, does_not(has_item(video_ntiid)))

        # Post video to our ordered contents link
        video_source['ntiid'] = video_ntiid
        res = self.testapp.post_json(contents_link + '/index/0',
                                     video_source,
                                     status=201)
        res = res.json_body
        assert_that(res.get('MimeType'),
                    is_('application/vnd.nextthought.ntivideo'))
        assert_that(res.get('NTIID'), is_(video_ntiid))

        group_res = self.testapp.get(group_href)
        group_res = group_res.json_body
        assert_that(group_res.get('Items'), has_length(2))
        item_zero = group_res.get('Items')[0]
        assert_that(item_zero.get('ntiid'), is_(video_ntiid))
        assert_that(item_zero.get('MimeType'),
                    is_('application/vnd.nextthought.ntivideo'))

        # Now it's in our media container.
        media_res = self._media_by_outline()
        container_ntiids = media_res.get('Containers').get(container_ntiid)
        assert_that(container_ntiids, has_item(video_ntiid))

        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            group = find_object_with_ntiid(group_ntiid)
            assert_that(group.child_order_locked, is_(True))
            ref_obj = group.Items[0]
            assert_that(ref_obj.locked, is_(True))
            assert_that(ref_obj, validly_provides(INTIVideoRef))
            target_ntiid = ref_obj.target
            assert_that(target_ntiid, is_(video_ntiid))
            video_obj = find_object_with_ntiid(target_ntiid)
            assert_that(video_obj, validly_provides(INTIVideo))

            for item in group:
                self._check_container_index(item, container_ids=(group_ntiid,
                                                                 lesson_ntiid))

            # Reset child move status
            group.child_order_locked = False

        # Upload/append roll into group
        roll_source = {"MimeType": NTIVideoRoll.mime_type,
                       "Items": [video_ntiid]}
        res = self.testapp.post_json(contents_link, roll_source, status=201)
        res = res.json_body
        roll_href = res.get('href')
        video_roll_ntiid = res.get('ntiid')
        assert_that(roll_href, not_none())
        assert_that(res.get('MimeType'), is_(NTIVideoRoll.mime_type))
        assert_that(res.get('Items'), has_length(1))
        assert_that(res.get('Creator'), is_('sjohnson@nextthought.com'))
        roll_item_zero = res.get('Items')[0]
        roll_item_zero_ntiid = roll_item_zero.get('ntiid')
        assert_that(roll_item_zero.get('MimeType'),
                    is_('application/vnd.nextthought.ntivideo'))

        group_res = self.testapp.get(group_href)
        group_res = group_res.json_body
        assert_that(group_res.get('Items'), has_length(3))
        item_zero = group_res.get('Items')[0]
        item_last = group_res.get('Items')[-1]
        assert_that(item_zero.get('ntiid'), is_(video_ntiid))
        assert_that(item_last.get('ntiid'), is_(video_roll_ntiid))
        assert_that(item_last.get('MimeType'), is_(NTIVideoRoll.mime_type))

        # Permissions
        self.testapp.get(roll_href, extra_environ=non_perm_env, status=403)

        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            # Check our objects are locked and are actually video(roll)
            # objects that can be found in course.
            group = find_object_with_ntiid(group_ntiid)
            assert_that(group.child_order_locked, is_(True))

            roll_obj = find_object_with_ntiid(video_roll_ntiid)
            assert_that(roll_obj, not_none())
            assert_that(roll_obj, validly_provides(INTIVideoRoll))

            # Since we insert into groups without a course,
            # containers will not work (?).
            # entry = find_object_with_ntiid(self.course_ntiid)
            # course = ICourseInstance(entry)
            # self._check_containers(course, items=(roll_obj,))
            # self._check_containers(course, packages=False, items=roll_obj.Items)

            self._check_container_index(roll_obj,
                                        container_ids=(group_ntiid, lesson_ntiid))

            assert_that(roll_obj.locked, is_(True))
            new_item = roll_obj.Items[0]

            assert_that(new_item, validly_provides(INTIVideoRef))
            assert_that(new_item.ntiid, is_not(new_item.target))
            assert_that(new_item.target, is_(video_ntiid))
            assert_that(new_item.locked, is_(True))

            # This doesn't use our request specific externalizer.
            to_external_object(roll_obj)

            # Reset child move status
            group.child_order_locked = False

        # Now append a video ntiid to video roll
        items = item_last.get('Items')
        items.append(video_ntiid)
        source = self._load_resource('nticourseoverviewgroup.json')
        source['Items'] = items
        res = self.testapp.put_json(roll_href, source, status=200)
        res = res.json_body

        roll_items = res.get('Items')
        assert_that(roll_items, has_length(2))
        video_ntiids = [x.get('NTIID') for x in roll_items]
        assert_that(video_ntiids, contains(roll_item_zero_ntiid, video_ntiid))
        assert_that(roll_items[0].get('NTIID'), is_(roll_item_zero_ntiid))
        assert_that(roll_items[0].get('MimeType'),
                    is_('application/vnd.nextthought.ntivideo'))
        assert_that(roll_items[1].get('NTIID'), is_(video_ntiid))
        assert_that(roll_items[1].get('MimeType'),
                    is_('application/vnd.nextthought.ntivideo'))

        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            roll_obj = find_object_with_ntiid(video_roll_ntiid)
            assert_that(roll_obj.locked, is_(True))
            for item in roll_obj.Items:
                assert_that(item.ntiid, is_not(item.target))
                assert_that(item, validly_provides(INTIVideoRef))
                self._check_container_index(item, container_ids=(video_roll_ntiid,
                                                                 group_ntiid,
                                                                 lesson_ntiid))

        # Now append another video ntiid to video roll, just on the ITEMS
        # field.
        items.append({"MimeType": "application/vnd.nextthought.ntivideo",
                                  "NTIID": video_ntiid})
        new_source = {}
        new_source['Items'] = items
        res = self.testapp.put_json(roll_href, new_source, status=200)
        res = res.json_body

        roll_items = res.get('Items')
        assert_that(roll_items, has_length(3))
        video_ntiids = [x.get('NTIID') for x in roll_items]
        assert_that(video_ntiids,
                    contains(roll_item_zero_ntiid, video_ntiid, video_ntiid))
        assert_that(roll_items[0].get('NTIID'), is_(roll_item_zero_ntiid))
        assert_that(roll_items[0].get('MimeType'),
                    is_('application/vnd.nextthought.ntivideo'))
        assert_that(roll_items[1].get('NTIID'), is_(video_ntiid))
        assert_that(roll_items[1].get('MimeType'),
                    is_('application/vnd.nextthought.ntivideo'))
        assert_that(roll_items[2].get('NTIID'), is_(video_ntiid))
        assert_that(roll_items[2].get('MimeType'),
                    is_('application/vnd.nextthought.ntivideo'))

        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            roll_obj = find_object_with_ntiid(video_roll_ntiid)
            assert_that(roll_obj.locked, is_(True))
            for item in roll_obj.Items:
                assert_that(item.ntiid, is_not(item.target))
                assert_that(item, validly_provides(INTIVideoRef))
                assert_that(item.locked, is_(True))
                assert_that(item.__parent__, not_none())
                self._check_container_index(item, container_ids=(video_roll_ntiid,
                                                                 group_ntiid,
                                                                 lesson_ntiid))

        # Insert new video ntiid into overview group
        res = self.testapp.post_json(self.assets_url, video_source, status=201)
        res = res.json_body
        new_video_ntiid = res.get('ntiid')
        new_video_href = res.get('href')
        res = self.testapp.post_json(contents_link,
                                     {'ntiid': new_video_ntiid}, status=201)
        res = res.json_body
        assert_that(res.get('ntiid'), is_(new_video_ntiid))
        assert_that(res.get('MimeType'),
                    is_('application/vnd.nextthought.ntivideo'))

        group_res = self.testapp.get(group_href)
        group_res = group_res.json_body
        assert_that(group_res.get('Items'), has_length(4))
        item_zero = group_res.get('Items')[0]
        item_roll = group_res.get('Items')[-2]
        item_last = group_res.get('Items')[-1]
        assert_that(item_zero.get('ntiid'), is_(video_ntiid))
        assert_that(item_roll.get('ntiid'), is_(video_roll_ntiid))
        assert_that(item_last.get('ntiid'), is_(new_video_ntiid))

        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            group = find_object_with_ntiid(group_ntiid)
            assert_that(group.child_order_locked, is_(True))
            for item in group:
                self._check_container_index(item, container_ids=(group_ntiid,
                                                                 lesson_ntiid))

        # Cannot have duplicate videos (by ntiid) in a group
        # self.testapp.post_json( contents_link, {'ntiid':new_video_ntiid}, status=422 )

        # Try to insert non-existant ntiid
        items.append(video_ntiid + 'xxx')
        self.testapp.put_json(roll_href, source, status=422)

        # Delete underlying video
        # Empty video roll is removed
        self.testapp.delete(video_href)
        group_res = self.testapp.get(group_href).json_body
        assert_that(group_res.get('Items'), has_length(2))
        first_item_ntiid = group_res.get('Items')[0]['ntiid']
        last_item_ntiid = group_res.get('Items')[1]['ntiid']
        assert_that(first_item_ntiid, is_(original_group_item_ntiid))
        assert_that(last_item_ntiid, is_(new_video_ntiid))

        # Now add a roll with new_video_ntiid
        # On new_video_ntiid deletion, video roll disappears
        roll_source = {"MimeType": NTIVideoRoll.mime_type,
                       "Items": [new_video_ntiid, content_video_ntiid]}
        self.testapp.post_json(contents_link, roll_source, status=201)
        self.testapp.delete(new_video_href)
        group_res = self.testapp.get(group_href).json_body
        assert_that(group_res.get('Items'), has_length(2))
        first_item_ntiid = group_res.get('Items')[0]['ntiid']
        last_item_ntiid = group_res.get('Items')[1]['ntiid']
        assert_that(first_item_ntiid, is_(original_group_item_ntiid))
        assert_that(last_item_ntiid, is_(content_video_ntiid))

        # Delete roll
        roll_source = {"MimeType": NTIVideoRoll.mime_type,
                       "Items": [content_video_ntiid]}
        res = self.testapp.post_json(contents_link, roll_source, status=201)
        res = res.json_body
        video_roll_href = res['href']
        video_roll_ntiid = res['ntiid']
        res = self.testapp.delete(video_roll_href, status=204)
        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            obj = find_object_with_ntiid(video_roll_ntiid)
            assert_that(obj, is_(none()))

            entry = find_object_with_ntiid(self.course_ntiid)
            course = ICourseInstance(entry)
            container = IPresentationAssetContainer(course)
            assert_that(container, does_not(has_key(video_roll_ntiid)))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_slidedeck_container(self):
        source = self._load_resource('ntislidedeck.json')

        # post
        res = self.testapp.post_json(self.assets_url, source, status=201)
        assert_that(res.json_body, has_entry('ntiid', is_not(none())))
        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            ntiid = res.json_body['ntiid']
            href = res.json_body['href']
            obj = find_object_with_ntiid(ntiid)
            assert_that(obj, not_none())
            assert_that(obj.__parent__, not_none())
            assert_that(obj, has_property('locked', is_(True)))
            assert_that(obj, validly_provides(INTISlideDeck))
            assert_that(obj,
                        has_property('title', is_('Install Software on a Macintosh')))

            entry = find_object_with_ntiid(self.course_ntiid)
            course = ICourseInstance(entry)

            items = chain(obj.Slides, obj.Videos, (obj,))
            self._check_containers(course, items=items, packages=False)
            mime_type = obj.mime_type
            source = to_external_object(obj)

        # Permissions
        non_perm_env = self._get_non_perm_environ()
        self.testapp.get(href, extra_environ=non_perm_env, status=403)

        # Change title
        res = self.testapp.put_json(href,
                                    {'title': 'Install Software on a MAC',
                                     'MimeType': mime_type},
                                    status=200)
        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            obj = find_object_with_ntiid(ntiid)
            assert_that(obj, has_property('locked', is_(True)))
            assert_that(obj,
                        has_property('title', is_('Install Software on a MAC')))
            history = ITransactionRecordHistory(obj)
            assert_that(history, has_length(2))
            # Only title shows up in history attributes.
            assert_that(tuple(history.records())[-1].attributes,
                        contains('title'))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_slidedeck(self):
        """
        Posting a slidedeck video to an overview group will expose
        our slidedeck in MediaByOutlineNode.
        """
        group_ntiid = 'tag:nextthought.com,2011-10:OU-NTICourseOverviewGroup-CS1323_F_2015_Intro_to_Computer_Programming.lec:01.01_LESSON.0'
        slide_video_ntiid = 'tag:nextthought.com,2011-10:OU-NTIVideo-CS1323_F_2015_Intro_to_Computer_Programming.ntivideo.video_02.01.02_How_to_Turingscraft'
        slide_deck_ntiid = 'tag:nextthought.com,2011-10:OU-NTISlideDeck-CS1323_F_2015_Intro_to_Computer_Programming.nsd.pres:How_To_Use_Turingscraft'
        res = self.testapp.get('/dataserver2/Objects/%s' % group_ntiid)
        res = res.json_body
        group_ntiid = res.get('ntiid')
        assert_that(res.get('Items'), has_length(1))
        contents_link = self.require_link_href_with_rel(res,
                                                        VIEW_ORDERED_CONTENTS)

        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            slide_deck = find_object_with_ntiid(slide_deck_ntiid)
            content_node = find_object_with_ntiid(
                group_ntiid).__parent__.__parent__
            content_ntiid = content_node.ContentNTIID
            catalog = get_library_catalog()
            original_containers = catalog.get_containers(slide_deck)
            containers = (
                'tag:nextthought.com,2011-10:OU-HTML-CS1323_F_2015_Intro_to_Computer_Programming.lec:02.02_LESSON',
            )
            catalog.remove_containers(slide_deck, containers=containers)

        # Empty
        media_res = self._media_by_outline()
        assert_that(media_res.get('Items').get(slide_deck_ntiid), none())

        # Insert
        res = self.testapp.post_json(contents_link + '/index/0',
                                     {'ntiid': slide_video_ntiid}, status=201)

        # Not empty
        media_res = self._media_by_outline()
        assert_that(media_res.get('Items').get(slide_deck_ntiid), not_none())
        assert_that(media_res.get('Containers'), has_entry(content_ntiid,
                                                           has_item(slide_deck_ntiid)))

        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            # Revert state
            slide_deck = find_object_with_ntiid(slide_deck_ntiid)
            catalog = get_library_catalog()
            catalog.update_containers(
                slide_deck, containers=original_containers)

    @WithSharedApplicationMockDS(testapp=True, users=True)
    @fudge.patch('nti.app.contenttypes.presentation.views.asset_views.CourseOverviewGroupInsertView.readInput',
                 'nti.app.contenttypes.presentation.views.asset_views.get_course_filer')
    def test_overview_group(self, mc_ri, mc_cf):
        source = self._load_resource('nticourseoverviewgroup.json')
        video_source = source.get('Items')[1]
        video_res = self.testapp.post_json(self.assets_url,
                                           video_source, status=201)
        video_ntiid = video_res.json_body.get('ntiid')
        source.get('Items')[1]['NTIID'] = video_ntiid

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
            self._check_container_index(obj)

            entry = find_object_with_ntiid(self.course_ntiid)
            course = ICourseInstance(entry)
            self._check_containers(course, False, obj.Items)

            source = to_external_object(obj)

        # Permissions
        non_perm_env = self._get_non_perm_environ()
        self.testapp.get(href, extra_environ=non_perm_env, status=403)

        # put
        source['Items'] = [source['Items'][1]]
        res = self.testapp.put_json(href, source, status=200)
        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            obj = find_object_with_ntiid(ntiid)
            assert_that(obj, has_property('locked', is_(True)))
            assert_that(obj, has_property('Items', has_length(1)))
            self._check_container_index(obj)
            history = ITransactionRecordHistory(obj)
            assert_that(history, has_length(2))

        # contents
        source = self._load_resource('relatedwork.json')
        source.pop('ntiid', None)
        assert_that(source,
                    has_entry('icon', 'http://bleach.com/aizen.jpg'))

        mc_ri.is_callable().with_args().returns(source)

        class CF(object):

            def save(self, *args, **kwargs):
                return 'http://bleach.org/ichigo.png'

            def remove(self, *args, **kwargs):
                return True
        mc_cf.is_callable().with_args().returns(CF())

        contents_url = href + '/@@contents'
        res = self.testapp.post(contents_url,
                                upload_files=[
                                    ('icon', 'ichigo.png', b'ichigo')],
                                status=201)

        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            # check returned object
            assert_that(res.json_body,
                        has_entry('icon', 'http://bleach.org/ichigo.png'))

            obj = find_object_with_ntiid(ntiid)
            rel_ntiid = res.json_body['ntiid']
            assert_that(obj, has_property('Items', has_length(2)))

            history = ITransactionRecordHistory(obj)
            assert_that(history, has_length(3))
            self._check_container_index(obj)

            obj = find_object_with_ntiid(rel_ntiid)
            # Our group does not adapt to a course (since no parent).
            self._check_container_index(obj,
                                        container_ids=(ntiid,),
                                        course=False)

        # Delete video from group; but asset still exists
        delete_suffix = self._get_delete_url_suffix(0, video_ntiid)
        self.testapp.delete(contents_url + delete_suffix)
        # No problem with multiple calls
        self.testapp.delete(contents_url + delete_suffix)
        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            obj = find_object_with_ntiid(ntiid)
            assert_that(obj, has_property('Items', has_length(1)))
            actual_video = find_object_with_ntiid(video_ntiid)
            assert_that(actual_video, not_none())
            assert_that(actual_video.__parent__, not_none())

        # Insert at index 0
        res = self.testapp.post_json(contents_url + '/index/0',
                                     upload_files=[
                                         ('icon', 'ichigo.png', b'ichigo')],
                                     status=201)
        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            obj = find_object_with_ntiid(ntiid)
            rel_ntiid = res.json_body['ntiid']
            assert_that(obj, has_property('Items', has_length(2)))

            history = ITransactionRecordHistory(obj)
            assert_that(history, has_length(greater_than_or_equal_to(4)))
            self._check_container_index(obj)

            obj = find_object_with_ntiid(rel_ntiid)
            self._check_container_index(
                obj, container_ids=(ntiid,), course=False)

        # Label length validation
        invalid_source = dict(source)
        invalid_source['label'] = INVALID_TITLE
        mc_ri.is_callable().with_args().returns(invalid_source)
        self.testapp.post(contents_url,
                          upload_files=[('icon', 'ichigo.png', b'ichigo')],
                          status=422)

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_overview_group_post(self):
        source = self._load_resource('nticourseoverviewgroup.json')

        # post
        res = self.testapp.post_json(self.assets_url, source, status=201)
        assert_that(res.json_body, has_entry('ntiid', is_not(none())))
        ntiid = res.json_body['ntiid']
        href = res.json_body['href']
        contents_url = href + '/@@contents'

        # Insert external link at index 0
        external_link = "http://www.google.com"
        related_work = {"href": external_link,
                        "MimeType": "application/vnd.nextthought.relatedworkref",
                        "label": "afd",
                        "byline": "",
                        "description": "afd",
                        "nti_requirements": "requirements",
                        "targetMimeType": "application/vnd.nextthought.externallink"}

        res = self.testapp.post_json(contents_url + '/index/0',
                                     related_work,
                                     status=201)
        res = res.json_body
        assert_that(res.get('href'), is_(external_link))

        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            obj = find_object_with_ntiid(ntiid)
            self._check_container_index(obj)
            rel_obj = obj.items[0]
            assert_that(rel_obj.__parent__, not_none())
            self._check_container_index(
                rel_obj, container_ids=(ntiid,), course=False)

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_lesson(self):
        source = self._load_resource('ntilessonoverview.json')
        source.pop('NTIID', None)

        # post
        res = self.testapp.post_json(self.assets_url, source, status=201)
        res = res.json_body
        lesson_ntiid = res.get('ntiid')
        lesson_href = res.get('href')
        assert_that(lesson_ntiid, not_none())
        assert_that(lesson_href, not_none())
        contents_link = self.require_link_href_with_rel(res,
                                                        VIEW_ORDERED_CONTENTS)

        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            obj = find_object_with_ntiid(lesson_ntiid)
            assert_that(obj, is_not(none()))
            assert_that(obj, validly_provides(INTILessonOverview))
            assert_that(obj, has_property('Items', has_length(1)))
            assert_that(obj.child_order_locked, is_(False))
            group_ntiid = obj.Items[0].ntiid

            entry = find_object_with_ntiid(self.course_ntiid)
            course = ICourseInstance(entry)
            self._check_containers(course, False, obj.Items)

            group = obj.Items[0]
            self._check_container_index(group, container_ids=(lesson_ntiid,))

            source = to_external_object(obj)

        # Permissions
        non_perm_env = self._get_non_perm_environ()
        self.testapp.get(lesson_href,
                         extra_environ=non_perm_env, status=403)

        # remove ntiid to fake a new group
        source['Items'][0].pop('ntiid', None)
        source['Items'][0].pop('NTIID', None)
        res = self.testapp.put_json(lesson_href, source, status=200)
        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            obj = find_object_with_ntiid(lesson_ntiid)
            old_group = find_object_with_ntiid(group_ntiid)
            assert_that(old_group, is_(none()))
            assert_that(obj, has_property('Items', has_length(1)))
            history = ITransactionRecordHistory(obj)
            assert_that(history, has_length(2))
            # XXX: posting to href does not toggle flag.
            # assert_that(obj.child_order_locked, is_( True ))
            # obj.child_order_locked = False # Reset

        # Contents, insert group at end
        source = {'title': 'mygroup'}
        res = self.testapp.post_json(contents_link, source, status=201)
        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            obj = find_object_with_ntiid(lesson_ntiid)
            group_ntiid = res.json_body['ntiid']
            assert_that(obj, has_property('Items', has_length(2)))
            assert_that(obj.Items[-1].ntiid, is_(group_ntiid))
            history = ITransactionRecordHistory(obj)
            assert_that(history, has_length(3))

            # No course since we do not have course lineage through lesson.
            obj = find_object_with_ntiid(group_ntiid)
            self._check_container_index(obj,
                                        container_ids=(lesson_ntiid,),
                                        course=False)

        # Long title validation
        invalid_source = {'title': INVALID_TITLE}
        self.testapp.post_json(contents_link, invalid_source, status=422)

        # Insert group at index 0
        res = self.testapp.post_json(contents_link + '/index/0',
                                     source,
                                     status=201)
        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            obj = find_object_with_ntiid(lesson_ntiid)
            group_ntiid = res.json_body['ntiid']
            assert_that(obj, has_property('Items', has_length(3)))
            assert_that(obj.Items[0].ntiid, is_(group_ntiid))
            assert_that(obj.child_order_locked, is_(True))
            obj.child_order_locked = False  # Reset

            obj = find_object_with_ntiid(group_ntiid)
            self._check_container_index(obj,
                                        container_ids=(lesson_ntiid,),
                                        course=False)

        # Another append
        utz_special = {
            'MimeType': "application/vnd.nextthought.nticourseoverviewgroup",
            'title': 'Discussions',
            'accentColor': 'b8b8b8'
        }
        res = self.testapp.post_json(contents_link, utz_special, status=201)
        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            obj = find_object_with_ntiid(lesson_ntiid)
            group_ntiid = res.json_body['ntiid']
            assert_that(obj, has_property('Items', has_length(4)))
            group = obj.Items[-1]
            group_index = len(obj.Items) - 1
            assert_that(group.ntiid, is_(group_ntiid))

            assert_that(obj.child_order_locked, is_(True))
            obj.child_order_locked = False  # Reset

        # Delete group from lesson
        delete_suffix = self._get_delete_url_suffix(group_index, group_ntiid)
        self.testapp.delete(contents_link + delete_suffix)
        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            obj = find_object_with_ntiid(lesson_ntiid)
            assert_that(obj, has_property('Items', has_length(3)))
            assert_that(obj.Items[-1].ntiid, is_not(group_ntiid))

            entry = find_object_with_ntiid(self.course_ntiid)
            course = ICourseInstance(entry)
            container = IPresentationAssetContainer(course)
            assert_that(container, does_not(has_key(group_ntiid)))

            group = find_object_with_ntiid(group_ntiid)
            assert_that(group, none())

            assert_that(obj.child_order_locked, is_(True))
            obj.child_order_locked = False  # Reset

    def _get_move_json(self, obj_ntiid, new_parent_ntiid, index=None, old_parent_ntiid=None):
        result = {'ObjectNTIID': obj_ntiid,
                  'ParentNTIID': new_parent_ntiid}
        if index is not None:
            result['Index'] = index
        if old_parent_ntiid is not None:
            result['OldParentNTIID'] = old_parent_ntiid
        return result

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_group_videos(self):
        source = self._load_resource('lesson_overview.json')
        # Remove all NTIIDs so things get registered.

        def _remove_ntiids(obj):
            obj.pop('NTIID', None)
            for item in obj.get('Items', ()):
                _remove_ntiids(item)
        _remove_ntiids(source)

        def _init_videos(source):
            _videos_ntiids = []
            _video_sources = source['Items'][-1]['Items']
            for _video_source in _video_sources:
                res = self.testapp.post_json(self.assets_url, _video_source, status=201)
                _videos_ntiids.append(res.json_body['NTIID'])
            return _videos_ntiids

        video_ntiids = _init_videos(source)
        for i, ntiid in enumerate(video_ntiids):
            source['Items'][-1]['Items'][i]['NTIID'] = ntiid

        res = self.testapp.post_json(self.assets_url, source, status=201)
        res = res.json_body
        move_link = self.require_link_href_with_rel(res, VIEW_NODE_MOVE)

        def _get_group(ext):
            return ext.get('Items')[-1]

        group = _get_group(res)
        last_group_ntiid = group.get('NTIID')
        video_ntiid = group.get('Items')[0].get('NTIID')
        original_size = len(group.get('Items'))

        # Moving a video does not create a new video.
        move_data = self._get_move_json(video_ntiid, last_group_ntiid)
        res = self.testapp.post_json(move_link, move_data)
        group = _get_group(res.json_body)
        group_items = group.get('Items')
        assert_that(group_items, has_length(original_size))
        assert_that(group_items[-1].get('Target-NTIID'), is_(video_ntiid))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_relatedwork(self):
        group_ntiid = 'tag:nextthought.com,2011-10:OU-NTICourseOverviewGroup-CS1323_F_2015_Intro_to_Computer_Programming.lec:01.01_LESSON.0'
        res = self.testapp.get('/dataserver2/Objects/%s' % group_ntiid)
        res = res.json_body
        group_ntiid = res.get('ntiid')
        assert_that(res.get('Items'), has_length(1))
        contents_link = self.require_link_href_with_rel(res,
                                                        VIEW_ORDERED_CONTENTS)

        source = self._load_resource('relatedwork.json')
        source.pop('NTIID', None)
        # In some cases, the client only gives us an href that points to content.
        # Validate we handle that and the given target case.
        non_target_source = dict(source)
        non_target_source.pop('target-ntiid', None)
        non_target_source.pop('target', None)
        unit_ntiid = source.get('href')

        def _xtest_reading(reading_source):
            res = self.testapp.post_json(
                contents_link, reading_source, status=201)
            res = res.json_body
            ref_ntiid = res.get('NTIID')
            assert_that(ref_ntiid, not_none())
            assert_that(res.get('href'), unit_ntiid)
            assert_that(res.get('target'), unit_ntiid)
            assert_that(res.get('nti_requirements'), 'requirements')

        _xtest_reading(non_target_source)
        _xtest_reading(source)

        # Now an external link
        external_link = dict(non_target_source)
        external_link['href'] = 'http://www.google.com'
        external_link[
            'targetMimeType'] = "application/vnd.nextthought.externallink"
        res = self.testapp.post_json(contents_link, external_link, status=201)
        res = res.json_body
        ref_ntiid = res.get('NTIID')
        assert_that(ref_ntiid, not_none())
        assert_that(res.get('href'), is_('http://www.google.com'))
        assert_that(res.get('target'), is_not('http://www.google.com'))
        assert_that(res.get('type'),
                    is_("application/vnd.nextthought.externallink"))
        assert_that(res.get('nti_requirements'), is_('requirements'))

        internal_link = dict(non_target_source)
        internal_link.pop('href', None)
        internal_link.pop('targetMimeType', 'text/plain')
        res = self.testapp.post(contents_link, internal_link,
                                upload_files=[('href', 'ichigo.txt', b'ichigo')])
        res = res.json_body
        ref_ntiid = res.get('NTIID')
        assert_that(ref_ntiid, not_none())
        href = res.get('href')
        assert_that(href, not_none())
        assert_that(is_internal_file_link(href), is_(True))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_calendar_event(self):
        group_ntiid = 'tag:nextthought.com,2011-10:OU-NTICourseOverviewGroup-CS1323_F_2015_Intro_to_Computer_Programming.lec:01.01_LESSON.0'
        res = self.testapp.get('/dataserver2/Objects/%s' % group_ntiid).json_body
        group_ntiid = res.get('ntiid')
        assert_that(res.get('Items'), has_length(1))
        contents_link = self.require_link_href_with_rel(res, VIEW_ORDERED_CONTENTS)

        # prepare course calendar event ref.
        source = {'MimeType': 'application/vnd.nextthought.nticalendareventref'}
        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            entry = find_object_with_ntiid(self.course_ntiid)
            course = ICourseInstance(entry)
            event = ICalendar(course).store_event(CourseCalendarEvent(title=u'testing'))
            source['target'] = event.ntiid
            event_oid = to_external_ntiid_oid(event)

            # section course sharing outline with parent
            section = course.SubInstances['001']
            section_event = ICalendar(section).store_event(CourseCalendarEvent(title=u'testing_child'))
            section_event_ntiid = section_event.ntiid

        # target isn't in the parent's calendar. currently this failed.
        #res = self.testapp.post_json(contents_link,
        #                            {'MimeType': 'application/vnd.nextthought.nticalendareventref',
        #                             'target': section_event_ntiid}, status=422)

        # target doesn't exist.
        res = self.testapp.post_json(contents_link,
                                    {'MimeType': 'application/vnd.nextthought.nticalendareventref',
                                     'target': source['target']+'_non_existing'}, status=422)
        assert_that('No valid calendar event found for given ntiid.' in res.body, is_(True))

        # target is not a ICourseCalendarEvent.
        with mock_dataserver.mock_db_trans(self.ds):
            user = self._create_user('test001')
            wrong_ntiid = ICalendar(user).store_event(UserCalendarEvent(title=u'tennis')).ntiid

        res = self.testapp.post_json(contents_link,
                                    {'MimeType': 'application/vnd.nextthought.nticalendareventref',
                                     'target': wrong_ntiid}, status=422)
        assert_that('No valid calendar event found for given ntiid.' in res.body, is_(True))

        res = self.testapp.post_json(contents_link, source, status=201).json_body
        ref_ntiid = res.get('NTIID')

        assert_that(ref_ntiid, not_none())
        assert_that(res.get('TargetMimeType'), 'application/vnd.nextthought.courseware.coursecalendarevent')
        assert_that(res.get('Target-NTIID'), source['target'])
        self.require_link_href_with_rel(res, 'edit')
        self.require_link_href_with_rel(res, 'schema')

        with mock_dataserver.mock_db_trans(self.ds, 'platform.ou.edu'):
            ref = find_object_with_ntiid(ref_ntiid)
            assert_that(INTICalendarEventRef.providedBy(ref), is_(True))
            assert_that(component.getUtility(INTICalendarEventRef, name=ref_ntiid), same_instance(ref))

            group = find_object_with_ntiid(group_ntiid)
            assert_that(ref in group.Items, is_(True))

            catalog = get_library_catalog()
            refs = catalog.search_objects(provided=INTICalendarEventRef, target=event.ntiid)
            assert_that(refs, has_item(ref))

        #remove calendar event
        self.testapp.delete('/dataserver2/Objects/%s' % event_oid, status=204)

        with mock_dataserver.mock_db_trans(self.ds, 'platform.ou.edu'):
            assert_that(ref in group.Items, is_(False))

            refs = catalog.search_objects(provided=INTICalendarEventRef, target=event.ntiid)
            assert_that(refs, has_length(0))

            assert_that(component.queryUtility(INTICalendarEventRef, name=ref_ntiid), is_(None))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_timeline(self):
        group_ntiid = 'tag:nextthought.com,2011-10:OU-NTICourseOverviewGroup-CS1323_F_2015_Intro_to_Computer_Programming.lec:01.01_LESSON.0'
        res = self.testapp.get('/dataserver2/Objects/%s' % group_ntiid)
        res = res.json_body
        group_ntiid = res.get('ntiid')
        assert_that(res.get('Items'), has_length(1))
        contents_link = self.require_link_href_with_rel(res,
                                                        VIEW_ORDERED_CONTENTS)

        source = self._load_resource('ntitimeline.json')
        source.pop('NTIID', None)

        res = self.testapp.post_json(self.assets_url, source, status=201)
        timeline_ntiid = res.json_body.get('NTIID')
        assert_that(timeline_ntiid, not_none())
        assert_that(res.json_body, has_entry('href', not_none()))

        # Only timeline in assets call.
        res = self.testapp.get(self.assets_url,
                               params={'accept': NTITimeLine.mime_type})
        res = res.json_body
        items = res.get('Items')
        assert_that(items, has_length(1))
        assert_that(items[0].get('NTIID'), is_(timeline_ntiid))

        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            obj = find_object_with_ntiid(timeline_ntiid)
            assert_that(obj, not_none())
            assert_that(obj.__parent__, not_none())
            assert_that(obj, validly_provides(INTITimeline))

            entry = find_object_with_ntiid(self.course_ntiid)
            course = ICourseInstance(entry)
            self._check_containers(course, items=(obj,), packages=False)

        self.testapp.post_json(contents_link,
                               {'ntiid': timeline_ntiid}, status=201)

        res = self.testapp.get('/dataserver2/Objects/%s' % group_ntiid)
        res = res.json_body
        assert_that(res.get('Items'), has_length(2))

        # Only timeline in assets call.
        res = self.testapp.get(self.assets_url,
                               params={'accept': NTITimeLine.mime_type})
        res = res.json_body
        items = res.get('Items')
        assert_that(items, has_length(1))
        assert_that(items[0].get('NTIID'), is_(timeline_ntiid))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_timeline_with_file(self):
        """
        Test creating a timeline by passing in the timeline content in multipart.
        """
        group_ntiid = 'tag:nextthought.com,2011-10:OU-NTICourseOverviewGroup-CS1323_F_2015_Intro_to_Computer_Programming.lec:01.01_LESSON.0'
        res = self.testapp.get('/dataserver2/Objects/%s' % group_ntiid)
        # Read in content bytes and the timeline source itself.
        path = os.path.join(os.path.dirname(__file__),
                            'ntitimeline_content.json')
        with open(path, "rb") as fp:
            timeline_content = fp.read()
        timeline_source = self._load_resource('ntitimeline.json')
        timeline_source.pop('NTIID', None)
        timeline_source.pop('href', None)
        res = res.json_body
        group_ntiid = res.get('ntiid')
        group_href = res.get('href')
        assert_that(res.get('Items'), has_length(1))

        # Now insert our timeline with a multipart href to the actual content.
        contents_link = self.require_link_href_with_rel(res,
                                                        VIEW_ORDERED_CONTENTS)
        res = self.testapp.post(contents_link, timeline_source,
                                upload_files=[('href', 'timeline_content', timeline_content)])
        res = res.json_body
        timeline_ntiid = res.get('NTIID')
        assert_that(timeline_ntiid, not_none())
        assert_that(res.get('MimeType'),
                    is_('application/vnd.nextthought.ntitimeline'))
        assert_that(res.get('href'), not_none())
        content_file = res.get('ContentFile')
        assert_that(content_file, not_none())
        content_file_ntiid = content_file.get('NTIID')
        assert_that(content_file_ntiid, not_none())
        assert_that(content_file.get('size'), not_none())
        assert_that(content_file.get('name'), is_('timeline_content'))

        # Validate group state.
        group = self.testapp.get(group_href)
        group = group.json_body
        group_items = group.get('Items')
        assert_that(group_items, has_length(2))
        assert_that(group_items[1].get('NTIID'), is_(timeline_ntiid))

        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            group = find_object_with_ntiid(group_ntiid)
            timeline_ref = group.Items[1]
            assert_that(timeline_ref.mime_type,
                        is_('application/vnd.nextthought.ntitimelineref'))
            assert_that(timeline_ref.target, is_(timeline_ntiid))

            timeline = find_object_with_ntiid(timeline_ntiid)
            assert_that(timeline, not_none())
            assert_that(timeline.ntiid, is_(timeline_ntiid))
            assert_that(timeline.__parent__, validly_provides(ICourseInstance))

            timeline_ref = component.queryUtility(INTITimelineRef,
                                                  name=timeline_ref.ntiid)
            assert_that(timeline_ref, not_none())
            assert_that(timeline_ref.ntiid, is_(timeline_ref.ntiid))
            assert_that(timeline_ref.__parent__,
                        validly_provides(INTICourseOverviewGroup))

        # Test delete
        delete_suffix = self._get_delete_url_suffix(1, timeline_ntiid)
        self.testapp.delete(contents_link + delete_suffix)

        # Gone from group, but still exists
        group = self.testapp.get(group_href)
        group = group.json_body
        group_items = group.get('Items')
        assert_that(group_items, has_length(1))
        assert_that(group_items[0].get('NTIID'), is_not(timeline_ntiid))

        # The asset should still exist even though its ref has been deleted
        self.testapp.get('/dataserver2/Objects/%s' %
                         timeline_ntiid)

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_moves(self):
        source = self._load_resource('lesson_overview.json')
        # Remove all NTIIDs so things get registered.

        def _remove_ntiids(obj):
            obj.pop('NTIID', None)
            for item in obj.get('Items', ()):
                _remove_ntiids(item)
        _remove_ntiids(source)
        res = self.testapp.post_json(self.assets_url, source, status=201)
        res = res.json_body

        move_link = self.require_link_href_with_rel(res, VIEW_NODE_MOVE)
        lesson_ntiid = res.get('NTIID')
        lesson_url = '/dataserver2/Objects/%s' % lesson_ntiid
        groups = res.get('Items')
        original_group_count = len(groups)
        first_group_ntiid = groups[0].get('NTIID')
        last_group_ntiid = groups[-1].get('NTIID')

        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            obj = find_object_with_ntiid(lesson_ntiid)
            assert_that(obj.child_order_locked, is_(False))
            self._check_container_index(obj)

        # Move our last item to first
        move_data = self._get_move_json(last_group_ntiid,
                                        lesson_ntiid,
                                        0, lesson_ntiid)
        self.testapp.post_json(move_link, move_data)

        res = self.testapp.get(lesson_url)
        res = res.json_body
        groups = res.get('Items')
        assert_that(groups, has_length(original_group_count))
        assert_that(groups[0].get('NTIID'), is_(last_group_ntiid))
        assert_that(groups[1].get('NTIID'), is_(first_group_ntiid))
        assert_that(groups[-1].get('NTIID'), is_not(first_group_ntiid))

        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            obj = find_object_with_ntiid(lesson_ntiid)
            assert_that(obj.child_order_locked, is_(True))
            obj.child_order_locked = False  # Reset
            self._check_container_index(obj)
            moved_group = find_object_with_ntiid(last_group_ntiid)
            assert_that(moved_group.__parent__.ntiid, is_(lesson_ntiid))
            self._test_transaction_history(moved_group,
                                           TRX_OVERVIEW_GROUP_MOVE_TYPE)
            self._check_container_index(moved_group,
                                        container_ids=(lesson_ntiid,))

        # Move the item back to the end
        move_data = self._get_move_json(last_group_ntiid, lesson_ntiid)
        self.testapp.post_json(move_link, move_data)

        res = self.testapp.get(lesson_url)
        res = res.json_body
        groups = res.get('Items')
        assert_that(groups, has_length(original_group_count))
        assert_that(groups[0].get('NTIID'), is_(first_group_ntiid))
        assert_that(groups[-1].get('NTIID'), is_(last_group_ntiid))

        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            obj = find_object_with_ntiid(lesson_ntiid)
            assert_that(obj.child_order_locked, is_(True))
            obj.child_order_locked = False  # Reset
            self._check_container_index(moved_group,
                                        container_ids=(lesson_ntiid,))

        # Overview groups
        source_group_index = 0
        target_group_index = 3
        source_group = groups[source_group_index]
        source_group_ntiid = source_group.get('NTIID')
        target_group = groups[target_group_index]
        target_group_ntiid = target_group.get('NTIID')
        group_items = source_group.get('Items')
        original_source_group_size = len(group_items)
        original_target_group_size = len(target_group.get('Items'))
        first_asset_ntiid = group_items[0].get('NTIID')
        last_asset_ntiid = group_items[-1].get('NTIID')

        # Move within an overview group
        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            obj = find_object_with_ntiid(source_group_ntiid)
            assert_that(obj.child_order_locked, is_(False))
            asset = find_object_with_ntiid(first_asset_ntiid)
            assert_that(asset.__parent__.ntiid, is_(source_group_ntiid))
            self._check_container_index(asset,
                                        container_ids=(lesson_ntiid, source_group_ntiid))

        move_data = self._get_move_json(first_asset_ntiid, source_group_ntiid)
        self.testapp.post_json(move_link, move_data)

        res = self.testapp.get(lesson_url)
        res = res.json_body
        groups = res.get('Items')
        assert_that(len(groups), is_(original_group_count))
        new_source_group = groups[source_group_index]
        new_source_group_items = new_source_group.get('Items')
        assert_that(new_source_group_items,
                    has_length(original_source_group_size))
        assert_that(new_source_group_items[-2].get('NTIID'),
                    is_(last_asset_ntiid))
        assert_that(new_source_group_items[-1].get('NTIID'),
                    is_(first_asset_ntiid))

        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            obj = find_object_with_ntiid(source_group_ntiid)
            assert_that(obj.child_order_locked, is_(True))
            obj.child_order_locked = False  # Reset
            assert_that(asset.__parent__.ntiid, is_(source_group_ntiid))
            self._check_container_index(asset,
                                        container_ids=(lesson_ntiid, source_group_ntiid))

        # Move between overview groups
        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            obj = find_object_with_ntiid(target_group_ntiid)
            assert_that(obj.child_order_locked, is_(False))

        move_data = self._get_move_json(first_asset_ntiid,
                                        target_group_ntiid,
                                        0, source_group_ntiid)
        self.testapp.post_json(move_link, move_data)

        res = self.testapp.get(lesson_url)
        res = res.json_body
        groups = res.get('Items')
        assert_that(len(groups), is_(original_group_count))
        new_source_group = groups[source_group_index]
        new_target_group = groups[target_group_index]
        new_source_group_items = new_source_group.get('Items')
        new_target_group_items = new_target_group.get('Items')
        assert_that(new_source_group_items,
                    has_length(original_source_group_size - 1))
        assert_that(new_target_group_items,
                    has_length(original_target_group_size + 1))
        assert_that(new_source_group_items[-1].get('NTIID'),
                    is_not(first_asset_ntiid))
        assert_that(new_target_group_items[0].get('NTIID'),
                    is_(first_asset_ntiid))

        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            obj = find_object_with_ntiid(target_group_ntiid)
            assert_that(obj.child_order_locked, is_(True))
            tar = find_object_with_ntiid(source_group_ntiid)
            assert_that(tar.child_order_locked, is_(True))
            obj.child_order_locked = tar.child_order_locked = False  # Reset
            moved_asset = find_object_with_ntiid(first_asset_ntiid)
            assert_that(moved_asset.__parent__.ntiid, is_(target_group_ntiid))
            self._test_transaction_history(moved_asset, TRX_ASSET_MOVE_TYPE)
            self._check_container_index(moved_asset,
                                        container_ids=(lesson_ntiid, target_group_ntiid))

        # Move back to original group
        move_data = self._get_move_json(first_asset_ntiid,
                                        source_group_ntiid, 0,
                                        target_group_ntiid)
        self.testapp.post_json(move_link, move_data)

        res = self.testapp.get(lesson_url)
        res = res.json_body
        groups = res.get('Items')
        assert_that(len(groups), is_(original_group_count))
        new_source_group = groups[source_group_index]
        new_target_group = groups[target_group_index]
        new_source_group_items = new_source_group.get('Items')
        new_target_group_items = new_target_group.get('Items')
        assert_that(new_source_group_items,
                    has_length(original_source_group_size))
        assert_that(new_target_group_items,
                    has_length(original_target_group_size))
        assert_that(new_source_group_items[0].get('NTIID'),
                    is_(first_asset_ntiid))
        assert_that(new_target_group_items[0].get('NTIID'),
                    is_not(first_asset_ntiid))

        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            obj = find_object_with_ntiid(target_group_ntiid)
            assert_that(obj.child_order_locked, is_(True))
            tar = find_object_with_ntiid(source_group_ntiid)
            assert_that(tar.child_order_locked, is_(True))
            obj.child_order_locked = tar.child_order_locked = False  # Reset
            assert_that(moved_asset.__parent__.ntiid, is_(source_group_ntiid))
            self._check_container_index(moved_asset,
                                        container_ids=(lesson_ntiid, source_group_ntiid))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_lesson_media_outline(self):
        outline_node_ntiid = "tag:nextthought.com,2011-10:NTI-NTICourseOutlineNode-Fall2015_CS_1323.0"
        node_data = {'MimeType': "application/vnd.nextthought.courses.courseoutlinecontentnode",
                     'title': "Chapter 1 - The First Chapter"}
        # Create node and publish it
        content_node = self.testapp.post_json('/dataserver2/Objects/%s/contents' % outline_node_ntiid,
                                              node_data)
        content_node = content_node.json_body
        lesson_node_href = content_node.get('href')
        self.testapp.post('%s/@@publish' % lesson_node_href)
        lesson_ntiid = content_node.get('LessonOverviewNTIID')

        # Add our overview group and registered video.
        group_source = self._load_resource('nticourseoverviewgroup.json')
        video_source = group_source.get('Items')[-1]
        video_res = self.testapp.post_json(self.assets_url,
                                           video_source,
                                           status=201)
        video_ntiid = video_res.json_body.get('ntiid')
        video_source['NTIID'] = video_ntiid
        self.testapp.post_json('/dataserver2/Objects/%s/contents' % lesson_ntiid,
                               group_source)
        with mock_dataserver.mock_db_trans(self.ds, 'janux.ou.edu'):
            video_obj = find_object_with_ntiid(video_ntiid)
            assert_that(video_obj, not_none())

        # Our media by outline contains just the single video
        # for this lesson.
        media_outline = self._media_by_outline()
        containers = media_outline.get('Containers')
        lesson_media = containers.get(lesson_ntiid)
        assert_that(lesson_media, not_none())
        assert_that(lesson_media, contains(video_ntiid))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_removing_refs(self):
        assignment_ntiid = "tag:nextthought.com,2011-10:OU-NAQ-CS1323_F_2015_Intro_to_Computer_Programming.naq.asg.assignment:iClicker_8_26"
        admin_environ = self._make_extra_environ(
            username=self.default_username)

        source = self._load_resource('ntilessonoverview.json')
        source.pop('NTIID', None)

        video_source = self._load_resource('ntivideo.json')
        video_source.pop('NTIID', None)
        res = self.testapp.post_json(self.assets_url, video_source, status=201)
        res = res.json_body
        video_ntiid = res.get('ntiid')

        # Insert lesson (with one group) and three groups.
        res = self.testapp.post_json(self.assets_url, source, status=201)
        res = res.json_body
        lesson_ntiid = res.get('ntiid')
        lesson_href = res.get('href')
        assert_that(lesson_ntiid, not_none())
        assert_that(lesson_href, not_none())
        group_zero_size = len(res.get('Items')[0].get('Items'))
        remove_refs_link = self.require_link_href_with_rel(res,
                                                           VIEW_LESSON_REMOVE_REFS)
        group_source = {'title': 'mygroup'}
        contents_link = self.require_link_href_with_rel(res,
                                                        VIEW_ORDERED_CONTENTS)
        group_one = self.testapp.post_json(contents_link,
                                           group_source).json_body
        g1_contents_link = self.require_link_href_with_rel(group_one,
                                                           VIEW_ORDERED_CONTENTS)
        group_two = self.testapp.post_json(contents_link,
                                           group_source).json_body
        g2_contents_link = self.require_link_href_with_rel(group_two,
                                                           VIEW_ORDERED_CONTENTS)
        group_three = self.testapp.post_json(contents_link,
                                             group_source).json_body
        g3_contents_link = self.require_link_href_with_rel(group_three,
                                                           VIEW_ORDERED_CONTENTS)

        ref = {
            "MimeType": "application/vnd.nextthought.assignmentref",
            "Target-NTIID": assignment_ntiid,
            "title": "title",
            "label": "label"
        }

        # Insert some refs into various groups.
        # Group one, just the assignment ref
        res = self.testapp.post_json(g1_contents_link, ref, status=201)
        res = res.json_body
        assert_that(res['NTIID'], is_not(res['Target-NTIID']))
        # Group two, just a video
        self.testapp.post_json(g2_contents_link,
                               {'ntiid': video_ntiid}, status=201)
        # Group three, one of each
        self.testapp.post_json(g3_contents_link,
                               {'ntiid': video_ntiid}, status=201)
        self.testapp.post_json(g3_contents_link, ref, status=201)

        # Validate current state
        lesson = self.testapp.get(lesson_href, status=200)
        lesson = lesson.json_body
        groups = lesson.get('Items')
        assert_that(groups[0].get('Items'), has_length(group_zero_size))
        assert_that(groups[1].get('Items'), has_length(1))
        assert_that(groups[2].get('Items'), has_length(1))
        assert_that(groups[3].get('Items'), has_length(2))

        # Now remove all corresponding refs
        self.testapp.delete('%s?target=%s' % (remove_refs_link, assignment_ntiid),
                            extra_environ=admin_environ)

        lesson = self.testapp.get(lesson_href, status=200)
        lesson = lesson.json_body
        groups = lesson.get('Items')
        assert_that(groups[0].get('Items'), has_length(group_zero_size))
        assert_that(groups[1].get('Items'), has_length(0))
        assert_that(groups[2].get('Items'), has_length(1))
        assert_that(groups[3].get('Items'), has_length(1))

        # Again with no hits works.
        self.testapp.delete('%s?target=%s' % (remove_refs_link, assignment_ntiid),
                            extra_environ=admin_environ)

        # Post two duplicate refs to group 3. We should be able
        # to delete one without any errors. This tests the case where
        # we have multiple matches for an ntiid, in which case we
        # just delete the one with the matching index.
        self.testapp.post_json(g3_contents_link, ref, status=201)
        self.testapp.post_json(g3_contents_link, ref, status=201)

        lesson = self.testapp.get(lesson_href, status=200)
        lesson = lesson.json_body
        groups = lesson.get('Items')
        assert_that(groups[3].get('Items'), has_length(3))

        # Index must be an int if we include it.
        self.testapp.delete(
            g3_contents_link + '/ntiid/' + assignment_ntiid + '?index=zero', status=422)

        # If we have a mismatch between the index and ntiid, we
        # should detect the conflict.
        self.testapp.delete(
            g3_contents_link + '/ntiid/' + assignment_ntiid + '?index=0', status=409)

        # It is also a conflict if we include no index, because we have
        # two matching ntiids but don't know which to delete.
        self.testapp.delete(
            g3_contents_link + '/ntiid/' + assignment_ntiid, status=409)

        # Not including an index param is treated the same as including an
        # empty one. In this case, that results in a conflict, for the same
        # reason as above.
        self.testapp.delete(
            g3_contents_link + '/ntiid/' + assignment_ntiid + '?index=', status=409)

        # Both indices 1 and 2 should match this ntiid, so we
        # just delete the second one.
        self.testapp.delete(
            g3_contents_link + '/ntiid/' + assignment_ntiid + '?index=2')

        # set up group 1 again with just one ref.
        self.testapp.post_json(g1_contents_link, ref, status=201)

        # now if we delete without the index, there is no ambiguity.
        self.testapp.delete(
            g1_contents_link + '/ntiid/' + assignment_ntiid)

        # The same is true if we include an empty index param;
        # it is treated as if it was not included.
        self.testapp.post_json(g1_contents_link, ref, status=201)
        self.testapp.delete(
            g1_contents_link + '/ntiid/' + assignment_ntiid + '?index=')
