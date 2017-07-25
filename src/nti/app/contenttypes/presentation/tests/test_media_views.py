#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import starts_with
does_not = is_not

import os
import simplejson

from nti.contenttypes.presentation.interfaces import IUserCreatedTranscript

from nti.contenttypes.presentation.utils import prepare_json_text

from nti.externalization.representation import to_json_representation

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.app.products.courseware.tests import InstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver


class TestMediaViews(ApplicationLayerTest):

    layer = InstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    course_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'
    course_url = '/dataserver2/%2B%2Betc%2B%2Bhostsites/platform.ou.edu/%2B%2Betc%2B%2Bsite/Courses/Fall2015/CS%201323'
    assets_url = course_url + '/assets'

    video_ntiid_cell = 'tag:nextthought.com,2011-10:OU-NTIVideo-CS1323_F_2015_Intro_to_Computer_Programming.ntivideo.video_02.02.04_Cell'
    transcript_ntiid = 'tag:nextthought.com,2011-10:OU-NTITranscript-CS1323_F_2015_Intro_to_Computer_Programming.ntivideo.video_02.02.04_Cell.0'
    video_ntiid_frogger = 'tag:nextthought.com,2011-10:OU-NTIVideo-CS1323_F_2015_Intro_to_Computer_Programming.ntivideo.video_05.01.02_Frogger_1'

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_transcripts(self):
        href = '/dataserver2/Objects/%s' % self.video_ntiid_cell
        res = self.testapp.get(href, status=200)
        href = self.require_link_href_with_rel(res.json_body, 'transcripts')
        res = self.testapp.get(href, status=200)
        assert_that(res.json_body, has_entry('Items', has_length(1)))

    def get_vtt_source(self):
        path = os.path.join(os.path.dirname(__file__), 'sample.vtt')
        with open(path, "r") as fp:
            source = fp.read()
        return source

    def _load_resource(self, name):
        path = os.path.join(os.path.dirname(__file__), name)
        with open(path, "r") as fp:
            source = simplejson.loads(prepare_json_text(fp.read()))
        return source

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_put_transcript_403(self):
        href = '/dataserver2/Objects/%s' % self.transcript_ntiid
        self.testapp.put(href,
                         upload_files=[
                            ('sample.vtt', 'sample.vtt', self.get_vtt_source())
                         ],
                        status=403)

    def upload_transcript(self, video_ntiid=None, check=True):
        data = {
            'lang': 'en',
            'type': 'text/vtt',
            'purpose': 'normal',
            'MimeType': 'application/vnd.nextthought.ntitranscript',
        }
        video_ntiid = video_ntiid or self.video_ntiid_cell
        href = '/dataserver2/Objects/%s' % video_ntiid
        video_res = self.testapp.get(href, status=200)
        if check:
            assert_that(video_res.json_body,
                        has_entry('transcripts', has_length(1)))

        href = self.require_link_href_with_rel(video_res.json_body, 'transcript')
        data = {'__json__': to_json_representation(data)}
        upload_res = self.testapp.post(href, data,
                                       upload_files=[
                                            ('sample.vtt', 'sample.vtt', self.get_vtt_source())
                                       ],
                                       status=200)
        return video_res, upload_res

    def _do_enroll(self, student='ichigo'):
        enroll_url = '/dataserver2/CourseAdmin/UserCourseEnroll'
        data = {
            'username': student,
            'ntiid': self.course_ntiid,
            'scope': 'ForCredit'
        }
        return self.testapp.post_json(enroll_url,
                                      data,
                                      status=201)

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_post_put_delete_transcript(self):
        _, res = self.upload_transcript()
        assert_that(res.json_body,
                    has_entry('src', starts_with('/dataserver2/')))
        assert_that(res.json_body,
                    has_entry('srcjsonp', is_(none())))
        assert_that(res.json_body,
                    has_entry('CreatedTime', is_not(none())))
        assert_that(res.json_body,
                    has_entry('Last Modified', is_not(none())))
        assert_that(res.json_body,
                    has_entry('Creator', is_not(none())))
        ntiid = res.json_body['NTIID']

        self.require_link_href_with_rel(res.json_body, 'edit')

        with mock_dataserver.mock_db_trans(self.ds, site_name='janux.ou.edu'):
            transcript = find_object_with_ntiid(ntiid)
            assert_that(IUserCreatedTranscript.providedBy(transcript),
                        is_(True))

        # get contents
        href = res.json_body['src']
        res = self.testapp.get(href, status=200)

        student = 'ichigo'
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user(student)
        self._do_enroll(student)

        student_environ = self._make_extra_environ(username=student)
        self.testapp.get(href, status=200, extra_environ=student_environ)

        # update
        href = '/dataserver2/Objects/%s' % ntiid
        self.testapp.put(href,
                         upload_files=[
                            ('sample.vtt', 'sample.vtt', self.get_vtt_source())
                         ],
                         status=200)


        href = '/dataserver2/Objects/%s' % self.video_ntiid_cell
        res = self.testapp.get(href, status=200)
        assert_that(res.json_body, has_entry('transcripts', has_length(2)))

        href = '/dataserver2/Objects/%s' % ntiid
        self.testapp.delete(href, status=200)

        href = '/dataserver2/Objects/%s' % self.video_ntiid_cell
        res = self.testapp.get(href, status=200)
        assert_that(res.json_body, has_entry('transcripts', has_length(1)))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_clear_transcripts(self):
        res, _ = self.upload_transcript(self.video_ntiid_frogger)
        href = self.require_link_href_with_rel(res.json_body, 'clear_transcripts')
        res = self.testapp.post(href, status=200)
        assert_that(res.json_body, has_entry('Items', has_length(1)))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_delete_video(self):
        # Content backed cannot be deleted
        video = self.testapp.get('/dataserver2/Objects/%s' % self.video_ntiid_frogger)
        video = video.json_body
        self.forbid_link_with_rel(video, 'Delete')

        video = self._load_resource("ntivideo.json")
        for name in ('NTIID', 'ntiid',):
            video.pop(name, None)
        res = self.testapp.post_json(self.assets_url, video)
        res = res.json_body
        delete_href = self.require_link_href_with_rel(res, 'Delete')
        self.testapp.delete(delete_href)

        self.testapp.get(delete_href, status=404)


    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_create_video(self):
        video = self._load_resource("ntivideo.json")
        transcripts = video.pop('transcripts', None)
        for name in ('NTIID', 'ntiid',):
            video.pop(name, None)
        res = self.testapp.post_json(self.assets_url,
                                     video,
                                     status=201)
        ntiid = res.json_body['ntiid']

        # transcripts cannot be put
        video.pop('sources', None)
        video['transcripts'] = transcripts
        href = '/dataserver2/Objects/%s' % ntiid
        video_res = self.testapp.put_json(href, video, status=200)
        assert_that(video_res.json_body,
                    has_entry('transcripts', is_(none())))

        _, res = self.upload_transcript(ntiid, False)
        transcript_ntiid = res.json_body['NTIID']
        with mock_dataserver.mock_db_trans(self.ds, site_name='janux.ou.edu'):
            transcript = find_object_with_ntiid(transcript_ntiid)
            assert_that(IUserCreatedTranscript.providedBy(transcript),
                        is_(True))
