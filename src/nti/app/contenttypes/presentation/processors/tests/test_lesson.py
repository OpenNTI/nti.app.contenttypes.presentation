#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import has_entry
from hamcrest import assert_that
from hamcrest import has_properties

from zope import component

from pyramid.testing import DummyRequest

from nti.app.contenttypes.presentation.interfaces import IPresentationAssetProcessor

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.contenttypes.presentation.group import NTICourseOverViewGroup

from nti.contenttypes.presentation.lesson import NTILessonOverView

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver


class TestLesson(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'
    entry_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'

    @classmethod
    def course_entry(cls):
        return find_object_with_ntiid(cls.entry_ntiid)

    @WithSharedApplicationMockDS(users=True, testapp=False)
    def test_handle_group(self):

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):

            course = ICourseInstance(self.course_entry())
            group = NTICourseOverViewGroup()

            lesson = NTILessonOverView()
            lesson.append(group)

            request = DummyRequest()
            processor = IPresentationAssetProcessor(lesson)
            processor.handle(lesson, course, "ichigo", request)

            assert_that(lesson,
                        has_properties('creator', "ichigo",
                                       "__parent__", is_(course)))

            assert_that(group,
                        has_properties('creator', "ichigo",
                                       "__parent__", is_(lesson)))

            container = IPresentationAssetContainer(course)
            assert_that(container,
                        has_entry(group.ntiid, is_(group)))
            assert_that(container,
                        has_entry(lesson.ntiid, is_(lesson)))
         
            reg = component.queryUtility(IPresentationAsset, group.ntiid)
            assert_that(reg, is_(group))
