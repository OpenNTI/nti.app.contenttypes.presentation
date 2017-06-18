#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import greater_than
does_not = is_not

from zope import component

from zope.intid.interfaces import IIntIds

from nti.app.contenttypes.presentation.utils.asset import make_asset_ntiid

from nti.app.contenttypes.presentation.utils.common import remove_invalid_assets
from nti.app.contenttypes.presentation.utils.common import remove_course_inaccessible_assets

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation.assessment import NTIAssignmentRef

from nti.contenttypes.presentation.interfaces import INTIAssignmentRef
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.contenttypes.presentation.lesson import NTILessonOverView

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.site.utils import registerUtility

from nti.app.products.courseware.tests import InstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver


class TestCommon(ApplicationLayerTest):

    layer = InstructedCourseApplicationTestLayer

    default_origin = 'http://platform.ou.edu'
    entry_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_remove_invalid_assets(self):
        # add invalid assets
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            intids = component.getUtility(IIntIds)
            # asset w/o doc id
            asset = NTILessonOverView()
            asset.ntiid = make_asset_ntiid(INTILessonOverview)
            registerUtility(component.getSiteManager(),
                            asset,
                            INTILessonOverview,
                            name=asset.ntiid)
            # container w/o parent
            asset = NTILessonOverView()
            intids.register(asset)
            asset.ntiid = make_asset_ntiid(INTILessonOverview)
            registerUtility(component.getSiteManager(),
                            asset,
                            INTILessonOverview,
                            name=asset.ntiid)
            # Invalid asset ref
            asset = NTIAssignmentRef()
            intids.register(asset)
            asset.ntiid = make_asset_ntiid(INTIAssignmentRef)
            asset.target = 'foo'
            registerUtility(component.getSiteManager(),
                            asset,
                            INTIAssignmentRef,
                            name=asset.ntiid)

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            removed, seen = remove_invalid_assets()
            assert_that(removed, has_length(3))
            assert_that(seen, has_length(greater_than(0)))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_remove_inaccessible_assets(self):
        # add invalid assets
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = find_object_with_ntiid(self.entry_ntiid)
            course = ICourseInstance(entry)
            container = IPresentationAssetContainer(course)
            intids = component.getUtility(IIntIds)
            # asset not in registry
            asset = NTILessonOverView()
            intids.register(asset)
            asset.ntiid = make_asset_ntiid(INTILessonOverview)
            container[asset.ntiid] = asset
            # asset without doc_id
            asset = NTILessonOverView()
            asset.ntiid = make_asset_ntiid(INTILessonOverview)
            container[asset.ntiid] = asset
            registerUtility(component.getSiteManager(),
                            asset,
                            INTILessonOverview,
                            name=asset.ntiid)
            # asset w/o parent
            asset = NTILessonOverView()
            intids.register(asset)
            asset.ntiid = make_asset_ntiid(INTILessonOverview)
            registerUtility(component.getSiteManager(),
                            asset,
                            INTILessonOverview,
                            name=asset.ntiid)
            container[asset.ntiid] = asset
            # not in master
            asset = NTILessonOverView()
            intids.register(asset)
            asset.ntiid = make_asset_ntiid(INTILessonOverview)
            registerUtility(component.getSiteManager(),
                            asset,
                            INTILessonOverview,
                            name=asset.ntiid)
            # invalid in catalog
            asset = NTILessonOverView()
            intids.register(asset)
            asset.ntiid = make_asset_ntiid(INTILessonOverview)
            catalog = get_library_catalog()
            catalog.index(asset, sites='platform.ou.edu')

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            result = remove_course_inaccessible_assets()
            assert_that(result,
                        has_entries('Difference', is_([]),
                                    'Removed', has_length(5),
                                    'Site', 'platform.ou.edu',
                                    'TotalContainedAssets', greater_than(100),
                                    'TotalRegisteredAssets', greater_than(100)))
