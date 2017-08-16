#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import contains
from hamcrest import not_none
from hamcrest import has_items
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import contains_inanyorder
does_not = is_not

import shutil
import tempfile

from nti.app.contenttypes.presentation import VIEW_CONTENTS
from nti.app.contenttypes.presentation import VIEW_ORDERED_CONTENTS
from nti.app.contenttypes.presentation import VIEW_OVERVIEW_CONTENT

from nti.app.contenttypes.presentation.exporter import UserAssetsExporter
from nti.app.contenttypes.presentation.exporter import LessonOverviewsExporter

from nti.app.contenttypes.presentation.importer import UserAssetsImporter
from nti.app.contenttypes.presentation.importer import AssetCleanerImporter
from nti.app.contenttypes.presentation.importer import LessonOverviewsImporter

from nti.cabinet.filer import DirectoryFiler

from nti.contenttypes.courses.exporter import CourseOutlineExporter

from nti.contenttypes.courses.importer import CourseOutlineImporter

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver

from nti.externalization.externalization import StandardExternalFields

ITEMS = StandardExternalFields.ITEMS


class TestImportExporter(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'
    entry_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'
    course_url = '/dataserver2/%2B%2Betc%2B%2Bhostsites/platform.ou.edu/%2B%2Betc%2B%2Bsite/Courses/Fall2015/CS%201323'
    outline_contents_url = '%s/Outline/%s' % (course_url, VIEW_CONTENTS)
    assets_url = '%s/assets' % course_url

    @classmethod
    def course_entry(cls):
        return find_object_with_ntiid(cls.entry_ntiid)

    @WithSharedApplicationMockDS(testapp=False, users=True)
    def test_lesson_exporter(self):
        tmp_dir = tempfile.mkdtemp(dir="/tmp")
        try:
            filer = DirectoryFiler(tmp_dir)
            # export
            with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
                course = ICourseInstance(self.course_entry())
                exporter = LessonOverviewsExporter()
                exporter.export(course, filer)
                assert_that(filer.list(), contains('Lessons'))
                assert_that(filer.list("Lessons"), has_length(18))

            # import
            with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
                course = ICourseInstance(self.course_entry())
                importer = LessonOverviewsImporter()
                result = importer.process(course, filer, False)
                assert_that(result, has_length(18))
        finally:
            shutil.rmtree(tmp_dir, True)

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_user_assets(self):
        """
        Test that user created videos get handled correctly on import/export.
        """
        # Create unit node, content node and lesson (unpublished).
        unit_title = 'ImportExportUnitTitle'
        unit_data = {'title': unit_title,
                     'MimeType': "application/vnd.nextthought.courses.courseoutlinenode"}
        res = self.testapp.post_json(self.outline_contents_url, unit_data)
        res = res.json_body
        unit_ntiid = res['ntiid']
        unit_contents_url = self.require_link_href_with_rel(res,
                                                            VIEW_ORDERED_CONTENTS)
        content_title = 'ImportExportContentTitle'
        content_data = {'title': content_title,
                        'MimeType': "application/vnd.nextthought.courses.courseoutlinecontentnode"}
        res = self.testapp.post_json(unit_contents_url, content_data)
        res = res.json_body
        content_ntiid = res['ntiid']
        lesson_ntiid = res['LessonOverviewNTIID']
        lesson_url = self.require_link_href_with_rel(res,
                                                     VIEW_OVERVIEW_CONTENT)
        lesson_res = self.testapp.get(lesson_url)
        lesson_res = lesson_res.json_body
        lesson_contents_url = self.require_link_href_with_rel(lesson_res,
                                                              VIEW_ORDERED_CONTENTS)
        group_title = 'ImportExportGroupTitle'
        group_res = self.testapp.post_json(lesson_contents_url,
                                           {'title': group_title})
        group_res = group_res.json_body
        group_ntiid = group_res['ntiid']
        group_contents_url = self.require_link_href_with_rel(group_res,
                                                             VIEW_ORDERED_CONTENTS)

        # Create a video and video roll and insert them into lesson.
        video1_source = "dJ1VorN9Cl0"
        video2_source = "ZxDn9z9yEkQ"
        video3_source = "SuXlZ5PHK9I"
        related_work_ref_title = 'ImportExportTitle'
        related_work_ref_href = 'http://www.google.com"'
        video_json = {"MimeType": "application/vnd.nextthought.ntivideo",
                      "sources": [{"MimeType": "application/vnd.nextthought.ntivideosource",
                                   "service": "youtube",
                                   "source": [video1_source],
                                   "type":["video/youtube"]}]}
        video2_json = {"MimeType": "application/vnd.nextthought.ntivideo",
                       "sources": [{"MimeType": "application/vnd.nextthought.ntivideosource",
                                    "service": "youtube",
                                    "source": [video2_source],
                                    "type":["video/youtube"]}]}
        video3_json = {"MimeType": "application/vnd.nextthought.ntivideo",
                       "sources": [{"MimeType": "application/vnd.nextthought.ntivideosource",
                                    "service": "youtube",
                                    "source": [video3_source],
                                    "type":["video/youtube"]}]}
        related_work_ref_json = {"href": related_work_ref_href,
                                 "MimeType": "application/vnd.nextthought.relatedworkref",
                                 "label": related_work_ref_title,
                                 "byline": "",
                                 "description": "ImportExportDescription",
                                 "targetMimeType": "application/vnd.nextthought.externallink"}

        video_res = self.testapp.post_json(self.assets_url, video_json)
        video_res = video_res.json_body
        video1_ntiid = video_res['NTIID']
        video_mime_type = video_res['MimeType']
        video_href = video_res['href']
        assert_that(video1_ntiid, not_none())
        assert_that(video_href, not_none())
        sources = video_res['sources']
        assert_that(sources, has_length(1))
        source1_ntiid = sources[0]['NTIID']
        assert_that(source1_ntiid, not_none())

        video_res = self.testapp.post_json(self.assets_url, video2_json)
        video_res = video_res.json_body
        video2_ntiid = video_res['NTIID']
        video_href = video_res['href']
        assert_that(video2_ntiid, not_none())
        assert_that(video_href, not_none())
        sources = video_res['sources']
        assert_that(sources, has_length(1))
        source2_ntiid = sources[0]['NTIID']
        assert_that(source2_ntiid, not_none())

        video_res = self.testapp.post_json(self.assets_url, video3_json)
        video_res = video_res.json_body
        video3_ntiid = video_res['NTIID']
        video_href = video_res['href']
        assert_that(video3_ntiid, not_none())
        assert_that(video_href, not_none())
        sources = video_res['sources']
        assert_that(sources, has_length(1))
        source3_ntiid = sources[0]['NTIID']
        assert_that(source3_ntiid, not_none())

        # Now insert the videos into lesson
        video_data = {"MimeType": "application/vnd.nextthought.ntivideo",
                      "NTIID": video1_ntiid}
        self.testapp.post_json(group_contents_url, video_data)
        roll_data = {"MimeType": "application/vnd.nextthought.videoroll",
                     ITEMS: [video2_ntiid, video3_ntiid]}
        res = self.testapp.post_json(group_contents_url, roll_data)
        res = res.json_body
        video_roll_ntiid = res['ntiid']
        res = self.testapp.post_json(group_contents_url, related_work_ref_json)
        res = res.json_body
        related_work_ref_ntiid = res['ntiid']

        # Export/Import
        tmp_dir = tempfile.mkdtemp(dir="/tmp")
        try:
            filer = DirectoryFiler(tmp_dir)
            with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
                course = ICourseInstance(self.course_entry())
                for factory in (CourseOutlineExporter,
                                LessonOverviewsExporter,
                                UserAssetsExporter):
                    exporter = factory()
                    exporter.export(course, filer, backup=False)
                assert_that(filer.list(), contains_inanyorder('Lessons',
                                                              'user_assets.json',
                                                              'course_outline.xml',
                                                              'course_outline.json'))
                assert_that(filer.list("Lessons"), has_length(19))

            with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
                course = ICourseInstance(self.course_entry())
                for factory in (AssetCleanerImporter,
                                CourseOutlineImporter,
                                UserAssetsImporter,
                                LessonOverviewsImporter):
                    importer = factory()
                    result = importer.process(course, filer, False)
                    if isinstance(factory, UserAssetsImporter):
                        assert_that(result, has_length(3))
        finally:
            shutil.rmtree(tmp_dir, True)

        # Now validate our post-import state
        res = self.testapp.get(self.outline_contents_url)
        res = res.json_body
        unit_ext = res[-1]
        assert_that(unit_ext['title'], is_(unit_title))
        assert_that(unit_ext['ntiid'], is_not(unit_ntiid))
        content_ext = unit_ext['contents'][-1]
        assert_that(content_ext['title'], is_(content_title))
        assert_that(content_ext['ntiid'], is_not(content_ntiid))
        lesson_overview_url = self.require_link_href_with_rel(content_ext,
                                                              VIEW_OVERVIEW_CONTENT)
        lesson_ext = self.testapp.get(lesson_overview_url)
        lesson_ext = lesson_ext.json_body
        assert_that(lesson_ext['ntiid'], is_not(lesson_ntiid))
        group_ext = lesson_ext[ITEMS][-1]
        assert_that(group_ext['title'], is_(group_title))
        assert_that(group_ext['ntiid'], is_not(group_ntiid))
        group_items = group_ext[ITEMS]
        assert_that(group_items, has_length(3))

        # Validate videos
        video = group_items[0]
        new_video1_ntiid = video['ntiid']
        assert_that(new_video1_ntiid,
                    is_not(video1_ntiid))
        assert_that(video['sources'][0]['source'],
                    contains(video1_source))

        video_roll = group_items[1]
        assert_that(video_roll['ntiid'], is_not(video_roll_ntiid))
        roll_items = video_roll[ITEMS]
        assert_that(roll_items, has_length(2))
        new_video2_ntiid = roll_items[0]['ntiid']
        new_video3_ntiid = roll_items[1]['ntiid']
        assert_that(new_video2_ntiid, is_not(video2_ntiid))
        assert_that(roll_items[0]['sources'][0]['source'],
                    contains(video2_source))
        assert_that(new_video3_ntiid, is_not(video3_ntiid))
        assert_that(roll_items[1]['sources'][0]['source'],
                    contains(video3_source))

        related_work_ref = group_items[2]
        assert_that(related_work_ref['label'], is_(related_work_ref_title))
        assert_that(related_work_ref['href'], is_(related_work_ref_href))
        assert_that(related_work_ref['ntiid'], is_not(related_work_ref_ntiid))

        # Correct videos show up in course assets
        assets_res = self.testapp.get(self.assets_url,
                                      {'accept': video_mime_type})
        assets_res = assets_res.json_body
        course_video_ntiids = [x['ntiid'] for x in assets_res[ITEMS]]
        assert_that(course_video_ntiids, has_items(new_video1_ntiid,
                                                   new_video2_ntiid,
                                                   new_video3_ntiid))
        assert_that(course_video_ntiids, does_not(
                                            has_items(video1_ntiid,
                                                      video2_ntiid,
                                                      video3_ntiid)))

        # TODO: Transcripts
