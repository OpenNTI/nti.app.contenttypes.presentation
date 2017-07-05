#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import greater_than
does_not = is_not

from zope import component

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation.group import NTICourseOverViewGroup

from nti.contenttypes.presentation.relatedwork import NTIRelatedWorkRef

from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.site.utils import registerUtility

from nti.app.products.courseware.tests import InstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver


class TestSyncViews(ApplicationLayerTest):

    layer = InstructedCourseApplicationTestLayer

    default_origin = 'http://platform.ou.edu'
    course_ntiid = u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_remove_invalid_assets(self):
        res = self.testapp.post('/dataserver2/@@RemoveInvalidPresentationAssets',
                                status=200)
        assert_that(res.json_body,
                    has_entry('Items', has_length(greater_than(0))))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_remove_inaccessible_assets(self):
        res = self.testapp.post('/dataserver2/@@RemoveCourseInaccessibleAssets',
                                status=200)
        assert_that(res.json_body,
                    has_entries('Difference', is_([]),
                                'Removed', has_length(0),
                                'Site', 'platform.ou.edu',
                                'TotalContainedAssets', greater_than(100),
                                'TotalRegisteredAssets', greater_than(100)))


    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_fix_all_inaccessible_assets(self):

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = find_object_with_ntiid(self.course_ntiid)
            course = ICourseInstance(entry)
            container = IPresentationAssetContainer(course)
            # asset to be skipped
            group = NTICourseOverViewGroup()
            container[group.ntiid] = group
            # asset in container not registered
            work = NTIRelatedWorkRef()
            container[work.ntiid] = work
            # asset registered not in containers
            work = NTIRelatedWorkRef()
            registerUtility(component.getSiteManager(),
                            work,
                            INTIRelatedWorkRef,
                            name=work.ntiid)

        res = self.testapp.post('/dataserver2/@@FixInaccessiblePresentationAssets',
                                status=200)
        assert_that(res.json_body,
                    has_entry('Items', 
                              has_entry('platform.ou.edu', has_length(2))))
