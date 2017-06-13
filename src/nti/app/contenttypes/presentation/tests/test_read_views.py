#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import greater_than

from nti.app.products.courseware.tests import InstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS


class TestReadViews(ApplicationLayerTest):

    layer = InstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    course_ntiid = u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'
    course_url = '/dataserver2/%2B%2Betc%2B%2Bhostsites/platform.ou.edu/%2B%2Betc%2B%2Bsite/Courses/Fall2015/CS%201323'
    assets_url = course_url + '/assets'

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_course_resolver(self):
        # get all assets
        assets_herf = '%s?accept=application/vnd.nextthought.ntilessonoverview' % self.assets_url
        res = self.testapp.get(assets_herf, status=200)
        assert_that(res.json_body,
                    has_entry('Items', has_length(greater_than(0))))
        # get first lesson and force-publish
        ntiid = res.json_body['Items'][0]['ntiid']
        href = '/dataserver2/Objects/%s/@@CourseResolver' % ntiid
        res = self.testapp.get(href, status=200)
        assert_that(res.json_body,
                    has_entry('Items', has_length(4)))
