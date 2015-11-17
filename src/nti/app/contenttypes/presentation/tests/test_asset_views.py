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

import os

import simplejson

from nti.contenttypes.presentation.utils import prepare_json_text

from nti.app.testing.decorators import WithSharedApplicationMockDS
from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.dataserver.tests import mock_dataserver

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.app.products.courseware.tests import InstructedCourseApplicationTestLayer

class TestAssetViews(ApplicationLayerTest):

    layer = InstructedCourseApplicationTestLayer

    default_origin = b'http://janux.ou.edu'

    course_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'
    course_url = '/dataserver2/%2B%2Betc%2B%2Bhostsites/platform.ou.edu/%2B%2Betc%2B%2Bsite/Courses/Fall2015/CS%201323'

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_post_ntivideo(self):
        path = os.path.join(os.path.dirname(__file__), 'ntivideo.json')
        with open(path, "r") as fp:
            source = simplejson.loads(prepare_json_text(fp.read()))
        source.pop('ntiid',  None)
        assets_url = self.course_url + '/assets'
        res = self.testapp.post_json(assets_url, source)
        print(res.json_body)
