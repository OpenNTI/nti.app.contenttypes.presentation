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

import fudge

from zope import component

from pyramid.testing import DummyRequest

from nti.app.contenttypes.presentation.interfaces import IPresentationAssetProcessor

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import IPresentationAssetContainer

from nti.contenttypes.presentation.media import NTIVideoRef
from nti.contenttypes.presentation.media import NTIVideoRoll

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver


class TestMedia(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'
    entry_ntiid = 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'

    @classmethod
    def course_entry(cls):
        return find_object_with_ntiid(cls.entry_ntiid)

    @WithSharedApplicationMockDS(users=True, testapp=False)
    @fudge.patch("nti.app.contenttypes.presentation.processors.group.get_remote_user")
    def test_handle_roll(self, mock_grm):

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            user = self._get_user(self.default_username)
            mock_grm.is_callable().with_args().returns(user)

            course = ICourseInstance(self.course_entry())
            roll = NTIVideoRoll()

            vid_ref = NTIVideoRef()
            vid_ref.target = u"tag:nextthought.com,2011-10:OU-NTISlideVideo-CS1323_S_2015_Intro_to_Computer_Programming.nsd.pres:Install_Mac_video"
            roll.append(vid_ref)

            request = DummyRequest()
            processor = IPresentationAssetProcessor(roll)
            processor.handle(roll, course, "ichigo", request)

            assert_that(roll,
                        has_properties('creator', "ichigo",
                                       "__parent__", is_(course)))

            assert_that(vid_ref,
                        has_properties('creator', "ichigo",
                                       "__parent__", is_(roll)))

            container = IPresentationAssetContainer(course)
            assert_that(container,
                        has_entry(roll.ntiid, is_(roll)))
            assert_that(container,
                        has_entry(vid_ref.ntiid, is_(vid_ref)))

            reg = component.queryUtility(IPresentationAsset, vid_ref.ntiid)
            assert_that(reg, is_(vid_ref))
