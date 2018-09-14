#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods

from hamcrest import is_
from hamcrest import is_not
from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import greater_than
does_not = is_not

from zope import component

from zope.intid.interfaces import IIntIds

from nti.app.products.courseware.tests import InstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.contenttypes.presentation.lesson import LessonConstraintContainer
from nti.contenttypes.presentation.lesson import AssignmentCompletionConstraint

from nti.dataserver.metadata.index import get_metadata_catalog

from nti.dataserver.tests.mock_dataserver import mock_db_trans


class TestAdminViews(ApplicationLayerTest):

    layer = InstructedCourseApplicationTestLayer

    default_origin = 'http://platform.ou.edu'

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_rebuild_asset_catalog(self):
        res = self.testapp.post('/dataserver2/@@RebuildPresentationAssetCatalog',
                                status=200)
        assert_that(res.json_body,
                    has_entries('Total', is_(greater_than(1000)),
                                'ItemCount', is_(greater_than(1000))))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_remove_invalid_constraints(self):
        
        with mock_db_trans() as conn:
            intids = component.getUtility(IIntIds)

            # sample meeting
            container = LessonConstraintContainer()
            conn.add(container)
            
            constraint = AssignmentCompletionConstraint()
            conn.add(constraint)
            container.append(constraint)

            # index
            doc_id = intids.getId(constraint)
            get_metadata_catalog().index_doc(doc_id, constraint)

        res = self.testapp.post('/dataserver2/@@RemoveInvalidLessonConstraints',
                                status=200)
        assert_that(res.json_body,
                    has_entries('RemovedCount', is_(1)))
