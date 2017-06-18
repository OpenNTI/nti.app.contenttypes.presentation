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

from nti.app.products.courseware.tests import InstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS


class TestAdminViews(ApplicationLayerTest):

    layer = InstructedCourseApplicationTestLayer

    default_origin = 'http://platform.ou.edu'

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
    def test_rebuild_asset_catalog(self):
        res = self.testapp.post('/dataserver2/@@RebuildPresentationAssetCatalog',
                                status=200)
        assert_that(res.json_body,
                    has_entries('Total', is_(greater_than(0)),
                                'ItemCount', is_(greater_than(0))))
