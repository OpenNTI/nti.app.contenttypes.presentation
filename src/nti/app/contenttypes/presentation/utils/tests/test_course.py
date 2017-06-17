#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import assert_that
does_not = is_not

from nti.app.contenttypes.presentation.utils.course import get_entry_by_relative_path_parts
from nti.app.contenttypes.presentation.utils.course import get_course_by_relative_path_parts

from nti.app.products.courseware.tests import InstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver

class TestCourse(ApplicationLayerTest):

    layer = InstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    @WithSharedApplicationMockDS(testapp=False, users=False)
    def test_course_by_relative_path_parts(self):

        with mock_dataserver.mock_db_trans(self.ds, site_name='janux.ou.edu'):
            parts = ('Fall2015', 'CS 1323')
            course = get_course_by_relative_path_parts(parts)
            assert_that(course, is_not(none()))
            
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            parts = ('Fall2015', 'CS_1323')
            course = get_course_by_relative_path_parts(parts)
            assert_that(course, is_not(none()))
            
        with mock_dataserver.mock_db_trans(self.ds, site_name='janux.ou.edu'):
            parts = ('Fall2015', 'foo')
            entry = get_entry_by_relative_path_parts(parts)
            assert_that(entry, is_(none()))
