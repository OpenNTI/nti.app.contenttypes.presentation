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
does_not = is_not

import os

from nti.externalization.representation import to_json_representation

from nti.app.products.courseware.tests import InstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS


class TestMediaViews(ApplicationLayerTest):

    layer = InstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    video_ntiid = 'tag:nextthought.com,2011-10:OU-NTIVideo-CLC3403_LawAndJustice.ntivideo.video_17.02'
    transcript_ntiid = 'tag:nextthought.com,2011-10:OU-NTITranscript-CLC3403_LawAndJustice.ntivideo.video_17.02.0'

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_transcripts(self):
        href = '/dataserver2/Objects/%s' % self.video_ntiid
        res = self.testapp.get(href, status=200)
        href = self.require_link_href_with_rel(res.json_body, 'transcripts')
        res = self.testapp.get(href, status=200)
        assert_that(res.json_body, has_entry('Items', has_length(1)))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_put_transcript(self):
        href = '/dataserver2/Objects/%s' % self.transcript_ntiid
        path = os.path.join(os.path.dirname(__file__), 'sample.vtt')
        with open(path, "r") as fp:
            source = fp.read()
        res = self.testapp.put(href,
                               upload_files=[
                                   ('sample.vtt', 'sample.vtt', source)
                               ],
                               status=200)
        assert_that(res.json_body,
                    has_entry('src', has_entry('Class', 'ContentBlobFile')))
        assert_that(res.json_body,
                    has_entry('srcjsonp', is_(none())))
        
    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_post_transcript(self):
        data = {
            'lang': 'en',
            'type': 'text/vtt',
            'purpose': 'normal', 
            'MimeType': 'application/vnd.nextthought.ntitranscript', 
        }
        href = '/dataserver2/Objects/%s' % self.video_ntiid
        res = self.testapp.get(href, status=200)
        href = self.require_link_href_with_rel(res.json_body, 'transcript')
        path = os.path.join(os.path.dirname(__file__), 'sample.vtt')
        with open(path, "r") as fp:
            source = fp.read()
        data = {'__json__': to_json_representation(data)}
        res = self.testapp.post(href, data,
                                upload_files=[
                                       ('sample.vtt', 'sample.vtt', source)
                                ],
                                status=200)
        assert_that(res.json_body,
                    has_entry('src', has_entry('Class', 'ContentBlobFile')))
        assert_that(res.json_body,
                    has_entry('srcjsonp', is_(none())))
