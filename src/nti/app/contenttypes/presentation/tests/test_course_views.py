#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import greater_than
from hamcrest import contains_inanyorder
does_not = is_not

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS


class TestCourseViews(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'
    entry_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_course_assets(self):
        href = '/dataserver2/Objects/%s/@@assets' % self.entry_ntiid
        res = self.testapp.get(href, status=200)
        assert_that(res.json_body,
                    has_entry('Items', has_length(greater_than(0))))
        
        href = '/dataserver2/Objects/%s/@@assets?accept=foo' % self.entry_ntiid
        res = self.testapp.get(href, status=200)
        assert_that(res.json_body,
                    has_entry('Items', has_length(0)))

        href = '/dataserver2/Objects/%s/@@assets?accept=application/vnd.nextthought.ntivideo' % self.entry_ntiid
        res = self.testapp.get(href, status=200).json_body
        assert_that(res, has_entry('Items', has_length(greater_than(0))))
        assert_that(res['Items'][0], has_entry('MimeType', 'application/vnd.nextthought.ntivideo'))

        href = '/dataserver2/Objects/%s/@@assets?accept=application/vnd.nextthought.questionsetref' % self.entry_ntiid
        res = self.testapp.get(href, status=200).json_body
        assert_that(res, has_entry('Items', has_length(greater_than(0))))
        assert_that(res['Items'][0], has_entry('MimeType', 'application/vnd.nextthought.questionsetref'))

        href = '/dataserver2/Objects/%s/@@assets?accept=application/vnd.nextthought.questionsetref,application/vnd.nextthought.ntivideo' % self.entry_ntiid
        res = self.testapp.get(href, status=200).json_body
        assert_that(set([x['MimeType'] for x in res['Items']]), contains_inanyorder('application/vnd.nextthought.ntivideo', 'application/vnd.nextthought.questionsetref'))
