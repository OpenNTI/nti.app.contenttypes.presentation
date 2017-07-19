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

from nti.externalization.representation import to_json_representation

from nti.app.products.courseware.tests import InstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS


class TestMediaViews(ApplicationLayerTest):

    layer = InstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    video_ntiid_02 = 'tag:nextthought.com,2011-10:OU-NTIVideo-CLC3403_LawAndJustice.ntivideo.video_17.02'
    legacy_transcript_ntiid = 'tag:nextthought.com,2011-10:OU-NTITranscript-CLC3403_LawAndJustice.ntivideo.video_17.02.0'

    video_ntiid_03 = 'tag:nextthought.com,2011-10:OU-NTIVideo-CLC3403_LawAndJustice.ntivideo.video_17.03'
    
    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_transcripts(self):
        href = '/dataserver2/Objects/%s' % self.video_ntiid_02
        res = self.testapp.get(href, status=200)
        href = self.require_link_href_with_rel(res.json_body, 'transcripts')
        res = self.testapp.get(href, status=200)
        assert_that(res.json_body, has_entry('Items', has_length(1)))

    def get_source(self):
        path = os.path.join(os.path.dirname(__file__), 'sample.vtt')
        with open(path, "r") as fp:
            source = fp.read()
        return source

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_put_transcript_403(self):
        href = '/dataserver2/Objects/%s' % self.legacy_transcript_ntiid
        self.testapp.put(href,
                         upload_files=[
                            ('sample.vtt', 'sample.vtt', self.get_source())
                         ],
                        status=403)
        
    def upload_transcript(self, video_ntiid=None):
        data = {
            'lang': 'en',
            'type': 'text/vtt',
            'purpose': 'normal', 
            'MimeType': 'application/vnd.nextthought.ntitranscript', 
        }
        video_ntiid = video_ntiid or self.video_ntiid_02
        href = '/dataserver2/Objects/%s' % video_ntiid
        video_res = self.testapp.get(href, status=200)
        assert_that(video_res.json_body, has_entry('transcripts', has_length(1)))
        
        href = self.require_link_href_with_rel(video_res.json_body, 'transcript')
        data = {'__json__': to_json_representation(data)}
        upload_res = self.testapp.post(href, data,
                                       upload_files=[
                                            ('sample.vtt', 'sample.vtt', self.get_source())
                                       ],
                                       status=200)
        return video_res, upload_res

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
        
        # update
        href = '/dataserver2/Objects/%s' % ntiid
        self.testapp.put(href,
                         upload_files=[
                            ('sample.vtt', 'sample.vtt', self.get_source())
                         ],
                         status=200)

        
        href = '/dataserver2/Objects/%s' % self.video_ntiid_02
        res = self.testapp.get(href, status=200)
        assert_that(res.json_body, has_entry('transcripts', has_length(2)))
        
        href = '/dataserver2/Objects/%s' % ntiid
        self.testapp.delete(href, status=200)
        
        href = '/dataserver2/Objects/%s' % self.video_ntiid_02
        res = self.testapp.get(href, status=200)
        assert_that(res.json_body, has_entry('transcripts', has_length(1)))
        
    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_clear_transcripts(self):
        res, _ = self.upload_transcript(self.video_ntiid_03)
        href = self.require_link_href_with_rel(res.json_body, 'clear_transcripts')        
        res = self.testapp.post(href, status=200)
        assert_that(res.json_body, has_entry('Items', has_length(1)))
