#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import not_none
from hamcrest import has_entry
from hamcrest import assert_that
from hamcrest import has_properties

from pyramid.testing import DummyRequest

from nti.app.contenttypes.presentation.interfaces import IPresentationAssetProcessor

from nti.app.products.courseware.resources.interfaces import ICourseSourceFiler

from nti.app.products.courseware.resources.model import CourseContentFile

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.contenttypes.presentation.relatedwork import NTIRelatedWorkRef

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver


class TestDocket(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'
    entry_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'

    @classmethod
    def course_entry(cls):
        return find_object_with_ntiid(cls.entry_ntiid)

    @WithSharedApplicationMockDS(users=False, testapp=False)
    def test_handle_docket(self):

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            course = ICourseInstance(self.course_entry())
            filer = ICourseSourceFiler(course)

            internal = CourseContentFile(filename=u'internal', data=b'')
            href = filer.save("internal", internal)

            workref = NTIRelatedWorkRef()
            workref.ntiid = u'tag:nextthought.com,2011-10:OU-RelatedWork-LSTD.relatedwork.1968'
            workref.href = href

            request = DummyRequest(post={'href': href})
            processor = IPresentationAssetProcessor(workref)
            processor.handle(workref, course, "ichigo", request)

            assert_that(workref,
                        has_properties('creator', "ichigo",
                                       "href", is_(href),
                                       "__parent__", is_(course),
                                       "type", is_('application/octet-stream'),
                                       "target", is_(not_none())))
            container = IPresentationAssetContainer(course)
            assert_that(container,
                        has_entry(workref.ntiid, workref))
